# Changelog

All notable changes to TimeTracker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — Phase 9B Final Polish (2026-02-12)

### Added
- **Migration 020** — Multi-tenant and query-pattern performance indexes
  - `ix_users_company_email` — multi-tenant login lookups
  - `ix_users_company_active` — admin user listing filters
  - `ix_teams_company` — team listing per tenant
  - `ix_time_entries_running` — partial index for running timer polls
  - `ix_tasks_project_status` — task board filtering
  - `ix_payroll_periods_date_range` — payroll date range queries
  - `ix_time_entries_user_running` — user timer queries
  - `ix_work_sessions_user_status` — active session lookups
- **Load test script** (`locustfile_phase9b.py`) — 4-scenario test with 115 concurrent users
- **Load test results template** (`LOAD_TEST_RESULTS.md`)
- **Phase 9 completion assessment** (`ASSESSMENT_PHASE9_COMPLETE.md`)

### Changed
- Updated `README.md` with i18n setup, environment variable table, and load test instructions
- Updated `CHANGELOG.md` with complete Phase 1–9 history

---

## Phase 9A — Internationalization (i18n) (2026-02-11)

### Added
- `react-i18next` and `i18next` integration
- `frontend/src/i18n/config.ts` — i18next initialization with bundled resources
- `frontend/src/i18n/locales/en/translation.json` — 200+ English translation keys across 14 namespaces
- i18n string extraction for core pages: LoginPage, DashboardPage, TimePage
- i18n string extraction for: NotFoundPage, Sidebar, ConnectionStatusIndicator
- Translation keys pre-defined for: StaffPage, ProjectsPage, TeamsPage, TasksPage, SettingsPage, AdminPage
- Common namespace for shared strings (`common.save`, `common.cancel`, etc.)
- i18n completeness tests (`i18n.test.ts`)
- `docs/I18N_GUIDE.md` — developer guide for adding languages

---

## Phase 8 — Security Hardening & Documentation (2026-02-10)

### Added
- Sentry integration (frontend + backend) for error tracking
- Password strength validation (12+ chars, mixed case, numbers, symbols)
- Rate limiting on login and sensitive endpoints
- CORS origin whitelist hardening
- CSP headers
- API key encryption at rest (Fernet / AES-256-GCM)
- Audit logging with severity levels
- AI features: NLP time entry, task estimation, productivity insights
- AI feature toggles per company
- AI usage logging and cost tracking

---

## Phase 7 — Testing (2026-02-09)

### Added
- 154+ backend tests (pytest)
- 137+ frontend unit tests (Vitest)
- 50+ E2E tests (Playwright)
- CI/CD pipeline (GitHub Actions): Lint → Test → Build → Deploy
- Test coverage reporting

---

## Phase 6 — Multi-Tenancy (2026-02-08)

### Added
- Company model with data isolation
- White-label branding (logo, colors, tagline, custom CSS)
- Subdomain routing for company-specific login
- Per-company settings and AI feature toggles
- Company-scoped queries across all endpoints

---

## Phases 2–5 — Staff, Payroll, Security & API Keys

### Added
- Staff management wizard with contact/employment details
- Pay rate configuration (hourly, daily, monthly, project-based)
- Payroll period management (weekly, bi-weekly, monthly, semi-monthly)
- Payroll processing and approval workflow
- Payroll reports and export
- Session management and IP-based security
- Account request self-service registration
- Email notifications (invitations, password reset, approvals)
- Micro-task management (work sessions, breaks, meetings)

---

## [1.0.0] - 2025-12-29

### Added
- **Core Features**
  - Time tracking with start/stop timers
  - Manual time entry creation
  - Project and task management
  - Team management with role-based access
  - Payroll period tracking
  
- **User Management**
  - JWT authentication with refresh tokens
  - Role-based access control (Employee, Manager, Admin, Super Admin)
  - Account request workflow for new users
  - Password security with bcrypt hashing

- **Reporting**
  - Personal time reports
  - Team reports for managers
  - Admin reports with organization-wide data
  - Real-time dashboard widgets
  - Weekly activity charts

- **Real-time Features**
  - WebSocket support for live updates
  - "Who's Working Now" widget
  - Active timers display

- **Security**
  - Rate limiting (60 req/min general, 5 req/min auth)
  - CORS protection
  - Input validation
  - SQL injection prevention
  - XSS protection

- **Infrastructure**
  - Docker containerization
  - PostgreSQL database
  - Redis caching
  - Caddy reverse proxy with auto-SSL
  - GitHub Actions CI/CD
  - Watchtower auto-updates

### Security
- Secure password hashing (bcrypt, 12 rounds)
- JWT token encryption
- Rate limiting on sensitive endpoints
- Environment-based configuration

---

## Version History Summary

| Version | Date | Highlights |
|---------|------|------------|
| 1.0.0 | 2025-12-29 | Initial production release |

---

## Upgrade Notes

### Upgrading to 1.0.0
This is the initial release. No upgrade steps required.

### Future Upgrades
1. Always backup your database before upgrading
2. Review the changelog for breaking changes
3. Run database migrations: `alembic upgrade head`
4. Restart all containers: `docker-compose restart`
