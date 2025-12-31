"""
Prompt Templates for AI Services

Centralized prompt templates for all AI features.
Ensures consistent formatting and easy maintenance.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


class PromptTemplates:
    """Centralized prompt templates for AI services."""

    # ============================================
    # TIME ENTRY SUGGESTION PROMPTS
    # ============================================

    @staticmethod
    def suggestion_system_prompt() -> str:
        """System prompt for time entry suggestion AI."""
        return """You are an intelligent assistant for a time tracking application. 
Your job is to suggest the most likely project and task a user wants to work on based on:
1. Their historical work patterns
2. Current time of day and day of week
3. Recent activity
4. Any partial description they've entered

Respond ONLY with valid JSON in this exact format:
{
  "suggestions": [
    {
      "project_id": <int>,
      "project_name": "<string>",
      "task_id": <int or null>,
      "task_name": "<string or null>",
      "suggested_description": "<string>",
      "confidence": <float 0.0-1.0>,
      "reason": "<brief explanation>"
    }
  ]
}

Rules:
- Return 3-5 suggestions ordered by confidence (highest first)
- Confidence should reflect how likely this is what the user wants
- Only suggest projects the user has access to
- Be concise in reasons (max 50 chars)"""

    @staticmethod
    def suggestion_user_prompt(
        user_name: str,
        current_time: datetime,
        day_of_week: str,
        recent_entries: List[Dict[str, Any]],
        available_projects: List[Dict[str, Any]],
        partial_description: Optional[str] = None
    ) -> str:
        """User prompt for time entry suggestion."""
        recent_str = "\n".join([
            f"- {e['project_name']}/{e.get('task_name', 'No task')}: "
            f"{e.get('description', 'No description')} "
            f"({e['duration_hours']:.1f}h on {e['day']})"
            for e in recent_entries[:10]
        ]) if recent_entries else "No recent entries"

        projects_str = "\n".join([
            f"- ID:{p['id']} {p['name']}" + 
            (f" (Tasks: {', '.join([t['name'] for t in p.get('tasks', [])])})" if p.get('tasks') else "")
            for p in available_projects[:15]
        ]) if available_projects else "No projects available"

        prompt = f"""User: {user_name}
Current time: {current_time.strftime('%H:%M')} on {day_of_week}

Recent time entries (last 7 days):
{recent_str}

Available projects:
{projects_str}
"""
        if partial_description:
            prompt += f"\nUser is typing: \"{partial_description}\"\n"
        
        prompt += "\nSuggest the most likely project/task combinations:"
        return prompt

    # ============================================
    # ANOMALY DETECTION PROMPTS
    # ============================================

    @staticmethod
    def anomaly_analysis_system_prompt() -> str:
        """System prompt for anomaly analysis AI enhancement."""
        return """You are a workplace wellness and compliance analyst assistant.
You help identify concerning patterns in employee time tracking data.

Your role is to:
1. Analyze time entry patterns for potential issues
2. Identify burnout risks
3. Flag unusual work patterns
4. Suggest appropriate responses

Be compassionate and focus on employee wellbeing, not punishment.
Format responses as JSON with actionable recommendations."""

    @staticmethod
    def anomaly_report_prompt(
        user_name: str,
        anomalies: List[Dict[str, Any]],
        time_summary: Dict[str, Any]
    ) -> str:
        """Generate a human-readable anomaly report."""
        anomalies_str = "\n".join([
            f"- {a['type']}: {a['description']} (Severity: {a['severity']})"
            for a in anomalies
        ]) if anomalies else "No anomalies detected"

        return f"""Employee: {user_name}

Time Summary (Last 7 Days):
- Total Hours: {time_summary.get('total_hours', 0):.1f}
- Average Per Day: {time_summary.get('avg_per_day', 0):.1f}
- Days Worked: {time_summary.get('days_worked', 0)}

Detected Anomalies:
{anomalies_str}

Provide:
1. Overall assessment (1-2 sentences)
2. Risk level (low/medium/high/critical)
3. Recommended actions (2-3 bullet points)"""

    # ============================================
    # DESCRIPTION GENERATION PROMPTS
    # ============================================

    @staticmethod
    def description_suggestion_prompt(
        project_name: str,
        task_name: Optional[str],
        recent_descriptions: List[str]
    ) -> str:
        """Generate suggested description for time entry."""
        recent_str = "\n".join([f"- {d}" for d in recent_descriptions[:5]]) if recent_descriptions else "None"
        
        task_info = f" on task '{task_name}'" if task_name else ""
        
        return f"""Project: {project_name}{task_info}

Recent descriptions for similar entries:
{recent_str}

Generate a concise, professional description (10-30 words) that the user might want to use.
Return ONLY the description text, no quotes or explanation."""

    # ============================================
    # NLP PARSING PROMPTS (Phase 3)
    # ============================================

    @staticmethod
    def nlp_parse_system_prompt() -> str:
        """System prompt for NLP time entry parsing."""
        return """You are a time entry parser. Convert natural language into structured time entry data.

Extract:
- Duration (in hours/minutes)
- Project name (fuzzy match against provided list)
- Task name (if mentioned)
- Date/time (relative to current date)
- Description

Respond ONLY with valid JSON:
{
  "duration_seconds": <int>,
  "project_match": "<best matching project name>",
  "project_confidence": <float 0.0-1.0>,
  "task_match": "<best matching task name or null>",
  "task_confidence": <float 0.0-1.0>,
  "start_time": "<ISO 8601 datetime>",
  "end_time": "<ISO 8601 datetime or null>",
  "description": "<extracted or generated description>",
  "parse_confidence": <float 0.0-1.0>,
  "clarification_needed": "<question if confidence < 0.7 or null>"
}"""

    @staticmethod
    def nlp_parse_user_prompt(
        text: str,
        current_datetime: datetime,
        timezone: str,
        available_projects: List[Dict[str, Any]]
    ) -> str:
        """User prompt for NLP parsing."""
        projects_str = ", ".join([p['name'] for p in available_projects[:20]])
        
        return f"""Current date/time: {current_datetime.isoformat()} ({timezone})

User's input: "{text}"

Available projects: {projects_str}

Parse this time entry request:"""

    # ============================================
    # REPORT SUMMARY PROMPTS (Phase 3)
    # ============================================

    @staticmethod
    def weekly_summary_prompt(
        user_name: str,
        week_data: Dict[str, Any],
        comparison_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate weekly summary report."""
        comparison_str = ""
        if comparison_data:
            comparison_str = f"""
Last Week Comparison:
- Hours: {comparison_data.get('total_hours', 0):.1f}h
- Projects: {comparison_data.get('project_count', 0)}
"""
        
        return f"""Generate a brief, insightful weekly summary for {user_name}.

This Week:
- Total Hours: {week_data.get('total_hours', 0):.1f}
- Projects Worked: {week_data.get('project_count', 0)}
- Tasks Completed: {week_data.get('tasks_completed', 0)}
- Most Time On: {week_data.get('top_project', 'N/A')}
- Busiest Day: {week_data.get('busiest_day', 'N/A')}
{comparison_str}

Write a 3-4 sentence summary highlighting:
1. Key accomplishment or focus area
2. Work pattern observation
3. One suggestion for next week

Keep tone positive and professional."""


# Singleton instance
prompt_templates = PromptTemplates()
