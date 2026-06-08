"""
API Routers
"""
from app.routers import (
    auth,
    categories,
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
    "auth", "users", "teams", "projects", "tasks", "categories",
    "time_entries", "reports", "websocket",
    "pay_rates", "payroll", "payroll_reports"
]
