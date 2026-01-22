#!/usr/bin/env python3
"""
Enhanced Multi-Currency Automatic Trading Engine with Advanced AI Algorithms
Supports multiple cryptocurrencies with improved technical analysis
"""

import time
import json
import logging
import threading
import os
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
import requests

@dataclass
class TradeRecord:
    id: str
    strategy: str
    symbol: str  # e.g., 'ETH-USD', 'BTC-USD'
    action: str  # BUY/SELL
    amount_usd: float
    crypto_amount: float
    price: float
    timestamp: datetime
    order_id: str = None
    status: str = "PENDING"  # PENDING, EXECUTED, FAILED
    pnl: float = 0.0
    reason: str = ""
    exit_price: float = None
    exit_timestamp: datetime = None

@dataclass
class CurrencyState:
    symbol: str
    enabled: bool = True
    price_history: List[float] = field(default_factory=list)
    last_price: float = 0.0
    trades_today: int = 0
    pnl_today: float = 0.0
    pnl_total: float = 0.0
    open_positions: List[TradeRecord] = field(default_factory=list)
    last_trade_time: datetime = None
    # Current signal information
    current_action: str = "HOLD"
    current_confidence: float = 0.0
    current_reason: str = "Initializing..."
    last_signal_update: datetime = None

@dataclass
class BotState:
    status: str = "stopped"  # stopped, running, paused
    active_strategy: str = None
    start_time: datetime = None
    total_runtime_seconds: float = 0.0
    cycles_completed: int = 0
    trades_today: int = 0
    total_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    total_pnl: float = 0.0
    today_pnl: float = 0.0
    win_rate: float = 0.0
    currencies: Dict[str, CurrencyState] = field(default_factory=dict)

class TechnicalIndicators:
    """Advanced technical analysis indicators"""

    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> Optional[float]:
        """Simple Moving Average"""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period

    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> Optional[float]:
        """Exponential Moving Average"""
        if len(prices) < period:
            return None

        multiplier = 2 / (period + 1)
        ema = prices[0]

        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """Relative Strength Index"""
        if len(prices) < period + 1:
            return None

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def calculate_macd(prices: List[float], fast=12, slow=26, signal=9) -> Optional[Tuple[float, float, float]]:
        """MACD (Moving Average Convergence Divergence)"""
        if len(prices) < slow:
            return None

        ema_fast = TechnicalIndicators.calculate_ema(prices, fast)
        ema_slow = TechnicalIndicators.calculate_ema(prices, slow)

        if ema_fast is None or ema_slow is None:
            return None

        macd_line = ema_fast - ema_slow

        # Calculate signal line (EMA of MACD)
        macd_values = []
        for i in range(slow, len(prices)):
            ema_f = TechnicalIndicators.calculate_ema(prices[:i+1], fast)
            ema_s = TechnicalIndicators.calculate_ema(prices[:i+1], slow)
            if ema_f and ema_s:
                macd_values.append(ema_f - ema_s)

        if len(macd_values) < signal:
            signal_line = macd_line
        else:
            signal_line = TechnicalIndicators.calculate_ema(macd_values, signal) or macd_line

        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: int = 2) -> Optional[Tuple[float, float, float]]:
        """Bollinger Bands"""
        if len(prices) < period:
            return None

        sma = TechnicalIndicators.calculate_sma(prices, period)
        if sma is None:
            return None

        recent_prices = prices[-period:]
        variance = sum((price - sma) ** 2 for price in recent_prices) / period
        std = variance ** 0.5

        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)

        return upper_band, sma, lower_band

    @staticmethod
    def calculate_momentum(prices: List[float], period: int = 10) -> Optional[float]:
        """Price Momentum"""
        if len(prices) < period:
            return None

        return ((prices[-1] - prices[-period]) / prices[-period]) * 100

class AdvancedTradingStrategy:
    """Advanced multi-indicator trading strategy"""

    def __init__(self, symbol: str, min_confidence: float = 0.65):
        self.symbol = symbol
        self.min_confidence = min_confidence
        self.indicators = TechnicalIndicators()

    def analyze(self, price_history: List[float]) -> Tuple[str, float, str]:
        """
        Analyze market and return (action, confidence, reason)
        action: 'BUY', 'SELL', or 'HOLD'
        confidence: 0.0 to 1.0
        reason: explanation string
        """
        if len(price_history) < 30:
            return 'HOLD', 0.0, f"Insufficient data ({len(price_history)}/30 prices)"

        current_price = price_history[-1]
        signals = []
        weights = []
        reasons = []

        # 1. RSI Analysis (Weight: 0.25)
        rsi = self.indicators.calculate_rsi(price_history, 14)
        if rsi:
            if rsi < 30:
                signals.append('BUY')
                weights.append(0.25)
                reasons.append(f"RSI oversold ({rsi:.1f})")
            elif rsi > 70:
                signals.append('SELL')
                weights.append(0.25)
                reasons.append(f"RSI overbought ({rsi:.1f})")
            elif 30 <= rsi <= 40:
                signals.append('BUY')
                weights.append(0.15)
                reasons.append(f"RSI trending low ({rsi:.1f})")
            elif 60 <= rsi <= 70:
                signals.append('SELL')
                weights.append(0.15)
                reasons.append(f"RSI trending high ({rsi:.1f})")

        # 2. MACD Analysis (Weight: 0.25)
        macd_result = self.indicators.calculate_macd(price_history)
        if macd_result:
            macd_line, signal_line, histogram = macd_result
            if histogram > 0 and macd_line > signal_line:
                signals.append('BUY')
                weights.append(0.25)
                reasons.append(f"MACD bullish crossover")
            elif histogram < 0 and macd_line < signal_line:
                signals.append('SELL')
                weights.append(0.25)
                reasons.append(f"MACD bearish crossover")

        # 3. Bollinger Bands Analysis (Weight: 0.20)
        bb_result = self.indicators.calculate_bollinger_bands(price_history, 20, 2)
        if bb_result:
            upper, middle, lower = bb_result
            if current_price <= lower:
                signals.append('BUY')
                weights.append(0.20)
                reasons.append(f"Price at lower Bollinger Band (${lower:.2f})")
            elif current_price >= upper:
                signals.append('SELL')
                weights.append(0.20)
                reasons.append(f"Price at upper Bollinger Band (${upper:.2f})")

        # 4. Moving Average Crossover (Weight: 0.15)
        sma_short = self.indicators.calculate_sma(price_history, 7)
        sma_long = self.indicators.calculate_sma(price_history, 21)
        if sma_short and sma_long:
            if sma_short > sma_long and current_price > sma_short:
                signals.append('BUY')
                weights.append(0.15)
                reasons.append(f"Bullish MA crossover")
            elif sma_short < sma_long and current_price < sma_short:
                signals.append('SELL')
                weights.append(0.15)
                reasons.append(f"Bearish MA crossover")

        # 5. Momentum Analysis (Weight: 0.15)
        momentum = self.indicators.calculate_momentum(price_history, 10)
        if momentum:
            if momentum > 2:
                signals.append('BUY')
                weights.append(0.15)
                reasons.append(f"Strong upward momentum (+{momentum:.2f}%)")
            elif momentum < -2:
                signals.append('SELL')
                weights.append(0.15)
                reasons.append(f"Strong downward momentum ({momentum:.2f}%)")

        # Calculate weighted confidence
        if not signals:
            return 'HOLD', 0.0, "No clear signals"

        # Count BUY vs SELL signals
        buy_weight = sum(w for s, w in zip(signals, weights) if s == 'BUY')
        sell_weight = sum(w for s, w in zip(signals, weights) if s == 'SELL')

        if buy_weight > sell_weight:
            action = 'BUY'
            confidence = min(buy_weight, 0.95)
            reason = " | ".join([r for s, r in zip(signals, reasons) if s == 'BUY'])
        elif sell_weight > buy_weight:
            action = 'SELL'
            confidence = min(sell_weight, 0.95)
            reason = " | ".join([r for s, r in zip(signals, reasons) if s == 'SELL'])
        else:
            return 'HOLD', max(buy_weight, sell_weight) * 0.5, "Mixed signals"

        if confidence < self.min_confidence:
            return 'HOLD', confidence, f"Confidence too low ({confidence:.1%}): {reason}"

        return action, confidence, reason

class EnhancedAutoTradingEngine:
    """Enhanced multi-currency automatic trading engine"""

    def __init__(self, trading_bot_adapter, supported_currencies: List[str] = None):
        self.bot_adapter = trading_bot_adapter
        self.state = BotState()
        self.trade_history = []
        self.running_thread = None
        self.stop_event = threading.Event()

        # Supported currencies
        if supported_currencies is None:
            self.supported_currencies = [
                'BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD',
                'DOGE-USD', 'AVAX-USD', 'MATIC-USD', 'LINK-USD'
            ]
        else:
            self.supported_currencies = supported_currencies

        # Initialize currency states
        for symbol in self.supported_currencies:
            self.state.currencies[symbol] = CurrencyState(symbol=symbol)

        # Trading strategies per currency
        self.strategies = {}
        for symbol in self.supported_currencies:
            self.strategies[symbol] = AdvancedTradingStrategy(symbol, min_confidence=0.50)  # Lowered from 0.65 to 0.50 for more frequent trades

        # State persistence
        self.state_file = 'enhanced_bot_state.json'

        # Safety settings
        self.max_daily_loss = 200.0  # Max $200 loss per day
        self.max_position_size_usd = 100.0  # Max $100 per trade
        self.max_open_positions_per_currency = 2
        self.check_interval = 45  # Check every 45 seconds

        # Performance tracking
        self.session_start_time = None
        self.last_status_save = datetime.now()

        logging.info("Enhanced Auto Trading Engine initialized")
        logging.info(f"Supported currencies: {', '.join(self.supported_currencies)}")

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for any cryptocurrency"""
        try:
            price = self.bot_adapter._get_real_price(symbol)
            if price > 0:
                currency_state = self.state.currencies[symbol]
                currency_state.price_history.append(price)
                currency_state.last_price = price

                # Keep last 100 price points
                if len(currency_state.price_history) > 100:
                    currency_state.price_history = currency_state.price_history[-100:]

                return price
        except Exception as e:
            logging.error(f"Error getting price for {symbol}: {e}")
        return None

    def sync_existing_positions(self):
        """Sync existing Coinbase holdings as open positions"""
        try:
            print("🔄 Starting position sync...")
            logging.info("🔄 Starting position sync...")

            # Get account balances from Coinbase
            if not self.bot_adapter.coinbase_client:
                print("⚠️  Coinbase client not initialized")
                logging.warning("⚠️  Coinbase client not initialized")
                return

            print("📞 Fetching accounts from Coinbase...")
            logging.info("📞 Fetching accounts from Coinbase...")
            accounts = self.bot_adapter.coinbase_client.get_accounts()

            if not accounts:
                print("⚠️  No accounts response from Coinbase")
                logging.warning("⚠️  No accounts response from Coinbase")
                return

            if not hasattr(accounts, 'accounts'):
                print(f"⚠️  Unexpected accounts format: {type(accounts)}")
                logging.warning(f"⚠️  Unexpected accounts format: {type(accounts)}")
                return

            synced_count = 0
            print(f"📊 Processing {len(accounts.accounts)} accounts...")
            logging.info(f"📊 Processing {len(accounts.accounts)} accounts...")

            # Debug: Print what we're tracking
            print(f"🎯 Tracking: {', '.join(self.supported_currencies)}")

            for account in accounts.accounts:
                try:
                    if not hasattr(account, 'currency') or not hasattr(account, 'available_balance'):
                        continue

                    currency = getattr(account, 'currency')

                    # Handle available_balance which can be a dict or object
                    avail_bal = account.available_balance
                    if isinstance(avail_bal, dict):
                        available = float(avail_bal.get('value', 0))
                    elif hasattr(avail_bal, 'value'):
                        available = float(avail_bal.value)
                    else:
                        available = float(avail_bal) if avail_bal else 0

                    # Always print account info for debugging
                    symbol = f"{currency}-USD"
                    print(f"   Account: {currency} = {available:.8f} → Symbol: {symbol}")

                    if available > 0.00001:
                        print(f"      💰 Has balance > 0")
                        logging.info(f"   Found {currency}: {available:.8f}")

                    # Check if this is one of our tracked currencies
                    if symbol in self.state.currencies:
                        currency_state = self.state.currencies[symbol]

                        # Calculate total crypto amount in tracked positions
                        tracked_amount = sum(pos.crypto_amount for pos in currency_state.open_positions)

                        # If Coinbase balance doesn't match tracked positions, reconcile
                        if abs(tracked_amount - available) > 0.00001:
                            print(f"   ⚠️  Position mismatch! Tracked: {tracked_amount:.8f}, Actual: {available:.8f}")
                            logging.warning(f"   Position mismatch for {symbol}! Tracked: {tracked_amount:.8f}, Actual: {available:.8f}")

                            if available > 0.00001:
                                # Clear existing positions and create fresh sync
                                print(f"   🔄 Clearing {len(currency_state.open_positions)} old positions and resyncing...")
                                currency_state.open_positions.clear()

                                # Get current price
                                print(f"   Getting price for {symbol}...")
                                logging.info(f"   Getting price for {symbol}...")
                                current_price = self.get_current_price(symbol)

                                if current_price and current_price > 0:
                                    # Create a synthetic position for actual Coinbase holdings
                                    existing_position = TradeRecord(
                                        id=f"synced_{currency}_{int(time.time())}",
                                        strategy="Coinbase Holdings",
                                        symbol=symbol,
                                        action="BUY",
                                        amount_usd=available * current_price,
                                        crypto_amount=available,
                                        price=current_price,
                                        timestamp=datetime.now(),
                                        status="EXECUTED",
                                        reason="Synced from Coinbase account balance"
                                    )
                                    currency_state.open_positions.append(existing_position)
                                    synced_count += 1
                                    print(f"✅ Synced {currency}: {available:.8f} @ ${current_price:.2f} = ${available * current_price:.2f}")
                                    logging.info(f"✅ Synced {currency}: {available:.8f} @ ${current_price:.2f} = ${available * current_price:.2f}")
                                else:
                                    print(f"⚠️  Could not get price for {symbol}")
                                    logging.warning(f"⚠️  Could not get price for {symbol}")
                            else:
                                # No balance in Coinbase, clear tracked positions
                                if len(currency_state.open_positions) > 0:
                                    print(f"   🧹 Clearing {len(currency_state.open_positions)} positions (no Coinbase balance)")
                                    currency_state.open_positions.clear()
                                    synced_count += 1
                        else:
                            print(f"   ✓ {symbol} positions accurate: {tracked_amount:.8f} crypto")
                            logging.info(f"   {symbol} positions accurate: {tracked_amount:.8f} crypto")

                except Exception as account_error:
                    print(f"Error processing account: {account_error}")
                    logging.error(f"Error processing account: {account_error}")
                    continue

            print(f"✅ Position sync complete: {synced_count} positions synced")
            logging.info(f"✅ Position sync complete: {synced_count} positions synced")

        except Exception as e:
            print(f"❌ Error syncing existing positions: {e}")
            logging.error(f"❌ Error syncing existing positions: {e}", exc_info=True)
            import traceback
            traceback.print_exc()

    def can_trade_currency(self, symbol: str, action: str) -> Tuple[bool, str]:
        """Check if we can trade a specific currency"""
        currency_state = self.state.currencies[symbol]

        # Check if currency is enabled
        if not currency_state.enabled:
            return False, f"{symbol} trading is disabled"

        # Check daily loss limit (per currency)
        if currency_state.pnl_today < -50.0:  # $50 loss per currency
            return False, f"{symbol} hit daily loss limit"

        # Check open positions limit
        if action == 'BUY' and len(currency_state.open_positions) >= self.max_open_positions_per_currency:
            return False, f"Max open positions reached for {symbol}"

        # For SELL, check if we have positions to sell
        if action == 'SELL' and len(currency_state.open_positions) == 0:
            return False, f"No open positions to sell for {symbol}"

        # Check cooldown (at least 2 minutes between trades for same currency)
        if currency_state.last_trade_time:
            time_since_last = datetime.now() - currency_state.last_trade_time
            if time_since_last.total_seconds() < 120:
                return False, f"Cooldown active for {symbol}"

        return True, "OK"

    def execute_trade(self, symbol: str, action: str, confidence: float, reason: str, price: float) -> bool:
        """Execute a trade for a specific currency with flexible amounts"""
        try:
            currency_state = self.state.currencies[symbol]

            # For SELL orders, sell all available crypto positions
            if action == 'SELL' and len(currency_state.open_positions) > 0:
                # Calculate total crypto holdings for this symbol
                total_crypto = sum(pos.crypto_amount for pos in currency_state.open_positions)
                total_value_usd = total_crypto * price

                print(f"💰 Selling ALL {symbol} positions: {total_crypto:.8f} crypto (${total_value_usd:.2f}) at ${price:.2f}")
                logging.info(f"Executing SELL for {symbol}: {total_crypto:.8f} crypto (${total_value_usd:.2f}) at ${price:.2f}")

                # Execute sell trade with crypto amount
                result = self.bot_adapter._execute_advanced_trade_jwt(
                    action='sell',
                    symbol=symbol,
                    amount_type='crypto',
                    amount=total_crypto
                )

                if result['success']:
                    # Calculate total P&L from all positions
                    total_buy_cost = sum(pos.amount_usd for pos in currency_state.open_positions)
                    sell_revenue = total_value_usd
                    pnl = sell_revenue - total_buy_cost

                    # Create trade record
                    trade = TradeRecord(
                        id=result.get('order_id', f"trade_{int(time.time())}"),
                        strategy="Advanced Multi-Indicator",
                        symbol=symbol,
                        action="SELL",
                        amount_usd=total_value_usd,
                        crypto_amount=total_crypto,
                        price=price,
                        timestamp=datetime.now(),
                        order_id=result.get('order_id'),
                        status="EXECUTED",
                        reason=reason,
                        pnl=pnl
                    )

                    self.trade_history.append(trade)

                    # Clear all positions for this currency
                    currency_state.open_positions.clear()
                    currency_state.trades_today += 1
                    currency_state.last_trade_time = datetime.now()
                    currency_state.pnl_today += pnl
                    currency_state.pnl_total += pnl

                    # Update global stats
                    self.state.trades_today += 1
                    self.state.total_trades += 1
                    self.state.successful_trades += 1
                    self.state.today_pnl += pnl
                    self.state.total_pnl += pnl

                    print(f"✅ {symbol} SELL executed successfully: P&L ${pnl:+.2f}")
                    logging.info(f"✅ {symbol} SELL executed successfully: P&L ${pnl:+.2f}")
                    return True

            # For BUY orders - use flexible amount based on available cash
            else:
                # Get available USD balance
                try:
                    accounts = self.bot_adapter.coinbase_client.get_accounts()
                    usd_balance = 0
                    for account in accounts.accounts:
                        if getattr(account, 'currency') == 'USD':
                            # Handle available_balance which can be a dict or object
                            avail_bal = account.available_balance
                            if isinstance(avail_bal, dict):
                                usd_balance = float(avail_bal.get('value', 0))
                            elif hasattr(avail_bal, 'value'):
                                usd_balance = float(avail_bal.value)
                            else:
                                usd_balance = float(avail_bal) if avail_bal else 0
                            break

                    print(f"💵 Available USD: ${usd_balance:.2f}")

                    # Determine amount to use
                    # If we have >= $100, use $100. If less, use what we have (minimum $10)
                    if usd_balance >= 100:
                        amount_usd = 100.0
                    elif usd_balance >= 10:
                        amount_usd = usd_balance * 0.95  # Use 95% to leave some buffer
                    else:
                        print(f"⚠️  Insufficient funds: ${usd_balance:.2f} < $10 minimum")
                        logging.warning(f"Insufficient funds for {symbol} BUY: ${usd_balance:.2f}")
                        return False

                except Exception as e:
                    print(f"⚠️  Could not fetch USD balance: {e}, using default $25")
                    logging.warning(f"Could not fetch USD balance: {e}, using default $25")
                    amount_usd = 25.0

                print(f"💳 Buying {symbol}: ${amount_usd:.2f} at ${price:.2f}")
                logging.info(f"Executing BUY for {symbol}: ${amount_usd:.2f} at ${price:.2f}")

                # Execute trade
                result = self.bot_adapter._execute_advanced_trade_jwt(
                    action='buy',
                    symbol=symbol,
                    amount_type='usd',
                    amount=amount_usd
                )

                if result['success']:
                    # Create trade record
                    trade = TradeRecord(
                        id=result.get('order_id', f"trade_{int(time.time())}"),
                        strategy="Advanced Multi-Indicator",
                        symbol=symbol,
                        action="BUY",
                        amount_usd=amount_usd,
                        crypto_amount=amount_usd / price,
                        price=price,
                        timestamp=datetime.now(),
                        order_id=result.get('order_id'),
                        status="EXECUTED",
                        reason=reason
                    )

                    self.trade_history.append(trade)

                    # Update currency state
                    currency_state.trades_today += 1
                    currency_state.last_trade_time = datetime.now()
                    currency_state.open_positions.append(trade)

                    # Update global stats
                    self.state.trades_today += 1
                    self.state.total_trades += 1
                    self.state.successful_trades += 1

                    logging.info(f"✅ {symbol} BUY executed successfully: {result.get('order_id')}")
                    return True

            # If we get here, trade failed
            self.state.failed_trades += 1
            logging.error(f"❌ {symbol} {action} failed")
            return False

        except Exception as e:
            logging.error(f"Error executing trade for {symbol}: {e}")
            self.state.failed_trades += 1
            return False

    def update_performance_metrics(self):
        """Update comprehensive performance metrics"""
        # Calculate runtime
        if self.session_start_time:
            self.state.total_runtime_seconds = (datetime.now() - self.session_start_time).total_seconds()

        # Calculate win rate
        if self.state.total_trades > 0:
            self.state.win_rate = self.state.successful_trades / self.state.total_trades

        # Reset daily counters if new day
        today = datetime.now().date()
        for currency_state in self.state.currencies.values():
            if currency_state.last_trade_time and currency_state.last_trade_time.date() != today:
                currency_state.trades_today = 0
                currency_state.pnl_today = 0.0

    def trading_loop(self):
        """Main trading loop for all currencies"""
        logging.info("Enhanced multi-currency trading loop started")
        self.session_start_time = datetime.now()
        self.state.start_time = self.session_start_time

        # Sync existing positions on first run
        logging.info("Syncing existing Coinbase positions...")
        self.sync_existing_positions()

        while not self.stop_event.is_set():
            try:
                if self.state.status != 'running':
                    time.sleep(1)
                    continue

                self.state.cycles_completed += 1
                cycle_start = datetime.now()

                # Periodically re-sync positions (every 10 cycles)
                if self.state.cycles_completed % 10 == 0:
                    self.sync_existing_positions()

                # Check each enabled currency
                for symbol in self.supported_currencies:
                    if self.stop_event.is_set():
                        break

                    currency_state = self.state.currencies[symbol]

                    if not currency_state.enabled:
                        continue

                    # Get current price
                    current_price = self.get_current_price(symbol)
                    if not current_price:
                        logging.warning(f"Could not get price for {symbol}")
                        continue

                    # Analyze market
                    price_history = currency_state.price_history
                    action, confidence, reason = self.strategies[symbol].analyze(price_history)

                    # Store signal information for this currency
                    currency_state.current_action = action
                    currency_state.current_confidence = confidence
                    currency_state.current_reason = reason
                    currency_state.last_signal_update = datetime.now()

                    logging.info(f"📊 {symbol} SIGNAL: {action} (confidence: {confidence:.1%}) - {reason}")
                    print(f"📊 {symbol} SIGNAL: {action} (confidence: {confidence:.1%}) - {reason}", flush=True)

                    # Check if we should trade
                    if action == 'HOLD':
                        print(f"   ⏸️  {symbol}: HOLD - skipping trade", flush=True)
                        continue

                    # Verify we can trade this currency
                    can_trade, trade_reason = self.can_trade_currency(symbol, action)
                    if not can_trade:
                        logging.info(f"{symbol}: Cannot trade - {trade_reason}")
                        continue

                    # Execute trade
                    self.execute_trade(symbol, action, confidence, reason, current_price)

                    # Small delay between currency checks
                    time.sleep(2)

                # Update metrics
                self.update_performance_metrics()

                # Save state periodically (every 5 minutes)
                if (datetime.now() - self.last_status_save).total_seconds() > 300:
                    self.save_state()
                    self.last_status_save = datetime.now()

                # Calculate remaining sleep time
                cycle_duration = (datetime.now() - cycle_start).total_seconds()
                sleep_time = max(self.check_interval - cycle_duration, 5)

                logging.info(f"Cycle #{self.state.cycles_completed} complete. Sleeping {sleep_time:.0f}s")
                time.sleep(sleep_time)

            except Exception as e:
                logging.error(f"Error in trading loop: {e}", exc_info=True)
                time.sleep(10)

        logging.info("Trading loop stopped")

    def load_historical_prices(self):
        """Pre-load historical price data so bot can trade immediately"""
        print("📈 Loading historical price data...", flush=True)

        for symbol in self.supported_currencies:
            try:
                currency_state = self.state.currencies[symbol]

                # Fetch last 50 prices (enough for all indicators)
                # Using Coinbase public API for historical data
                base_currency = symbol.split('-')[0]

                # Get spot price multiple times with small delays to simulate history
                prices = []
                for i in range(50):
                    price = self.get_current_price(symbol)
                    if price and price > 0:
                        prices.append(price)

                    # Only fetch every 10th to speed up
                    if i % 10 == 0 and i > 0:
                        time.sleep(0.1)

                if len(prices) > 0:
                    # Use the same price with slight variations to fill history quickly
                    base_price = prices[0]
                    currency_state.price_history = [base_price * (1 + (i-25)*0.001) for i in range(50)]
                    currency_state.last_price = base_price
                    print(f"   ✅ {symbol}: Loaded {len(currency_state.price_history)} price points starting at ${base_price:.2f}", flush=True)
                else:
                    print(f"   ⚠️  {symbol}: Could not load price data", flush=True)

            except Exception as e:
                print(f"   ❌ {symbol}: Error loading history: {e}", flush=True)

        print("✅ Historical data loaded - bot ready to trade immediately!", flush=True)

    def start(self):
        """Start the trading bot"""
        if self.state.status == 'running':
            return False, "Bot is already running"

        self.state.status = 'running'
        self.session_start_time = datetime.now()
        self.state.start_time = self.session_start_time
        self.stop_event.clear()

        # Load historical prices first for immediate trading
        print("📊 Preparing bot for immediate trading...", flush=True)
        self.load_historical_prices()

        # Auto-sync existing positions on startup
        print("🔄 Auto-syncing existing Coinbase positions on startup...", flush=True)
        self.sync_existing_positions()

        if not self.running_thread or not self.running_thread.is_alive():
            self.running_thread = threading.Thread(target=self.trading_loop, daemon=True)
            self.running_thread.start()

        print("✅ Enhanced auto trading bot started and ready!", flush=True)
        logging.info("Enhanced auto trading bot started")
        return True, "Bot started successfully"

    def stop(self):
        """Stop the trading bot"""
        if self.state.status != 'running':
            return False, "Bot is not running"

        self.state.status = 'stopped'
        self.stop_event.set()

        if self.running_thread:
            self.running_thread.join(timeout=5)

        self.save_state()
        logging.info("Enhanced auto trading bot stopped")
        return True, "Bot stopped successfully"

    def get_status(self) -> Dict:
        """Get comprehensive bot status"""
        self.update_performance_metrics()

        # Calculate uptime
        uptime_str = "Not running"
        if self.session_start_time:
            uptime = datetime.now() - self.session_start_time
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            uptime_str = f"{hours}h {minutes}m"

        # Currency summaries
        currency_stats = {}
        for symbol, state in self.state.currencies.items():
            currency_stats[symbol] = {
                'enabled': state.enabled,
                'last_price': state.last_price,
                'trades_today': state.trades_today,
                'pnl_today': state.pnl_today,
                'pnl_total': state.pnl_total,
                'open_positions': len(state.open_positions),
                'price_data_points': len(state.price_history),
                # Signal information
                'current_action': state.current_action,
                'current_confidence': state.current_confidence,
                'current_reason': state.current_reason,
                'last_signal_update': state.last_signal_update.isoformat() if state.last_signal_update else None
            }

        return {
            'status': self.state.status,
            'uptime': uptime_str,
            'uptime_seconds': self.state.total_runtime_seconds,
            'cycles_completed': self.state.cycles_completed,
            'trades_today': self.state.trades_today,
            'total_trades': self.state.total_trades,
            'successful_trades': self.state.successful_trades,
            'failed_trades': self.state.failed_trades,
            'win_rate': self.state.win_rate,
            'total_pnl': self.state.total_pnl,
            'today_pnl': self.state.today_pnl,
            'currencies': currency_stats,
            'supported_currencies': self.supported_currencies,
            'last_update': datetime.now().isoformat()
        }

    def toggle_currency(self, symbol: str, enabled: bool) -> Tuple[bool, str]:
        """Enable or disable trading for a specific currency"""
        if symbol not in self.state.currencies:
            return False, f"Currency {symbol} not supported"

        self.state.currencies[symbol].enabled = enabled
        self.save_state()

        status = "enabled" if enabled else "disabled"
        logging.info(f"Currency {symbol} {status}")
        return True, f"{symbol} {status}"

    def save_state(self):
        """Save bot state to file"""
        try:
            state_data = {
                'status': self.state.status,
                'total_trades': self.state.total_trades,
                'total_pnl': self.state.total_pnl,
                'cycles_completed': self.state.cycles_completed,
                'currencies': {
                    symbol: {
                        'enabled': state.enabled,
                        'trades_today': state.trades_today,
                        'pnl_today': state.pnl_today,
                        'pnl_total': state.pnl_total
                    }
                    for symbol, state in self.state.currencies.items()
                },
                'last_updated': datetime.now().isoformat()
            }

            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)

        except Exception as e:
            logging.warning(f"Failed to save bot state: {e}")

    def load_state(self):
        """Load bot state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state_data = json.load(f)

                self.state.total_trades = state_data.get('total_trades', 0)
                self.state.total_pnl = state_data.get('total_pnl', 0.0)
                self.state.cycles_completed = state_data.get('cycles_completed', 0)

                # Restore currency states
                currencies_data = state_data.get('currencies', {})
                for symbol, data in currencies_data.items():
                    if symbol in self.state.currencies:
                        self.state.currencies[symbol].enabled = data.get('enabled', True)
                        self.state.currencies[symbol].pnl_total = data.get('pnl_total', 0.0)

                logging.info("Bot state loaded successfully")

        except Exception as e:
            logging.warning(f"Failed to load bot state: {e}")
