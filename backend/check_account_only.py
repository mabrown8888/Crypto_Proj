#!/usr/bin/env python3
"""
Check account details only - no orders
"""

import requests
import json
from coinbase_jwt import get_coinbase_headers
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

def check_account_details():
    """Check detailed account information"""
    print("🔍 Checking Account Details")
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
            
            print(f"Found {len(accounts)} accounts:")
            print()
            
            for account in accounts:
                currency = account.get('currency')
                available = float(account.get('available_balance', {}).get('value', '0'))
                hold = float(account.get('hold', {}).get('value', '0'))
                uuid = account.get('uuid', '')
                
                print(f"📊 {currency} Account ({uuid[:8]}...):")
                print(f"   Available Balance: {available}")
                print(f"   Hold Balance: {hold}")
                print(f"   Total: {available + hold}")
                print(f"   Ready to trade: {'✅' if available > 0 else '❌'}")
                
                # Check account-specific details
                account_type = account.get('type', 'Unknown')
                active = account.get('active', False)
                default = account.get('default', False)
                
                print(f"   Type: {account_type}")
                print(f"   Active: {'✅' if active else '❌'}")
                print(f"   Default: {'✅' if default else '❌'}")
                
                # Check for any restrictions or special flags
                for key, value in account.items():
                    if key not in ['uuid', 'currency', 'available_balance', 'hold', 'type', 'active', 'default'] and value:
                        print(f"   {key}: {value}")
                
                print()
                
        else:
            print(f"❌ Failed to get account details: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

def check_trading_permissions():
    """Check if we can access trading-related endpoints"""
    print("🔍 Checking Trading Permissions")
    print("=" * 40)
    
    # Try to get orders (should work even if empty)
    try:
        path = '/api/v3/brokerage/orders/historical/batch'
        headers = get_coinbase_headers('GET', path)
        url = f'https://api.coinbase.com{path}'
        
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Orders endpoint status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Can access orders endpoint")
        else:
            print(f"❌ Orders endpoint failed: {response.text}")
    except Exception as e:
        print(f"❌ Orders endpoint error: {e}")
    
    # Try to get fills (executed trades)
    try:
        path = '/api/v3/brokerage/orders/historical/fills'
        headers = get_coinbase_headers('GET', path)
        url = f'https://api.coinbase.com{path}'
        
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Fills endpoint status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Can access fills endpoint")
        else:
            print(f"❌ Fills endpoint failed: {response.text}")
    except Exception as e:
        print(f"❌ Fills endpoint error: {e}")

if __name__ == "__main__":
    check_account_details()
    check_trading_permissions()