#!/usr/bin/env python3
"""
TIME TRACKER - FRESH START FOR PRODUCTION
==========================================
Purpose: Clear ALL test/operational data before going live
This script preserves STRUCTURE but removes TEST DATA

⚠️  WARNING: THIS WILL DELETE ALL OPERATIONAL DATA!
⚠️  BACKUP YOUR DATABASE FIRST!

Usage:
    python fresh_start_production.py --dry-run    # Preview changes only
    python fresh_start_production.py --execute    # Actually delete data

Requirements:
    pip install asyncpg python-dotenv
"""

import asyncio
import os
import sys
from datetime import datetime

# Check if we have the required packages
try:
    import asyncpg
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Run: pip install asyncpg python-dotenv")
    sys.exit(1)


# ============================================
# CONFIGURATION
# ============================================

# Tables to DELETE (operational/test data)
TABLES_TO_DELETE = [
    # Order matters due to foreign key constraints!
    # Delete children first, then parents
    "payroll_adjustments",    # References payroll_entries
    "payroll_entries",        # References payroll_periods, users
    "payroll_periods",        # References companies, users
    "time_entries",           # References users, projects, tasks
    "audit_logs",             # References users, companies
    "ai_usage_log",           # References users, companies
    "project_budget_history", # References projects
    "email_logs",             # References users, companies
    "notifications",          # References users
]

# Tables to PRESERVE (structure/config)
TABLES_TO_PRESERVE = [
    "companies",              # Company structure
    "white_label_configs",    # Branding settings
    "users",                  # All user accounts
    "teams",                  # Team structure
    "team_members",           # Team memberships
    "projects",               # Project definitions
    "tasks",                  # Task definitions
    "pay_rates",              # Pay rate configurations
    "pay_rate_history",       # Pay rate change history
    "api_keys",               # API integrations
    "ai_feature_settings",    # AI settings per company
    "user_ai_preferences",    # User AI preferences
    "account_requests",       # Pending account requests
    "alembic_version",        # Migration tracking
]


async def get_table_count(conn, table_name: str) -> int:
    """Get the row count for a table."""
    try:
        result = await conn.fetchval(f'SELECT COUNT(*) FROM "{table_name}"')
        return result or 0
    except Exception as e:
        print(f"  ⚠️  Could not count {table_name}: {e}")
        return -1


async def delete_table_data(conn, table_name: str, dry_run: bool = True) -> int:
    """Delete all data from a table."""
    count = await get_table_count(conn, table_name)
    
    if count == 0:
        print(f"  ⏭️  {table_name}: Already empty")
        return 0
    
    if dry_run:
        print(f"  🔍 {table_name}: Would delete {count} rows")
        return count
    
    try:
        await conn.execute(f'DELETE FROM "{table_name}"')
        print(f"  ✅ {table_name}: Deleted {count} rows")
        return count
    except Exception as e:
        print(f"  ❌ {table_name}: Error - {e}")
        return -1


async def reset_sequence(conn, table_name: str, dry_run: bool = True):
    """Reset a table's ID sequence to 1."""
    sequence_name = f"{table_name}_id_seq"
    try:
        if dry_run:
            print(f"  🔍 Would reset {sequence_name}")
        else:
            await conn.execute(f"SELECT setval('{sequence_name}', 1, false)")
            print(f"  ✅ Reset {sequence_name}")
    except Exception as e:
        # Sequence might not exist for all tables
        pass


async def show_preserved_data(conn):
    """Show counts for preserved tables."""
    print("\n📊 PRESERVED DATA (Will NOT be deleted):")
    print("-" * 45)
    for table in TABLES_TO_PRESERVE:
        count = await get_table_count(conn, table)
        if count >= 0:
            print(f"  ✅ {table}: {count} rows")


async def main(dry_run: bool = True):
    """Main execution function."""
    
    print("=" * 60)
    print("TIME TRACKER - FRESH START FOR PRODUCTION")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Mode: {'DRY RUN (Preview Only)' if dry_run else '🚨 EXECUTING FOR REAL 🚨'}")
    print("=" * 60)
    
    # Load environment
    load_dotenv()
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        # Try alternative env var names
        database_url = os.getenv("DB_URL") or os.getenv("POSTGRES_URL")
    
    if not database_url:
        print("\n❌ ERROR: DATABASE_URL not found in environment!")
        print("Make sure your .env file contains DATABASE_URL")
        return False
    
    # Convert SQLAlchemy URL to asyncpg format
    # postgresql+asyncpg://user:pass@host/db -> postgresql://user:pass@host/db
    database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    database_url = database_url.replace("postgres+asyncpg://", "postgresql://")
    
    # Parse connection string for display (hide password)
    try:
        # Extract host from URL for display
        if "@" in database_url:
            host_part = database_url.split("@")[1].split("/")[0]
            print(f"\n🔌 Connecting to: {host_part}")
    except:
        pass
    
    # Connect to database
    try:
        conn = await asyncpg.connect(database_url)
        print("✅ Connected to database")
    except Exception as e:
        print(f"\n❌ ERROR: Could not connect to database: {e}")
        return False
    
    try:
        # Start transaction
        async with conn.transaction():
            
            # Show what will be preserved
            await show_preserved_data(conn)
            
            # Show and optionally delete test data
            print("\n🗑️  OPERATIONAL DATA TO DELETE:")
            print("-" * 45)
            
            total_deleted = 0
            for table in TABLES_TO_DELETE:
                count = await delete_table_data(conn, table, dry_run)
                if count > 0:
                    total_deleted += count
            
            # Reset sequences
            print("\n🔄 SEQUENCE RESETS:")
            print("-" * 45)
            for table in TABLES_TO_DELETE:
                await reset_sequence(conn, table, dry_run)
            
            # Summary
            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            print(f"Total rows {'to delete' if dry_run else 'deleted'}: {total_deleted}")
            
            if dry_run:
                print("\n⚠️  DRY RUN COMPLETE - No changes were made!")
                print("To execute for real, run:")
                print("  python fresh_start_production.py --execute")
                # Rollback transaction (no changes)
                raise asyncio.CancelledError("Dry run rollback")
            else:
                print("\n✅ ALL CHANGES COMMITTED!")
                print("Your database is now ready for production!")
                
    except asyncio.CancelledError:
        # Expected for dry run
        pass
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("Transaction rolled back - no changes saved")
        return False
    finally:
        await conn.close()
        print("\n🔌 Database connection closed")
    
    return True


if __name__ == "__main__":
    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python fresh_start_production.py --dry-run    # Preview changes only")
        print("  python fresh_start_production.py --execute    # Actually delete data")
        sys.exit(1)
    
    arg = sys.argv[1].lower()
    
    if arg == "--dry-run":
        asyncio.run(main(dry_run=True))
    elif arg == "--execute":
        print("\n" + "🚨" * 20)
        print("WARNING: This will DELETE ALL operational data!")
        print("Make sure you have a backup!")
        print("🚨" * 20)
        
        confirm = input("\nType 'DELETE' to confirm: ")
        if confirm == "DELETE":
            asyncio.run(main(dry_run=False))
        else:
            print("Aborted.")
    else:
        print(f"Unknown argument: {arg}")
        print("Use --dry-run or --execute")
        sys.exit(1)
