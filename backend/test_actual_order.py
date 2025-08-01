#!/usr/bin/env python3
"""
Test actual order to see the real error
"""

import requests
import json
from coinbase_jwt import get_coinbase_headers
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

def test_actual_order_error():
    """Make a real order request to see the exact error"""
    print("🧪 Testing Actual Order Request")
    print("=" * 40)
    
    order_body = {
        'client_order_id': 'debug-order-123456',
        'product_id': 'BTC-USD',
        'side': 'BUY',
        'order_configuration': {
            'market_market_ioc': {
                'quote_size': '1.00'  # $1 order
            }
        }
    }
    
    body_json = json.dumps(order_body)
    headers = get_coinbase_headers('POST', '/api/v3/brokerage/orders', body_json)
    url = 'https://api.coinbase.com/api/v3/brokerage/orders'
    
    print(f"Order: {json.dumps(order_body, indent=2)}")
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print()
    
    try:
        print("Making API request to test error response...")
        
        response = requests.post(url, headers=headers, data=body_json, timeout=30)
        
        print(f"\n📊 Response Details:")
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Body: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Order placed successfully!")
                success_response = data.get('success_response', {})
                print(f"Order ID: {success_response.get('order_id')}")
            else:
                print("❌ Order failed (success=false)")
                error_response = data.get('error_response', {})
                print(f"Error details: {json.dumps(error_response, indent=2)}")
        elif response.status_code == 401:
            print("❌ 401 Unauthorized - JWT authentication failed")
            try:
                error_data = response.json()
                print(f"Error details: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Raw response: {response.text}")
        elif response.status_code == 400:
            print("❌ 400 Bad Request - Order validation failed")
            try:
                error_data = response.json()
                print(f"Error details: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Raw response: {response.text}")
        else:
            print(f"❌ HTTP {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_actual_order_error()