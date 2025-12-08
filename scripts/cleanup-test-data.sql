-- ============================================
-- TIME TRACKER - TEST DATA CLEANUP SCRIPT
-- ============================================
-- This script removes test data created by automated tests
-- Order matters for foreign key constraints!
-- ============================================

-- Start transaction for safety
BEGIN;

-- Show counts before cleanup
SELECT 'Before cleanup:' as status;
SELECT 'Test users to delete: ' || COUNT(*)::text FROM users 
WHERE email LIKE 'test-%@example.com' 
   OR email LIKE 'admin-%@example.com' 
   OR email LIKE 'newuser-%@example.com';
   
SELECT 'Test teams to delete: ' || COUNT(*)::text FROM teams 
WHERE name IN ('Test Team', 'New Team', 'Updated Team Name', 'Time Entry Test Team', 
               'Team To Delete', 'Integration Test Team', 'New team', 'Tech team');

-- Step 1: Get test user IDs
CREATE TEMP TABLE test_user_ids AS
SELECT id FROM users 
WHERE email LIKE 'test-%@example.com' 
   OR email LIKE 'admin-%@example.com' 
   OR email LIKE 'newuser-%@example.com';

-- Step 2: Get test team IDs (keeping Development Team and Design Team)
CREATE TEMP TABLE test_team_ids AS
SELECT id FROM teams 
WHERE name IN ('Test Team', 'New Team', 'Updated Team Name', 'Time Entry Test Team', 
               'Team To Delete', 'Integration Test Team', 'New team', 'Tech team');

-- Step 3: Get project IDs belonging to test teams
CREATE TEMP TABLE test_project_ids AS
SELECT id FROM projects WHERE team_id IN (SELECT id FROM test_team_ids);

-- Step 4: Delete payroll_adjustments for test users
DELETE FROM payroll_adjustments 
WHERE created_by IN (SELECT id FROM test_user_ids);

-- Step 5: Delete payroll_entries for test users
DELETE FROM payroll_entries 
WHERE user_id IN (SELECT id FROM test_user_ids);

-- Step 6: Delete payroll_periods approved by test users
UPDATE payroll_periods SET approved_by = NULL 
WHERE approved_by IN (SELECT id FROM test_user_ids);

-- Step 7: Delete pay_rate_history for test users
DELETE FROM pay_rate_history 
WHERE changed_by IN (SELECT id FROM test_user_ids);

-- Step 8: Delete pay_rates for test users
DELETE FROM pay_rates 
WHERE user_id IN (SELECT id FROM test_user_ids)
   OR created_by IN (SELECT id FROM test_user_ids);

-- Step 9: Delete ALL time entries that reference test projects OR test users
DELETE FROM time_entries 
WHERE user_id IN (SELECT id FROM test_user_ids)
   OR project_id IN (SELECT id FROM test_project_ids);

-- Step 10: Delete tasks in test projects
DELETE FROM tasks 
WHERE project_id IN (SELECT id FROM test_project_ids);

-- Step 11: Delete test projects
DELETE FROM projects 
WHERE id IN (SELECT id FROM test_project_ids);

-- Step 12: Delete team memberships for test users and test teams
DELETE FROM team_members 
WHERE user_id IN (SELECT id FROM test_user_ids)
   OR team_id IN (SELECT id FROM test_team_ids);

-- Step 13: Delete test teams FIRST (before users, because teams.owner_id references users)
DELETE FROM teams 
WHERE id IN (SELECT id FROM test_team_ids)
  AND name NOT IN ('Development Team', 'Design Team');

-- Step 14: NOW delete test users (but keep main seed users)
DELETE FROM users 
WHERE id IN (SELECT id FROM test_user_ids)
  AND email NOT IN ('admin@timetracker.com', 'worker@timetracker.com');

-- Show counts after cleanup
SELECT 'After cleanup:' as status;
SELECT 'Users remaining: ' || COUNT(*)::text FROM users;
SELECT 'Teams remaining: ' || COUNT(*)::text FROM teams;
SELECT 'Projects remaining: ' || COUNT(*)::text FROM projects;
SELECT 'Time entries remaining: ' || COUNT(*)::text FROM time_entries;

-- Clean up temp tables
DROP TABLE test_user_ids;
DROP TABLE test_team_ids;
DROP TABLE test_project_ids;

-- Commit the transaction
COMMIT;

-- Reset sequences to avoid gaps
SELECT setval('users_id_seq', (SELECT COALESCE(MAX(id), 1) FROM users));
SELECT setval('teams_id_seq', (SELECT COALESCE(MAX(id), 1) FROM teams));
SELECT setval('projects_id_seq', (SELECT COALESCE(MAX(id), 1) FROM projects));
SELECT setval('tasks_id_seq', (SELECT COALESCE(MAX(id), 1) FROM tasks));
SELECT setval('time_entries_id_seq', (SELECT COALESCE(MAX(id), 1) FROM time_entries));

SELECT 'Cleanup complete!' as status;
