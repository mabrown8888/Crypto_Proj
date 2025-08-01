#!/usr/bin/env python3
"""
Test JWT format and compare with working example
"""

import requests
import json
import jwt as pyjwt
from coinbase_jwt import get_coinbase_headers, CoinbaseJWTGenerator
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

def decode_jwt_payload(token):
    """Decode JWT payload without verification for debugging"""
    try:
        # Remove "Bearer " prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        
        # Decode without verification (for debugging only)
        header = pyjwt.get_unverified_header(token)
        payload = pyjwt.decode(token, options={"verify_signature": False})
        
        return header, payload
    except Exception as e:
        print(f"Error decoding JWT: {e}")
        return None, None

def test_jwt_generation():
    """Test JWT generation and format"""
    print("🔍 Testing JWT Generation")
    print("=" * 40)
    
    try:
        generator = CoinbaseJWTGenerator()
        
        # Test GET request (this worked before)
        print("1. Testing GET /api/v3/brokerage/accounts")
        get_headers = get_coinbase_headers('GET', '/api/v3/brokerage/accounts')
        get_token = get_headers['Authorization'].replace('Bearer ', '')
        
        get_header, get_payload = decode_jwt_payload(get_token)
        print(f"   Header: {json.dumps(get_header, indent=2)}")
        print(f"   Payload: {json.dumps(get_payload, indent=2)}")
        
        # Test with GET request to verify it still works
        print("\n2. Testing GET request to verify JWT works...")
        url = 'https://api.coinbase.com/api/v3/brokerage/accounts'
        response = requests.get(url, headers=get_headers, timeout=30)
        print(f"   GET Response: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ GET JWT works correctly")
        else:
            print(f"   ❌ GET JWT failed: {response.text}")
        
        # Test POST request (this is failing)
        print("\n3. Testing POST /api/v3/brokerage/orders")
        order_body = {
            'client_order_id': 'test-jwt-debug',
            'product_id': 'BTC-USD',
            'side': 'BUY',
            'order_configuration': {
                'market_market_ioc': {
                    'quote_size': '1.00'
                }
            }
        }
        body_json = json.dumps(order_body)
        
        post_headers = get_coinbase_headers('POST', '/api/v3/brokerage/orders', body_json)
        post_token = post_headers['Authorization'].replace('Bearer ', '')
        
        post_header, post_payload = decode_jwt_payload(post_token)
        print(f"   Header: {json.dumps(post_header, indent=2)}")
        print(f"   Payload: {json.dumps(post_payload, indent=2)}")
        
        print(f"\n4. Comparing GET vs POST JWT:")
        print(f"   GET URI:  {get_payload.get('uri')}")
        print(f"   POST URI: {post_payload.get('uri')}")
        
        # Check if they have the same basic structure
        get_keys = set(get_payload.keys())
        post_keys = set(post_payload.keys())
        print(f"   GET keys:  {sorted(get_keys)}")
        print(f"   POST keys: {sorted(post_keys)}")
        
        if get_keys == post_keys:
            print("   ✅ JWT payload structure matches")
        else:
            print(f"   ❌ JWT payload structure differs: {get_keys.symmetric_difference(post_keys)}")
            
    except Exception as e:
        print(f"❌ Error testing JWT: {e}")

def test_minimal_post():
    """Test minimal POST to see exact error"""
    print("\n🧪 Testing Minimal POST Order")
    print("=" * 40)
    
    try:
        order_body = {
            'client_order_id': 'minimal-test-123',
            'product_id': 'BTC-USD',
            'side': 'BUY',
            'order_configuration': {
                'market_market_ioc': {
                    'quote_size': '1.00'
                }
            }
        }
        
        body_json = json.dumps(order_body)
        headers = get_coinbase_headers('POST', '/api/v3/brokerage/orders', body_json)
        url = 'https://api.coinbase.com/api/v3/brokerage/orders'
        
        print(f"Order: {json.dumps(order_body, indent=2)}")
        print(f"Headers: {headers}")
        
        print("\n⚠️  Making REAL API call - this will place a $1 order!")
        # Commented out for safety - uncomment if you want to test
        # response = requests.post(url, headers=headers, data=body_json, timeout=30)
        # print(f"Response: {response.status_code} - {response.text}")
        print("Skipped actual order for safety")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_jwt_generation()
    test_minimal_post()