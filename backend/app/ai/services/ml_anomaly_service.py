"""
ML-Enhanced Anomaly Detection Service (Phase 4)

Advanced anomaly detection using machine learning:
- Isolation Forest for statistical anomaly detection
- User behavioral baselines
- Burnout risk prediction
- Pattern learning and personalization
"""

import logging
import pickle
from typing import List, Dict, Any, Optional, Tuple, TypedDict, TYPE_CHECKING
from datetime import datetime, date, timedelta
from enum import Enum
from dataclasses import dataclass, field
import json
import statistics
from collections import defaultdict


class DailyEntryData(TypedDict):
    """Type definition for daily entry aggregation."""
    hours: float
    entries: List[Any]  # TimeEntry objects
    start_times: List[float]
    end_times: List[float]
    projects: List[str]

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.config import ai_settings
from app.ai.utils.cache_manager import AICacheManager, get_cache_manager
from app.services.ai_feature_service import AIFeatureManager

logger = logging.getLogger(__name__)

# Type stubs for optional ML libraries
if TYPE_CHECKING:
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

# Runtime placeholders
np: Any = None
IsolationForest: Any = None
StandardScaler: Any = None

# Try to import ML libraries - graceful fallback if not installed
try:
    import numpy as np  # type: ignore[no-redef]
    from sklearn.ensemble import IsolationForest  # type: ignore[no-redef]
    from sklearn.preprocessing import StandardScaler  # type: ignore[no-redef]
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("scikit-learn not installed. ML anomaly detection disabled.")


class MLAnomalyType(str, Enum):
    """Types of ML-detected anomalies."""
    STATISTICAL_OUTLIER = "statistical_outlier"
    PATTERN_DEVIATION = "pattern_deviation"
    BEHAVIORAL_CHANGE = "behavioral_change"
    BURNOUT_RISK = "burnout_risk"
    WORKLOAD_IMBALANCE = "workload_imbalance"
    TIME_PATTERN_ANOMALY = "time_pattern_anomaly"


class RiskLevel(str, Enum):
    """Risk levels for burnout prediction."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class UserBaseline:
    """User's behavioral baseline."""
    user_id: int
    avg_daily_hours: float
    std_daily_hours: float
    avg_weekly_hours: float
    typical_start_hour: float
    typical_end_hour: float
    preferred_days: List[int]  # 0=Monday, 6=Sunday
    project_distribution: Dict[str, float]
    avg_entry_duration: float
    entries_per_day: float
    calculated_at: datetime
    data_points: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "avg_daily_hours": round(self.avg_daily_hours, 2),
            "std_daily_hours": round(self.std_daily_hours, 2),
            "avg_weekly_hours": round(self.avg_weekly_hours, 2),
            "typical_start_hour": round(self.typical_start_hour, 1),
            "typical_end_hour": round(self.typical_end_hour, 1),
            "preferred_days": self.preferred_days,
            "avg_entry_duration": round(self.avg_entry_duration, 1),
            "entries_per_day": round(self.entries_per_day, 1),
            "calculated_at": self.calculated_at.isoformat(),
            "data_points": self.data_points
        }


@dataclass
class BurnoutRiskAssessment:
    """Burnout risk assessment result."""
    user_id: int
    user_name: str
    risk_level: RiskLevel
    risk_score: float  # 0-100
    factors: List[Dict[str, Any]]
    recommendations: List[str]
    trend: str  # "improving", "stable", "worsening"
    assessed_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "risk_level": self.risk_level.value,
            "risk_score": round(self.risk_score, 1),
            "factors": self.factors,
            "recommendations": self.recommendations,
            "trend": self.trend,
            "assessed_at": self.assessed_at.isoformat()
        }


@dataclass
class MLAnomaly:
    """ML-detected anomaly."""
    type: MLAnomalyType
    severity: str  # "info", "warning", "critical"
    user_id: int
    user_name: str
    description: str
    confidence: float
    detected_at: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    recommendation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "severity": self.severity,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "description": self.description,
            "confidence": round(self.confidence, 2),
            "detected_at": self.detected_at.isoformat(),
            "details": self.details,
            "recommendation": self.recommendation
        }


class MLAnomalyService:
    """
    ML-enhanced anomaly detection service.
    
    Uses Isolation Forest for statistical anomaly detection
    and behavioral baselines for personalized analysis.
    """
    
    # Feature names for the model
    FEATURE_NAMES = [
        "daily_hours",
        "entry_count",
        "avg_entry_duration",
        "start_hour",
        "end_hour",
        "span_hours",  # end - start
        "weekend_flag",
        "consecutive_days",
        "hours_deviation",  # from baseline
        "time_deviation"  # from typical schedule
    ]
    
    def __init__(
        self,
        db: AsyncSession,
        cache_manager: Optional[AICacheManager] = None
    ):
        self.db = db
        self.cache = cache_manager
        self._feature_manager: Optional[AIFeatureManager] = None
        self._models: Dict[int, Any] = {}  # Per-user Isolation Forest models
        self._baselines: Dict[int, UserBaseline] = {}
        self._scaler: Optional[Any] = StandardScaler() if ML_AVAILABLE else None
        
        # Configuration
        self.contamination = 0.1  # Expected anomaly rate
        self.min_samples_for_model = 30  # Minimum entries for ML
        self.baseline_days = 30  # Days for baseline calculation
        self.burnout_threshold = 70  # Risk score threshold

    async def _get_feature_manager(self) -> AIFeatureManager:
        """Get feature manager instance."""
        if self._feature_manager is None:
            self._feature_manager = AIFeatureManager(self.db)
        return self._feature_manager

    # ============================================
    # BASELINE MANAGEMENT
    # ============================================
    
    async def calculate_user_baseline(
        self,
        user_id: int,
        period_days: int = 30
    ) -> UserBaseline:
        """Calculate behavioral baseline for a user."""
        from app.models import User, TimeEntry
        
        # Get user
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        period_start = datetime.now() - timedelta(days=period_days)
        
        # Get time entries
        entries_result = await self.db.execute(
            select(TimeEntry)
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    TimeEntry.start_time >= period_start,
                    TimeEntry.is_running == False
                )
            )
            .order_by(TimeEntry.start_time)
        )
        entries = entries_result.scalars().all()
        
        if not entries:
            # Return default baseline
            return UserBaseline(
                user_id=user_id,
                avg_daily_hours=8.0,
                std_daily_hours=1.5,
                avg_weekly_hours=40.0,
                typical_start_hour=9.0,
                typical_end_hour=17.0,
                preferred_days=[0, 1, 2, 3, 4],
                project_distribution={},
                avg_entry_duration=60.0,
                entries_per_day=3.0,
                calculated_at=datetime.now(),
                data_points=0
            )
        
        # Group by date - explicitly typed
        def create_daily_entry() -> DailyEntryData:
            return {
                "hours": 0.0,
                "entries": [],
                "start_times": [],
                "end_times": [],
                "projects": []
            }
        
        daily_data: Dict[date, DailyEntryData] = defaultdict(create_daily_entry)
        
        for entry in entries:
            day_key = entry.start_time.date()
            duration_hours = (entry.duration_seconds or 0) / 3600
            daily_data[day_key]["hours"] += duration_hours
            daily_data[day_key]["entries"].append(entry)
            daily_data[day_key]["start_times"].append(entry.start_time.hour + entry.start_time.minute / 60)
            if entry.end_time:
                daily_data[day_key]["end_times"].append(entry.end_time.hour + entry.end_time.minute / 60)
            if entry.project_id:
                daily_data[day_key]["projects"].append(str(entry.project_id))
        
        # Calculate statistics
        daily_hours = [d["hours"] for d in daily_data.values() if d["hours"] > 0]
        
        avg_daily = statistics.mean(daily_hours) if daily_hours else 8.0
        std_daily = statistics.stdev(daily_hours) if len(daily_hours) > 1 else 1.5
        
        # Weekly hours
        weeks = defaultdict(float)
        for day, data in daily_data.items():
            week_num = day.isocalendar()[1]
            weeks[week_num] += data["hours"]
        weekly_hours = list(weeks.values())
        avg_weekly = statistics.mean(weekly_hours) if weekly_hours else 40.0
        
        # Typical times
        all_starts = []
        all_ends = []
        for data in daily_data.values():
            all_starts.extend(data["start_times"])
            all_ends.extend(data["end_times"])
        
        typical_start = statistics.mean(all_starts) if all_starts else 9.0
        typical_end = statistics.mean(all_ends) if all_ends else 17.0
        
        # Preferred days (days with most entries)
        day_counts = defaultdict(int)
        for day in daily_data.keys():
            day_counts[day.weekday()] += 1
        preferred = sorted(day_counts.keys(), key=lambda x: day_counts[x], reverse=True)[:5]
        
        # Project distribution
        all_projects = []
        for data in daily_data.values():
            all_projects.extend(data["projects"])
        project_counts = defaultdict(int)
        for p in all_projects:
            project_counts[p] += 1
        total_projects = len(all_projects) or 1
        project_dist = {k: v / total_projects for k, v in project_counts.items()}
        
        # Entry statistics
        all_entries = [e for d in daily_data.values() for e in d["entries"]]
        durations = [(e.duration_seconds or 0) / 60 for e in all_entries]  # in minutes
        avg_duration = statistics.mean(durations) if durations else 60.0
        entries_per_day = len(all_entries) / len(daily_data) if daily_data else 3.0
        
        baseline = UserBaseline(
            user_id=user_id,
            avg_daily_hours=avg_daily,
            std_daily_hours=std_daily,
            avg_weekly_hours=avg_weekly,
            typical_start_hour=typical_start,
            typical_end_hour=typical_end,
            preferred_days=preferred,
            project_distribution=project_dist,
            avg_entry_duration=avg_duration,
            entries_per_day=entries_per_day,
            calculated_at=datetime.now(),
            data_points=len(all_entries)
        )
        
        # Cache baseline
        self._baselines[user_id] = baseline
        
        return baseline

    async def get_user_baseline(self, user_id: int) -> UserBaseline:
        """Get cached or calculate user baseline."""
        if user_id in self._baselines:
            # Check if baseline is fresh (less than 1 day old)
            baseline = self._baselines[user_id]
            if (datetime.now() - baseline.calculated_at).days < 1:
                return baseline
        
        return await self.calculate_user_baseline(user_id)

    # ============================================
    # ML ANOMALY DETECTION
    # ============================================
    
    async def _build_feature_vector(
        self,
        entries: List[Any],
        baseline: UserBaseline
    ) -> Optional[List[float]]:
        """Build feature vector for a day's entries."""
        if not entries:
            return None
        
        # Calculate daily metrics
        total_hours = sum((e.duration_seconds or 0) / 3600 for e in entries)
        entry_count = len(entries)
        avg_duration = statistics.mean([(e.duration_seconds or 0) / 60 for e in entries])
        
        start_times = [e.start_time.hour + e.start_time.minute / 60 for e in entries]
        end_times = [
            (e.end_time.hour + e.end_time.minute / 60) if e.end_time 
            else (e.start_time.hour + (e.duration_seconds or 0) / 3600)
            for e in entries
        ]
        
        start_hour = min(start_times)
        end_hour = max(end_times)
        span_hours = end_hour - start_hour
        
        # Day of week
        day = entries[0].start_time.date()
        weekend_flag = 1 if day.weekday() >= 5 else 0
        
        # Consecutive work days (simplified)
        consecutive_days = 1  # Would need more context
        
        # Deviation from baseline
        hours_deviation = (total_hours - baseline.avg_daily_hours) / (baseline.std_daily_hours or 1)
        time_deviation = abs(start_hour - baseline.typical_start_hour) / 2  # Normalized
        
        return [
            total_hours,
            entry_count,
            avg_duration,
            start_hour,
            end_hour,
            span_hours,
            weekend_flag,
            consecutive_days,
            hours_deviation,
            time_deviation
        ]

    async def train_user_model(
        self,
        user_id: int,
        period_days: int = 90
    ) -> Dict[str, Any]:
        """Train Isolation Forest model for user."""
        if not ML_AVAILABLE:
            return {
                "success": False,
                "error": "ML libraries not installed"
            }
        
        from app.models import TimeEntry
        
        period_start = datetime.now() - timedelta(days=period_days)
        
        # Get time entries
        entries_result = await self.db.execute(
            select(TimeEntry)
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    TimeEntry.start_time >= period_start,
                    TimeEntry.is_running == False
                )
            )
            .order_by(TimeEntry.start_time)
        )
        entries = list(entries_result.scalars().all())
        
        if len(entries) < self.min_samples_for_model:
            return {
                "success": False,
                "error": f"Insufficient data. Need {self.min_samples_for_model} entries, have {len(entries)}"
            }
        
        # Get baseline
        baseline = await self.get_user_baseline(user_id)
        
        # Group entries by day
        daily_entries = defaultdict(list)
        for entry in entries:
            day_key = entry.start_time.date()
            daily_entries[day_key].append(entry)
        
        # Build feature matrix
        feature_vectors = []
        for day_entries in daily_entries.values():
            vector = await self._build_feature_vector(day_entries, baseline)
            if vector:
                feature_vectors.append(vector)
        
        if len(feature_vectors) < 10:
            return {
                "success": False,
                "error": "Not enough days with data for training"
            }
        
        # Train model
        X = np.array(feature_vectors)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        model = IsolationForest(
            contamination=self.contamination,
            random_state=42,
            n_estimators=100
        )
        model.fit(X_scaled)
        
        # Store model and scaler
        self._models[user_id] = {
            "model": model,
            "scaler": scaler,
            "trained_at": datetime.now(),
            "samples": len(feature_vectors)
        }
        
        return {
            "success": True,
            "samples_used": len(feature_vectors),
            "trained_at": datetime.now().isoformat()
        }

    async def detect_ml_anomalies(
        self,
        user_id: int,
        period_days: int = 7
    ) -> List[MLAnomaly]:
        """Detect anomalies using ML model."""
        from app.models import User, TimeEntry
        
        anomalies = []
        
        # Get user info
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            return anomalies
        
        # Get baseline
        baseline = await self.get_user_baseline(user_id)
        
        # Check if we have a trained model
        if user_id not in self._models and ML_AVAILABLE:
            # Try to train one
            train_result = await self.train_user_model(user_id)
            if not train_result.get("success"):
                logger.info(f"No ML model for user {user_id}: {train_result.get('error')}")
        
        period_start = datetime.now() - timedelta(days=period_days)
        
        # Get recent entries
        entries_result = await self.db.execute(
            select(TimeEntry)
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    TimeEntry.start_time >= period_start,
                    TimeEntry.is_running == False
                )
            )
            .order_by(TimeEntry.start_time)
        )
        entries = list(entries_result.scalars().all())
        
        # Group by day
        daily_entries = defaultdict(list)
        for entry in entries:
            day_key = entry.start_time.date()
            daily_entries[day_key].append(entry)
        
        # ML-based detection
        if user_id in self._models and ML_AVAILABLE:
            model_data = self._models[user_id]
            model = model_data["model"]
            scaler = model_data["scaler"]
            
            for day, day_entries in daily_entries.items():
                vector = await self._build_feature_vector(day_entries, baseline)
                if vector:
                    X = np.array([vector])
                    X_scaled = scaler.transform(X)
                    prediction = model.predict(X_scaled)[0]
                    score = model.decision_function(X_scaled)[0]
                    
                    if prediction == -1:  # Anomaly detected
                        confidence = min(1.0, abs(score) * 2)
                        severity = "warning" if confidence < 0.7 else "critical"
                        
                        # Determine anomaly type
                        total_hours = vector[0]
                        if total_hours > baseline.avg_daily_hours + 2 * baseline.std_daily_hours:
                            anomaly_type = MLAnomalyType.STATISTICAL_OUTLIER
                            description = f"Unusually high hours ({total_hours:.1f}h) detected on {day}"
                        elif abs(vector[3] - baseline.typical_start_hour) > 3:
                            anomaly_type = MLAnomalyType.TIME_PATTERN_ANOMALY
                            description = f"Unusual work time pattern on {day}"
                        else:
                            anomaly_type = MLAnomalyType.PATTERN_DEVIATION
                            description = f"Work pattern deviation detected on {day}"
                        
                        anomalies.append(MLAnomaly(
                            type=anomaly_type,
                            severity=severity,
                            user_id=user_id,
                            user_name=user.name,
                            description=description,
                            confidence=confidence,
                            detected_at=datetime.now(),
                            details={
                                "date": day.isoformat(),
                                "hours": round(total_hours, 1),
                                "baseline_avg": round(baseline.avg_daily_hours, 1),
                                "anomaly_score": round(score, 3)
                            },
                            recommendation=self._get_recommendation(anomaly_type, vector, baseline)
                        ))
        
        # Rule-based behavioral detection (always run)
        anomalies.extend(await self._detect_behavioral_anomalies(
            user_id, user.name, daily_entries, baseline
        ))
        
        return anomalies

    async def _detect_behavioral_anomalies(
        self,
        user_id: int,
        user_name: str,
        daily_entries: Dict[date, List[Any]],
        baseline: UserBaseline
    ) -> List[MLAnomaly]:
        """Detect behavioral anomalies without ML."""
        anomalies = []
        
        # Check for workload imbalance
        if daily_entries:
            daily_hours = [
                sum((e.duration_seconds or 0) / 3600 for e in entries)
                for entries in daily_entries.values()
            ]
            
            if daily_hours:
                max_hours = max(daily_hours)
                min_hours = min(daily_hours) if min(daily_hours) > 0 else 0.1
                imbalance_ratio = max_hours / min_hours
                
                if imbalance_ratio > 3:
                    anomalies.append(MLAnomaly(
                        type=MLAnomalyType.WORKLOAD_IMBALANCE,
                        severity="warning",
                        user_id=user_id,
                        user_name=user_name,
                        description=f"Significant workload imbalance detected (ratio: {imbalance_ratio:.1f}x)",
                        confidence=min(1.0, imbalance_ratio / 5),
                        detected_at=datetime.now(),
                        details={
                            "max_hours": round(max_hours, 1),
                            "min_hours": round(min_hours, 1),
                            "imbalance_ratio": round(imbalance_ratio, 1)
                        },
                        recommendation="Consider redistributing tasks for more balanced workload"
                    ))
        
        # Check for behavioral change (compared to baseline)
        if baseline.data_points > 0:
            recent_avg = statistics.mean([
                sum((e.duration_seconds or 0) / 3600 for e in entries)
                for entries in daily_entries.values()
            ]) if daily_entries else 0
            
            deviation = abs(recent_avg - baseline.avg_daily_hours)
            if deviation > baseline.std_daily_hours * 2:
                change_direction = "increase" if recent_avg > baseline.avg_daily_hours else "decrease"
                anomalies.append(MLAnomaly(
                    type=MLAnomalyType.BEHAVIORAL_CHANGE,
                    severity="info",
                    user_id=user_id,
                    user_name=user_name,
                    description=f"Significant {change_direction} in daily hours detected",
                    confidence=min(1.0, deviation / (baseline.std_daily_hours * 3)),
                    detected_at=datetime.now(),
                    details={
                        "baseline_avg": round(baseline.avg_daily_hours, 1),
                        "recent_avg": round(recent_avg, 1),
                        "change": round(recent_avg - baseline.avg_daily_hours, 1)
                    },
                    recommendation=f"Review recent workload changes that may explain this {change_direction}"
                ))
        
        return anomalies

    def _get_recommendation(
        self,
        anomaly_type: MLAnomalyType,
        vector: List[float],
        baseline: UserBaseline
    ) -> str:
        """Generate recommendation based on anomaly type."""
        if anomaly_type == MLAnomalyType.STATISTICAL_OUTLIER:
            return "Review time entries for accuracy and consider if overtime was planned"
        elif anomaly_type == MLAnomalyType.TIME_PATTERN_ANOMALY:
            return "Unusual working hours detected. Ensure work-life balance is maintained"
        elif anomaly_type == MLAnomalyType.PATTERN_DEVIATION:
            return "Work pattern differs from your typical behavior. Verify entries are correct"
        else:
            return "Review recent time entries for any irregularities"

    # ============================================
    # BURNOUT RISK PREDICTION
    # ============================================
    
    async def assess_burnout_risk(
        self,
        user_id: int,
        period_days: int = 30
    ) -> BurnoutRiskAssessment:
        """Assess burnout risk for a user."""
        from app.models import User, TimeEntry
        
        # Get user
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Get baseline and recent data
        baseline = await self.get_user_baseline(user_id)
        period_start = datetime.now() - timedelta(days=period_days)
        
        entries_result = await self.db.execute(
            select(TimeEntry)
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    TimeEntry.start_time >= period_start,
                    TimeEntry.is_running == False
                )
            )
            .order_by(TimeEntry.start_time)
        )
        entries = list(entries_result.scalars().all())
        
        # Group by day
        daily_entries = defaultdict(list)
        for entry in entries:
            day_key = entry.start_time.date()
            daily_entries[day_key].append(entry)
        
        # Calculate risk factors
        factors = []
        risk_score = 0
        
        # Factor 1: Overtime frequency
        overtime_days = 0
        daily_hours_list = []
        for day, day_entries in daily_entries.items():
            hours = sum((e.duration_seconds or 0) / 3600 for e in day_entries)
            daily_hours_list.append(hours)
            if hours > 9:  # More than 9 hours is overtime
                overtime_days += 1
        
        overtime_rate = overtime_days / max(len(daily_entries), 1)
        overtime_score = min(30, overtime_rate * 100)
        risk_score += overtime_score
        factors.append({
            "name": "Overtime Frequency",
            "score": round(overtime_score, 1),
            "max_score": 30,
            "detail": f"{overtime_days} overtime days out of {len(daily_entries)} work days"
        })
        
        # Factor 2: Weekend work
        weekend_days = sum(
            1 for day in daily_entries.keys()
            if day.weekday() >= 5
        )
        weekend_score = min(20, weekend_days * 5)
        risk_score += weekend_score
        factors.append({
            "name": "Weekend Work",
            "score": round(weekend_score, 1),
            "max_score": 20,
            "detail": f"{weekend_days} weekend days worked"
        })
        
        # Factor 3: Late work hours
        late_entries = sum(
            1 for entries in daily_entries.values()
            for e in entries
            if e.end_time and e.end_time.hour >= 20
        )
        late_score = min(20, late_entries * 2)
        risk_score += late_score
        factors.append({
            "name": "Late Work Hours",
            "score": round(late_score, 1),
            "max_score": 20,
            "detail": f"{late_entries} entries ending after 8 PM"
        })
        
        # Factor 4: Hours variance (inconsistent schedule)
        hours_std = 0.0
        if len(daily_hours_list) > 1:
            hours_std = statistics.stdev(daily_hours_list)
            variance_score = min(15, hours_std * 3)
        else:
            variance_score = 0
        risk_score += variance_score
        factors.append({
            "name": "Schedule Inconsistency",
            "score": round(variance_score, 1),
            "max_score": 15,
            "detail": f"Hours standard deviation: {hours_std:.1f}" if len(daily_hours_list) > 1 else "N/A"
        })
        
        # Factor 5: No days off
        work_streak = 0
        max_streak = 0
        current_date = date.today()
        for i in range(period_days):
            check_date = current_date - timedelta(days=i)
            if check_date in daily_entries:
                work_streak += 1
                max_streak = max(max_streak, work_streak)
            else:
                work_streak = 0
        
        streak_score = min(15, max(0, max_streak - 5) * 3)
        risk_score += streak_score
        factors.append({
            "name": "Consecutive Work Days",
            "score": round(streak_score, 1),
            "max_score": 15,
            "detail": f"Longest work streak: {max_streak} days"
        })
        
        # Determine risk level
        if risk_score < 30:
            risk_level = RiskLevel.LOW
        elif risk_score < 50:
            risk_level = RiskLevel.MODERATE
        elif risk_score < 70:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL
        
        # Generate recommendations
        recommendations = []
        if overtime_score > 15:
            recommendations.append("Consider delegating tasks to reduce overtime frequency")
        if weekend_score > 10:
            recommendations.append("Try to avoid weekend work to maintain work-life balance")
        if late_score > 10:
            recommendations.append("Set boundaries for work hours to avoid late-night work")
        if variance_score > 10:
            recommendations.append("Establish a more consistent daily schedule")
        if streak_score > 10:
            recommendations.append("Ensure regular days off to prevent exhaustion")
        if not recommendations:
            recommendations.append("Keep maintaining your healthy work patterns")
        
        # Calculate trend (compare first and second half of period)
        if len(daily_hours_list) >= 10:
            mid = len(daily_hours_list) // 2
            first_half_avg = statistics.mean(daily_hours_list[:mid])
            second_half_avg = statistics.mean(daily_hours_list[mid:])
            
            if second_half_avg > first_half_avg * 1.1:
                trend = "worsening"
            elif second_half_avg < first_half_avg * 0.9:
                trend = "improving"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return BurnoutRiskAssessment(
            user_id=user_id,
            user_name=user.name,
            risk_level=risk_level,
            risk_score=risk_score,
            factors=factors,
            recommendations=recommendations,
            trend=trend,
            assessed_at=datetime.now()
        )

    async def scan_team_burnout(
        self,
        team_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Scan all users for burnout risk."""
        from app.models import User, TeamMember
        
        # Get users
        if team_id:
            query = (
                select(User)
                .join(TeamMember, User.id == TeamMember.user_id)
                .where(
                    and_(
                        User.is_active == True,
                        TeamMember.team_id == team_id
                    )
                )
            )
        else:
            query = select(User).where(User.is_active == True)
        
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        assessments = []
        risk_distribution = {"low": 0, "moderate": 0, "high": 0, "critical": 0}
        
        for user in users:
            try:
                assessment = await self.assess_burnout_risk(user.id)
                assessments.append(assessment.to_dict())
                risk_distribution[assessment.risk_level.value] += 1
            except Exception as e:
                logger.error(f"Error assessing user {user.id}: {e}")
        
        return {
            "assessments": assessments,
            "risk_distribution": risk_distribution,
            "total_users": len(users),
            "high_risk_count": risk_distribution["high"] + risk_distribution["critical"],
            "assessed_at": datetime.now().isoformat()
        }


# Factory function
async def get_ml_anomaly_service(db: AsyncSession) -> MLAnomalyService:
    """Get ML anomaly service instance."""
    cache = await get_cache_manager()
    return MLAnomalyService(db, cache)
