# Load Test Results — Phase 9B

**Date:** _(fill in after running)_
**Environment:** local dev / staging / production
**Backend:** FastAPI on `127.0.0.1:8000`
**Database:** PostgreSQL 15+
**Migration 020 applied:** yes / no

---

## Test Configuration

| Parameter              | Value |
|------------------------|-------|
| Total concurrent users | 115   |
| Login users (weight)   | 50    |
| Time entry users       | 50    |
| Report users           | 10    |
| Export users           | 5     |
| Test duration          | 5 min |
| Ramp-up rate           | 10 users/sec |

## How to Run

```bash
# 1. Start backend
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2. Create test users (if not done)
python setup_load_test_users.py

# 3. Apply Phase 9B indexes
alembic upgrade head

# 4. Run load test
cd .. && locust -f locustfile_phase9b.py --host=http://127.0.0.1:8000

# 5. Open http://localhost:8089, set 115 users, spawn rate 10/s, run 5 min
```

---

## Results

### Response Times (milliseconds)

| Endpoint                          | Requests | p50 | p95 | p99 | Fail % |
|-----------------------------------|----------|-----|-----|-----|--------|
| `POST /api/auth/login`            |          |     |     |     |        |
| `GET  /api/time-entries [list]`   |          |     |     |     |        |
| `POST /api/time-entries [create]` |          |     |     |     |        |
| `POST /api/time-entries/start`    |          |     |     |     |        |
| `POST /api/time-entries/stop`     |          |     |     |     |        |
| `GET  /api/reports/dashboard`     |          |     |     |     |        |
| `GET  /api/reports/weekly`        |          |     |     |     |        |
| `GET  /api/reports/projects`      |          |     |     |     |        |
| `GET  /api/reports/admin/dashboard`|         |     |     |     |        |
| `GET  /api/export/time-entries [csv]` |      |     |     |     |        |
| `GET  /api/export/time-entries [excel]`|     |     |     |     |        |
| `GET  /api/export/report [csv]`   |          |     |     |     |        |

### Aggregate

| Metric           | Value   | Target     | Pass? |
|------------------|---------|------------|-------|
| Total req/sec    |         | > 100      | ⬜    |
| p95 response     |     ms  | < 1000 ms  | ⬜    |
| p99 response     |     ms  | < 3000 ms  | ⬜    |
| Error rate       |       % | < 1 %      | ⬜    |
| Peak CPU usage   |       % | < 70 %     | ⬜    |
| Memory growth    |     MB  | < 50 MB    | ⬜    |
| DB connections   |         | < pool max | ⬜    |

### Flagged Endpoints (p95 > 1000 ms)

| Endpoint | p95   | Recommendation |
|----------|-------|----------------|
| _(none)_ | —     | —              |

---

## Notes

- Fill in results after running the test.
- Compare before / after applying migration 020 to measure index impact.
- Download Locust CSVs from the web UI for trend tracking.
