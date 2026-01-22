#!/usr/bin/env python3
"""
Test trade execution to see what's happening
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import auto_trading_engine

print("🧪 TESTING TRADE EXECUTION")
print("=" * 50)

# Test a small trade execution directly
try:
    bot_adapter = auto_trading_engine.bot_adapter
    
    print("📊 Testing $1 BTC buy order...")
    result = bot_adapter._execute_advanced_trade_jwt(
        action='buy',
        symbol='BTC-USD',
        amount_type='usd',
        amount=1.0  # Test with $1
    )
    
    print(f"Result: {result}")
    print(f"Success: {result.get('success', False)}")
    print(f"Error: {result.get('error', 'None')}")
    print(f"Order ID: {result.get('order_id', 'None')}")
    
    if result.get('success'):
        print("✅ Trade execution API is working!")
    else:
        print("❌ Trade execution API is failing")
        print(f"Reason: {result.get('error')}")
        
except Exception as e:
    print(f"❌ Exception during test: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("🔍 This will help identify why trades aren't reaching Coinbase")