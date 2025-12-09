from app.services.auth_service import auth_service

# Generate hash
new_hash = auth_service.hash_password('admin123')
print(f"Generated hash: {new_hash}")

# Verify it works
verify = auth_service.verify_password('admin123', new_hash)
print(f"Verification: {verify}")

# Print SQL update command
print(f"\nRun this SQL:")
print(f"UPDATE users SET password_hash = '{new_hash}' WHERE email = 'admin@timetracker.com';")
