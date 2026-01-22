#!/usr/bin/env python3
"""
Real-time bot monitoring script
Shows what the bot is doing right now
"""

import sys
import os
import json
import time
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def monitor_bot():
    """Monitor bot activity in real-time"""
    print("🤖 REAL-TIME BOT MONITOR")
    print("=" * 60)
    print("Press Ctrl+C to stop monitoring\n")
    
    try:
        # Check if state file exists
        if os.path.exists('bot_state.json'):
            with open('bot_state.json', 'r') as f:
                state = json.load(f)
                print(f"📊 Persisted State:")
                print(f"   Status: {state['status']}")
                print(f"   Strategy: {state['active_strategy']}")
                print(f"   Total Trades: {state['total_trades']}")
                print(f"   Last Updated: {state['last_updated']}")
        
        # Import here to avoid initialization issues
        from app import auto_trading_engine
        
        print(f"\n🔍 Live Engine State:")
        print(f"   Status: {auto_trading_engine.state.status}")
        print(f"   Strategy: {auto_trading_engine.state.active_strategy}")
        print(f"   Trades Today: {auto_trading_engine.state.trades_today}")
        
        # Check thread
        if auto_trading_engine.running_thread and auto_trading_engine.running_thread.is_alive():
            print(f"   Thread: ✅ RUNNING")
        else:
            print(f"   Thread: ❌ NOT RUNNING")
        
        # Price history
        price_count = len(auto_trading_engine.price_history)
        print(f"\n📈 Market Data:")
        print(f"   Price Points: {price_count}")
        if price_count > 0:
            print(f"   Latest Price: ${auto_trading_engine.price_history[-1]:,.2f}")
            if price_count >= 5:
                avg = sum(auto_trading_engine.price_history[-5:]) / 5
                print(f"   5-Point Average: ${avg:,.2f}")
        
        # Last signal
        if auto_trading_engine.state.last_signal:
            signal = auto_trading_engine.state.last_signal
            print(f"\n🎯 Last Trading Signal:")
            print(f"   Action: {signal.action.value}")
            print(f"   Confidence: {signal.confidence:.1%}")
            print(f"   Reason: {signal.reason}")
            print(f"   Time: {signal.timestamp}")
        else:
            print(f"\n⏳ Waiting for signals...")
            print(f"   Need {max(0, 5 - price_count)} more price points")
        
        # Trade history
        if auto_trading_engine.trade_history:
            print(f"\n💰 Recent Trades:")
            for trade in auto_trading_engine.trade_history[-3:]:
                print(f"   {trade.timestamp}: {trade.action} ${trade.amount_usd} - {trade.status}")
        
        print("\n" + "=" * 60)
        print("📌 Bot Configuration:")
        print(f"   Check Interval: {auto_trading_engine.check_interval} seconds")
        print(f"   Min Confidence: {auto_trading_engine.min_confidence:.0%}")
        print(f"   Max Daily Loss: ${auto_trading_engine.max_daily_loss}")
        
        print("\n⚠️  IMPORTANT:")
        print("   - Bot needs 5+ price points to start generating signals")
        print("   - First signal expected after ~2.5 minutes")
        print("   - Trades execute when confidence > 60%")
        
        # Get current balances
        try:
            balances = auto_trading_engine.bot_adapter.get_account_balances_jwt()
            print(f"\n💼 Account Balances:")
            for balance in balances:
                if balance['currency'] in ['USD', 'BTC'] and balance['available'] > 0:
                    print(f"   {balance['currency']}: {balance['available']:.8f}")
        except:
            pass
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    monitor_bot()