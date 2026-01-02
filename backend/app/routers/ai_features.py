"""
AI Features Router - Endpoints for managing AI feature toggles.

Provides:
- User endpoints to view and toggle their own AI preferences
- Admin endpoints for global feature control
- Admin endpoints for per-user overrides
- Usage statistics and monitoring
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User
from app.dependencies import get_current_active_user
from app.services.ai_feature_service import AIFeatureManager
from app.schemas.ai_features import (
    AIFeatureSettingResponse,
    AIFeatureSettingUpdate,
    UserAIPreferenceResponse,
    UserAIPreferenceUpdate,
    FeatureStatusResponse,
    UserFeaturesResponse,
    AdminFeaturesResponse,
    AdminFeatureSummary,
    FeatureUsageStats,
    UserPreferenceAdminView,
    AdminOverrideRequest,
    UsageSummaryResponse,
    UserUsageSummaryResponse,
    BatchUserOverrideRequest,
    BatchUpdateResponse,
)

router = APIRouter(prefix="/ai/features", tags=["ai-features"])


# ============================================
# HELPER DEPENDENCIES
# ============================================

def require_admin(current_user: User = Depends(get_current_active_user)):
    """Dependency to require admin or super_admin role."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_super_admin(current_user: User = Depends(get_current_active_user)):
    """Dependency to require super_admin role."""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user


# ============================================
# USER ENDPOINTS
# ============================================

@router.get("", response_model=List[AIFeatureSettingResponse])
async def list_all_features(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all available AI features.
    
    Returns list of all AI features with their global settings.
    Does not include user-specific status.
    """
    manager = AIFeatureManager(db)
    features = await manager.get_all_global_settings()
    return [AIFeatureSettingResponse.model_validate(f) for f in features]


@router.get("/me", response_model=UserFeaturesResponse)
async def get_my_features(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all AI features with status for current user.
    
    Returns complete list of features with:
    - Final computed status (is_enabled)
    - Global setting
    - User's preference
    - Whether admin has overridden
    - Human-readable reason for status
    """
    manager = AIFeatureManager(db)
    features = await manager.get_user_features_summary(current_user.id)
    return UserFeaturesResponse(
        features=[FeatureStatusResponse(**f) for f in features]
    )


@router.get("/me/{feature_id}", response_model=FeatureStatusResponse)
async def get_my_feature_status(
    feature_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get status of a specific feature for current user.
    """
    manager = AIFeatureManager(db)
    
    # Verify feature exists
    global_setting = await manager.get_global_setting(feature_id)
    if not global_setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature '{feature_id}' not found"
        )
    
    status_info = await manager.get_feature_status_for_user(feature_id, current_user.id)
    return FeatureStatusResponse(
        feature_id=feature_id,
        feature_name=global_setting.feature_name,
        description=global_setting.description,
        api_provider=global_setting.api_provider,
        **status_info
    )


@router.put("/me/{feature_id}", response_model=FeatureStatusResponse)
async def toggle_my_feature(
    feature_id: str,
    update: UserAIPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Toggle a feature for yourself.
    
    Note: If admin has overridden your setting, this won't have any effect.
    The response will indicate if admin override is in place.
    """
    manager = AIFeatureManager(db)
    
    # Verify feature exists
    global_setting = await manager.get_global_setting(feature_id)
    if not global_setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature '{feature_id}' not found"
        )
    
    # Check if admin override is in place
    existing_pref = await manager.get_user_preference(current_user.id, feature_id)
    if existing_pref and existing_pref.admin_override:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This setting has been locked by an administrator"
        )
    
    # Update user preference
    await manager.set_user_preference(
        user_id=current_user.id,
        feature_id=feature_id,
        is_enabled=update.is_enabled
    )
    
    # Return updated status
    status_info = await manager.get_feature_status_for_user(feature_id, current_user.id)
    return FeatureStatusResponse(
        feature_id=feature_id,
        feature_name=global_setting.feature_name,
        description=global_setting.description,
        api_provider=global_setting.api_provider,
        **status_info
    )


@router.get("/check/{feature_id}")
async def check_feature_enabled(
    feature_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Quick check if a feature is enabled for current user.
    
    Use this endpoint from AI services before making API calls.
    Returns simple boolean response for performance.
    """
    manager = AIFeatureManager(db)
    is_enabled = await manager.is_enabled(feature_id, current_user.id)
    return {"feature_id": feature_id, "is_enabled": is_enabled}


# ============================================
# ADMIN ENDPOINTS - GLOBAL SETTINGS
# ============================================

@router.get("/admin", response_model=AdminFeaturesResponse)
async def get_admin_features_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get admin-level features summary.
    
    Returns all features with:
    - Global settings
    - User adoption stats
    - Usage statistics for current month
    """
    manager = AIFeatureManager(db)
    features = await manager.get_admin_features_summary()
    
    return AdminFeaturesResponse(
        features=[
            AdminFeatureSummary(
                feature_id=f["feature_id"],
                feature_name=f["feature_name"],
                description=f.get("description"),
                is_enabled=f["is_enabled"],
                api_provider=f.get("api_provider"),
                requires_api_key=f.get("requires_api_key", True),
                enabled_user_count=f["enabled_user_count"],
                total_user_count=f["total_user_count"],
                usage_this_month=FeatureUsageStats(**f["usage_this_month"])
            )
            for f in features
        ]
    )


@router.put("/admin/{feature_id}", response_model=AIFeatureSettingResponse)
async def toggle_global_feature(
    feature_id: str,
    update: AIFeatureSettingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Toggle a feature globally (admin or super admin).
    
    When disabled globally, no user can access the feature.
    """
    manager = AIFeatureManager(db)
    
    setting = await manager.update_global_setting(
        feature_id=feature_id,
        is_enabled=update.is_enabled,
        updated_by=current_user.id
    )
    
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature '{feature_id}' not found"
        )
    
    return AIFeatureSettingResponse.model_validate(setting)


# ============================================
# ADMIN ENDPOINTS - USER OVERRIDES
# ============================================

@router.get("/admin/users/{user_id}", response_model=UserPreferenceAdminView)
async def get_user_preferences_admin(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get a specific user's AI preferences (admin view).
    """
    # Verify user exists
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    
    manager = AIFeatureManager(db)
    features = await manager.get_user_features_summary(user_id)
    
    return UserPreferenceAdminView(
        user_id=user.id,
        user_name=user.name,
        user_email=user.email,
        preferences=[FeatureStatusResponse(**f) for f in features]
    )


@router.put("/admin/users/{user_id}/{feature_id}", response_model=FeatureStatusResponse)
async def set_user_override(
    user_id: int,
    feature_id: str,
    override: AdminOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Set admin override for a user's feature (admin only).
    
    This locks the setting so the user cannot change it.
    """
    # Verify user exists
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    
    manager = AIFeatureManager(db)
    
    # Verify feature exists
    global_setting = await manager.get_global_setting(feature_id)
    if not global_setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature '{feature_id}' not found"
        )
    
    await manager.set_admin_override(
        user_id=user_id,
        feature_id=feature_id,
        is_enabled=override.is_enabled,
        admin_id=current_user.id
    )
    
    status_info = await manager.get_feature_status_for_user(feature_id, user_id)
    return FeatureStatusResponse(
        feature_id=feature_id,
        feature_name=global_setting.feature_name,
        description=global_setting.description,
        api_provider=global_setting.api_provider,
        **status_info
    )


@router.delete("/admin/users/{user_id}/{feature_id}")
async def remove_user_override(
    user_id: int,
    feature_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Remove admin override for a user's feature.
    
    This restores the user's ability to control the setting.
    """
    manager = AIFeatureManager(db)
    
    pref = await manager.remove_admin_override(user_id, feature_id)
    
    if not pref:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No override found for user {user_id} on feature '{feature_id}'"
        )
    
    return {"message": "Override removed", "feature_id": feature_id, "user_id": user_id}


@router.post("/admin/batch-override", response_model=BatchUpdateResponse)
async def batch_set_user_overrides(
    request: BatchUserOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Set admin override for multiple users at once.
    """
    manager = AIFeatureManager(db)
    
    # Verify feature exists
    global_setting = await manager.get_global_setting(request.feature_id)
    if not global_setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature '{request.feature_id}' not found"
        )
    
    updated = 0
    failed = 0
    
    for user_id in request.user_ids:
        try:
            await manager.set_admin_override(
                user_id=user_id,
                feature_id=request.feature_id,
                is_enabled=request.is_enabled,
                admin_id=current_user.id
            )
            updated += 1
        except Exception:
            failed += 1
    
    return BatchUpdateResponse(
        success=failed == 0,
        updated_count=updated,
        failed_count=failed,
        message=f"Updated {updated} users" + (f", {failed} failed" if failed else "")
    )


# ============================================
# ADMIN SEED ENDPOINT
# ============================================

@router.post("/admin/seed")
async def seed_ai_features(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Seed default AI features into the database.
    
    Run this if the ai_feature_settings table is empty.
    Only admins can run this endpoint.
    """
    from sqlalchemy import text
    
    # Check if features already exist
    result = await db.execute(text("SELECT COUNT(*) FROM ai_feature_settings"))
    count = result.scalar()
    
    if count > 0:
        return {
            "status": "already_seeded",
            "message": f"AI features already exist ({count} features found)",
            "count": count
        }
    
    features = [
        ("ai_suggestions", "Time Entry Suggestions", "AI-powered suggestions for projects and tasks based on your work patterns", True, True, "gemini"),
        ("ai_anomaly_alerts", "Anomaly Detection", "Automatic detection of unusual work patterns like overtime or missing entries", True, True, "gemini"),
        ("ai_payroll_forecast", "Payroll Forecasting", "Predictive analytics for payroll and budget planning", False, True, "gemini"),
        ("ai_nlp_entry", "Natural Language Entry", "Create time entries using natural language like 'Log 2 hours on Project Alpha'", False, True, "gemini"),
        ("ai_report_summaries", "AI Report Summaries", "AI-generated insights and summaries in your reports", False, True, "gemini"),
        ("ai_task_estimation", "Task Duration Estimation", "AI-powered estimates for how long tasks will take", False, True, "gemini"),
    ]
    
    for feature in features:
        await db.execute(
            text("""
                INSERT INTO ai_feature_settings 
                (feature_id, feature_name, description, is_enabled, requires_api_key, api_provider)
                VALUES (:fid, :fname, :desc, :enabled, :req_key, :provider)
                ON CONFLICT (feature_id) DO NOTHING
            """),
            {
                "fid": feature[0],
                "fname": feature[1],
                "desc": feature[2],
                "enabled": feature[3],
                "req_key": feature[4],
                "provider": feature[5]
            }
        )
    
    await db.commit()
    
    return {
        "status": "success",
        "message": f"Seeded {len(features)} AI features",
        "features": [f[0] for f in features]
    }


# ============================================
# USAGE STATISTICS ENDPOINTS
# ============================================

@router.get("/usage/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get overall AI usage summary (admin only).
    """
    manager = AIFeatureManager(db)
    summary = await manager.get_usage_summary(days)
    return UsageSummaryResponse(**summary)


@router.get("/usage/user/{user_id}", response_model=UserUsageSummaryResponse)
async def get_user_usage(
    user_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get AI usage for a specific user (admin only).
    """
    manager = AIFeatureManager(db)
    summary = await manager.get_user_usage_stats(user_id, days)
    return UserUsageSummaryResponse(**summary)


@router.get("/usage/me", response_model=UserUsageSummaryResponse)
async def get_my_usage(
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get your own AI usage statistics.
    """
    manager = AIFeatureManager(db)
    summary = await manager.get_user_usage_stats(current_user.id, days)
    return UserUsageSummaryResponse(**summary)
