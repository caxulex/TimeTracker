"""
API Routers
"""
from app.routers import (
    auth,
    pay_rates,
    payroll,
    payroll_reports,
    projects,
    reports,
    tasks,
    teams,
    time_entries,
    users,
    websocket,
)

__all__ = [
    "auth", "users", "teams", "projects", "tasks",
    "time_entries", "reports", "websocket",
    "pay_rates", "payroll", "payroll_reports"
]
