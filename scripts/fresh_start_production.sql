-- ============================================
-- TIME TRACKER - FRESH START FOR PRODUCTION
-- ============================================
-- Purpose: Clear ALL test/operational data before going live
-- This script preserves STRUCTURE but removes TEST DATA
-- 
-- ⚠️  WARNING: THIS WILL DELETE ALL OPERATIONAL DATA!
-- ⚠️  BACKUP YOUR DATABASE FIRST!
-- ============================================
-- Run: psql -h your-host -U your-user -d your-db -f fresh_start_production.sql
-- ============================================

-- ============================================
-- WHAT WILL BE PRESERVED (Structure/Config):
-- ============================================
-- ✅ companies - Your company structure
-- ✅ white_label_configs - Branding settings
-- ✅ users - All user accounts (passwords, roles)
-- ✅ teams - Team structure
-- ✅ team_members - Team memberships
-- ✅ projects - Project definitions
-- ✅ tasks - Task definitions
-- ✅ pay_rates - Pay rate configurations
-- ✅ pay_rate_history - Pay rate change history
-- ✅ api_keys - API integrations
-- ✅ ai_feature_settings - AI settings per company
-- ✅ user_ai_preferences - User AI preferences
-- ✅ account_requests - Pending account requests
-- ============================================

-- ============================================
-- WHAT WILL BE DELETED (Test Data):
-- ============================================
-- 🗑️  time_entries - All time tracking records
-- 🗑️  payroll_periods - All payroll periods
-- 🗑️  payroll_entries - All payroll calculations
-- 🗑️  payroll_adjustments - All payroll adjustments
-- 🗑️  audit_logs - All audit trail
-- 🗑️  ai_usage_log - AI usage statistics
-- 🗑️  project_budget_history - Budget tracking snapshots
-- 🗑️  email_logs - Email history
-- 🗑️  notifications - All notifications
-- ============================================

-- Safety: Start a transaction (can be rolled back if needed)
BEGIN;

-- ============================================
-- STEP 1: Show current data counts
-- ============================================
SELECT '=== CURRENT DATA COUNTS (Before Deletion) ===' as status;
SELECT 'Companies: ' || COUNT(*)::text FROM companies;
SELECT 'Users: ' || COUNT(*)::text FROM users;
SELECT 'Teams: ' || COUNT(*)::text FROM teams;
SELECT 'Projects: ' || COUNT(*)::text FROM projects;
SELECT 'Tasks: ' || COUNT(*)::text FROM tasks;
SELECT 'Time Entries: ' || COUNT(*)::text FROM time_entries;
SELECT 'Payroll Periods: ' || COUNT(*)::text FROM payroll_periods;
SELECT 'Payroll Entries: ' || COUNT(*)::text FROM payroll_entries;
SELECT 'Payroll Adjustments: ' || COUNT(*)::text FROM payroll_adjustments;
SELECT 'Audit Logs: ' || COUNT(*)::text FROM audit_logs;
SELECT 'Notifications: ' || COUNT(*)::text FROM notifications;
SELECT 'Email Logs: ' || COUNT(*)::text FROM email_logs;

-- ============================================
-- STEP 2: DELETE OPERATIONAL DATA
-- Order matters due to foreign key constraints!
-- ============================================

SELECT '=== DELETING OPERATIONAL DATA ===' as status;

-- 2a. Delete payroll_adjustments FIRST (references payroll_entries)
DELETE FROM payroll_adjustments;
SELECT 'Deleted payroll_adjustments' as step;

-- 2b. Delete payroll_entries (references payroll_periods and users)
DELETE FROM payroll_entries;
SELECT 'Deleted payroll_entries' as step;

-- 2c. Delete payroll_periods (references companies and users)
DELETE FROM payroll_periods;
SELECT 'Deleted payroll_periods' as step;

-- 2d. Delete time_entries (references users, projects, tasks)
DELETE FROM time_entries;
SELECT 'Deleted time_entries' as step;

-- 2e. Delete audit_logs (references users and companies)
DELETE FROM audit_logs;
SELECT 'Deleted audit_logs' as step;

-- 2f. Delete ai_usage_log (references users and companies)
DELETE FROM ai_usage_log;
SELECT 'Deleted ai_usage_log' as step;

-- 2g. Delete project_budget_history (references projects)
DELETE FROM project_budget_history;
SELECT 'Deleted project_budget_history' as step;

-- 2h. Delete email_logs (references users and companies)
DELETE FROM email_logs;
SELECT 'Deleted email_logs' as step;

-- 2i. Delete notifications (references users)
DELETE FROM notifications;
SELECT 'Deleted notifications' as step;

-- ============================================
-- STEP 3: Reset budget tracking on projects
-- ============================================
-- Reset project budgets to start fresh (optional)
-- Uncomment if you want to reset budget tracking:
-- UPDATE projects SET current_hours = 0 WHERE current_hours IS NOT NULL;
-- SELECT 'Reset project current_hours' as step;

-- ============================================
-- STEP 4: Verify data counts after deletion
-- ============================================
SELECT '=== DATA COUNTS AFTER DELETION ===' as status;
SELECT 'Companies (preserved): ' || COUNT(*)::text FROM companies;
SELECT 'Users (preserved): ' || COUNT(*)::text FROM users;
SELECT 'Teams (preserved): ' || COUNT(*)::text FROM teams;
SELECT 'Projects (preserved): ' || COUNT(*)::text FROM projects;
SELECT 'Tasks (preserved): ' || COUNT(*)::text FROM tasks;
SELECT 'Pay Rates (preserved): ' || COUNT(*)::text FROM pay_rates;
SELECT 'Time Entries: ' || COUNT(*)::text FROM time_entries;
SELECT 'Payroll Periods: ' || COUNT(*)::text FROM payroll_periods;
SELECT 'Audit Logs: ' || COUNT(*)::text FROM audit_logs;
SELECT 'Notifications: ' || COUNT(*)::text FROM notifications;

-- ============================================
-- STEP 5: Reset sequences to avoid ID gaps
-- ============================================
SELECT '=== RESETTING SEQUENCES ===' as status;

-- Reset time_entries sequence
SELECT setval('time_entries_id_seq', 1, false);

-- Reset payroll sequences
SELECT setval('payroll_periods_id_seq', 1, false);
SELECT setval('payroll_entries_id_seq', 1, false);
SELECT setval('payroll_adjustments_id_seq', 1, false);

-- Reset audit log sequence
SELECT setval('audit_logs_id_seq', 1, false);

-- Reset notification sequence
SELECT setval('notifications_id_seq', 1, false);

-- Reset email log sequence (if exists)
-- SELECT setval('email_logs_id_seq', 1, false);

SELECT '=== Sequences reset ===' as status;

-- ============================================
-- STEP 6: COMMIT OR ROLLBACK
-- ============================================
-- ⚠️  IMPORTANT: Review the output above!
-- If everything looks correct, change ROLLBACK to COMMIT
-- ============================================

-- FOR TESTING (does NOT save changes):
ROLLBACK;
SELECT '⚠️  TRANSACTION ROLLED BACK - No changes saved!' as final_status;
SELECT 'Change ROLLBACK to COMMIT on line 159 to execute for real' as instruction;

-- FOR REAL EXECUTION (uncomment this, comment out ROLLBACK above):
-- COMMIT;
-- SELECT '✅ TRANSACTION COMMITTED - Data has been deleted!' as final_status;

