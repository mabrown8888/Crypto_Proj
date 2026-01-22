#!/usr/bin/env python3
"""
Polymarket Prediction Market Trading Engine
Integrates Polymarket prediction markets with the trading dashboard
"""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PolymarketEngine:
    """
    Engine for trading on Polymarket prediction markets
    """

    def __init__(self, private_key: str = None, proxy_address: str = None, signature_type: int = 1):
        """
        Initialize Polymarket client

        Args:
            private_key: Ethereum private key (from Magic.link or wallet)
            proxy_address: Polymarket proxy wallet address
            signature_type: 1 for Magic/email, 2 for browser wallets, 0 for EOA
        """
        self.private_key = private_key or os.getenv('POLYMARKET_PRIVATE_KEY')
        self.proxy_address = proxy_address or os.getenv('POLYMARKET_PROXY_ADDRESS')
        self.signature_type = signature_type

        # Polymarket API host
        self.host = "https://clob.polymarket.com"
        self.chain_id = 137  # Polygon mainnet

        # Initialize client if credentials available
        self.client = None
        self.is_connected = False

        if self.private_key and self.proxy_address:
            try:
                self.connect()
            except Exception as e:
                logger.error(f"Failed to initialize Polymarket client: {e}")
        else:
            logger.warning("Polymarket credentials not found in environment")

    def connect(self):
        """Connect to Polymarket"""
        try:
            self.client = ClobClient(
                host=self.host,
                key=self.private_key,
                chain_id=self.chain_id,
                signature_type=self.signature_type,
                funder=self.proxy_address
            )

            # Create or derive API credentials
            self.client.set_api_creds(self.client.create_or_derive_api_creds())

            self.is_connected = True
            logger.info("Successfully connected to Polymarket")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Polymarket: {e}")
            self.is_connected = False
            return False

    def get_markets(self, limit: int = 20) -> List[Dict]:
        """
        Get active prediction markets

        Args:
            limit: Number of markets to return

        Returns:
            List of market data dictionaries
        """
        try:
            response = requests.get(
                f"{self.host}/markets",
                params={"limit": limit, "active": True}
            )
            response.raise_for_status()
            markets = response.json()

            # Format market data
            formatted_markets = []
            for market in markets:
                formatted_markets.append({
                    'id': market.get('condition_id'),
                    'question': market.get('question'),
                    'description': market.get('description', ''),
                    'end_date': market.get('end_date_iso'),
                    'volume': market.get('volume', 0),
                    'liquidity': market.get('liquidity', 0),
                    'yes_price': market.get('outcome_prices', [0.5, 0.5])[0] if market.get('outcome_prices') else 0.5,
                    'no_price': market.get('outcome_prices', [0.5, 0.5])[1] if market.get('outcome_prices') else 0.5,
                    'category': market.get('category', 'Other'),
                    'tokens': market.get('tokens', [])
                })

            return formatted_markets
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []

    def get_market_details(self, condition_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific market

        Args:
            condition_id: The market condition ID

        Returns:
            Market details dictionary
        """
        try:
            response = requests.get(f"{self.host}/markets/{condition_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch market details: {e}")
            return None

    def get_balance(self) -> Optional[Dict]:
        """
        Get USDC balance

        Returns:
            Balance information
        """
        if not self.is_connected or not self.client:
            logger.error("Not connected to Polymarket")
            return None

        try:
            # Get balance from the API
            balance = self.client.get_balance()
            return {
                'usdc': float(balance) / 1e6 if balance else 0.0  # Convert from microUSDC
            }
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return None

    def get_positions(self) -> List[Dict]:
        """
        Get current open positions

        Returns:
            List of position dictionaries
        """
        if not self.is_connected or not self.client:
            logger.error("Not connected to Polymarket")
            return []

        try:
            positions = self.client.get_positions()
            formatted_positions = []

            for pos in positions:
                formatted_positions.append({
                    'market_id': pos.get('market'),
                    'token_id': pos.get('asset_id'),
                    'side': pos.get('side'),  # YES or NO
                    'size': float(pos.get('size', 0)),
                    'value': float(pos.get('value', 0)),
                    'avg_price': float(pos.get('avg_price', 0)),
                    'current_price': float(pos.get('current_price', 0)),
                    'pnl': float(pos.get('pnl', 0))
                })

            return formatted_positions
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            return []

    def place_order(
        self,
        token_id: str,
        side: str,
        size: float,
        price: float,
        order_type: str = "GTC"
    ) -> Optional[Dict]:
        """
        Place an order on a prediction market

        Args:
            token_id: Token ID for the market outcome
            side: "BUY" or "SELL"
            size: Amount to trade in USDC
            price: Price per share (0.0 to 1.0)
            order_type: "GTC" (Good-til-cancelled) or "FOK" (Fill-or-kill)

        Returns:
            Order result dictionary
        """
        if not self.is_connected or not self.client:
            logger.error("Not connected to Polymarket")
            return None

        try:
            # Validate inputs
            if not 0 < price < 1:
                raise ValueError("Price must be between 0 and 1")

            if size <= 0:
                raise ValueError("Size must be positive")

            # Create order
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side.upper(),
                fee_rate_bps=0  # Fee rate in basis points
            )

            # Submit order
            if order_type.upper() == "FOK":
                result = self.client.create_and_post_order(order_args, OrderType.FOK)
            else:
                result = self.client.create_and_post_order(order_args, OrderType.GTC)

            logger.info(f"Order placed: {side} {size} @ {price}")

            return {
                'order_id': result.get('orderID'),
                'token_id': token_id,
                'side': side,
                'size': size,
                'price': price,
                'status': result.get('status', 'PENDING'),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order

        Args:
            order_id: The order ID to cancel

        Returns:
            Success boolean
        """
        if not self.is_connected or not self.client:
            logger.error("Not connected to Polymarket")
            return False

        try:
            result = self.client.cancel(order_id)
            logger.info(f"Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False

    def get_order_book(self, token_id: str) -> Optional[Dict]:
        """
        Get order book for a specific token

        Args:
            token_id: Token ID

        Returns:
            Order book with bids and asks
        """
        try:
            response = requests.get(f"{self.host}/book", params={"token_id": token_id})
            response.raise_for_status()
            book = response.json()

            return {
                'bids': book.get('bids', []),
                'asks': book.get('asks', []),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to fetch order book: {e}")
            return None

    def get_trade_history(self) -> List[Dict]:
        """
        Get historical trades

        Returns:
            List of trade dictionaries
        """
        if not self.is_connected or not self.client:
            logger.error("Not connected to Polymarket")
            return []

        try:
            trades = self.client.get_trades()
            formatted_trades = []

            for trade in trades:
                formatted_trades.append({
                    'trade_id': trade.get('id'),
                    'market_id': trade.get('market'),
                    'side': trade.get('side'),
                    'size': float(trade.get('size', 0)),
                    'price': float(trade.get('price', 0)),
                    'timestamp': trade.get('timestamp'),
                    'status': trade.get('status')
                })

            return formatted_trades
        except Exception as e:
            logger.error(f"Failed to fetch trade history: {e}")
            return []

    def get_status(self) -> Dict:
        """
        Get current engine status

        Returns:
            Status dictionary
        """
        return {
            'connected': self.is_connected,
            'platform': 'Polymarket',
            'host': self.host,
            'has_credentials': bool(self.private_key and self.proxy_address)
        }


# Example usage
if __name__ == "__main__":
    # Initialize engine
    engine = PolymarketEngine()

    # Get status
    status = engine.get_status()
    print(f"Polymarket Status: {status}")

    # Get markets
    if engine.is_connected:
        markets = engine.get_markets(limit=5)
        print(f"\nTop 5 Active Markets:")
        for market in markets:
            print(f"- {market['question']}")
            print(f"  YES: ${market['yes_price']:.2f} | NO: ${market['no_price']:.2f}")
            print(f"  Volume: ${market['volume']:,.0f}")
