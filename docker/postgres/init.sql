-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'regular_user',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    phone VARCHAR(50),
    address TEXT,
    emergency_contact_name VARCHAR(255),
    emergency_contact_phone VARCHAR(50),
    job_title VARCHAR(255),
    department VARCHAR(255),
    employment_type VARCHAR(50),
    start_date DATE,
    expected_hours_per_week INTEGER,
    manager_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create teams table
CREATE TABLE IF NOT EXISTS teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create team_members table
CREATE TABLE IF NOT EXISTS team_members (
    team_id INTEGER NOT NULL REFERENCES teams(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    PRIMARY KEY (team_id, user_id)
);

-- Create projects table
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    color VARCHAR(7) NOT NULL DEFAULT '#3B82F6',
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'TODO',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create time_entries table
CREATE TABLE IF NOT EXISTS time_entries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    project_id INTEGER NOT NULL REFERENCES projects(id),
    task_id INTEGER REFERENCES tasks(id),
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    description TEXT,
    is_running BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create indexes
CREATE INDEX IF NOT EXISTS ix_time_entries_user_id ON time_entries(user_id);
CREATE INDEX IF NOT EXISTS ix_time_entries_project_id ON time_entries(project_id);
CREATE INDEX IF NOT EXISTS ix_time_entries_task_id ON time_entries(task_id);
CREATE INDEX IF NOT EXISTS ix_time_entries_start_time ON time_entries(start_time);
CREATE INDEX IF NOT EXISTS ix_time_entries_created_at ON time_entries(created_at);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
CREATE INDEX IF NOT EXISTS ix_projects_team_id ON projects(team_id);
CREATE INDEX IF NOT EXISTS ix_tasks_project_id ON tasks(project_id);

-- Create account_requests table
CREATE TABLE IF NOT EXISTS account_requests (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    job_title VARCHAR(255),
    department VARCHAR(255),
    message TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    admin_notes TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS ix_account_requests_email ON account_requests(email);
CREATE INDEX IF NOT EXISTS ix_account_requests_status ON account_requests(status);
-- Create payroll_periods table
CREATE TABLE IF NOT EXISTS payroll_periods (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    period_type VARCHAR(20) NOT NULL DEFAULT 'monthly',
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    approved_by INTEGER REFERENCES users(id),
    approved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
-- Create pay_rates table
CREATE TABLE IF NOT EXISTS pay_rates (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    rate_type VARCHAR(20) NOT NULL DEFAULT 'hourly',
    base_rate NUMERIC(10, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    overtime_multiplier NUMERIC(4, 2) NOT NULL DEFAULT 1.5,
    effective_from DATE NOT NULL,
    effective_to DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create pay_rate_history table
CREATE TABLE IF NOT EXISTS pay_rate_history (
    id SERIAL PRIMARY KEY,
    pay_rate_id INTEGER NOT NULL REFERENCES pay_rates(id),
    previous_rate NUMERIC(10, 2) NOT NULL,
    new_rate NUMERIC(10, 2) NOT NULL,
    previous_overtime_multiplier NUMERIC(4, 2),
    new_overtime_multiplier NUMERIC(4, 2),
    changed_by INTEGER NOT NULL REFERENCES users(id),
    change_reason TEXT,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create pay_rates indexes
CREATE INDEX IF NOT EXISTS ix_pay_rates_user_id ON pay_rates(user_id);
CREATE INDEX IF NOT EXISTS ix_pay_rates_effective_from ON pay_rates(effective_from);
CREATE INDEX IF NOT EXISTS ix_pay_rate_history_pay_rate_id ON pay_rate_history(pay_rate_id);
-- Create payroll_entries table
CREATE TABLE IF NOT EXISTS payroll_entries (
    id SERIAL PRIMARY KEY,
    payroll_period_id INTEGER NOT NULL REFERENCES payroll_periods(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    regular_hours NUMERIC(8, 2) NOT NULL DEFAULT 0.00,
    overtime_hours NUMERIC(8, 2) NOT NULL DEFAULT 0.00,
    regular_rate NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    overtime_rate NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    gross_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    adjustments_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    net_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create payroll_adjustments table
CREATE TABLE IF NOT EXISTS payroll_adjustments (
    id SERIAL PRIMARY KEY,
    payroll_entry_id INTEGER NOT NULL REFERENCES payroll_entries(id),
    adjustment_type VARCHAR(20) NOT NULL,
    description VARCHAR(500) NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create payroll indexes
CREATE INDEX IF NOT EXISTS ix_payroll_periods_start_date ON payroll_periods(start_date);
CREATE INDEX IF NOT EXISTS ix_payroll_periods_end_date ON payroll_periods(end_date);
CREATE INDEX IF NOT EXISTS ix_payroll_periods_status ON payroll_periods(status);
CREATE INDEX IF NOT EXISTS ix_payroll_entries_payroll_period_id ON payroll_entries(payroll_period_id);
CREATE INDEX IF NOT EXISTS ix_payroll_entries_user_id ON payroll_entries(user_id);
CREATE INDEX IF NOT EXISTS ix_payroll_adjustments_payroll_entry_id ON payroll_adjustments(payroll_entry_id);
