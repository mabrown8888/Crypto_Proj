#!/usr/bin/env python3
"""
Test a tiny real order to see what error we get
"""

import requests
import json
from coinbase_jwt import get_coinbase_headers
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

def test_tiny_order():
    """Test a very small order to diagnose the exact error"""
    print("🧪 Testing Tiny Order ($1 BTC)")
    print("=" * 40)
    
    # Create a minimal order
    order_body = {
        'client_order_id': 'test-debug-123456789',
        'product_id': 'BTC-USD',  # Use BTC-USD instead of BTC-USDC
        'side': 'BUY',
        'order_configuration': {
            'market_market_ioc': {
                'quote_size': '1.00'  # $1 order
            }
        }
    }
    
    body_json = json.dumps(order_body)
    path = '/api/v3/brokerage/orders'
    headers = get_coinbase_headers('POST', path, body_json)
    url = f'https://api.coinbase.com{path}'
    
    print(f"Order details:")
    print(json.dumps(order_body, indent=2))
    print(f"\nMaking request to: {url}")
    
    try:
        response = requests.post(url, headers=headers, data=body_json, timeout=30)
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Order placed successfully!")
                success_response = data.get('success_response', {})
                print(f"Order ID: {success_response.get('order_id')}")
            else:
                print("❌ Order failed (success=false)")
                error_response = data.get('error_response', {})
                print(f"Error: {error_response}")
        else:
            print(f"❌ HTTP Error {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error details: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Raw error: {response.text}")
                
    except Exception as e:
        print(f"❌ Request failed: {e}")

def check_account_restrictions():
    """Check if there are any account restrictions"""
    print("\n🔍 Checking Account Details")
    print("=" * 40)
    
    # Get detailed account info
    path = '/api/v3/brokerage/accounts'
    headers = get_coinbase_headers('GET', path)
    url = f'https://api.coinbase.com{path}'
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            accounts = data.get('accounts', [])
            
            for account in accounts:
                currency = account.get('currency')
                available = float(account.get('available_balance', {}).get('value', '0'))
                hold = float(account.get('hold', {}).get('value', '0'))
                
                print(f"{currency} Account:")
                print(f"  Available: {available}")
                print(f"  Hold: {hold}")
                print(f"  Ready to trade: {'✅' if available > 0 else '❌'}")
                
                # Check if account has any restrictions
                restrictions = account.get('restrictions', [])
                if restrictions:
                    print(f"  ⚠️  Restrictions: {restrictions}")
                else:
                    print(f"  ✅ No restrictions")
                print()
        else:
            print(f"❌ Failed to get account details: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # First check account details
    check_account_restrictions()
    
    # Ask user if they want to test a real order
    print("\n⚠️  WARNING: The next test will place a REAL $1 BTC order!")
    print("This will spend $1 of your USD balance.")
    
    confirm = input("Do you want to proceed? (yes/no): ").lower().strip()
    
    if confirm == 'yes':
        test_tiny_order()
    else:
        print("Test cancelled. No orders placed.")