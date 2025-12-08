"""
Database seed script for development
Run with: python -m app.seed
"""

import bcrypt
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, User, Team, TeamMember, Project, Task, TimeEntry
from app.config import settings

# Use sync URL for seeding
SYNC_DATABASE_URL = settings.DATABASE_URL.replace("+asyncpg", "+psycopg")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def seed_database():
    """Seed the database with initial data"""
    engine = create_engine(SYNC_DATABASE_URL)
    
    with Session(engine) as session:
        # Check if data already exists
        if session.query(User).count() > 0:
            print("Database already seeded. Skipping...")
            return
        
        print("Seeding database...")
        
        # Create users
        admin = User(
            email="admin@timetracker.com",
            password_hash=hash_password("admin123"),
            name="Admin User",
            role="super_admin",
            is_active=True,
        )
        
        user1 = User(
            email="john@example.com",
            password_hash=hash_password("password123"),
            name="John Doe",
            role="regular_user",
            is_active=True,
        )
        
        user2 = User(
            email="jane@example.com",
            password_hash=hash_password("password123"),
            name="Jane Smith",
            role="regular_user",
            is_active=True,
        )
        
        user3 = User(
            email="bob@example.com",
            password_hash=hash_password("password123"),
            name="Bob Wilson",
            role="regular_user",
            is_active=True,
        )
        
        session.add_all([admin, user1, user2, user3])
        session.flush()
        
        print(f"Created 4 users")
        
        # Create teams
        team1 = Team(
            name="Development Team",
            owner_id=admin.id,
        )
        
        team2 = Team(
            name="Design Team",
            owner_id=user1.id,
        )
        
        session.add_all([team1, team2])
        session.flush()
        
        print(f"Created 2 teams")
        
        # Create team members
        members = [
            TeamMember(team_id=team1.id, user_id=admin.id),
            TeamMember(team_id=team1.id, user_id=user1.id),
            TeamMember(team_id=team1.id, user_id=user2.id),
            TeamMember(team_id=team2.id, user_id=user1.id),
            TeamMember(team_id=team2.id, user_id=user3.id),
        ]
        session.add_all(members)
        session.flush()
        
        print(f"Created {len(members)} team memberships")
        
        # Create projects
        project1 = Project(
            team_id=team1.id,
            name="Time Tracker MVP",
            description="Building the time tracker application",
            color="#3B82F6",
        )
        
        project2 = Project(
            team_id=team1.id,
            name="API Documentation",
            description="Creating comprehensive API docs",
            color="#10B981",
        )
        
        project3 = Project(
            team_id=team2.id,
            name="UI/UX Redesign",
            description="Redesigning the user interface",
            color="#F59E0B",
        )
        
        session.add_all([project1, project2, project3])
        session.flush()
        
        print(f"Created 3 projects")
        
        # Create tasks
        tasks = [
            Task(project_id=project1.id, name="Setup project structure", status="DONE"),
            Task(project_id=project1.id, name="Create database models", status="DONE"),
            Task(project_id=project1.id, name="Implement auth API", status="IN_PROGRESS"),
            Task(project_id=project1.id, name="Build timer component", status="TODO"),
            Task(project_id=project1.id, name="Create reporting dashboard", status="TODO"),
            Task(project_id=project2.id, name="Document auth endpoints", status="IN_PROGRESS"),
            Task(project_id=project2.id, name="Document project APIs", status="TODO"),
            Task(project_id=project2.id, name="Create Postman collection", status="TODO"),
            Task(project_id=project3.id, name="Create wireframes", status="DONE"),
            Task(project_id=project3.id, name="Design component library", status="IN_PROGRESS"),
            Task(project_id=project3.id, name="Prototype dashboard", status="TODO"),
        ]
        
        session.add_all(tasks)
        session.flush()
        
        print(f"Created {len(tasks)} tasks")
        
        # Create time entries
        now = datetime.now(timezone.utc)
        time_entries = []
        
        for day_offset in range(7):
            date = now - timedelta(days=day_offset)
            start = date.replace(hour=9, minute=0, second=0, microsecond=0)
            end = date.replace(hour=12, minute=30, second=0, microsecond=0)
            duration = int((end - start).total_seconds())
            time_entries.append(TimeEntry(
                user_id=user1.id,
                project_id=project1.id,
                task_id=tasks[2].id,
                start_time=start,
                end_time=end,
                duration_seconds=duration,
                description="Working on authentication implementation",
                is_running=False,
            ))
            
            start = date.replace(hour=14, minute=0, second=0, microsecond=0)
            end = date.replace(hour=17, minute=0, second=0, microsecond=0)
            duration = int((end - start).total_seconds())
            time_entries.append(TimeEntry(
                user_id=user1.id,
                project_id=project1.id,
                task_id=tasks[3].id,
                start_time=start,
                end_time=end,
                duration_seconds=duration,
                description="Building timer UI component",
                is_running=False,
            ))
        
        for day_offset in range(5):
            date = now - timedelta(days=day_offset)
            start = date.replace(hour=10, minute=0, second=0, microsecond=0)
            end = date.replace(hour=15, minute=0, second=0, microsecond=0)
            duration = int((end - start).total_seconds())
            time_entries.append(TimeEntry(
                user_id=user2.id,
                project_id=project2.id,
                task_id=tasks[5].id,
                start_time=start,
                end_time=end,
                duration_seconds=duration,
                description="Writing API documentation",
                is_running=False,
            ))
        
        running_entry = TimeEntry(
            user_id=user1.id,
            project_id=project1.id,
            task_id=tasks[2].id,
            start_time=now - timedelta(hours=1),
            end_time=None,
            duration_seconds=None,
            description="Currently working on auth",
            is_running=True,
        )
        time_entries.append(running_entry)
        
        session.add_all(time_entries)
        session.commit()
        
        print(f"Created {len(time_entries)} time entries")
        print("\n✅ Database seeded successfully!")
        print("\nTest accounts:")
        print("  Admin: admin@timetracker.com / admin123")
        print("  User:  john@example.com / password123")
        print("  User:  jane@example.com / password123")
        print("  User:  bob@example.com / password123")


if __name__ == "__main__":
    seed_database()
