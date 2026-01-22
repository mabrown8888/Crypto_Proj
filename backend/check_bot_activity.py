#!/usr/bin/env python3
"""
Check if the auto trading bot is actively running
"""

import sys
import os
import json

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import auto_trading_engine
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

def check_bot_activity():
    """Check current bot activity and status"""
    print("🤖 Auto Trading Bot Activity Check")
    print("=" * 50)
    
    try:
        # Get full status
        status = auto_trading_engine.get_status()
        
        print(f"Bot Status: {status['status']}")
        print(f"Active Strategy: {status['active_strategy']}")
        print(f"Total Trades Today: {status['performance']['totalTrades']}")
        print(f"Today's P&L: ${status['performance']['todayPnL']:.2f}")
        
        # Check current signal
        signal = status.get('current_signal')
        if signal:
            print(f"\n📊 Current Trading Signal:")
            print(f"   Action: {signal['action']}")
            print(f"   Confidence: {signal['confidence'] * 100:.1f}%")
            print(f"   Reason: {signal['reason']}")
            print(f"   Price: ${signal['price']:.2f}")
            print(f"   Time: {signal['timestamp']}")
        else:
            print("\n⏳ No trading signal yet (bot may still be gathering price data)")
        
        # Check price history
        price_count = len(auto_trading_engine.price_history)
        print(f"\n📈 Price History: {price_count} data points")
        if price_count > 0:
            print(f"   Latest Price: ${auto_trading_engine.price_history[-1]:.2f}")
            
        # Check if bot thread is alive
        if auto_trading_engine.running_thread and auto_trading_engine.running_thread.is_alive():
            print("\n✅ Bot thread is ACTIVE and running!")
        else:
            print("\n❌ Bot thread is not running")
            
        # Show next action
        if status['status'] == 'running':
            print(f"\n🔄 Bot is checking market every {auto_trading_engine.check_interval} seconds")
            print("📌 Will execute trades when confidence > 60% on BUY/SELL signals")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking bot: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    check_bot_activity()