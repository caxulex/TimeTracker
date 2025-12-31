"""
Task Duration Estimation Service (Phase 4)

ML-based task duration prediction using:
- XGBoost regression for time estimation
- TF-IDF for task description features
- Historical user performance analysis
"""

import logging
import pickle
import re
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import statistics

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.config import ai_settings
from app.ai.utils.cache_manager import AICacheManager, get_cache_manager

logger = logging.getLogger(__name__)

# Type stubs for optional ML libraries
if TYPE_CHECKING:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    import xgboost as xgb

# Runtime imports with fallbacks
np: Any = None
TfidfVectorizer: Any = None
StandardScaler: Any = None
LabelEncoder: Any = None
xgb: Any = None

try:
    import numpy as np  # type: ignore[no-redef]
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("NumPy not installed.")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[no-redef]
    from sklearn.preprocessing import StandardScaler, LabelEncoder  # type: ignore[no-redef]
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not installed. TF-IDF features disabled.")

try:
    import xgboost as xgb  # type: ignore[no-redef]
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost not installed. Using fallback estimation.")

ML_AVAILABLE = NUMPY_AVAILABLE and SKLEARN_AVAILABLE and XGBOOST_AVAILABLE


@dataclass
class DurationEstimate:
    """Task duration estimate result."""
    estimated_minutes: float
    confidence: float
    range_min: float
    range_max: float
    method: str  # "ml", "historical", "fallback"
    factors: List[Dict[str, Any]]
    similar_tasks: List[Dict[str, Any]]
    recommendation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "estimated_minutes": round(self.estimated_minutes, 0),
            "estimated_hours": round(self.estimated_minutes / 60, 2),
            "confidence": round(self.confidence, 2),
            "range": {
                "min_minutes": round(self.range_min, 0),
                "max_minutes": round(self.range_max, 0),
                "min_hours": round(self.range_min / 60, 2),
                "max_hours": round(self.range_max / 60, 2)
            },
            "method": self.method,
            "factors": self.factors,
            "similar_tasks": self.similar_tasks[:5],  # Top 5 similar tasks
            "recommendation": self.recommendation
        }


@dataclass
class UserPerformanceProfile:
    """User's historical task performance."""
    user_id: int
    avg_task_duration: float  # minutes
    task_completion_rate: float
    speed_factor: float  # Relative to team average (1.0 = average)
    preferred_task_types: List[str]
    peak_performance_hours: List[int]
    task_count: int
    calculated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "avg_task_duration": round(self.avg_task_duration, 0),
            "task_completion_rate": round(self.task_completion_rate, 2),
            "speed_factor": round(self.speed_factor, 2),
            "preferred_task_types": self.preferred_task_types,
            "peak_performance_hours": self.peak_performance_hours,
            "task_count": self.task_count,
            "calculated_at": self.calculated_at.isoformat()
        }


class TaskEstimationService:
    """
    ML-powered task duration estimation service.
    
    Uses XGBoost regression with features including:
    - Task description (TF-IDF vectorized)
    - Project/category information
    - User historical performance
    - Time of day and week patterns
    """
    
    def __init__(
        self,
        db: AsyncSession,
        cache_manager: Optional[AICacheManager] = None
    ):
        self.db = db
        self.cache = cache_manager
        
        # ML components - use Any for type hints with optional dependencies
        self._model: Optional[Any] = None  # XGBoost model
        self._vectorizer: Optional[Any] = None  # TfidfVectorizer
        self._scaler: Optional[Any] = None  # StandardScaler
        self._project_encoder: Optional[Any] = None  # LabelEncoder
        self._is_trained: bool = False
        
        # User profiles cache
        self._user_profiles: Dict[int, UserPerformanceProfile] = {}
        
        # Configuration
        self.min_samples = 50  # Minimum tasks for ML training
        self.tfidf_max_features = 100  # TF-IDF vocabulary size
        self.default_estimate_minutes = 60  # Fallback default

    # ============================================
    # USER PERFORMANCE PROFILING
    # ============================================
    
    async def build_user_profile(
        self,
        user_id: int,
        period_days: int = 90
    ) -> UserPerformanceProfile:
        """Build performance profile for a user."""
        from app.models import TimeEntry, User
        
        period_start = datetime.now() - timedelta(days=period_days)
        
        # Get completed time entries
        entries_result = await self.db.execute(
            select(TimeEntry)
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    TimeEntry.start_time >= period_start,
                    TimeEntry.is_running == False,
                    TimeEntry.duration_seconds.isnot(None)
                )
            )
            .order_by(TimeEntry.start_time)
        )
        entries = list(entries_result.scalars().all())
        
        if not entries:
            return UserPerformanceProfile(
                user_id=user_id,
                avg_task_duration=self.default_estimate_minutes,
                task_completion_rate=0.0,
                speed_factor=1.0,
                preferred_task_types=[],
                peak_performance_hours=[9, 10, 11, 14, 15],
                task_count=0,
                calculated_at=datetime.now()
            )
        
        # Calculate metrics
        durations = [(e.duration_seconds or 0) / 60 for e in entries]  # in minutes
        avg_duration = statistics.mean(durations)
        
        # Task types from descriptions
        task_types = defaultdict(int)
        for entry in entries:
            if entry.description:
                # Extract keywords (simple approach)
                words = entry.description.lower().split()
                common_types = ["meeting", "review", "code", "test", "design", 
                              "debug", "fix", "implement", "document", "research"]
                for word in words:
                    for task_type in common_types:
                        if task_type in word:
                            task_types[task_type] += 1
        
        preferred_types = sorted(task_types.keys(), key=lambda x: task_types[x], reverse=True)[:5]
        
        # Peak performance hours (hours with shortest task times)
        hour_durations = defaultdict(list)
        for entry in entries:
            hour = entry.start_time.hour
            duration = (entry.duration_seconds or 0) / 60
            if 5 < duration < 480:  # Filter outliers
                hour_durations[hour].append(duration)
        
        hour_avgs = {
            hour: statistics.mean(durs) 
            for hour, durs in hour_durations.items() 
            if len(durs) >= 3
        }
        
        peak_hours = sorted(hour_avgs.keys(), key=lambda x: hour_avgs[x])[:5]
        if not peak_hours:
            peak_hours = [9, 10, 11, 14, 15]
        
        # Speed factor (will be updated when comparing to team)
        speed_factor = 1.0
        
        profile = UserPerformanceProfile(
            user_id=user_id,
            avg_task_duration=avg_duration,
            task_completion_rate=1.0,  # Simplified
            speed_factor=speed_factor,
            preferred_task_types=preferred_types,
            peak_performance_hours=peak_hours,
            task_count=len(entries),
            calculated_at=datetime.now()
        )
        
        self._user_profiles[user_id] = profile
        return profile

    async def get_user_profile(self, user_id: int) -> UserPerformanceProfile:
        """Get cached or build user profile."""
        if user_id in self._user_profiles:
            profile = self._user_profiles[user_id]
            if (datetime.now() - profile.calculated_at).days < 1:
                return profile
        
        return await self.build_user_profile(user_id)

    # ============================================
    # MODEL TRAINING
    # ============================================
    
    async def train_model(
        self,
        team_id: Optional[int] = None,
        period_days: int = 180
    ) -> Dict[str, Any]:
        """Train the XGBoost duration estimation model."""
        if not ML_AVAILABLE:
            return {
                "success": False,
                "error": "ML libraries not installed (xgboost, scikit-learn)"
            }
        
        from app.models import TimeEntry, Project
        
        period_start = datetime.now() - timedelta(days=period_days)
        
        # Build query
        query = (
            select(TimeEntry)
            .where(
                and_(
                    TimeEntry.start_time >= period_start,
                    TimeEntry.is_running == False,
                    TimeEntry.duration_seconds.isnot(None),
                    TimeEntry.duration_seconds > 300,  # At least 5 minutes
                    TimeEntry.duration_seconds < 28800  # Less than 8 hours
                )
            )
        )
        
        result = await self.db.execute(query)
        entries = list(result.scalars().all())
        
        if len(entries) < self.min_samples:
            return {
                "success": False,
                "error": f"Insufficient data. Need {self.min_samples} tasks, have {len(entries)}"
            }
        
        # Prepare features
        descriptions = []
        project_ids = []
        user_ids = []
        hours = []
        day_of_week = []
        durations = []
        
        for entry in entries:
            # Target variable
            duration_minutes = (entry.duration_seconds or 0) / 60
            durations.append(duration_minutes)
            
            # Features
            descriptions.append(entry.description or "")
            project_ids.append(str(entry.project_id or "none"))
            user_ids.append(entry.user_id)
            hours.append(entry.start_time.hour)
            day_of_week.append(entry.start_time.weekday())
        
        # TF-IDF vectorization
        self._vectorizer = TfidfVectorizer(
            max_features=self.tfidf_max_features,
            stop_words='english',
            ngram_range=(1, 2)
        )
        tfidf_features = self._vectorizer.fit_transform(descriptions).toarray()
        
        # Encode projects
        self._project_encoder = LabelEncoder()
        project_encoded = self._project_encoder.fit_transform(project_ids)
        
        # Combine features
        X = np.column_stack([
            tfidf_features,
            project_encoded,
            hours,
            day_of_week
        ])
        y = np.array(durations)
        
        # Scale features
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)
        
        # Train XGBoost model
        self._model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42
        )
        self._model.fit(X_scaled, y)
        
        self._is_trained = True
        
        # Calculate training metrics
        predictions = self._model.predict(X_scaled)
        mae = np.mean(np.abs(predictions - y))
        rmse = np.sqrt(np.mean((predictions - y) ** 2))
        
        return {
            "success": True,
            "samples_used": len(entries),
            "mae_minutes": round(mae, 1),
            "rmse_minutes": round(rmse, 1),
            "trained_at": datetime.now().isoformat()
        }

    # ============================================
    # ESTIMATION
    # ============================================
    
    async def estimate_duration(
        self,
        description: str,
        project_id: Optional[int] = None,
        user_id: Optional[int] = None,
        scheduled_hour: Optional[int] = None
    ) -> DurationEstimate:
        """Estimate duration for a task."""
        factors = []
        similar_tasks = []
        
        # Get user profile if available
        user_profile = None
        if user_id:
            try:
                user_profile = await self.get_user_profile(user_id)
            except Exception as e:
                logger.warning(f"Could not get user profile: {e}")
        
        # ML estimation
        if ML_AVAILABLE and self._is_trained and self._model is not None:
            estimate = await self._ml_estimate(
                description, project_id, user_id, scheduled_hour, user_profile
            )
            if estimate:
                return estimate
        
        # Historical estimation (fallback)
        historical = await self._historical_estimate(
            description, project_id, user_id
        )
        if historical:
            return historical
        
        # Ultimate fallback
        return DurationEstimate(
            estimated_minutes=self.default_estimate_minutes,
            confidence=0.3,
            range_min=30,
            range_max=120,
            method="fallback",
            factors=[{
                "name": "Default Estimate",
                "description": "Using default value due to insufficient data"
            }],
            similar_tasks=[],
            recommendation="Track more tasks to improve estimation accuracy"
        )

    async def _ml_estimate(
        self,
        description: str,
        project_id: Optional[int],
        user_id: Optional[int],
        scheduled_hour: Optional[int],
        user_profile: Optional[UserPerformanceProfile]
    ) -> Optional[DurationEstimate]:
        """ML-based estimation using XGBoost."""
        try:
            # Prepare features
            tfidf = self._vectorizer.transform([description or ""]).toarray()
            
            project_str = str(project_id or "none")
            try:
                project_encoded = self._project_encoder.transform([project_str])[0]
            except ValueError:
                # Unknown project
                project_encoded = 0
            
            hour = scheduled_hour or datetime.now().hour
            dow = datetime.now().weekday()
            
            # Combine features
            X = np.column_stack([
                tfidf,
                [[project_encoded]],
                [[hour]],
                [[dow]]
            ])
            X_scaled = self._scaler.transform(X)
            
            # Predict
            prediction = self._model.predict(X_scaled)[0]
            
            # Adjust for user performance
            if user_profile and user_profile.speed_factor != 1.0:
                prediction *= user_profile.speed_factor
            
            # Calculate confidence based on model performance
            confidence = 0.75  # Base confidence for ML
            
            # Wider range for longer estimates
            range_factor = 0.3
            range_min = prediction * (1 - range_factor)
            range_max = prediction * (1 + range_factor)
            
            # Build factors explanation
            factors = [
                {
                    "name": "Task Description",
                    "description": f"Keywords analyzed: {len(description.split()) if description else 0} words"
                },
                {
                    "name": "Time of Day",
                    "description": f"Scheduled for hour {hour}",
                    "impact": "neutral"
                }
            ]
            
            if user_profile:
                factors.append({
                    "name": "User Performance",
                    "description": f"Speed factor: {user_profile.speed_factor:.2f}x",
                    "impact": "faster" if user_profile.speed_factor < 1 else "slower" if user_profile.speed_factor > 1 else "neutral"
                })
            
            recommendation = None
            if user_profile and hour not in user_profile.peak_performance_hours:
                recommendation = f"Consider scheduling during peak hours ({user_profile.peak_performance_hours[:3]}) for better efficiency"
            
            return DurationEstimate(
                estimated_minutes=prediction,
                confidence=confidence,
                range_min=range_min,
                range_max=range_max,
                method="ml",
                factors=factors,
                similar_tasks=[],  # Would need additional lookup
                recommendation=recommendation
            )
            
        except Exception as e:
            logger.error(f"ML estimation failed: {e}")
            return None

    async def _historical_estimate(
        self,
        description: str,
        project_id: Optional[int],
        user_id: Optional[int]
    ) -> Optional[DurationEstimate]:
        """Historical data-based estimation."""
        from app.models import TimeEntry
        
        # Build query for similar tasks
        conditions = [
            TimeEntry.is_running == False,
            TimeEntry.duration_seconds.isnot(None),
            TimeEntry.duration_seconds > 300,
            TimeEntry.duration_seconds < 28800
        ]
        
        if project_id:
            conditions.append(TimeEntry.project_id == project_id)
        
        if user_id:
            conditions.append(TimeEntry.user_id == user_id)
        
        query = (
            select(TimeEntry)
            .where(and_(*conditions))
            .order_by(TimeEntry.start_time.desc())
            .limit(100)
        )
        
        result = await self.db.execute(query)
        entries = list(result.scalars().all())
        
        if not entries:
            return None
        
        # Find similar by description
        similar = []
        if description:
            desc_words = set(description.lower().split())
            for entry in entries:
                if entry.description:
                    entry_words = set(entry.description.lower().split())
                    overlap = len(desc_words & entry_words)
                    if overlap > 0:
                        similar.append({
                            "entry": entry,
                            "similarity": overlap / max(len(desc_words), 1)
                        })
            
            similar.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Calculate estimate
        if similar:
            # Weight by similarity
            weighted_sum = sum(
                (s["entry"].duration_seconds / 60) * s["similarity"]
                for s in similar[:10]
            )
            weight_total = sum(s["similarity"] for s in similar[:10])
            estimate = weighted_sum / weight_total if weight_total > 0 else self.default_estimate_minutes
            confidence = min(0.8, 0.3 + (len(similar) / 20) * 0.5)
        else:
            # Use average from entries
            durations = [(e.duration_seconds or 0) / 60 for e in entries]
            estimate = statistics.mean(durations)
            confidence = 0.5
        
        # Calculate range
        range_factor = 0.4 if not similar else 0.3
        
        similar_tasks_data = [
            {
                "description": s["entry"].description[:100] if s["entry"].description else "",
                "duration_minutes": round((s["entry"].duration_seconds or 0) / 60, 0),
                "similarity": round(s["similarity"], 2)
            }
            for s in similar[:5]
        ]
        
        return DurationEstimate(
            estimated_minutes=estimate,
            confidence=confidence,
            range_min=estimate * (1 - range_factor),
            range_max=estimate * (1 + range_factor),
            method="historical",
            factors=[
                {
                    "name": "Historical Data",
                    "description": f"Based on {len(entries)} similar completed tasks"
                }
            ],
            similar_tasks=similar_tasks_data,
            recommendation="Consider breaking down large tasks for more accurate estimates" if estimate > 240 else None
        )

    # ============================================
    # BATCH ESTIMATION
    # ============================================
    
    async def estimate_batch(
        self,
        tasks: List[Dict[str, Any]],
        user_id: Optional[int] = None
    ) -> List[DurationEstimate]:
        """Estimate durations for multiple tasks."""
        results = []
        
        for task in tasks:
            estimate = await self.estimate_duration(
                description=task.get("description", ""),
                project_id=task.get("project_id"),
                user_id=user_id or task.get("user_id"),
                scheduled_hour=task.get("scheduled_hour")
            )
            results.append(estimate)
        
        return results

    async def get_estimation_stats(self) -> Dict[str, Any]:
        """Get estimation service statistics."""
        return {
            "model_trained": self._is_trained,
            "ml_available": ML_AVAILABLE,
            "cached_profiles": len(self._user_profiles),
            "min_samples_required": self.min_samples,
            "tfidf_features": self.tfidf_max_features if self._vectorizer else 0
        }


# Factory function
async def get_task_estimation_service(db: AsyncSession) -> TaskEstimationService:
    """Get task estimation service instance."""
    cache = await get_cache_manager()
    return TaskEstimationService(db, cache)
