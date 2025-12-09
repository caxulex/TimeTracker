UPDATE users SET password_hash = '$2b$12$IC7GLi8/CCFkao5uA1B0Tu0Ws0fhUfgRYHwwGsynQD37nNd.XAN3e' WHERE email = 'joe3@joe.com';
SELECT email, name FROM users WHERE email = 'joe3@joe.com';
