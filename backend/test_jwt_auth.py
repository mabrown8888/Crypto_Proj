#!/usr/bin/env python3
"""
Test script for Coinbase JWT authentication
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv
from coinbase_jwt import get_coinbase_headers

# Load environment variables from parent directory
load_dotenv('../.env')

def test_jwt_accounts():
    """Test JWT authentication with accounts endpoint"""
    try:
        print("Testing JWT authentication with Coinbase API...")
        
        # Test accounts endpoint
        path = '/api/v3/brokerage/accounts'
        headers = get_coinbase_headers('GET', path)
        url = f'https://api.coinbase.com{path}'
        
        print(f"Making request to: {url}")
        print(f"Headers: {headers}")
        
        response = requests.get(url, headers=headers, timeout=30)
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {response.headers}")
        
        if response.status_code == 200:
            data = response.json()
            accounts = data.get('accounts', [])
            print(f"✅ Success! Retrieved {len(accounts)} accounts")
            
            for account in accounts[:3]:  # Show first 3 accounts
                currency = account.get('currency')
                balance = account.get('available_balance', {}).get('value', '0')
                print(f"  - {currency}: {balance}")
            
            return True
        else:
            print(f"❌ Failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_jwt_order_preview():
    """Test JWT authentication with a small order preview"""
    try:
        print("\nTesting order preview...")
        
        # Small test order body
        order_body = {
            'client_order_id': 'test-order-preview-123',
            'product_id': 'BTC-USD',
            'side': 'BUY',
            'order_configuration': {
                'market_market_ioc': {
                    'quote_size': '1.00'  # $1 test order
                }
            }
        }
        
        body_json = json.dumps(order_body)
        path = '/api/v3/brokerage/orders'
        headers = get_coinbase_headers('POST', path, body_json)
        url = f'https://api.coinbase.com{path}'
        
        print(f"Test order body: {order_body}")
        
        # NOTE: This will create a real order! Only run if you want to test with real money
        print("⚠️  WARNING: This would create a real $1 BTC order!")
        print("⚠️  Skipping actual order creation for safety")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in order preview: {e}")
        return False

def main():
    """Run JWT authentication tests"""
    print("🚀 Starting Coinbase JWT Authentication Tests")
    print("=" * 50)
    
    # Check environment variables
    api_key = os.getenv('COINBASE_API_KEY')
    api_secret = os.getenv('COINBASE_API_SECRET')
    
    if not api_key or not api_secret:
        print("❌ Missing COINBASE_API_KEY or COINBASE_API_SECRET environment variables")
        return False
    
    print(f"✅ API Key: {api_key[:50]}...")
    print(f"✅ API Secret: Present ({len(api_secret)} characters)")
    
    # Test accounts
    if test_jwt_accounts():
        print("✅ JWT authentication working!")
    else:
        print("❌ JWT authentication failed")
        return False
    
    # Test order preview (without actually placing order)
    test_jwt_order_preview()
    
    print("\n" + "=" * 50)
    print("🎉 JWT Authentication tests completed!")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)