#!/usr/bin/env python3
"""
Test CORS fix for authenticated API calls
"""

import requests
import json

def test_authenticated_request():
    """Test authenticated API call with Authorization header"""
    print("Testing authenticated API call...")
    
    # First login to get token
    login_url = "http://localhost:5001/api/auth/login"
    credentials = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        # Login
        login_response = requests.post(login_url, json=credentials)
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.status_code}")
            return False
        
        token_data = login_response.json()
        if not token_data.get('success'):
            print(f"❌ Login failed: {token_data.get('error')}")
            return False
        
        token = token_data['token']
        print(f"✅ Login successful, got token: {token[:50]}...")
        
        # Test authenticated endpoint
        balance_url = "http://localhost:5001/api/account-balances"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        print(f"Testing authenticated request to: {balance_url}")
        print(f"Headers: {headers}")
        
        balance_response = requests.get(balance_url, headers=headers)
        
        print(f"Response status: {balance_response.status_code}")
        print(f"Response: {balance_response.text}")
        
        if balance_response.status_code == 200:
            data = balance_response.json()
            if data.get('success'):
                balances = data.get('balances', [])
                print(f"✅ Authenticated request successful! Got {len(balances)} balances")
                for balance in balances:
                    currency = balance.get('currency')
                    available = balance.get('available', 0)
                    print(f"  - {currency}: {available}")
                return True
            else:
                print(f"❌ API error: {data.get('error')}")
        else:
            print(f"❌ HTTP error: {balance_response.status_code}")
            print(f"Response headers: {balance_response.headers}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return False

if __name__ == "__main__":
    print("🧪 Testing CORS Fix for Authenticated Requests")
    print("=" * 50)
    
    success = test_authenticated_request()
    
    if success:
        print("\n✅ CORS fix successful! Frontend should now work.")
    else:
        print("\n❌ CORS fix failed. Check server logs.")