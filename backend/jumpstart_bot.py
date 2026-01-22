#!/usr/bin/env python3
"""
Jump-start the bot with some initial price data
So you don't have to wait for it to collect
"""

import sys
import os
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import auto_trading_engine

print("🚀 Jump-starting bot with price data...")

# Add some recent price history to get started quickly
if len(auto_trading_engine.price_history) < 10:
    # Simulate recent price movements around current price
    base_price = 113000
    simulated_prices = [
        base_price - 200,  # Small dip
        base_price - 150,
        base_price - 100,
        base_price - 50,
        base_price,
        base_price + 30,
        base_price + 20,
        base_price - 10,
        base_price - 5,
        base_price + 10
    ]
    
    for price in simulated_prices:
        if len(auto_trading_engine.price_history) < 10:
            auto_trading_engine.price_history.append(price)
    
    print(f"✅ Added price history: {len(auto_trading_engine.price_history)} points")

# Now get a fresh price
current_price = auto_trading_engine.get_current_price()
if current_price:
    print(f"📊 Current BTC price: ${current_price:,.2f}")

# Generate a signal
if len(auto_trading_engine.price_history) >= 10:
    signal = auto_trading_engine.strategy_manager.get_trading_signal(auto_trading_engine.price_history)
    if signal:
        print(f"\n🎯 Trading Signal Generated:")
        print(f"   Action: {signal.action.value}")
        print(f"   Confidence: {signal.confidence:.1%}")
        print(f"   Reason: {signal.reason}")
        auto_trading_engine.state.last_signal = signal
        
print("\n✅ Bot is ready to trade!")
print("Check your browser console for updates...")