#!/usr/bin/env python3
"""
Automatic Trading Engine for AI-Powered Day Trading
"""

import time
import json
import logging
import threading
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import requests
from ai_trading_strategies import AITradingStrategyManager, SignalStrength, TradingSignal
from coinbase_jwt import get_coinbase_headers

@dataclass
class TradeRecord:
    id: str
    strategy: str
    action: str  # BUY/SELL
    amount_usd: float
    price: float
    timestamp: datetime
    order_id: str = None
    status: str = "PENDING"  # PENDING, EXECUTED, FAILED
    pnl: float = 0.0
    reason: str = ""

@dataclass
class BotState:
    status: str = "stopped"  # stopped, running, paused
    active_strategy: str = None
    trades_today: int = 0
    total_trades: int = 0
    total_pnl: float = 0.0
    today_pnl: float = 0.0
    profitable_trades: int = 0
    last_signal: TradingSignal = None
    last_price_check: datetime = None

class AutoTradingEngine:
    """Main automatic trading engine"""
    
    def __init__(self, trading_bot_adapter):
        self.bot_adapter = trading_bot_adapter
        self.strategy_manager = AITradingStrategyManager()
        self.state = BotState()
        self.price_history = []
        self.trade_history = []
        self.running_thread = None
        self.stop_event = threading.Event()
        
        # State persistence file
        self.state_file = 'bot_state.json'
        
        # Safety settings
        self.max_daily_loss = 100.0  # Max $100 loss per day
        self.max_total_risk = 500.0  # Max $500 at risk
        self.min_confidence = 0.5    # Lowered to 50% for more trades
        self.check_interval = 30     # Check every 30 seconds
        
        # Load persisted state
        self.load_state()
        
        logging.info("Auto Trading Engine initialized")
    
    def load_state(self):
        """Load persisted bot state"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state_data = json.load(f)
                    
                if 'active_strategy' in state_data and state_data['active_strategy']:
                    strategy_id = state_data['active_strategy']
                    # Set the strategy in both manager and state
                    if self.strategy_manager.set_active_strategy(strategy_id):
                        self.state.active_strategy = strategy_id
                        logging.info(f"Restored active strategy: {strategy_id}")
                    else:
                        logging.warning(f"Failed to restore strategy: {strategy_id}")
                        
                # Restore other state fields if needed
                if 'total_trades' in state_data:
                    self.state.total_trades = state_data['total_trades']
                if 'total_pnl' in state_data:
                    self.state.total_pnl = state_data['total_pnl']
                    
                # Restore bot status and restart if it was running
                if 'status' in state_data and state_data['status'] == 'running':
                    logging.info("Bot was previously running, restarting...")
                    # Don't call self.start() here as it might cause recursion
                    # Just mark as running and start the thread
                    self.state.status = 'running'
                    self.stop_event.clear()
                    if not self.running_thread or not self.running_thread.is_alive():
                        self.running_thread = threading.Thread(target=self.trading_loop, daemon=False)
                        self.running_thread.start()
                        logging.info("Auto trading bot auto-restarted")
                    
        except Exception as e:
            logging.warning(f"Failed to load bot state: {e}")
    
    def save_state(self):
        """Save current bot state"""
        try:
            state_data = {
                'active_strategy': self.state.active_strategy,
                'status': self.state.status,
                'total_trades': self.state.total_trades,
                'total_pnl': self.state.total_pnl,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
                
        except Exception as e:
            logging.warning(f"Failed to save bot state: {e}")
    
    def get_current_price(self) -> Optional[float]:
        """Get current BTC price"""
        try:
            # Use existing bot adapter method
            price = self.bot_adapter._get_real_btc_price()
            if price > 0:
                self.price_history.append(price)
                # Keep last 100 price points
                if len(self.price_history) > 100:
                    self.price_history = self.price_history[-100:]
                return price
        except Exception as e:
            logging.error(f"Error getting current price: {e}")
        return None
    
    def can_trade_safely(self, signal: TradingSignal) -> tuple:
        """Check if it's safe to execute trade"""
        
        # Check daily loss limit
        if self.state.today_pnl < -self.max_daily_loss:
            return False, f"Daily loss limit reached: ${abs(self.state.today_pnl):.2f}"
        
        # Check confidence threshold
        if signal.confidence < self.min_confidence:
            return False, f"Confidence too low: {signal.confidence:.1%} < {self.min_confidence:.1%}"
        
        # Check if we have enough balance
        try:
            balances = self.bot_adapter.get_account_balances_jwt()
            usd_balance = 0
            btc_balance = 0
            
            for balance in balances:
                if balance['currency'] == 'USD':
                    usd_balance = balance['available']
                elif balance['currency'] == 'BTC':
                    btc_balance = balance['available']
            
            if signal.action in [SignalStrength.BUY, SignalStrength.STRONG_BUY]:
                if signal.amount_usd and usd_balance < signal.amount_usd:
                    return False, f"Insufficient USD: ${usd_balance:.2f} < ${signal.amount_usd:.2f}"
            elif signal.action in [SignalStrength.SELL, SignalStrength.STRONG_SELL]:
                required_btc = (signal.amount_usd or 25.0) / signal.price if signal.price > 0 else 0
                if btc_balance < required_btc:
                    return False, f"Insufficient BTC: {btc_balance:.8f} < {required_btc:.8f}"
        
        except Exception as e:
            return False, f"Error checking balances: {str(e)}"
        
        return True, "Safe to trade"
    
    def execute_trade(self, signal: TradingSignal) -> bool:
        """Execute a trade based on the signal"""
        try:
            # Safety check
            can_trade, reason = self.can_trade_safely(signal)
            if not can_trade:
                print(f"🚫 TRADE BLOCKED: {reason}")
                logging.warning(f"Trade blocked: {reason}")
                return False
            
            # Determine trade parameters
            action = 'buy' if signal.action in [SignalStrength.BUY, SignalStrength.STRONG_BUY] else 'sell'
            amount = signal.amount_usd or 25.0  # Default $25 if not specified
            
            # Create trade record
            trade_record = TradeRecord(
                id=f"auto_{int(time.time())}",
                strategy=self.state.active_strategy,
                action=action.upper(),
                amount_usd=amount,
                price=signal.price,
                timestamp=datetime.now(),
                reason=signal.reason,
                status="PENDING"
            )
            
            print(f"🚀 ATTEMPTING TRADE: {action.upper()} ${amount} BTC at ${signal.price:.2f}")
            print(f"   Strategy: {self.state.active_strategy}")
            print(f"   Confidence: {signal.confidence:.1%}")
            print(f"   Reason: {signal.reason}")
            logging.info(f"Executing auto trade: {action} ${amount} BTC at ${signal.price:.2f}")
            
            # Execute trade using existing bot adapter
            print(f"📞 Calling Coinbase API for {action.upper()} order...")
            result = self.bot_adapter._execute_advanced_trade_jwt(
                action=action,
                symbol='BTC-USD',  # Use USD instead of USDC for consistency
                amount_type='usd',
                amount=amount
            )
            
            if result['success']:
                trade_record.status = "EXECUTED"
                trade_record.order_id = result.get('order_id')
                
                # Update statistics
                self.state.trades_today += 1
                self.state.total_trades += 1
                
                # Record the trade
                self.strategy_manager.record_trade()
                self.trade_history.append(trade_record)
                
                print(f"✅ TRADE EXECUTED SUCCESSFULLY!")
                print(f"   Order ID: {result.get('order_id')}")
                print(f"   Total Trades Today: {self.state.trades_today}")
                logging.info(f"Auto trade executed successfully: {result.get('order_id')}")
                return True
            else:
                trade_record.status = "FAILED"
                trade_record.reason = result.get('error', 'Unknown error')
                self.trade_history.append(trade_record)
                
                print(f"❌ TRADE FAILED!")
                print(f"   Error: {result.get('error', 'Unknown error')}")
                print(f"   Full response: {result}")
                logging.error(f"Auto trade failed: {result.get('error')}")
                return False
                
        except Exception as e:
            print(f"💥 EXCEPTION DURING TRADE EXECUTION: {e}")
            logging.error(f"Error executing auto trade: {e}")
            return False
    
    def update_performance_stats(self):
        """Update performance statistics"""
        today = datetime.now().date()
        
        # Reset daily stats if new day
        if self.state.last_price_check and self.state.last_price_check.date() != today:
            self.state.trades_today = 0
            self.state.today_pnl = 0.0
        
        # Calculate P&L from recent trades (simplified)
        total_pnl = 0.0
        today_pnl = 0.0
        profitable_trades = 0
        
        for trade in self.trade_history:
            if trade.status == "EXECUTED":
                # Simplified P&L calculation - in practice, you'd track actual fills
                if trade.action == "BUY":
                    # For buy orders, we estimate based on price movement
                    pass  # Actual P&L would be calculated when position is closed
                
                if trade.timestamp.date() == today:
                    today_pnl += trade.pnl
                
                total_pnl += trade.pnl
                if trade.pnl > 0:
                    profitable_trades += 1
        
        self.state.total_pnl = total_pnl
        self.state.today_pnl = today_pnl
        self.state.profitable_trades = profitable_trades
    
    def trading_loop(self):
        """Main trading loop"""
        logging.info("Auto trading loop started")
        cycle_count = 0
        
        while not self.stop_event.is_set():
            try:
                if self.state.status != 'running':
                    time.sleep(1)
                    continue
                
                cycle_count += 1
                logging.info(f"Trading cycle #{cycle_count} starting...")
                
                # Get current price
                current_price = self.get_current_price()
                if not current_price:
                    logging.warning("Could not get current price, skipping cycle")
                    time.sleep(self.check_interval)
                    continue
                
                logging.info(f"Fetched price: ${current_price:,.2f} (Total points: {len(self.price_history)})")
                
                self.state.last_price_check = datetime.now()
                
                # Get trading signal from active strategy
                if len(self.price_history) >= 5:  # Need some price history
                    logging.info("Generating trading signal...")
                    signal = self.strategy_manager.get_trading_signal(self.price_history)
                    
                    if signal:
                        self.state.last_signal = signal
                        
                        # Console output for debugging
                        print(f"📊 TRADING SIGNAL GENERATED:")
                        print(f"   Action: {signal.action.value}")
                        print(f"   Confidence: {signal.confidence:.1%}")
                        print(f"   Amount: ${signal.amount_usd or 25.0}")
                        print(f"   Price: ${signal.price:.2f}")
                        print(f"   Reason: {signal.reason}")
                        
                        # Log signal for debugging
                        logging.info(f"📊 Trading signal: {signal.action.value} (confidence: {signal.confidence:.1%}) - {signal.reason}")
                        
                        # Execute trade if signal is strong enough
                        if signal.action in [SignalStrength.BUY, SignalStrength.STRONG_BUY, SignalStrength.SELL, SignalStrength.STRONG_SELL]:
                            if signal.confidence >= self.min_confidence:
                                print(f"🎯 SIGNAL MEETS THRESHOLD - EXECUTING {signal.action.value} TRADE")
                                print(f"   Confidence: {signal.confidence:.1%} >= {self.min_confidence:.0%}")
                                logging.info(f"Signal meets threshold, executing {signal.action.value} trade...")
                                success = self.execute_trade(signal)
                                if success:
                                    print("✅ Auto trade cycle completed successfully")
                                    logging.info("✅ Auto trade executed successfully")
                                else:
                                    print("❌ Auto trade cycle failed")
                                    logging.warning("❌ Auto trade execution failed")
                            else:
                                print(f"⏸️ Signal confidence {signal.confidence:.1%} below threshold {self.min_confidence:.0%} - NO TRADE")
                                logging.info(f"Signal confidence {signal.confidence:.1%} below threshold {self.min_confidence:.0%}")
                        else:
                            print(f"📊 Signal is HOLD - no action taken")
                            logging.info(f"Signal is HOLD - no action taken")
                else:
                    logging.info(f"Need {5 - len(self.price_history)} more price points for signals")
                
                # Update performance stats
                self.update_performance_stats()
                
                # Wait before next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                logging.error(f"Error in trading loop: {e}")
                time.sleep(self.check_interval)
        
        logging.info("Auto trading loop stopped")
    
    def start(self) -> bool:
        """Start the automatic trading bot"""
        if self.state.status == 'running':
            logging.info("Bot is already running")
            return True  # Return True if already running
        
        if not self.state.active_strategy:
            logging.error("Cannot start: No active strategy selected")
            return False
        
        self.state.status = 'running'
        self.stop_event.clear()
        self.save_state()  # Persist the running state
        
        # Start trading thread (not daemon so it continues even if user leaves)
        self.running_thread = threading.Thread(target=self.trading_loop, daemon=False)
        self.running_thread.start()
        
        logging.info(f"Auto trading bot started with strategy: {self.state.active_strategy}")
        return True
    
    def pause(self) -> bool:
        """Pause the trading bot"""
        if self.state.status != 'running':
            return False
        
        self.state.status = 'paused'
        logging.info("Auto trading bot paused")
        return True
    
    def stop(self) -> bool:
        """Stop the trading bot"""
        if self.state.status == 'stopped':
            return False
        
        self.state.status = 'stopped'
        self.stop_event.set()
        
        if self.running_thread and self.running_thread.is_alive():
            self.running_thread.join(timeout=5)
        
        logging.info("Auto trading bot stopped")
        return True
    
    def set_strategy(self, strategy_id: str) -> bool:
        """Set the active trading strategy"""
        if self.strategy_manager.set_active_strategy(strategy_id):
            self.state.active_strategy = strategy_id
            self.save_state()  # Persist the strategy selection
            logging.info(f"Active strategy set to: {strategy_id}")
            return True
        return False
    
    def _serialize_signal(self, signal):
        """Convert TradingSignal to JSON-serializable dict"""
        if not signal:
            return None
        return {
            'action': signal.action.value if hasattr(signal.action, 'value') else str(signal.action),
            'confidence': signal.confidence,
            'reason': signal.reason,
            'price': signal.price,
            'timestamp': signal.timestamp.isoformat() if signal.timestamp else None,
            'amount_usd': getattr(signal, 'amount_usd', None)
        }
    
    def get_status(self) -> Dict:
        """Get current bot status and stats"""
        win_rate = 0.0
        if self.state.total_trades > 0:
            win_rate = (self.state.profitable_trades / self.state.total_trades) * 100
        
        return {
            'status': self.state.status,
            'active_strategy': self.state.active_strategy,
            'performance': {
                'totalTrades': self.state.total_trades,
                'profitableTrades': self.state.profitable_trades,
                'totalPnL': self.state.total_pnl,
                'todayPnL': self.state.today_pnl,
                'winRate': win_rate
            },
            'current_signal': self._serialize_signal(self.state.last_signal) if self.state.last_signal else None,
            'strategies': self.strategy_manager.get_available_strategies()
        }
    
    def get_trading_history(self, limit: int = 50) -> List[Dict]:
        """Get recent trading history"""
        recent_trades = sorted(self.trade_history, key=lambda x: x.timestamp, reverse=True)[:limit]
        
        return [
            {
                'id': trade.id,
                'strategy': trade.strategy,
                'action': trade.action,
                'amount': trade.amount_usd,
                'price': trade.price,
                'timestamp': trade.timestamp.isoformat(),
                'order_id': trade.order_id,
                'status': trade.status,
                'pnl': trade.pnl,
                'reason': trade.reason
            }
            for trade in recent_trades
        ]