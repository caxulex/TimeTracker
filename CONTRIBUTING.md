# Contributing to TimeTracker

Thank you for your interest in contributing to TimeTracker! This document provides guidelines and instructions for contributing.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Coding Standards](#coding-standards)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)

---

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help maintain a positive community

---

## Getting Started

### Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.11+
- **Docker** and Docker Compose
- **Git**

### Forking the Repository

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/TimeTracker.git
   cd TimeTracker
   ```
3. Add upstream remote:
   ```bash
   git remote add upstream https://github.com/ORIGINAL_OWNER/TimeTracker.git
   ```

---

## Development Setup

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env with your local settings
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file (if needed)
cp .env.example .env.local
```

### Start Development Services

```bash
# Start database and Redis
docker-compose up -d postgres redis

# Run backend
cd backend
uvicorn app.main:app --reload --port 8000

# Run frontend (in another terminal)
cd frontend
npm run dev
```

---

## Project Structure

```
TimeTracker/
├── backend/               # FastAPI backend
│   ├── app/
│   │   ├── main.py       # Application entry
│   │   ├── config.py     # Settings
│   │   ├── database.py   # Database setup
│   │   ├── routers/      # API endpoints
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   └── middleware/   # Custom middleware
│   ├── alembic/          # Database migrations
│   └── tests/            # Backend tests
│
├── frontend/             # React frontend
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── pages/        # Page components
│   │   ├── stores/       # Zustand stores
│   │   ├── api/          # API client
│   │   ├── hooks/        # Custom hooks
│   │   └── utils/        # Utilities
│   └── e2e/              # Playwright tests
│
└── docs/                 # Documentation
```

---

## Coding Standards

### Backend (Python)

- Follow **PEP 8** style guide
- Use **type hints** for all functions
- Use **async/await** for database operations
- Maximum line length: 100 characters

```python
# Good
async def get_user_by_id(user_id: int) -> User | None:
    """Retrieve a user by their ID."""
    async with get_db() as db:
        return await db.get(User, user_id)

# Bad
def get_user(id):
    # No type hints, unclear naming
    return db.query(User).get(id)
```

### Frontend (TypeScript)

- Use **TypeScript** for all new code
- Use **functional components** with hooks
- Use **Zustand** for global state
- Use **React Query** for server state

```typescript
// Good
interface UserProps {
  userId: number;
  onSelect: (user: User) => void;
}

export function UserCard({ userId, onSelect }: UserProps) {
  const { data: user } = useQuery(['user', userId], () => fetchUser(userId));
  // ...
}

// Bad
export function UserCard(props: any) {
  const [user, setUser] = useState();
  // ...
}
```

### Git Commit Messages

Follow conventional commits:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no code change)
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance

Examples:
```
feat(auth): add password strength indicator
fix(timer): prevent duplicate API calls on page load
docs: update CONTRIBUTING guide
```

---

## Making Changes

### Creating a Branch

```bash
# Sync with upstream
git fetch upstream
git checkout master
git merge upstream/master

# Create feature branch
git checkout -b feature/your-feature-name
```

### Branch Naming

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation
- `refactor/` - Code improvements

---

## Testing

### Backend Tests

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py
```

### Frontend Tests

```bash
cd frontend

# Run unit tests
npm run test

# Run with coverage
npm run test:coverage

# Run E2E tests
npm run test:e2e
```

### Before Submitting

Ensure all tests pass:

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm run test && npm run lint
```

---

## Submitting Changes

### Pull Request Process

1. **Update your branch**:
   ```bash
   git fetch upstream
   git rebase upstream/master
   ```

2. **Push your branch**:
   ```bash
   git push origin feature/your-feature-name
   ```

3. **Create Pull Request**:
   - Go to GitHub and create a PR
   - Fill in the PR template
   - Link any related issues

### PR Checklist

- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated (if needed)
- [ ] No console.log or debug statements
- [ ] Commit messages follow conventions

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactoring

## Testing
Describe how you tested the changes

## Related Issues
Fixes #123
```

---

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Tailwind CSS](https://tailwindcss.com/docs)

---

## Questions?

If you have questions, please:
1. Check existing issues and documentation
2. Open a new issue with the "question" label

Thank you for contributing! 🎉
