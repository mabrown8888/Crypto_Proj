
import os
import time
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from coinbase.rest import RESTClient
import requests
from threading import Thread
import signal
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TradingConfig:
    """Configuration class for trading parameters"""
    api_key: str = os.getenv('COINBASE_API_KEY')
    api_secret: str = os.getenv('COINBASE_API_SECRET')
    base_currency: str = "BTC"
    quote_currency: str = "USDC"
    trade_amount_usd: float = 25.0  # 5% of $500 account
    max_position_size: float = 400.0  # 80% of $500 account
    stop_loss_percentage: float = 1.5  # Tighter stop loss
    take_profit_percentage: float = 2.5  # Quicker profits
    rsi_oversold: int = 35  # More sensitive signals
    rsi_overbought: int = 65  # More sensitive signals
    sma_short_period: int = 5  # Faster signals
    sma_long_period: int = 15  # Faster signals
    check_interval: int = 30  # seconds
    max_daily_trades: int = 15  # More opportunities
    risk_per_trade_percent: float = 1.0

class TechnicalIndicators:
    """Technical analysis indicators for trading decisions"""

    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> float:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period

    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return None

        # Calculate smoothing factor
        k = 2 / (period + 1)

        # Start with SMA as the first EMA value
        ema = sum(prices[:period]) / period

        # Calculate EMA for remaining values
        for price in prices[period:]:
            ema = (price * k) + (ema * (1 - k))

        return ema

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return None

        price_changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]

        gains = [change if change > 0 else 0 for change in price_changes]
        losses = [-change if change < 0 else 0 for change in price_changes]

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: int = 2) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return None, None, None

        sma = TechnicalIndicators.calculate_sma(prices, period)
        variance = sum([(price - sma) ** 2 for price in prices[-period:]]) / period
        std = variance ** 0.5

        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)

        return upper_band, sma, lower_band

class RiskManager:
    """Risk management for trading operations"""

    def __init__(self, config: TradingConfig):
        self.config = config
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()

    def reset_daily_counters(self):
        """Reset daily counters at start of new day"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.last_reset_date = today
            logger.info("Daily counters reset for new trading day")

    def can_place_trade(self, current_portfolio_value: float) -> bool:
        """Check if trade can be placed based on risk rules"""
        self.reset_daily_counters()

        # Check daily trade limit
        if self.daily_trades >= self.config.max_daily_trades:
            logger.warning(f"Daily trade limit reached: {self.daily_trades}")
            return False

        # Check if trade amount would exceed max position size
        if self.config.trade_amount_usd > self.config.max_position_size:
            logger.warning(f"Trade amount ${self.config.trade_amount_usd} exceeds max position ${self.config.max_position_size}")
            return False

        return True

    def calculate_position_size(self, current_price: float, portfolio_value: float) -> float:
        """Calculate optimal position size based on risk management"""
        # Risk per trade as percentage of portfolio
        risk_amount = portfolio_value * (self.config.risk_per_trade_percent / 100)

        # Calculate position size based on stop loss
        stop_loss_distance = current_price * (self.config.stop_loss_percentage / 100)
        position_size_by_risk = risk_amount / stop_loss_distance

        # Use minimum of calculated size and fixed trade amount
        max_position_by_amount = self.config.trade_amount_usd / current_price

        return min(position_size_by_risk, max_position_by_amount)

class CoinbaseClient:
    """Coinbase API client wrapper with error handling"""

    def __init__(self, api_key: str, api_secret: str):
        self.client = RESTClient(api_key=api_key, api_secret=api_secret)
        self.last_request_time = 0
        self.min_request_interval = 0.1  # Rate limiting

    def _rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()

    def get_account_balance(self) -> Dict:
        """Get account balances with error handling"""
        self._rate_limit()
        try:
            accounts = self.client.get_accounts()
            return accounts
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return None

    def get_product_ticker(self, product_id: str) -> Dict:
        """Get current ticker price"""
        self._rate_limit()
        try:
            ticker = self.client.get_product(product_id)
            # Convert to dict if it's an object
            if hasattr(ticker, '__dict__'):
                return ticker.__dict__
            return ticker
        except Exception as e:
            logger.error(f"Error getting ticker for {product_id}: {e}")
            return None

    def get_product_candles(self, product_id: str, granularity: int, start: str, end: str) -> List:
        """Get historical candle data"""
        self._rate_limit()
        try:
            candles = self.client.get_candles(
                product_id=product_id,
                start=start,
                end=end,
                granularity=granularity
            )
            return candles
        except Exception as e:
            logger.error(f"Error getting candles for {product_id}: {e}")
            return None

    def place_market_order(self, product_id: str, side: str, size: str) -> Dict:
        """Place a market order"""
        self._rate_limit()
        try:
            if side.lower() == 'buy':
                order = self.client.market_order_buy(
                    client_order_id=f"bot_{int(time.time())}",
                    product_id=product_id,
                    quote_size=size
                )
            else:
                order = self.client.market_order_sell(
                    client_order_id=f"bot_{int(time.time())}",
                    product_id=product_id,
                    base_size=size
                )

            logger.info(f"Order placed: {side} {size} {product_id}")
            return order
        except Exception as e:
            logger.error(f"Error placing {side} order: {e}")
            return None

    def place_limit_order(self, product_id: str, side: str, size: str, price: str) -> Dict:
        """Place a limit order"""
        self._rate_limit()
        try:
            if side.lower() == 'buy':
                order = self.client.limit_order_buy(
                    client_order_id=f"bot_{int(time.time())}",
                    product_id=product_id,
                    base_size=size,
                    limit_price=price
                )
            else:
                order = self.client.limit_order_sell(
                    client_order_id=f"bot_{int(time.time())}",
                    product_id=product_id,
                    base_size=size,
                    limit_price=price
                )

            logger.info(f"Limit order placed: {side} {size} {product_id} at {price}")
            return order
        except Exception as e:
            logger.error(f"Error placing limit {side} order: {e}")
            return None

class TradingBot:
    """Main trading bot class"""

    def __init__(self, config: TradingConfig):
        self.config = config
        self.client = CoinbaseClient(config.api_key, config.api_secret)
        self.risk_manager = RiskManager(config)
        self.running = False
        self.price_history = []
        self.current_position = None
        self.product_id = f"{config.base_currency}-{config.quote_currency}"

        # Performance tracking
        self.trades_executed = []
        self.total_pnl = 0.0
        
        # Bootstrap with historical data
        self.bootstrap_price_history()

    def bootstrap_price_history(self):
        """Fetch historical data to initialize price history"""
        try:
            # Get last 30 minutes of 1-minute candles
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=30)
            
            candles = self.client.get_product_candles(
                self.product_id,
                granularity="ONE_MINUTE",  # Use string format
                start=str(int(start_time.timestamp())),
                end=str(int(end_time.timestamp()))
            )
            
            if candles:
                # Handle different response formats
                candle_data = candles
                if hasattr(candles, 'candles'):
                    candle_data = candles.candles
                elif hasattr(candles, '__dict__'):
                    candle_data = candles.__dict__.get('candles', candles)
                
                # Extract closing prices from candles
                price_count = 0
                for candle in candle_data:
                    try:
                        if hasattr(candle, 'close'):
                            price = float(candle.close)
                        elif isinstance(candle, (list, tuple)) and len(candle) >= 5:
                            price = float(candle[4])  # Close price is typically index 4
                        elif isinstance(candle, dict):
                            price = float(candle.get('close', candle.get('c', 0)))
                        else:
                            continue
                            
                        if price > 0:
                            self.price_history.append(price)
                            price_count += 1
                            if price_count >= 20:  # Get 20 prices max
                                break
                    except (ValueError, TypeError, AttributeError):
                        continue
                
                if self.price_history:
                    logger.info(f"Bootstrapped with {len(self.price_history)} historical prices")
                else:
                    logger.warning("Could not extract prices from historical data")
            else:
                logger.warning("Could not fetch historical data, will collect live data")
                
        except Exception as e:
            logger.warning(f"Failed to bootstrap price history: {e}")

    def get_market_data(self) -> Optional[Dict]:
        """Fetch current market data and update price history"""
        ticker = self.client.get_product_ticker(self.product_id)
        if not ticker:
            return None

        try:
            # Try different possible price fields
            current_price = 0
            if isinstance(ticker, dict):
                current_price = float(ticker.get('price', ticker.get('ask', ticker.get('bid', 0))))
            else:
                # For object responses, try common attributes
                if hasattr(ticker, 'price'):
                    current_price = float(ticker.price)
                elif hasattr(ticker, 'ask'):
                    current_price = float(ticker.ask)
                elif hasattr(ticker, 'bid'):
                    current_price = float(ticker.bid)
            
            if current_price > 0:
                self.price_history.append(current_price)
                # Keep only last 50 prices for calculations
                if len(self.price_history) > 50:
                    self.price_history = self.price_history[-50:]

                return {
                    'price': current_price,
                    'timestamp': datetime.now()
                }
            else:
                logger.warning(f"No valid price found in ticker response: {ticker}")
        except (ValueError, TypeError) as e:
            logger.error(f"Error processing price data: {e}")

        return None

    def analyze_market(self) -> Dict:
        """Perform technical analysis on current market data"""
        if len(self.price_history) < max(self.config.sma_long_period, 10):
            return {'signal': 'HOLD', 'reason': 'Insufficient data'}

        current_price = self.price_history[-1]

        # Calculate technical indicators
        sma_short = TechnicalIndicators.calculate_sma(self.price_history, self.config.sma_short_period)
        sma_long = TechnicalIndicators.calculate_sma(self.price_history, self.config.sma_long_period)
        rsi = TechnicalIndicators.calculate_rsi(self.price_history, 10)
        upper_bb, middle_bb, lower_bb = TechnicalIndicators.calculate_bollinger_bands(self.price_history, 15, 1.5)

        signals = []

        # Moving Average Crossover Strategy
        if sma_short and sma_long:
            if sma_short > sma_long:
                signals.append('BUY')
            else:
                signals.append('SELL')

        # RSI Strategy
        if rsi:
            if rsi < self.config.rsi_oversold:
                signals.append('BUY')
            elif rsi > self.config.rsi_overbought:
                signals.append('SELL')

        # Bollinger Bands Strategy
        if lower_bb and upper_bb:
            if current_price <= lower_bb:
                signals.append('BUY')
            elif current_price >= upper_bb:
                signals.append('SELL')

        # Determine overall signal
        buy_signals = signals.count('BUY')
        sell_signals = signals.count('SELL')

        if buy_signals > sell_signals and buy_signals >= 1:
            signal = 'BUY'
            reason = f"Buy signals: {buy_signals}, Sell signals: {sell_signals}"
        elif sell_signals > buy_signals and sell_signals >= 1:
            signal = 'SELL'
            reason = f"Sell signals: {sell_signals}, Buy signals: {buy_signals}"
        else:
            signal = 'HOLD'
            reason = f"Mixed signals - Buy: {buy_signals}, Sell: {sell_signals}"

        return {
            'signal': signal,
            'reason': reason,
            'indicators': {
                'price': current_price,
                'sma_short': sma_short,
                'sma_long': sma_long,
                'rsi': rsi,
                'bollinger_upper': upper_bb,
                'bollinger_middle': middle_bb,
                'bollinger_lower': lower_bb
            }
        }

    def execute_trade(self, signal: str, market_data: Dict):
        """Execute trade based on signal"""
        if signal == 'HOLD':
            return

        current_price = market_data['price']

        # Get current portfolio value
        accounts = self.client.get_account_balance()
        if not accounts:
            logger.error("Could not retrieve account balance")
            return

        # Calculate portfolio value from actual account balance
        portfolio_value = 500.0  # Your actual account value
        try:
            if accounts and hasattr(accounts, 'accounts'):
                for account in accounts.accounts:
                    if hasattr(account, 'currency') and account.currency == 'USDC':
                        portfolio_value = float(account.available_balance.value)
                        break
        except Exception as e:
            logger.warning(f"Could not get actual balance, using default: {e}")

        # Check if trade is allowed
        if not self.risk_manager.can_place_trade(portfolio_value):
            return

        if signal == 'BUY' and not self.current_position:
            # Calculate position size
            position_size = self.risk_manager.calculate_position_size(current_price, portfolio_value)

            # Place buy order
            order = self.client.place_market_order(
                self.product_id, 
                'buy', 
                str(self.config.trade_amount_usd)
            )

            if order:
                self.current_position = {
                    'side': 'long',
                    'entry_price': current_price,
                    'size': position_size,
                    'timestamp': datetime.now(),
                    'stop_loss': current_price * (1 - self.config.stop_loss_percentage / 100),
                    'take_profit': current_price * (1 + self.config.take_profit_percentage / 100)
                }

                self.risk_manager.daily_trades += 1
                self.trades_executed.append({
                    'type': 'BUY',
                    'price': current_price,
                    'size': position_size,
                    'timestamp': datetime.now()
                })

                logger.info(f"Opened long position at {current_price}")

        elif signal == 'SELL':
            if not self.current_position:
                logger.info("SELL signal received but no position to close")
                return
            elif self.current_position['side'] != 'long':
                logger.info("SELL signal received but not in long position")
                return
            # Only sell if we actually have a position
            # Close long position
            order = self.client.place_market_order(
                self.product_id, 
                'sell', 
                str(self.current_position['size'])
            )

            if order:
                # Calculate P&L
                pnl = (current_price - self.current_position['entry_price']) * self.current_position['size']
                self.total_pnl += pnl
                self.risk_manager.daily_pnl += pnl

                self.trades_executed.append({
                    'type': 'SELL',
                    'price': current_price,
                    'size': self.current_position['size'],
                    'timestamp': datetime.now(),
                    'pnl': pnl
                })

                logger.info(f"Closed long position at {current_price}, P&L: {pnl:.2f}")
                self.current_position = None

    def check_stop_loss_take_profit(self, current_price: float):
        """Check and execute stop loss or take profit"""
        if not self.current_position:
            return

        position = self.current_position

        if (position['side'] == 'long' and 
            (current_price <= position['stop_loss'] or current_price >= position['take_profit'])):

            # Execute stop loss or take profit
            order = self.client.place_market_order(
                self.product_id, 
                'sell', 
                str(position['size'])
            )

            if order:
                pnl = (current_price - position['entry_price']) * position['size']
                self.total_pnl += pnl

                reason = "Take Profit" if current_price >= position['take_profit'] else "Stop Loss"
                logger.info(f"{reason} executed at {current_price}, P&L: {pnl:.2f}")

                self.current_position = None

    def run_trading_loop(self):
        """Main trading loop"""
        logger.info("Starting trading bot...")
        self.running = True

        while self.running:
            try:
                logger.debug("Starting new trading loop iteration...")
                
                # Get market data
                market_data = self.get_market_data()
                if not market_data:
                    logger.warning("Failed to get market data, retrying...")
                    time.sleep(10)
                    continue

                current_price = market_data['price']

                # Check stop loss/take profit
                self.check_stop_loss_take_profit(current_price)

                # Analyze market and get trading signal
                analysis = self.analyze_market()

                logger.info(f"Price: {current_price:.2f}, Signal: {analysis['signal']}, Reason: {analysis['reason']}")

                # Execute trade if signal is strong enough
                self.execute_trade(analysis['signal'], market_data)

                # Wait before next iteration
                logger.debug(f"Sleeping for {self.config.check_interval} seconds...")
                time.sleep(self.config.check_interval)

            except KeyboardInterrupt:
                logger.info("Received interrupt signal, stopping bot...")
                self.stop()
                break
            except Exception as e:
                logger.error(f"Unexpected error in trading loop: {e}")
                time.sleep(30)  # Wait before retrying

    def stop(self):
        """Stop the trading bot"""
        self.running = False

        # Close any open positions
        if self.current_position:
            logger.info("Closing open position before shutdown...")
            market_data = self.get_market_data()
            if market_data:
                self.execute_trade('SELL', market_data)

        # Print performance summary
        self.print_performance_summary()
        logger.info("Trading bot stopped")

    def print_performance_summary(self):
        """Print performance summary"""
        logger.info("=== PERFORMANCE SUMMARY ===")
        logger.info(f"Total trades executed: {len(self.trades_executed)}")
        logger.info(f"Total P&L: {self.total_pnl:.2f} {self.config.quote_currency}")
        logger.info(f"Daily trades: {self.risk_manager.daily_trades}")
        logger.info(f"Daily P&L: {self.risk_manager.daily_pnl:.2f}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global bot
    if 'bot' in globals():
        bot.stop()
    sys.exit(0)

def main():
    """Main function to run the trading bot"""
    global bot

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Configure your trading parameters here
    config = TradingConfig(
        base_currency="BTC",
        quote_currency="USDC",
        trade_amount_usd=100.0,
        check_interval=30  # Check every 5 minutes
    )

    # Create and start the trading bot
    bot = TradingBot(config)

    try:
        bot.run_trading_loop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        if bot:
            bot.stop()

if __name__ == "__main__":
    main()
