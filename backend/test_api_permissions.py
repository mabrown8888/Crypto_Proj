#!/usr/bin/env python3
"""
Test Coinbase API key permissions and trading capabilities
"""

import requests
import json
from coinbase_jwt import get_coinbase_headers
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

def test_api_permissions():
    """Test various API endpoints to check permissions"""
    print("🔍 Testing Coinbase API Key Permissions")
    print("=" * 50)
    
    # Test 1: Accounts (should work)
    print("\n1. Testing Accounts Endpoint...")
    try:
        path = '/api/v3/brokerage/accounts'
        headers = get_coinbase_headers('GET', path)
        url = f'https://api.coinbase.com{path}'
        
        response = requests.get(url, headers=headers, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            accounts = data.get('accounts', [])
            print(f"   ✅ Success: {len(accounts)} accounts found")
            for acc in accounts:
                print(f"      - {acc.get('currency')}: {acc.get('available_balance', {}).get('value', '0')}")
        else:
            print(f"   ❌ Failed: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: Products (check available trading pairs)
    print("\n2. Testing Products Endpoint...")
    try:
        path = '/api/v3/brokerage/products'
        headers = get_coinbase_headers('GET', path)
        url = f'https://api.coinbase.com{path}'
        
        response = requests.get(url, headers=headers, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            products = data.get('products', [])
            btc_products = [p for p in products if 'BTC' in p.get('product_id', '')]
            print(f"   ✅ Success: {len(products)} products, {len(btc_products)} BTC pairs")
            
            # Show available BTC trading pairs
            print("   Available BTC pairs:")
            for product in btc_products[:10]:  # Show first 10
                product_id = product.get('product_id')
                status = product.get('status')
                trading_disabled = product.get('trading_disabled', False)
                print(f"      - {product_id}: {status}, Trading: {'❌' if trading_disabled else '✅'}")
        else:
            print(f"   ❌ Failed: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: Check if we can place a test order (preview mode)
    print("\n3. Testing Order Preview...")
    try:
        # Small test order - this shouldn't actually execute
        order_body = {
            'client_order_id': 'test-preview-only',
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
        
        print(f"   Test order: {order_body}")
        print("   ⚠️  NOTE: This is a REAL order test - only do this if you want to buy $1 of BTC!")
        
        # For safety, let's just check the headers are working
        print(f"   Headers generated successfully: {bool(headers.get('Authorization'))}")
        print("   Skipping actual order for safety")
        
    except Exception as e:
        print(f"   ❌ Error generating order: {e}")
    
    # Test 4: Check portfolios
    print("\n4. Testing Portfolios Endpoint...")
    try:
        path = '/api/v3/brokerage/portfolios'
        headers = get_coinbase_headers('GET', path)
        url = f'https://api.coinbase.com{path}'
        
        response = requests.get(url, headers=headers, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            portfolios = data.get('portfolios', [])
            print(f"   ✅ Success: {len(portfolios)} portfolios found")
            for portfolio in portfolios:
                name = portfolio.get('name', 'Unknown')
                uuid = portfolio.get('uuid', '')[:8]
                print(f"      - {name} ({uuid}...)")
        else:
            print(f"   ❌ Failed: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_api_permissions()