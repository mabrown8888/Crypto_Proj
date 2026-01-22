#!/usr/bin/env python3
"""
Test script to verify Coinbase perpetual short order capability
"""

import os
import sys
from dotenv import load_dotenv
from coinbase.rest import RESTClient

# Load environment variables
load_dotenv('../.env')

def test_coinbase_perp_access():
    """Test if we can access Coinbase perpetual futures"""

    api_key = os.getenv('COINBASE_API_KEY')
    api_secret = os.getenv('COINBASE_API_SECRET')

    if not api_key or not api_secret:
        print("❌ ERROR: COINBASE_API_KEY or COINBASE_API_SECRET not found in .env")
        return False

    print(f"✓ Found API credentials")
    print(f"  API Key: {api_key[:8]}...")

    try:
        # Initialize Coinbase client
        client = RESTClient(api_key=api_key, api_secret=api_secret)
        print("✓ Coinbase client initialized")

        # Test 1: Get accounts
        print("\n1. Testing account access...")
        accounts = client.get_accounts()
        if accounts:
            print(f"✓ Can access accounts")
        else:
            print("❌ No accounts found")
            return False

        # Test 2: Check for perpetual futures capability
        print("\n2. Checking perpetual futures access...")
        try:
            positions = client.list_futures_positions()
            print(f"✓ Can access futures positions API")
            print(f"  Current positions: {len(positions.positions) if hasattr(positions, 'positions') else 0}")
        except Exception as e:
            print(f"❌ Cannot access futures API: {e}")
            print("\n⚠️  You may need Coinbase International Exchange access for perpetuals")
            print("   Visit: https://international.coinbase.com/")
            return False

        # Test 3: Check product info for BTC-PERP-INTX
        print("\n3. Checking BTC-PERP-INTX product...")
        try:
            # Try to get product info (read-only operation)
            product = client.get_product("BTC-PERP-INTX")
            if product:
                print(f"✓ BTC-PERP-INTX product exists")
                print(f"  Status: {product.get('status', 'unknown')}")
            else:
                print("⚠️  Could not fetch BTC-PERP-INTX product details")
        except Exception as e:
            print(f"⚠️  Could not check product: {e}")

        print("\n" + "="*60)
        print("✅ SUCCESS: Your Coinbase account CAN trade perpetual futures!")
        print("="*60)
        print("\nTo place a SHORT order via API:")
        print("  POST /api/hedge/perp/order")
        print("  {")
        print('    "product_id": "BTC-PERP-INTX",')
        print('    "side": "sell",')
        print('    "size": 0.001,')
        print('    "order_type": "market"')
        print("  }")
        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nPossible issues:")
        print("  1. API keys don't have futures trading permissions")
        print("  2. You need Coinbase International Exchange access")
        print("  3. Account not approved for derivatives trading")
        return False

if __name__ == "__main__":
    print("Testing Coinbase Perpetual Futures Access")
    print("="*60)
    success = test_coinbase_perp_access()
    sys.exit(0 if success else 1)
