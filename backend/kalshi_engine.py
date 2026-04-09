#!/usr/bin/env python3
"""
Kalshi Prediction Market Trading Engine
CFTC-regulated prediction market for US residents
"""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KalshiEngine:
    """
    Engine for trading on Kalshi prediction markets
    US-legal and CFTC-regulated
    """

    def __init__(self, api_key_id: str = None, private_key_path: str = None, demo_mode: bool = False):
        """
        Initialize Kalshi client

        Args:
            api_key_id: Your Kalshi API Key ID (UUID format)
            private_key_path: Path to your private key .key file
            demo_mode: Use demo environment instead of production
        """
        # Determine demo mode first
        self.demo_mode = demo_mode or os.getenv('KALSHI_DEMO_MODE', 'false').lower() == 'true'

        # Load credentials based on mode
        if self.demo_mode:
            self.api_key_id = api_key_id or os.getenv('KALSHI_DEMO_API_KEY_ID')
            key_path = private_key_path or os.getenv('KALSHI_DEMO_PRIVATE_KEY_PATH')
            logger.info("Using Kalshi DEMO environment")
        else:
            self.api_key_id = api_key_id or os.getenv('KALSHI_PROD_API_KEY_ID')
            key_path = private_key_path or os.getenv('KALSHI_PROD_PRIVATE_KEY_PATH')
            logger.info("Using Kalshi PRODUCTION environment")

        # Make path absolute if it's relative
        if key_path and not os.path.isabs(key_path):
            # Get the directory of this file (backend/)
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            key_path = os.path.join(backend_dir, key_path)

        self.private_key_path = key_path

        # Kalshi API host
        if self.demo_mode:
            self.host = "https://demo-api.kalshi.co"
        else:
            self.host = "https://api.elections.kalshi.com"

        self.base_path = "/trade-api/v2"

        # Load private key
        self.private_key = None
        self.is_connected = False
        self.auth_token = None
        self.token_expiry = None

        if self.api_key_id and self.private_key_path:
            logger.info(f"Initializing Kalshi with API key: {self.api_key_id[:8]}...")
            logger.info(f"Private key path: {self.private_key_path}")
            try:
                self._load_private_key()
                self.login()
                logger.info(f"Kalshi initialization complete. Connected: {self.is_connected}")
            except Exception as e:
                logger.error(f"Failed to initialize Kalshi client: {e}", exc_info=True)
        else:
            logger.warning(f"Kalshi credentials not found - api_key_id: {bool(self.api_key_id)}, private_key_path: {bool(self.private_key_path)}")

    def _load_private_key(self):
        """Load the private key from file"""
        try:
            if not os.path.exists(self.private_key_path):
                logger.error(f"Private key file not found: {self.private_key_path}")
                return

            with open(self.private_key_path, 'rb') as key_file:
                self.private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                    backend=default_backend()
                )
            logger.info("Private key loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load private key: {e}")
            self.private_key = None

    def _generate_signature(self, timestamp: str, method: str, path: str) -> str:
        """
        Generate authentication signature

        Args:
            timestamp: Current time in milliseconds
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path without query parameters

        Returns:
            Base64-encoded signature
        """
        if not self.private_key:
            raise Exception("Private key not loaded")

        # Create message: timestamp + method + path
        message = f"{timestamp}{method}{path}"
        message_bytes = message.encode('utf-8')

        # Sign with RSA-PSS
        signature = self.private_key.sign(
            message_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )

        # Encode to base64
        return base64.b64encode(signature).decode('utf-8')

    def _make_authenticated_request(self, method: str, endpoint: str, data: dict = None) -> Optional[Dict]:
        """
        Make an authenticated API request

        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., '/portfolio/balance')
            data: Request payload for POST/PUT

        Returns:
            Response data
        """
        if not self.api_key_id or not self.private_key:
            logger.error("API credentials not configured")
            return None

        # Generate timestamp
        timestamp = str(int(datetime.now().timestamp() * 1000))

        # Full path for signing (without query params)
        path = f"{self.base_path}{endpoint.split('?')[0]}"

        # Generate signature
        try:
            signature = self._generate_signature(timestamp, method, path)
        except Exception as e:
            logger.error(f"Failed to generate signature: {e}")
            return None

        # Headers
        headers = {
            'KALSHI-ACCESS-KEY': self.api_key_id,
            'KALSHI-ACCESS-SIGNATURE': signature,
            'KALSHI-ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }

        # Full URL
        url = f"{self.host}{self.base_path}{endpoint}"

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    def login(self) -> bool:
        """
        Login to Kalshi (not needed with signature auth, but good for testing)

        Returns:
            Success boolean
        """
        try:
            # Test the connection by fetching balance
            balance = self.get_balance()
            if balance is not None:
                self.is_connected = True
                logger.info("Successfully connected to Kalshi")
                return True
            else:
                self.is_connected = False
                return False
        except Exception as e:
            logger.error(f"Failed to connect to Kalshi: {e}")
            self.is_connected = False
            return False

    def get_balance(self) -> Optional[Dict]:
        """
        Get account balance

        Returns:
            Balance information
        """
        result = self._make_authenticated_request('GET', '/portfolio/balance')
        if result:
            return {
                'balance': result.get('balance', 0) / 100,  # Convert cents to dollars
                'payout': result.get('payout', 0) / 100
            }
        return None

    def get_markets(self, limit: int = 20, status: str = 'open', category: str = None, min_volume: int = 0) -> List[Dict]:
        """
        Get active prediction markets

        Args:
            limit: Number of markets to return
            status: Market status (open, closed, settled)
            category: Filter by category (e.g., 'crypto', 'politics', 'sports')
            min_volume: Minimum volume to avoid resting orders (default: 0)

        Returns:
            List of market dictionaries
        """
        # If category is crypto, get markets from crypto series
        if category and category.lower() == 'crypto':
            return self._get_crypto_markets(limit=limit, status=status, min_volume=min_volume)

        # Otherwise get all markets
        params = f'limit={limit}&status={status}'
        result = self._make_authenticated_request('GET', f'/markets?{params}')

        if not result or 'markets' not in result:
            return []

        formatted_markets = []
        for market in result['markets']:
            # Filter for crypto-related markets by keywords
            title = market.get('title', '').lower()
            subtitle = market.get('subtitle', '').lower()

            # Log the market for debugging
            logger.debug(f"Market: {title}")

            crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'solana', 'sol',
                             'cardano', 'ada', 'dogecoin', 'doge', 'polygon', 'matic',
                             'avalanche', 'avax', 'chainlink', 'link', 'cryptocurrency',
                             'ripple', 'xrp', 'polkadot', 'dot', 'shiba', 'usdc', 'usdt',
                             'binance', 'coinbase', 'defi', 'nft', 'blockchain', 'btc-usd',
                             'eth-usd', 'digital currency', 'virtual currency', '$', 'price',
                             'all time high', 'below', 'above', 'hit', 'will bitcoin',
                             'will ethereum', 'will btc', 'will eth', 'cryptocurrencies']

            # Check if crypto-related
            is_crypto = any(keyword in title or keyword in subtitle for keyword in crypto_keywords)

            # If category filter is 'crypto', only include crypto markets
            if category and category.lower() == 'crypto':
                if not is_crypto:
                    continue  # Skip non-crypto markets
                else:
                    logger.info(f"Found crypto market: {title}")

            # Get bid/ask prices — handle new _dollars suffix (multiply by 100 to get cents scale)
            def _p(key_dollars, key_old):
                v = market.get(key_dollars)
                if v is not None:
                    try: return round(float(v) * 100)
                    except: pass
                return int(market.get(key_old, 0) or 0)

            yes_bid = _p('yes_bid_dollars', 'yes_bid')
            no_bid  = _p('no_bid_dollars',  'no_bid')
            yes_ask = _p('yes_ask_dollars', 'yes_ask')
            no_ask  = _p('no_ask_dollars',  'no_ask')

            # Calculate mid prices for display
            yes_price = (yes_bid + yes_ask) / 2 if yes_ask > 0 else yes_bid
            no_price = (no_bid + no_ask) / 2 if no_ask > 0 else no_bid

            # If no prices available, use complement
            if yes_price == 0 and no_price > 0:
                yes_price = 100 - no_price
            elif no_price == 0 and yes_price > 0:
                no_price = 100 - yes_price

            # Get volume and open interest — handle _fp suffix
            def _fp(key_fp, key_old):
                v = market.get(key_fp)
                if v is not None:
                    try: return float(v)
                    except: pass
                return float(market.get(key_old, 0) or 0)

            volume = _fp('volume_fp', 'volume') or _fp('volume_24h_fp', 'volume_24h')
            open_interest = _fp('open_interest_fp', 'open_interest')

            # Skip markets with very low volume to avoid resting orders (if min_volume set)
            if min_volume > 0 and volume < min_volume:
                continue

            formatted_markets.append({
                'id': market.get('ticker'),
                'question': market.get('title'),
                'subtitle': market.get('subtitle', ''),
                'category': 'Crypto' if is_crypto else market.get('category', 'Other'),
                'close_date': market.get('close_date'),
                'expiration_date': market.get('expiration_date'),
                'yes_price': yes_price,  # Keep in cents (0-99) for percentage display
                'no_price': no_price,    # Keep in cents (0-99) for percentage display
                'yes_bid': yes_bid,
                'yes_ask': yes_ask,
                'no_bid': no_bid,
                'no_ask': no_ask,
                'volume': volume,
                'liquidity': open_interest,
                'status': market.get('status', 'unknown'),
                'has_liquidity': volume > 1000 or open_interest > 100  # Flag for good liquidity
            })

        return formatted_markets

    def _get_crypto_markets(self, limit: int = 100, status: str = 'open', min_volume: int = 0) -> List[Dict]:
        """
        Get all crypto markets by fetching from crypto series

        Args:
            limit: Max markets to return
            status: Market status
            min_volume: Minimum volume filter

        Returns:
            List of crypto market dictionaries
        """
        # First get all crypto series
        result = self._make_authenticated_request('GET', '/series')
        if not result or 'series' not in result:
            logger.error("Failed to fetch series")
            return []

        # Filter for crypto series
        crypto_series = [s.get('ticker') for s in result.get('series', [])
                        if s.get('category', '').lower() == 'crypto']

        logger.info(f"Found {len(crypto_series)} crypto series")

        # Get markets from each crypto series
        all_markets = []
        for series_ticker in crypto_series:
            if len(all_markets) >= limit:
                break

            result = self._make_authenticated_request('GET', f'/markets?series_ticker={series_ticker}&status={status}&limit=100')
            if result and 'markets' in result:
                for market in result['markets']:
                    if len(all_markets) >= limit:
                        break

                    # Get bid/ask prices — handle new _dollars suffix
                    def _p2(key_dollars, key_old):
                        v = market.get(key_dollars)
                        if v is not None:
                            try: return round(float(v) * 100)
                            except: pass
                        return int(market.get(key_old, 0) or 0)

                    yes_bid = _p2('yes_bid_dollars', 'yes_bid')
                    no_bid  = _p2('no_bid_dollars',  'no_bid')
                    yes_ask = _p2('yes_ask_dollars', 'yes_ask')
                    no_ask  = _p2('no_ask_dollars',  'no_ask')

                    # Calculate mid prices
                    yes_price = (yes_bid + yes_ask) / 2 if yes_ask > 0 else yes_bid
                    no_price = (no_bid + no_ask) / 2 if no_ask > 0 else no_bid

                    # If no prices, use complement
                    if yes_price == 0 and no_price > 0:
                        yes_price = 100 - no_price
                    elif no_price == 0 and yes_price > 0:
                        no_price = 100 - yes_price

                    def _fp2(key_fp, key_old):
                        v = market.get(key_fp)
                        if v is not None:
                            try: return float(v)
                            except: pass
                        return float(market.get(key_old, 0) or 0)

                    volume = _fp2('volume_fp', 'volume') or _fp2('volume_24h_fp', 'volume_24h')
                    open_interest = _fp2('open_interest_fp', 'open_interest')

                    # Skip low volume if filter set
                    if min_volume > 0 and volume < min_volume:
                        continue

                    all_markets.append({
                        'id': market.get('ticker'),
                        'question': market.get('title'),
                        'subtitle': market.get('subtitle', ''),
                        'category': 'Crypto',
                        'close_date': market.get('close_time'),
                        'expiration_date': market.get('expiration_time'),
                        'yes_price': yes_price,
                        'no_price': no_price,
                        'yes_bid': yes_bid,
                        'yes_ask': yes_ask,
                        'no_bid': no_bid,
                        'no_ask': no_ask,
                        'volume': volume,
                        'liquidity': open_interest,
                        'status': market.get('status', 'unknown'),
                        'has_liquidity': volume > 1000 or open_interest > 100
                    })

        logger.info(f"Returning {len(all_markets)} crypto markets")
        return all_markets

    def get_market(self, ticker: str) -> Optional[Dict]:
        """
        Get market information for a specific ticker.
        Returns prices in cents (0-99) for consistency with other methods.

        Args:
            ticker: Market ticker symbol

        Returns:
            Market dictionary with prices in cents
        """
        result = self._make_authenticated_request('GET', f'/markets/{ticker}')

        if not result or 'market' not in result:
            return None

        market = result['market']

        # Get bid/ask prices (already in cents from API)
        yes_bid = market.get('yes_bid', 0)
        yes_ask = market.get('yes_ask', 0)
        no_bid = market.get('no_bid', 0)
        no_ask = market.get('no_ask', 0)

        return {
            'ticker': market.get('ticker'),
            'title': market.get('title'),
            'subtitle': market.get('subtitle'),
            'category': market.get('category'),
            'close_time': market.get('close_time'),
            'expiration_time': market.get('expiration_time'),
            'yes_bid': yes_bid,
            'yes_ask': yes_ask,
            'no_bid': no_bid,
            'no_ask': no_ask,
            'yes_price': (yes_bid + yes_ask) / 2 if yes_ask > 0 else yes_bid,
            'no_price': (no_bid + no_ask) / 2 if no_ask > 0 else no_bid,
            'last_price': market.get('last_price', 0),
            'volume': market.get('volume', 0),
            'open_interest': market.get('open_interest', 0),
            'status': market.get('status')
        }

    def get_market_details(self, ticker: str) -> Optional[Dict]:
        """
        Get detailed information about a specific market.
        NOTE: Returns prices as decimals (0-1) for backward compatibility.
        Use get_market() for cents-based prices.

        Args:
            ticker: Market ticker symbol

        Returns:
            Market details dictionary
        """
        result = self._make_authenticated_request('GET', f'/markets/{ticker}')

        if not result or 'market' not in result:
            return None

        market = result['market']
        return {
            'ticker': market.get('ticker'),
            'title': market.get('title'),
            'subtitle': market.get('subtitle'),
            'category': market.get('category'),
            'close_date': market.get('close_date'),
            'expiration_date': market.get('expiration_date'),
            'yes_price': market.get('yes_bid', 0) / 100,
            'no_price': market.get('no_bid', 0) / 100,
            'last_price': market.get('last_price', 0) / 100,
            'volume': market.get('volume', 0),
            'open_interest': market.get('open_interest', 0),
            'status': market.get('status')
        }

    def get_positions(self) -> List[Dict]:
        """
        Get current open positions

        Returns:
            List of position dictionaries
        """
        logger.info("Fetching Kalshi positions...")
        result = self._make_authenticated_request('GET', '/portfolio/positions')

        if not result:
            logger.warning("No result from Kalshi positions API")
            return []

        # Kalshi API returns market_positions, not positions
        positions_list = result.get('market_positions', [])

        if not positions_list:
            logger.warning(f"No market_positions found. Available keys: {result.keys()}")
            # Try event_positions as fallback
            positions_list = result.get('event_positions', [])
            if not positions_list:
                logger.warning("No event_positions found either")
                return []

        logger.info(f"Received {len(positions_list)} positions from Kalshi API")

        # Log the first position to see what fields are available
        if positions_list:
            logger.info(f"Sample position data (first position): {json.dumps(positions_list[0], indent=2)}")

        formatted_positions = []
        for pos in positions_list:
            ticker = pos.get('ticker', '')
            # API may return 'position' (int) or 'position_fp' (string fixed-point)
            position_value = pos.get('position', None)
            if position_value is None:
                position_fp = pos.get('position_fp', '0')
                try:
                    position_value = float(position_fp)
                except (ValueError, TypeError):
                    position_value = 0

            # Skip positions with 0 quantity
            if position_value == 0:
                logger.debug(f"Skipping {ticker} - position is 0")
                continue

            # Parse ticker to extract strike and side
            # Example tickers: KXBTC-25NOV1017-B96250 (Below 96,250)
            #                  KXBTCD-25NOV1017-T95999.99 (Top/Above 95,999.99)
            strike = None
            side = 'UNKNOWN'
            expiry_date = None

            ticker_parts = ticker.split('-')
            if len(ticker_parts) >= 3:
                # Extract date: 25NOV1017 -> 2025-11-10 17:00
                date_str = ticker_parts[1]
                # Extract strike: B96250 or T95999.99
                strike_part = ticker_parts[2]

                # Parse side from position sign (applies to both B and T contracts)
                # Positive position = YES contracts owned
                # Negative position = NO contracts owned
                # B=Below contract type, T=Top/Above contract type (doesn't affect side detection)
                if strike_part.startswith('B'):
                    side = 'YES' if position_value > 0 else 'NO'
                    strike_str = strike_part[1:]
                elif strike_part.startswith('T'):
                    side = 'YES' if position_value > 0 else 'NO'  # Same logic as B - position sign determines side
                    strike_str = strike_part[1:]
                else:
                    strike_str = strike_part

                try:
                    strike = float(strike_str)
                except ValueError:
                    strike = strike_str

                # Parse expiry date
                try:
                    # Example: 25NOV1017 -> Nov 10, 2025 17:00
                    expiry_date = f"{date_str[:2]}-{date_str[2:5]}-{date_str[5:7]} {date_str[7:9]}:00"
                except:
                    expiry_date = date_str

            # Get all available price/cost fields from API
            # API may return fields as cents (int) or as '_dollars' strings
            def _dollars(key):
                v = pos.get(key + '_dollars', pos.get(key, 0))
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return 0.0

            total_traded_dollars = _dollars('total_traded')   # dollars
            market_exposure_dollars = _dollars('market_exposure')  # dollars
            fees_paid_dollars = _dollars('fees_paid')  # dollars
            realized_pnl_dollars = _dollars('realized_pnl')  # dollars
            resting_orders_count = pos.get('resting_orders_count', 0)

            # Convert legacy cent-based fields if they came in as cents (>1 and no _dollars suffix present)
            # If _dollars suffix was used, values are already in dollars; otherwise divide by 100
            if pos.get('total_traded_dollars') is None and total_traded_dollars > 1:
                total_traded_dollars /= 100
                market_exposure_dollars /= 100
                fees_paid_dollars /= 100
                realized_pnl_dollars /= 100

            # Calculate entry price per contract (as fraction 0-1)
            entry_price = 0
            if position_value != 0 and total_traded_dollars != 0:
                entry_price = total_traded_dollars / abs(position_value)

            # Calculate current price per contract (as fraction 0-1)
            current_price = 0
            if position_value != 0 and market_exposure_dollars != 0:
                current_price = market_exposure_dollars / abs(position_value)

            # Get market status fields
            market_status = pos.get('market_status', 'open')

            formatted_positions.append({
                'ticker': ticker,
                'position': position_value,
                'quantity': abs(position_value),
                'side': side,
                'strike': strike,
                'entry_price': entry_price,
                'current_price': current_price,
                'total_cost': total_traded_dollars,
                'current_value': market_exposure_dollars,
                'pnl': market_exposure_dollars - total_traded_dollars,
                'fees_paid': fees_paid_dollars,
                'realized_pnl': realized_pnl_dollars,
                'resting_orders': resting_orders_count,
                'status': market_status,
                'expiry': expiry_date
            })

            logger.debug(f"Formatted position: {ticker} | strike=${strike} | side={side} | qty={position_value} | entry={entry_price}¢ | current={current_price}¢")

        logger.info(f"Returning {len(formatted_positions)} formatted positions")
        return formatted_positions

    def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        price: int,
        action: str = "buy",
        order_type: str = "limit"
    ) -> Optional[Dict]:
        """
        Place an order on a prediction market

        Args:
            ticker: Market ticker symbol
            side: "yes" or "no"
            quantity: Number of contracts
            price: Price in cents (1-99)
            action: "buy" or "sell"
            order_type: "limit" or "market"

        Returns:
            Order result dictionary
        """
        if price < 1 or price > 99:
            logger.error("Price must be between 1 and 99 cents")
            return None

        order_data = {
            'ticker': ticker,
            'action': action.lower(),
            'side': side.lower(),
            'count': quantity,
            'type': order_type,
            'yes_price': price if side.lower() == 'yes' else None,
            'no_price': price if side.lower() == 'no' else None
        }

        logger.info(f"Placing {action} order: {ticker} {side} x{quantity} @ {price}¢")
        result = self._make_authenticated_request('POST', '/portfolio/orders', order_data)

        if result and 'order' in result:
            order = result['order']
            logger.info(f"Order placed successfully: {order.get('order_id')}")
            return {
                'order_id': order.get('order_id'),
                'ticker': ticker,
                'side': side,
                'action': action,
                'quantity': quantity,
                'price': price,
                'status': order.get('status'),
                'timestamp': datetime.now().isoformat()
            }

        logger.error(f"Failed to place order: {result}")
        return None

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order

        Args:
            order_id: The order ID to cancel

        Returns:
            Success boolean
        """
        result = self._make_authenticated_request('DELETE', f'/portfolio/orders/{order_id}')
        return result is not None

    def get_orders(self, ticker: str = None) -> List[Dict]:
        """
        Get order history

        Args:
            ticker: Optional ticker to filter by

        Returns:
            List of order dictionaries
        """
        endpoint = '/portfolio/orders'
        if ticker:
            endpoint += f'?ticker={ticker}'

        result = self._make_authenticated_request('GET', endpoint)

        if not result or 'orders' not in result:
            return []

        formatted_orders = []
        for order in result['orders']:
            formatted_orders.append({
                'order_id': order.get('order_id'),
                'ticker': order.get('ticker'),
                'side': order.get('side'),
                'quantity': order.get('count'),
                'price': order.get('yes_price', order.get('no_price', 0)),
                'status': order.get('status'),
                'created_at': order.get('created_time')
            })

        return formatted_orders

    def get_status(self) -> Dict:
        """
        Get current engine status

        Returns:
            Status dictionary
        """
        return {
            'connected': self.is_connected,
            'platform': 'Kalshi',
            'host': self.host,
            'demo_mode': self.demo_mode,
            'has_credentials': bool(self.api_key_id and self.private_key),
            'us_legal': True,
            'regulated': 'CFTC'
        }


# Example usage
if __name__ == "__main__":
    # Initialize engine
    engine = KalshiEngine()

    # Get status
    status = engine.get_status()
    print(f"Kalshi Status: {status}")

    # Get markets
    if engine.is_connected:
        markets = engine.get_markets(limit=5)
        print(f"\nTop 5 Active Markets:")
        for market in markets:
            print(f"- {market['question']}")
            print(f"  YES: ${market['yes_price']:.2f} | NO: ${market['no_price']:.2f}")
            print(f"  Volume: {market['volume']:,}")
