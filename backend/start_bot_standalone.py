#!/usr/bin/env python3
"""
Standalone bot starter - ensures bot is running with logging
"""

import sys
import os
import json
import logging
from datetime import datetime

# Configure logging to file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_activity.log'),
        logging.StreamHandler()
    ]
)

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def ensure_bot_running():
    """Ensure the bot is running with the persisted strategy"""
    try:
        # Import after path is set
        from app import auto_trading_engine
        
        logging.info("=" * 60)
        logging.info("STARTING BOT MONITOR")
        
        # Check current state
        logging.info(f"Current Status: {auto_trading_engine.state.status}")
        logging.info(f"Current Strategy: {auto_trading_engine.state.active_strategy}")
        
        # If no strategy, set one
        if not auto_trading_engine.state.active_strategy:
            logging.info("No strategy set, setting trend_following")
            auto_trading_engine.set_strategy('trend_following')
        
        # Start if not running
        if auto_trading_engine.state.status != 'running':
            logging.info("Bot not running, starting...")
            success = auto_trading_engine.start()
            logging.info(f"Start result: {success}")
        else:
            logging.info("Bot is already running")
            
        # Check if thread is alive
        if auto_trading_engine.running_thread and auto_trading_engine.running_thread.is_alive():
            logging.info("✅ Bot thread is ACTIVE")
        else:
            logging.info("❌ Bot thread is NOT active - restarting")
            auto_trading_engine.start()
        
        # Log current stats
        logging.info(f"Price History: {len(auto_trading_engine.price_history)} points")
        logging.info(f"Trade History: {len(auto_trading_engine.trade_history)} trades")
        
        # Force a price fetch to test
        logging.info("Testing price fetch...")
        price = auto_trading_engine.get_current_price()
        if price:
            logging.info(f"✅ Price fetch successful: ${price:,.2f}")
        else:
            logging.info("❌ Price fetch failed")
            
        logging.info("=" * 60)
        logging.info("Bot is now running. Check bot_activity.log for updates.")
        logging.info("The bot will:")
        logging.info("  1. Check prices every 30 seconds")
        logging.info("  2. Generate signals after 5 price points")
        logging.info("  3. Execute trades when confidence > 60%")
        
        return True
        
    except Exception as e:
        logging.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    ensure_bot_running()