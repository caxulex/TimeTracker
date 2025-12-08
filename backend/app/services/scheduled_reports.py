"""
Scheduled Reports Service - TASK-031
Email digests and scheduled report generation
"""

import redis
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from app.config import settings

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

SCHEDULED_REPORTS_KEY = "scheduled_reports:configs"
REPORT_HISTORY_KEY = "scheduled_reports:history"


class ScheduleFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class ScheduledReport:
    """Scheduled report configuration"""
    id: str
    name: str
    template_id: str
    frequency: str
    recipients: List[str]
    user_id: int
    enabled: bool = True
    last_sent: Optional[str] = None
    next_run: Optional[str] = None
    params: Optional[Dict] = None
    created_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "template_id": self.template_id,
            "frequency": self.frequency,
            "recipients": self.recipients,
            "user_id": self.user_id,
            "enabled": self.enabled,
            "last_sent": self.last_sent,
            "next_run": self.next_run,
            "params": self.params or {},
            "created_at": self.created_at
        }


class ScheduledReportService:
    """Service for managing scheduled reports"""
    
    @staticmethod
    def _generate_id() -> str:
        """Generate unique report ID"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    @staticmethod
    def _calculate_next_run(frequency: str) -> str:
        """Calculate next run time based on frequency"""
        now = datetime.utcnow()
        
        if frequency == ScheduleFrequency.DAILY.value:
            next_run = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
        elif frequency == ScheduleFrequency.WEEKLY.value:
            # Monday at 8 AM
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0 and now.hour >= 8:
                days_until_monday = 7
            next_run = now.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=days_until_monday)
        elif frequency == ScheduleFrequency.MONTHLY.value:
            # First day of next month at 8 AM
            if now.month == 12:
                next_run = datetime(now.year + 1, 1, 1, 8, 0, 0)
            else:
                next_run = datetime(now.year, now.month + 1, 1, 8, 0, 0)
        else:
            next_run = now + timedelta(days=1)
        
        return next_run.isoformat()
    
    @staticmethod
    def create_scheduled_report(
        name: str,
        template_id: str,
        frequency: str,
        recipients: List[str],
        user_id: int,
        params: Optional[Dict] = None
    ) -> ScheduledReport:
        """Create a new scheduled report"""
        report = ScheduledReport(
            id=ScheduledReportService._generate_id(),
            name=name,
            template_id=template_id,
            frequency=frequency,
            recipients=recipients,
            user_id=user_id,
            enabled=True,
            next_run=ScheduledReportService._calculate_next_run(frequency),
            params=params,
            created_at=datetime.utcnow().isoformat()
        )
        
        redis_client.hset(SCHEDULED_REPORTS_KEY, report.id, json.dumps(report.to_dict()))
        return report
    
    @staticmethod
    def get_scheduled_report(report_id: str) -> Optional[ScheduledReport]:
        """Get a scheduled report by ID"""
        data = redis_client.hget(SCHEDULED_REPORTS_KEY, report_id)
        if data:
            d = json.loads(data)
            return ScheduledReport(**d)
        return None
    
    @staticmethod
    def get_user_scheduled_reports(user_id: int) -> List[ScheduledReport]:
        """Get all scheduled reports for a user"""
        all_reports = redis_client.hgetall(SCHEDULED_REPORTS_KEY)
        reports = []
        for data in all_reports.values():
            d = json.loads(data)
            if d.get("user_id") == user_id:
                reports.append(ScheduledReport(**d))
        return reports
    
    @staticmethod
    def get_all_scheduled_reports() -> List[ScheduledReport]:
        """Get all scheduled reports (admin)"""
        all_reports = redis_client.hgetall(SCHEDULED_REPORTS_KEY)
        return [ScheduledReport(**json.loads(data)) for data in all_reports.values()]
    
    @staticmethod
    def update_scheduled_report(
        report_id: str,
        name: Optional[str] = None,
        frequency: Optional[str] = None,
        recipients: Optional[List[str]] = None,
        enabled: Optional[bool] = None,
        params: Optional[Dict] = None
    ) -> Optional[ScheduledReport]:
        """Update a scheduled report"""
        report = ScheduledReportService.get_scheduled_report(report_id)
        if not report:
            return None
        
        if name is not None:
            report.name = name
        if frequency is not None:
            report.frequency = frequency
            report.next_run = ScheduledReportService._calculate_next_run(frequency)
        if recipients is not None:
            report.recipients = recipients
        if enabled is not None:
            report.enabled = enabled
        if params is not None:
            report.params = params
        
        redis_client.hset(SCHEDULED_REPORTS_KEY, report.id, json.dumps(report.to_dict()))
        return report
    
    @staticmethod
    def delete_scheduled_report(report_id: str) -> bool:
        """Delete a scheduled report"""
        return bool(redis_client.hdel(SCHEDULED_REPORTS_KEY, report_id))
    
    @staticmethod
    def get_due_reports() -> List[ScheduledReport]:
        """Get reports that are due to run"""
        now = datetime.utcnow()
        due_reports = []
        
        all_reports = ScheduledReportService.get_all_scheduled_reports()
        for report in all_reports:
            if report.enabled and report.next_run:
                next_run = datetime.fromisoformat(report.next_run)
                if next_run <= now:
                    due_reports.append(report)
        
        return due_reports
    
    @staticmethod
    def mark_report_sent(report_id: str) -> Optional[ScheduledReport]:
        """Mark a report as sent and update next run time"""
        report = ScheduledReportService.get_scheduled_report(report_id)
        if not report:
            return None
        
        report.last_sent = datetime.utcnow().isoformat()
        report.next_run = ScheduledReportService._calculate_next_run(report.frequency)
        
        redis_client.hset(SCHEDULED_REPORTS_KEY, report.id, json.dumps(report.to_dict()))
        
        # Log to history
        history_entry = {
            "report_id": report.id,
            "report_name": report.name,
            "sent_at": report.last_sent,
            "recipients": report.recipients
        }
        redis_client.lpush(f"{REPORT_HISTORY_KEY}:{report.user_id}", json.dumps(history_entry))
        redis_client.ltrim(f"{REPORT_HISTORY_KEY}:{report.user_id}", 0, 99)
        
        return report
    
    @staticmethod
    def get_report_history(user_id: int, limit: int = 20) -> List[Dict]:
        """Get report sending history for a user"""
        history = redis_client.lrange(f"{REPORT_HISTORY_KEY}:{user_id}", 0, limit - 1)
        return [json.loads(h) for h in history]
    
    @staticmethod
    def toggle_report(report_id: str) -> Optional[ScheduledReport]:
        """Toggle report enabled/disabled status"""
        report = ScheduledReportService.get_scheduled_report(report_id)
        if not report:
            return None
        
        report.enabled = not report.enabled
        redis_client.hset(SCHEDULED_REPORTS_KEY, report.id, json.dumps(report.to_dict()))
        return report
