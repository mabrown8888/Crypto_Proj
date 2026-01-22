#!/usr/bin/env python3
"""
Debug why trades aren't executing
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import auto_trading_engine
from ai_trading_strategies import TradingSignal, SignalStrength
from datetime import datetime

print("🔍 DEBUGGING TRADE EXECUTION")
print("=" * 50)

# Check current state
print(f"Bot Status: {auto_trading_engine.state.status}")
print(f"Active Strategy: {auto_trading_engine.state.active_strategy}")
print(f"Price History: {len(auto_trading_engine.price_history)} points")

# Get current signal
if auto_trading_engine.state.last_signal:
    signal = auto_trading_engine.state.last_signal
    print(f"\n📊 Current Signal:")
    print(f"   Action: {signal.action.value}")
    print(f"   Confidence: {signal.confidence:.1%}")
    print(f"   Amount: ${signal.amount_usd}")
    print(f"   Price: ${signal.price:.2f}")
    
    # Test safety check
    print(f"\n🛡️ Safety Check:")
    can_trade, reason = auto_trading_engine.can_trade_safely(signal)
    print(f"   Can Trade: {can_trade}")
    print(f"   Reason: {reason}")
    
    # Check balances
    try:
        balances = auto_trading_engine.bot_adapter.get_account_balances_jwt()
        print(f"\n💰 Account Balances:")
        for balance in balances:
            if balance['currency'] in ['USD', 'BTC']:
                print(f"   {balance['currency']}: {balance['available']:.8f}")
                
        # Calculate if we have enough for the trade
        usd_balance = next((b['available'] for b in balances if b['currency'] == 'USD'), 0)
        print(f"\n🔢 Trade Check:")
        print(f"   Required: ${signal.amount_usd}")
        print(f"   Available: ${usd_balance:.2f}")
        print(f"   Sufficient: {usd_balance >= signal.amount_usd}")
        
    except Exception as e:
        print(f"❌ Error checking balances: {e}")
    
    # Check if action is in the right list
    buy_actions = [SignalStrength.BUY, SignalStrength.STRONG_BUY]
    sell_actions = [SignalStrength.SELL, SignalStrength.STRONG_SELL]
    
    print(f"\n🎯 Signal Analysis:")
    print(f"   Signal Action: {signal.action}")
    print(f"   Is BUY action: {signal.action in buy_actions}")
    print(f"   Is SELL action: {signal.action in sell_actions}")
    print(f"   Should Execute: {signal.action in buy_actions or signal.action in sell_actions}")
    
    # Check confidence threshold
    print(f"\n📏 Confidence Check:")
    print(f"   Signal Confidence: {signal.confidence:.1%}")
    print(f"   Min Threshold: {auto_trading_engine.min_confidence:.1%}")
    print(f"   Above Threshold: {signal.confidence >= auto_trading_engine.min_confidence}")
    
else:
    print("❌ No current signal")

print("\n" + "=" * 50)
print("🔍 If all checks pass but no trade, check Flask logs for errors")