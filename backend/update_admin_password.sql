UPDATE users SET password_hash = '$2b$12$iIPbkxiPg25dZWpYXvrNvugvPcFsu9x7svvr1qd42l/fMfxdUq42K' WHERE email = 'admin@timetracker.com';
SELECT email, name, role, substring(password_hash, 1, 20) as hash_check FROM users WHERE email = 'admin@timetracker.com';
