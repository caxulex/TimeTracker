#!/usr/bin/env python3
"""
Migration Script: Assign NULL company_id data to default company

This script fixes the multi-tenancy issue where original data was created
without company_id (NULL). It:
1. Creates a "TimeTracker" company if it doesn't exist
2. Updates all users with NULL company_id to belong to this company
3. Updates all teams with NULL company_id to belong to this company

Usage:
    cd backend
    python -m scripts.migrate_null_company
    
    Or from project root (Docker):
    docker compose exec backend python -m scripts.migrate_null_company

IMPORTANT: Run this in production to fix the "No data" issue in AI panels.
"""

import asyncio
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta


async def migrate_null_company_data():
    """Migrate NULL company_id data to a default company"""
    from sqlalchemy import select, update, func
    from app.database import async_session
    from app.models import User, Company, WhiteLabelConfig, Team, TeamMember, PayrollPeriod
    
    print("=" * 70)
    print("NULL Company Migration Script")
    print("=" * 70)
    print("\nThis script assigns all NULL company_id data to a default company.")
    print("This is required for multi-tenancy strict isolation to work properly.\n")
    
    async with async_session() as db:  # type: ignore[attr-defined]
        try:
            # Step 1: Check if default company already exists
            print("Step 1: Checking for existing 'TimeTracker' company...")
            
            result = await db.execute(
                select(Company).where(Company.slug == "timetracker-default")
            )
            default_company = result.scalar_one_or_none()
            
            if default_company:
                print(f"   ✓ Default company exists (ID: {default_company.id})")
            else:
                # Create default TimeTracker company
                print("   Creating default 'TimeTracker' company...")
                
                default_company = Company(
                    name="TimeTracker",
                    slug="timetracker-default",
                    email="admin@timetracker.com",
                    phone=None,
                    subscription_tier="enterprise",  # Main platform gets enterprise
                    status="active",
                    trial_ends_at=None,  # No trial for main company
                    subscription_ends_at=None,
                    max_users=1000,
                    max_projects=10000,
                    timezone="UTC",
                )
                db.add(default_company)
                await db.flush()  # Get ID
                
                print(f"   ✓ Default company created (ID: {default_company.id})")
                
                # Create white-label config for default company
                branding = WhiteLabelConfig(
                    company_id=default_company.id,
                    app_name="TimeTracker",
                    company_name="TimeTracker",
                    tagline="Track Your Time Efficiently",
                    subdomain="app",
                    primary_color="#3B82F6",      # Blue-500
                    secondary_color="#1D4ED8",    # Blue-700
                    accent_color="#10B981",       # Emerald-500
                    support_email="admin@timetracker.com",
                    show_powered_by=False,
                )
                db.add(branding)
                print(f"   ✓ White-label config created")
            
            company_id = default_company.id
            
            # Step 2: Update users with NULL company_id
            print("\nStep 2: Migrating users with NULL company_id...")
            
            result = await db.execute(
                select(func.count(User.id)).where(User.company_id.is_(None))
            )
            null_user_count = result.scalar() or 0
            
            if null_user_count > 0:
                await db.execute(
                    update(User)
                    .where(User.company_id.is_(None))
                    .values(company_id=company_id)
                )
                print(f"   ✓ Updated {null_user_count} users to company_id={company_id}")
            else:
                print("   ✓ No users with NULL company_id found")
            
            # Step 3: Update teams with NULL company_id
            print("\nStep 3: Migrating teams with NULL company_id...")
            
            result = await db.execute(
                select(func.count(Team.id)).where(Team.company_id.is_(None))
            )
            null_team_count = result.scalar() or 0
            
            if null_team_count > 0:
                await db.execute(
                    update(Team)
                    .where(Team.company_id.is_(None))
                    .values(company_id=company_id)
                )
                print(f"   ✓ Updated {null_team_count} teams to company_id={company_id}")
            else:
                print("   ✓ No teams with NULL company_id found")
            
            # Step 4: Update payroll periods with NULL company_id (if applicable)
            print("\nStep 4: Migrating payroll periods with NULL company_id...")
            
            try:
                result = await db.execute(
                    select(func.count(PayrollPeriod.id)).where(PayrollPeriod.company_id.is_(None))
                )
                null_payroll_count = result.scalar() or 0
                
                if null_payroll_count > 0:
                    await db.execute(
                        update(PayrollPeriod)
                        .where(PayrollPeriod.company_id.is_(None))
                        .values(company_id=company_id)
                    )
                    print(f"   ✓ Updated {null_payroll_count} payroll periods to company_id={company_id}")
                else:
                    print("   ✓ No payroll periods with NULL company_id found")
            except Exception as e:
                print(f"   ⚠ PayrollPeriod migration skipped: {str(e)[:50]}")
            
            # Commit all changes
            await db.commit()
            
            # Step 5: Verify migration
            print("\n" + "=" * 70)
            print("Migration Complete!")
            print("=" * 70)
            
            # Get final counts
            result = await db.execute(
                select(func.count(User.id)).where(User.company_id == company_id)
            )
            user_count = result.scalar() or 0
            
            result = await db.execute(
                select(func.count(Team.id)).where(Team.company_id == company_id)
            )
            team_count = result.scalar() or 0
            
            print(f"\n📊 Default Company '{default_company.name}' Statistics:")
            print(f"   • Company ID: {company_id}")
            print(f"   • Total Users: {user_count}")
            print(f"   • Total Teams: {team_count}")
            
            # List admin users
            result = await db.execute(
                select(User).where(
                    User.company_id == company_id,
                    User.role.in_(["super_admin", "admin", "company_admin"])
                )
            )
            admins = result.scalars().all()
            
            print(f"\n👤 Admin Users in Default Company:")
            for admin in admins:
                print(f"   • {admin.email} ({admin.role})")
            
            print("\n✅ AI panels should now work correctly!")
            print("   Please refresh the browser and test Cash Flow, Project Budget, etc.")
            
            return default_company
            
        except Exception as e:
            await db.rollback()
            print(f"\n❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(migrate_null_company_data())
