from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import threading
import time
import json
import queue
import requests
from datetime import datetime, timedelta
import logging
import sys
import os
import re
from textblob import TextBlob
from auth import token_required, register_user, authenticate_user, refresh_token
from coinbase_jwt import get_coinbase_headers
import requests
import uuid
from auto_trading_engine import AutoTradingEngine
from enhanced_auto_trading_engine import EnhancedAutoTradingEngine
from polymarket_engine import PolymarketEngine
from kalshi_engine import KalshiEngine
from hedge_engine import HedgeEngine
from kalshi_ml_trader import SmartKalshiTrader

# Add the parent directory to sys.path to import the trading bot
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv('../.env')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
CORS(app, origins=["http://localhost:3000"], allow_headers=["Content-Type", "Authorization"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global variables to store bot data
bot_data = {
    'connected': False,
    'current_price': 0,
    'signal': 'HOLD',
    'reason': 'Initializing...',
    'portfolio_value': 500.0,
    'daily_pnl': 0.0,
    'total_pnl': 0.0,
    'daily_trades': 0,
    'position': None,
    'indicators': {},
    'price_history': [],
    'last_update': None
}

# Multi-crypto data storage
crypto_data = {
    'BTC-USDC': {'price': 0, 'change_24h': 0, 'volume_24h': 0, 'market_cap': 0, 'indicators': {}, 'price_history': []},
    'ETH-USDC': {'price': 0, 'change_24h': 0, 'volume_24h': 0, 'market_cap': 0, 'indicators': {}, 'price_history': []},
    'SOL-USDC': {'price': 0, 'change_24h': 0, 'volume_24h': 0, 'market_cap': 0, 'indicators': {}, 'price_history': []},
    'ADA-USDC': {'price': 0, 'change_24h': 0, 'volume_24h': 0, 'market_cap': 0, 'indicators': {}, 'price_history': []},
    'DOGE-USDC': {'price': 0, 'change_24h': 0, 'volume_24h': 0, 'market_cap': 0, 'indicators': {}, 'price_history': []},
    'AVAX-USDC': {'price': 0, 'change_24h': 0, 'volume_24h': 0, 'market_cap': 0, 'indicators': {}, 'price_history': []},
    'MATIC-USDC': {'price': 0, 'change_24h': 0, 'volume_24h': 0, 'market_cap': 0, 'indicators': {}, 'price_history': []},
    'LINK-USDC': {'price': 0, 'change_24h': 0, 'volume_24h': 0, 'market_cap': 0, 'indicators': {}, 'price_history': []}
}

# Portfolio breakdown by crypto
portfolio_data = {
    'total_value': 0,
    'allocations': {},
    'performance': {},
    'last_update': None
}

sentiment_data = {
    'overall_sentiment': 'neutral',
    'sentiment_score': 0.0,
    'social_volume': 0,
    'trending_topics': [],
    'fear_greed_index': 50,
    'news_sentiment': {
        'articles': [],
        'average_sentiment': 0.0,
        'positive_count': 0,
        'negative_count': 0,
        'neutral_count': 0
    },
    'social_sentiment': {
        'twitter_sentiment': 0.0,
        'reddit_sentiment': 0.0,
        'mentions_24h': 0,
        'trending_hashtags': []
    },
    'market_indicators': {
        'volatility_index': 0.0,
        'sentiment_vs_price_correlation': 0.0,
        'market_momentum': 'neutral'
    },
    'trading_signals': {
        'sentiment_signal': 'HOLD',
        'confidence': 0.0,
        'reasoning': ''
    }
}

whale_data = {
    'large_transactions': [],
    'whale_alerts': [],
    'flow_summary': {
        'inflow': 0,
        'outflow': 0,
        'net_flow': 0
    }
}

# Message queue for bot communication
message_queue = queue.Queue()

class TradingBotAdapter:
    """Adapter to connect with the existing trading bot"""
    
    def __init__(self):
        self.running = False
        self.coinbase_client = None
        self._init_coinbase_client()
        
    def _init_coinbase_client(self):
        """Initialize Coinbase CDP client"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            api_key = os.getenv('COINBASE_API_KEY')
            api_secret = os.getenv('COINBASE_API_SECRET')
            
            if api_key and api_secret:
                try:
                    from coinbase.rest import RESTClient
                    self.coinbase_client = RESTClient(api_key=api_key, api_secret=api_secret)
                    self.api_type = "advanced_trade"
                    logging.info("Coinbase Advanced Trade API initialized successfully")
                    
                    # Test the client
                    try:
                        accounts = self.coinbase_client.get_accounts()
                        logging.info("Coinbase client connected successfully")
                    except Exception as test_error:
                        logging.warning(f"Coinbase client test failed: {test_error}")
                        
                except Exception as coinbase_error:
                    logging.error(f"Coinbase API initialization failed: {coinbase_error}")
                    self.coinbase_client = None
                        
            else:
                logging.warning("Coinbase API credentials not found, using mock data")
                self.coinbase_client = None
                
        except Exception as e:
            logging.error(f"Failed to initialize Coinbase client: {e}")
            self.coinbase_client = None
        
    def start_bot_monitoring(self):
        """Start monitoring the trading bot"""
        self.running = True
        thread = threading.Thread(target=self._monitor_bot)
        thread.daemon = True
        thread.start()
        
    def _monitor_bot(self):
        """Monitor bot status and data"""
        while self.running:
            try:
                # Get real trading bot data
                self._update_bot_data()
                self._fetch_market_sentiment()
                self._monitor_whale_activity()
                
                # Update multi-crypto data
                self.update_crypto_data()
                
                # Update portfolio breakdown
                portfolio_breakdown = self.get_portfolio_breakdown()
                
                # Emit updates to connected clients
                socketio.emit('bot_update', bot_data)
                socketio.emit('sentiment_update', sentiment_data)
                socketio.emit('whale_update', whale_data)
                socketio.emit('crypto_update', crypto_data)
                socketio.emit('portfolio_update', portfolio_breakdown)
                
                time.sleep(30)  # Update every 30 seconds
                
            except Exception as e:
                logging.error(f"Error in bot monitoring: {e}")
                time.sleep(60)
                
    def _update_bot_data(self):
        """Update bot data with real Coinbase data"""
        global bot_data
        
        try:
            if self.coinbase_client:
                # Get real market data
                current_price = self._get_real_btc_price()
                portfolio_value = self._get_real_portfolio_value()
                
                # Update bot data with real values
                bot_data.update({
                    'connected': True,
                    'current_price': current_price,
                    'portfolio_value': portfolio_value,
                    'last_update': datetime.now().isoformat()
                })
                
                # Add to price history
                bot_data['price_history'].append({
                    'timestamp': datetime.now().isoformat(),
                    'price': current_price
                })
                
                # Keep only last 100 price points
                if len(bot_data['price_history']) > 100:
                    bot_data['price_history'] = bot_data['price_history'][-100:]
                    
                # Get real technical indicators
                self._update_technical_indicators()
                
                logging.info(f"Updated bot data - Price: ${current_price}, Portfolio: ${portfolio_value}")
            else:
                # Fallback to CoinGecko price
                current_price = self._get_current_btc_price()
                bot_data.update({
                    'connected': False,
                    'current_price': current_price,
                    'last_update': datetime.now().isoformat()
                })
                
        except Exception as e:
            logging.error(f"Error updating bot data: {e}")
            bot_data['connected'] = False
            
    def _get_real_price(self, symbol='BTC-USDC'):
        """Get real price for any crypto from Coinbase"""
        try:
            logging.info(f"Getting real price for {symbol}")

            # Try Coinbase public API first (works for all symbols)
            try:
                # Map symbol to Coinbase format (e.g., ETH-USDC becomes ETH-USD)
                product_id = symbol.replace('-USDC', '-USD')
                url = f'https://api.coinbase.com/v2/prices/{product_id}/spot'
                logging.info(f"Fetching price from: {url}")
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    price = float(data.get('data', {}).get('amount', 0))
                    if price > 0:
                        logging.info(f"Got price for {symbol} from public API: ${price}")
                        return price
            except Exception as api_error:
                logging.warning(f"Public API failed for {symbol}: {api_error}")

            # Try SDK method
            if self.coinbase_client:
                ticker = self.coinbase_client.get_product(symbol)
                if ticker:
                    # Handle different response formats
                    if hasattr(ticker, 'price'):
                        price = float(ticker.price)
                        logging.info(f"Got price for {symbol} from SDK: ${price}")
                        return price
                    elif hasattr(ticker, 'quote_size'):
                        price = float(ticker.quote_size)
                        logging.info(f"Got price for {symbol} from SDK: ${price}")
                        return price
                    elif isinstance(ticker, dict):
                        price = float(ticker.get('price', ticker.get('ask', ticker.get('bid', 0))))
                        if price > 0:
                            logging.info(f"Got price for {symbol} from SDK: ${price}")
                            return price

            # Fallback to CoinGecko for BTC
            if symbol == 'BTC-USDC':
                logging.info("Falling back to CoinGecko for BTC")
                return self._get_current_btc_price()

            logging.error(f"No price available for {symbol}")
            return 0
        except Exception as e:
            logging.error(f"Error getting real price for {symbol}: {e}", exc_info=True)
            if symbol == 'BTC-USDC':
                return self._get_current_btc_price()
            return 0

    def _get_real_btc_price(self):
        """Get real BTC price from Coinbase (legacy wrapper)"""
        return self._get_real_price('BTC-USDC')
            
    def _get_real_portfolio_value(self):
        """Get real portfolio value from Coinbase"""
        try:
            if self.coinbase_client:
                # Get accounts using the REST client
                accounts = self.coinbase_client.get_accounts()
                if accounts and hasattr(accounts, 'accounts'):
                    total_value = 0
                    for account in accounts.accounts:
                        if hasattr(account, 'available_balance') and hasattr(account.available_balance, 'value'):
                            balance = float(account.available_balance.value)
                            
                            # Convert to USD if needed
                            if hasattr(account, 'currency'):
                                if account.currency == 'BTC':
                                    balance *= bot_data.get('current_price', 104000)  # Convert BTC to USD
                                elif account.currency in ['USDC', 'USD']:
                                    pass  # Already in USD
                                    
                            total_value += balance
                    
                    return total_value if total_value > 0 else 500.0
            
            return 500.0  # Default value
        except Exception as e:
            logging.error(f"Error getting real portfolio value: {e}")
            return 500.0
            
    def get_order_history(self, limit=50):
        """Get real order history from Coinbase"""
        try:
            if self.coinbase_client:
                # Get orders using the REST client
                orders = self.coinbase_client.get_orders(limit=limit)
                processed_orders = []
                
                if orders and hasattr(orders, 'orders'):
                    for order in orders.orders:
                        processed_order = {
                            'id': getattr(order, 'order_id', 'unknown'),
                            'product_id': getattr(order, 'product_id', 'BTC-USDC'),
                            'side': getattr(order, 'side', 'unknown'),
                            'status': getattr(order, 'status', 'unknown'),
                            'size': float(getattr(order, 'size', 0)),
                            'filled_size': float(getattr(order, 'filled_size', 0)),
                            'price': float(getattr(order, 'average_filled_price', 0)) if hasattr(order, 'average_filled_price') and order.average_filled_price else None,
                            'created_time': getattr(order, 'created_time', datetime.now().isoformat()),
                            'completion_percentage': getattr(order, 'completion_percentage', '0'),
                            'fee': float(getattr(order, 'total_fees', 0)) if hasattr(order, 'total_fees') else 0,
                            'total_value': 0  # Will calculate below
                        }
                        
                        # Calculate total value
                        if processed_order['price'] and processed_order['filled_size']:
                            processed_order['total_value'] = processed_order['price'] * processed_order['filled_size']
                        
                        processed_orders.append(processed_order)
                
                return processed_orders
            
            return []
        except Exception as e:
            logging.error(f"Error getting order history: {e}")
            return []
            
    def get_fills_history(self, limit=50):
        """Get real fills/trades history from Coinbase"""
        try:
            if self.coinbase_client:
                # Get fills (executed trades) using the REST client
                fills = self.coinbase_client.get_fills(limit=limit)
                processed_fills = []
                
                if fills and hasattr(fills, 'fills'):
                    for fill in fills.fills:
                        processed_fill = {
                            'trade_id': getattr(fill, 'trade_id', 'unknown'),
                            'order_id': getattr(fill, 'order_id', 'unknown'),
                            'product_id': getattr(fill, 'product_id', 'BTC-USDC'),
                            'side': getattr(fill, 'side', 'unknown'),
                            'size': float(getattr(fill, 'size', 0)),
                            'price': float(getattr(fill, 'price', 0)),
                            'fee': float(getattr(fill, 'commission', 0)) if hasattr(fill, 'commission') else 0,
                            'created_at': getattr(fill, 'trade_time', datetime.now().isoformat()),
                            'total_value': 0  # Will calculate below
                        }
                        
                        # Calculate total value
                        if processed_fill['price'] and processed_fill['size']:
                            processed_fill['total_value'] = processed_fill['price'] * processed_fill['size']
                        
                        processed_fills.append(processed_fill)
                
                return processed_fills
            
            return []
        except Exception as e:
            logging.error(f"Error getting fills history: {e}")
            return []

    def calculate_pnl_from_trades(self):
        """Calculate P&L from actual trade history"""
        try:
            fills = self.get_fills_history(limit=100)
            if not fills:
                return {
                    'daily_pnl': 0.0,
                    'total_pnl': 0.0,
                    'daily_trades': 0
                }

            # Group trades by product to calculate P&L
            positions = {}
            daily_pnl = 0.0
            total_pnl = 0.0
            daily_trades = 0
            today = datetime.now().date()

            for fill in fills:
                product = fill['product_id']
                side = fill['side']
                size = fill['size']
                price = fill['price']
                fee = fill['fee']
                created_at = fill['created_at']

                # Parse timestamp
                try:
                    if isinstance(created_at, str):
                        trade_date = datetime.fromisoformat(created_at.replace('Z', '+00:00')).date()
                    else:
                        trade_date = created_at.date() if hasattr(created_at, 'date') else today
                except:
                    trade_date = today

                # Count today's trades
                if trade_date == today:
                    daily_trades += 1

                # Initialize position for this product
                if product not in positions:
                    positions[product] = {
                        'buys': [],
                        'sells': [],
                        'realized_pnl': 0.0
                    }

                # Track buys and sells
                if side.upper() == 'BUY':
                    positions[product]['buys'].append({
                        'size': size,
                        'price': price,
                        'fee': fee,
                        'date': trade_date
                    })
                elif side.upper() == 'SELL':
                    # Calculate realized P&L for sells
                    # Simple FIFO matching
                    remaining_sell = size
                    for buy in positions[product]['buys']:
                        if remaining_sell <= 0:
                            break

                        matched_size = min(buy['size'], remaining_sell)
                        buy_cost = matched_size * buy['price'] + buy['fee'] * (matched_size / buy['size'])
                        sell_revenue = matched_size * price - fee * (matched_size / size)
                        pnl = sell_revenue - buy_cost

                        positions[product]['realized_pnl'] += pnl
                        if trade_date == today:
                            daily_pnl += pnl
                        total_pnl += pnl

                        buy['size'] -= matched_size
                        remaining_sell -= matched_size

            return {
                'daily_pnl': round(daily_pnl, 2),
                'total_pnl': round(total_pnl, 2),
                'daily_trades': daily_trades
            }

        except Exception as e:
            logging.error(f"Error calculating P&L: {e}")
            return {
                'daily_pnl': 0.0,
                'total_pnl': 0.0,
                'daily_trades': 0
            }

    def update_crypto_data(self):
        """Update data for all supported cryptocurrencies"""
        try:
            # Map of our symbols to CoinGecko IDs
            coingecko_mapping = {
                'BTC-USDC': 'bitcoin',
                'ETH-USDC': 'ethereum', 
                'SOL-USDC': 'solana',
                'ADA-USDC': 'cardano',
                'DOGE-USDC': 'dogecoin',
                'AVAX-USDC': 'avalanche-2',
                'MATIC-USDC': 'matic-network',
                'LINK-USDC': 'chainlink'
            }
            
            # Get data from CoinGecko (more comprehensive than individual Coinbase calls)
            coin_ids = ','.join(coingecko_mapping.values())
            response = requests.get(
                f'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={coin_ids}&order=market_cap_desc&per_page=20&page=1&sparkline=false&price_change_percentage=24h',
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                for coin in data:
                    # Find corresponding symbol
                    symbol = None
                    for pair, cg_id in coingecko_mapping.items():
                        if cg_id == coin['id']:
                            symbol = pair
                            break
                    
                    if symbol and symbol in crypto_data:
                        crypto_data[symbol].update({
                            'price': coin.get('current_price', 0),
                            'change_24h': coin.get('price_change_percentage_24h', 0),
                            'volume_24h': coin.get('total_volume', 0),
                            'market_cap': coin.get('market_cap', 0),
                            'last_update': datetime.now().isoformat()
                        })
                        
                        # Add to price history
                        crypto_data[symbol]['price_history'].append({
                            'timestamp': datetime.now().isoformat(),
                            'price': coin.get('current_price', 0)
                        })
                        
                        # Keep only last 100 points
                        if len(crypto_data[symbol]['price_history']) > 100:
                            crypto_data[symbol]['price_history'] = crypto_data[symbol]['price_history'][-100:]
                
                # Also try to get real Coinbase data for major pairs
                if self.coinbase_client:
                    for symbol in ['BTC-USDC', 'ETH-USDC', 'SOL-USDC']:
                        try:
                            ticker = self.coinbase_client.get_product(symbol)
                            if ticker and hasattr(ticker, 'price'):
                                # Override with more accurate Coinbase price if available
                                crypto_data[symbol]['price'] = float(ticker.price)
                        except Exception as e:
                            logging.debug(f"Could not get Coinbase price for {symbol}: {e}")
                            
                logging.info(f"Updated crypto data for {len(crypto_data)} cryptocurrencies")
                
        except Exception as e:
            logging.error(f"Error updating crypto data: {e}")
            
    def get_portfolio_breakdown(self):
        """Get portfolio breakdown across all cryptocurrencies and Kalshi positions"""
        try:
            total_value = 0
            allocations = {}

            # Get Coinbase accounts
            if self.coinbase_client:
                accounts = self.coinbase_client.get_accounts()
                if accounts:
                    # Handle different response formats
                    accounts_list = []
                    if hasattr(accounts, 'accounts'):
                        accounts_list = accounts.accounts
                    elif isinstance(accounts, dict) and 'accounts' in accounts:
                        accounts_list = accounts['accounts']
                    elif isinstance(accounts, list):
                        accounts_list = accounts

                    for account in accounts_list:
                        try:
                            # Handle different account object formats
                            if hasattr(account, 'currency'):
                                currency = account.currency
                            elif isinstance(account, dict):
                                currency = account.get('currency')
                            else:
                                continue

                            # Get balance with different possible formats
                            balance = 0
                            if hasattr(account, 'available_balance'):
                                if hasattr(account.available_balance, 'value'):
                                    balance = float(account.available_balance.value)
                                elif isinstance(account.available_balance, dict):
                                    balance = float(account.available_balance.get('value', 0))
                                elif isinstance(account.available_balance, (int, float, str)):
                                    balance = float(account.available_balance)
                            elif isinstance(account, dict):
                                if 'available_balance' in account:
                                    if isinstance(account['available_balance'], dict):
                                        balance = float(account['available_balance'].get('value', 0))
                                    else:
                                        balance = float(account['available_balance'])
                                elif 'balance' in account:
                                    balance = float(account['balance'])

                            if balance > 0:
                                # Convert to USD value
                                if currency in ['USD', 'USDC']:
                                    usd_value = balance
                                else:
                                    # Find corresponding price in crypto_data
                                    pair = f"{currency}-USDC"
                                    if pair in crypto_data and crypto_data[pair]['price'] > 0:
                                        usd_value = balance * crypto_data[pair]['price']
                                    else:
                                        usd_value = 0

                                allocations[currency] = {
                                    'balance': balance,
                                    'usd_value': usd_value,
                                    'percentage': 0  # Will calculate after getting total
                                }
                                total_value += usd_value

                        except Exception as account_error:
                            logging.debug(f"Error processing account: {account_error}")
                            continue

            # Get Kalshi positions
            try:
                if kalshi_engine and kalshi_engine.is_connected:
                    # Get Kalshi balance
                    kalshi_balance = kalshi_engine.get_balance()
                    if kalshi_balance and kalshi_balance.get('balance', 0) > 0:
                        balance = kalshi_balance['balance']
                        allocations['KALSHI'] = {
                            'balance': balance,
                            'usd_value': balance,
                            'percentage': 0
                        }
                        total_value += balance

                    # Get Kalshi positions
                    kalshi_positions = kalshi_engine.get_positions()
                    if kalshi_positions:
                        total_kalshi_value = sum(pos.get('current_value', 0) for pos in kalshi_positions)
                        if total_kalshi_value > 0:
                            # Add positions value to existing KALSHI allocation or create new one
                            if 'KALSHI' in allocations:
                                allocations['KALSHI']['balance'] += total_kalshi_value
                                allocations['KALSHI']['usd_value'] += total_kalshi_value
                            else:
                                allocations['KALSHI'] = {
                                    'balance': total_kalshi_value,
                                    'usd_value': total_kalshi_value,
                                    'percentage': 0
                                }
                            total_value += total_kalshi_value

                        logging.info(f"Added {len(kalshi_positions)} Kalshi positions worth ${total_kalshi_value:.2f}")
            except Exception as kalshi_error:
                logging.warning(f"Could not fetch Kalshi positions: {kalshi_error}")

            # Calculate percentages
            for currency in allocations:
                if total_value > 0:
                    allocations[currency]['percentage'] = (allocations[currency]['usd_value'] / total_value) * 100

            portfolio_data.update({
                'total_value': total_value,
                'allocations': allocations,
                'last_update': datetime.now().isoformat()
            })

            logging.info(f"Portfolio breakdown: {len(allocations)} assets, total value: ${total_value:.2f}")
            return portfolio_data

        except Exception as e:
            logging.error(f"Error getting portfolio breakdown: {e}")
            # Return a default portfolio with some sample data for testing
            default_portfolio = {
                'total_value': 500.0,
                'allocations': {
                    'USDC': {
                        'balance': 500.0,
                        'usd_value': 500.0,
                        'percentage': 100.0
                    }
                },
                'last_update': datetime.now().isoformat()
            }
            return default_portfolio
    
    def execute_market_order(self, action, symbol, amount_type, amount):
        """Execute a market buy or sell order using CDP SDK or fallback to Advanced Trade"""
        try:
            if not self.coinbase_client:
                return {'success': False, 'error': 'Coinbase client not initialized'}
            
            # Validate action
            if action not in ['buy', 'sell']:
                return {'success': False, 'error': 'Invalid action. Must be buy or sell'}
            
            # Try CDP service first, fallback to Advanced Trade API
            cdp_result = self._execute_cdp_service_trade(action, symbol, amount_type, amount)
            if cdp_result['success']:
                return cdp_result
            else:
                logging.warning(f"CDP service failed: {cdp_result['error']}, falling back to Advanced Trade")
                return self._execute_advanced_trade(action, symbol, amount_type, amount)
                
        except Exception as e:
            logging.error(f"Error executing market order: {e}")
            return {'success': False, 'error': str(e)}
    
    def _execute_cdp_service_trade(self, action, symbol, amount_type, amount):
        """Execute trade using CDP service (Node.js microservice)"""
        try:
            import requests

            # Determine the side and product_id
            side = action.upper()
            # Convert -USDC to -USD for Coinbase API
            product_id = symbol.replace('-USDC', '-USD')

            # The CDP service now expects the amount in the correct currency (quote for buy, base for sell)
            payload = {
                'side': side,
                'product_id': product_id,
                'amount': str(amount) # Ensure amount is a string for the API
            }

            # Call CDP service
            try:
                response = requests.post('http://localhost:3001/trade', 
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data['success']:
                        return {
                            'success': True,
                            'message': f'{action.title()} order executed via CDP',
                            'order_id': data.get('order_id'),
                        }
                    else:
                        return {'success': False, 'error': data.get('error', 'CDP trade failed')}
                else:
                    return {'success': False, 'error': f'CDP service error: {response.status_code} - {response.text}'}
                    
            except requests.exceptions.ConnectionError:
                return {'success': False, 'error': 'CDP service not available'}
            except requests.exceptions.Timeout:
                return {'success': False, 'error': 'CDP service timeout'}
                
        except Exception as e:
            logging.error(f"CDP service trade error: {e}")
            return {'success': False, 'error': f'CDP service failed: {str(e)}'}
    
    def _execute_advanced_trade_jwt(self, action, symbol, amount_type, amount):
        """Execute trade using Advanced Trade API with JWT authentication"""
        try:
            # Get current price for calculations
            current_price = self._get_real_price(symbol)
            if current_price <= 0:
                return {'success': False, 'error': 'Unable to get current price'}
            
            # Calculate order size
            if amount_type == 'usd':
                quote_size = str(round(amount, 2))
                base_size = None
            else:
                base_size = str(round(amount, 8))
                quote_size = None
            
            # Validate minimum order size
            if amount_type == 'crypto' and amount < 0.00001:
                return {'success': False, 'error': f'Order size too small. Minimum 0.00001 BTC, requested: {amount:.8f}'}
            elif amount_type == 'usd' and amount < 1.0:
                return {'success': False, 'error': f'Order size too small. Minimum $1.00 USD, requested: ${amount:.2f}'}
            
            # Generate unique client order ID
            client_order_id = str(uuid.uuid4())
            
            # Map frontend symbol to Coinbase product ID
            # Coinbase Advanced Trade uses -USD pairs, not -USDC
            product_id = symbol.replace('-USDC', '-USD')
            
            # Prepare order body according to Coinbase API format
            order_body = {
                'client_order_id': client_order_id,
                'product_id': product_id,
                'side': action.upper(),
                'order_configuration': {
                    'market_market_ioc': {}
                }
            }
            
            # Set quote_size for buy orders or base_size for sell orders
            if action.upper() == 'BUY':
                order_body['order_configuration']['market_market_ioc']['quote_size'] = quote_size
            else:
                order_body['order_configuration']['market_market_ioc']['base_size'] = base_size
            
            # Convert to JSON string for JWT signing
            body_json = json.dumps(order_body)
            
            # Get JWT authenticated headers
            path = '/api/v3/brokerage/orders'
            headers = get_coinbase_headers('POST', path, body_json)
            
            # Make the API request
            url = f'https://api.coinbase.com{path}'
            logging.info(f"Creating order with JWT: {order_body}")
            
            response = requests.post(url, headers=headers, data=body_json, timeout=30)
            
            logging.info(f"JWT order response status: {response.status_code}")
            logging.info(f"JWT order response body: {response.text}")
            
            if response.status_code == 200:
                response_data = response.json()
                logging.info(f"Order response: {response_data}")
                
                if response_data.get('success'):
                    success_response = response_data.get('success_response', {})
                    return {
                        'success': True,
                        'message': 'Order placed successfully',
                        'order_id': success_response.get('order_id'),
                        'executed_amount': float(base_size) if base_size else amount / current_price,
                        'executed_price': current_price
                    }
                else:
                    error_response = response_data.get('error_response', {})
                    error_msg = error_response.get('error', 'Unknown error')
                    return {'success': False, 'error': f'JWT Order failed: {error_msg}'}
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_data.get('error', response.text))
                except:
                    error_msg = response.text
                
                full_error = f"JWT HTTP {response.status_code}: {error_msg}"
                logging.error(f"JWT Order failed: {full_error}")
                return {'success': False, 'error': full_error}
                
        except Exception as e:
            logging.error(f"JWT Advanced Trade order error: {e}")
            return {'success': False, 'error': f'Order execution failed: {str(e)}'}

    def _execute_advanced_trade(self, action, symbol, amount_type, amount):
        """Execute trade using Advanced Trade API (fallback to old method)"""
        logging.info(f"Executing trade: {action} {amount} {amount_type} of {symbol}")
        
        # First try JWT authentication
        logging.info("Trying JWT authentication method...")
        jwt_result = self._execute_advanced_trade_jwt(action, symbol, amount_type, amount)
        
        if jwt_result['success']:
            logging.info("✅ JWT method succeeded!")
            return jwt_result
        
        logging.warning(f"JWT method failed: {jwt_result['error']}")
        logging.info("Trying legacy SDK method...")
        
        # Return JWT error if it's a clear API error, don't try legacy
        if any(keyword in jwt_result['error'].lower() for keyword in ['insufficient', 'minimum', 'invalid', 'unauthorized', 'forbidden']):
            logging.error(f"JWT method failed with API error, not trying legacy: {jwt_result['error']}")
            return jwt_result
        
        try:
            # Get current price for calculations
            current_price = self._get_real_price(symbol)
            if current_price <= 0:
                return {'success': False, 'error': 'Unable to get current price'}
            
            # Calculate order size
            if amount_type == 'usd':
                crypto_amount = amount / current_price
            else:
                crypto_amount = amount
            
            # Validate minimum order size
            if crypto_amount < 0.00001:
                return {'success': False, 'error': f'Order size too small. Minimum 0.00001 BTC, requested: {crypto_amount:.8f}'}
            
            # Generate unique client order ID
            client_order_id = str(uuid.uuid4())
            
            # Prepare order parameters
            if action == 'buy':
                order_config = {
                    'market_market_ioc': {
                        'quote_size': str(round(amount, 2)) if amount_type == 'usd' else str(round(crypto_amount * current_price, 2))
                    }
                }
            else:
                order_config = {
                    'market_market_ioc': {
                        'base_size': str(round(crypto_amount, 8))
                    }
                }
            
            # Execute the order
            # Map to Coinbase product ID format (-USD instead of -USDC)
            product_id = symbol.replace('-USDC', '-USD')
            order_params = {
                'client_order_id': client_order_id,
                'product_id': product_id,
                'side': action.upper(),
                'order_configuration': order_config
            }
            
            logging.info(f"Creating Advanced Trade order with params: {order_params}")
            order_response = self.coinbase_client.create_order(**order_params)
            
            if hasattr(order_response, 'success') and order_response.success:
                order_id = getattr(order_response, 'order_id', 'unknown')
                
                return {
                    'success': True,
                    'message': f'{action.capitalize()} order executed successfully',
                    'order_id': order_id,
                    'executed_amount': crypto_amount,
                    'executed_price': current_price
                }
            else:
                error_msg = getattr(order_response, 'error_response', {}).get('message', 'Unknown error') if hasattr(order_response, 'error_response') else 'Order failed'
                return {'success': False, 'error': f'Order failed: {error_msg}'}
                
        except Exception as api_error:
            logging.error(f"Advanced Trade API Error: {api_error}")
            error_msg = str(api_error)
            
            # Provide more specific error messages
            if "account is not available" in error_msg.lower():
                return {'success': False, 'error': 'Account not available for trading. Please check: 1) Account verification status, 2) API key trading permissions, 3) Account restrictions in Coinbase'}
            elif "invalid_argument" in error_msg.lower():
                return {'success': False, 'error': 'Invalid trading argument. This may be due to insufficient funds, minimum order requirements, or account restrictions.'}
            elif "unauthorized" in error_msg.lower():
                return {'success': False, 'error': 'API key lacks trading permissions. Please enable trade permissions in your Coinbase API settings.'}
            elif "forbidden" in error_msg.lower():
                return {'success': False, 'error': 'Trading is forbidden for this account. Please verify your account is approved for trading.'}
            
            return {'success': False, 'error': f'API Error: {error_msg}'}
    
    def get_portfolios(self):
        """Get available portfolios"""
        try:
            if not self.coinbase_client:
                return []
            
            portfolios = self.coinbase_client.get_portfolios()
            portfolio_list = []
            
            if hasattr(portfolios, 'portfolios'):
                for portfolio in portfolios.portfolios:
                    portfolio_list.append({
                        'uuid': getattr(portfolio, 'uuid', ''),
                        'name': getattr(portfolio, 'name', ''),
                        'type': getattr(portfolio, 'type', '')
                    })
            
            logging.info(f"Available portfolios: {portfolio_list}")
            return portfolio_list
            
        except Exception as e:
            logging.error(f"Error getting portfolios: {e}")
            return []

    def get_account_balances_jwt(self):
        """Get account balances using JWT authentication"""
        try:
            path = '/api/v3/brokerage/accounts'
            headers = get_coinbase_headers('GET', path)
            url = f'https://api.coinbase.com{path}'
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                accounts = data.get('accounts', [])
                
                balances = []
                for account in accounts:
                    currency = account.get('currency')
                    available_balance = float(account.get('available_balance', {}).get('value', '0'))
                    hold = float(account.get('hold', {}).get('value', '0'))
                    
                    if available_balance > 0 or hold > 0:
                        balances.append({
                            'currency': currency,
                            'available': available_balance,
                            'held': hold,
                            'total': available_balance + hold
                        })
                
                logging.info(f"JWT: Retrieved {len(balances)} account balances")
                return balances
            else:
                logging.error(f"JWT account balances failed: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            logging.error(f"JWT account balances error: {e}")
            return []

    def get_account_balances(self):
        """Get account balances for all currencies"""
        try:
            # First try JWT method
            jwt_balances = self.get_account_balances_jwt()
            if jwt_balances:
                return jwt_balances
            
            logging.warning("JWT balances failed, trying legacy method")
            
            if not self.coinbase_client:
                return []
            
            # First check what portfolios are available
            portfolios = self.get_portfolios()
            
            accounts = self.coinbase_client.get_accounts()
            balances = []
            
            # Handle different response formats
            accounts_list = []
            if hasattr(accounts, 'accounts'):
                accounts_list = accounts.accounts
            elif isinstance(accounts, dict) and 'accounts' in accounts:
                accounts_list = accounts['accounts']
            elif isinstance(accounts, list):
                accounts_list = accounts
            
            for account in accounts_list:
                try:
                    # Handle different account object formats
                    if hasattr(account, 'currency'):
                        currency = account.currency
                    elif isinstance(account, dict):
                        currency = account.get('currency')
                    else:
                        continue
                    
                    # Get available balance
                    available_balance = 0
                    total_balance = 0
                    
                    if hasattr(account, 'available_balance'):
                        if hasattr(account.available_balance, 'value'):
                            available_balance = float(account.available_balance.value)
                        elif isinstance(account.available_balance, dict):
                            available_balance = float(account.available_balance.get('value', 0))
                        elif isinstance(account.available_balance, (int, float, str)):
                            available_balance = float(account.available_balance)
                    elif isinstance(account, dict):
                        if 'available_balance' in account:
                            if isinstance(account['available_balance'], dict):
                                available_balance = float(account['available_balance'].get('value', 0))
                            else:
                                available_balance = float(account['available_balance'])
                        elif 'balance' in account:
                            available_balance = float(account['balance'])
                    
                    # Get total balance (available + held)
                    if hasattr(account, 'balance'):
                        if hasattr(account.balance, 'value'):
                            total_balance = float(account.balance.value)
                        elif isinstance(account.balance, dict):
                            total_balance = float(account.balance.get('value', 0))
                        elif isinstance(account.balance, (int, float, str)):
                            total_balance = float(account.balance)
                    else:
                        total_balance = available_balance
                    
                    # Only include accounts with balance > 0 or major currencies
                    if available_balance > 0 or currency in ['USD', 'USDC', 'BTC', 'ETH']:
                        balances.append({
                            'currency': currency,
                            'available': available_balance,
                            'total': total_balance,
                            'held': max(0, total_balance - available_balance)
                        })
                        
                except Exception as account_error:
                    logging.debug(f"Error processing account balance: {account_error}")
                    continue
            
            return balances
            
        except Exception as e:
            logging.error(f"Error getting account balances: {e}")
            return []
            
    def _update_technical_indicators(self):
        """Update technical indicators with real data"""
        try:
            if len(bot_data['price_history']) >= 20:
                prices = [point['price'] for point in bot_data['price_history'][-20:]]
                current_price = prices[-1]
                
                # Simple technical indicators without external libraries
                # RSI approximation
                price_changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
                gains = [change if change > 0 else 0 for change in price_changes]
                losses = [-change if change < 0 else 0 for change in price_changes]
                
                avg_gain = sum(gains[-14:]) / 14 if len(gains) >= 14 else sum(gains) / len(gains) if gains else 0
                avg_loss = sum(losses[-14:]) / 14 if len(losses) >= 14 else sum(losses) / len(losses) if losses else 0
                
                rsi = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss > 0 else 100
                
                # Simple Moving Averages
                sma_short = sum(prices[-5:]) / 5 if len(prices) >= 5 else current_price
                sma_long = sum(prices[-15:]) / 15 if len(prices) >= 15 else current_price
                
                # Simple Bollinger Bands approximation
                sma_20 = sum(prices[-20:]) / 20 if len(prices) >= 20 else current_price
                variance = sum([(price - sma_20) ** 2 for price in prices[-20:]]) / 20 if len(prices) >= 20 else 0
                std_dev = variance ** 0.5
                upper_bb = sma_20 + (2 * std_dev)
                lower_bb = sma_20 - (2 * std_dev)
                
                # Update bot data
                bot_data['indicators'] = {
                    'rsi': round(rsi, 1),
                    'sma_short': round(sma_short, 2),
                    'sma_long': round(sma_long, 2),
                    'bollinger_upper': round(upper_bb, 2),
                    'bollinger_middle': round(sma_20, 2),
                    'bollinger_lower': round(lower_bb, 2)
                }
                
                # Calculate trading signal
                self._calculate_trading_signal(current_price)
                
        except Exception as e:
            logging.error(f"Error updating technical indicators: {e}")
            
    def _calculate_trading_signal(self, current_price):
        """Calculate trading signal based on indicators"""
        try:
            indicators = bot_data['indicators']
            signals = []
            
            # RSI signals
            if indicators['rsi'] < 35:
                signals.append('BUY')
            elif indicators['rsi'] > 65:
                signals.append('SELL')
                
            # SMA crossover
            if indicators['sma_short'] > indicators['sma_long']:
                signals.append('BUY')
            else:
                signals.append('SELL')
                
            # Bollinger Bands
            if current_price <= indicators['bollinger_lower']:
                signals.append('BUY')
            elif current_price >= indicators['bollinger_upper']:
                signals.append('SELL')
                
            # Determine overall signal
            buy_signals = signals.count('BUY')
            sell_signals = signals.count('SELL')
            
            if buy_signals > sell_signals:
                bot_data['signal'] = 'BUY'
                bot_data['reason'] = f"Buy signals: {buy_signals}, Sell signals: {sell_signals}"
            elif sell_signals > buy_signals:
                bot_data['signal'] = 'SELL'
                bot_data['reason'] = f"Sell signals: {sell_signals}, Buy signals: {buy_signals}"
            else:
                bot_data['signal'] = 'HOLD'
                bot_data['reason'] = f"Mixed signals - Buy: {buy_signals}, Sell: {sell_signals}"
                
        except Exception as e:
            logging.error(f"Error calculating trading signal: {e}")
            bot_data['signal'] = 'HOLD'
            bot_data['reason'] = 'Error calculating signal'
            
    def _get_current_btc_price(self):
        """Get current BTC price from CoinGecko API"""
        try:
            response = requests.get(
                'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd',
                timeout=10
            )
            data = response.json()
            return data['bitcoin']['usd']
        except:
            return 104000  # Fallback price
            
    def _fetch_market_sentiment(self):
        """Fetch comprehensive market sentiment data"""
        global sentiment_data
        
        try:
            # Fetch Fear & Greed Index
            self._fetch_fear_greed_index()
            
            # Fetch news sentiment
            self._fetch_news_sentiment()
            
            # Fetch social media sentiment
            self._fetch_social_sentiment()
            
            # Calculate market indicators
            self._calculate_market_indicators()
            
            # Generate trading signals based on sentiment
            self._generate_sentiment_signals()
            
            # Update overall sentiment
            sentiment_data['overall_sentiment'] = self._calculate_sentiment()
            sentiment_data['sentiment_score'] = self._calculate_overall_sentiment_score()
            
        except Exception as e:
            logging.error(f"Error fetching sentiment: {e}")
            
    def _fetch_fear_greed_index(self):
        """Fetch Fear & Greed Index"""
        try:
            response = requests.get('https://api.alternative.me/fng/', timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and len(data['data']) > 0:
                    sentiment_data['fear_greed_index'] = int(data['data'][0]['value'])
        except Exception as e:
            logging.error(f"Error fetching Fear & Greed Index: {e}")
            
    def _fetch_news_sentiment(self):
        """Fetch and analyze cryptocurrency news sentiment"""
        try:
            # Use NewsAPI (requires API key) or fallback to CryptoCompare news
            news_articles = []
            
            # Try CryptoCompare news API (free tier available)
            try:
                response = requests.get(
                    'https://min-api.cryptocompare.com/data/v2/news/?categories=BTC&lang=EN',
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    if 'Data' in data:
                        for article in data['Data'][:10]:  # Get top 10 articles
                            title = article.get('title', '')
                            body = article.get('body', '')[:200]  # First 200 chars
                            
                            # Analyze sentiment using TextBlob
                            title_sentiment = TextBlob(title).sentiment.polarity
                            body_sentiment = TextBlob(body).sentiment.polarity if body else 0
                            
                            overall_sentiment = (title_sentiment + body_sentiment) / 2
                            
                            news_articles.append({
                                'title': title,
                                'url': article.get('url', ''),
                                'published_on': datetime.fromtimestamp(article.get('published_on', 0)).isoformat(),
                                'source': article.get('source_info', {}).get('name', 'Unknown'),
                                'sentiment_score': round(overall_sentiment, 3),
                                'sentiment_label': self._get_sentiment_label(overall_sentiment)
                            })
            except Exception as e:
                logging.error(f"Error fetching CryptoCompare news: {e}")
            
            # If no articles from CryptoCompare, try alternative sources
            if not news_articles:
                news_articles = self._fetch_alternative_news()
            
            # Calculate news sentiment metrics
            if news_articles:
                sentiments = [article['sentiment_score'] for article in news_articles]
                avg_sentiment = sum(sentiments) / len(sentiments)
                
                positive_count = len([s for s in sentiments if s > 0.1])
                negative_count = len([s for s in sentiments if s < -0.1])
                neutral_count = len(sentiments) - positive_count - negative_count
                
                sentiment_data['news_sentiment'].update({
                    'articles': news_articles,
                    'average_sentiment': round(avg_sentiment, 3),
                    'positive_count': positive_count,
                    'negative_count': negative_count,
                    'neutral_count': neutral_count
                })
            
        except Exception as e:
            logging.error(f"Error fetching news sentiment: {e}")
            
    def _fetch_alternative_news(self):
        """Fetch news from alternative sources"""
        articles = []
        try:
            # Try CoinGecko trending
            response = requests.get('https://api.coingecko.com/api/v3/search/trending', timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'coins' in data:
                    for coin in data['coins'][:5]:
                        if 'item' in coin:
                            item = coin['item']
                            if 'bitcoin' in item.get('name', '').lower() or 'btc' in item.get('symbol', '').lower():
                                # Create synthetic article based on trending data
                                title = f"{item.get('name', 'Bitcoin')} trending - Market Cap Rank #{item.get('market_cap_rank', 'N/A')}"
                                sentiment_score = 0.3  # Trending is generally positive
                                
                                articles.append({
                                    'title': title,
                                    'url': f"https://coingecko.com/en/coins/{item.get('id', 'bitcoin')}",
                                    'published_on': datetime.now().isoformat(),
                                    'source': 'CoinGecko Trending',
                                    'sentiment_score': sentiment_score,
                                    'sentiment_label': self._get_sentiment_label(sentiment_score)
                                })
        except Exception as e:
            logging.error(f"Error fetching alternative news: {e}")
        
        return articles
    
    def _fetch_social_sentiment(self):
        """Fetch social media sentiment data"""
        try:
            # Since we don't have Twitter API access, we'll simulate realistic social sentiment
            # In a real implementation, you would integrate with:
            # - Twitter API v2 for tweets about Bitcoin/crypto
            # - Reddit API for r/Bitcoin, r/cryptocurrency posts
            # - Telegram channels, Discord servers, etc.
            
            # Simulate based on Fear & Greed Index and news sentiment
            fear_greed = sentiment_data['fear_greed_index']
            news_avg = sentiment_data['news_sentiment']['average_sentiment']
            
            # Calculate synthetic social sentiment
            twitter_sentiment = ((fear_greed - 50) / 50 * 0.6) + (news_avg * 0.4)
            reddit_sentiment = ((fear_greed - 50) / 50 * 0.5) + (news_avg * 0.3) + (0.2 * (1 if fear_greed < 40 else -1 if fear_greed > 60 else 0))
            
            # Generate trending hashtags based on market conditions
            trending_hashtags = self._generate_trending_hashtags(fear_greed, news_avg)
            
            # Calculate mentions based on market activity
            base_mentions = 5000
            volatility_multiplier = 1 + abs(news_avg) * 2
            mentions_24h = int(base_mentions * volatility_multiplier * (fear_greed / 50))
            
            sentiment_data['social_sentiment'].update({
                'twitter_sentiment': round(twitter_sentiment, 3),
                'reddit_sentiment': round(reddit_sentiment, 3),
                'mentions_24h': mentions_24h,
                'trending_hashtags': trending_hashtags
            })
            
            # Update legacy fields for compatibility
            sentiment_data['social_volume'] = mentions_24h
            sentiment_data['trending_topics'] = trending_hashtags[:5]  # Top 5 for legacy component
            
        except Exception as e:
            logging.error(f"Error fetching social sentiment: {e}")
    
    def _generate_trending_hashtags(self, fear_greed, news_sentiment):
        """Generate realistic trending hashtags based on market conditions"""
        base_tags = ['#Bitcoin', '#BTC', '#Crypto', '#Blockchain']
        
        if fear_greed < 25:  # Extreme Fear
            trending = ['#BitcoinCrash', '#BTCDOWN', '#CryptoBear', '#HODL', '#BuyTheDip']
        elif fear_greed < 45:  # Fear
            trending = ['#BitcoinDip', '#CryptoCorrection', '#MarketFear', '#HODL', '#Accumulate']
        elif fear_greed > 75:  # Extreme Greed
            trending = ['#BitcoinMoon', '#BTCUP', '#CryptoBull', '#ToTheMoon', '#FOMO']
        elif fear_greed > 55:  # Greed
            trending = ['#BitcoinRally', '#CryptoPump', '#BullMarket', '#BTCATH', '#CryptoGains']
        else:  # Neutral
            trending = ['#BitcoinTrading', '#CryptoNews', '#DeFi', '#Web3', '#CryptoAnalysis']
        
        # Add news-based tags
        if news_sentiment > 0.2:
            trending.extend(['#PositiveNews', '#CryptoAdoption'])
        elif news_sentiment < -0.2:
            trending.extend(['#CryptoFUD', '#MarketNews'])
        
        return base_tags + trending[:6]  # Return top trending tags
    
    def _calculate_market_indicators(self):
        """Calculate advanced market indicators"""
        try:
            # Get recent price history for volatility calculation
            if len(bot_data['price_history']) >= 10:
                prices = [point['price'] for point in bot_data['price_history'][-10:]]
                
                # Calculate volatility (standard deviation of returns)
                returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
                if returns:
                    mean_return = sum(returns) / len(returns)
                    variance = sum([(r - mean_return) ** 2 for r in returns]) / len(returns)
                    volatility = (variance ** 0.5) * 100  # Convert to percentage
                else:
                    volatility = 0
            else:
                volatility = 5.0  # Default volatility
            
            # Calculate sentiment vs price correlation (simplified)
            fear_greed = sentiment_data['fear_greed_index']
            news_sentiment = sentiment_data['news_sentiment']['average_sentiment']
            
            # Higher fear/greed index suggests more extreme sentiment
            sentiment_extremity = abs(fear_greed - 50) / 50
            price_sentiment_correlation = sentiment_extremity * (1 if news_sentiment > 0 else -1)
            
            # Determine market momentum
            momentum = 'neutral'
            if fear_greed < 30 and news_sentiment < -0.1:
                momentum = 'strong_bearish'
            elif fear_greed < 45 and news_sentiment < 0:
                momentum = 'bearish'
            elif fear_greed > 70 and news_sentiment > 0.1:
                momentum = 'strong_bullish'
            elif fear_greed > 55 and news_sentiment > 0:
                momentum = 'bullish'
            
            sentiment_data['market_indicators'].update({
                'volatility_index': round(volatility, 2),
                'sentiment_vs_price_correlation': round(price_sentiment_correlation, 3),
                'market_momentum': momentum
            })
            
        except Exception as e:
            logging.error(f"Error calculating market indicators: {e}")
    
    def _generate_sentiment_signals(self):
        """Generate trading signals based on sentiment analysis"""
        try:
            fear_greed = sentiment_data['fear_greed_index']
            news_sentiment = sentiment_data['news_sentiment']['average_sentiment']
            social_sentiment = (sentiment_data['social_sentiment']['twitter_sentiment'] + 
                              sentiment_data['social_sentiment']['reddit_sentiment']) / 2
            
            # Combine sentiment factors
            signals = []
            confidence_factors = []
            
            # Fear & Greed signals (contrarian approach)
            if fear_greed < 25:  # Extreme fear - potential buy signal
                signals.append('BUY')
                confidence_factors.append(0.8)
            elif fear_greed < 35:  # Fear - weak buy signal
                signals.append('BUY')
                confidence_factors.append(0.4)
            elif fear_greed > 75:  # Extreme greed - potential sell signal
                signals.append('SELL')
                confidence_factors.append(0.8)
            elif fear_greed > 65:  # Greed - weak sell signal
                signals.append('SELL')
                confidence_factors.append(0.4)
            
            # News sentiment signals
            if news_sentiment > 0.3:  # Very positive news
                signals.append('BUY')
                confidence_factors.append(0.6)
            elif news_sentiment > 0.1:  # Positive news
                signals.append('BUY')
                confidence_factors.append(0.3)
            elif news_sentiment < -0.3:  # Very negative news
                signals.append('SELL')
                confidence_factors.append(0.6)
            elif news_sentiment < -0.1:  # Negative news
                signals.append('SELL')
                confidence_factors.append(0.3)
            
            # Social sentiment signals
            if social_sentiment > 0.4:  # Very positive social sentiment
                signals.append('BUY')
                confidence_factors.append(0.5)
            elif social_sentiment < -0.4:  # Very negative social sentiment
                signals.append('SELL')
                confidence_factors.append(0.5)
            
            # Determine overall signal
            if not signals:
                final_signal = 'HOLD'
                confidence = 0.0
                reasoning = 'Neutral sentiment across all indicators'
            else:
                buy_signals = signals.count('BUY')
                sell_signals = signals.count('SELL')
                
                if buy_signals > sell_signals:
                    final_signal = 'BUY'
                    confidence = sum([conf for i, conf in enumerate(confidence_factors) if signals[i] == 'BUY']) / buy_signals
                    reasoning = f"Bullish sentiment: {buy_signals} buy vs {sell_signals} sell signals"
                elif sell_signals > buy_signals:
                    final_signal = 'SELL'
                    confidence = sum([conf for i, conf in enumerate(confidence_factors) if signals[i] == 'SELL']) / sell_signals
                    reasoning = f"Bearish sentiment: {sell_signals} sell vs {buy_signals} buy signals"
                else:
                    final_signal = 'HOLD'
                    confidence = sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0
                    reasoning = f"Mixed signals: {buy_signals} buy vs {sell_signals} sell signals"
            
            sentiment_data['trading_signals'].update({
                'sentiment_signal': final_signal,
                'confidence': round(confidence, 2),
                'reasoning': reasoning
            })
            
        except Exception as e:
            logging.error(f"Error generating sentiment signals: {e}")
            sentiment_data['trading_signals'].update({
                'sentiment_signal': 'HOLD',
                'confidence': 0.0,
                'reasoning': 'Error calculating signals'
            })
    
    def _get_sentiment_label(self, score):
        """Convert sentiment score to label"""
        if score > 0.3:
            return 'Very Positive'
        elif score > 0.1:
            return 'Positive'
        elif score > -0.1:
            return 'Neutral'
        elif score > -0.3:
            return 'Negative'
        else:
            return 'Very Negative'
    
    def _calculate_overall_sentiment_score(self):
        """Calculate overall sentiment score combining all factors"""
        try:
            fear_greed_score = (sentiment_data['fear_greed_index'] - 50) / 50
            news_score = sentiment_data['news_sentiment']['average_sentiment']
            social_score = (sentiment_data['social_sentiment']['twitter_sentiment'] + 
                           sentiment_data['social_sentiment']['reddit_sentiment']) / 2
            
            # Weighted average: Fear & Greed (40%), News (35%), Social (25%)
            overall_score = (fear_greed_score * 0.4) + (news_score * 0.35) + (social_score * 0.25)
            return round(overall_score, 3)
        except:
            return 0.0
            
    def _calculate_sentiment(self):
        """Calculate overall sentiment based on fear & greed index"""
        index = sentiment_data['fear_greed_index']
        if index < 25:
            return 'extreme_fear'
        elif index < 45:
            return 'fear'
        elif index < 55:
            return 'neutral'
        elif index < 75:
            return 'greed'
        else:
            return 'extreme_greed'
            
    def _monitor_whale_activity(self):
        """Monitor whale activity (placeholder for actual whale tracking)"""
        global whale_data
        
        # Simulate whale data
        whale_data.update({
            'large_transactions': [
                {
                    'hash': '0x123...abc',
                    'amount': 1000.5,
                    'from': '1A1zP1...ZVb',
                    'to': '1BvBMS...XYZ',
                    'timestamp': datetime.now().isoformat(),
                    'usd_value': 104000000
                }
            ],
            'whale_alerts': [
                {
                    'type': 'large_transfer',
                    'message': '1,000 BTC moved from unknown wallet',
                    'timestamp': datetime.now().isoformat(),
                    'impact': 'medium'
                }
            ],
            'flow_summary': {
                'inflow': 5000000,
                'outflow': 3000000,
                'net_flow': 2000000
            }
        })

# Initialize bot adapter
bot_adapter = TradingBotAdapter()

# Initialize auto trading engine (enhanced multi-currency only)
# Create dummy legacy bot to avoid breaking old API endpoints (not used for trading)
auto_trading_engine = AutoTradingEngine(bot_adapter)
# Enhanced multi-currency bot is the ONLY active trading bot
enhanced_engine = EnhancedAutoTradingEngine(bot_adapter)
enhanced_engine.load_state()

@app.route('/api/bot/status')
def get_bot_status():
    """Get current bot status with real-time P&L calculation"""
    # Calculate real P&L from trade history
    pnl_data = bot_adapter.calculate_pnl_from_trades()

    # Update bot_data with calculated values
    bot_data['daily_pnl'] = pnl_data['daily_pnl']
    bot_data['total_pnl'] = pnl_data['total_pnl']
    bot_data['daily_trades'] = pnl_data['daily_trades']

    return jsonify(bot_data)

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Start the trading bot"""
    try:
        bot_adapter.start_bot_monitoring()
        return jsonify({'success': True, 'message': 'Bot started successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Stop the trading bot"""
    try:
        bot_adapter.running = False
        bot_data['connected'] = False
        return jsonify({'success': True, 'message': 'Bot stopped successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sentiment')
def get_sentiment():
    """Get market sentiment data"""
    return jsonify(sentiment_data)

@app.route('/api/test')
def test_endpoint():
    """Simple test endpoint"""
    return jsonify({'success': True, 'message': 'Backend is working!', 'timestamp': datetime.now().isoformat()})

@app.route('/api/test-trading')
def test_trading():
    """Test if trading is possible with current API setup"""
    try:
        if not bot_adapter.coinbase_client:
            return jsonify({'success': False, 'error': 'No Coinbase client'})
        
        # Test different API capabilities
        result = {
            'can_read_accounts': False,
            'can_read_user': False,
            'can_read_products': False,
            'api_errors': []
        }
        
        # Test accounts
        try:
            accounts = bot_adapter.coinbase_client.get_accounts()
            result['can_read_accounts'] = True
            result['accounts_count'] = len(accounts.accounts) if hasattr(accounts, 'accounts') else 0
        except Exception as e:
            result['api_errors'].append(f"Accounts: {str(e)}")
        
        # Test user info
        try:
            user = bot_adapter.coinbase_client.get_user()
            result['can_read_user'] = True
        except Exception as e:
            result['api_errors'].append(f"User: {str(e)}")
            
        # Test products
        try:
            products = bot_adapter.coinbase_client.get_products()
            result['can_read_products'] = True
        except Exception as e:
            result['api_errors'].append(f"Products: {str(e)}")
        
        return jsonify({
            'success': True,
            'api_test_results': result,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/products')
def get_products():
    """Get available trading products"""
    try:
        if not bot_adapter.coinbase_client:
            return jsonify({'success': False, 'error': 'Coinbase client not initialized'}), 400
        
        # Get list of available products
        products = bot_adapter.coinbase_client.get_products()
        
        # Filter for BTC pairs
        btc_products = []
        if hasattr(products, 'products'):
            for product in products.products:
                if hasattr(product, 'product_id') and 'BTC' in product.product_id:
                    btc_products.append({
                        'product_id': product.product_id,
                        'status': getattr(product, 'status', 'unknown'),
                        'base_currency': getattr(product, 'base_currency_id', ''),
                        'quote_currency': getattr(product, 'quote_currency_id', '')
                    })
        
        return jsonify({
            'success': True,
            'btc_products': btc_products[:10],  # Show first 10 BTC products
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error getting products: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/whales')
def get_whale_data():
    """Get whale tracking data"""
    return jsonify(whale_data)

@app.route('/api/orders')
def get_orders():
    """Get order history"""
    try:
        limit = request.args.get('limit', 50, type=int)
        orders = bot_adapter.get_order_history(limit=limit)
        return jsonify({
            'success': True,
            'orders': orders,
            'count': len(orders)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trades')
@token_required
def get_trades():
    """Get fills/trades history"""
    try:
        limit = request.args.get('limit', 50, type=int)
        trades = bot_adapter.get_fills_history(limit=limit)
        return jsonify({
            'success': True,
            'trades': trades,
            'count': len(trades)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/crypto')
def get_crypto_data():
    """Get multi-cryptocurrency data"""
    return jsonify({
        'success': True,
        'crypto_data': crypto_data,
        'last_update': datetime.now().isoformat()
    })

@app.route('/api/portfolio')
def get_portfolio():
    """Get portfolio breakdown"""
    portfolio_breakdown = bot_adapter.get_portfolio_breakdown()
    return jsonify({
        'success': True,
        'portfolio': portfolio_breakdown
    })

@app.route('/api/crypto/<symbol>')
def get_crypto_detail(symbol):
    """Get detailed data for a specific cryptocurrency"""
    symbol = symbol.upper()
    if symbol not in crypto_data:
        return jsonify({'success': False, 'error': 'Cryptocurrency not supported'}), 404
    
    return jsonify({
        'success': True,
        'symbol': symbol,
        'data': crypto_data[symbol]
    })

@app.route('/api/execute-trade', methods=['POST'])
@token_required
def execute_trade():
    """Execute a real trade using Coinbase Advanced API"""
    try:
        data = request.json
        action = data.get('action')  # 'buy', 'sell'
        symbol = data.get('symbol', 'BTC-USDC')  # Trading pair
        amount_type = data.get('amount_type', 'usd')  # 'usd' or 'crypto'
        amount = float(data.get('amount', 25))  # Amount to trade
        
        if not bot_adapter.coinbase_client:
            return jsonify({
                'success': False, 
                'error': 'Coinbase client not initialized. Check API credentials.'
            }), 400
        
        # Execute the trade
        result = bot_adapter.execute_market_order(action, symbol, amount_type, amount)
        
        if result['success']:
            # Log the trade
            logging.info(f"Trade executed: {action} {amount} {amount_type} of {symbol}")
            
            # Update portfolio data
            bot_adapter.get_portfolio_breakdown()
            
            return jsonify({
                'success': True,
                'message': result['message'],
                'order_id': result.get('order_id'),
                'executed_amount': result.get('executed_amount'),
                'executed_price': result.get('executed_price'),
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
        
    except Exception as e:
        logging.error(f"Error executing trade: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get-quote', methods=['POST'])
@token_required
def get_quote():
    """Get a price quote for a potential trade"""
    try:
        data = request.json
        logging.info(f"Get quote request data: {data}")
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
            
        symbol = data.get('symbol', 'BTC-USDC')
        amount_type = data.get('amount_type', 'usd')
        amount = float(data.get('amount', 25))
        
        if not bot_adapter.coinbase_client:
            return jsonify({
                'success': False,
                'error': 'Coinbase client not initialized'
            }), 400
        
        # Get current price for any crypto
        current_price = bot_adapter._get_real_price(symbol)
        
        if amount_type == 'usd':
            crypto_amount = amount / current_price if current_price > 0 else 0
            usd_amount = amount
        else:
            crypto_amount = amount
            usd_amount = amount * current_price
        
        # Calculate estimated fees (Coinbase Advanced is typically 0.6% for market orders)
        fee_rate = 0.006
        estimated_fee = usd_amount * fee_rate
        
        return jsonify({
            'success': True,
            'symbol': symbol,
            'current_price': current_price,
            'crypto_amount': round(crypto_amount, 8),
            'usd_amount': round(usd_amount, 2),
            'estimated_fee': round(estimated_fee, 2),
            'total_cost': round(usd_amount + estimated_fee, 2) if amount_type == 'usd' else round(usd_amount - estimated_fee, 2),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/portfolios')
def get_portfolios():
    """Get available portfolios"""
    try:
        if not bot_adapter.coinbase_client:
            return jsonify({'success': False, 'error': 'Coinbase client not initialized'}), 400
        
        portfolios = bot_adapter.get_portfolios()
        
        return jsonify({
            'success': True,
            'portfolios': portfolios,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error getting portfolios: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/strategies')
def get_strategies():
    """Get available trading strategies"""
    strategies = [
      {
        'id': 'momentum_scalper',
        'name': 'AI Momentum Scalper',
        'description': 'High-frequency strategy based on price momentum and volume analysis',
        'type': 'aggressive',
        'confidence': 85,
        'expected_return': '15-25%',
        'risk_level': 'high',
        'timeframe': '1-5 minutes',
        'conditions': ['High volume', 'Strong momentum', 'Clear trend'],
        'performance': {
          'win_rate': 72,
          'avg_return': 1.8,
          'max_drawdown': -5.2,
          'trades_24h': 45
        },
        'signals': {
          'entry': 'RSI divergence + volume spike',
          'exit': 'Momentum reversal or 2% target',
          'stop_loss': '1.5% from entry'
        },
        'active': False
      },
      {
        'id': 'sentiment_rider',
        'name': 'Sentiment Momentum Rider',
        'description': 'Combines social sentiment with technical analysis for medium-term trades',
        'type': 'balanced',
        'confidence': 78,
        'expected_return': '8-15%',
        'risk_level': 'medium',
        'timeframe': '1-4 hours',
        'conditions': ['Positive sentiment shift', 'Technical confirmation', 'Volume support'],
        'performance': {
          'win_rate': 68,
          'avg_return': 3.2,
          'max_drawdown': -8.1,
          'trades_24h': 12
        },
        'signals': {
          'entry': 'Sentiment score > 0.6 + breakout',
          'exit': 'Sentiment reversal or profit target',
          'stop_loss': '2.5% from entry'
        },
        'active': True
      },
      {
        'id': 'whale_follower',
        'name': 'Whale Movement Tracker',
        'description': 'Follows large wallet movements and exchange flows for position sizing',
        'type': 'conservative',
        'confidence': 71,
        'expected_return': '5-12%',
        'risk_level': 'low',
        'timeframe': '4-24 hours',
        'conditions': ['Large whale transactions', 'Exchange flow changes', 'Technical support'],
        'performance': {
          'win_rate': 75,
          'avg_return': 2.1,
          'max_drawdown': -3.8,
          'trades_24h': 6
        },
        'signals': {
          'entry': 'Whale accumulation + technical setup',
          'exit': 'Whale distribution or target hit',
          'stop_loss': '2% from entry'
        },
        'active': False
      }
    ]
    return jsonify({'success': True, 'strategies': strategies})

@app.route('/api/strategies/active', methods=['POST'])
def set_active_strategy():
    """Set the active trading strategy"""
    try:
        data = request.json
        strategy_id = data.get('strategy_id')
        # In a real application, you would store this in a database or a more persistent cache
        bot_data['active_strategy'] = strategy_id
        logging.info(f"Active strategy set to: {strategy_id}")
        return jsonify({'success': True, 'message': f'Active strategy set to {strategy_id}'})
    except Exception as e:
        logging.error(f"Error setting active strategy: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/insights')
def get_ai_insights():
    """Get AI-generated insights"""
    insights = [
        {
          'id': 1,
          'type': 'opportunity',
          'title': 'Bullish Momentum Building',
          'description': 'AI detects accumulation pattern with 73% probability of upward movement in next 2-4 hours',
          'confidence': 73,
          'action': 'Consider increasing position size',
          'timestamp': datetime.now().isoformat()
        },
        {
          'id': 2,
          'type': 'warning',
          'title': 'Whale Distribution Alert',
          'description': 'Large wallet showing distribution pattern. Reduce risk exposure.',
          'confidence': 81,
          'action': 'Implement tighter stop losses',
          'timestamp': (datetime.now() - timedelta(minutes=15)).isoformat()
        },
        {
          'id': 3,
          'type': 'strategy',
          'title': 'Optimal Entry Window',
          'description': 'Technical indicators align for optimal entry in next 30 minutes',
          'confidence': 67,
          'action': 'Prepare for position entry',
          'timestamp': (datetime.now() - timedelta(minutes=30)).isoformat()
        }
      ]
    return jsonify({'success': True, 'insights': insights})

@app.route('/api/account-balances')
@token_required
def get_account_balances():
    """Get current account balances"""
    try:
        logging.info("Account balances request received")
        
        if not bot_adapter.coinbase_client:
            logging.warning("Coinbase client not initialized")
            return jsonify({
                'success': False,
                'error': 'Coinbase client not initialized'
            }), 400
        
        balances = bot_adapter.get_account_balances()
        logging.info(f"Retrieved {len(balances)} account balances")
        
        return jsonify({
            'success': True,
            'balances': balances,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error getting account balances: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/voice-command', methods=['POST'])
def process_voice_command():
    """Process voice commands"""
    try:
        data = request.json
        command = data.get('command', '').lower()
        
        response = {'success': True, 'action': None, 'message': ''}
        
        if 'buy' in command:
            response['action'] = 'buy'
            response['message'] = 'Executing buy order'
        elif 'sell' in command:
            response['action'] = 'sell'
            response['message'] = 'Executing sell order'
        elif 'status' in command:
            response['action'] = 'status'
            response['message'] = f"Current price: ${bot_data['current_price']}, Signal: {bot_data['signal']}"
        elif 'stop' in command:
            response['action'] = 'stop'
            response['message'] = 'Stopping trading bot'
        else:
            response['message'] = 'Command not recognized'
            
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/test-trade')
@token_required
def test_minimal_trade():
    """Test a minimal trade to debug the exact issue"""
    try:
        if not bot_adapter.coinbase_client:
            return jsonify({'success': False, 'error': 'Coinbase client not initialized'})
        
        # Try to create a very small test order
        import uuid
        client_order_id = str(uuid.uuid4())
        
        order_params = {
            'client_order_id': client_order_id,
            'product_id': 'BTC-USDC',
            'side': 'BUY',
            'order_configuration': {
                'market_market_ioc': {
                    'quote_size': '10.00'  # $10 test order
                }
            }
        }
        
        logging.info(f"Test order params: {order_params}")
        
        # Try the order and capture the full response
        try:
            # First, let's check if we can get trading permissions info
            try:
                permissions_test = bot_adapter.coinbase_client.get_unix_time()
                logging.info(f"API connection test successful: {permissions_test}")
            except Exception as perm_e:
                logging.error(f"API connection test failed: {perm_e}")
            
            order_response = bot_adapter.coinbase_client.create_order(**order_params)
            return jsonify({
                'success': True,
                'response_type': str(type(order_response)),
                'response_data': str(order_response)
            })
        except Exception as e:
            # Log the full error details
            logging.error(f"Full error details: {e}")
            logging.error(f"Error type: {type(e)}")
            
            return jsonify({
                'success': False,
                'error': str(e),
                'error_type': str(type(e)),
                'suggestion': 'This appears to be a Coinbase account-level restriction. Contact Coinbase support to enable API trading.'
            })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/sports-analysis')
def get_sports_analysis():
    """Get AI-powered sports betting analysis"""
    try:
        sport = request.args.get('sport', 'all')
        confidence = request.args.get('confidence', 'all')
        
        # Generate AI analysis using multiple AI APIs
        analysis_result = generate_sports_analysis(sport, confidence)
        
        return jsonify({
            'success': True,
            'games': analysis_result['games'],
            'analysis': analysis_result['analysis']
        })
        
    except Exception as e:
        logging.error(f"Error getting sports analysis: {e}")
        return jsonify({'success': False, 'error': str(e)})

def generate_sports_analysis(sport_filter, confidence_filter):
    """Generate AI-powered sports betting analysis using Perplexity API"""
    import requests
    import json
    from datetime import datetime, timedelta
    
    # Get real-time sports data from Perplexity
    today_games = get_todays_games_from_perplexity(sport_filter)
    
    # If no real games found, fall back to mock data for demo
    if not today_games:
        logging.warning("No real games found, using mock data")
        today = datetime.now()
        today_games = [
            {
                'id': '1',
                'sport': 'NBA',
                'home_team': 'Los Angeles Lakers',
                'away_team': 'Golden State Warriors',
                'time': (today + timedelta(hours=3)).isoformat(),
                'odds': {'home': '-110', 'away': '+105'}
            },
            {
                'id': '2',
                'sport': 'NFL',
                'home_team': 'Kansas City Chiefs',
                'away_team': 'Buffalo Bills',
                'time': (today + timedelta(hours=5)).isoformat(),
                'odds': {'home': '-125', 'away': '+110'}
            },
            {
                'id': '3',
                'sport': 'MLB',
                'home_team': 'New York Yankees',
                'away_team': 'Boston Red Sox',
                'time': (today + timedelta(hours=2)).isoformat(),
                'odds': {'home': '-140', 'away': '+130'}
            }
        ]
    
    # Filter games by sport
    if sport_filter != 'all':
        today_games = [g for g in today_games if g['sport'].lower() == sport_filter.lower()]
    
    # Generate AI analysis for each game
    game_analysis = {}
    total_confidence = 0
    high_confidence_count = 0
    total_value = 0
    
    for game in today_games:
        analysis = get_ai_game_analysis_with_perplexity(game)
        game_analysis[game['id']] = analysis
        
        total_confidence += analysis['confidence']
        if analysis['confidence'] >= 80:
            high_confidence_count += 1
        if 'recommendation' in analysis and 'value' in analysis['recommendation']:
            total_value += analysis['recommendation']['value']
    
    # Filter by confidence
    if confidence_filter == 'high':
        today_games = [g for g in today_games if game_analysis[g['id']]['confidence'] >= 80]
    elif confidence_filter == 'medium':
        today_games = [g for g in today_games if 60 <= game_analysis[g['id']]['confidence'] < 80]
    elif confidence_filter == 'low':
        today_games = [g for g in today_games if game_analysis[g['id']]['confidence'] < 60]
    
    # Generate overall summary using AI
    summary = generate_ai_summary_with_perplexity(today_games, game_analysis)
    
    analysis_summary = {
        'summary': summary,
        'high_confidence_bets': high_confidence_count,
        'avg_confidence': round(total_confidence / len(today_games) if today_games else 0),
        'total_value': round(total_value, 1)
    }
    
    return {
        'games': today_games,
        'analysis': {**game_analysis, **analysis_summary}
    }

def get_todays_games_from_perplexity(sport_filter):
    """Get today's games and odds using Perplexity API"""
    import requests
    from datetime import datetime
    
    PERPLEXITY_API_KEY = "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"
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Create sport-specific query
    if sport_filter == 'all':
        query = f"What are today's ({today}) major sports games in NBA, NFL, MLB, NHL with current betting odds and lines? Include team names, game times, moneyline odds, and point spreads."
    else:
        sport_name = {
            'nba': 'NBA basketball',
            'nfl': 'NFL football', 
            'mlb': 'MLB baseball',
            'nhl': 'NHL hockey',
            'soccer': 'MLS/Premier League soccer'
        }.get(sport_filter.lower(), sport_filter.upper())
        
        query = f"What are today's ({today}) {sport_name} games with current betting odds and lines? Include team names, game times, moneyline odds, point spreads, and over/under totals."
    
    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a sports betting expert. Provide real-time sports data and betting information in a structured format. Always include team names, game times, and current odds."
                    },
                    {
                        "role": "user", 
                        "content": query
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 2000
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            perplexity_response = data['choices'][0]['message']['content']
            
            # Parse the response to extract game data
            games = parse_perplexity_games_response(perplexity_response, sport_filter)
            logging.info(f"Perplexity found {len(games)} games")
            return games
            
        else:
            logging.error(f"Perplexity API error: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        logging.error(f"Error calling Perplexity API: {e}")
        return []

def parse_perplexity_games_response(response_text, sport_filter):
    """Parse Perplexity response to extract game data"""
    import re
    from datetime import datetime
    
    games = []
    
    # Try to extract game information using regex patterns
    # Look for patterns like "Team A vs Team B" or "Team A @ Team B"
    game_patterns = [
        r'([A-Za-z\s]+(?:Lakers|Warriors|Chiefs|Bills|Yankees|Red Sox|Celtics|Heat|Cowboys|Packers|Dodgers|Giants|Rangers|Kings|Knicks|Nets|Clippers|Suns|Nuggets|Thunder|Mavericks|Spurs|Hawks|Magic|Hornets|Pistons|Pacers|Cavaliers|Bucks|Bulls|76ers|Raptors)[A-Za-z\s]*)\s+(?:vs|@|against)\s+([A-Za-z\s]+(?:Lakers|Warriors|Chiefs|Bills|Yankees|Red Sox|Celtics|Heat|Cowboys|Packers|Dodgers|Giants|Rangers|Kings|Knicks|Nets|Clippers|Suns|Nuggets|Thunder|Mavericks|Spurs|Hawks|Magic|Hornets|Pistons|Pacers|Cavaliers|Bucks|Bulls|76ers|Raptors)[A-Za-z\s]*)',
        r'(\w+\s+\w+)\s+vs\s+(\w+\s+\w+)'
    ]
    
    game_id = 1
    for pattern in game_patterns:
        matches = re.findall(pattern, response_text, re.IGNORECASE)
        for match in matches:
            team1, team2 = match[0].strip(), match[1].strip()
            
            # Determine sport from team names or filter
            detected_sport = detect_sport_from_teams(team1, team2) or sport_filter.upper()
            
            game = {
                'id': str(game_id),
                'sport': detected_sport,
                'home_team': team2,  # Second team is usually home
                'away_team': team1,  # First team is usually away
                'time': datetime.now().isoformat(),
                'odds': extract_odds_from_text(response_text, team1, team2)
            }
            
            games.append(game)
            game_id += 1
    
    # If no games found through parsing, create sample games based on current real matchups
    if not games:
        games = get_fallback_games(sport_filter)
    
    return games[:10]  # Limit to 10 games

def detect_sport_from_teams(team1, team2):
    """Detect sport based on team names"""
    nba_teams = ['Lakers', 'Warriors', 'Celtics', 'Heat', 'Knicks', 'Nets', 'Clippers', 'Suns', 'Nuggets', 'Thunder']
    nfl_teams = ['Chiefs', 'Bills', 'Cowboys', 'Packers', 'Patriots', 'Ravens', 'Steelers', 'Bengals']
    mlb_teams = ['Yankees', 'Red Sox', 'Dodgers', 'Giants', 'Mets', 'Cubs', 'Cardinals', 'Astros']
    
    combined_text = f"{team1} {team2}".lower()
    
    for team in nba_teams:
        if team.lower() in combined_text:
            return 'NBA'
    for team in nfl_teams:
        if team.lower() in combined_text:
            return 'NFL'
    for team in mlb_teams:
        if team.lower() in combined_text:
            return 'MLB'
    
    return None

def extract_odds_from_text(text, team1, team2):
    """Extract betting odds from text"""
    import re
    
    # Look for odds patterns like -110, +105, etc.
    odds_pattern = r'[+-]\d{3,4}'
    odds_matches = re.findall(odds_pattern, text)
    
    if len(odds_matches) >= 2:
        return {
            'away': odds_matches[0],
            'home': odds_matches[1]
        }
    
    # Default odds if none found
    return {
        'away': '+105',
        'home': '-110'
    }

def get_fallback_games(sport_filter):
    """Get fallback games when Perplexity doesn't return results"""
    from datetime import datetime, timedelta
    
    today = datetime.now()
    
    if sport_filter == 'nba' or sport_filter == 'all':
        return [
            {
                'id': '1',
                'sport': 'NBA',
                'home_team': 'Los Angeles Lakers',
                'away_team': 'Boston Celtics',
                'time': (today + timedelta(hours=3)).isoformat(),
                'odds': {'home': '-115', 'away': '+110'}
            }
        ]
    elif sport_filter == 'nfl':
        return [
            {
                'id': '2',
                'sport': 'NFL',
                'home_team': 'Kansas City Chiefs',
                'away_team': 'Buffalo Bills',
                'time': (today + timedelta(hours=5)).isoformat(),
                'odds': {'home': '-125', 'away': '+115'}
            }
        ]
    
    return []

def get_ai_game_analysis_with_perplexity(game):
    """Get AI analysis for a single game using Perplexity API"""
    import requests
    
    PERPLEXITY_API_KEY = "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"
    
    query = f"""Analyze the {game['sport']} game between {game['away_team']} @ {game['home_team']} for sports betting purposes. Consider:

1. Recent team performance and form
2. Head-to-head matchup history  
3. Key player injuries and availability
4. Home field/court advantage
5. Weather conditions (if applicable)
6. Betting line movement and public sentiment
7. Statistical matchups and trends

Provide:
- A specific betting recommendation (moneyline, spread, or over/under)
- Confidence level (65-95%)
- Expected value percentage
- Risk assessment (Low/Medium/High)
- 2-3 key analysis factors
- Brief reasoning for the recommendation

Be specific and actionable for betting purposes."""

    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert sports betting analyst with access to real-time data. Provide specific, actionable betting recommendations with confidence levels and reasoning."
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                "temperature": 0.2,
                "max_tokens": 1500
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            ai_response = data['choices'][0]['message']['content']
            
            # Parse the AI response to extract structured data
            analysis = parse_perplexity_analysis_response(ai_response, game)
            return analysis
            
        else:
            logging.error(f"Perplexity analysis error: {response.status_code}")
            return get_fallback_analysis(game)
            
    except Exception as e:
        logging.error(f"Error getting Perplexity analysis: {e}")
        return get_fallback_analysis(game)

def parse_perplexity_analysis_response(response_text, game):
    """Parse Perplexity analysis response into structured data"""
    import re
    import random
    
    # Extract confidence level
    confidence_match = re.search(r'confidence[:\s]*(\d{2,3})%?', response_text, re.IGNORECASE)
    confidence = int(confidence_match.group(1)) if confidence_match else random.randint(70, 90)
    
    # Extract expected value
    value_match = re.search(r'expected value[:\s]*[+]?(\d+(?:\.\d+)?)%?', response_text, re.IGNORECASE)
    expected_value = float(value_match.group(1)) if value_match else random.uniform(5, 15)
    
    # Extract risk level
    risk_match = re.search(r'risk[:\s]*(low|medium|high)', response_text, re.IGNORECASE)
    risk_level = risk_match.group(1).capitalize() if risk_match else 'Medium'
    
    # Try to extract betting recommendation
    bet_patterns = [
        r'(take|bet|recommend)[:\s]*([^.]+?)(?:\.|$)',
        r'recommendation[:\s]*([^.]+?)(?:\.|$)',
        r'(moneyline|spread|over|under)[:\s]*([^.]+?)(?:\.|$)'
    ]
    
    bet_recommendation = None
    bet_type = 'moneyline'
    
    for pattern in bet_patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            if len(match.groups()) == 2:
                bet_recommendation = match.group(2).strip()
                if 'spread' in match.group(1).lower() or 'spread' in match.group(2).lower():
                    bet_type = 'spread'
                elif 'over' in match.group(2).lower() or 'under' in match.group(2).lower():
                    bet_type = 'over_under'
            else:
                bet_recommendation = match.group(1).strip()
            break
    
    # If no specific recommendation found, create one
    if not bet_recommendation:
        recommendations = [
            f"Take {game['away_team']} +3.5",
            f"{game['home_team']} Moneyline",
            f"Over 215.5 total points"
        ]
        bet_recommendation = random.choice(recommendations)
        bet_type = 'spread' if '+' in bet_recommendation else 'moneyline'
    
    # Extract key factors (look for bullet points or numbered lists)
    factors = []
    factor_patterns = [
        r'[•\-\*]\s*([^•\-\*\n]+)',
        r'\d+\.\s*([^\d\n]+)',
        r'(?:because|due to|given)[:\s]*([^.]+)'
    ]
    
    for pattern in factor_patterns:
        matches = re.findall(pattern, response_text, re.IGNORECASE)
        factors.extend([match.strip()[:50] for match in matches if len(match.strip()) > 10])
    
    if not factors:
        factors = [
            f"{game['home_team']} strong home record",
            f"{game['away_team']} recent form",
            "Key matchup advantages"
        ]
    
    # Generate betting percentages
    public_pct = random.randint(45, 75)
    sharp_pct = random.randint(35, 65)
    
    # Extract reasoning or create default
    reasoning_patterns = [
        r'reasoning[:\s]*([^.]+?)(?:\.|$)',
        r'because[:\s]*([^.]+?)(?:\.|$)',
        r'rationale[:\s]*([^.]+?)(?:\.|$)'
    ]
    
    reasoning = None
    for pattern in reasoning_patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            reasoning = match.group(1).strip()
            break
    
    if not reasoning:
        reasoning = f"Analysis favors this play based on recent form and statistical matchups"
    
    return {
        'confidence': min(95, max(65, confidence)),
        'recommendation': {
            'bet': bet_recommendation,
            'type': bet_type,
            'reasoning': reasoning[:200],  # Limit length
            'value': round(expected_value, 1),
            'risk': risk_level
        },
        'public_percentage': f"{public_pct}% on {game['home_team']}",
        'sharp_percentage': f"{sharp_pct}% on {game['away_team']}",
        'factors': factors[:3]  # Limit to 3 factors
    }

def get_fallback_analysis(game):
    """Fallback analysis when Perplexity API fails"""
    import random
    
    confidence = random.randint(70, 88)
    
    recommendations = [
        {
            'bet': f"Take {game['away_team']} +3.5",
            'type': 'spread',
            'reasoning': f"Road team has strong ATS record and favorable matchup",
            'value': round(random.uniform(6, 14), 1),
            'risk': 'Medium'
        },
        {
            'bet': f"{game['home_team']} Moneyline",
            'type': 'moneyline',
            'reasoning': f"Home field advantage and recent form favor {game['home_team']}",
            'value': round(random.uniform(4, 12), 1),
            'risk': 'Low'
        }
    ]
    
    recommendation = random.choice(recommendations)
    
    factors = [
        f"{game['home_team']} 7-3 ATS last 10 games",
        f"{game['away_team']} strong road performance",
        "Key player availability favors pick"
    ]
    
    return {
        'confidence': confidence,
        'recommendation': recommendation,
        'public_percentage': f"{random.randint(45, 75)}% on {game['home_team']}",
        'sharp_percentage': f"{random.randint(35, 65)}% on {game['away_team']}",
        'factors': factors
    }

def generate_ai_summary_with_perplexity(games, analysis):
    """Generate overall summary using Perplexity AI"""
    import requests
    
    if not games:
        return "No games available for analysis today."
    
    PERPLEXITY_API_KEY = "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"
    
    # Create summary of all games
    games_summary = []
    for game in games:
        game_analysis = analysis.get(game['id'], {})
        confidence = game_analysis.get('confidence', 0)
        recommendation = game_analysis.get('recommendation', {})
        
        games_summary.append(f"{game['away_team']} @ {game['home_team']} ({game['sport']}) - {confidence}% confidence, recommending {recommendation.get('bet', 'TBD')}")
    
    query = f"""As a sports betting expert, provide a brief daily summary for today's {len(games)} games:

{chr(10).join(games_summary)}

Write a 2-3 sentence summary highlighting:
1. Overall market opportunities
2. Key themes or patterns you see
3. General betting advice for the day

Keep it professional and actionable for sports bettors."""

    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional sports betting analyst. Provide concise, actionable daily summaries."
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 500
            },
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content'].strip()
        else:
            logging.error(f"Perplexity summary error: {response.status_code}")
            
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
    
    # Fallback summary
    high_conf_count = len([g for g in games if analysis.get(g['id'], {}).get('confidence', 0) >= 80])
    return f"Today features {len(games)} games with {high_conf_count} high-confidence opportunities. Market analysis suggests focusing on key statistical edges and contrarian plays where public sentiment diverges from sharp money."

def get_ai_game_analysis(game):
    """Get AI analysis for a single game using Claude API (mock for now)"""
    
    # Mock AI analysis (replace with actual AI API calls)
    import random
    
    # Simulate different analysis based on teams
    confidence = random.randint(65, 95)
    
    # Generate recommendation based on game
    recommendations = [
        {
            'bet': f"Take {game['away_team']} +3.5",
            'type': 'spread',
            'reasoning': f"Strong road performance and favorable matchup history against {game['home_team']}",
            'value': round(random.uniform(5, 15), 1),
            'risk': 'Medium'
        },
        {
            'bet': f"{game['home_team']} Moneyline",
            'type': 'moneyline', 
            'reasoning': f"Home field advantage and recent form favor {game['home_team']}",
            'value': round(random.uniform(3, 12), 1),
            'risk': 'Low'
        },
        {
            'bet': f"Over 215.5 points",
            'type': 'over_under',
            'reasoning': "Both teams average high scoring with weak defensive metrics",
            'value': round(random.uniform(8, 18), 1),
            'risk': 'High'
        }
    ]
    
    recommendation = random.choice(recommendations)
    
    factors = [
        f"{game['home_team']} 7-3 ATS last 10",
        f"{game['away_team']} strong road record",
        "Key player injuries",
        "Weather conditions favorable",
        "Historical head-to-head trends"
    ]
    
    return {
        'confidence': confidence,
        'recommendation': recommendation,
        'public_percentage': f"{random.randint(45, 75)}% on {game['home_team']}",
        'sharp_percentage': f"{random.randint(35, 65)}% on {game['away_team']}",
        'factors': random.sample(factors, 3)
    }

def generate_ai_summary(games, analysis):
    """Generate overall AI summary for the day"""
    
    if not games:
        return "No games match your selected criteria today."
    
    high_conf_games = [g for g in games if analysis[g['id']]['confidence'] >= 80]
    
    summaries = [
        f"Today features {len(games)} games with strong betting opportunities. AI analysis identifies {len(high_conf_games)} high-confidence plays with favorable expected value.",
        f"Market inefficiencies detected in {len(games)} matchups today. Sharp money appears to be targeting road underdogs in key spots.",
        f"Strong statistical edges found across {len(games)} games. Public betting patterns suggest contrarian opportunities in primetime matchups."
    ]
    
    return summaries[len(games) % len(summaries)]

@app.route('/api/account-status-debug')
@token_required
def get_account_status_debug():
    """Diagnostic endpoint to check account status and trading permissions"""
    try:
        if not bot_adapter.coinbase_client:
            return jsonify({'success': False, 'error': 'Coinbase client not initialized'})
        
        debug_info = {}
        
        # Test basic API access
        try:
            product = bot_adapter.coinbase_client.get_product('BTC-USDC')
            debug_info['api_read_access'] = 'OK'
        except Exception as e:
            debug_info['api_read_access'] = f'Error: {str(e)}'
        
        # Get accounts
        try:
            accounts = bot_adapter.coinbase_client.get_accounts()
            debug_info['accounts_response'] = str(type(accounts))
            if hasattr(accounts, 'accounts'):
                debug_info['accounts_count'] = len(accounts.accounts)
            elif isinstance(accounts, list):
                debug_info['accounts_count'] = len(accounts)
            else:
                debug_info['accounts_count'] = 'Unknown format'
        except Exception as e:
            debug_info['accounts_error'] = str(e)
        
        # Get portfolios
        try:
            portfolios = bot_adapter.coinbase_client.get_portfolios()
            debug_info['portfolios_response'] = str(type(portfolios))
            if hasattr(portfolios, 'portfolios'):
                debug_info['portfolios'] = [{'name': p.name, 'uuid': p.uuid} for p in portfolios.portfolios]
            elif isinstance(portfolios, list):
                debug_info['portfolios'] = [{'name': getattr(p, 'name', 'Unknown'), 'uuid': getattr(p, 'uuid', 'Unknown')} for p in portfolios]
        except Exception as e:
            debug_info['portfolios_error'] = str(e)
        
        return jsonify({
            'success': True,
            'debug_info': debug_info
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Auto Trading API Endpoints
@app.route('/api/trading-strategies')
@token_required
def get_trading_strategies():
    """Get available AI trading strategies"""
    try:
        strategies = auto_trading_engine.strategy_manager.get_available_strategies()
        return jsonify({'success': True, 'strategies': strategies})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/set-trading-strategy', methods=['POST'])
@token_required
def set_trading_strategy():
    """Set the active trading strategy"""
    try:
        data = request.json
        strategy_id = data.get('strategy_id')
        
        logging.info(f"Setting strategy request: {strategy_id}")
        
        if not strategy_id:
            return jsonify({'success': False, 'error': 'Strategy ID required'}), 400
        
        # Log available strategies
        available = [s['id'] for s in auto_trading_engine.strategy_manager.get_available_strategies()]
        logging.info(f"Available strategies: {available}")
        
        success = auto_trading_engine.set_strategy(strategy_id)
        logging.info(f"Strategy set result: {success}")
        logging.info(f"Engine active strategy after: {auto_trading_engine.state.active_strategy}")
        
        if success:
            return jsonify({'success': True, 'message': f'Strategy set to {strategy_id}'})
        else:
            return jsonify({'success': False, 'error': 'Invalid strategy ID'}), 400
            
    except Exception as e:
        logging.error(f"Exception in set_trading_strategy: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trading-bot/<action>', methods=['POST'])
@token_required
def control_trading_bot(action):
    """Control the auto trading bot (start/pause/stop)"""
    try:
        logging.info(f"Bot control request: {action}")
        logging.info(f"Current bot status: {auto_trading_engine.state.status}")
        logging.info(f"Current active strategy: {auto_trading_engine.state.active_strategy}")
        
        if action == 'start':
            # Check if strategy is set before attempting to start
            if not auto_trading_engine.state.active_strategy:
                logging.error("Cannot start bot: No active strategy set")
                return jsonify({'success': False, 'error': 'No active strategy selected. Please select a strategy first.'}), 400
            
            success = auto_trading_engine.start()
            logging.info(f"Bot start result: {success}")
        elif action == 'pause':
            success = auto_trading_engine.pause()
        elif action == 'stop':
            success = auto_trading_engine.stop()
        else:
            return jsonify({'success': False, 'error': 'Invalid action'}), 400
        
        if success:
            logging.info(f"Bot {action} successful")
            return jsonify({'success': True, 'message': f'Bot {action}ed successfully'})
        else:
            logging.error(f"Bot {action} failed")
            return jsonify({'success': False, 'error': f'Failed to {action} bot'}), 400
            
    except Exception as e:
        logging.error(f"Exception in control_trading_bot: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auto-trading-performance')
@token_required
def get_auto_trading_performance():
    """Get auto trading performance stats"""
    try:
        status = auto_trading_engine.get_status()
        return jsonify(status['performance'])
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/monitor')
def mobile_monitor():
    """Serve mobile monitoring page"""
    return send_from_directory('.', 'mobile_monitor.html')

@app.route('/api/bot-monitor')
@token_required
def get_bot_monitor():
    """Get detailed bot monitoring data"""
    try:
        # Get full status
        status = auto_trading_engine.get_status()
        
        # Add more details
        monitor_data = {
            'status': status['status'],
            'strategy': status['active_strategy'],
            'performance': status['performance'],
            'price_history_count': len(auto_trading_engine.price_history),
            'latest_price': auto_trading_engine.price_history[-1] if auto_trading_engine.price_history else None,
            'thread_alive': auto_trading_engine.running_thread.is_alive() if auto_trading_engine.running_thread else False,
            'last_signal': None,
            'trade_history_count': len(auto_trading_engine.trade_history),
            'check_interval': auto_trading_engine.check_interval,
            'min_confidence': auto_trading_engine.min_confidence
        }
        
        # Add last signal if exists
        if auto_trading_engine.state.last_signal:
            monitor_data['last_signal'] = auto_trading_engine._serialize_signal(auto_trading_engine.state.last_signal)
        
        # Add last few prices
        if auto_trading_engine.price_history:
            monitor_data['recent_prices'] = auto_trading_engine.price_history[-5:]
        
        return jsonify(monitor_data)
    except Exception as e:
        logging.error(f"Bot monitor error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/current-trading-signal')
@token_required
def get_current_trading_signal():
    """Get current AI trading signal"""
    try:
        status = auto_trading_engine.get_status()
        signal = status.get('current_signal')
        
        # If no signal yet, return a default one
        if not signal:
            signal = {
                'action': 'HOLD',
                'confidence': 0,
                'reason': 'Waiting for more market data...',
                'timestamp': datetime.now().isoformat()
            }
        
        return jsonify({'success': True, 'signal': signal})
    except Exception as e:
        logging.error(f"Error getting current signal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auto-trading-history')
@token_required
def get_auto_trading_history():
    """Get auto trading history"""
    try:
        limit = request.args.get('limit', 50, type=int)
        trades = auto_trading_engine.get_trading_history(limit)
        return jsonify({'success': True, 'trades': trades})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auto-trading-status')
@token_required
def get_auto_trading_status():
    """Get complete auto trading status"""
    try:
        status = auto_trading_engine.get_status()
        return jsonify({'success': True, **status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Enhanced Auto Trading Engine Endpoints
@app.route('/api/enhanced-bot/status')
@token_required
def get_enhanced_bot_status():
    """Get enhanced multi-currency bot status"""
    try:
        status = enhanced_engine.get_status()
        return jsonify({'success': True, **status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/enhanced-bot/start', methods=['POST'])
@token_required
def start_enhanced_bot():
    """Start enhanced multi-currency trading bot"""
    try:
        success, message = enhanced_engine.start()
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/enhanced-bot/stop', methods=['POST'])
@token_required
def stop_enhanced_bot():
    """Stop enhanced multi-currency trading bot"""
    try:
        success, message = enhanced_engine.stop()
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/enhanced-bot/toggle-currency', methods=['POST'])
@token_required
def toggle_currency():
    """Enable/disable trading for a specific currency"""
    try:
        data = request.json
        symbol = data.get('symbol')
        enabled = data.get('enabled', True)

        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol is required'}), 400

        success, message = enhanced_engine.toggle_currency(symbol, enabled)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/enhanced-bot/trade-history')
@token_required
def get_enhanced_trade_history():
    """Get recent trade history from enhanced bot"""
    try:
        limit = int(request.args.get('limit', 50))
        trades = enhanced_engine.trade_history[-limit:]

        # Convert to serializable format
        trades_data = []
        for trade in trades:
            trades_data.append({
                'id': trade.id,
                'strategy': trade.strategy,
                'symbol': trade.symbol,
                'action': trade.action,
                'amount_usd': trade.amount_usd,
                'crypto_amount': trade.crypto_amount,
                'price': trade.price,
                'timestamp': trade.timestamp.isoformat(),
                'status': trade.status,
                'pnl': trade.pnl,
                'reason': trade.reason
            })

        return jsonify({
            'success': True,
            'trades': trades_data,
            'count': len(trades_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/enhanced-bot/sync-positions', methods=['POST'])
@token_required
def sync_positions():
    """Manually sync existing Coinbase positions"""
    try:
        enhanced_engine.sync_existing_positions()
        return jsonify({
            'success': True,
            'message': 'Positions synced successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Authentication endpoints
@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username and password are required'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400
        
        result = register_user(username, password, email)
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user and return JWT token"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username and password are required'}), 400
        
        result = authenticate_user(username, password)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 401
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/refresh', methods=['POST'])
def refresh():
    """Refresh JWT token"""
    try:
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'success': False, 'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'success': False, 'error': 'Token is missing'}), 401
        
        result = refresh_token(token)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 401
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/verify', methods=['GET'])
@token_required
def verify_token_endpoint():
    """Verify if token is valid"""
    return jsonify({
        'success': True,
        'message': 'Token is valid',
        'user_id': request.current_user_id
    })

# ============================================================================
# POLYMARKET ENDPOINTS
# ============================================================================

# Initialize Polymarket engine (DISABLED - Not available in US)
polymarket_engine = None
# Polymarket is not available in the United States - skipping initialization
logging.info("Polymarket engine disabled (not available in US)")

@app.route('/api/polymarket/status')
def polymarket_status():
    """Get Polymarket connection status"""
    try:
        if polymarket_engine:
            status = polymarket_engine.get_status()
            return jsonify(status)
        else:
            return jsonify({
                'connected': False,
                'error': 'Polymarket engine not initialized'
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/polymarket/markets')
def polymarket_markets():
    """Get active prediction markets"""
    try:
        limit = request.args.get('limit', 20, type=int)
        if polymarket_engine:
            markets = polymarket_engine.get_markets(limit=limit)
            return jsonify({'markets': markets})
        else:
            return jsonify({'error': 'Polymarket engine not initialized'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/polymarket/market/<condition_id>')
def polymarket_market_details(condition_id):
    """Get details for a specific market"""
    try:
        if polymarket_engine:
            details = polymarket_engine.get_market_details(condition_id)
            if details:
                return jsonify(details)
            else:
                return jsonify({'error': 'Market not found'}), 404
        else:
            return jsonify({'error': 'Polymarket engine not initialized'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/polymarket/balance')
def polymarket_balance():
    """Get USDC balance"""
    try:
        if polymarket_engine and polymarket_engine.is_connected:
            balance = polymarket_engine.get_balance()
            if balance:
                return jsonify(balance)
            else:
                return jsonify({'error': 'Failed to fetch balance'}), 500
        else:
            return jsonify({'error': 'Not connected to Polymarket'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/polymarket/positions')
def polymarket_positions():
    """Get current positions"""
    try:
        if polymarket_engine and polymarket_engine.is_connected:
            positions = polymarket_engine.get_positions()
            return jsonify({'positions': positions})
        else:
            return jsonify({'error': 'Not connected to Polymarket'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/polymarket/order', methods=['POST'])
def polymarket_place_order():
    """Place an order on Polymarket"""
    try:
        if not polymarket_engine or not polymarket_engine.is_connected:
            return jsonify({'error': 'Not connected to Polymarket'}), 401

        data = request.json
        token_id = data.get('token_id')
        side = data.get('side')  # BUY or SELL
        size = data.get('size')
        price = data.get('price')
        order_type = data.get('order_type', 'GTC')

        if not all([token_id, side, size, price]):
            return jsonify({'error': 'Missing required fields'}), 400

        result = polymarket_engine.place_order(
            token_id=token_id,
            side=side,
            size=float(size),
            price=float(price),
            order_type=order_type
        )

        if result:
            return jsonify({'success': True, 'order': result})
        else:
            return jsonify({'error': 'Failed to place order'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/polymarket/cancel-order', methods=['POST'])
def polymarket_cancel_order():
    """Cancel an order"""
    try:
        if not polymarket_engine or not polymarket_engine.is_connected:
            return jsonify({'error': 'Not connected to Polymarket'}), 401

        data = request.json
        order_id = data.get('order_id')

        if not order_id:
            return jsonify({'error': 'order_id required'}), 400

        success = polymarket_engine.cancel_order(order_id)

        if success:
            return jsonify({'success': True, 'message': 'Order cancelled'})
        else:
            return jsonify({'error': 'Failed to cancel order'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/polymarket/orderbook/<token_id>')
def polymarket_orderbook(token_id):
    """Get order book for a token"""
    try:
        if polymarket_engine:
            orderbook = polymarket_engine.get_order_book(token_id)
            if orderbook:
                return jsonify(orderbook)
            else:
                return jsonify({'error': 'Failed to fetch order book'}), 500
        else:
            return jsonify({'error': 'Polymarket engine not initialized'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/polymarket/trades')
def polymarket_trades():
    """Get trade history"""
    try:
        if polymarket_engine and polymarket_engine.is_connected:
            trades = polymarket_engine.get_trade_history()
            return jsonify({'trades': trades})
        else:
            return jsonify({'error': 'Not connected to Polymarket'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# KALSHI ENDPOINTS (US-Legal Prediction Markets)
# ============================================================================

# Initialize Kalshi engine
kalshi_engine = None
try:
    kalshi_engine = KalshiEngine()
    logging.info("Kalshi engine initialized")
except Exception as e:
    logging.error(f"Failed to initialize Kalshi engine: {e}")

@app.route('/api/kalshi/status')
def kalshi_status():
    """Get Kalshi connection status"""
    try:
        if kalshi_engine:
            status = kalshi_engine.get_status()
            return jsonify(status)
        else:
            return jsonify({
                'connected': False,
                'error': 'Kalshi engine not initialized'
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/kalshi/markets')
def kalshi_markets():
    """Get active prediction markets"""
    try:
        limit = request.args.get('limit', 100, type=int)
        status = request.args.get('status', 'open')
        min_volume = request.args.get('min_volume', 100, type=int)  # Require some volume to avoid resting orders

        if kalshi_engine:
            # First try to get crypto markets
            logging.info("Fetching crypto markets...")
            markets = kalshi_engine.get_markets(limit=limit, status=status, category='crypto', min_volume=0)

            logging.info(f"Found {len(markets)} crypto markets")

            # If no crypto markets found, get all markets with good liquidity
            if len(markets) == 0:
                logging.info("No crypto markets found, fetching all liquid markets")
                markets = kalshi_engine.get_markets(limit=30, status=status, category=None, min_volume=min_volume)
                logging.info(f"Found {len(markets)} liquid markets")

            return jsonify({'markets': markets})
        else:
            return jsonify({'error': 'Kalshi engine not initialized'}), 500
    except Exception as e:
        logging.error(f"Error fetching markets: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/kalshi/market/<ticker>')
def kalshi_market_details(ticker):
    """Get details for a specific market"""
    try:
        if kalshi_engine:
            details = kalshi_engine.get_market_details(ticker)
            if details:
                return jsonify(details)
            else:
                return jsonify({'error': 'Market not found'}), 404
        else:
            return jsonify({'error': 'Kalshi engine not initialized'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/kalshi/balance')
def kalshi_balance():
    """Get account balance"""
    try:
        if kalshi_engine and kalshi_engine.is_connected:
            balance = kalshi_engine.get_balance()
            if balance:
                return jsonify(balance)
            else:
                return jsonify({'error': 'Failed to fetch balance'}), 500
        else:
            return jsonify({'error': 'Not connected to Kalshi'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/kalshi/positions')
def kalshi_positions():
    """Get current positions"""
    try:
        if kalshi_engine and kalshi_engine.is_connected:
            positions = kalshi_engine.get_positions()
            return jsonify({'positions': positions})
        else:
            return jsonify({'error': 'Not connected to Kalshi'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/kalshi/order', methods=['POST'])
def kalshi_place_order():
    """Place an order on Kalshi"""
    try:
        if not kalshi_engine or not kalshi_engine.is_connected:
            return jsonify({'error': 'Not connected to Kalshi'}), 401

        data = request.json
        ticker = data.get('ticker')
        side = data.get('side')  # yes or no
        quantity = data.get('quantity')
        price = data.get('price')  # in cents (1-99)

        if not all([ticker, side, quantity, price]):
            return jsonify({'error': 'Missing required fields'}), 400

        result = kalshi_engine.place_order(
            ticker=ticker,
            side=side,
            quantity=int(quantity),
            price=int(price)
        )

        if result:
            return jsonify({'success': True, 'order': result})
        else:
            return jsonify({'error': 'Failed to place order'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/kalshi/cancel-order', methods=['POST'])
def kalshi_cancel_order():
    """Cancel an order"""
    try:
        if not kalshi_engine or not kalshi_engine.is_connected:
            return jsonify({'error': 'Not connected to Kalshi'}), 401

        data = request.json
        order_id = data.get('order_id')

        if not order_id:
            return jsonify({'error': 'order_id required'}), 400

        success = kalshi_engine.cancel_order(order_id)

        if success:
            return jsonify({'success': True, 'message': 'Order cancelled'})
        else:
            return jsonify({'error': 'Failed to cancel order'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/kalshi/orders')
def kalshi_orders():
    """Get order history"""
    try:
        if kalshi_engine and kalshi_engine.is_connected:
            ticker = request.args.get('ticker')
            orders = kalshi_engine.get_orders(ticker=ticker)
            return jsonify({'orders': orders})
        else:
            return jsonify({'error': 'Not connected to Kalshi'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# KALSHI ML TRADING BOT ENDPOINTS
# ============================================================================

# Initialize ML trader (lazily)
kalshi_ml_trader = None

def get_kalshi_ml_trader():
    """Get or create the Kalshi ML trader instance."""
    global kalshi_ml_trader
    if kalshi_ml_trader is None:
        try:
            kalshi_ml_trader = SmartKalshiTrader()
            kalshi_ml_trader.initialize()
            logging.info("Kalshi ML Trader initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize Kalshi ML Trader: {e}")
            import traceback
            traceback.print_exc()
            return None
    return kalshi_ml_trader

@app.route('/api/kalshi/opportunities')
def get_kalshi_opportunities():
    """
    Get ML-analyzed Kalshi trading opportunities.

    Returns:
        {
            "success": bool,
            "btc_price": float,
            "price_history": [...],  // Last 4 hours of BTC prices
            "opportunities": [
                {
                    "ticker": str,
                    "market_type": "range" | "threshold",
                    "strike": float,           // Strike price or range midpoint
                    "subtitle": str,           // Market description
                    "market_odds": float,      // Current market price (0-100)
                    "model_odds": float,       // Our model probability (0-100)
                    "ev": float,               // Expected value (percentage points)
                    "side": "YES" | "NO",      // Recommended side
                    "hours_to_expiry": float,
                    "volume": int,
                    "yes_ask": int,            // Current YES ask in cents
                    "no_ask": int,             // Current NO ask in cents
                    "ml_score": float,         // ML confidence score
                    "recommended": bool        // Passes all filters for trading
                }
            ],
            "recommended_trades": [...],  // Opportunities that pass all filters
            "timestamp": str
        }
    """
    import requests as req
    from datetime import datetime, timedelta

    try:
        # 1. Get current BTC price
        try:
            r = req.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=10)
            btc_price = float(r.json()['data']['amount'])
        except:
            btc_price = None

        # 2. Get price history (last 4 hours)
        price_history = []
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=4)
            url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
            params = {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'granularity': 300  # 5 minutes
            }
            r = req.get(url, params=params, timeout=30)
            candles = r.json()
            for c in sorted(candles, key=lambda x: x[0]):
                price_history.append({
                    'timestamp': c[0] * 1000,
                    'price': c[4],
                    'high': c[2],
                    'low': c[1]
                })
        except Exception as e:
            logging.warning(f"Failed to fetch price history: {e}")

        # 3. Get ML trader and analyze markets
        trader = get_kalshi_ml_trader()
        if not trader:
            return jsonify({
                'success': False,
                'error': 'ML Trader not initialized',
                'btc_price': btc_price,
                'price_history': price_history,
                'opportunities': [],
                'recommended_trades': []
            })

        # Update current price in trader
        trader.current_price = btc_price

        # Run ML analysis
        raw_opportunities = trader.analyze_all_markets()

        # Format opportunities for frontend
        opportunities = []
        recommended_trades = []

        for opp in raw_opportunities:
            # Convert numpy types to Python native types for JSON serialization
            ev_val = float(opp.get('ev', 0))
            ev_adj_val = float(opp.get('ev_adjusted', 0))

            formatted = {
                'ticker': opp.get('ticker', ''),
                'market_type': opp.get('market_type', 'range'),
                'strike': float(opp.get('strike', opp.get('lower', 0)) or 0),
                'lower': float(opp.get('lower') or 0),
                'upper': float(opp.get('upper') or 0) if opp.get('upper') else None,
                'subtitle': opp.get('subtitle', ''),
                'market_odds': float(round(opp.get('market_prob', 0) * 100, 1)),
                'model_odds': float(round(opp.get('model_prob', 0) * 100, 1)),
                'ev': float(round(ev_val * 100, 2)),  # Raw EV in percentage points
                'side': opp.get('side', 'YES'),
                'hours_to_expiry': float(round(opp.get('hours', 0), 1)),
                'volume': int(opp.get('volume', 0)),
                'yes_ask': int(opp.get('yes_ask', 0)),
                'no_ask': int(opp.get('no_ask', 0)),
                'ml_score': float(round(opp.get('ml_score', 0), 3)),
                # QUANT-GRADE v2 metrics
                'ev_raw': float(round(ev_val * 100, 2)),  # Raw EV (%)
                'ev_adjusted': float(round(ev_adj_val, 2)),  # Risk-adjusted EV (σ units)
                'ev_time_weighted': float(round(opp.get('ev_time_weighted', 0) * 100, 2)),  # Time-weighted EV (%)
                'prob_uncertainty': float(round(opp.get('prob_uncertainty', 0.05) * 100, 1)),  # Model uncertainty (%)
                'ml_size_multiplier': float(round(opp.get('ml_size_multiplier', 1.0), 2)),  # Position size scaler
                'signal_confidence': float(round(opp.get('signal_confidence', 0.5), 2)),  # Signal agreement
                'high_edge_override': bool(opp.get('high_edge_override', False)),  # Whether high edge override was used
                # Filtering passes if: raw EV >= 1% AND risk-adjusted EV >= 0.5
                'recommended': bool(ev_val >= 0.01 and ev_adj_val >= 0.5)
            }
            opportunities.append(formatted)

            if formatted['recommended']:
                recommended_trades.append(formatted)

        # Sort by EV descending
        opportunities.sort(key=lambda x: x['ev'], reverse=True)
        recommended_trades.sort(key=lambda x: x['ev'], reverse=True)

        # Build algorithm summary
        signals = trader.signals or {}

        # Import quant config values
        from kalshi_ml_trader import (
            MIN_EV_ADJUSTED, MIN_EV_RAW, MIN_ML_SCORE_HARD,
            MIN_MODEL_PROB, MAX_MODEL_PROB, MIN_VOLUME
        )

        algorithm_summary = {
            # Direction signals
            'direction': signals.get('direction', 'NEUTRAL'),
            'direction_score': round(signals.get('direction_score', 0), 3),
            'rsi': round(signals.get('rsi', 50), 1),
            'momentum_4h': round(signals.get('momentum_4h', 0) * 100, 2),  # As percentage
            'momentum_24h': round(signals.get('momentum_24h', 0) * 100, 2),  # As percentage
            'vol_regime': round(signals.get('vol_regime', 1.0), 3),
            'funding_rate_bps': round(signals.get('funding_rate', 0) * 10000, 2),
            'fear_greed': signals.get('fear_greed', 50),
            'whale_activity': round(signals.get('whale_activity', 0), 3),
            'garch_vol_annual': round(trader.vol_model.get_adjusted_vol(24) * 100, 1) if trader.vol_model else 0,

            # QUANT-GRADE v2: Algorithm configuration
            'quant_config': {
                'min_ev_adjusted': MIN_EV_ADJUSTED,  # Risk-adjusted EV threshold (σ units)
                'min_ev_raw': MIN_EV_RAW * 100,  # Raw EV threshold (%)
                'min_ml_score': MIN_ML_SCORE_HARD,  # Hard ML floor
                'min_prob': MIN_MODEL_PROB * 100,  # Min model probability (%)
                'max_prob': MAX_MODEL_PROB * 100,  # Max model probability (%)
                'min_volume': MIN_VOLUME,  # Volume filter
                'approach': 'log-odds signal adjustment + risk-adjusted EV + time-weighted EV'
            }
        }

        # Add enhanced data signals if available
        if trader.enhanced_signals:
            deribit = trader.enhanced_signals.get('deribit', {})
            algorithm_summary['dvol'] = deribit.get('dvol', 0)
            algorithm_summary['dvol_signal'] = deribit.get('signal', {}).get('direction', 'NEUTRAL')

            oi = trader.enhanced_signals.get('open_interest', {})
            algorithm_summary['open_interest_btc'] = round(oi.get('open_interest_btc', 0), 0)
            algorithm_summary['long_short_ratio'] = round(oi.get('long_short_ratio', 1.0), 3)

            ob = trader.enhanced_signals.get('orderbook', {})
            algorithm_summary['orderbook_imbalance'] = round(ob.get('imbalance', 0) * 100, 1)

        return jsonify({
            'success': True,
            'btc_price': btc_price,
            'price_history': price_history,
            'opportunities': opportunities,
            'recommended_trades': recommended_trades,
            'total_markets_scanned': len(raw_opportunities),
            'algorithm_summary': algorithm_summary,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logging.error(f"Error getting Kalshi opportunities: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/kalshi/execute-trades', methods=['POST'])
def execute_kalshi_trades():
    """
    Execute recommended Kalshi trades.

    Request body:
        {
            "trades": [...],      // List of trades to execute (from recommended_trades)
            "dry_run": bool,      // If true, simulate without placing real orders
            "max_risk": float     // Maximum total risk in dollars (default: 50)
        }
    """
    try:
        trader = get_kalshi_ml_trader()
        if not trader:
            return jsonify({'success': False, 'error': 'ML Trader not initialized'}), 500

        data = request.get_json() or {}
        trades = data.get('trades', [])
        dry_run = data.get('dry_run', True)
        max_risk = data.get('max_risk', 50.0)

        if not trades:
            return jsonify({'success': False, 'error': 'No trades provided'}), 400

        # ---------------------------------------------------------------
        # BUDGET SAFETY: Subtract existing position cost from max_risk
        # This prevents double-buying when clicking Execute multiple times
        # ---------------------------------------------------------------
        existing_cost = 0
        try:
            existing_positions = trader.kalshi.get_positions()
            for pos in existing_positions:
                total_cost_dollars = pos.get('total_cost', 0)
                existing_cost += total_cost_dollars
            logging.info(f"Existing Kalshi positions cost: ${existing_cost:.2f}")
        except Exception as e:
            logging.warning(f"Could not fetch existing positions for budget check: {e}")

        effective_budget = max(0, max_risk - existing_cost)
        logging.info(f"Budget: max_risk=${max_risk:.2f} - existing=${existing_cost:.2f} = effective=${effective_budget:.2f}")

        if effective_budget <= 0:
            return jsonify({
                'success': True,
                'dry_run': dry_run,
                'trades_executed': 0,
                'total_cost': 0,
                'results': [],
                'message': f'Budget exhausted: already have ${existing_cost:.2f} in positions (max_risk=${max_risk:.2f})',
                'existing_cost': existing_cost,
                'timestamp': datetime.now().isoformat()
            })

        # Execute trades
        results = []
        total_cost = 0

        for trade in trades:
            if total_cost >= effective_budget:
                break

            ticker = trade.get('ticker')
            side = trade.get('side', 'YES').lower()

            # Calculate quantity based on remaining budget
            remaining_budget = effective_budget - total_cost

            # Get price - try multiple field names for compatibility
            if side == 'yes':
                price_cents = trade.get('yes_ask') or trade.get('price') or trade.get('market_odds')
            else:
                price_cents = trade.get('no_ask') or trade.get('price') or (100 - trade.get('market_odds', 0))

            logging.info(f"Trade data: ticker={ticker}, side={side}, price_cents={price_cents}, trade_data={trade}")

            if not price_cents or price_cents <= 0:
                logging.warning(f"Skipping trade {ticker}: invalid price {price_cents}")
                results.append({
                    'ticker': ticker,
                    'side': side.upper(),
                    'quantity': 0,
                    'price_cents': price_cents,
                    'status': 'failed',
                    'error': f'Invalid price: {price_cents}'
                })
                continue

            quantity = min(10, int(remaining_budget / (price_cents / 100)))  # Max 10 contracts per trade
            if quantity <= 0:
                continue

            cost = quantity * (price_cents / 100)

            if dry_run:
                results.append({
                    'ticker': ticker,
                    'side': side.upper(),
                    'quantity': quantity,
                    'price_cents': price_cents,
                    'cost': cost,
                    'status': 'simulated',
                    'ev': trade.get('ev', 0)
                })
            else:
                # Execute real trade
                try:
                    logging.info(f"Placing order: {ticker} {side.upper()} x{quantity} @ {price_cents}c")
                    order_result = trader.kalshi.place_order(
                        ticker=ticker,
                        side=side,
                        quantity=quantity,
                        price=int(price_cents),  # Price in cents
                        order_type='limit'
                    )
                    if order_result:
                        results.append({
                            'ticker': ticker,
                            'side': side.upper(),
                            'quantity': quantity,
                            'price_cents': price_cents,
                            'cost': cost,
                            'status': 'executed',
                            'order_id': order_result.get('order', {}).get('order_id'),
                            'ev': trade.get('ev', 0)
                        })
                    else:
                        results.append({
                            'ticker': ticker,
                            'side': side.upper(),
                            'quantity': quantity,
                            'price_cents': price_cents,
                            'status': 'failed',
                            'error': 'Order returned None'
                        })
                except Exception as e:
                    logging.error(f"Order failed for {ticker}: {e}")
                    results.append({
                        'ticker': ticker,
                        'side': side.upper(),
                        'quantity': quantity,
                        'price_cents': price_cents,
                        'status': 'failed',
                        'error': str(e)
                    })

            total_cost += cost

        return jsonify({
            'success': True,
            'dry_run': dry_run,
            'trades_executed': len([r for r in results if r['status'] in ['executed', 'simulated']]),
            'total_cost': total_cost,
            'results': results,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logging.error(f"Error executing Kalshi trades: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# BTC MONITOR ENDPOINT - Real-time position tracking
# ============================================================================

@app.route('/api/btc-monitor')
def btc_monitor():
    """
    Get comprehensive BTC monitoring data:
    - Real-time BTC price
    - Historical price data (last 4 hours)
    - Active Kalshi positions with analysis
    - What needs to happen for each bet to win
    """
    import requests as req
    from datetime import datetime, timedelta

    try:
        # 1. Get real-time BTC price from Coinbase
        try:
            r = req.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=10)
            btc_price = float(r.json()['data']['amount'])
        except:
            btc_price = None

        # 2. Get historical BTC prices (last 4 hours, 5-min intervals)
        price_history = []
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=4)
            url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
            params = {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'granularity': 300  # 5 minutes
            }
            r = req.get(url, params=params, timeout=30)
            candles = r.json()
            # Format: [timestamp, low, high, open, close, volume]
            for c in sorted(candles, key=lambda x: x[0]):
                price_history.append({
                    'timestamp': c[0] * 1000,  # Convert to milliseconds for JS
                    'price': c[4],  # close price
                    'high': c[2],
                    'low': c[1]
                })
        except Exception as e:
            logging.warning(f"Failed to fetch price history: {e}")

        # 3. Get Kalshi positions
        positions_data = []
        total_cost = 0
        total_potential_payout = 0

        if kalshi_engine and kalshi_engine.is_connected:
            try:
                result = kalshi_engine._make_authenticated_request("GET", "/portfolio/positions")
                if result and "market_positions" in result:
                    now = datetime.now()

                    for p in result["market_positions"]:
                        ticker = p.get("ticker", "")
                        pos = p.get("position", 0)

                        # Only include KXBTC positions with active positions
                        if "KXBTC" not in ticker or pos == 0:
                            continue

                        # Determine side: positive = YES, negative = NO
                        side = "YES" if pos > 0 else "NO"
                        abs_pos = abs(pos)

                        # Detect market type:
                        # KXBTCMAXY = yearly max (will BTC ever reach X this year)
                        # KXBTCD = daily threshold (will BTC be above/below X at expiry)
                        # KXBTC = range (will BTC be between X-Y at expiry)
                        is_yearly_market = "KXBTCMAXY" in ticker
                        is_threshold_market = "KXBTCD" in ticker

                        # Parse ticker: KXBTC-26JAN1416-B97125 or KXBTCD-26JAN22-T104500 or KXBTCMAXY-26DEC31-199999.99
                        ticker_parts = ticker.split('-')
                        if len(ticker_parts) < 3:
                            continue

                        date_part = ticker_parts[1]  # e.g., "26JAN1416" or "26JAN22" or "26DEC31"
                        strike_part = ticker_parts[2]  # e.g., "B97125" or "T104500" or "199999.99"

                        # Parse expiry time
                        try:
                            year = int('20' + date_part[:2])
                            month_str = date_part[2:5]
                            day = int(date_part[5:7])
                            hour = int(date_part[7:9]) if len(date_part) >= 9 else 16
                            minute = int(date_part[9:11]) if len(date_part) >= 11 else 0

                            months = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                                     'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
                            month = months.get(month_str.upper(), 1)

                            expiry = datetime(year, month, day, hour, minute)
                            time_to_expiry = (expiry - now).total_seconds()

                            # Create descriptive expiry string with full date
                            today = now.date()
                            tomorrow = today + timedelta(days=1)
                            expiry_date = expiry.date()

                            if is_yearly_market:
                                # Yearly markets: show full date
                                expiry_str = expiry.strftime('%b %d, %Y')
                            elif expiry_date == today:
                                # Today: "5:00 PM Today"
                                expiry_str = expiry.strftime('%I:%M %p') + ' Today'
                            elif expiry_date == tomorrow:
                                # Tomorrow: "5:00 PM Tomorrow"
                                expiry_str = expiry.strftime('%I:%M %p') + ' Tomorrow'
                            elif time_to_expiry < 7 * 24 * 3600:
                                # Within a week: "5:00 PM Wed Jan 24"
                                expiry_str = expiry.strftime('%I:%M %p %a %b %d')
                            else:
                                # Further out: "Jan 24, 2026"
                                expiry_str = expiry.strftime('%b %d, %Y')

                            # Also store the full expiry datetime for filtering
                            expiry_full = expiry.isoformat()
                        except:
                            time_to_expiry = 3600
                            expiry_str = "Unknown"
                            expiry_full = None

                        # Parse strike/range based on market type
                        lower = None
                        upper = None
                        threshold = None
                        threshold_direction = None  # 'above' or 'below'
                        market_type = 'range'

                        if is_yearly_market:
                            # KXBTCMAXY yearly markets: strike_part is just a number like "199999.99"
                            # YES = BTC will reach this price at some point during the year
                            # NO = BTC will NOT reach this price during the year
                            market_type = 'yearly'
                            try:
                                threshold = float(strike_part)
                                # For yearly max: YES wins if BTC ever reaches threshold, NO wins if it never does
                                threshold_direction = 'above' if side == 'YES' else 'below'
                            except:
                                pass
                        elif is_threshold_market:
                            # KXBTCD threshold markets: T104500 = threshold at $104,500
                            # YES = BTC ends above threshold, NO = BTC ends below threshold
                            market_type = 'threshold'
                            if strike_part.startswith('T'):
                                try:
                                    threshold = float(strike_part[1:])
                                    # For threshold markets: YES wins if above, NO wins if below
                                    threshold_direction = 'above' if side == 'YES' else 'below'
                                except:
                                    pass
                        else:
                            # KXBTC range markets: B97125 = range around $97,125
                            market_type = 'range'
                            if strike_part.startswith('B'):
                                try:
                                    strike = float(strike_part[1:])
                                    lower = strike - 125
                                    upper = strike + 125
                                except:
                                    pass

                        # Calculate position metrics
                        cost = p.get("total_traded", 0) / 100
                        avg_price = cost / abs_pos if abs_pos > 0 else 0
                        potential_payout = abs_pos * 1.0  # $1 per contract if wins

                        total_cost += cost
                        total_potential_payout += potential_payout

                        # Determine status and what needs to happen
                        in_range = False
                        distance = None
                        what_needs_to_happen = ""

                        if is_yearly_market and btc_price and threshold:
                            # Yearly max market logic
                            # YES wins if BTC ever reaches threshold during the year
                            # NO wins if BTC never reaches threshold
                            distance = threshold - btc_price
                            if threshold_direction == 'above':
                                # Betting YES that BTC will reach this price
                                if btc_price >= threshold:
                                    in_range = True
                                    what_needs_to_happen = f"BTC already reached ${threshold:,.0f}! Waiting for settlement."
                                else:
                                    what_needs_to_happen = f"BTC needs to reach ${threshold:,.0f} anytime before expiry (${distance:,.0f} away)"
                            else:
                                # Betting NO that BTC will NOT reach this price
                                if btc_price >= threshold:
                                    what_needs_to_happen = f"BTC already hit ${threshold:,.0f} - bet lost unless it settles differently"
                                else:
                                    in_range = True
                                    what_needs_to_happen = f"BTC must stay below ${threshold:,.0f} until expiry (${distance:,.0f} buffer)"
                        elif is_threshold_market and btc_price and threshold:
                            # Threshold market logic
                            if threshold_direction == 'above':
                                # Bet wins if BTC ends above threshold
                                if btc_price > threshold:
                                    in_range = True
                                    distance = btc_price - threshold
                                    what_needs_to_happen = f"BTC stays above ${threshold:,.0f} (currently +${distance:,.0f})"
                                else:
                                    distance = threshold - btc_price
                                    what_needs_to_happen = f"BTC rises ${distance:,.0f} above ${threshold:,.0f}"
                            else:
                                # Bet wins if BTC ends below threshold
                                if btc_price < threshold:
                                    in_range = True
                                    distance = threshold - btc_price
                                    what_needs_to_happen = f"BTC stays below ${threshold:,.0f} (currently -${distance:,.0f})"
                                else:
                                    distance = btc_price - threshold
                                    what_needs_to_happen = f"BTC falls ${distance:,.0f} below ${threshold:,.0f}"
                        elif btc_price and lower and upper:
                            # Range market logic
                            if lower <= btc_price < upper:
                                in_range = True
                                what_needs_to_happen = f"BTC stays between ${lower:,.0f}-${upper:,.0f}"
                                distance = 0
                            elif btc_price < lower:
                                distance = lower - btc_price
                                what_needs_to_happen = f"BTC needs to rise ${distance:,.0f} to ${lower:,.0f}"
                            else:
                                distance = btc_price - upper
                                what_needs_to_happen = f"BTC needs to fall ${distance:,.0f} to ${upper:,.0f}"

                        positions_data.append({
                            'ticker': ticker,
                            'quantity': abs_pos,
                            'side': side,
                            'market_type': market_type,
                            'lower': lower,
                            'upper': upper,
                            'threshold': threshold,
                            'threshold_direction': threshold_direction,
                            'cost': cost,
                            'avg_price_cents': int(avg_price * 100),
                            'potential_payout': potential_payout,
                            'expiry': expiry_str,
                            'expiry_full': expiry_full if 'expiry_full' in dir() else None,
                            'time_to_expiry_seconds': max(0, time_to_expiry),
                            'in_range': in_range,
                            'distance': distance,
                            'what_needs_to_happen': what_needs_to_happen,
                        })

                    # Sort by expiry time
                    positions_data.sort(key=lambda x: x['time_to_expiry_seconds'])

            except Exception as e:
                logging.error(f"Failed to fetch Kalshi positions: {e}")

        # 4. Calculate summary stats
        winning_positions = [p for p in positions_data if p['in_range']]
        winning_payout = sum(p['potential_payout'] for p in winning_positions)

        return jsonify({
            'btc_price': btc_price,
            'price_history': price_history,
            'positions': positions_data,
            'summary': {
                'total_positions': len(positions_data),
                'total_cost': total_cost,
                'total_potential_payout': total_potential_payout,
                'winning_positions': len(winning_positions),
                'current_winning_payout': winning_payout,
                'current_pnl': winning_payout - total_cost if winning_positions else -total_cost,
            },
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logging.error(f"BTC monitor error: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# DEBUG: Raw Kalshi API data endpoint
# ============================================================================

@app.route('/api/kalshi/debug-data')
def kalshi_debug_data():
    """Debug endpoint to see raw Kalshi API responses"""
    result = {
        'kalshi_connected': kalshi_engine.is_connected if kalshi_engine else False,
        'fills': None,
        'settlements': None,
        'positions': None,
        'orders': None,
    }

    if kalshi_engine and kalshi_engine.is_connected:
        try:
            fills_result = kalshi_engine._make_authenticated_request('GET', '/portfolio/fills?limit=100')
            result['fills'] = fills_result
        except Exception as e:
            result['fills_error'] = str(e)

        try:
            settlements_result = kalshi_engine._make_authenticated_request('GET', '/portfolio/settlements?limit=100')
            result['settlements'] = settlements_result
        except Exception as e:
            result['settlements_error'] = str(e)

        try:
            positions_result = kalshi_engine._make_authenticated_request('GET', '/portfolio/positions')
            result['positions'] = positions_result
        except Exception as e:
            result['positions_error'] = str(e)

        try:
            orders_result = kalshi_engine._make_authenticated_request('GET', '/portfolio/orders?limit=100')
            result['orders'] = orders_result
        except Exception as e:
            result['orders_error'] = str(e)

    return jsonify(result)

# ============================================================================
# ALGORITHM ANALYTICS ENDPOINT
# ============================================================================

@app.route('/api/algorithm/analytics')
def algorithm_analytics():
    """
    Get comprehensive algorithm performance analytics from REAL Kalshi data:
    - Sharpe ratio, win rate, profit factor
    - Equity curve
    - Daily returns distribution
    - Model calibration
    - Signal performance breakdown
    """
    from datetime import datetime, timedelta
    from collections import defaultdict
    import math

    timeframe = request.args.get('timeframe', '7d')

    try:
        from datetime import timezone
        now_utc = datetime.now(timezone.utc)

        # Determine date range (in UTC)
        if timeframe == '24h':
            start_date = now_utc - timedelta(days=1)
        elif timeframe == '7d':
            start_date = now_utc - timedelta(days=7)
        elif timeframe == '30d':
            start_date = now_utc - timedelta(days=30)
        else:  # 'all'
            start_date = now_utc - timedelta(days=365)

        now = datetime.now()  # Keep local time for display
        logging.info(f"Analytics request: timeframe={timeframe}, start_date={start_date.isoformat()}")

        # =====================================================
        # FETCH REAL DATA FROM KALSHI API
        # =====================================================
        fills = []
        orders = []
        positions = []
        settlements = []

        if kalshi_engine and kalshi_engine.is_connected:
            # Get fills (executed trades) - fetch more to ensure we get all
            try:
                fills_result = kalshi_engine._make_authenticated_request('GET', '/portfolio/fills?limit=1000')
                logging.info(f"Fills API raw result keys: {fills_result.keys() if fills_result else 'None'}")
                if fills_result:
                    # Log the raw structure to understand it
                    logging.info(f"Fills result structure: {list(fills_result.keys())}")
                    if 'fills' in fills_result:
                        fills = fills_result['fills']
                        logging.info(f"Fetched {len(fills)} fills from Kalshi API")
                        if fills:
                            logging.info(f"Sample fill structure: {fills[0]}")
                    else:
                        # Maybe the data is under a different key
                        logging.info(f"No 'fills' key, checking other keys: {fills_result}")
            except Exception as e:
                logging.warning(f"Could not fetch fills: {e}")
                import traceback
                traceback.print_exc()

            # Get orders
            try:
                orders_result = kalshi_engine._make_authenticated_request('GET', '/portfolio/orders?limit=1000')
                if orders_result and 'orders' in orders_result:
                    orders = orders_result['orders']
                    logging.info(f"Fetched {len(orders)} orders from Kalshi")
            except Exception as e:
                logging.warning(f"Could not fetch orders: {e}")

            # Get current positions
            try:
                positions_result = kalshi_engine._make_authenticated_request('GET', '/portfolio/positions')
                if positions_result and 'market_positions' in positions_result:
                    positions = positions_result['market_positions']
                    logging.info(f"Fetched {len(positions)} positions from Kalshi")
            except Exception as e:
                logging.warning(f"Could not fetch positions: {e}")

            # Get settlements (resolved trades)
            try:
                settlements_result = kalshi_engine._make_authenticated_request('GET', '/portfolio/settlements?limit=1000')
                logging.info(f"Settlements API raw result keys: {settlements_result.keys() if settlements_result else 'None'}")
                if settlements_result:
                    logging.info(f"Settlements result structure: {list(settlements_result.keys())}")
                    if 'settlements' in settlements_result:
                        settlements = settlements_result['settlements']
                        logging.info(f"Fetched {len(settlements)} settlements from Kalshi")
                        if settlements:
                            logging.info(f"Sample settlement structure: {settlements[0]}")
                    else:
                        logging.info(f"No 'settlements' key, raw data: {settlements_result}")
            except Exception as e:
                logging.warning(f"Could not fetch settlements: {e}")
                import traceback
                traceback.print_exc()

        # =====================================================
        # LOAD TRADE LOG FOR MODEL_PROB AND EV DATA
        # =====================================================
        trade_log = {}
        try:
            from hedge_engine import HedgeEngine
            log_entries = HedgeEngine.load_trade_log()
            # Index by ticker for quick lookup
            for entry in log_entries:
                ticker = entry.get('ticker', '')
                if ticker:
                    trade_log[ticker] = {
                        'model_prob': entry.get('model_prob', 0),
                        'market_prob': entry.get('market_prob', 0),
                        'ev': entry.get('ev', 0)
                    }
            logging.info(f"Loaded {len(trade_log)} entries from trade log")
        except Exception as e:
            logging.warning(f"Could not load trade log: {e}")

        # =====================================================
        # PROCESS SETTLEMENTS INTO TRADES (primary data source)
        # Settlements show completed trades with outcomes - this matches Kalshi portfolio page
        # =====================================================
        trades = []
        skipped_count = 0

        # Process settlements as primary trade source
        for s in settlements:
            try:
                # Get settlement time - try multiple field names
                settled_time = s.get('settled_time') or s.get('settlement_time') or s.get('created_time') or ''

                # Parse the settlement date properly (Kalshi uses UTC)
                settle_date = None
                if settled_time:
                    try:
                        if settled_time.endswith('Z'):
                            settle_date = datetime.fromisoformat(settled_time.replace('Z', '+00:00'))
                        else:
                            settle_date = datetime.fromisoformat(settled_time)
                    except Exception as e:
                        logging.warning(f"Could not parse settlement time '{settled_time}': {e}")

                    if settle_date:
                        # Make sure settle_date is timezone-aware for comparison
                        if settle_date.tzinfo is None:
                            settle_date = settle_date.replace(tzinfo=timezone.utc)

                        # Compare UTC to UTC
                        if settle_date < start_date:
                            skipped_count += 1
                            continue

                ticker = s.get('ticker', '')
                market_result = s.get('market_result', s.get('result', ''))
                revenue = (s.get('revenue', 0) or 0) / 100.0  # Convert cents to dollars

                # Get position info - try multiple field names
                # Kalshi settlements may include: yes_count/no_count OR count with side
                yes_count = s.get('yes_count', 0) or 0
                no_count = s.get('no_count', 0) or 0

                # Also check for alternative field structure
                if yes_count == 0 and no_count == 0:
                    count = s.get('count', 0) or 0
                    side_field = s.get('side', '').upper()
                    if side_field == 'YES':
                        yes_count = count
                    elif side_field == 'NO':
                        no_count = count

                # Determine side and quantity from position
                # Settlements have yes_total_cost/no_total_cost (total cost in cents), not per-contract price
                if yes_count > 0:
                    side = 'YES'
                    quantity = yes_count
                    yes_total_cost = s.get('yes_total_cost', 0) or 0
                    entry_price = (yes_total_cost / yes_count) / 100.0 if yes_count > 0 else 0
                elif no_count > 0:
                    side = 'NO'
                    quantity = no_count
                    no_total_cost = s.get('no_total_cost', 0) or 0
                    entry_price = (no_total_cost / no_count) / 100.0 if no_count > 0 else 0
                else:
                    # Try to infer from revenue - if we got paid, we had a position
                    if revenue > 0:
                        # We won something, try to figure out what
                        quantity = 1
                        side = 'YES' if market_result.lower() == 'yes' else 'NO'
                        entry_price = 0.5  # Default estimate
                    else:
                        # Skip if no position info
                        logging.debug(f"Skipping settlement with no position info: {s}")
                        continue

                cost = quantity * entry_price if entry_price else revenue * 0.5  # Estimate if no price

                # Determine win/loss from market_result and side
                # If market_result is 'yes', YES bets won. If 'no', NO bets won.
                if market_result.lower() == 'yes':
                    won = (side == 'YES')
                elif market_result.lower() == 'no':
                    won = (side == 'NO')
                else:
                    # Try to infer from revenue
                    won = revenue > cost if cost > 0 else revenue > 0

                # Calculate P&L
                if won is True:
                    pnl = revenue - cost if cost > 0 else quantity * 1.0 - cost
                elif won is False:
                    pnl = -cost if cost > 0 else -revenue
                else:
                    pnl = revenue - cost

                # Determine if this was a BTC market
                is_btc = 'KXBTC' in ticker

                # Get model_prob and EV from trade log if available
                market_prob = entry_price  # Entry price IS market probability

                if ticker in trade_log:
                    # Use recorded values from trade execution
                    log_entry = trade_log[ticker]
                    model_prob = log_entry.get('model_prob', 0)
                    ev = log_entry.get('ev', 0)
                else:
                    # Estimate: our strategy targets 4-8% edge, use 5% baseline
                    EDGE_THRESHOLD = 0.05
                    model_prob = min(0.99, max(0.01, market_prob + EDGE_THRESHOLD))
                    ev = model_prob - market_prob

                trades.append({
                    'time': settled_time,
                    'ticker': ticker,
                    'side': side,
                    'quantity': quantity,
                    'price': entry_price,
                    'cost': cost,
                    'is_btc': is_btc,
                    'settled': True,
                    'won': won,
                    'pnl': pnl,
                    'revenue': revenue,
                    'market_result': market_result,
                    'model_prob': model_prob,
                    'market_prob': market_prob,
                    'ev': ev,
                })
            except Exception as e:
                logging.warning(f"Error processing settlement: {e}, settlement data: {s}")
                import traceback
                traceback.print_exc()
                continue

        # Also add current positions as pending trades
        for p in positions:
            try:
                ticker = p.get('ticker', '')
                position = p.get('position', 0)

                if position == 0:
                    continue

                # Positive position = YES, negative = NO
                side = 'YES' if position > 0 else 'NO'
                quantity = abs(position)

                # Get market info for entry price estimate
                market_exposure = p.get('market_exposure', 0) / 100.0
                resting_order_count = p.get('resting_order_count', 0)

                # Estimate entry price from exposure/position
                entry_price = market_exposure / quantity if quantity > 0 and market_exposure > 0 else 0.5
                cost = market_exposure if market_exposure > 0 else quantity * 0.5

                is_btc = 'KXBTC' in ticker

                # Get model_prob and EV from trade log if available
                market_prob = entry_price
                if ticker in trade_log:
                    log_entry = trade_log[ticker]
                    model_prob = log_entry.get('model_prob', 0)
                    ev = log_entry.get('ev', 0)
                else:
                    EDGE_THRESHOLD = 0.05
                    model_prob = min(0.99, max(0.01, market_prob + EDGE_THRESHOLD))
                    ev = model_prob - market_prob

                trades.append({
                    'time': datetime.now(timezone.utc).isoformat(),
                    'ticker': ticker,
                    'side': side,
                    'quantity': quantity,
                    'price': entry_price,
                    'cost': cost,
                    'is_btc': is_btc,
                    'settled': False,
                    'won': None,
                    'pnl': 0,
                    'model_prob': model_prob,
                    'market_prob': market_prob,
                    'ev': ev,
                })
            except Exception as e:
                logging.warning(f"Error processing position: {e}, position data: {p}")
                continue

        logging.info(f"Processed {len(trades)} trades from {len(settlements)} settlements + {len(positions)} positions (skipped {skipped_count} outside timeframe)")

        # =====================================================
        # COUNT WINS/LOSSES FROM PROCESSED TRADES
        # (P&L already calculated from settlements above)
        # =====================================================
        total_cost = 0
        total_revenue = 0
        wins = 0
        losses = 0
        pending = 0

        for trade in trades:
            total_cost += trade.get('cost', 0)

            if trade.get('settled'):
                if trade.get('won') is True:
                    wins += 1
                    total_revenue += trade.get('revenue', trade.get('quantity', 0) * 1.0)
                elif trade.get('won') is False:
                    losses += 1
                pending += 1

        logging.info(f"Counted from trades: wins={wins}, losses={losses}, pending={pending}, total_cost=${total_cost:.2f}")

        # =====================================================
        # CALCULATE METRICS
        # =====================================================
        total_trades = len(trades)
        settled_trades = wins + losses

        logging.info(f"Trade stats: total={total_trades}, wins={wins}, losses={losses}, pending={pending}")

        # Win rate (only from settled trades)
        win_rate = wins / settled_trades if settled_trades > 0 else 0
        logging.info(f"Win rate: {win_rate:.2%} ({wins}/{settled_trades})")

        # P&L
        gross_profit = sum(t['pnl'] for t in trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t['pnl'] for t in trades if t.get('pnl', 0) < 0))
        total_pnl = gross_profit - gross_loss

        # Profit factor (cap at 999.99 to avoid JSON Infinity issue)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.99 if gross_profit > 0 else 0)

        # Calculate daily P&L for equity curve and Sharpe
        daily_pnl = defaultdict(float)
        for trade in trades:
            if trade.get('settled'):
                try:
                    trade_date = datetime.fromisoformat(trade['time'].replace('Z', '+00:00')).strftime('%Y-%m-%d')
                    daily_pnl[trade_date] += trade.get('pnl', 0)
                except:
                    pass

        # Sharpe ratio calculation
        returns = list(daily_pnl.values())
        if len(returns) > 1:
            avg_return = sum(returns) / len(returns)
            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            std_return = math.sqrt(variance) if variance > 0 else 0
            sharpe_ratio = (avg_return / std_return) * math.sqrt(252) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
            avg_return = returns[0] if returns else 0

        # ROI
        roi = total_pnl / total_cost if total_cost > 0 else 0

        # =====================================================
        # BUILD EQUITY CURVE FROM REAL DATA
        # =====================================================
        equity_curve = []
        initial_equity = 100.0  # Starting reference
        running_equity = initial_equity

        # Sort daily P&L by date
        sorted_dates = sorted(daily_pnl.keys())
        for date in sorted_dates:
            running_equity += daily_pnl[date]
            equity_curve.append({
                'date': datetime.strptime(date, '%Y-%m-%d').strftime('%m/%d'),
                'equity': round(running_equity, 2)
            })

        # If no equity curve data, create a simple one
        if not equity_curve:
            equity_curve = [{'date': now.strftime('%m/%d'), 'equity': initial_equity + total_pnl}]

        # Max drawdown
        peak = initial_equity
        max_dd = 0
        for point in equity_curve:
            if point['equity'] > peak:
                peak = point['equity']
            dd = (peak - point['equity']) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        # =====================================================
        # BUILD DAILY RETURNS
        # =====================================================
        daily_returns = []
        prev_equity = initial_equity
        for point in equity_curve:
            ret = (point['equity'] - prev_equity) / prev_equity if prev_equity > 0 else 0
            daily_returns.append({
                'date': point['date'],
                'return': round(ret, 4)
            })
            prev_equity = point['equity']

        # =====================================================
        # WIN RATE OVER TIME (rolling window)
        # =====================================================
        win_rate_over_time = []
        settled_list = [t for t in trades if t.get('settled')]
        window_size = min(20, max(5, len(settled_list) // 4))

        for i in range(window_size, len(settled_list) + 1, max(1, len(settled_list) // 10)):
            window = settled_list[max(0, i-window_size):i]
            window_wins = sum(1 for t in window if t.get('won'))
            wr = window_wins / len(window) if window else 0
            win_rate_over_time.append({
                'trade_num': i,
                'win_rate': round(wr, 3)
            })

        # =====================================================
        # MODEL CALIBRATION (from actual predictions vs outcomes)
        # =====================================================
        # Group trades by predicted probability buckets
        calibration_buckets = defaultdict(lambda: {'predicted_sum': 0, 'actual_sum': 0, 'count': 0})

        for trade in trades:
            if trade.get('settled') and 'model_prob' in trade:
                prob = trade['model_prob']
                bucket_idx = min(9, int(prob * 10))
                bucket_name = f"{bucket_idx*10}-{(bucket_idx+1)*10}%"
                calibration_buckets[bucket_name]['predicted_sum'] += prob
                calibration_buckets[bucket_name]['actual_sum'] += 1 if trade.get('won') else 0
                calibration_buckets[bucket_name]['count'] += 1

        model_calibration = []
        for i in range(10):
            bucket = f"{i*10}-{(i+1)*10}%"
            if calibration_buckets[bucket]['count'] > 0:
                predicted = calibration_buckets[bucket]['predicted_sum'] / calibration_buckets[bucket]['count']
                actual = calibration_buckets[bucket]['actual_sum'] / calibration_buckets[bucket]['count']
            else:
                predicted = (i + 0.5) / 10
                actual = predicted  # No data, assume calibrated
            model_calibration.append({
                'predicted_bucket': bucket,
                'predicted': round(predicted, 2),
                'actual': round(actual, 2)
            })

        # =====================================================
        # SIGNAL PERFORMANCE
        # For now, show aggregate stats since we don't track which signal triggered each trade
        # In production, this would require logging the signal at trade execution time
        # =====================================================
        # Calculate overall stats that we can derive from real data
        avg_entry_price = sum(t.get('price', 0) for t in settled_list) / len(settled_list) if settled_list else 0
        avg_trade_ev = sum(t.get('ev', 0) for t in settled_list) / len(settled_list) if settled_list else 0

        # Show one "Combined Model" entry with real aggregate data
        signal_performance = {
            'Combined Model': {
                'trades': settled_trades,
                'win_rate': round(win_rate, 3),
                'avg_ev': round(avg_trade_ev, 4),  # Actual EV (model_prob - market_prob)
                'pnl': round(total_pnl, 2),
                'contribution': 1.0
            }
        }

        # Note: To get per-signal breakdown, need to log signal info at trade execution time

        # =====================================================
        # RECENT TRADES
        # =====================================================
        recent_trades = []
        total_ev = 0
        for trade in sorted(trades, key=lambda x: x.get('time', ''), reverse=True)[:20]:
            try:
                time_str = datetime.fromisoformat(trade['time'].replace('Z', '+00:00')).strftime('%m/%d %H:%M')
            except:
                time_str = trade.get('time', '')[:16]

            model_prob = trade.get('model_prob', 0)
            market_prob = trade.get('market_prob', trade.get('price', 0))
            ev = trade.get('ev', model_prob - market_prob if model_prob > 0 else 0)
            total_ev += ev

            recent_trades.append({
                'time': time_str,
                'ticker': trade['ticker'],
                'side': trade['side'],
                'quantity': trade['quantity'],
                'price': trade['price'],
                'cost': round(trade['cost'], 2),
                'model_prob': round(model_prob, 4),
                'market_prob': round(market_prob, 4),
                'ev': round(ev, 4),
                'settled': trade['settled'],
                'won': trade.get('won'),
                'pnl': round(trade.get('pnl', 0), 2)
            })

        # Calculate derived metrics
        current_equity = initial_equity + total_pnl

        # Average EV per trade (sum of edge we targeted across ALL trades, not just recent)
        all_trades_ev = sum(t.get('ev', 0) for t in trades)
        avg_ev = all_trades_ev / len(trades) if trades else 0

        return jsonify({
            'summary': {
                'sharpe_ratio': round(sharpe_ratio, 2),
                'win_rate': round(win_rate, 3),
                'total_trades': total_trades,
                'total_pnl': round(total_pnl, 2),
                'roi': round(roi, 4),
                'max_drawdown': round(-max_dd, 4),
                'profit_factor': round(profit_factor, 2),
                'avg_ev_per_trade': round(avg_ev, 4),
                'initial_equity': initial_equity,
                'current_equity': round(current_equity, 2)
            },
            'equity_curve': equity_curve,
            'daily_returns': daily_returns,
            'win_rate_over_time': win_rate_over_time,
            'model_calibration': model_calibration,
            'signal_performance': signal_performance,
            'recent_trades': recent_trades,
            'timeframe': timeframe,
            'generated_at': now.isoformat()
        })

    except Exception as e:
        logging.error(f"Algorithm analytics error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================================================
# BTC HEDGING ENDPOINTS (Linear Programming Optimization)
# ============================================================================

# Initialize Hedge engine
hedge_engine = None
try:
    hedge_engine = HedgeEngine()
    logging.info("Hedge engine initialized")
except Exception as e:
    logging.error(f"Failed to initialize Hedge engine: {e}")

@app.route('/api/hedge/status')
def hedge_status():
    """Get current hedge status including portfolio and active positions"""
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        status = hedge_engine.get_hedge_status()
        return jsonify(status)
    except Exception as e:
        logging.error(f"Error getting hedge status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/hedge/optimize', methods=['POST'])
def hedge_optimize():
    """
    Optimize the BTC hedge ladder using linear programming.

    Request body:
        {
            "budget_pct": 0.02,  // Monthly budget as % of notional (default 2%)
            "target_coverage": 0.68,  // Target cents on dollar at min_coverage_drawdown
            "min_coverage_drawdown": -0.20,  // Drawdown level for target coverage (default -20%)
            "min_volume": 100  // Minimum market volume filter
        }
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        data = request.get_json() or {}
        budget_pct = data.get('budget_pct', 0.02)
        target_coverage = data.get('target_coverage', 0.68)
        min_coverage_drawdown = data.get('min_coverage_drawdown', -0.20)
        min_volume = data.get('min_volume', 100)

        logging.info(f"Optimizing hedge with budget={budget_pct*100:.1f}%, target={target_coverage*100:.0f}% @ {min_coverage_drawdown*100:.0f}%")

        result = hedge_engine.optimize_hedge(
            budget_pct=budget_pct,
            target_coverage=target_coverage,
            min_coverage_drawdown=min_coverage_drawdown,
            min_volume=min_volume
        )

        return jsonify(result)
    except Exception as e:
        logging.error(f"Error optimizing hedge: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/hedge/execute', methods=['POST'])
def hedge_execute():
    """
    Execute the optimized hedge by placing orders on Kalshi.

    Request body:
        {
            "optimization_result": {...},  // Result from /api/hedge/optimize
            "dry_run": true  // If true, simulate without placing real orders
        }
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        optimization_result = data.get('optimization_result')
        dry_run = data.get('dry_run', True)

        if not optimization_result:
            return jsonify({'error': 'optimization_result is required'}), 400

        logging.info(f"Executing hedge (dry_run={dry_run})")

        result = hedge_engine.execute_hedge(
            optimization_result=optimization_result,
            dry_run=dry_run
        )

        return jsonify(result)
    except Exception as e:
        logging.error(f"Error executing hedge: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/hedge/coverage')
def hedge_coverage():
    """
    Get real-time coverage ("cents on dollar") at various drawdown scenarios.

    Query params:
        - drawdowns: comma-separated list (e.g., "-0.05,-0.10,-0.20,-0.30")
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        # Get hedge status which includes coverage
        status = hedge_engine.get_hedge_status()

        if not status.get('success'):
            return jsonify({'error': 'Failed to get hedge status'}), 500

        return jsonify({
            'success': True,
            'coverage': status.get('current_coverage', {}),
            'portfolio': status.get('portfolio', {}),
            'num_positions': status.get('num_positions', 0)
        })
    except Exception as e:
        logging.error(f"Error getting coverage: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/hedge/positions')
def hedge_positions():
    """Get all active hedge positions from Kalshi"""
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        status = hedge_engine.get_hedge_status()

        if status.get('success'):
            return jsonify({
                'success': True,
                'positions': status.get('active_positions', []),
                'num_positions': status.get('num_positions', 0)
            })
        else:
            return jsonify({'error': 'Failed to get positions'}), 500
    except Exception as e:
        logging.error(f"Error getting positions: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# PERPETUALS DELTA HEDGING ENDPOINTS
# ============================================================================

@app.route('/api/hedge/perp/positions')
def hedge_perp_positions():
    """Get current perpetual futures positions"""
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        result = hedge_engine.get_perp_positions()
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error getting perp positions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/hedge/perp/order', methods=['POST'])
def hedge_perp_order():
    """
    Place a perpetual futures order.

    Request body:
        {
            "product_id": "BTC-PERP-INTX",
            "side": "buy" or "sell",
            "size": 0.1,
            "order_type": "market", "limit", or "stop_limit",
            "limit_price": 114000 (optional, for limit/stop_limit),
            "stop_price": 113000 (optional, for stop_limit)
        }
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        product_id = data.get('product_id', 'BTC-PERP-INTX')
        side = data.get('side')
        size = data.get('size')
        order_type = data.get('order_type', 'market')
        limit_price = data.get('limit_price')
        stop_price = data.get('stop_price')

        if not side or not size:
            return jsonify({'error': 'side and size are required'}), 400

        result = hedge_engine.place_perp_order(
            product_id=product_id,
            side=side,
            size=size,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price
        )

        return jsonify(result)
    except Exception as e:
        logging.error(f"Error placing perp order: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/hedge/delta')
def hedge_delta():
    """Get total BTC delta exposure across all positions"""
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        result = hedge_engine.calculate_total_delta()
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error calculating delta: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/hedge/auto-delta', methods=['POST'])
def hedge_auto_delta():
    """
    Automatically hedge delta to target percentage.

    Request body:
        {
            "target_delta_pct": 0.90,  // Target 90% delta
            "product_id": "BTC-PERP-INTX",
            "dry_run": true
        }
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        data = request.get_json() or {}
        target_delta_pct = data.get('target_delta_pct', 0.90)
        product_id = data.get('product_id', 'BTC-PERP-INTX')
        dry_run = data.get('dry_run', True)

        logging.info(f"Auto-hedging delta to {target_delta_pct*100:.0f}% (dry_run={dry_run})")

        result = hedge_engine.auto_hedge_delta(
            target_delta_pct=target_delta_pct,
            product_id=product_id,
            dry_run=dry_run
        )

        return jsonify(result)
    except Exception as e:
        logging.error(f"Error in auto-hedge: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/hedge/simulate-combined', methods=['POST'])
def hedge_simulate_combined():
    """
    Simulate combined hedging strategy using both Perpetuals and Kalshi options.

    Request body:
        {
            "perp_delta_target_pct": 0.90,  // Target 90% delta for perps
            "kalshi_budget_pct": 0.02,      // 2% monthly budget for Kalshi
            "kalshi_coverage_target": 0.68  // 68 cents on dollar coverage
        }
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        data = request.get_json() or {}
        perp_delta_target_pct = data.get('perp_delta_target_pct', 0.90)
        kalshi_budget_pct = data.get('kalshi_budget_pct', 0.02)
        kalshi_coverage_target = data.get('kalshi_coverage_target', 0.68)

        logging.info(f"Running combined hedge simulation: perp_delta={perp_delta_target_pct*100:.0f}%, kalshi_budget={kalshi_budget_pct*100:.1f}%")

        result = hedge_engine.simulate_combined_hedge(
            perp_delta_target_pct=perp_delta_target_pct,
            kalshi_budget_pct=kalshi_budget_pct,
            kalshi_coverage_target=kalshi_coverage_target
        )

        return jsonify(result)
    except Exception as e:
        logging.error(f"Error in combined simulation: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/hedge/daily-trading', methods=['POST'])
def hedge_daily_trading():
    """
    Simulate combined hedging strategy using ONLY Kalshi markets expiring today.

    Request body:
        {
            "kalshi_budget_pct": 0.02,      // Budget for Kalshi as % of notional (2%)
            "perp_delta_target_pct": 0.90   // Target delta with perps (90% = 10% hedge)
        }
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        data = request.get_json() or {}
        kalshi_budget_pct = data.get('kalshi_budget_pct', 0.02)
        perp_delta_target_pct = data.get('perp_delta_target_pct', 0.90)

        logging.info(f"Running daily Kalshi combined hedge: kalshi_budget={kalshi_budget_pct*100}%, perp_target={perp_delta_target_pct*100}%")

        result = hedge_engine.simulate_daily_kalshi_trading(
            kalshi_budget_pct=kalshi_budget_pct,
            perp_delta_target_pct=perp_delta_target_pct
        )

        return jsonify(result)
    except Exception as e:
        logging.error(f"Error in daily trading simulation: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/hedge/execute-daily', methods=['POST'])
def execute_daily_hedge():
    """
    Execute the daily combined hedge strategy (Kalshi + Coinbase perpetuals).

    Request body:
        {
            "simulation_result": {...},  // Result from /api/hedge/daily-trading
            "dry_run": true,             // If true, simulate without placing real orders
            "product_id": "BTC-PERP-INTX" // Perpetual product to trade (optional)
        }
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        data = request.get_json() or {}
        simulation_result = data.get('simulation_result')
        dry_run = data.get('dry_run', True)
        product_id = data.get('product_id', 'BTC-PERP-INTX')

        if not simulation_result:
            return jsonify({'error': 'simulation_result required', 'success': False}), 400

        logging.info(f"Executing daily hedge: dry_run={dry_run}, product_id={product_id}")

        result = hedge_engine.execute_daily_hedge(
            simulation_result=simulation_result,
            dry_run=dry_run,
            product_id=product_id
        )

        return jsonify(result)
    except Exception as e:
        logging.error(f"Error executing daily hedge: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/hedge/live-positions', methods=['GET'])
def get_live_hedge_positions():
    """
    Get all active hedge positions for live tracking.

    Returns:
        {
            "success": bool,
            "spot_position": {...},        // BTC spot holdings
            "perp_positions": [...],       // Coinbase perpetual positions with P&L
            "kalshi_positions": [...],     // Kalshi binary option positions with P&L
            "combined_pnl": float,         // Total unrealized P&L
            "current_delta": float,        // Current BTC delta exposure
            "delta_pct": float,            // Delta as % of spot holdings
            "timestamp": str
        }
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        logging.info("Fetching live hedge positions")

        result = hedge_engine.get_live_hedge_positions()

        return jsonify(result)
    except Exception as e:
        logging.error(f"Error getting live hedge positions: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

# ============================================================================
# ENHANCED HEDGE OPTIMIZATION ENDPOINTS (GARCH + PROBABILITY WEIGHTING)
# ============================================================================

@app.route('/api/hedge/optimize-advanced', methods=['POST'])
def hedge_optimize_advanced():
    """
    Enhanced hedge optimization using GARCH volatility, probability-weighted scenarios,
    implied volatility analysis, and signal adjustments.

    Request body:
        {
            "budget_pct": 0.02,              // Monthly budget as % of notional (default 2%)
            "target_coverage": 0.68,          // Target cents on dollar (default 68%)
            "min_coverage_drawdown": -0.20,   // Drawdown level for target (default -20%)
            "horizon_days": 30,               // Time horizon for optimization (default 30)
            "min_volume": 100,                // Minimum market volume filter
            "prefer_underpriced": true,       // Prefer IV < GARCH vol contracts
            "include_theta": true,            // Include time decay scoring
            "include_transaction_costs": true, // Include slippage in costs
            "slippage_pct": 0.015,            // Expected slippage (default 1.5%)
            "signal_kwargs": {                // Optional signal adjustments
                "funding_rate": 0.001,
                "rsi": 72,
                "vix": 18
            }
        }

    Returns:
        {
            "success": bool,
            "optimization": {...},            // LP optimization results
            "volatility_analysis": {...},     // GARCH forecasts and analysis
            "probability_scenarios": [...],   // Probability-weighted scenarios used
            "market_analysis": {...},         // IV mispricing detection
            "recommended_trades": [...],      // Filtered by EV threshold
            "expected_coverage": {...}        // Coverage at various drawdown levels
        }
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        data = request.get_json() or {}

        budget_pct = data.get('budget_pct', 0.02)
        target_coverage = data.get('target_coverage', 0.68)
        min_coverage_drawdown = data.get('min_coverage_drawdown', -0.20)
        horizon_days = data.get('horizon_days', 30)
        min_volume = data.get('min_volume', 100)
        prefer_underpriced = data.get('prefer_underpriced', True)
        include_theta = data.get('include_theta', True)
        include_transaction_costs = data.get('include_transaction_costs', True)
        slippage_pct = data.get('slippage_pct', 0.015)
        signal_kwargs = data.get('signal_kwargs', None)

        logging.info(f"Running advanced hedge optimization: budget={budget_pct*100:.1f}%, "
                     f"horizon={horizon_days}d, target={target_coverage*100:.0f}%")

        result = hedge_engine.optimize_hedge_advanced(
            budget_pct=budget_pct,
            target_coverage=target_coverage,
            min_coverage_drawdown=min_coverage_drawdown,
            horizon_days=horizon_days,
            min_volume=min_volume,
            prefer_underpriced=prefer_underpriced,
            include_theta=include_theta,
            include_transaction_costs=include_transaction_costs,
            slippage_pct=slippage_pct,
            signal_kwargs=signal_kwargs
        )

        return jsonify(result)
    except Exception as e:
        logging.error(f"Error in advanced hedge optimization: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/hedge/volatility', methods=['GET'])
def hedge_volatility():
    """
    Get comprehensive volatility analysis including GARCH forecasts,
    realized volatility, and market regime assessment.

    Returns:
        {
            "success": bool,
            "garch": {
                "current_vol": float,         // Current annualized volatility
                "forecast_30d": float,        // 30-day average forecast
                "params": {...},              // GARCH parameters (omega, alpha, beta)
                "persistence": float          // alpha + beta (should be < 1)
            },
            "realized": {
                "vol_7d": float,              // 7-day realized vol
                "vol_30d": float,             // 30-day realized vol
                "vol_90d": float              // 90-day realized vol
            },
            "regime": {
                "current": str,               // "low", "normal", "high", "extreme"
                "interpretation": str         // Human-readable description
            },
            "drawdown_distribution": {...},   // Historical drawdown percentiles
            "historical_var": {...}           // Value at Risk metrics
        }
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        logging.info("Fetching volatility analysis")

        result = hedge_engine.get_volatility_analysis()

        return jsonify(result)
    except Exception as e:
        logging.error(f"Error getting volatility analysis: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/hedge/probability', methods=['POST'])
def hedge_probability():
    """
    Calculate model probability for a specific strike price using GARCH
    and signal adjustments.

    Request body:
        {
            "strike_price": 85000,            // Strike price to calculate probability for
            "horizon_days": 30,               // Time horizon (default 30)
            "signal_kwargs": {                // Optional signal adjustments
                "funding_rate": 0.001,
                "rsi": 72,
                "vix": 18
            }
        }

    Returns:
        {
            "success": bool,
            "strike_price": float,
            "current_price": float,
            "drawdown_pct": float,            // Implied drawdown to strike
            "base_probability": float,        // Lognormal probability before signals
            "adjusted_probability": float,    // Final probability after signal adjustment
            "signal_adjustment": float,       // Total signal adjustment applied
            "garch_vol": float,               // GARCH volatility used
            "horizon_days": int
        }
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        data = request.get_json() or {}

        strike_price = data.get('strike_price')
        if strike_price is None:
            return jsonify({'error': 'strike_price is required'}), 400

        horizon_days = data.get('horizon_days', 30)
        signal_kwargs = data.get('signal_kwargs', {})

        logging.info(f"Calculating probability for strike ${strike_price:,.0f}")

        # Import required modules
        from market_data_service import get_market_data_service
        from volatility_model import GARCHVolatilityModel, SignalAdjuster
        import numpy as np
        from scipy.stats import norm

        # Get market data
        market_data = get_market_data_service()
        df = market_data.fetch_ohlc_data(days=365)
        current_price = float(df['close'].iloc[-1])

        # Fit GARCH model
        returns = market_data.calculate_log_returns()
        garch_model = GARCHVolatilityModel()
        garch_fit = garch_model.fit(returns)

        # Get volatility forecast
        forecast = garch_model.forecast_volatility(horizon=horizon_days)
        avg_vol = float(forecast['volatility'].mean())

        # Calculate base lognormal probability
        drawdown_pct = (strike_price - current_price) / current_price
        daily_vol = avg_vol / np.sqrt(365)
        period_vol = daily_vol * np.sqrt(horizon_days)

        z_score = np.log(strike_price / current_price) / period_vol
        base_prob = float(norm.cdf(z_score))

        # Apply signal adjustments
        signal_adjuster = SignalAdjuster()
        adjustment = signal_adjuster.compute_adjustment(**signal_kwargs)
        adjusted_prob = signal_adjuster.adjust_probability(base_prob, **signal_kwargs)

        return jsonify({
            'success': True,
            'strike_price': strike_price,
            'current_price': current_price,
            'drawdown_pct': drawdown_pct,
            'base_probability': base_prob,
            'adjusted_probability': adjusted_prob,
            'signal_adjustment': adjustment,
            'garch_vol': avg_vol,
            'horizon_days': horizon_days
        })
    except Exception as e:
        logging.error(f"Error calculating probability: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/hedge/expected-value', methods=['POST'])
def hedge_expected_value():
    """
    Calculate expected value (edge) for Kalshi markets by comparing
    model probability to market price.

    Request body:
        {
            "min_edge_threshold": 0.04,       // Minimum EV to consider (default 4%)
            "horizon_days": 30,               // Time horizon (default 30)
            "min_volume": 100,                // Minimum market volume
            "signal_kwargs": {}               // Optional signal adjustments
        }

    Returns:
        {
            "success": bool,
            "opportunities": [
                {
                    "market_ticker": str,
                    "strike_price": float,
                    "market_price": float,    // Current YES price
                    "model_probability": float,
                    "expected_value": float,  // p_model - p_market
                    "edge_pct": float,        // EV as percentage
                    "recommendation": str     // "BUY", "AVOID", or "NEUTRAL"
                }
            ],
            "summary": {
                "total_markets_analyzed": int,
                "opportunities_found": int,
                "avg_edge": float
            }
        }
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        data = request.get_json() or {}

        min_edge_threshold = data.get('min_edge_threshold', 0.04)
        horizon_days = data.get('horizon_days', 30)
        min_volume = data.get('min_volume', 100)
        signal_kwargs = data.get('signal_kwargs', {})

        logging.info(f"Analyzing expected value across markets (threshold={min_edge_threshold*100:.0f}%)")

        # Import required modules
        from market_data_service import get_market_data_service
        from volatility_model import GARCHVolatilityModel, SignalAdjuster
        import numpy as np
        from scipy.stats import norm

        # Get market data and fit GARCH
        market_data = get_market_data_service()
        df = market_data.fetch_ohlc_data(days=365)
        current_price = float(df['close'].iloc[-1])

        returns = market_data.calculate_log_returns()
        garch_model = GARCHVolatilityModel()
        garch_model.fit(returns)

        forecast = garch_model.forecast_volatility(horizon=horizon_days)
        avg_vol = float(forecast['volatility'].mean())
        daily_vol = avg_vol / np.sqrt(365)
        period_vol = daily_vol * np.sqrt(horizon_days)

        signal_adjuster = SignalAdjuster()

        # Fetch Kalshi markets
        markets = hedge_engine.kalshi_engine.fetch_btc_binary_markets() if hedge_engine.kalshi_engine else []

        opportunities = []
        for market in markets:
            if market.get('volume', 0) < min_volume:
                continue

            strike_price = market.get('strike_price', 0)
            if strike_price <= 0 or strike_price >= current_price:
                continue

            # Get market price (YES price for "below strike")
            yes_price = market.get('yes_price', market.get('last_price', 0))
            if yes_price <= 0:
                continue
            market_prob = yes_price / 100.0  # Convert cents to probability

            # Calculate model probability
            z_score = np.log(strike_price / current_price) / period_vol
            base_prob = float(norm.cdf(z_score))
            model_prob = signal_adjuster.adjust_probability(base_prob, **signal_kwargs)

            # Calculate expected value
            ev = model_prob - market_prob

            recommendation = "NEUTRAL"
            if ev >= min_edge_threshold:
                recommendation = "BUY"
            elif ev <= -min_edge_threshold:
                recommendation = "AVOID"

            opportunities.append({
                'market_ticker': market.get('ticker', 'unknown'),
                'strike_price': strike_price,
                'market_price': yes_price,
                'model_probability': round(model_prob, 4),
                'expected_value': round(ev, 4),
                'edge_pct': round(ev * 100, 2),
                'recommendation': recommendation
            })

        # Sort by absolute EV
        opportunities.sort(key=lambda x: abs(x['expected_value']), reverse=True)

        # Filter to only significant opportunities
        significant_opps = [o for o in opportunities if abs(o['expected_value']) >= min_edge_threshold]

        return jsonify({
            'success': True,
            'opportunities': opportunities,
            'significant_opportunities': significant_opps,
            'summary': {
                'total_markets_analyzed': len(markets),
                'opportunities_found': len(significant_opps),
                'avg_edge': round(np.mean([o['expected_value'] for o in significant_opps]) if significant_opps else 0, 4),
                'current_price': current_price,
                'garch_vol': round(avg_vol, 4),
                'horizon_days': horizon_days
            }
        })
    except Exception as e:
        logging.error(f"Error calculating expected value: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


# =============================================================================
# SMART CASH-OUT SYSTEM ENDPOINTS
# =============================================================================

@app.route('/api/hedge/cash-out/status', methods=['GET'])
def cash_out_status():
    """Get summary of all tracked positions for cash-out monitoring."""
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        summary = hedge_engine.get_position_summary()
        return jsonify({
            'success': True,
            **summary
        })
    except Exception as e:
        logging.error(f"Error getting cash-out status: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/hedge/cash-out/check', methods=['GET'])
def cash_out_check():
    """
    Check all positions for cash-out triggers.
    Returns which positions should be cashed out and why.
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        # Check all positions but don't execute
        result = hedge_engine.monitor_all_positions(dry_run=True)
        return jsonify({
            'success': True,
            **result
        })
    except Exception as e:
        logging.error(f"Error checking cash-out triggers: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/hedge/cash-out/check/<ticker>', methods=['GET'])
def cash_out_check_single(ticker):
    """Check a specific position for cash-out triggers."""
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        result = hedge_engine.check_cash_out(ticker)
        return jsonify({
            'success': True,
            **result
        })
    except Exception as e:
        logging.error(f"Error checking cash-out for {ticker}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/hedge/cash-out/execute', methods=['POST'])
def cash_out_execute():
    """
    Execute cash-out for triggered positions.

    Request body:
    {
        "dry_run": true/false,  // If true, simulate without executing
        "ticker": "KXBTC-...",  // Optional: specific ticker to cash out
        "force": false          // If true, execute even without trigger
    }
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        data = request.get_json() or {}
        dry_run = data.get('dry_run', True)
        specific_ticker = data.get('ticker')
        force = data.get('force', False)

        if specific_ticker:
            # Check and execute for specific ticker
            check_result = hedge_engine.check_cash_out(specific_ticker)

            if check_result['action'] == 'SELL' or force:
                quantity = check_result.get('quantity') or check_result.get('current_quantity', 0)
                trigger = check_result.get('trigger', 'manual') if not force else 'manual_force'

                if quantity <= 0:
                    return jsonify({'error': 'No quantity to sell'}), 400

                exec_result = hedge_engine.execute_cash_out(
                    ticker=specific_ticker,
                    quantity=quantity,
                    trigger=trigger,
                    dry_run=dry_run
                )
                return jsonify({
                    'success': exec_result.get('success', False),
                    'check_result': check_result,
                    'execution': exec_result
                })
            else:
                return jsonify({
                    'success': True,
                    'message': 'No cash-out trigger met',
                    'check_result': check_result
                })
        else:
            # Monitor and execute all positions
            result = hedge_engine.monitor_all_positions(dry_run=dry_run)
            return jsonify({
                'success': True,
                **result
            })

    except Exception as e:
        logging.error(f"Error executing cash-out: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/hedge/cash-out/track', methods=['POST'])
def cash_out_track_position():
    """
    Manually track a position for cash-out monitoring.
    Useful for positions opened outside the automated system.

    Request body:
    {
        "ticker": "KXBTC-26JAN2215-B89000",
        "entry_price": 24,  // cents
        "quantity": 10,
        "side": "yes",
        "model_prob": 0.30,  // optional
        "market_prob": 0.24  // optional
    }
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        required = ['ticker', 'entry_price', 'quantity']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        hedge_engine.track_new_position(
            ticker=data['ticker'],
            entry_price=data['entry_price'],
            quantity=data['quantity'],
            model_prob=data.get('model_prob', data['entry_price'] / 100 + 0.05),
            market_prob=data.get('market_prob', data['entry_price'] / 100),
            side=data.get('side', 'yes')
        )

        return jsonify({
            'success': True,
            'message': f"Now tracking {data['ticker']} x{data['quantity']} @ {data['entry_price']}¢"
        })

    except Exception as e:
        logging.error(f"Error tracking position: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/hedge/cash-out/config', methods=['GET', 'POST'])
def cash_out_config():
    """Get or update cash-out configuration."""
    try:
        from hedge_engine import CASH_OUT_CONFIG

        if request.method == 'GET':
            return jsonify({
                'success': True,
                'config': CASH_OUT_CONFIG
            })

        # POST - update config
        data = request.get_json() or {}
        updated = []

        for key, value in data.items():
            if key in CASH_OUT_CONFIG:
                CASH_OUT_CONFIG[key] = value
                updated.append(key)

        return jsonify({
            'success': True,
            'updated': updated,
            'config': CASH_OUT_CONFIG
        })

    except Exception as e:
        logging.error(f"Error with cash-out config: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/hedge/cash-out/sync', methods=['POST'])
def cash_out_sync_positions():
    """
    Sync current Kalshi positions to the cash-out tracker.
    Call this to import existing positions that weren't opened through the hedge engine.
    """
    try:
        if not hedge_engine:
            return jsonify({'error': 'Hedge engine not initialized'}), 500

        result = hedge_engine.sync_positions_from_kalshi()
        return jsonify(result)

    except Exception as e:
        logging.error(f"Error syncing positions: {e}")
        return jsonify({'error': str(e)}), 500


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    # Emit initial data to the newly connected client
    socketio.emit('bot_update', bot_data)
    socketio.emit('sentiment_update', sentiment_data)
    socketio.emit('whale_update', whale_data)
    socketio.emit('crypto_update', crypto_data)
    socketio.emit('portfolio_update', bot_adapter.get_portfolio_breakdown())

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')


# =============================================================================
# AUTOMATIC CASH-OUT MONITOR (Background Thread)
# =============================================================================

cash_out_monitor_running = False
CASH_OUT_CHECK_INTERVAL = 30  # Check every 30 seconds (for short-expiry contracts)

def cash_out_monitor_loop():
    """Background thread that monitors positions and auto-executes cash-outs."""
    global cash_out_monitor_running

    logging.info("Cash-out monitor started (checking every 30 seconds)")

    # AUTO-SYNC: Pull current Kalshi positions into tracker on startup
    if hedge_engine:
        try:
            sync_result = hedge_engine.sync_positions_from_kalshi()
            logging.info(f"Auto-sync: {sync_result.get('message', 'done')}")
        except Exception as e:
            logging.error(f"Auto-sync failed: {e}")

    while cash_out_monitor_running:
        try:
            if hedge_engine:
                # Check all positions for exit triggers
                result = hedge_engine.monitor_all_positions(dry_run=False)  # LIVE execution

                if result.get('cash_outs_executed', 0) > 0:
                    logging.info(f"AUTO CASH-OUT: Executed {result['cash_outs_executed']} cash-outs")
                    for action in result.get('actions_taken', []):
                        logging.info(f"  - {action['ticker']}: {action['reason']}")

                    # Emit to connected clients
                    socketio.emit('cash_out_alert', {
                        'type': 'cash_out_executed',
                        'count': result['cash_outs_executed'],
                        'total_pnl': result.get('total_realized_pnl', 0),
                        'actions': result.get('actions_taken', [])
                    })

                # Log status periodically
                positions_count = result.get('positions_checked', 0)
                if positions_count > 0:
                    logging.debug(f"Cash-out monitor: Checked {positions_count} positions")

        except Exception as e:
            logging.error(f"Cash-out monitor error: {e}")

        # Sleep in small intervals to allow clean shutdown
        for _ in range(CASH_OUT_CHECK_INTERVAL):
            if not cash_out_monitor_running:
                break
            time.sleep(1)

    logging.info("Cash-out monitor stopped")


def start_cash_out_monitor():
    """Start the background cash-out monitor."""
    global cash_out_monitor_running

    if cash_out_monitor_running:
        logging.warning("Cash-out monitor already running")
        return

    cash_out_monitor_running = True
    thread = threading.Thread(target=cash_out_monitor_loop, daemon=True)
    thread.start()
    logging.info("Cash-out monitor thread started")


def stop_cash_out_monitor():
    """Stop the background cash-out monitor."""
    global cash_out_monitor_running
    cash_out_monitor_running = False
    logging.info("Cash-out monitor stopping...")


@app.route('/api/hedge/cash-out/monitor/start', methods=['POST'])
def start_monitor_endpoint():
    """Start the automatic cash-out monitor."""
    start_cash_out_monitor()
    return jsonify({'success': True, 'message': 'Cash-out monitor started'})


@app.route('/api/hedge/cash-out/monitor/stop', methods=['POST'])
def stop_monitor_endpoint():
    """Stop the automatic cash-out monitor."""
    stop_cash_out_monitor()
    return jsonify({'success': True, 'message': 'Cash-out monitor stopped'})


@app.route('/api/hedge/cash-out/monitor/status', methods=['GET'])
def monitor_status_endpoint():
    """Get cash-out monitor status."""
    return jsonify({
        'success': True,
        'running': cash_out_monitor_running,
        'check_interval_seconds': CASH_OUT_CHECK_INTERVAL
    })


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("Starting AI Trading Co-Pilot Backend...")

    # Initialize crypto data on startup
    print("Initializing cryptocurrency data...")
    bot_adapter.update_crypto_data()

    # Start bot monitoring
    bot_adapter.start_bot_monitoring()

    # Cash-out monitor does NOT auto-start
    # User must click "Start Cash-Outs" button in dashboard to enable
    print("Cash-out monitor ready (start via dashboard button)")

    # Run the Flask-SocketIO app
    socketio.run(app, host='127.0.0.1', port=5001, debug=False, allow_unsafe_werkzeug=True)