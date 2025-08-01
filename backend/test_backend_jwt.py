#!/usr/bin/env python3
"""
Test backend JWT method directly
"""

import sys
import os
import json

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import TradingBotAdapter
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

def test_backend_jwt_method():
    """Test the backend JWT method directly"""
    print("🔍 Testing Backend JWT Method")
    print("=" * 40)
    
    try:
        # Create bot adapter instance
        bot_adapter = TradingBotAdapter()
        
        # Test the JWT method directly
        print("Testing _execute_advanced_trade_jwt method...")
        
        result = bot_adapter._execute_advanced_trade_jwt(
            action='buy',
            symbol='BTC-USDC',  # This gets mapped to BTC-USD
            amount_type='usd',
            amount=1  # $1 test
        )
        
        print(f"Result: {json.dumps(result, indent=2)}")
        
        if result['success']:
            print("✅ Backend JWT method works!")
        else:
            print(f"❌ Backend JWT method failed: {result['error']}")
            
    except Exception as e:
        print(f"❌ Error testing backend method: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_backend_jwt_method()