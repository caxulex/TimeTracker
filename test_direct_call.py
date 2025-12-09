import sys
sys.path.insert(0, r"c:\Users\caxul\Builds Laboratorio del Dolor\TimeTracker\backend")

import asyncio
from app.routers.reports import get_admin_dashboard
from app.database import get_db
from app.models import User
from datetime import datetime

print("=" * 80)
print("CALLING get_admin_dashboard DIRECTLY")
print("=" * 80)

# Create a mock user
class MockUser:
    id = 1
    email = "admin@timetracker.com"
    role = "super_admin"
    is_active = True

mock_user = MockUser()

# Try calling the function
async def test():
    # Get db session
    async for db in get_db():
        try:
            result = await get_admin_dashboard(db=db, current_user=mock_user)
            print(f"\nResult: {result}")
        finally:
            await db.close()
        break

asyncio.run(test())
