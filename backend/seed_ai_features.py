"""
Script to seed AI feature settings into the database.
Run this if the ai_feature_settings table is empty.

Usage (on server):
  docker-compose -f docker-compose.prod.yml exec backend python seed_ai_features.py
"""

import asyncio
import sys
sys.path.insert(0, '/app')

from sqlalchemy import text
from app.database import async_session


FEATURES = [
    {
        "feature_id": "ai_suggestions",
        "feature_name": "Time Entry Suggestions",
        "description": "AI-powered suggestions for projects and tasks based on your work patterns",
        "is_enabled": True,
        "requires_api_key": True,
        "api_provider": "gemini"
    },
    {
        "feature_id": "ai_anomaly_alerts",
        "feature_name": "Anomaly Detection",
        "description": "Automatic detection of unusual work patterns like overtime or missing entries",
        "is_enabled": True,
        "requires_api_key": True,
        "api_provider": "gemini"
    },
    {
        "feature_id": "ai_payroll_forecast",
        "feature_name": "Payroll Forecasting",
        "description": "Predictive analytics for payroll and budget planning",
        "is_enabled": False,
        "requires_api_key": True,
        "api_provider": "gemini"
    },
    {
        "feature_id": "ai_nlp_entry",
        "feature_name": "Natural Language Entry",
        "description": "Create time entries using natural language like 'Log 2 hours on Project Alpha'",
        "is_enabled": False,
        "requires_api_key": True,
        "api_provider": "gemini"
    },
    {
        "feature_id": "ai_report_summaries",
        "feature_name": "AI Report Summaries",
        "description": "AI-generated insights and summaries in your reports",
        "is_enabled": False,
        "requires_api_key": True,
        "api_provider": "gemini"
    },
    {
        "feature_id": "ai_task_estimation",
        "feature_name": "Task Duration Estimation",
        "description": "AI-powered estimates for how long tasks will take",
        "is_enabled": False,
        "requires_api_key": True,
        "api_provider": "gemini"
    }
]


async def seed_features():
    async with async_session() as db:
        # Check if features already exist
        result = await db.execute(text("SELECT COUNT(*) FROM ai_feature_settings"))
        count = result.scalar()
        
        if count > 0:
            print(f"✅ AI features already seeded ({count} features found)")
            
            # Show existing features
            result = await db.execute(text("SELECT feature_id, feature_name, is_enabled FROM ai_feature_settings"))
            for row in result:
                status = "✅ ON" if row[2] else "❌ OFF"
                print(f"   - {row[0]}: {row[1]} [{status}]")
            return
        
        print("🔄 Seeding AI features...")
        
        for feature in FEATURES:
            await db.execute(
                text("""
                    INSERT INTO ai_feature_settings 
                    (feature_id, feature_name, description, is_enabled, requires_api_key, api_provider)
                    VALUES (:feature_id, :feature_name, :description, :is_enabled, :requires_api_key, :api_provider)
                    ON CONFLICT (feature_id) DO NOTHING
                """),
                feature
            )
            status = "✅ ON" if feature["is_enabled"] else "❌ OFF"
            print(f"   ✓ {feature['feature_id']}: {feature['feature_name']} [{status}]")
        
        await db.commit()
        print("\n✅ AI features seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed_features())
