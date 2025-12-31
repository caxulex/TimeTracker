"""
Time Entry Suggestion Service

Provides intelligent time entry suggestions based on:
- User historical patterns
- Time of day/week context
- Recent activity
- Partial description matching
- AI enhancement for complex cases
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.config import ai_settings
from app.ai.services.ai_client import AIClient, get_ai_client, AIProviderError
from app.ai.utils.prompt_templates import PromptTemplates
from app.ai.utils.cache_manager import AICacheManager, get_cache_manager
from app.ai.models.feature_engineering import (
    TimeContext,
    UserContext,
    SuggestionFeatures
)
from app.services.ai_feature_service import AIFeatureManager

logger = logging.getLogger(__name__)


class SuggestionResult:
    """Container for a single suggestion."""
    
    def __init__(
        self,
        project_id: int,
        project_name: str,
        task_id: Optional[int] = None,
        task_name: Optional[str] = None,
        suggested_description: Optional[str] = None,
        confidence: float = 0.0,
        reason: str = "",
        source: str = "pattern"  # "pattern", "ai", "recent"
    ):
        self.project_id = project_id
        self.project_name = project_name
        self.task_id = task_id
        self.task_name = task_name
        self.suggested_description = suggested_description
        self.confidence = confidence
        self.reason = reason
        self.source = source
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "suggested_description": self.suggested_description,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            "source": self.source
        }


class SuggestionService:
    """
    Service for generating time entry suggestions.
    
    Uses a multi-stage approach:
    1. Pattern-based: Fast, frequency-based suggestions
    2. Context-aware: Time of day/week patterns
    3. AI-enhanced: GPT/Gemini for complex matching
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

    async def _get_ai_client(self) -> AIClient:
        """Get AI client instance."""
        if self._ai_client is None:
            self._ai_client = await get_ai_client(self.db)
        return self._ai_client

    async def _get_feature_manager(self) -> AIFeatureManager:
        """Get feature manager instance."""
        if self._feature_manager is None:
            self._feature_manager = AIFeatureManager(self.db)
        return self._feature_manager

    async def get_suggestions(
        self,
        user_id: int,
        partial_description: Optional[str] = None,
        limit: int = 5,
        use_ai: bool = True
    ) -> Dict[str, Any]:
        """
        Get time entry suggestions for user.
        
        Args:
            user_id: User requesting suggestions
            partial_description: Optional text user is typing
            limit: Max number of suggestions
            use_ai: Whether to use AI enhancement
            
        Returns:
            Dict with suggestions list and metadata
        """
        try:
            # Check if feature is enabled
            fm = await self._get_feature_manager()
            if not await fm.is_enabled("ai_suggestions", user_id):
                return {
                    "suggestions": [],
                    "enabled": False,
                    "message": "AI suggestions are disabled"
                }

            # Check rate limit
            if self.cache:
                allowed, count = await self.cache.check_rate_limit(user_id)
                if not allowed:
                    return {
                        "suggestions": [],
                        "rate_limited": True,
                        "message": "Rate limit exceeded"
                    }

            # Build context
            time_context = TimeContext.from_datetime(datetime.now())
            user_context = await self._build_user_context(user_id)
            
            # Check cache first
            cache_key_context = {
                "user_id": user_id,
                "hour": time_context.hour,
                "day": time_context.day_of_week.value,
                "partial": partial_description or ""
            }
            
            if self.cache:
                cached = await self.cache.get_suggestion_cache(user_id, cache_key_context)
                if cached:
                    logger.info(f"Returning cached suggestions for user {user_id}")
                    return cached

            # Stage 1: Pattern-based suggestions
            suggestions = await self._get_pattern_suggestions(
                user_context,
                time_context,
                partial_description
            )

            # Stage 2: AI enhancement (if enabled and needed)
            if use_ai and len(suggestions) < limit:
                try:
                    ai_suggestions = await self._get_ai_suggestions(
                        user_context,
                        time_context,
                        partial_description
                    )
                    # Merge AI suggestions (avoid duplicates)
                    existing_ids = {s.project_id for s in suggestions}
                    for ai_sug in ai_suggestions:
                        if ai_sug.project_id not in existing_ids:
                            suggestions.append(ai_sug)
                except AIProviderError as e:
                    logger.warning(f"AI suggestions failed: {e}, using pattern-only")

            # Sort by confidence and limit
            suggestions.sort(key=lambda x: x.confidence, reverse=True)
            suggestions = suggestions[:limit]

            # Filter by confidence threshold
            suggestions = [
                s for s in suggestions 
                if s.confidence >= ai_settings.SUGGESTION_CONFIDENCE_THRESHOLD
            ]

            result = {
                "suggestions": [s.to_dict() for s in suggestions],
                "enabled": True,
                "total_found": len(suggestions),
                "context": {
                    "time_of_day": time_context.time_of_day.value,
                    "day_of_week": time_context.day_of_week.value
                }
            }

            # Cache result
            if self.cache and suggestions:
                await self.cache.set_suggestion_cache(
                    user_id,
                    cache_key_context,
                    result
                )

            # Log usage
            await fm.log_usage(
                user_id=user_id,
                feature_id="ai_suggestions",
                tokens_used=0
            )

            return result

        except Exception as e:
            logger.error(f"Error getting suggestions for user {user_id}: {e}")
            return {
                "suggestions": [],
                "error": str(e),
                "enabled": True
            }

    async def _build_user_context(self, user_id: int) -> UserContext:
        """Build user context from database."""
        from app.models import User, TimeEntry, Project, Task
        
        # Get user info
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise ValueError(f"User {user_id} not found")

        context = UserContext(
            user_id=user_id,
            user_name=user.name,
            department=getattr(user, 'department', None),
            expected_hours_per_week=float(user.expected_hours_per_week) if user.expected_hours_per_week else 40.0
        )

        # Get recent time entries
        lookback_date = datetime.now() - timedelta(days=ai_settings.SUGGESTION_LOOKBACK_DAYS)
        
        entries_query = await self.db.execute(
            select(TimeEntry, Project.name.label("project_name"), Task.name.label("task_name"))
            .join(Project, TimeEntry.project_id == Project.id)
            .outerjoin(Task, TimeEntry.task_id == Task.id)
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    TimeEntry.start_time >= lookback_date
                )
            )
            .order_by(TimeEntry.start_time.desc())
            .limit(100)
        )
        entries = entries_query.all()

        context.recent_entries = [
            {
                "project_id": e.TimeEntry.project_id,
                "project_name": e.project_name,
                "task_id": e.TimeEntry.task_id,
                "task_name": e.task_name,
                "description": e.TimeEntry.description,
                "start_time": e.TimeEntry.start_time,
                "duration_hours": (
                    (e.TimeEntry.end_time - e.TimeEntry.start_time).total_seconds() / 3600
                    if e.TimeEntry.end_time else 0
                ),
                "day": e.TimeEntry.start_time.strftime("%A")
            }
            for e in entries
        ]

        # Get active projects (not archived)
        projects_query = await self.db.execute(
            select(Project)
            .where(Project.is_archived == False)
            .limit(50)
        )
        projects = projects_query.scalars().all()
        
        context.active_projects = [
            {"id": p.id, "name": p.name}
            for p in projects
        ]

        # Compute common projects
        project_counts: Dict[int, int] = {}
        for entry in context.recent_entries:
            pid = entry["project_id"]
            project_counts[pid] = project_counts.get(pid, 0) + 1
        
        context.most_common_projects = sorted(
            [
                {"project_id": pid, "count": count}
                for pid, count in project_counts.items()
            ],
            key=lambda x: x["count"],
            reverse=True
        )[:5]

        return context

    async def _get_pattern_suggestions(
        self,
        user_context: UserContext,
        time_context: TimeContext,
        partial_description: Optional[str] = None
    ) -> List[SuggestionResult]:
        """Generate pattern-based suggestions."""
        suggestions = []
        
        # Create feature set
        features = SuggestionFeatures(
            user_context=user_context,
            time_context=time_context,
            partial_description=partial_description
        )
        features.compute_project_frequencies(user_context.recent_entries)
        features.compute_time_slot_patterns(user_context.recent_entries)
        
        if partial_description:
            features.extract_keywords()

        # Build project lookup
        project_lookup = {p["id"]: p for p in user_context.active_projects}

        # Strategy 1: Most frequent projects
        for project_info in user_context.most_common_projects[:3]:
            pid = project_info["project_id"]
            if pid in project_lookup:
                proj = project_lookup[pid]
                freq = features.project_frequencies.get(pid, 0)
                suggestions.append(SuggestionResult(
                    project_id=pid,
                    project_name=proj["name"],
                    confidence=min(0.9, 0.5 + freq * 0.5),  # Base + frequency bonus
                    reason="Frequently used project",
                    source="pattern"
                ))

        # Strategy 2: Time-of-day patterns
        time_slot = time_context.time_of_day.value
        if time_slot in ["morning", "afternoon", "evening"]:
            slot_key = "morning" if time_slot in ["morning", "early_morning"] else time_slot
            slot_projects = features.time_slot_patterns.get(slot_key, [])
            
            for pid in slot_projects[:2]:
                if pid in project_lookup and pid not in {s.project_id for s in suggestions}:
                    proj = project_lookup[pid]
                    suggestions.append(SuggestionResult(
                        project_id=pid,
                        project_name=proj["name"],
                        confidence=0.6,
                        reason=f"Often used in the {slot_key}",
                        source="pattern"
                    ))

        # Strategy 3: Recent entries (most recent project)
        if user_context.recent_entries:
            recent = user_context.recent_entries[0]
            pid = recent["project_id"]
            if pid in project_lookup and pid not in {s.project_id for s in suggestions}:
                proj = project_lookup[pid]
                suggestions.append(SuggestionResult(
                    project_id=pid,
                    project_name=proj["name"],
                    task_id=recent.get("task_id"),
                    task_name=recent.get("task_name"),
                    suggested_description=recent.get("description"),
                    confidence=0.7,
                    reason="Your most recent entry",
                    source="recent"
                ))

        # Strategy 4: Keyword matching (if partial description)
        if features.description_keywords:
            for entry in user_context.recent_entries[:20]:
                desc = (entry.get("description") or "").lower()
                matches = sum(1 for kw in features.description_keywords if kw in desc)
                if matches > 0:
                    pid = entry["project_id"]
                    if pid in project_lookup and pid not in {s.project_id for s in suggestions}:
                        proj = project_lookup[pid]
                        suggestions.append(SuggestionResult(
                            project_id=pid,
                            project_name=proj["name"],
                            task_id=entry.get("task_id"),
                            task_name=entry.get("task_name"),
                            suggested_description=entry.get("description"),
                            confidence=0.5 + (matches * 0.1),
                            reason="Matches your description",
                            source="pattern"
                        ))
                        break

        return suggestions

    async def _get_ai_suggestions(
        self,
        user_context: UserContext,
        time_context: TimeContext,
        partial_description: Optional[str] = None
    ) -> List[SuggestionResult]:
        """Get AI-enhanced suggestions."""
        try:
            client = await self._get_ai_client()
            
            if not client.is_initialized:
                return []

            system_prompt = PromptTemplates.suggestion_system_prompt()
            user_prompt = PromptTemplates.suggestion_user_prompt(
                user_name=user_context.user_name,
                current_time=time_context.current_datetime,
                day_of_week=time_context.day_of_week.value.capitalize(),
                recent_entries=user_context.recent_entries[:10],
                available_projects=user_context.active_projects,
                partial_description=partial_description
            )

            response = await client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=ai_settings.GEMINI_TEMPERATURE,
                max_tokens=500,
                feature="ai_suggestions"
            )

            suggestions = []
            data = response.get("data", {})
            
            if isinstance(data, dict) and "suggestions" in data:
                project_lookup = {p["id"]: p for p in user_context.active_projects}
                
                for sug in data["suggestions"][:5]:
                    pid = sug.get("project_id")
                    if pid and pid in project_lookup:
                        suggestions.append(SuggestionResult(
                            project_id=pid,
                            project_name=sug.get("project_name", project_lookup[pid]["name"]),
                            task_id=sug.get("task_id"),
                            task_name=sug.get("task_name"),
                            suggested_description=sug.get("suggested_description"),
                            confidence=float(sug.get("confidence", 0.5)),
                            reason=sug.get("reason", "AI suggested"),
                            source="ai"
                        ))

            return suggestions

        except Exception as e:
            logger.error(f"AI suggestion generation failed: {e}")
            return []

    async def record_feedback(
        self,
        user_id: int,
        suggestion_project_id: int,
        accepted: bool,
        actual_project_id: Optional[int] = None
    ) -> bool:
        """
        Record user feedback on suggestion.
        This data improves future suggestions.
        """
        try:
            fm = await self._get_feature_manager()
            await fm.log_usage(
                user_id=user_id,
                feature_id="ai_suggestions",
                metadata={
                    "suggestion_project_id": suggestion_project_id,
                    "accepted": accepted,
                    "actual_project_id": actual_project_id
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to record suggestion feedback: {e}")
            return False


# Factory function
async def get_suggestion_service(db: AsyncSession) -> SuggestionService:
    """Create suggestion service instance."""
    cache = await get_cache_manager()
    return SuggestionService(db, cache)
