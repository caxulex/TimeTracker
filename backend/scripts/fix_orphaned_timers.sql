-- ============================================
-- FIX ORPHANED TIMERS
-- 
-- This script stops all running time entries for users who:
-- 1. Don't have an active work session
-- 2. Have time entries without a work_session_id (legacy entries)
--
-- Run this in your PostgreSQL database to clean up orphaned timers:
-- docker-compose exec postgres psql -U postgres -d time_tracker -f /path/to/fix_orphaned_timers.sql
-- ============================================

-- First, show what will be affected (preview)
SELECT 
    te.id as entry_id,
    u.name as user_name,
    u.email as user_email,
    te.start_time,
    te.work_session_id,
    CASE WHEN te.work_session_id IS NULL THEN 'No session' ELSE 'Session: ' || te.work_session_id::text END as session_status
FROM time_entries te
JOIN users u ON te.user_id = u.id
WHERE te.end_time IS NULL
ORDER BY te.start_time DESC;

-- Now fix orphaned entries (entries without active sessions)
-- This closes ALL running time entries where the user has no active session
UPDATE time_entries te
SET 
    end_time = NOW(),
    is_running = false,
    is_paused = false,
    duration_seconds = EXTRACT(EPOCH FROM (NOW() - te.start_time))::int - COALESCE(te.pause_seconds, 0)
FROM users u
WHERE te.user_id = u.id
AND te.end_time IS NULL
AND NOT EXISTS (
    SELECT 1 FROM work_sessions ws
    WHERE ws.user_id = te.user_id
    AND ws.end_time IS NULL
);

-- Also close entries that ARE linked to a session but that session has ended
UPDATE time_entries te
SET 
    end_time = ws.end_time,
    is_running = false,
    is_paused = false,
    duration_seconds = EXTRACT(EPOCH FROM (ws.end_time - te.start_time))::int - COALESCE(te.pause_seconds, 0)
FROM work_sessions ws
WHERE te.work_session_id = ws.id
AND te.end_time IS NULL
AND ws.end_time IS NOT NULL;

-- Verify - should return 0 rows if all fixed
SELECT COUNT(*) as remaining_running_entries
FROM time_entries 
WHERE end_time IS NULL;

-- Show updated entries
SELECT 
    te.id as entry_id,
    u.name as user_name,
    te.start_time,
    te.end_time,
    te.duration_seconds,
    te.is_running
FROM time_entries te
JOIN users u ON te.user_id = u.id
WHERE te.updated_at > NOW() - INTERVAL '1 minute'
ORDER BY te.updated_at DESC
LIMIT 20;
