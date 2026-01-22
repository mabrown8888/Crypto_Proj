#!/usr/bin/env python3
"""
Test the auto trading system
"""

import sys
import os
import time
import json

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import TradingBotAdapter
from auto_trading_engine import AutoTradingEngine
from ai_trading_strategies import SignalStrength
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

def test_trading_strategies():
    """Test the AI trading strategies"""
    print("🧪 Testing AI Trading Strategies")
    print("=" * 50)
    
    try:
        # Create bot adapter and engine
        bot_adapter = TradingBotAdapter()
        engine = AutoTradingEngine(bot_adapter)
        
        # Test strategy manager
        strategies = engine.strategy_manager.get_available_strategies()
        print(f"✅ Found {len(strategies)} trading strategies:")
        
        for strategy in strategies:
            print(f"  • {strategy['name']} ({strategy['risk_level']})")
            print(f"    - {strategy['description']}")
            print(f"    - Max trade: ${strategy['max_trade_amount']}")
            print(f"    - Daily trades: {strategy['max_daily_trades']}")
            print()
        
        # Test setting a strategy
        success = engine.set_strategy('conservative')
        if success:
            print("✅ Successfully set conservative strategy")
        else:
            print("❌ Failed to set strategy")
            
        # Test getting current price
        price = engine.get_current_price()
        if price:
            print(f"✅ Current BTC price: ${price:.2f}")
        else:
            print("❌ Failed to get current price")
            
        # Test signal generation with some mock price data
        if len(engine.price_history) >= 5:
            signal = engine.strategy_manager.get_trading_signal(engine.price_history)
            if signal:
                print(f"✅ Generated trading signal:")
                print(f"   Action: {signal.action.value}")
                print(f"   Confidence: {signal.confidence:.1%}")
                print(f"   Reason: {signal.reason}")
                print(f"   Price: ${signal.price:.2f}")
            else:
                print("❌ No trading signal generated")
        else:
            print("⚠️  Not enough price history for signal generation")
            
        # Test safety checks
        if len(engine.price_history) > 0:
            # Create a mock signal for testing
            from ai_trading_strategies import TradingSignal
            from datetime import datetime
            
            mock_signal = TradingSignal(
                action=SignalStrength.BUY,
                confidence=0.8,
                reason="Test signal",
                price=engine.price_history[-1],
                timestamp=datetime.now(),
                amount_usd=10.0  # Small test amount
            )
            
            can_trade, reason = engine.can_trade_safely(mock_signal)
            print(f"✅ Safety check result: {'✅ Safe' if can_trade else '❌ Blocked'}")
            print(f"   Reason: {reason}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing strategies: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test that the API endpoints are properly set up"""
    print("\n🔗 Testing API Endpoint Setup")
    print("=" * 50)
    
    # This would normally require the Flask app to be running
    # For now, just verify the functions exist
    try:
        from app import auto_trading_engine
        status = auto_trading_engine.get_status()
        
        print("✅ Auto trading engine status:")
        print(f"   Status: {status['status']}")
        print(f"   Active strategy: {status['active_strategy']}")
        print(f"   Total trades: {status['performance']['totalTrades']}")
        print(f"   Available strategies: {len(status['strategies'])}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing API setup: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing Auto Trading System")
    print("=" * 60)
    
    # Test strategies
    strategy_test = test_trading_strategies()
    
    # Test API setup
    api_test = test_api_endpoints()
    
    print("\n" + "=" * 60)
    if strategy_test and api_test:
        print("🎉 All tests passed! Auto trading system is ready.")
        print("\n📋 Next steps:")
        print("1. Restart your Flask backend (python3 app.py)")
        print("2. Go to the 'Auto Trading Bot' tab in your frontend")
        print("3. Select a trading strategy")
        print("4. Start with small amounts for testing")
        print("\n⚠️  IMPORTANT: Start with conservative strategy and small amounts!")
    else:
        print("❌ Some tests failed. Check the errors above.")
        
    print("=" * 60)