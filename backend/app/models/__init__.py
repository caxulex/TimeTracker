"""
SQLAlchemy models for Time Tracker
"""

import enum
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


# ============================================
# ENUMS
# ============================================

class RateType(str, enum.Enum):
    """Pay rate type enumeration"""
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"
    PROJECT_BASED = "project_based"


class PeriodType(str, enum.Enum):
    """Payroll period type enumeration"""
    WEEKLY = "weekly"
    BI_WEEKLY = "bi_weekly"
    SEMI_MONTHLY = "semi_monthly"
    MONTHLY = "monthly"


class PeriodStatus(str, enum.Enum):
    """Payroll period status enumeration"""
    DRAFT = "draft"
    PROCESSING = "processing"
    APPROVED = "approved"
    PAID = "paid"
    VOID = "void"


class EntryStatus(str, enum.Enum):
    """Payroll entry status enumeration"""
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"


class AccountRequestStatus(str, enum.Enum):
    """Account request status enumeration"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AdjustmentType(str, enum.Enum):
    """Payroll adjustment type enumeration"""
    BONUS = "bonus"
    DEDUCTION = "deduction"
    REIMBURSEMENT = "reimbursement"
    TAX = "tax"
    OTHER = "other"


class SubscriptionTier(str, enum.Enum):
    """Company subscription tier enumeration"""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class CompanyStatus(str, enum.Enum):
    """Company status enumeration"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    CANCELLED = "cancelled"


# ============================================
# COMPANY / MULTI-TENANT MODELS
# ============================================

class Company(Base):
    """
    Company/Tenant model for multi-tenant support.
    Each company is a separate tenant with their own users, teams, and data.
    """
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)  # URL-safe identifier
    email: Mapped[str] = mapped_column(String(255), nullable=False)  # Primary contact email
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Subscription
    subscription_tier: Mapped[str] = mapped_column(String(50), default="trial", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="trial", nullable=False)
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    subscription_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Limits (based on tier)
    max_users: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_projects: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # Settings
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    date_format: Mapped[str] = mapped_column(String(20), default="YYYY-MM-DD", nullable=False)
    time_format: Mapped[str] = mapped_column(String(20), default="HH:mm", nullable=False)

    # Email/SMTP Configuration
    smtp_server: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int] = mapped_column(Integer, default=587, nullable=False)
    smtp_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    smtp_password_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    smtp_from_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    smtp_from_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Overtime / payroll configuration (C2 - per-company FLSA opt-in)
    overtime_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    overtime_threshold_hours_per_week: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("40.00"), server_default="40.00", nullable=False
    )
    overtime_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), default=Decimal("1.50"), server_default="1.50", nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    white_label_config: Mapped[Optional["WhiteLabelConfig"]] = relationship("WhiteLabelConfig", back_populates="company", uselist=False)
    teams: Mapped[list["Team"]] = relationship("Team", back_populates="company")

    def __repr__(self) -> str:
        return f"<Company(id={self.id}, name={self.name}, slug={self.slug})>"


class WhiteLabelConfig(Base):
    """
    White-label configuration for company branding.
    Allows each company to customize the look and feel of the application.
    """
    __tablename__ = "white_label_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Domain Configuration
    custom_domain: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    subdomain: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)  # xyz-corp.timetracker.com

    # Branding - Application Identity
    app_name: Mapped[str] = mapped_column(String(100), default="Time Tracker", nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tagline: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Branding - Visual Assets
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    favicon_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    login_background_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Branding - Colors (hex format)
    primary_color: Mapped[str] = mapped_column(String(7), default="#2563eb", nullable=False)
    secondary_color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    accent_color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)

    # Contact & Support
    support_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    support_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Legal Links
    terms_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    privacy_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Display Options
    show_powered_by: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    custom_css: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Custom CSS overrides
    custom_js: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Custom JS (careful with security)

    # Email Customization
    email_from_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_from_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="white_label_config")

    def __repr__(self) -> str:
        return f"<WhiteLabelConfig(company_id={self.company_id}, app_name={self.app_name})>"


# ============================================
# EXISTING MODELS
# ============================================

class User(Base):
    """User model with comprehensive staff information"""
    __tablename__ = "users"

    # Basic Identity
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="regular_user")  # super_admin, company_admin, team_lead, regular_user
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Multi-tenant: Company association (nullable for platform super_admins)
    company_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)

    # Contact Information
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Employment Details
    job_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    employment_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)  # full_time, part_time, contractor
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expected_hours_per_week: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    manager_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    company: Mapped[Optional["Company"]] = relationship("Company", foreign_keys=[company_id])
    teams: Mapped[list["TeamMember"]] = relationship("TeamMember", back_populates="user")
    time_entries: Mapped[list["TimeEntry"]] = relationship("TimeEntry", back_populates="user")
    pay_rates: Mapped[list["PayRate"]] = relationship("PayRate", back_populates="user", foreign_keys="PayRate.user_id")
    payroll_entries: Mapped[list["PayrollEntry"]] = relationship("PayrollEntry", back_populates="user")
    manager: Mapped[Optional["User"]] = relationship("User", remote_side=[id], foreign_keys=[manager_id])
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    work_sessions: Mapped[list["WorkSession"]] = relationship("WorkSession", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role}, company_id={self.company_id})>"


class Team(Base):
    """Team model"""
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    # Multi-tenancy: company isolation
    company_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    owner: Mapped[User] = relationship("User")
    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="teams")
    members: Mapped[list["TeamMember"]] = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="team", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Team(id={self.id}, name={self.name}, company_id={self.company_id})>"


class TeamMember(Base):
    """Team membership model"""
    __tablename__ = "team_members"

    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")  # owner, admin, member
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    team: Mapped[Team] = relationship("Team", back_populates="members")
    user: Mapped[User] = relationship("User", back_populates="teams")

    def __repr__(self) -> str:
        return f"<TeamMember(team_id={self.team_id}, user_id={self.user_id}, role={self.role})>"


class Project(Base):
    """Project model"""
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(7), default="#3B82F6", nullable=False)  # Hex color
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Budget fields (admin-only visibility)
    budget_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)  # USD budget
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # Project deadline

    # Relationships
    team: Mapped[Team] = relationship("Team", back_populates="projects")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    time_entries: Mapped[list["TimeEntry"]] = relationship("TimeEntry", back_populates="project", cascade="all, delete-orphan")
    budget_history: Mapped[list["ProjectBudgetHistory"]] = relationship("ProjectBudgetHistory", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name}, team_id={self.team_id})>"


class Task(Base):
    """Task model"""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="TODO", nullable=False)  # TODO, IN_PROGRESS, DONE
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    project: Mapped[Project] = relationship("Project", back_populates="tasks")
    time_entries: Mapped[list["TimeEntry"]] = relationship("TimeEntry", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, name={self.name}, status={self.status})>"


class TimeEntry(Base):
    """Time entry model"""
    __tablename__ = "time_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("projects.id"), nullable=True)
    task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_running: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Link to work session (NULLABLE for backward compatibility with existing entries)
    work_session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("work_sessions.id"), nullable=True
    )

    # Pause tracking (for breaks/meetings)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    pause_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Long-timer warning email idempotency stamp (migration 024).
    # Set by the hourly long-timer warning job after a successful send;
    # NULL means no warning email has been sent for this entry.
    long_timer_email_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="time_entries")
    project: Mapped[Optional[Project]] = relationship("Project", back_populates="time_entries")
    task: Mapped[Optional[Task]] = relationship("Task", back_populates="time_entries")
    work_session: Mapped[Optional["WorkSession"]] = relationship("WorkSession", back_populates="time_entries")

    def __repr__(self) -> str:
        return f"<TimeEntry(id={self.id}, user_id={self.user_id}, is_running={self.is_running})>"


# ============================================
# WORK SESSION / MICRO-TASK MODELS
# ============================================

class WorkSession(Base):
    """
    Represents a user's work day/session.
    Links multiple TimeEntry records together.
    Tracks global work time, breaks, and meetings.
    """
    __tablename__ = "work_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    company_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("companies.id"), nullable=True, index=True)

    # Session timing
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Calculated totals (updated on session end)
    total_work_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_break_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_meeting_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Status tracking
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    # Values: "active", "break", "meeting", "completed"

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="work_sessions")
    company: Mapped[Optional["Company"]] = relationship("Company")
    time_entries: Mapped[list["TimeEntry"]] = relationship("TimeEntry", back_populates="work_session")
    breaks: Mapped[list["SessionBreak"]] = relationship("SessionBreak", back_populates="work_session", cascade="all, delete-orphan")
    meetings: Mapped[list["SessionMeeting"]] = relationship("SessionMeeting", back_populates="work_session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<WorkSession(id={self.id}, user_id={self.user_id}, status={self.status})>"


class SessionBreak(Base):
    """
    Records break periods within a work session.
    Breaks pause BOTH global and task timers.
    """
    __tablename__ = "session_breaks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    work_session_id: Mapped[int] = mapped_column(Integer, ForeignKey("work_sessions.id"), nullable=False, index=True)

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    break_type: Mapped[str] = mapped_column(String(20), default="short", nullable=False)
    # Values: "short", "lunch", "other"

    # Relationships
    work_session: Mapped["WorkSession"] = relationship("WorkSession", back_populates="breaks")

    def __repr__(self) -> str:
        return f"<SessionBreak(id={self.id}, session_id={self.work_session_id}, type={self.break_type})>"


class SessionMeeting(Base):
    """
    Records meeting periods within a work session.
    Meetings pause ONLY task timer, global timer keeps running.
    Now also creates a time entry for the meeting itself.
    """
    __tablename__ = "session_meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    work_session_id: Mapped[int] = mapped_column(Integer, ForeignKey("work_sessions.id"), nullable=False, index=True)

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    meeting_type: Mapped[str] = mapped_column(String(20), default="internal", nullable=False)
    # Values: "internal", "external", "client"

    # Track paused entry to resume after meeting
    paused_entry_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("time_entries.id"), nullable=True)
    # The time entry created for this meeting
    time_entry_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("time_entries.id"), nullable=True)

    # Relationships
    work_session: Mapped["WorkSession"] = relationship("WorkSession", back_populates="meetings")
    paused_entry: Mapped[Optional["TimeEntry"]] = relationship("TimeEntry", foreign_keys=[paused_entry_id])
    time_entry: Mapped[Optional["TimeEntry"]] = relationship("TimeEntry", foreign_keys=[time_entry_id])

    def __repr__(self) -> str:
        return f"<SessionMeeting(id={self.id}, session_id={self.work_session_id}, title={self.title})>"


# ============================================
# PAYROLL MODELS
# ============================================

class PayRate(Base):
    """Pay rate configuration for users"""
    __tablename__ = "pay_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    rate_type: Mapped[str] = mapped_column(String(20), nullable=False, default=RateType.HOURLY.value)
    base_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    overtime_multiplier: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("1.5"))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="pay_rates", foreign_keys=[user_id])
    creator: Mapped[User] = relationship("User", foreign_keys=[created_by])
    history: Mapped[list["PayRateHistory"]] = relationship("PayRateHistory", back_populates="pay_rate")

    def __repr__(self) -> str:
        return f"<PayRate(id={self.id}, user_id={self.user_id}, rate={self.base_rate}, type={self.rate_type})>"


class PayRateHistory(Base):
    """Audit trail for pay rate changes"""
    __tablename__ = "pay_rate_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pay_rate_id: Mapped[int] = mapped_column(Integer, ForeignKey("pay_rates.id"), nullable=False, index=True)
    previous_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    new_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    previous_overtime_multiplier: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2))
    new_overtime_multiplier: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2))
    changed_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    pay_rate: Mapped[PayRate] = relationship("PayRate", back_populates="history")
    changed_by_user: Mapped[User] = relationship("User")

    def __repr__(self) -> str:
        return f"<PayRateHistory(id={self.id}, pay_rate_id={self.pay_rate_id}, {self.previous_rate} -> {self.new_rate})>"


class PayrollPeriod(Base):
    """Payroll period definition"""
    __tablename__ = "payroll_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False, default=PeriodType.MONTHLY.value)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PeriodStatus.DRAFT.value, index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    # Employee selection criteria (stored as JSON-like string for filtering)
    selected_user_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Comma-separated user IDs, null = all
    rate_type_filter: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Filter by rate type (hourly, monthly, etc.)

    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    approver: Mapped[Optional[User]] = relationship("User")
    entries: Mapped[list["PayrollEntry"]] = relationship("PayrollEntry", back_populates="period", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<PayrollPeriod(id={self.id}, name={self.name}, status={self.status})>"


class PayrollEntry(Base):
    """Individual payroll entry per user per period"""
    __tablename__ = "payroll_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    payroll_period_id: Mapped[int] = mapped_column(Integer, ForeignKey("payroll_periods.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    regular_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0.00"))
    overtime_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0.00"))
    regular_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    overtime_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    adjustments_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=EntryStatus.PENDING.value)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    period: Mapped[PayrollPeriod] = relationship("PayrollPeriod", back_populates="entries")
    user: Mapped[User] = relationship("User", back_populates="payroll_entries")
    adjustments: Mapped[list["PayrollAdjustment"]] = relationship("PayrollAdjustment", back_populates="entry", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<PayrollEntry(id={self.id}, user_id={self.user_id}, net={self.net_amount})>"


class PayrollAdjustment(Base):
    """Adjustments to payroll entries (bonus, deductions, etc.)"""
    __tablename__ = "payroll_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    payroll_entry_id: Mapped[int] = mapped_column(Integer, ForeignKey("payroll_entries.id"), nullable=False, index=True)
    adjustment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)  # Positive or negative
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    entry: Mapped[PayrollEntry] = relationship("PayrollEntry", back_populates="adjustments")
    creator: Mapped[User] = relationship("User")

    def __repr__(self) -> str:
        return f"<PayrollAdjustment(id={self.id}, type={self.adjustment_type}, amount={self.amount})>"


# ============================================
# ACCOUNT REQUESTS MODEL
# ============================================

class AccountRequest(Base):
    """Account request model for user self-service registration"""
    __tablename__ = "account_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Submitted Information
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Request Metadata
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit Trail
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Email Notification Tracking
    email_notification_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    email_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewed_by])

    def __repr__(self) -> str:
        return f"<AccountRequest(id={self.id}, email={self.email}, status={self.status})>"


# ============================================
# AUDIT LOG MODEL
# ============================================

class AuditLog(Base):
    """Audit log model for tracking all system changes"""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True, default=lambda: datetime.now(timezone.utc))
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    old_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, resource_type={self.resource_type})>"


# ============================================
# API KEY MODEL (for AI integrations)
# ============================================

class AIProvider(str, enum.Enum):
    """Supported AI provider enumeration"""
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    OTHER = "other"


class APIKey(Base):
    """
    API Key model for secure storage of AI provider credentials.
    Keys are encrypted at rest using AES-256-GCM.
    SEC-020: Secure API Key Storage
    """
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # gemini, openai, etc.
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)  # AES-256-GCM encrypted
    key_preview: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g., "...xxxx" for display
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Optional friendly name
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Tracking
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Additional metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    creator: Mapped[User] = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<APIKey(id={self.id}, provider={self.provider}, active={self.is_active})>"


# ============================================
# INDEXES
# ============================================

# Existing indexes
Index("ix_time_entries_user_id", TimeEntry.user_id)
Index("ix_time_entries_project_id", TimeEntry.project_id)
Index("ix_time_entries_task_id", TimeEntry.task_id)
Index("ix_time_entries_start_time", TimeEntry.start_time)
Index("ix_time_entries_created_at", TimeEntry.created_at)
Index("ix_users_email", User.email)
Index("ix_projects_team_id", Project.team_id)
Index("ix_tasks_project_id", Task.project_id)

# Payroll indexes
Index("ix_pay_rates_user_effective", PayRate.user_id, PayRate.effective_from)
Index("ix_payroll_periods_dates", PayrollPeriod.start_date, PayrollPeriod.end_date)
Index("ix_payroll_entries_period_user", PayrollEntry.payroll_period_id, PayrollEntry.user_id)

# API Key indexes
Index("ix_api_keys_provider_active", APIKey.provider, APIKey.is_active)


# ============================================
# AI FEATURE TOGGLE MODELS
# ============================================

class AIFeatureSetting(Base):
    """
    Global AI feature settings controlled by admins.
    Each feature can be enabled/disabled globally for all users.
    """
    __tablename__ = "ai_feature_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    feature_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    feature_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    requires_api_key: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    api_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    config: Mapped[Optional[dict]] = mapped_column("config", Text, nullable=True)  # JSON stored as text

    # Tracking
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    updater: Mapped[Optional[User]] = relationship("User", foreign_keys=[updated_by])

    def __repr__(self) -> str:
        return f"<AIFeatureSetting(feature_id={self.feature_id}, enabled={self.is_enabled})>"


class UserAIPreference(Base):
    """
    Per-user AI feature preferences.
    Users can toggle AI features for their own session.
    Admins can override user preferences.
    """
    __tablename__ = "user_ai_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    admin_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    admin_override_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Tracking
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
    admin: Mapped[Optional[User]] = relationship("User", foreign_keys=[admin_override_by])

    __table_args__ = (
        Index("ix_user_ai_preferences_user_feature", "user_id", "feature_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<UserAIPreference(user_id={self.user_id}, feature_id={self.feature_id}, enabled={self.is_enabled})>"


class AIUsageLog(Base):
    """
    AI usage tracking for cost monitoring and analytics.
    Logs every AI API call with tokens used and estimated cost.
    """
    __tablename__ = "ai_usage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    feature_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    api_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    request_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # JSON column for metadata

    # Relationships
    user: Mapped[Optional[User]] = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_ai_usage_log_user_date", "user_id", "request_timestamp"),
        Index("ix_ai_usage_log_feature_date", "feature_id", "request_timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AIUsageLog(id={self.id}, feature_id={self.feature_id}, user_id={self.user_id})>"


# ============================================
# PROJECT BUDGET HISTORY MODEL
# ============================================

class ProjectBudgetHistory(Base):
    """
    Tracks changes to project budget for audit trail.
    Records who changed the budget, when, and what values changed.
    """
    __tablename__ = "project_budget_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    changed_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Budget change tracking
    old_budget_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    new_budget_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    old_deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    new_deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Change metadata
    change_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="budget_history")
    changed_by: Mapped[Optional[User]] = relationship("User", foreign_keys=[changed_by_id])

    __table_args__ = (
        Index("ix_project_budget_history_project_date", "project_id", "changed_at"),
    )

    def __repr__(self) -> str:
        return f"<ProjectBudgetHistory(project_id={self.project_id}, changed_at={self.changed_at})>"


# ============================================
# EMAIL LOG MODEL
# ============================================

class EmailStatus(str, enum.Enum):
    """Email status enumeration"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class EmailLog(Base):
    """
    Tracks all emails sent from the system for delivery monitoring.
    Provides visibility into email delivery status and errors.
    """
    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)

    # Email details
    to_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    email_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # welcome, password_reset, notification, etc.

    # Status tracking
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Extra data
    email_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_email_log_company_date", "company_id", "created_at"),
        Index("ix_email_log_status_date", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<EmailLog(id={self.id}, to={self.to_email}, type={self.email_type}, status={self.status})>"


# ============================================
# IN-APP NOTIFICATION MODEL
# ============================================

class NotificationType(str, enum.Enum):
    """Notification type enumeration"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    TIMER_REMINDER = "timer_reminder"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"
    TEAM_UPDATE = "team_update"
    PAYROLL = "payroll"
    SYSTEM = "system"


class Notification(Base):
    """
    In-app notifications for users.
    Supports real-time delivery via WebSocket and persistent storage.
    """
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)

    # Notification content
    type: Mapped[str] = mapped_column(String(50), default="info", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Link to related entity (optional)
    link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # time_entry, approval, payroll, etc.
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Extra data (for custom notification content)
    notification_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")

    __table_args__ = (
        Index("ix_notification_user_read", "user_id", "is_read"),
        Index("ix_notification_user_created", "user_id", "created_at"),
        Index("ix_notification_company_created", "company_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, user_id={self.user_id}, type={self.type}, read={self.is_read})>"


# ============================================
# BASECAMP INTEGRATION MODELS
# ============================================


class BasecampCredentials(Base):
    """Per-company Basecamp OAuth credentials.

    Tokens are encrypted at rest with ``API_KEY_ENCRYPTION_KEY``
    (AES-256-GCM via ``app.services.encryption_service``). Exactly one
    row per company (UNIQUE on ``company_id``).
    """
    __tablename__ = "basecamp_credentials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    account_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    connected_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # v2: optional target team. NULL = legacy behavior (lowest-id team).
    target_team_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
    )
    # v2: opt-in 4-hourly auto-sync. Defaults to False.
    auto_sync_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<BasecampCredentials(id={self.id}, company_id={self.company_id}, "
            f"account_id={self.account_id})>"
        )


class BasecampProjectMapping(Base):
    """Maps a Basecamp project to an internal TimeTracker ``Project`` row.

    The triple (``company_id``, ``basecamp_account_id``,
    ``basecamp_project_id``) is UNIQUE so the sync routine is
    idempotent.
    """
    __tablename__ = "basecamp_project_mappings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    basecamp_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    basecamp_project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    internal_project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "basecamp_account_id",
            "basecamp_project_id",
            name="uq_basecamp_project_mapping_external",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<BasecampProjectMapping(id={self.id}, company_id={self.company_id}, "
            f"basecamp_project_id={self.basecamp_project_id}, "
            f"internal_project_id={self.internal_project_id})>"
        )


class BasecampTaskMapping(Base):
    """Maps a Basecamp to-do to an internal TimeTracker ``Task`` row.

    The triple (``company_id``, ``basecamp_account_id``,
    ``basecamp_todo_id``) is UNIQUE so the to-do sync routine is
    idempotent and multi-tenant safe: the same Basecamp to-do id
    observed by two different connected accounts on two different
    TimeTracker companies will not collide.

    ``basecamp_todolist_id`` is preserved (not part of the UNIQUE) so
    v3.1 can surface to-do list grouping without a schema migration.
    """
    __tablename__ = "basecamp_task_mappings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    basecamp_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    basecamp_project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    basecamp_todolist_id: Mapped[str] = mapped_column(String(64), nullable=False)
    basecamp_todo_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "basecamp_account_id",
            "basecamp_todo_id",
            name="uq_basecamp_task_mapping_external",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<BasecampTaskMapping(id={self.id}, company_id={self.company_id}, "
            f"basecamp_todo_id={self.basecamp_todo_id}, "
            f"task_id={self.task_id})>"
        )

