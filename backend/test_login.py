#!/usr/bin/env python3
"""
Test login functionality
"""

import requests
import json

def test_login():
    """Test login with default credentials"""
    print("Testing login functionality...")
    
    url = "http://localhost:5001/api/auth/login"
    
    # Test credentials
    credentials = {
        "username": "admin",
        "password": "admin123"
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=credentials, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Login successful!")
                print(f"Token: {data.get('token')[:50]}...")
                print(f"Username: {data.get('username')}")
                return True
            else:
                print("❌ Login failed:", data.get('error'))
        else:
            print("❌ HTTP Error:", response.status_code)
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return False

def test_register():
    """Test registration with new user"""
    print("\nTesting registration functionality...")
    
    url = "http://localhost:5001/api/auth/register"
    
    # Test credentials
    credentials = {
        "username": "testuser",
        "password": "test123",
        "email": "test@example.com"
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=credentials, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            if data.get('success'):
                print("✅ Registration successful!")
                return True
            else:
                print("❌ Registration failed:", data.get('error'))
        else:
            print("❌ HTTP Error:", response.status_code)
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return False

if __name__ == "__main__":
    print("🧪 Testing Authentication Endpoints")
    print("=" * 40)
    
    # Test login
    test_login()
    
    # Test registration  
    test_register()