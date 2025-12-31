"""
Feature Engineering for AI Models

Data models and utilities for preparing features for AI predictions.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, time, date, timedelta
from enum import Enum


class DayOfWeek(str, Enum):
    """Day of week enum."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class TimeOfDay(str, Enum):
    """Time of day categories."""
    EARLY_MORNING = "early_morning"  # 5:00 - 8:59
    MORNING = "morning"              # 9:00 - 11:59
    AFTERNOON = "afternoon"          # 12:00 - 16:59
    EVENING = "evening"              # 17:00 - 20:59
    NIGHT = "night"                  # 21:00 - 4:59


@dataclass
class TimeContext:
    """Context about current time for predictions."""
    current_datetime: datetime
    day_of_week: DayOfWeek
    time_of_day: TimeOfDay
    is_weekend: bool
    hour: int
    minute: int

    @classmethod
    def from_datetime(cls, dt: Optional[datetime] = None) -> "TimeContext":
        """Create TimeContext from datetime."""
        if dt is None:
            dt = datetime.now()
        
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        dow = DayOfWeek(day_names[dt.weekday()])
        
        hour = dt.hour
        if 5 <= hour < 9:
            tod = TimeOfDay.EARLY_MORNING
        elif 9 <= hour < 12:
            tod = TimeOfDay.MORNING
        elif 12 <= hour < 17:
            tod = TimeOfDay.AFTERNOON
        elif 17 <= hour < 21:
            tod = TimeOfDay.EVENING
        else:
            tod = TimeOfDay.NIGHT
        
        return cls(
            current_datetime=dt,
            day_of_week=dow,
            time_of_day=tod,
            is_weekend=dt.weekday() >= 5,
            hour=hour,
            minute=dt.minute
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for caching/serialization."""
        return {
            "current_datetime": self.current_datetime.isoformat(),
            "day_of_week": self.day_of_week.value,
            "time_of_day": self.time_of_day.value,
            "is_weekend": self.is_weekend,
            "hour": self.hour,
            "minute": self.minute
        }


@dataclass
class UserContext:
    """Context about user for AI predictions."""
    user_id: int
    user_name: str
    department: Optional[str] = None
    job_title: Optional[str] = None
    expected_hours_per_week: float = 40.0
    manager_id: Optional[int] = None
    
    # Computed from history
    avg_entries_per_day: float = 0.0
    most_common_projects: List[Dict[str, Any]] = field(default_factory=list)
    most_common_tasks: List[Dict[str, Any]] = field(default_factory=list)
    typical_start_time: Optional[time] = None
    typical_end_time: Optional[time] = None
    
    # Recent activity
    recent_entries: List[Dict[str, Any]] = field(default_factory=list)
    active_projects: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for caching/serialization."""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "department": self.department,
            "job_title": self.job_title,
            "expected_hours_per_week": self.expected_hours_per_week,
            "avg_entries_per_day": self.avg_entries_per_day,
            "most_common_projects": self.most_common_projects,
            "most_common_tasks": self.most_common_tasks,
            "typical_start_time": self.typical_start_time.isoformat() if self.typical_start_time else None,
            "typical_end_time": self.typical_end_time.isoformat() if self.typical_end_time else None,
            "recent_entries_count": len(self.recent_entries),
            "active_projects_count": len(self.active_projects)
        }


@dataclass
class SuggestionFeatures:
    """Features for time entry suggestion model."""
    user_context: UserContext
    time_context: TimeContext
    partial_description: Optional[str] = None
    
    # Computed features
    project_frequencies: Dict[int, float] = field(default_factory=dict)
    task_frequencies: Dict[int, float] = field(default_factory=dict)
    time_slot_patterns: Dict[str, List[int]] = field(default_factory=dict)
    description_keywords: List[str] = field(default_factory=list)

    def compute_project_frequencies(self, entries: List[Dict[str, Any]]) -> None:
        """Compute project frequency scores from recent entries."""
        if not entries:
            return
        
        # Count occurrences
        project_counts: Dict[int, int] = {}
        for entry in entries:
            pid = entry.get("project_id")
            if pid:
                project_counts[pid] = project_counts.get(pid, 0) + 1
        
        # Normalize to frequencies
        total = sum(project_counts.values())
        self.project_frequencies = {
            pid: count / total 
            for pid, count in project_counts.items()
        }

    def compute_time_slot_patterns(self, entries: List[Dict[str, Any]]) -> None:
        """Compute which projects are commonly used at which times."""
        patterns: Dict[str, Dict[int, int]] = {}
        
        for entry in entries:
            start_time = entry.get("start_time")
            if not start_time:
                continue
            
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            
            # Determine time slot
            hour = start_time.hour
            if 5 <= hour < 12:
                slot = "morning"
            elif 12 <= hour < 17:
                slot = "afternoon"
            else:
                slot = "evening"
            
            pid = entry.get("project_id")
            if pid:
                if slot not in patterns:
                    patterns[slot] = {}
                patterns[slot][pid] = patterns[slot].get(pid, 0) + 1
        
        # Convert to sorted lists of project IDs
        self.time_slot_patterns = {
            slot: sorted(projects.keys(), key=lambda p: projects[p], reverse=True)
            for slot, projects in patterns.items()
        }

    def extract_keywords(self) -> None:
        """Extract keywords from partial description."""
        if not self.partial_description:
            return
        
        # Simple keyword extraction
        text = self.partial_description.lower()
        # Remove common words
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "on", "in", "at", "for", "to"}
        words = text.split()
        self.description_keywords = [w for w in words if w not in stop_words and len(w) > 2]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API/caching."""
        return {
            "user_context": self.user_context.to_dict(),
            "time_context": self.time_context.to_dict(),
            "partial_description": self.partial_description,
            "project_frequencies": self.project_frequencies,
            "time_slot_patterns": self.time_slot_patterns,
            "description_keywords": self.description_keywords
        }


@dataclass
class AnomalyFeatures:
    """Features for anomaly detection."""
    user_id: int
    user_name: str
    period_start: date
    period_end: date
    expected_hours_per_day: float = 8.0
    
    # Daily metrics
    daily_hours: Dict[str, float] = field(default_factory=dict)  # date -> hours
    daily_entry_counts: Dict[str, int] = field(default_factory=dict)  # date -> count
    
    # Computed metrics
    total_hours: float = 0.0
    avg_hours_per_day: float = 0.0
    max_hours_day: float = 0.0
    min_hours_day: float = 0.0
    days_worked: int = 0
    weekend_hours: float = 0.0
    
    # Pattern metrics
    consecutive_long_days: int = 0
    days_over_threshold: int = 0
    missing_days: List[str] = field(default_factory=list)
    
    def compute_metrics(self) -> None:
        """Compute all metrics from daily data."""
        if not self.daily_hours:
            return
        
        hours_list = list(self.daily_hours.values())
        self.total_hours = sum(hours_list)
        self.days_worked = len([h for h in hours_list if h > 0])
        self.avg_hours_per_day = self.total_hours / self.days_worked if self.days_worked > 0 else 0
        self.max_hours_day = max(hours_list) if hours_list else 0
        self.min_hours_day = min([h for h in hours_list if h > 0], default=0)
        
        # Compute weekend hours
        self.weekend_hours = 0.0
        for date_str, hours in self.daily_hours.items():
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
                if d.weekday() >= 5:  # Saturday or Sunday
                    self.weekend_hours += hours
            except ValueError:
                pass
        
        # Compute consecutive long days
        self._compute_consecutive_long_days()
        
        # Find missing days
        self._find_missing_days()

    def _compute_consecutive_long_days(self, threshold: float = 10.0) -> None:
        """Count maximum consecutive days over threshold."""
        dates = sorted(self.daily_hours.keys())
        max_consecutive = 0
        current_consecutive = 0
        
        for date_str in dates:
            hours = self.daily_hours[date_str]
            if hours >= threshold:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
                self.days_over_threshold += 1
            else:
                current_consecutive = 0
        
        self.consecutive_long_days = max_consecutive

    def _find_missing_days(self) -> None:
        """Find weekdays with no time entries."""
        current = self.period_start
        while current <= self.period_end:
            # Skip weekends
            if current.weekday() < 5:  # Monday to Friday
                date_str = current.strftime("%Y-%m-%d")
                hours = self.daily_hours.get(date_str, 0)
                if hours < 1:  # Less than 1 hour logged
                    self.missing_days.append(date_str)
            current += timedelta(days=1)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_hours": round(self.total_hours, 2),
            "avg_hours_per_day": round(self.avg_hours_per_day, 2),
            "max_hours_day": round(self.max_hours_day, 2),
            "min_hours_day": round(self.min_hours_day, 2),
            "days_worked": self.days_worked,
            "weekend_hours": round(self.weekend_hours, 2),
            "consecutive_long_days": self.consecutive_long_days,
            "days_over_threshold": self.days_over_threshold,
            "missing_days_count": len(self.missing_days)
        }
