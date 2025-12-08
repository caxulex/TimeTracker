import httpx
import json

# Test login as admin
resp = httpx.post('http://localhost:8080/api/auth/login', json={'email': 'admin@timetracker.com', 'password': 'admin123'})
print('Admin login:', resp.status_code)
admin_token = resp.json().get('access_token')

# Test login as worker
resp = httpx.post('http://localhost:8080/api/auth/login', json={'email': 'worker@timetracker.com', 'password': 'worker123'})
print('Worker login:', resp.status_code)
worker_token = resp.json().get('access_token')

# Admin can see all users?
headers = {'Authorization': f'Bearer {admin_token}'}
resp = httpx.get('http://localhost:8080/api/users', headers=headers)
print('Admin list users:', resp.status_code)
if resp.status_code == 200:
    users = resp.json()
    total = users.get('total', len(users.get('items', [])))
    print(f'  Total users visible to admin: {total}')
    for u in users.get('items', [])[:5]:
        print(f"    - {u.get('email')} ({u.get('role')})")

# Admin can see team report?
resp = httpx.get('http://localhost:8080/api/reports/team?team_id=1', headers=headers)
print('Admin team report:', resp.status_code)
if resp.status_code == 200:
    report = resp.json()
    print(f"  Report has {len(report.get('by_user', []))} user summaries")
    for u in report.get('by_user', []):
        print(f"    - {u.get('user_name')}: {u.get('total_hours')}h")

# Worker can see their own dashboard?
headers_worker = {'Authorization': f'Bearer {worker_token}'}
resp = httpx.get('http://localhost:8080/api/reports/dashboard', headers=headers_worker)
print('Worker dashboard:', resp.status_code)

# Worker can see team report? (should fail if not admin)
resp = httpx.get('http://localhost:8080/api/reports/team?team_id=1', headers=headers_worker)
print('Worker team report:', resp.status_code, '(expected: 403 if worker is not team admin)')

# Check if worker is in any team
resp = httpx.get('http://localhost:8080/api/teams', headers=headers_worker)
print('Worker teams:', resp.status_code)
if resp.status_code == 200:
    teams = resp.json()
    print(f"  Worker is in {teams.get('total', 0)} teams")

# Check worker's time entries
resp = httpx.get('http://localhost:8080/api/time', headers=headers_worker)
print('Worker time entries:', resp.status_code)
if resp.status_code == 200:
    entries = resp.json()
    print(f"  Worker has {entries.get('total', 0)} time entries")

print("\n--- ADMIN VISIBILITY CHECK ---")
print("Can admin see ALL workers' time entries?")

# Get all time entries as admin (check if admin can see others)
resp = httpx.get('http://localhost:8080/api/time', headers=headers)
print('Admin time entries:', resp.status_code)
if resp.status_code == 200:
    entries = resp.json()
    print(f"  Admin sees {entries.get('total', 0)} time entries")
