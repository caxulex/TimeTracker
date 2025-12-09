import sys
sys.path.insert(0, r"c:\Users\caxul\Builds Laboratorio del Dolor\TimeTracker\backend")

from app.routers import reports

print(f"Router object: {reports.router}")
print(f"Number of routes: {len(reports.router.routes)}")
print("\nAll routes:")
for route in reports.router.routes:
    print(f"  - {route.path} {route.methods if hasattr(route, 'methods') else 'N/A'}")

# Find dashboard route
dashboard_routes = [r for r in reports.router.routes if 'dashboard' in r.path]
print(f"\nDashboard routes found: {len(dashboard_routes)}")
for route in dashboard_routes:
    print(f"  Path: {route.path}")
    print(f"  Endpoint: {route.endpoint}")
    print(f"  Name: {route.name}")
