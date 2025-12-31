"""
AI Feature Manager Service

Manages AI feature toggles at both global (admin) and user levels.
Provides methods to check if features are enabled and track usage.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AIFeatureSetting, 
    UserAIPreference, 
    AIUsageLog, 
    User,
    APIKey
)


class AIFeatureManager:
    """
    Centralized service for managing AI feature toggles.
    
    Features can be controlled at two levels:
    1. Global (admin) - affects all users
    2. Per-user - users can disable features for themselves
    
    Priority: Global OFF > Admin Override > User Preference > Default ON
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================
    # FEATURE STATUS CHECKS
    # ============================================

    async def is_enabled(self, feature_id: str, user_id: int) -> bool:
        """
        Check if an AI feature is enabled for a specific user.
        
        Returns True only if:
        1. Global setting is enabled AND
        2. User hasn't disabled it (unless admin overrode) AND
        3. Admin hasn't force-disabled it for this user
        
        Args:
            feature_id: The feature identifier (e.g., 'ai_suggestions')
            user_id: The user ID to check
            
        Returns:
            bool: True if feature should be active for this user
        """
        # Get global setting
        global_setting = await self.get_global_setting(feature_id)
        if not global_setting or not global_setting.is_enabled:
            return False
        
        # Check if API key is required and available
        if global_setting.requires_api_key and global_setting.api_provider:
            has_key = await self._has_active_api_key(global_setting.api_provider)
            if not has_key:
                return False
        
        # Get user preference
        user_pref = await self.get_user_preference(user_id, feature_id)
        
        if user_pref:
            # Admin override takes precedence
            if user_pref.admin_override:
                return user_pref.is_enabled
            # Otherwise use user's preference
            return user_pref.is_enabled
        
        # No user preference set - default to enabled
        return True

    async def get_feature_status_for_user(
        self, 
        feature_id: str, 
        user_id: int
    ) -> Dict[str, Any]:
        """
        Get detailed feature status for a user including why it's enabled/disabled.
        
        Returns dict with:
        - is_enabled: Final status
        - global_enabled: Global setting
        - user_enabled: User's preference (if set)
        - admin_override: Whether admin overrode
        - reason: Human-readable reason for status
        """
        global_setting = await self.get_global_setting(feature_id)
        
        if not global_setting:
            return {
                "is_enabled": False,
                "global_enabled": False,
                "user_enabled": None,
                "admin_override": False,
                "reason": "Feature not found"
            }
        
        if not global_setting.is_enabled:
            return {
                "is_enabled": False,
                "global_enabled": False,
                "user_enabled": None,
                "admin_override": False,
                "reason": "Disabled by administrator"
            }
        
        # Check API key requirement
        if global_setting.requires_api_key and global_setting.api_provider:
            has_key = await self._has_active_api_key(global_setting.api_provider)
            if not has_key:
                return {
                    "is_enabled": False,
                    "global_enabled": True,
                    "user_enabled": None,
                    "admin_override": False,
                    "reason": f"Requires {global_setting.api_provider} API key"
                }
        
        user_pref = await self.get_user_preference(user_id, feature_id)
        
        if user_pref:
            if user_pref.admin_override:
                return {
                    "is_enabled": user_pref.is_enabled,
                    "global_enabled": True,
                    "user_enabled": user_pref.is_enabled,
                    "admin_override": True,
                    "reason": "Admin override" if not user_pref.is_enabled else "Enabled (admin override)"
                }
            return {
                "is_enabled": user_pref.is_enabled,
                "global_enabled": True,
                "user_enabled": user_pref.is_enabled,
                "admin_override": False,
                "reason": "User preference" if not user_pref.is_enabled else "Enabled"
            }
        
        return {
            "is_enabled": True,
            "global_enabled": True,
            "user_enabled": None,
            "admin_override": False,
            "reason": "Enabled (default)"
        }

    async def _has_active_api_key(self, provider: str) -> bool:
        """Check if there's an active API key for the given provider."""
        query = select(APIKey).where(
            and_(
                APIKey.provider == provider,
                APIKey.is_active == True
            )
        ).limit(1)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    # ============================================
    # GLOBAL SETTINGS (Admin)
    # ============================================

    async def get_global_setting(self, feature_id: str) -> Optional[AIFeatureSetting]:
        """Get global setting for a specific feature."""
        query = select(AIFeatureSetting).where(
            AIFeatureSetting.feature_id == feature_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_all_global_settings(self) -> List[AIFeatureSetting]:
        """Get all global AI feature settings."""
        query = select(AIFeatureSetting).order_by(AIFeatureSetting.feature_name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_global_setting(
        self,
        feature_id: str,
        is_enabled: bool,
        updated_by: int
    ) -> Optional[AIFeatureSetting]:
        """Update global feature setting (admin only)."""
        setting = await self.get_global_setting(feature_id)
        if not setting:
            return None
        
        setting.is_enabled = is_enabled
        setting.updated_by = updated_by
        setting.updated_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(setting)
        return setting

    # ============================================
    # USER PREFERENCES
    # ============================================

    async def get_user_preference(
        self, 
        user_id: int, 
        feature_id: str
    ) -> Optional[UserAIPreference]:
        """Get user's preference for a specific feature."""
        query = select(UserAIPreference).where(
            and_(
                UserAIPreference.user_id == user_id,
                UserAIPreference.feature_id == feature_id
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_all_user_preferences(self, user_id: int) -> List[UserAIPreference]:
        """Get all AI feature preferences for a user."""
        query = select(UserAIPreference).where(
            UserAIPreference.user_id == user_id
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def set_user_preference(
        self,
        user_id: int,
        feature_id: str,
        is_enabled: bool
    ) -> UserAIPreference:
        """Set user's preference for a feature."""
        pref = await self.get_user_preference(user_id, feature_id)
        
        if pref:
            # Don't allow changes if admin override is set
            if pref.admin_override:
                return pref
            pref.is_enabled = is_enabled
            pref.updated_at = datetime.now(timezone.utc)
        else:
            pref = UserAIPreference(
                user_id=user_id,
                feature_id=feature_id,
                is_enabled=is_enabled
            )
            self.db.add(pref)
        
        await self.db.commit()
        await self.db.refresh(pref)
        return pref

    async def set_admin_override(
        self,
        user_id: int,
        feature_id: str,
        is_enabled: bool,
        admin_id: int
    ) -> UserAIPreference:
        """Set admin override for a user's feature (admin only)."""
        pref = await self.get_user_preference(user_id, feature_id)
        
        if pref:
            pref.is_enabled = is_enabled
            pref.admin_override = True
            pref.admin_override_by = admin_id
            pref.updated_at = datetime.now(timezone.utc)
        else:
            pref = UserAIPreference(
                user_id=user_id,
                feature_id=feature_id,
                is_enabled=is_enabled,
                admin_override=True,
                admin_override_by=admin_id
            )
            self.db.add(pref)
        
        await self.db.commit()
        await self.db.refresh(pref)
        return pref

    async def remove_admin_override(
        self,
        user_id: int,
        feature_id: str
    ) -> Optional[UserAIPreference]:
        """Remove admin override, restoring user control."""
        pref = await self.get_user_preference(user_id, feature_id)
        if pref and pref.admin_override:
            pref.admin_override = False
            pref.admin_override_by = None
            pref.updated_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(pref)
        return pref

    # ============================================
    # USER FEATURES SUMMARY
    # ============================================

    async def get_user_features_summary(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get complete features summary for a user.
        Returns list of all features with their status for this user.
        """
        all_features = await self.get_all_global_settings()
        result = []
        
        for feature in all_features:
            status = await self.get_feature_status_for_user(feature.feature_id, user_id)
            result.append({
                "feature_id": feature.feature_id,
                "feature_name": feature.feature_name,
                "description": feature.description,
                "api_provider": feature.api_provider,
                **status
            })
        
        return result

    # ============================================
    # ADMIN FEATURES SUMMARY
    # ============================================

    async def get_admin_features_summary(self) -> List[Dict[str, Any]]:
        """
        Get admin-level features summary with usage statistics.
        """
        all_features = await self.get_all_global_settings()
        result = []
        
        for feature in all_features:
            # Count users with feature enabled
            enabled_count = await self._count_users_with_feature_enabled(feature.feature_id)
            total_users = await self._count_total_users()
            
            # Get usage stats for this month
            usage_stats = await self.get_feature_usage_stats(feature.feature_id)
            
            result.append({
                "feature_id": feature.feature_id,
                "feature_name": feature.feature_name,
                "description": feature.description,
                "is_enabled": feature.is_enabled,
                "api_provider": feature.api_provider,
                "requires_api_key": feature.requires_api_key,
                "enabled_user_count": enabled_count,
                "total_user_count": total_users,
                "usage_this_month": usage_stats
            })
        
        return result

    async def _count_users_with_feature_enabled(self, feature_id: str) -> int:
        """Count users who have the feature enabled (or default)."""
        # Count users who explicitly disabled
        disabled_query = select(func.count(UserAIPreference.id)).where(
            and_(
                UserAIPreference.feature_id == feature_id,
                UserAIPreference.is_enabled == False
            )
        )
        disabled_result = await self.db.execute(disabled_query)
        disabled_count = disabled_result.scalar() or 0
        
        total_users = await self._count_total_users()
        return total_users - disabled_count

    async def _count_total_users(self) -> int:
        """Count total active users."""
        query = select(func.count(User.id)).where(User.is_active == True)
        result = await self.db.execute(query)
        return result.scalar() or 0

    # ============================================
    # USAGE TRACKING
    # ============================================

    async def log_usage(
        self,
        user_id: int,
        feature_id: str,
        api_provider: Optional[str] = None,
        tokens_used: Optional[int] = None,
        estimated_cost: Optional[Decimal] = None,
        response_time_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AIUsageLog:
        """Log an AI feature usage event."""
        import json
        
        log = AIUsageLog(
            user_id=user_id,
            feature_id=feature_id,
            api_provider=api_provider,
            tokens_used=tokens_used,
            estimated_cost=estimated_cost,
            response_time_ms=response_time_ms,
            success=success,
            error_message=error_message,
            request_metadata=json.dumps(metadata) if metadata else None
        )
        
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def get_feature_usage_stats(
        self, 
        feature_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get usage statistics for a feature over the past N days."""
        from datetime import timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = select(
            func.count(AIUsageLog.id).label("total_requests"),
            func.sum(AIUsageLog.tokens_used).label("total_tokens"),
            func.sum(AIUsageLog.estimated_cost).label("total_cost"),
            func.avg(AIUsageLog.response_time_ms).label("avg_response_time"),
            func.count(AIUsageLog.id).filter(AIUsageLog.success == True).label("successful_requests")
        ).where(
            and_(
                AIUsageLog.feature_id == feature_id,
                AIUsageLog.request_timestamp >= cutoff
            )
        )
        
        result = await self.db.execute(query)
        row = result.one()
        
        return {
            "total_requests": row.total_requests or 0,
            "total_tokens": row.total_tokens or 0,
            "total_cost": float(row.total_cost) if row.total_cost else 0.0,
            "avg_response_time_ms": float(row.avg_response_time) if row.avg_response_time else 0.0,
            "success_rate": (row.successful_requests / row.total_requests * 100) if row.total_requests else 100.0,
            "period_days": days
        }

    async def get_user_usage_stats(
        self, 
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get usage statistics for a user over the past N days."""
        from datetime import timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = select(
            AIUsageLog.feature_id,
            func.count(AIUsageLog.id).label("request_count"),
            func.sum(AIUsageLog.tokens_used).label("tokens_used"),
            func.sum(AIUsageLog.estimated_cost).label("estimated_cost")
        ).where(
            and_(
                AIUsageLog.user_id == user_id,
                AIUsageLog.request_timestamp >= cutoff
            )
        ).group_by(AIUsageLog.feature_id)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        features_usage = {}
        total_tokens = 0
        total_cost = 0.0
        
        for row in rows:
            features_usage[row.feature_id] = {
                "request_count": row.request_count,
                "tokens_used": row.tokens_used or 0,
                "estimated_cost": float(row.estimated_cost) if row.estimated_cost else 0.0
            }
            total_tokens += row.tokens_used or 0
            total_cost += float(row.estimated_cost) if row.estimated_cost else 0.0
        
        return {
            "user_id": user_id,
            "period_days": days,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "features": features_usage
        }

    async def get_usage_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get overall AI usage summary for admin dashboard."""
        from datetime import timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Overall stats
        overall_query = select(
            func.count(AIUsageLog.id).label("total_requests"),
            func.sum(AIUsageLog.tokens_used).label("total_tokens"),
            func.sum(AIUsageLog.estimated_cost).label("total_cost"),
            func.count(func.distinct(AIUsageLog.user_id)).label("unique_users")
        ).where(AIUsageLog.request_timestamp >= cutoff)
        
        overall_result = await self.db.execute(overall_query)
        overall = overall_result.one()
        
        # Per-feature breakdown
        feature_query = select(
            AIUsageLog.feature_id,
            func.count(AIUsageLog.id).label("request_count"),
            func.sum(AIUsageLog.tokens_used).label("tokens_used"),
            func.sum(AIUsageLog.estimated_cost).label("cost")
        ).where(
            AIUsageLog.request_timestamp >= cutoff
        ).group_by(AIUsageLog.feature_id)
        
        feature_result = await self.db.execute(feature_query)
        features = {
            row.feature_id: {
                "request_count": row.request_count,
                "tokens_used": row.tokens_used or 0,
                "cost": float(row.cost) if row.cost else 0.0
            }
            for row in feature_result.all()
        }
        
        return {
            "period_days": days,
            "total_requests": overall.total_requests or 0,
            "total_tokens": overall.total_tokens or 0,
            "total_cost": float(overall.total_cost) if overall.total_cost else 0.0,
            "unique_users": overall.unique_users or 0,
            "features": features
        }
