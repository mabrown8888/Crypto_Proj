#!/usr/bin/env python3
"""
Create a default user for testing
"""

from auth import register_user
import sys

def create_default_user():
    """Create a default user for testing"""
    print("Creating default user...")
    
    # Default credentials
    username = "admin"
    password = "admin123"
    email = "admin@example.com"
    
    result = register_user(username, password, email)
    
    if result['success']:
        print(f"✅ User '{username}' created successfully!")
        print(f"📧 Email: {email}")
        print(f"🔑 Password: {password}")
        print("\nYou can now login with these credentials.")
    else:
        print(f"❌ Failed to create user: {result['error']}")
        return False
    
    return True

if __name__ == "__main__":
    success = create_default_user()
    sys.exit(0 if success else 1)