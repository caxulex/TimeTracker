# ============================================
# TIME TRACKER - TEST DATA SEEDER
# Phase 7: Demo data for testing and demos
# ============================================
"""
Test Data Seeder for TimeTracker
Creates realistic demo data for testing and demonstrations.

Usage:
    cd backend
    python -m scripts.seed_demo_data
    
Or with docker:
    docker compose exec backend python -m scripts.seed_demo_data
"""

import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models import User, Team, TeamMember, Project, Task, TimeEntry
from app.services.auth_service import AuthService

# Configuration
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5434/time_tracker"

# Demo data configuration
DEMO_USERS = [
    {"email": "demo@example.com", "name": "Demo User", "password": "DemoPass123!", "role": "regular_user"},
    {"email": "alice@example.com", "name": "Alice Johnson", "password": "AlicePass123!", "role": "team_lead"},
    {"email": "bob@example.com", "name": "Bob Smith", "password": "BobPass123!", "role": "regular_user"},
    {"email": "carol@example.com", "name": "Carol Williams", "password": "CarolPass123!", "role": "regular_user"},
    {"email": "dave@example.com", "name": "Dave Brown", "password": "DavePass123!", "role": "regular_user"},
    {"email": "admin@example.com", "name": "Admin User", "password": "AdminPass123!", "role": "admin"},
]

DEMO_TEAMS = [
    {"name": "Development Team", "description": "Software development team"},
    {"name": "Design Team", "description": "UI/UX design team"},
    {"name": "Marketing Team", "description": "Marketing and growth team"},
]

DEMO_PROJECTS = [
    {"name": "Website Redesign", "description": "Complete website overhaul", "color": "#3B82F6"},
    {"name": "Mobile App v2", "description": "iOS and Android app development", "color": "#10B981"},
    {"name": "API Integration", "description": "Third-party API integrations", "color": "#F59E0B"},
    {"name": "Marketing Campaign Q1", "description": "Q1 2026 marketing campaign", "color": "#EF4444"},
    {"name": "Internal Tools", "description": "Internal productivity tools", "color": "#8B5CF6"},
]

DEMO_TASKS = [
    {"name": "Design homepage mockups", "status": "completed", "priority": "high"},
    {"name": "Implement user authentication", "status": "completed", "priority": "high"},
    {"name": "Create API documentation", "status": "in_progress", "priority": "medium"},
    {"name": "Setup CI/CD pipeline", "status": "completed", "priority": "medium"},
    {"name": "Write unit tests", "status": "in_progress", "priority": "medium"},
    {"name": "Code review - feature branch", "status": "pending", "priority": "low"},
    {"name": "Database optimization", "status": "in_progress", "priority": "high"},
    {"name": "User feedback analysis", "status": "pending", "priority": "medium"},
    {"name": "Performance benchmarking", "status": "pending", "priority": "low"},
    {"name": "Security audit", "status": "in_progress", "priority": "high"},
]

DEMO_DESCRIPTIONS = [
    "Working on feature implementation",
    "Bug fixing and code cleanup",
    "Code review and feedback",
    "Team standup meeting",
    "Client call - project status",
    "Documentation updates",
    "Testing and QA",
    "Design review session",
    "Sprint planning meeting",
    "Technical research",
    "Deployment and monitoring",
    "Performance optimization",
    "Database migrations",
    "API endpoint development",
    "UI/UX improvements",
]


async def clear_demo_data(session: AsyncSession):
    """Clear existing demo data (optional, for fresh seeding)."""
    print("Clearing existing demo data...")
    
    # Delete in order due to foreign keys (using SQLAlchemy 2.0 delete syntax)
    await session.execute(delete(TimeEntry))
    await session.execute(delete(Task))
    await session.execute(delete(Project))
    await session.execute(delete(TeamMember))
    await session.execute(delete(Team))
    
    # Delete demo users (keep non-demo users)
    demo_emails = [u["email"] for u in DEMO_USERS]
    for email in demo_emails:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            await session.delete(user)
    
    await session.commit()
    print("Demo data cleared.")


async def create_demo_users(session: AsyncSession) -> List[User]:
    """Create demo users."""
    print("Creating demo users...")
    users = []
    
    for user_data in DEMO_USERS:
        # Check if user already exists
        result = await session.execute(select(User).where(User.email == user_data["email"]))
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"  User {user_data['email']} already exists, skipping...")
            users.append(existing)
            continue
        
        user = User(
            email=user_data["email"],
            name=user_data["name"],
            password_hash=AuthService.hash_password(user_data["password"]),
            role=user_data["role"],
            is_active=True,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        users.append(user)
        print(f"  Created user: {user.name} ({user.email})")
    
    await session.commit()
    return users


async def create_demo_teams(session: AsyncSession, users: List[User]) -> List[Team]:
    """Create demo teams."""
    print("Creating demo teams...")
    teams = []
    
    for i, team_data in enumerate(DEMO_TEAMS):
        # Assign different owners
        owner = users[i % len(users)]
        
        team = Team(
            name=team_data["name"],
            description=team_data.get("description"),
            owner_id=owner.id,
        )
        session.add(team)
        await session.flush()
        await session.refresh(team)
        teams.append(team)
        print(f"  Created team: {team.name}")
        
        # Add owner as team member
        owner_member = TeamMember(
            team_id=team.id,
            user_id=owner.id,
            role="owner",
        )
        session.add(owner_member)
        
        # Add other users as members
        for j, user in enumerate(users):
            if user.id != owner.id:
                member = TeamMember(
                    team_id=team.id,
                    user_id=user.id,
                    role="member" if j % 2 == 0 else "viewer",
                )
                session.add(member)
    
    await session.commit()
    return teams


async def create_demo_projects(session: AsyncSession, teams: List[Team]) -> List[Project]:
    """Create demo projects."""
    print("Creating demo projects...")
    projects = []
    
    for i, proj_data in enumerate(DEMO_PROJECTS):
        team = teams[i % len(teams)]
        
        project = Project(
            name=proj_data["name"],
            description=proj_data.get("description"),
            team_id=team.id,
            color=proj_data.get("color", "#3B82F6"),
        )
        session.add(project)
        await session.flush()
        await session.refresh(project)
        projects.append(project)
        print(f"  Created project: {project.name}")
    
    await session.commit()
    return projects


async def create_demo_tasks(session: AsyncSession, projects: List[Project], users: List[User]) -> List[Task]:
    """Create demo tasks."""
    print("Creating demo tasks...")
    tasks = []
    
    for i, task_data in enumerate(DEMO_TASKS):
        project = projects[i % len(projects)]
        assignee = users[i % len(users)]
        
        task = Task(
            name=task_data["name"],
            description=f"Task description for: {task_data['name']}",
            project_id=project.id,
            assigned_to_id=assignee.id,
            status=task_data.get("status", "pending"),
            priority=task_data.get("priority", "medium"),
        )
        session.add(task)
        await session.flush()
        await session.refresh(task)
        tasks.append(task)
        print(f"  Created task: {task.name}")
    
    await session.commit()
    return tasks


async def create_demo_time_entries(
    session: AsyncSession, 
    users: List[User], 
    projects: List[Project],
    tasks: List[Task]
) -> List[TimeEntry]:
    """Create demo time entries for the past 30 days."""
    print("Creating demo time entries...")
    entries = []
    now = datetime.now(timezone.utc)
    
    for user in users:
        # Create 5-15 entries per user over past 30 days
        num_entries = random.randint(5, 15)
        
        for _ in range(num_entries):
            # Random day in past 30 days
            days_ago = random.randint(0, 30)
            # Random hour of workday (8am - 6pm)
            hour = random.randint(8, 17)
            minute = random.choice([0, 15, 30, 45])
            
            start_time = now - timedelta(days=days_ago)
            start_time = start_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Duration between 30 min and 4 hours
            duration_minutes = random.choice([30, 45, 60, 90, 120, 180, 240])
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            project = random.choice(projects)
            task = random.choice([t for t in tasks if t.project_id == project.id] or tasks)
            description = random.choice(DEMO_DESCRIPTIONS)
            
            entry = TimeEntry(
                user_id=user.id,
                project_id=project.id,
                task_id=task.id if random.random() > 0.3 else None,
                description=description,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration_minutes * 60,
                is_running=False,
            )
            session.add(entry)
            entries.append(entry)
    
    await session.commit()
    print(f"  Created {len(entries)} time entries")
    return entries


async def seed_demo_data(clear_first: bool = False):
    """Main seeding function."""
    print("=" * 50)
    print("TIME TRACKER - Demo Data Seeder")
    print("=" * 50)
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            if clear_first:
                await clear_demo_data(session)
            
            users = await create_demo_users(session)
            teams = await create_demo_teams(session, users)
            projects = await create_demo_projects(session, teams)
            tasks = await create_demo_tasks(session, projects, users)
            entries = await create_demo_time_entries(session, users, projects, tasks)
            
            print("\n" + "=" * 50)
            print("Demo data seeding completed!")
            print("=" * 50)
            print(f"\nCreated:")
            print(f"  - {len(users)} users")
            print(f"  - {len(teams)} teams")
            print(f"  - {len(projects)} projects")
            print(f"  - {len(tasks)} tasks")
            print(f"  - {len(entries)} time entries")
            print("\nDemo login credentials:")
            print("  Email: demo@example.com")
            print("  Password: DemoPass123!")
            print("\nAdmin login:")
            print("  Email: admin@example.com")
            print("  Password: AdminPass123!")
            
        except Exception as e:
            print(f"\nError during seeding: {e}")
            await session.rollback()
            raise
    
    await engine.dispose()


if __name__ == "__main__":
    import sys
    clear_first = "--clear" in sys.argv
    asyncio.run(seed_demo_data(clear_first=clear_first))
