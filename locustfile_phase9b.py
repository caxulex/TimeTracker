"""
Phase 9B Load Testing Script
=============================
Focused load test simulating the specific concurrent scenarios requested:

  a) 50 concurrent users logging in
  b) 50 concurrent users creating time entries
  c) 10 concurrent users running reports
  d)  5 concurrent users running exports

Run with:
    locust -f locustfile_phase9b.py --host=http://127.0.0.1:8000

Then open http://localhost:8089 to start the test.
Set: 115 total users, spawn rate 10/s, run for 5 minutes.

Prerequisites:
    1. Backend running on port 8000
    2. Test users created: python backend/setup_load_test_users.py
    3. At least one project in the database
"""

from locust import HttpUser, task, between, TaskSet
import random
from datetime import datetime, timedelta, timezone


# ---------------------------------------------------------------------------
# SCENARIO A: Login-heavy users (weight 50)
# Simulates frequent authentication requests — measures auth throughput.
# ---------------------------------------------------------------------------
class LoginBehavior(TaskSet):

    @task(1)
    def login(self):
        user_num = random.randint(1, 100)
        payload = {
            "email": f"loadtest{user_num}@test.com",
            "password": "TestPassword123!",
        }
        with self.client.post(
            "/api/auth/login",
            json=payload,
            catch_response=True,
            name="/api/auth/login",
        ) as resp:
            if resp.status_code in (200, 401):
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")


class LoginUser(HttpUser):
    tasks = [LoginBehavior]
    wait_time = between(0.5, 2)
    weight = 50


# ---------------------------------------------------------------------------
# SCENARIO B: Time-entry creators (weight 50)
# Simulates users creating, listing, starting and stopping time entries.
# ---------------------------------------------------------------------------
class TimeEntryBehavior(TaskSet):

    token: str = ""
    headers: dict = {}

    def on_start(self):
        user_num = random.randint(1, 100)
        resp = self.client.post("/api/auth/login", json={
            "email": f"loadtest{user_num}@test.com",
            "password": "TestPassword123!",
        })
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")
            self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(5)
    def list_time_entries(self):
        self.client.get(
            "/api/time-entries?skip=0&limit=20",
            headers=self.headers,
            name="/api/time-entries [list]",
        )

    @task(3)
    def create_time_entry(self):
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=random.randint(1, 8))
        end = start + timedelta(hours=1)
        payload = {
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "description": f"Load test entry {random.randint(1, 99999)}",
        }
        self.client.post(
            "/api/time-entries",
            json=payload,
            headers=self.headers,
            name="/api/time-entries [create]",
        )

    @task(2)
    def start_timer(self):
        payload = {
            "description": f"Timer test {random.randint(1, 99999)}",
        }
        with self.client.post(
            "/api/time-entries/start",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="/api/time-entries/start",
        ) as resp:
            # 400 = timer already running, which is expected
            if resp.status_code in (200, 201, 400):
                resp.success()

    @task(2)
    def stop_timer(self):
        with self.client.post(
            "/api/time-entries/stop",
            headers=self.headers,
            catch_response=True,
            name="/api/time-entries/stop",
        ) as resp:
            # 400 = no running timer, expected
            if resp.status_code in (200, 400):
                resp.success()


class TimeEntryUser(HttpUser):
    tasks = [TimeEntryBehavior]
    wait_time = between(1, 3)
    weight = 50


# ---------------------------------------------------------------------------
# SCENARIO C: Report viewers (weight 10)
# Simulates users viewing dashboards and reports — heaviest DB queries.
# ---------------------------------------------------------------------------
class ReportBehavior(TaskSet):

    token: str = ""
    headers: dict = {}

    def on_start(self):
        user_num = random.randint(1, 100)
        resp = self.client.post("/api/auth/login", json={
            "email": f"loadtest{user_num}@test.com",
            "password": "TestPassword123!",
        })
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")
            self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(5)
    def view_dashboard(self):
        self.client.get(
            "/api/reports/dashboard",
            headers=self.headers,
            name="/api/reports/dashboard",
        )

    @task(3)
    def view_weekly(self):
        self.client.get(
            "/api/reports/weekly",
            headers=self.headers,
            name="/api/reports/weekly",
        )

    @task(2)
    def view_projects_report(self):
        self.client.get(
            "/api/reports/projects",
            headers=self.headers,
            name="/api/reports/projects",
        )

    @task(1)
    def view_admin_dashboard(self):
        with self.client.get(
            "/api/reports/admin/dashboard",
            headers=self.headers,
            catch_response=True,
            name="/api/reports/admin/dashboard",
        ) as resp:
            # 403 = not admin, expected for regular users
            if resp.status_code in (200, 403):
                resp.success()


class ReportUser(HttpUser):
    tasks = [ReportBehavior]
    wait_time = between(2, 5)
    weight = 10


# ---------------------------------------------------------------------------
# SCENARIO D: Export users (weight 5)
# Simulates users running CSV/Excel exports — file generation.
# ---------------------------------------------------------------------------
class ExportBehavior(TaskSet):

    token: str = ""
    headers: dict = {}

    def on_start(self):
        user_num = random.randint(1, 100)
        resp = self.client.post("/api/auth/login", json={
            "email": f"loadtest{user_num}@test.com",
            "password": "TestPassword123!",
        })
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")
            self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def export_csv(self):
        with self.client.get(
            "/api/export/time-entries?format=csv",
            headers=self.headers,
            catch_response=True,
            name="/api/export/time-entries [csv]",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()

    @task(2)
    def export_excel(self):
        with self.client.get(
            "/api/export/time-entries?format=xlsx",
            headers=self.headers,
            catch_response=True,
            name="/api/export/time-entries [excel]",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()

    @task(1)
    def export_report(self):
        with self.client.get(
            "/api/export/report?format=csv",
            headers=self.headers,
            catch_response=True,
            name="/api/export/report [csv]",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()


class ExportUser(HttpUser):
    tasks = [ExportBehavior]
    wait_time = between(3, 8)
    weight = 5
