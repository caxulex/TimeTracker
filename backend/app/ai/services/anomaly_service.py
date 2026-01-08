"""
Anomaly Detection Service

Detects unusual patterns in time tracking data:
- Extended work days (>12 hours)
- Consecutive long days (>10h × 5 days)
- Weekend work spikes
- Missing time entries
- Duplicate entries
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from enum import Enum
from dataclasses import dataclass, field
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.config import ai_settings
from app.ai.services.ai_client import AIClient, get_ai_client
from app.ai.utils.cache_manager import AICacheManager, get_cache_manager
from app.ai.models.feature_engineering import AnomalyFeatures
from app.services.ai_feature_service import AIFeatureManager

logger = logging.getLogger(__name__)


class AnomalySeverity(str, Enum):
    """Anomaly severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AnomalyType(str, Enum):
    """Types of anomalies detected."""
    EXTENDED_DAY = "extended_day"
    CONSECUTIVE_LONG_DAYS = "consecutive_long_days"
    WEEKEND_SPIKE = "weekend_spike"
    MISSING_TIME = "missing_time"
    DUPLICATE_ENTRY = "duplicate_entry"
    OVERTIME_RISK = "overtime_risk"
    BURNOUT_RISK = "burnout_risk"


@dataclass
class Anomaly:
    """Single anomaly detection result."""
    type: AnomalyType
    severity: AnomalySeverity
    user_id: int
    user_name: str
    description: str
    detected_at: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    recommendation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "severity": self.severity.value,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "description": self.description,
            "detected_at": self.detected_at.isoformat(),
            "details": self.details,
            "recommendation": self.recommendation
        }


class AnomalyService:
    """
    Service for detecting anomalies in time tracking data.
    
    Uses rule-based detection with optional AI enhancement
    for contextual analysis.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        cache_manager: Optional[AICacheManager] = None
    ):
        self.db = db
        self.cache = cache_manager
        self._ai_client: Optional[AIClient] = None
        self._feature_manager: Optional[AIFeatureManager] = None
        
        # Thresholds from config
        self.extended_day_hours = ai_settings.ANOMALY_EXTENDED_DAY_HOURS
        self.consecutive_long_days_count = ai_settings.ANOMALY_CONSECUTIVE_LONG_DAYS
        self.weekend_spike_hours = ai_settings.ANOMALY_WEEKEND_HOURS
        self.long_day_threshold = ai_settings.ANOMALY_LONG_DAY_HOURS

    async def _get_feature_manager(self) -> AIFeatureManager:
        """Get feature manager instance."""
        if self._feature_manager is None:
            self._feature_manager = AIFeatureManager(self.db)
        return self._feature_manager

    async def scan_user(
        self,
        user_id: int,
        period_days: int = 7
    ) -> Dict[str, Any]:
        """
        Scan a single user for anomalies.
        
        Args:
            user_id: User to scan
            period_days: Days to look back
            
        Returns:
            Dict with anomalies and summary
        """
        try:
            # Check if feature is enabled
            fm = await self._get_feature_manager()
            if not await fm.is_enabled("ai_anomaly_alerts", user_id):
                return {
                    "anomalies": [],
                    "enabled": False,
                    "message": "Anomaly detection is disabled",
                    "scan_date": datetime.now().isoformat(),
                    "period_days": period_days,
                    "user_id": user_id
                }

            # Check cache
            cache_date = date.today().isoformat()
            if self.cache:
                cached = await self.cache.get_anomaly_cache(cache_date, user_id)
                if cached:
                    return cached

            # Build features
            features = await self._build_features(user_id, period_days)
            
            # Run detection
            anomalies = []
            anomalies.extend(await self._detect_extended_days(features))
            anomalies.extend(await self._detect_consecutive_long_days(features))
            anomalies.extend(await self._detect_weekend_spikes(features))
            anomalies.extend(await self._detect_missing_time(features))
            anomalies.extend(await self._detect_duplicates(features, user_id))
            anomalies.extend(await self._detect_burnout_risk(features))

            result = {
                "user_id": user_id,
                "user_name": features.user_name,
                "anomalies": [a.to_dict() for a in anomalies],
                "summary": features.to_dict(),
                "scan_date": datetime.now().isoformat(),
                "period_days": period_days,
                "enabled": True
            }

            # Cache result
            if self.cache:
                await self.cache.set_anomaly_cache(
                    cache_date,
                    result,
                    user_id
                )

            # Log usage
            await fm.log_usage(
                user_id=user_id,
                feature_id="ai_anomaly_alerts"
            )

            return result

        except Exception as e:
            logger.error(f"Error scanning user {user_id}: {e}")
            return {
                "anomalies": [],
                "error": str(e),
                "enabled": True,
                "scan_date": datetime.now().isoformat(),
                "period_days": period_days,
                "user_id": user_id
            }

    async def scan_all_users(
        self,
        period_days: int = 7,
        team_id: Optional[int] = None,
        company_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scan all users (or team) for anomalies.
        Used by scheduled daily scan.
        
        Args:
            period_days: Days to look back
            team_id: Optional team filter
            company_id: Optional company filter for multi-tenancy
            
        Returns:
            Dict with all anomalies and statistics
        """
        from app.models import User, Team, TeamMember
        
        try:
            fm = await self._get_feature_manager()
            # Check if feature is globally enabled (use system check without user-specific prefs)
            global_setting = await fm.get_global_setting("ai_anomaly_alerts")
            if not global_setting or not global_setting.is_enabled:
                return {
                    "anomalies": [],
                    "enabled": False,
                    "scan_date": datetime.now().isoformat(),
                    "period_days": period_days,
                    "message": "Anomaly detection is disabled"
                }

            # Get users to scan
            if team_id:
                # Get users via TeamMember
                query = (
                    select(User)
                    .join(TeamMember, User.id == TeamMember.user_id)
                    .where(User.is_active == True)
                    .where(TeamMember.team_id == team_id)
                )
            else:
                query = select(User).where(User.is_active == True)
            
            # Filter by company_id if provided (multi-tenancy)
            if company_id is not None:
                query = query.where(User.company_id == company_id)
            
            result = await self.db.execute(query)
            users = result.scalars().all()

            all_anomalies = []
            users_scanned = 0
            users_with_anomalies = 0

            for user in users:
                user_result = await self.scan_user(user.id, period_days)
                users_scanned += 1
                
                if user_result.get("anomalies"):
                    users_with_anomalies += 1
                    all_anomalies.extend(user_result["anomalies"])

            # Sort by severity
            severity_order = {"critical": 0, "warning": 1, "info": 2}
            all_anomalies.sort(
                key=lambda x: severity_order.get(x["severity"], 3)
            )

            return {
                "anomalies": all_anomalies,
                "statistics": {
                    "users_scanned": users_scanned,
                    "users_with_anomalies": users_with_anomalies,
                    "total_anomalies": len(all_anomalies),
                    "critical_count": len([a for a in all_anomalies if a["severity"] == "critical"]),
                    "warning_count": len([a for a in all_anomalies if a["severity"] == "warning"]),
                    "info_count": len([a for a in all_anomalies if a["severity"] == "info"])
                },
                "scan_date": datetime.now().isoformat(),
                "period_days": period_days,
                "enabled": True
            }

        except Exception as e:
            logger.error(f"Error in full anomaly scan: {e}")
            return {
                "anomalies": [],
                "error": str(e),
                "enabled": True,
                "scan_date": datetime.now().isoformat(),
                "period_days": period_days
            }

    async def _build_features(
        self,
        user_id: int,
        period_days: int
    ) -> AnomalyFeatures:
        """Build anomaly features from time entries."""
        from app.models import User, TimeEntry
        
        # Get user
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise ValueError(f"User {user_id} not found")

        period_start = date.today() - timedelta(days=period_days)
        period_end = date.today()

        features = AnomalyFeatures(
            user_id=user_id,
            user_name=user.name,
            period_start=period_start,
            period_end=period_end
        )

        # Get time entries grouped by day
        entries_query = await self.db.execute(
            select(TimeEntry)
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    TimeEntry.start_time >= datetime.combine(period_start, datetime.min.time()),
                    TimeEntry.start_time <= datetime.combine(period_end, datetime.max.time())
                )
            )
            .order_by(TimeEntry.start_time)
        )
        entries = entries_query.scalars().all()

        # Aggregate by day
        for entry in entries:
            if entry.end_time is None:
                continue
            
            day_str = entry.start_time.date().isoformat()
            duration_hours = (entry.end_time - entry.start_time).total_seconds() / 3600
            
            features.daily_hours[day_str] = features.daily_hours.get(day_str, 0) + duration_hours
            features.daily_entry_counts[day_str] = features.daily_entry_counts.get(day_str, 0) + 1

        # Compute metrics
        features.compute_metrics()
        
        return features

    async def _detect_extended_days(
        self,
        features: AnomalyFeatures
    ) -> List[Anomaly]:
        """Detect days with extended work hours."""
        anomalies = []
        
        for day_str, hours in features.daily_hours.items():
            if hours >= self.extended_day_hours:
                anomalies.append(Anomaly(
                    type=AnomalyType.EXTENDED_DAY,
                    severity=AnomalySeverity.WARNING if hours < 14 else AnomalySeverity.CRITICAL,
                    user_id=features.user_id,
                    user_name=features.user_name,
                    description=f"Extended work day: {hours:.1f} hours on {day_str}",
                    detected_at=datetime.now(),
                    details={
                        "date": day_str,
                        "hours": round(hours, 2),
                        "threshold": self.extended_day_hours
                    },
                    recommendation="Consider taking breaks and maintaining work-life balance"
                ))
        
        return anomalies

    async def _detect_consecutive_long_days(
        self,
        features: AnomalyFeatures
    ) -> List[Anomaly]:
        """Detect consecutive days with long hours."""
        anomalies = []
        
        if features.consecutive_long_days >= self.consecutive_long_days_count:
            anomalies.append(Anomaly(
                type=AnomalyType.CONSECUTIVE_LONG_DAYS,
                severity=AnomalySeverity.CRITICAL,
                user_id=features.user_id,
                user_name=features.user_name,
                description=(
                    f"{features.consecutive_long_days} consecutive days "
                    f"with {self.long_day_threshold}+ hours"
                ),
                detected_at=datetime.now(),
                details={
                    "consecutive_days": features.consecutive_long_days,
                    "threshold_hours": self.long_day_threshold,
                    "threshold_days": self.consecutive_long_days_count
                },
                recommendation="This pattern may indicate burnout risk. Consider workload review."
            ))
        
        return anomalies

    async def _detect_weekend_spikes(
        self,
        features: AnomalyFeatures
    ) -> List[Anomaly]:
        """Detect unusual weekend work."""
        anomalies = []
        
        if features.weekend_hours >= self.weekend_spike_hours:
            anomalies.append(Anomaly(
                type=AnomalyType.WEEKEND_SPIKE,
                severity=AnomalySeverity.INFO if features.weekend_hours < 8 else AnomalySeverity.WARNING,
                user_id=features.user_id,
                user_name=features.user_name,
                description=f"Weekend work spike: {features.weekend_hours:.1f} hours",
                detected_at=datetime.now(),
                details={
                    "weekend_hours": round(features.weekend_hours, 2),
                    "threshold": self.weekend_spike_hours
                },
                recommendation="Ensure weekend work is planned and compensated appropriately"
            ))
        
        return anomalies

    async def _detect_missing_time(
        self,
        features: AnomalyFeatures
    ) -> List[Anomaly]:
        """Detect missing time entries."""
        anomalies = []
        
        # Only flag if significant missing days
        if len(features.missing_days) >= 2:
            anomalies.append(Anomaly(
                type=AnomalyType.MISSING_TIME,
                severity=AnomalySeverity.INFO,
                user_id=features.user_id,
                user_name=features.user_name,
                description=f"Missing time entries for {len(features.missing_days)} weekdays",
                detected_at=datetime.now(),
                details={
                    "missing_days": features.missing_days[:5],  # Show first 5
                    "total_missing": len(features.missing_days)
                },
                recommendation="Consider filling in missing time entries"
            ))
        
        return anomalies

    async def _detect_duplicates(
        self,
        features: AnomalyFeatures,
        user_id: int
    ) -> List[Anomaly]:
        """Detect potential duplicate entries."""
        from app.models import TimeEntry
        
        anomalies = []
        
        # Query for potential duplicates (same project, similar time, same day)
        query = await self.db.execute(
            select(
                func.date(TimeEntry.start_time).label("entry_date"),
                TimeEntry.project_id,
                func.count().label("count")
            )
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    TimeEntry.start_time >= datetime.combine(
                        features.period_start, datetime.min.time()
                    )
                )
            )
            .group_by(
                func.date(TimeEntry.start_time),
                TimeEntry.project_id
            )
            .having(func.count() > 3)  # More than 3 entries same project same day
        )
        
        duplicates = query.all()
        
        for dup in duplicates:
            anomalies.append(Anomaly(
                type=AnomalyType.DUPLICATE_ENTRY,
                severity=AnomalySeverity.INFO,
                user_id=features.user_id,
                user_name=features.user_name,
                description=f"Multiple entries ({dup.count}) for same project on {dup.entry_date}",
                detected_at=datetime.now(),
                details={
                    "date": str(dup.entry_date),
                    "project_id": dup.project_id,
                    "entry_count": dup.count
                },
                recommendation="Review entries for potential duplicates or consolidation"
            ))
        
        return anomalies

    async def _detect_burnout_risk(
        self,
        features: AnomalyFeatures
    ) -> List[Anomaly]:
        """Detect burnout risk based on multiple factors."""
        anomalies = []
        
        # Calculate burnout risk score
        risk_score = 0
        risk_factors = []
        
        if features.avg_hours_per_day > 9:
            risk_score += 20
            risk_factors.append(f"High avg hours ({features.avg_hours_per_day:.1f}h/day)")
        
        if features.consecutive_long_days >= 3:
            risk_score += 30
            risk_factors.append(f"{features.consecutive_long_days} consecutive long days")
        
        if features.weekend_hours > 4:
            risk_score += 15
            risk_factors.append(f"Weekend work ({features.weekend_hours:.1f}h)")
        
        if features.max_hours_day > 12:
            risk_score += 20
            risk_factors.append(f"Max {features.max_hours_day:.1f}h in single day")
        
        if features.days_worked == 7:  # Worked every day
            risk_score += 15
            risk_factors.append("No days off in period")

        if risk_score >= 40:
            anomalies.append(Anomaly(
                type=AnomalyType.BURNOUT_RISK,
                severity=(
                    AnomalySeverity.CRITICAL if risk_score >= 60 
                    else AnomalySeverity.WARNING
                ),
                user_id=features.user_id,
                user_name=features.user_name,
                description=f"Potential burnout risk detected (score: {risk_score}/100)",
                detected_at=datetime.now(),
                details={
                    "risk_score": risk_score,
                    "risk_factors": risk_factors,
                    "period_stats": features.to_dict()
                },
                recommendation=(
                    "Consider discussing workload and wellbeing with manager. "
                    "Regular breaks and time off are important for sustained productivity."
                )
            ))
        
        return anomalies

    async def dismiss_anomaly(
        self,
        user_id: int,
        anomaly_type: str,
        dismissed_by: int,
        reason: Optional[str] = None
    ) -> bool:
        """
        Dismiss/acknowledge an anomaly.
        Records in audit log.
        """
        try:
            fm = await self._get_feature_manager()
            await fm.log_usage(
                user_id=dismissed_by,
                feature_id="ai_anomaly_alerts",
                metadata={
                    "target_user_id": user_id,
                    "anomaly_type": anomaly_type,
                    "reason": reason
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to dismiss anomaly: {e}")
            return False


# Factory function
async def get_anomaly_service(db: AsyncSession) -> AnomalyService:
    """Create anomaly service instance."""
    cache = await get_cache_manager()
    return AnomalyService(db, cache)
