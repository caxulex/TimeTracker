# Changelog

All notable changes to TimeTracker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Enhanced health endpoint with DB/Redis connectivity checks (`/api/health`)
- Version info endpoint (`/api/version`)
- User Quick Start Guide documentation
- Password strength indicator with real-time feedback
- Request ID tracking for debugging
- CSV export for time entries
- Keyboard shortcuts for common actions
- Dark mode support
- Custom 404 page

### Changed
- Improved error handling for 403/401 responses
- Enhanced rate limiting with proper headers

### Fixed
- WebSocket real-time updates for "Who's Working Now" widget
- Running timer data in Weekly Activity chart
- SuperAdmin user management email validation
- TypeError in getInitials for undefined names
- Rate limit (429) handling with debouncing
- Login page API calls when not authenticated

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
