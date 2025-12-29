-- Create Superadmin User Script
-- Run this in the PostgreSQL database

-- Check if user exists first
DO $$
DECLARE
    user_exists BOOLEAN;
    password_hash TEXT := '$2b$12$E8VM9nubLahVwTAHhp7Lou1vS2bUIRMFoyeCOiyOC8O8dRNq7Y7A6';
BEGIN
    SELECT EXISTS(SELECT 1 FROM users WHERE email = 'shae@shaemarcus.com') INTO user_exists;
    
    IF user_exists THEN
        -- Update existing user to superadmin
        UPDATE users 
        SET role = 'super_admin',
            password_hash = password_hash,
            is_active = true
        WHERE email = 'shae@shaemarcus.com';
        RAISE NOTICE 'Updated existing user to super_admin!';
    ELSE
        -- Create new superadmin user
        INSERT INTO users (email, password_hash, name, role, is_active, created_at, updated_at)
        VALUES (
            'shae@shaemarcus.com',
            password_hash,
            'Shae Marcus',
            'super_admin',
            true,
            NOW(),
            NOW()
        );
        RAISE NOTICE 'Superadmin account created!';
    END IF;
END $$;

-- Verify the user was created
SELECT id, email, name, role, is_active FROM users WHERE email = 'shae@shaemarcus.com';
