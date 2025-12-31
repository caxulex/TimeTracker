"""
NLP Service

Natural Language Processing service for:
- Parsing natural language time entries
- Entity extraction (project, task, duration, date)
- Fuzzy matching against user's projects/tasks
- Conversational time entry creation

Uses AI (Gemini/OpenAI) for understanding natural language
and structured function calling for entity extraction.
"""

import logging
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass, field
from enum import Enum
from difflib import SequenceMatcher
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.config import ai_settings
from app.ai.services.ai_client import get_ai_client, AIClient
from app.ai.utils.cache_manager import get_cache_manager
from app.services.ai_feature_service import AIFeatureManager

logger = logging.getLogger(__name__)


class ParseConfidence(str, Enum):
    """Confidence levels for NLP parsing."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ParsedDuration:
    """Parsed duration from natural language."""
    seconds: int
    original_text: str
    confidence: float


@dataclass
class ParsedDate:
    """Parsed date from natural language."""
    date: date
    original_text: str
    confidence: float


@dataclass
class ParsedEntity:
    """A parsed entity from natural language input."""
    entity_type: str  # project, task, duration, date, description
    value: Any
    original_text: str
    confidence: float
    matched_id: Optional[int] = None  # ID if matched to database record


@dataclass
class NLPParseResult:
    """Result of parsing natural language time entry."""
    original_text: str
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    task_id: Optional[int] = None
    task_name: Optional[str] = None
    duration_seconds: Optional[int] = None
    duration_display: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    confidence: float = 0.0
    confidence_level: ParseConfidence = ParseConfidence.LOW
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    parsed_entities: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_text": self.original_text,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "duration_seconds": self.duration_seconds,
            "duration_display": self.duration_display,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "description": self.description,
            "confidence": round(self.confidence, 3),
            "confidence_level": self.confidence_level.value,
            "needs_clarification": self.needs_clarification,
            "clarification_question": self.clarification_question,
            "parsed_entities": self.parsed_entities,
            "suggestions": self.suggestions
        }


class NLPService:
    """
    Service for natural language time entry processing.
    
    Parses text like:
    - "Log 2 hours on Project Alpha yesterday"
    - "3h client meeting for Project Beta"
    - "worked 45 min on bug fixes this morning"
    """
    
    # Duration patterns
    DURATION_PATTERNS = [
        # "2 hours", "2h", "2hrs"
        (r'(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b', lambda m: int(float(m.group(1)) * 3600)),
        # "30 minutes", "30min", "30m"
        (r'(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|m)\b', lambda m: int(float(m.group(1)) * 60)),
        # "1:30" or "1h30m" or "1h 30m"
        (r'(\d+):(\d+)', lambda m: int(m.group(1)) * 3600 + int(m.group(2)) * 60),
        (r'(\d+)h\s*(\d+)m?', lambda m: int(m.group(1)) * 3600 + int(m.group(2)) * 60),
        # "1 and a half hours"
        (r'(\d+)\s+and\s+a\s+half\s+hours?', lambda m: int(float(m.group(1)) * 3600 + 1800)),
        # "half hour", "half an hour"
        (r'half\s+(?:an?\s+)?hours?', lambda m: 1800),
        # "quarter hour"
        (r'quarter\s+hours?', lambda m: 900),
    ]
    
    # Date patterns
    DATE_KEYWORDS = {
        "today": lambda: date.today(),
        "yesterday": lambda: date.today() - timedelta(days=1),
        "tomorrow": lambda: date.today() + timedelta(days=1),
        "last week": lambda: date.today() - timedelta(weeks=1),
        "this morning": lambda: date.today(),
        "this afternoon": lambda: date.today(),
        "this evening": lambda: date.today(),
    }
    
    # Day of week patterns
    DAYS_OF_WEEK = {
        "monday": 0, "mon": 0,
        "tuesday": 1, "tue": 1, "tues": 1,
        "wednesday": 2, "wed": 2,
        "thursday": 3, "thu": 3, "thurs": 3,
        "friday": 4, "fri": 4,
        "saturday": 5, "sat": 5,
        "sunday": 6, "sun": 6,
    }
    
    def __init__(
        self,
        db: AsyncSession,
        ai_client: Optional[AIClient] = None
    ):
        self.db = db
        self.ai_client = ai_client
        self._feature_manager: Optional[AIFeatureManager] = None
    
    async def _get_feature_manager(self) -> AIFeatureManager:
        """Get or create feature manager."""
        if self._feature_manager is None:
            self._feature_manager = AIFeatureManager(self.db)
        return self._feature_manager
    
    async def parse_time_entry(
        self,
        text: str,
        user_id: int,
        timezone: str = "UTC",
        use_ai: bool = True
    ) -> Dict[str, Any]:
        """
        Parse natural language into time entry fields.
        
        Args:
            text: Natural language input
            user_id: User ID for context
            timezone: User's timezone
            use_ai: Whether to use AI for enhancement
            
        Returns:
            Dict with parsed fields and confidence
        """
        try:
            # Check if feature is enabled
            fm = await self._get_feature_manager()
            if not await fm.is_enabled("ai_nlp_entry", user_id):
                return {
                    "success": False,
                    "enabled": False,
                    "message": "Natural language entry is disabled"
                }
            
            # Clean input
            text = text.strip()
            if not text:
                return {
                    "success": False,
                    "error": "Empty input"
                }
            
            # Get user's projects and tasks for matching
            projects = await self._get_user_projects(user_id)
            tasks = await self._get_user_tasks(user_id)
            
            # Start with rule-based parsing
            result = NLPParseResult(original_text=text)
            
            # Parse duration
            duration_info = self._parse_duration(text)
            if duration_info:
                result.duration_seconds = duration_info.seconds
                result.duration_display = self._format_duration(duration_info.seconds)
                result.parsed_entities.append({
                    "type": "duration",
                    "value": duration_info.seconds,
                    "display": result.duration_display,
                    "original": duration_info.original_text,
                    "confidence": duration_info.confidence
                })
            
            # Parse date
            date_info = self._parse_date(text, timezone)
            if date_info:
                result.start_time = datetime.combine(date_info.date, datetime.min.time())
                if result.duration_seconds:
                    result.end_time = result.start_time + timedelta(seconds=result.duration_seconds)
                result.parsed_entities.append({
                    "type": "date",
                    "value": date_info.date.isoformat(),
                    "original": date_info.original_text,
                    "confidence": date_info.confidence
                })
            else:
                # Default to today
                result.start_time = datetime.combine(date.today(), datetime.min.time())
                if result.duration_seconds:
                    result.end_time = result.start_time + timedelta(seconds=result.duration_seconds)
            
            # Match project
            project_match = self._match_project(text, projects)
            if project_match:
                result.project_id = project_match["id"]
                result.project_name = project_match["name"]
                result.parsed_entities.append({
                    "type": "project",
                    "value": project_match["name"],
                    "id": project_match["id"],
                    "confidence": project_match["confidence"]
                })
            
            # Match task
            if result.project_id:
                task_match = self._match_task(text, tasks, result.project_id)
                if task_match:
                    result.task_id = task_match["id"]
                    result.task_name = task_match["name"]
                    result.parsed_entities.append({
                        "type": "task",
                        "value": task_match["name"],
                        "id": task_match["id"],
                        "confidence": task_match["confidence"]
                    })
            
            # Extract description (remaining text after removing parsed entities)
            result.description = self._extract_description(text, result)
            
            # Calculate overall confidence
            result.confidence = self._calculate_confidence(result)
            result.confidence_level = self._get_confidence_level(result.confidence)
            
            # Use AI for enhancement if confidence is low
            if use_ai and self.ai_client and result.confidence < 0.7:
                enhanced = await self._enhance_with_ai(
                    text, user_id, projects, tasks, result
                )
                if enhanced:
                    result = enhanced
            
            # Check if clarification needed
            if result.confidence < ai_settings.NLP_CONFIDENCE_THRESHOLD:
                result.needs_clarification = True
                result.clarification_question = self._generate_clarification(result)
            
            # Add suggestions if project not matched
            if not result.project_id and projects:
                result.suggestions = [
                    {"id": p["id"], "name": p["name"]}
                    for p in projects[:5]
                ]
            
            # Log usage
            await fm.log_usage(
                user_id=user_id,
                feature_id="ai_nlp_entry",
                metadata={
                    "confidence": result.confidence,
                    "used_ai": use_ai and self.ai_client is not None
                }
            )
            
            return {
                "success": True,
                "enabled": True,
                "result": result.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Error parsing time entry: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _parse_duration(self, text: str) -> Optional[ParsedDuration]:
        """Parse duration from text."""
        text_lower = text.lower()
        
        for pattern, converter in self.DURATION_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    seconds = converter(match)
                    return ParsedDuration(
                        seconds=seconds,
                        original_text=match.group(0),
                        confidence=0.9
                    )
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _parse_date(self, text: str, timezone: str = "UTC") -> Optional[ParsedDate]:
        """Parse date from text."""
        text_lower = text.lower()
        
        # Check keyword dates first
        for keyword, date_func in self.DATE_KEYWORDS.items():
            if keyword in text_lower:
                return ParsedDate(
                    date=date_func(),
                    original_text=keyword,
                    confidence=0.95
                )
        
        # Check day of week
        for day_name, day_num in self.DAYS_OF_WEEK.items():
            if day_name in text_lower:
                # Find the most recent occurrence of this day
                today = date.today()
                days_since = (today.weekday() - day_num) % 7
                if days_since == 0:
                    days_since = 7  # Last week's same day
                target_date = today - timedelta(days=days_since)
                
                # Check if "next" is mentioned
                if f"next {day_name}" in text_lower:
                    target_date = today + timedelta(days=(day_num - today.weekday()) % 7 or 7)
                
                return ParsedDate(
                    date=target_date,
                    original_text=day_name,
                    confidence=0.85
                )
        
        # Try dateutil parser for explicit dates
        try:
            # Remove duration patterns first to avoid confusion
            clean_text = re.sub(r'\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b', '', text_lower)
            parsed = date_parser.parse(clean_text, fuzzy=True, dayfirst=False)
            if parsed.date() != date.today():  # Only use if not defaulting to today
                return ParsedDate(
                    date=parsed.date(),
                    original_text="",
                    confidence=0.7
                )
        except (ValueError, TypeError):
            pass
        
        return None
    
    def _match_project(
        self,
        text: str,
        projects: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Match text against user's projects using fuzzy matching."""
        if not projects:
            return None
        
        text_lower = text.lower()
        best_match = None
        best_score = 0.0
        
        for project in projects:
            project_name_lower = project["name"].lower()
            
            # Exact match
            if project_name_lower in text_lower:
                return {
                    "id": project["id"],
                    "name": project["name"],
                    "confidence": 0.95
                }
            
            # Fuzzy match
            score = SequenceMatcher(None, project_name_lower, text_lower).ratio()
            
            # Check if any word from project name is in text
            project_words = project_name_lower.split()
            word_matches = sum(1 for word in project_words if len(word) > 2 and word in text_lower)
            word_score = word_matches / len(project_words) if project_words else 0
            
            combined_score = max(score, word_score)
            
            if combined_score > best_score and combined_score > 0.3:
                best_score = combined_score
                best_match = {
                    "id": project["id"],
                    "name": project["name"],
                    "confidence": combined_score
                }
        
        return best_match
    
    def _match_task(
        self,
        text: str,
        tasks: List[Dict[str, Any]],
        project_id: int
    ) -> Optional[Dict[str, Any]]:
        """Match text against tasks for a specific project."""
        project_tasks = [t for t in tasks if t.get("project_id") == project_id]
        if not project_tasks:
            return None
        
        text_lower = text.lower()
        best_match = None
        best_score = 0.0
        
        for task in project_tasks:
            task_name_lower = task["name"].lower()
            
            # Exact match
            if task_name_lower in text_lower:
                return {
                    "id": task["id"],
                    "name": task["name"],
                    "confidence": 0.95
                }
            
            # Fuzzy match
            score = SequenceMatcher(None, task_name_lower, text_lower).ratio()
            
            if score > best_score and score > 0.4:
                best_score = score
                best_match = {
                    "id": task["id"],
                    "name": task["name"],
                    "confidence": score
                }
        
        return best_match
    
    def _extract_description(
        self,
        text: str,
        result: NLPParseResult
    ) -> str:
        """Extract description from remaining text."""
        description = text
        
        # Remove duration patterns
        for pattern, _ in self.DURATION_PATTERNS:
            description = re.sub(pattern, '', description, flags=re.IGNORECASE)
        
        # Remove date keywords
        for keyword in self.DATE_KEYWORDS.keys():
            description = re.sub(rf'\b{keyword}\b', '', description, flags=re.IGNORECASE)
        
        # Remove day names
        for day_name in self.DAYS_OF_WEEK.keys():
            description = re.sub(rf'\b{day_name}\b', '', description, flags=re.IGNORECASE)
        
        # Remove project name if matched
        if result.project_name:
            description = re.sub(
                rf'\b{re.escape(result.project_name)}\b',
                '',
                description,
                flags=re.IGNORECASE
            )
        
        # Remove task name if matched
        if result.task_name:
            description = re.sub(
                rf'\b{re.escape(result.task_name)}\b',
                '',
                description,
                flags=re.IGNORECASE
            )
        
        # Remove common filler words
        filler_words = ['on', 'for', 'at', 'in', 'worked', 'log', 'logged', 'spent', 'doing']
        for word in filler_words:
            description = re.sub(rf'\b{word}\b', '', description, flags=re.IGNORECASE)
        
        # Clean up whitespace
        description = ' '.join(description.split())
        
        return description.strip()
    
    def _calculate_confidence(self, result: NLPParseResult) -> float:
        """Calculate overall confidence score."""
        scores = []
        weights = []
        
        # Duration is important
        if result.duration_seconds:
            scores.append(0.9)
            weights.append(0.3)
        else:
            scores.append(0.0)
            weights.append(0.3)
        
        # Project is critical
        if result.project_id:
            project_conf = next(
                (e["confidence"] for e in result.parsed_entities if e["type"] == "project"),
                0.5
            )
            scores.append(project_conf)
            weights.append(0.4)
        else:
            scores.append(0.0)
            weights.append(0.4)
        
        # Task is nice to have
        if result.task_id:
            task_conf = next(
                (e["confidence"] for e in result.parsed_entities if e["type"] == "task"),
                0.5
            )
            scores.append(task_conf)
            weights.append(0.2)
        else:
            scores.append(0.3)  # Partial credit if no task
            weights.append(0.2)
        
        # Date
        if any(e["type"] == "date" for e in result.parsed_entities):
            scores.append(0.9)
            weights.append(0.1)
        else:
            scores.append(0.5)  # Default to today is acceptable
            weights.append(0.1)
        
        # Weighted average
        total_weight = sum(weights)
        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _get_confidence_level(self, confidence: float) -> ParseConfidence:
        """Convert numeric confidence to level."""
        if confidence >= 0.8:
            return ParseConfidence.HIGH
        elif confidence >= 0.5:
            return ParseConfidence.MEDIUM
        else:
            return ParseConfidence.LOW
    
    def _generate_clarification(self, result: NLPParseResult) -> str:
        """Generate a clarification question."""
        missing = []
        
        if not result.duration_seconds:
            missing.append("how long")
        
        if not result.project_id:
            missing.append("which project")
        
        if missing:
            return f"Could you clarify {' and '.join(missing)}?"
        
        return "Could you provide more details?"
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in human-readable form."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        
        return " ".join(parts) or "0m"
    
    async def _get_user_projects(self, user_id: int) -> List[Dict[str, Any]]:
        """Get projects accessible to user."""
        from app.models import Project, TeamMember, Team
        
        # Get user's team IDs
        team_result = await self.db.execute(
            select(TeamMember.team_id)
            .where(TeamMember.user_id == user_id)
        )
        team_ids = [row[0] for row in team_result.fetchall()]
        
        # Get projects from those teams
        if team_ids:
            result = await self.db.execute(
                select(Project)
                .where(
                    and_(
                        Project.team_id.in_(team_ids),
                        Project.is_archived == False
                    )
                )
                .order_by(Project.name)
            )
            projects = result.scalars().all()
        else:
            # Fallback: get all non-archived projects
            result = await self.db.execute(
                select(Project)
                .where(Project.is_archived == False)
                .limit(50)
            )
            projects = result.scalars().all()
        
        return [
            {"id": p.id, "name": p.name, "team_id": p.team_id}
            for p in projects
        ]
    
    async def _get_user_tasks(self, user_id: int) -> List[Dict[str, Any]]:
        """Get tasks from user's projects."""
        from app.models import Task, Project, TeamMember
        
        # Get user's team IDs
        team_result = await self.db.execute(
            select(TeamMember.team_id)
            .where(TeamMember.user_id == user_id)
        )
        team_ids = [row[0] for row in team_result.fetchall()]
        
        if team_ids:
            result = await self.db.execute(
                select(Task)
                .join(Project, Task.project_id == Project.id)
                .where(
                    and_(
                        Project.team_id.in_(team_ids),
                        Project.is_archived == False
                    )
                )
            )
            tasks = result.scalars().all()
        else:
            result = await self.db.execute(
                select(Task)
                .join(Project, Task.project_id == Project.id)
                .where(Project.is_archived == False)
                .limit(100)
            )
            tasks = result.scalars().all()
        
        return [
            {"id": t.id, "name": t.name, "project_id": t.project_id}
            for t in tasks
        ]
    
    async def _enhance_with_ai(
        self,
        text: str,
        user_id: int,
        projects: List[Dict[str, Any]],
        tasks: List[Dict[str, Any]],
        current_result: NLPParseResult
    ) -> Optional[NLPParseResult]:
        """Use AI to enhance parsing results."""
        if not self.ai_client:
            return None
        
        try:
            # Build context prompt
            project_list = ", ".join([p["name"] for p in projects[:10]])
            
            prompt = f"""Parse this time entry request and extract the relevant information.

User said: "{text}"

Available projects: {project_list}

Extract:
1. Duration (in hours and minutes)
2. Project name (must match one from the list above)
3. Task description
4. Date (relative to today: {date.today().isoformat()})

Return a JSON object with:
{{
    "duration_hours": number,
    "duration_minutes": number,
    "project_name": string or null,
    "description": string,
    "date": "YYYY-MM-DD" or null
}}

Be precise. If unsure, set to null."""

            response = await self.ai_client.generate(
                system_prompt="You are a precise time entry parser. Return only valid JSON.",
                user_prompt=prompt,
                max_tokens=300,
                temperature=0.1
            )
            
            if not response or not response.get("data"):
                return None
            
            # Parse AI response
            data = response["data"]
            content = data.get("raw_text", "") if isinstance(data, dict) else str(data)
            
            # Try to extract JSON
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if not json_match:
                return None
            
            ai_result = json.loads(json_match.group())
            
            # Create enhanced result
            enhanced = NLPParseResult(original_text=text)
            
            # Duration
            hours = ai_result.get("duration_hours", 0) or 0
            minutes = ai_result.get("duration_minutes", 0) or 0
            if hours or minutes:
                enhanced.duration_seconds = int(hours * 3600 + minutes * 60)
                enhanced.duration_display = self._format_duration(enhanced.duration_seconds)
            elif current_result.duration_seconds:
                enhanced.duration_seconds = current_result.duration_seconds
                enhanced.duration_display = current_result.duration_display
            
            # Project - use AI suggestion for matching
            ai_project_name = ai_result.get("project_name")
            if ai_project_name:
                # Find best match
                for project in projects:
                    if project["name"].lower() == ai_project_name.lower():
                        enhanced.project_id = project["id"]
                        enhanced.project_name = project["name"]
                        break
                    elif ai_project_name.lower() in project["name"].lower():
                        enhanced.project_id = project["id"]
                        enhanced.project_name = project["name"]
                        break
            
            # Fall back to rule-based if AI didn't match
            if not enhanced.project_id and current_result.project_id:
                enhanced.project_id = current_result.project_id
                enhanced.project_name = current_result.project_name
            
            # Description
            enhanced.description = ai_result.get("description") or current_result.description
            
            # Date
            ai_date = ai_result.get("date")
            if ai_date:
                try:
                    enhanced.start_time = datetime.combine(
                        date.fromisoformat(ai_date),
                        datetime.min.time()
                    )
                except ValueError:
                    enhanced.start_time = current_result.start_time
            else:
                enhanced.start_time = current_result.start_time
            
            if enhanced.start_time and enhanced.duration_seconds:
                enhanced.end_time = enhanced.start_time + timedelta(seconds=enhanced.duration_seconds)
            
            # Recalculate confidence (AI-enhanced gets a boost)
            enhanced.confidence = min(self._calculate_confidence(enhanced) + 0.15, 1.0)
            enhanced.confidence_level = self._get_confidence_level(enhanced.confidence)
            
            return enhanced
            
        except Exception as e:
            logger.error(f"AI enhancement failed: {e}")
            return None
    
    async def confirm_entry(
        self,
        user_id: int,
        parsed_result: Dict[str, Any],
        modifications: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Confirm and create time entry from parsed result.
        
        Args:
            user_id: User ID
            parsed_result: Previously parsed result
            modifications: User modifications
            
        Returns:
            Created time entry or error
        """
        try:
            from app.models import TimeEntry
            
            # Merge modifications
            entry_data = {
                "project_id": parsed_result.get("project_id"),
                "task_id": parsed_result.get("task_id"),
                "duration_seconds": parsed_result.get("duration_seconds"),
                "start_time": parsed_result.get("start_time"),
                "end_time": parsed_result.get("end_time"),
                "description": parsed_result.get("description", "")
            }
            
            if modifications:
                entry_data.update(modifications)
            
            # Validate required fields
            if not entry_data.get("project_id"):
                return {"success": False, "error": "Project is required"}
            
            if not entry_data.get("duration_seconds") and not entry_data.get("start_time"):
                return {"success": False, "error": "Duration or start time is required"}
            
            # Parse datetime if string
            if isinstance(entry_data.get("start_time"), str):
                entry_data["start_time"] = datetime.fromisoformat(entry_data["start_time"])
            if isinstance(entry_data.get("end_time"), str):
                entry_data["end_time"] = datetime.fromisoformat(entry_data["end_time"])
            
            # Create time entry
            time_entry = TimeEntry(
                user_id=user_id,
                project_id=entry_data["project_id"],
                task_id=entry_data.get("task_id"),
                start_time=entry_data.get("start_time") or datetime.now(),
                end_time=entry_data.get("end_time"),
                duration_seconds=entry_data.get("duration_seconds"),
                description=entry_data.get("description", ""),
                is_running=False
            )
            
            self.db.add(time_entry)
            await self.db.commit()
            await self.db.refresh(time_entry)
            
            return {
                "success": True,
                "time_entry_id": time_entry.id,
                "message": "Time entry created successfully"
            }
            
        except Exception as e:
            logger.error(f"Error creating time entry: {e}")
            await self.db.rollback()
            return {"success": False, "error": str(e)}


# Factory function
async def get_nlp_service(db: AsyncSession) -> NLPService:
    """Create NLP service instance."""
    ai_client = await get_ai_client(db)
    return NLPService(db, ai_client)
