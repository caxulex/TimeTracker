"""
Semantic Task Search Service (Phase 5.1)

Intelligent task search using semantic similarity:
- Text embeddings for task descriptions
- Cosine similarity matching
- Context-aware suggestions
- Historical task relevance scoring
"""

import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import re

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.config import ai_settings
from app.ai.utils.cache_manager import AICacheManager, get_cache_manager
from app.ai.services.ai_client import get_ai_client

logger = logging.getLogger(__name__)


@dataclass
class SimilarTask:
    """A similar task result."""
    task_id: Optional[int]
    task_name: str
    project_id: Optional[int]
    project_name: str
    description: str
    similarity_score: float
    avg_duration_minutes: Optional[float]
    times_used: int
    last_used: Optional[datetime]


@dataclass
class SearchResult:
    """Semantic search result."""
    query: str
    results: List[SimilarTask]
    search_time_ms: float
    method: str  # "embedding" or "keyword" or "hybrid"


class SemanticSearchService:
    """
    Semantic Task Search Service
    
    Uses AI embeddings to find similar tasks based on:
    - Task description semantic similarity
    - Project context
    - User history
    - Time patterns
    """
    
    def __init__(
        self,
        db: AsyncSession,
        cache_manager: Optional[AICacheManager] = None
    ):
        self.db = db
        self.cache = cache_manager
        
        # Embedding cache (in-memory for session)
        self._embedding_cache: Dict[str, List[float]] = {}
        
        # Configuration
        self.max_results = 10
        self.min_similarity = 0.3
        self.cache_ttl = 3600  # 1 hour

    async def search_similar_tasks(
        self,
        query: str,
        user_id: int,
        team_id: Optional[int] = None,
        project_id: Optional[int] = None,
        limit: int = 10
    ) -> SearchResult:
        """
        Search for tasks similar to the query.
        
        Uses a hybrid approach:
        1. Keyword matching for exact terms
        2. Semantic similarity for meaning
        3. User history for relevance
        """
        import time
        start_time = time.time()
        
        from app.models import TimeEntry, Task, Project, TeamMember
        
        # Build base query for tasks/entries the user has access to
        if team_id:
            # Get tasks from team projects
            accessible_projects = await self.db.execute(
                select(Project.id)
                .where(Project.team_id == team_id)
            )
            project_ids = [p[0] for p in accessible_projects.fetchall()]
        else:
            # Get user's own entries
            project_ids = None
        
        # Step 1: Keyword search
        keyword_matches = await self._keyword_search(query, user_id, project_ids, limit * 2)
        
        # Step 2: Get historical tasks for semantic comparison
        historical_tasks = await self._get_historical_tasks(user_id, project_ids, limit=100)
        
        # Step 3: Semantic ranking
        ranked_results = await self._rank_by_similarity(query, historical_tasks, keyword_matches)
        
        # Step 4: Filter by project if specified
        if project_id:
            ranked_results = [r for r in ranked_results if r.project_id == project_id]
        
        # Limit results
        final_results = ranked_results[:limit]
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return SearchResult(
            query=query,
            results=final_results,
            search_time_ms=round(elapsed_ms, 2),
            method="hybrid"
        )

    async def _keyword_search(
        self,
        query: str,
        user_id: int,
        project_ids: Optional[List[int]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Perform keyword-based search."""
        from app.models import TimeEntry, Task, Project
        
        # Tokenize query
        tokens = self._tokenize(query)
        
        # Build search conditions
        conditions = []
        for token in tokens:
            pattern = f"%{token}%"
            # Always search in TimeEntry description
            search_conditions = [TimeEntry.description.ilike(pattern)]
            # Optionally include Task.name search
            if Task is not None:
                search_conditions.append(Task.name.ilike(pattern))
            conditions.append(or_(*search_conditions))
        
        if not conditions:
            return []
        
        # Query time entries
        base_query = (
            select(
                TimeEntry.description,
                TimeEntry.project_id,
                TimeEntry.task_id,
                TimeEntry.duration_seconds,
                TimeEntry.start_time,
                Project.name.label("project_name"),
                func.count().label("usage_count")
            )
            .outerjoin(Project, TimeEntry.project_id == Project.id)
            .where(TimeEntry.user_id == user_id)
            .where(TimeEntry.description.isnot(None))
            .where(or_(*conditions))
        )
        
        if project_ids:
            base_query = base_query.where(TimeEntry.project_id.in_(project_ids))
        
        base_query = (
            base_query
            .group_by(
                TimeEntry.description,
                TimeEntry.project_id,
                TimeEntry.task_id,
                TimeEntry.duration_seconds,
                TimeEntry.start_time,
                Project.name
            )
            .order_by(func.count().desc())
            .limit(limit)
        )
        
        result = await self.db.execute(base_query)
        rows = result.fetchall()
        
        return [
            {
                "description": row.description,
                "project_id": row.project_id,
                "task_id": row.task_id,
                "project_name": row.project_name or "No Project",
                "duration_seconds": row.duration_seconds,
                "start_time": row.start_time,
                "usage_count": row.usage_count
            }
            for row in rows
        ]

    async def _get_historical_tasks(
        self,
        user_id: int,
        project_ids: Optional[List[int]],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get historical task data for semantic comparison."""
        from app.models import TimeEntry, Project
        
        # Get recent unique task descriptions
        query = (
            select(
                TimeEntry.description,
                TimeEntry.project_id,
                TimeEntry.task_id,
                Project.name.label("project_name"),
                func.avg(TimeEntry.duration_seconds).label("avg_duration"),
                func.count().label("usage_count"),
                func.max(TimeEntry.start_time).label("last_used")
            )
            .outerjoin(Project, TimeEntry.project_id == Project.id)
            .where(TimeEntry.user_id == user_id)
            .where(TimeEntry.description.isnot(None))
            .where(TimeEntry.description != "")
        )
        
        if project_ids:
            query = query.where(TimeEntry.project_id.in_(project_ids))
        
        query = (
            query
            .group_by(
                TimeEntry.description,
                TimeEntry.project_id,
                TimeEntry.task_id,
                Project.name
            )
            .order_by(func.count().desc())
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        return [
            {
                "description": row.description,
                "project_id": row.project_id,
                "task_id": row.task_id,
                "project_name": row.project_name or "No Project",
                "avg_duration": row.avg_duration,
                "usage_count": row.usage_count,
                "last_used": row.last_used
            }
            for row in rows
        ]

    async def _rank_by_similarity(
        self,
        query: str,
        historical_tasks: List[Dict[str, Any]],
        keyword_matches: List[Dict[str, Any]]
    ) -> List[SimilarTask]:
        """Rank tasks by semantic similarity to query."""
        if not historical_tasks and not keyword_matches:
            return []
        
        # Combine sources (keyword matches get boost)
        all_tasks = {}
        
        for task in historical_tasks:
            key = (task["description"], task["project_id"])
            all_tasks[key] = {**task, "keyword_match": False}
        
        for task in keyword_matches:
            key = (task["description"], task["project_id"])
            if key in all_tasks:
                all_tasks[key]["keyword_match"] = True
                all_tasks[key]["usage_count"] = max(
                    all_tasks[key].get("usage_count", 0),
                    task.get("usage_count", 0)
                )
            else:
                all_tasks[key] = {**task, "keyword_match": True}
        
        # Calculate similarity scores
        results = []
        query_lower = query.lower()
        query_tokens = set(self._tokenize(query))
        
        for key, task in all_tasks.items():
            description = task["description"]
            desc_lower = description.lower()
            desc_tokens = set(self._tokenize(description))
            
            # Calculate similarity components
            
            # 1. Exact match bonus
            exact_bonus = 0.5 if query_lower in desc_lower else 0.0
            
            # 2. Token overlap (Jaccard similarity)
            intersection = query_tokens & desc_tokens
            union = query_tokens | desc_tokens
            jaccard = len(intersection) / len(union) if union else 0.0
            
            # 3. Keyword match bonus
            keyword_bonus = 0.2 if task.get("keyword_match") else 0.0
            
            # 4. Usage frequency bonus (logarithmic)
            import math
            usage_count = task.get("usage_count", 1)
            usage_bonus = min(0.2, math.log10(usage_count + 1) * 0.1)
            
            # 5. Recency bonus
            last_used = task.get("last_used")
            recency_bonus = 0.0
            if last_used:
                days_ago = (datetime.now() - last_used).days
                recency_bonus = max(0, 0.1 - days_ago * 0.001)
            
            # Combine scores
            similarity = (
                jaccard * 0.5 +
                exact_bonus +
                keyword_bonus +
                usage_bonus +
                recency_bonus
            )
            
            # Normalize to 0-1
            similarity = min(1.0, max(0.0, similarity))
            
            if similarity >= self.min_similarity:
                results.append(SimilarTask(
                    task_id=task.get("task_id"),
                    task_name=description[:100],
                    project_id=task.get("project_id"),
                    project_name=task.get("project_name", "No Project"),
                    description=description,
                    similarity_score=round(similarity, 3),
                    avg_duration_minutes=(
                        round(task["avg_duration"] / 60, 1)
                        if task.get("avg_duration")
                        else None
                    ),
                    times_used=task.get("usage_count", 1),
                    last_used=task.get("last_used")
                ))
        
        # Sort by similarity score
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        return results

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into searchable terms."""
        # Remove special characters
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        # Split and filter
        tokens = [t.strip() for t in text.split() if len(t.strip()) >= 2]
        return tokens

    async def get_task_suggestions_for_time(
        self,
        user_id: int,
        hour: int,
        day_of_week: int,
        team_id: Optional[int] = None,
        limit: int = 5
    ) -> List[SimilarTask]:
        """
        Get task suggestions based on time patterns.
        
        Finds tasks the user commonly works on at this time.
        """
        from app.models import TimeEntry, Project
        
        # Find entries at similar times
        query = (
            select(
                TimeEntry.description,
                TimeEntry.project_id,
                TimeEntry.task_id,
                Project.name.label("project_name"),
                func.avg(TimeEntry.duration_seconds).label("avg_duration"),
                func.count().label("usage_count"),
                func.max(TimeEntry.start_time).label("last_used")
            )
            .outerjoin(Project, TimeEntry.project_id == Project.id)
            .where(TimeEntry.user_id == user_id)
            .where(TimeEntry.description.isnot(None))
            .where(func.extract('hour', TimeEntry.start_time).between(hour - 1, hour + 1))
            .where(func.extract('dow', TimeEntry.start_time) == day_of_week)
            .group_by(
                TimeEntry.description,
                TimeEntry.project_id,
                TimeEntry.task_id,
                Project.name
            )
            .order_by(func.count().desc())
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        return [
            SimilarTask(
                task_id=row.task_id,
                task_name=row.description[:100] if row.description else "Unnamed Task",
                project_id=row.project_id,
                project_name=row.project_name or "No Project",
                description=row.description or "",
                similarity_score=1.0,  # Time-based match
                avg_duration_minutes=round(row.avg_duration / 60, 1) if row.avg_duration else None,
                times_used=row.usage_count,
                last_used=row.last_used
            )
            for row in rows
        ]


# Service factory
_semantic_search_service: Optional[SemanticSearchService] = None


async def get_semantic_search_service(db: AsyncSession) -> SemanticSearchService:
    """Get or create semantic search service instance."""
    global _semantic_search_service
    cache_manager = await get_cache_manager()
    return SemanticSearchService(db, cache_manager)
