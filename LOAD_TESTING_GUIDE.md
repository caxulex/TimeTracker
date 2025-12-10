# Load Testing Guide for Time Tracker

## Prerequisites

1. **Backend Running**: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
2. **Database Running**: PostgreSQL + Redis containers
3. **Locust Installed**: `pip install locust` (already done)

## Setup Test Users

Create 100 test users for load testing:

```bash
cd backend
python setup_load_test_users.py
```

This creates users:
- **Emails**: loadtest1@test.com - loadtest100@test.com
- **Password**: test123

## Running Load Tests

### 1. Start Locust

```bash
cd TimeTracker
locust --host=http://127.0.0.1:8000
```

### 2. Open Web UI

Navigate to: http://localhost:8089

### 3. Configure Test Scenarios

#### Scenario 1: Light Load (10 users)
- **Number of users**: 10
- **Spawn rate**: 2 users/second
- **Duration**: 5 minutes
- **Expected**: All requests should succeed, < 500ms response time

#### Scenario 2: Medium Load (50 users)
- **Number of users**: 50
- **Spawn rate**: 5 users/second
- **Duration**: 10 minutes
- **Expected**: < 1000ms response time, < 1% error rate

#### Scenario 3: Heavy Load (100 users)
- **Number of users**: 100
- **Spawn rate**: 10 users/second
- **Duration**: 15 minutes
- **Expected**: < 2000ms response time, < 5% error rate

#### Scenario 4: Stress Test (200+ users)
- **Number of users**: 200
- **Spawn rate**: 10 users/second
- **Duration**: 5 minutes
- **Purpose**: Find breaking point

## Metrics to Monitor

### 1. Locust Dashboard
- **Requests/second**: Should increase linearly with users
- **Response Time**: Monitor 50th, 95th, 99th percentiles
- **Failure Rate**: Should stay below 1-5%
- **Total Requests**: Track successful vs failed

### 2. Backend Metrics
Open: http://127.0.0.1:8000/api/monitoring/metrics

Monitor:
- **CPU Usage**: Should stay < 80%
- **Memory Usage**: Should not continuously increase (memory leaks)
- **Database Connections**: Check connection pool usage

### 3. Database
```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity;

-- Check slow queries
SELECT query, state, query_start 
FROM pg_stat_activity 
WHERE state != 'idle' 
ORDER BY query_start;
```

## Expected Performance

### Target Metrics (at 100 concurrent users):
- ✅ **Response Time (95th percentile)**: < 1000ms
- ✅ **Throughput**: > 100 requests/second
- ✅ **Error Rate**: < 1%
- ✅ **CPU Usage**: < 70%
- ✅ **Memory**: Stable (no continuous growth)

### Red Flags:
- ❌ Response time > 3000ms
- ❌ Error rate > 10%
- ❌ Memory continuously increasing
- ❌ Database connection pool exhausted
- ❌ 500 errors in logs

## Common Issues & Solutions

### Issue: High Response Times
**Cause**: Database queries not optimized  
**Solution**: Add indexes, optimize N+1 queries

### Issue: Database Connection Exhaustion
**Cause**: Too many concurrent DB connections  
**Solution**: Adjust pool size in `config.py`

### Issue: Memory Leaks
**Cause**: Not closing database sessions  
**Solution**: Use context managers, check for unclosed connections

### Issue: High CPU Usage
**Cause**: Inefficient algorithms, CPU-bound operations  
**Solution**: Profile with `py-spy`, optimize hot paths

## Cleanup

After load testing, delete test users:

```bash
cd backend
python setup_load_test_users.py cleanup
```

## Analysis

### Generate Report

Locust automatically generates:
- Charts for response times
- Request statistics
- Failure distribution
- Download CSV for further analysis

### Key Questions to Answer:
1. What is the maximum concurrent users we can handle?
2. Which endpoints are slowest?
3. Are there any endpoints that fail under load?
4. Does performance degrade linearly or exponentially?
5. Are there memory leaks?

## Next Steps After Load Testing

Based on results:
1. **Optimize slow endpoints** (target: < 500ms for 95th percentile)
2. **Add caching** for frequently accessed data
3. **Database indexing** for common queries
4. **Connection pooling** optimization
5. **Consider horizontal scaling** if needed

## Production Recommendations

- **Monitoring**: Set up APM (New Relic, DataDog, or Prometheus)
- **Auto-scaling**: Configure based on CPU/Memory usage
- **Rate Limiting**: Already implemented, adjust limits based on test results
- **Caching**: Add Redis caching for dashboard data
- **CDN**: For static frontend assets
