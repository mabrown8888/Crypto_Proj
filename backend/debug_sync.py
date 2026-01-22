#!/usr/bin/env python3
"""
Debug script to test position syncing
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from coinbase_adapter import CoinbaseAdapter

# Initialize adapter
adapter = CoinbaseAdapter()

print("=" * 80)
print("FETCHING ALL COINBASE ACCOUNTS")
print("=" * 80)

try:
    accounts = adapter.coinbase_client.get_accounts()
    print(f"\nTotal accounts: {len(accounts.accounts)}\n")

    for account in accounts.accounts:
        currency = getattr(account, 'currency', 'UNKNOWN')
        available = float(getattr(account.available_balance, 'value', 0))

        if available > 0.00001:
            print(f"✅ {currency}: {available:.8f}")

            # Test symbol conversion
            symbol = f"{currency}-USD"
            print(f"   Would map to: {symbol}")
        else:
            print(f"⚪ {currency}: {available:.8f} (empty)")

    print("\n" + "=" * 80)
    print("SUPPORTED CURRENCIES IN BOT:")
    print("=" * 80)
    supported = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOGE-USD', 'AVAX-USD', 'MATIC-USD', 'LINK-USD']
    for symbol in supported:
        print(f"  - {symbol}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
