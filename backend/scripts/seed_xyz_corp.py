#!/usr/bin/env python3
"""
XYZ Corp Seed Script
Creates a test company with white-label configuration for testing multi-tenancy.

Usage:
    cd backend
    python -m scripts.seed_xyz_corp
    
    Or from project root:
    docker compose exec backend python -m scripts.seed_xyz_corp
"""

import asyncio
import sys
import os

# ============================================
# PRODUCTION SAFETY GUARD
# ============================================
_environment = os.environ.get("ENVIRONMENT", "").lower()
if _environment == "production":
    print("=" * 60)
    print("ERROR: Seed scripts must NOT be run in production!")
    print(f"  ENVIRONMENT={os.environ.get('ENVIRONMENT')}")
    print("  This script creates users with known passwords and")
    print("  test data that is not suitable for production use.")
    print("=" * 60)
    sys.exit(1)

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta


async def seed_xyz_corp():
    """Seed XYZ Corp company with white-label branding"""
    from sqlalchemy import select
    from app.database import async_session
    from app.models import User, Company, WhiteLabelConfig, Team, TeamMember
    from app.services.auth_service import AuthService
    
    print("=" * 60)
    print("XYZ Corp Seed Script")
    print("=" * 60)
    
    # Note: async_session is properly typed as async_sessionmaker in database.py
    # Pylance may show false positive errors due to sessionmaker type inference
    async with async_session() as db:  # type: ignore[attr-defined]
        try:
            # Check if XYZ Corp already exists
            result = await db.execute(
                select(Company).where(Company.slug == "xyz-corp")
            )
            existing_company = result.scalar_one_or_none()
            
            if existing_company:
                print(f"⚠️  XYZ Corp already exists (ID: {existing_company.id})")
                
                # Get existing admin user
                result = await db.execute(
                    select(User).where(User.email == "shaeadam@gmail.com")
                )
                admin = result.scalar_one_or_none()
                
                # Get existing branding
                result = await db.execute(
                    select(WhiteLabelConfig).where(
                        WhiteLabelConfig.company_id == existing_company.id
                    )
                )
                branding = result.scalar_one_or_none()
                
                print("\n📊 Existing Configuration:")
                print(f"   Company ID: {existing_company.id}")
                print(f"   Company Name: {existing_company.name}")
                print(f"   Slug: {existing_company.slug}")
                print(f"   Status: {existing_company.status}")
                print(f"   Tier: {existing_company.subscription_tier}")
                if admin:
                    print(f"   Admin Email: {admin.email}")
                if branding:
                    print(f"   App Name: {branding.app_name}")
                    print(f"   Primary Color: {branding.primary_color}")
                
                print("\n✅ To reset, delete the company manually first.")
                return existing_company
            
            # Create XYZ Corp company
            print("\n📦 Creating XYZ Corp company...")
            
            company = Company(
                name="XYZ Corp",
                slug="xyz-corp",
                email="shaeadam@gmail.com",
                phone="+1-555-XYZ-CORP",
                subscription_tier="standard",  # Paid-tier test fixture
                status="active",
                trial_ends_at=datetime.now(timezone.utc) + timedelta(days=365),  # Extended trial
                max_users=100,
                max_projects=500,
                timezone="America/New_York",
            )
            db.add(company)
            await db.flush()  # Get company ID
            
            print(f"   ✓ Company created (ID: {company.id})")
            
            # Create white-label branding configuration
            print("\n🎨 Creating white-label branding...")
            
            branding = WhiteLabelConfig(
                company_id=company.id,
                app_name="XYZ Time",
                company_name="XYZ Corp",
                tagline="Track Time Like a Pro",
                subdomain="xyz-corp",
                # Custom domain would be: custom_domain="time.xyzcorp.com",
                logo_url=None,  # Can be set later via API
                favicon_url=None,
                login_background_url=None,
                primary_color="#7c3aed",      # Purple (Violet-600)
                secondary_color="#4f46e5",    # Indigo-600
                accent_color="#f97316",       # Orange-500
                support_email="shaeadam@gmail.com",
                support_url="https://xyzcorp.com/support",
                terms_url="https://xyzcorp.com/terms",
                privacy_url="https://xyzcorp.com/privacy",
                show_powered_by=False,  # Hide "Powered by TimeTracker"
            )
            db.add(branding)
            
            print(f"   ✓ Branding created")
            print(f"      App Name: {branding.app_name}")
            print(f"      Primary Color: {branding.primary_color}")
            print(f"      Subdomain: {branding.subdomain}")
            
            # Create admin user
            print("\n👤 Creating admin user...")
            
            # Check if user already exists
            result = await db.execute(
                select(User).where(User.email == "shaeadam@gmail.com")
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                # Update existing user to be company admin
                existing_user.company_id = company.id
                existing_user.role = "company_admin"
                admin = existing_user
                print(f"   ✓ Updated existing user to company admin")
            else:
                # Create new admin user
                admin = User(
                    email="shaeadam@gmail.com",
                    password_hash=AuthService.hash_password("XyzTest123!"),
                    name="Shae Adam",
                    role="company_admin",
                    company_id=company.id,
                    is_active=True,
                )
                db.add(admin)
                print(f"   ✓ Admin user created")
            
            # Create a sample employee user
            print("\n👥 Creating sample employee...")
            
            result = await db.execute(
                select(User).where(User.email == "employee@xyzcorp.com")
            )
            existing_employee = result.scalar_one_or_none()
            
            if not existing_employee:
                employee = User(
                    email="employee@xyzcorp.com",
                    password_hash=AuthService.hash_password("Employee123!"),
                    name="Alex Employee",
                    role="employee",
                    company_id=company.id,
                    is_active=True,
                )
                db.add(employee)
                print(f"   ✓ Employee created")
            else:
                existing_employee.company_id = company.id
                print(f"   ✓ Updated existing employee")
            
            # Create default team
            print("\n🏢 Creating default team...")
            
            result = await db.execute(
                select(Team).where(
                    Team.company_id == company.id,
                    Team.name == "XYZ Default Team"
                )
            )
            existing_team = result.scalar_one_or_none()
            
            if not existing_team:
                team = Team(
                    name="XYZ Default Team",
                    company_id=company.id,
                    description="Default team for XYZ Corp projects",
                )
                db.add(team)
                await db.flush()
                print(f"   ✓ Default team created")
            else:
                team = existing_team
                print(f"   ✓ Using existing team")
            
            # Add admin and employee to team
            print("\n👥 Adding users to team...")
            
            # Check if admin is already in team
            result = await db.execute(
                select(TeamMember).where(
                    TeamMember.team_id == team.id,
                    TeamMember.user_id == admin.id
                )
            )
            if not result.scalar_one_or_none():
                admin_member = TeamMember(
                    team_id=team.id,
                    user_id=admin.id,
                    role="admin",
                )
                db.add(admin_member)
                print(f"   ✓ Admin added to team")
            
            # Add employee if exists
            if not existing_employee:
                result = await db.execute(
                    select(User).where(User.email == "employee@xyzcorp.com")
                )
                existing_employee = result.scalar_one_or_none()
            
            if existing_employee:
                result = await db.execute(
                    select(TeamMember).where(
                        TeamMember.team_id == team.id,
                        TeamMember.user_id == existing_employee.id
                    )
                )
                if not result.scalar_one_or_none():
                    employee_member = TeamMember(
                        team_id=team.id,
                        user_id=existing_employee.id,
                        role="member",
                    )
                    db.add(employee_member)
                    print(f"   ✓ Employee added to team")
            
            await db.commit()
            
            print("\n" + "=" * 60)
            print("✅ XYZ CORP SEEDED SUCCESSFULLY!")
            print("=" * 60)
            
            print("\n📋 LOGIN CREDENTIALS:")
            print("-" * 40)
            print("Admin Account:")
            print(f"   Email: shaeadam@gmail.com")
            print(f"   Password: XyzTest123!")
            print(f"   Role: company_admin")
            print()
            print("Employee Account:")
            print(f"   Email: employee@xyzcorp.com")
            print(f"   Password: Employee123!")
            print(f"   Role: employee")
            
            print("\n🔗 ACCESS URLS:")
            print("-" * 40)
            print(f"   Company Slug: xyz-corp")
            print(f"   Login URL: http://localhost:5173/login?company=xyz-corp")
            print(f"   API Branding: GET /api/companies/branding/xyz-corp")
            
            print("\n🎨 WHITE-LABEL BRANDING:")
            print("-" * 40)
            print(f"   App Name: {branding.app_name}")
            print(f"   Tagline: {branding.tagline}")
            print(f"   Primary Color: {branding.primary_color}")
            print(f"   Secondary Color: {branding.secondary_color}")
            print(f"   Accent Color: {branding.accent_color}")
            print(f"   Show Powered By: {branding.show_powered_by}")
            
            print("\n📡 API TEST COMMANDS:")
            print("-" * 40)
            print("Get branding config:")
            print("   curl http://localhost:8000/api/companies/branding/xyz-corp")
            print()
            print("Get company info:")
            print("   curl http://localhost:8000/api/companies/by-slug/xyz-corp")
            
            print("\n" + "=" * 60)
            
            return company
            
        except Exception as e:
            await db.rollback()
            print(f"\n❌ Error seeding XYZ Corp: {e}")
            raise


async def main():
    """Main entry point"""
    try:
        await seed_xyz_corp()
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
