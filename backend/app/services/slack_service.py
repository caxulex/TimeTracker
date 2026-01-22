"""
Slack Notification Service

Sends notifications to Slack channels via webhooks.
Simple, reliable, and requires no additional dependencies.
"""

import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class SlackNotificationService:
    """
    Service for sending Slack notifications via webhooks.
    
    Setup:
    1. Go to https://api.slack.com/apps
    2. Create a new app or use existing one
    3. Enable "Incoming Webhooks"
    4. Add webhook to your channel
    5. Copy the webhook URL to SLACK_WEBHOOK_URL env variable
    
    Usage:
        slack = SlackNotificationService()
        await slack.send_message("Hello from TimeTracker!")
    """
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or getattr(settings, 'SLACK_WEBHOOK_URL', None)
        self.app_name = getattr(settings, 'APP_NAME', 'Time Tracker')
        self.enabled = bool(self.webhook_url)
    
    async def send_message(
        self,
        text: str,
        channel: Optional[str] = None,
        username: Optional[str] = None,
        icon_emoji: Optional[str] = ":clock1:",
        blocks: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Send a simple text message to Slack.
        
        Args:
            text: The message text
            channel: Override default channel (optional)
            username: Override bot username (optional)
            icon_emoji: Emoji icon for the bot (optional)
            blocks: Slack Block Kit blocks for rich formatting (optional)
            
        Returns:
            bool: True if message was sent successfully
        """
        if not self.enabled:
            logger.debug("Slack notifications disabled (no webhook URL)")
            return False
        
        payload = {
            "text": text,
            "username": username or self.app_name,
            "icon_emoji": icon_emoji
        }
        
        if channel:
            payload["channel"] = channel
        
        if blocks:
            payload["blocks"] = blocks
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logger.info(f"Slack notification sent: {text[:50]}...")
                    return True
                else:
                    logger.error(f"Slack webhook failed: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False
    
    async def send_payroll_notification(
        self,
        period_name: str,
        total_employees: int,
        total_amount: float,
        status: str = "processed"
    ) -> bool:
        """Send payroll processing notification"""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"💰 Payroll {status.title()}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Period:*\n{period_name}"},
                    {"type": "mrkdwn", "text": f"*Status:*\n{status.title()}"},
                    {"type": "mrkdwn", "text": f"*Employees:*\n{total_employees}"},
                    {"type": "mrkdwn", "text": f"*Total Amount:*\n${total_amount:,.2f}"}
                ]
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Processed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
                ]
            }
        ]
        
        return await self.send_message(
            text=f"Payroll {status}: {period_name} - {total_employees} employees - ${total_amount:,.2f}",
            blocks=blocks,
            icon_emoji=":moneybag:"
        )
    
    async def send_user_notification(
        self,
        event_type: str,
        user_name: str,
        user_email: str,
        details: Optional[str] = None
    ) -> bool:
        """Send user-related notification (registration, approval, etc.)"""
        emoji_map = {
            "registered": ":wave:",
            "approved": ":white_check_mark:",
            "rejected": ":x:",
            "invited": ":email:",
            "joined": ":tada:"
        }
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji_map.get(event_type, ':bust_in_silhouette:')} *User {event_type.title()}*\n*Name:* {user_name}\n*Email:* {user_email}"
                }
            }
        ]
        
        if details:
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": details}]
            })
        
        return await self.send_message(
            text=f"User {event_type}: {user_name} ({user_email})",
            blocks=blocks,
            icon_emoji=emoji_map.get(event_type, ":bust_in_silhouette:")
        )
    
    async def send_system_alert(
        self,
        title: str,
        message: str,
        severity: str = "info"
    ) -> bool:
        """Send system alert notification"""
        emoji_map = {
            "info": ":information_source:",
            "warning": ":warning:",
            "error": ":rotating_light:",
            "success": ":white_check_mark:"
        }
        
        color_map = {
            "info": "#2196F3",
            "warning": "#FFC107",
            "error": "#F44336",
            "success": "#4CAF50"
        }
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji_map.get(severity, ':bell:')} {title}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"*Severity:* {severity.upper()} | *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
                ]
            }
        ]
        
        return await self.send_message(
            text=f"[{severity.upper()}] {title}: {message}",
            blocks=blocks,
            icon_emoji=emoji_map.get(severity, ":bell:")
        )
    
    async def send_backup_notification(
        self,
        backup_file: str,
        backup_size: str,
        status: str = "completed"
    ) -> bool:
        """Send database backup notification"""
        emoji = ":white_check_mark:" if status == "completed" else ":x:"
        
        return await self.send_message(
            text=f"{emoji} Database Backup {status.title()}\nFile: {backup_file}\nSize: {backup_size}",
            icon_emoji=":floppy_disk:"
        )


# Singleton instance
slack_service = SlackNotificationService()


# Convenience functions
async def notify_slack(message: str) -> bool:
    """Quick way to send a Slack message"""
    return await slack_service.send_message(message)


async def notify_payroll_processed(period_name: str, employees: int, amount: float) -> bool:
    """Notify when payroll is processed"""
    return await slack_service.send_payroll_notification(period_name, employees, amount, "processed")


async def notify_user_registered(name: str, email: str) -> bool:
    """Notify when a new user registers"""
    return await slack_service.send_user_notification("registered", name, email)


async def notify_user_approved(name: str, email: str) -> bool:
    """Notify when a user is approved"""
    return await slack_service.send_user_notification("approved", name, email)
