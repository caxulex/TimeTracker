"""
Load Testing Script for Time Tracker Application
Uses Locust to simulate concurrent users and measure performance

Run with:
    locust --host=http://127.0.0.1:8000

Then open http://localhost:8089 to configure:
- Number of users (start with 10, then 50, then 100)
- Spawn rate (users per second)
- Host URL
"""

from locust import HttpUser, task, between, TaskSet
import random
import json
from datetime import datetime, timedelta


class UserBehavior(TaskSet):
    """Simulates realistic user behavior patterns"""
    
    def on_start(self):
        """Login when user starts"""
        self.login()
    
    def login(self):
        """Authenticate user and store token"""
        # Use test users (create these in DB first if needed)
        email = f"loadtest{random.randint(1, 100)}@test.com"
        password = "test123"
        
        # Try to login, if fails, register
        response = self.client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            # Register new user
            register_response = self.client.post("/api/auth/register", json={
                "email": email,
                "password": password,
                "name": f"Load Test User {random.randint(1, 100)}"
            })
            
            if register_response.status_code == 201:
                # Now login
                login_response = self.client.post("/api/auth/login", json={
                    "email": email,
                    "password": password
                })
                if login_response.status_code == 200:
                    self.token = login_response.json()["access_token"]
                    self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(10)
    def view_dashboard(self):
        """Most common action - view dashboard"""
        self.client.get("/api/reports/dashboard", headers=self.headers)
    
    @task(5)
    def view_weekly_summary(self):
        """View weekly time summary"""
        self.client.get("/api/reports/weekly", headers=self.headers)
    
    @task(8)
    def list_time_entries(self):
        """List recent time entries"""
        self.client.get("/api/time-entries?skip=0&limit=20", headers=self.headers)
    
    @task(3)
    def start_timer(self):
        """Start a timer (if not already running)"""
        # Check if timer is running first
        status = self.client.get("/api/time-entries/timer", headers=self.headers)
        
        if status.status_code == 200 and not status.json().get("is_running"):
            # Start timer
            self.client.post("/api/time-entries/start", 
                headers=self.headers,
                json={
                    "project_id": 1,  # Assume project 1 exists
                    "description": f"Load test entry {random.randint(1, 1000)}"
                }
            )
    
    @task(2)
    def stop_timer(self):
        """Stop the timer (if running)"""
        status = self.client.get("/api/time-entries/timer", headers=self.headers)
        
        if status.status_code == 200 and status.json().get("is_running"):
            self.client.post("/api/time-entries/stop", headers=self.headers)
    
    @task(4)
    def list_projects(self):
        """List available projects"""
        self.client.get("/api/projects?skip=0&limit=20", headers=self.headers)
    
    @task(2)
    def view_teams(self):
        """View teams"""
        self.client.get("/api/teams", headers=self.headers)
    
    @task(1)
    def create_time_entry(self):
        """Create a manual time entry"""
        start_time = datetime.utcnow() - timedelta(hours=random.randint(1, 8))
        end_time = start_time + timedelta(minutes=random.randint(30, 240))
        
        self.client.post("/api/time-entries",
            headers=self.headers,
            json={
                "project_id": 1,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "description": f"Manual entry {random.randint(1, 1000)}"
            }
        )


class AdminBehavior(TaskSet):
    """Simulates admin user behavior"""
    
    def on_start(self):
        """Login as admin"""
        response = self.client.post("/api/auth/login", json={
            "email": "admin@timetracker.com",
            "password": "admin123"
        })
        
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(5)
    def view_admin_dashboard(self):
        """View admin dashboard"""
        self.client.get("/api/reports/admin/dashboard", headers=self.headers)
    
    @task(3)
    def view_all_time_entries(self):
        """View all time entries"""
        self.client.get("/api/admin/time-entries?" + 
            f"start_date=2025-12-01&end_date=2025-12-31",
            headers=self.headers
        )
    
    @task(2)
    def view_activity_alerts(self):
        """View activity alerts"""
        self.client.get("/api/admin/activity-alerts", headers=self.headers)
    
    @task(3)
    def view_workers_report(self):
        """View workers report"""
        self.client.get("/api/admin/workers-report?" + 
            f"start_date=2025-12-01&end_date=2025-12-31",
            headers=self.headers
        )
    
    @task(1)
    def view_system_metrics(self):
        """View system metrics"""
        self.client.get("/api/monitoring/metrics", headers=self.headers)


class RegularUser(HttpUser):
    """Simulates regular user behavior"""
    tasks = [UserBehavior]
    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks
    weight = 9  # 90% of users are regular users


class AdminUser(HttpUser):
    """Simulates admin user behavior"""
    tasks = [AdminBehavior]
    wait_time = between(2, 8)  # Admins think more before actions
    weight = 1  # 10% of users are admins


class HealthCheckUser(HttpUser):
    """Continuously checks health endpoints (simulates monitoring)"""
    wait_time = between(5, 10)
    weight = 1
    
    @task
    def health_check(self):
        self.client.get("/health")
    
    @task
    def metrics_check(self):
        # Only if authenticated as admin
        pass  # Skip for now


# Performance Thresholds (for reference)
# - Response Time: 95th percentile should be < 1000ms
# - Throughput: Should handle 100+ requests/second
# - Error Rate: Should be < 1%
# - Database: Connection pool should not exhaust
# - Memory: Should not increase significantly over time (check for leaks)
