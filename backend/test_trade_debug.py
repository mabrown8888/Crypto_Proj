#!/usr/bin/env python3
"""
Debug the execute-trade endpoint
"""

import requests
import json

def get_auth_token():
    """Get authentication token"""
    login_url = "http://localhost:5001/api/auth/login"
    credentials = {
        "username": "admin",
        "password": "admin123"
    }
    
    response = requests.post(login_url, json=credentials)
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            return data['token']
    return None

def test_execute_trade():
    """Test execute-trade endpoint with debug info"""
    print("Testing execute-trade endpoint...")
    
    # Get auth token
    token = get_auth_token()
    if not token:
        print("❌ Failed to get auth token")
        return False
    
    print(f"✅ Got auth token: {token[:50]}...")
    
    # Test trade request
    trade_url = "http://localhost:5001/api/execute-trade"
    
    # This matches what your frontend sends
    trade_request = {
        "action": "buy",
        "symbol": "BTC-USDC", 
        "amountType": "usd",
        "amount": 25
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    print(f"Making request to: {trade_url}")
    print(f"Request body: {json.dumps(trade_request, indent=2)}")
    print(f"Headers: {headers}")
    
    try:
        response = requests.post(trade_url, json=trade_request, headers=headers)
        
        print(f"\nResponse status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Trade executed successfully!")
                return True
            else:
                print(f"❌ Trade failed: {data.get('error')}")
        elif response.status_code == 400:
            try:
                error_data = response.json()
                print(f"❌ 400 Bad Request: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"❌ 400 Bad Request: {response.text}")
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
    
    return False

def test_account_balances():
    """Test account balances to make sure auth is working"""
    print("\nTesting account balances for comparison...")
    
    token = get_auth_token()
    if not token:
        print("❌ Failed to get auth token")
        return
    
    balance_url = "http://localhost:5001/api/account-balances"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.get(balance_url, headers=headers)
        print(f"Balance endpoint status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            balances = data.get('balances', [])
            print(f"✅ Balances working: {len(balances)} accounts")
            for balance in balances:
                print(f"  - {balance['currency']}: {balance['available']}")
        else:
            print(f"❌ Balance request failed: {response.text}")
    except Exception as e:
        print(f"❌ Balance request error: {e}")

if __name__ == "__main__":
    print("🔍 Debugging Execute-Trade Endpoint")
    print("=" * 50)
    
    # Test account balances first (should work)
    test_account_balances()
    
    # Test execute trade (currently failing)
    test_execute_trade()