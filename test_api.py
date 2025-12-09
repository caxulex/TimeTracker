import requests
import json

# Login
login_data = {"email": "admin@timetracker.com", "password": "admin123"}
response = requests.post("http://127.0.0.1:8000/api/auth/login", json=login_data)
print(f"Login Status: {response.status_code}")
token = response.json()["access_token"]
print(f"Token: {token[:20]}...")

# Get dashboard
headers = {"Authorization": f"Bearer {token}"}
response = requests.get("http://127.0.0.1:8000/api/reports/admin/dashboard", headers=headers)
print(f"\nDashboard Status: {response.status_code}")
data = response.json()
print(json.dumps(data, indent=2))
