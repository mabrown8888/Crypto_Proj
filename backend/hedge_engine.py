"""
BTC Hedging Engine

Orchestrates the BTC hedging strategy using:
1. Coinbase for BTC portfolio and spot prices
2. Kalshi for binary options ladder ("BTC < K" contracts)
3. HedgeOptimizer for LP-based optimization

The engine dynamically reads BTC holdings, fetches available markets,
optimizes the hedge ladder, and executes orders.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from coinbase.rest import RESTClient
from kalshi_engine import KalshiEngine
from hedge_optimizer import HedgeOptimizer, EnhancedHedgeOptimizer

# Trade log file path
TRADE_LOG_FILE = os.path.join(os.path.dirname(__file__), 'trade_log.json')
# Position tracking file for cash-out system
POSITION_TRACKER_FILE = os.path.join(os.path.dirname(__file__), 'position_tracker.json')

logger = logging.getLogger(__name__)

# =============================================================================
# SMART CASH-OUT CONFIGURATION
# =============================================================================
# MODE: MINIMAL INTERVENTION
# - Only exit on stop-loss or near-expiry protection
# - Let positions ride to settlement (binary options should settle, not be traded)
# =============================================================================
CASH_OUT_CONFIG = {
    # -------------------------------------------------------------------------
    # PRICE-ZONE THRESHOLDS (determines which rules apply)
    # -------------------------------------------------------------------------
    'deep_itm_threshold': 70,      # Price > 70¢ = deep in the money
    'otm_threshold': 30,           # Price < 30¢ = out of the money
    # Between 30-70¢ = at the money (normal rules)

    # -------------------------------------------------------------------------
    # OUT OF THE MONEY (price < 30¢) - DISABLED (let it ride)
    # -------------------------------------------------------------------------
    'otm_tier1_profit_pct': 9.99,  # DISABLED - was 0.20
    'otm_tier1_sell_pct': 0.50,
    'otm_tier2_profit_pct': 9.99,  # DISABLED - was 0.40
    'otm_tier2_sell_pct': 0.30,
    'otm_tier3_profit_pct': 9.99,  # DISABLED - was 0.60
    'otm_tier3_sell_pct': 1.00,

    # -------------------------------------------------------------------------
    # AT THE MONEY (30-70¢) - DISABLED (let it ride)
    # -------------------------------------------------------------------------
    'atm_tier1_profit_pct': 9.99,  # DISABLED - was 0.25
    'atm_tier1_sell_pct': 0.50,
    'atm_tier2_profit_pct': 9.99,  # DISABLED - was 0.50
    'atm_tier2_sell_pct': 0.30,
    'atm_tier3_profit_pct': 9.99,  # DISABLED - was 0.75
    'atm_tier3_sell_pct': 1.00,

    # -------------------------------------------------------------------------
    # DEEP IN THE MONEY (price > 70¢) - let it ride to $1
    # -------------------------------------------------------------------------
    # NO profit-based exits! Expected payout is ~$1
    'ditm_min_profit_to_sell': 9.99,  # DISABLED - let it settle at $1

    # -------------------------------------------------------------------------
    # TIME-BASED RULES
    # -------------------------------------------------------------------------
    'urgent_exit_hours': 1,        # < 1 hour = urgent decisions
    'theta_warning_hours': 6,      # < 6 hours = theta accelerating
    'theta_exit_hours': 72,        # < 72 hours = consider theta (for longer dated)

    # Near-expiry behavior (STILL ACTIVE - protects against theta death):
    'near_expiry_itm_hold': 60,    # If < 1hr left AND price > 60¢ → HOLD for $1
    'near_expiry_otm_exit': 40,    # If < 1hr left AND price < 40¢ → EXIT (theta death)

    # -------------------------------------------------------------------------
    # UNIVERSAL RULES (apply to all zones)
    # -------------------------------------------------------------------------
    'spread_collapse_threshold': 0.00,  # DISABLED - was 0.05, don't exit on spread
    'stop_loss_pct': -0.30,             # ACTIVE - Exit at -30% loss
    'min_position_size': 1,
    'cooldown_minutes': 60,             # Don't sell positions less than 60 min old

    # -------------------------------------------------------------------------
    # MONITORING
    # -------------------------------------------------------------------------
    'check_interval_seconds': 30,  # Check every 30 seconds
}


class HedgeEngine:
    """Main orchestrator for BTC hedging with Kalshi binary options."""

    def __init__(self):
        """Initialize the hedge engine with Coinbase and Kalshi clients."""
        self.coinbase_client = None
        self.coinbase_derivatives_client = None
        self.kalshi_engine = None
        self.active_hedges = []  # Track active hedge positions
        self.last_optimization = None
        self._init_clients()

    def _init_clients(self):
        """Initialize Coinbase and Kalshi API clients."""
        # Initialize Coinbase spot client
        try:
            api_key = os.getenv('COINBASE_API_KEY')
            api_secret = os.getenv('COINBASE_API_SECRET')

            if api_key and api_secret:
                self.coinbase_client = RESTClient(api_key=api_key, api_secret=api_secret)
                logger.info("Coinbase spot client initialized successfully")
            else:
                logger.warning("Coinbase spot credentials not found")
        except Exception as e:
            logger.error(f"Failed to initialize Coinbase spot client: {e}")

        # Initialize Coinbase derivatives client (for perpetual futures)
        try:
            deriv_api_key = os.getenv('COINBASE_DERIVATIVES_API_KEY')
            deriv_api_secret = os.getenv('COINBASE_DERIVATIVES_API_SECRET')

            if deriv_api_key and deriv_api_secret:
                self.coinbase_derivatives_client = RESTClient(api_key=deriv_api_key, api_secret=deriv_api_secret)
                logger.info("Coinbase derivatives client initialized successfully")
            else:
                logger.warning("Coinbase derivatives credentials not found - perpetual futures will not be available")
        except Exception as e:
            logger.error(f"Failed to initialize Coinbase derivatives client: {e}")

        # Initialize Kalshi
        try:
            self.kalshi_engine = KalshiEngine()
            logger.info("Kalshi engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Kalshi engine: {e}")

    def get_btc_portfolio(self) -> Dict:
        """
        Get current BTC holdings and value from Coinbase.

        Returns:
            Dict with:
                - btc_balance: float (BTC amount)
                - btc_price: float (current spot price)
                - notional_value: float (BTC * price)
                - success: bool
                - message: str
        """
        if not self.coinbase_client:
            return {
                'success': False,
                'message': 'Coinbase client not initialized',
                'btc_balance': 0,
                'btc_price': 0,
                'notional_value': 0
            }

        try:
            # Get BTC account
            accounts_response = self.coinbase_client.get_accounts()
            btc_balance = 0.0

            # Debug logging
            logger.info(f"Accounts response type: {type(accounts_response)}")

            # Access the accounts attribute of the response object
            if accounts_response and hasattr(accounts_response, 'accounts'):
                logger.info(f"Found {len(accounts_response.accounts)} accounts")
                for account in accounts_response.accounts:
                    currency = account.currency if hasattr(account, 'currency') else 'Unknown'
                    logger.info(f"Account currency: {currency}")

                    if hasattr(account, 'currency') and account.currency == 'BTC':
                        logger.info("Found BTC account!")
                        if hasattr(account, 'available_balance'):
                            logger.info(f"Available balance object: {account.available_balance}")
                            # available_balance can be either a dict or an object
                            if isinstance(account.available_balance, dict):
                                btc_balance = float(account.available_balance.get('value', 0))
                                logger.info(f"BTC balance value (from dict): {btc_balance}")
                            elif hasattr(account.available_balance, 'value'):
                                btc_balance = float(account.available_balance.value)
                                logger.info(f"BTC balance value (from object): {btc_balance}")
                            break
                        else:
                            logger.warning("BTC account has no available_balance attribute")
            else:
                logger.warning("No accounts attribute in response")

            # Get current BTC price
            btc_price = self.get_btc_spot_price()

            notional_value = btc_balance * btc_price

            logger.info(f"BTC Portfolio: {btc_balance:.4f} BTC @ ${btc_price:.2f} = ${notional_value:.2f}")

            return {
                'success': True,
                'message': 'Portfolio retrieved successfully',
                'btc_balance': btc_balance,
                'btc_price': btc_price,
                'notional_value': notional_value,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting BTC portfolio: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'btc_balance': 0,
                'btc_price': 0,
                'notional_value': 0
            }

    def get_btc_spot_price(self) -> float:
        """
        Get current BTC spot price from Coinbase.

        Returns:
            BTC price in USD
        """
        if not self.coinbase_client:
            logger.warning("Coinbase client not available, using fallback price")
            return 67000.0  # Fallback price

        try:
            product = self.coinbase_client.get_product('BTC-USD')
            # product is a GetProductResponse object with attributes, not a dict
            if product and hasattr(product, 'price'):
                price = float(product.price)
                return price
            else:
                raise Exception("No price attribute in product response")
        except Exception as e:
            logger.error(f"Error getting BTC spot price: {e}")
            # Fallback: try alternative method
            try:
                import requests
                response = requests.get('https://api.coinbase.com/v2/prices/BTC-USD/spot')
                data = response.json()
                price = float(data['data']['amount'])
                return price
            except:
                return 114000.0  # Final fallback (updated to current price)

    def get_btc_hedge_markets(self, min_volume: int = 100) -> List[Dict]:
        """
        Fetch available BTC binary options markets from Kalshi.

        Args:
            min_volume: Minimum volume filter

        Returns:
            List of markets with structure:
                [{'strike': K, 'yes_price': p, 'ticker': '...', ...}, ...]
        """
        if not self.kalshi_engine:
            logger.error("Kalshi engine not initialized")
            return []

        try:
            # Get crypto markets from Kalshi
            markets = self.kalshi_engine.get_markets(
                limit=100,
                status='open',
                category='crypto',
                min_volume=min_volume
            )

            logger.info(f"Fetched {len(markets)} total crypto markets from Kalshi")
            if markets:
                # Log first 5 market titles to see what's available
                logger.info("Sample market titles:")
                for m in markets[:5]:
                    logger.info(f"  - {m.get('id', 'N/A')}: {m.get('question', 'N/A')}")

            # Filter for BTC markets and extract strike prices
            btc_markets = []
            btc_markets_no_strike = []
            for market in markets:
                ticker = market.get('id', '')  # kalshi_engine returns 'id', not 'ticker'
                title = market.get('question', '').upper()  # kalshi_engine returns 'question', not 'title'
                subtitle = market.get('subtitle', '').upper()  # subtitle often contains the strike
                full_text = f"{title} {subtitle}"  # Combine both for strike extraction

                # Look for BTC price-based binary options
                # We can use both BELOW and ABOVE markets:
                # - BELOW markets: Buy YES (pays if BTC < strike)
                # - ABOVE markets: Buy NO (pays if BTC <= strike)
                if ('BTC' in full_text or 'BITCOIN' in full_text):
                    # Try to extract strike price from both title and subtitle
                    strike = self._extract_strike_from_title(subtitle) or self._extract_strike_from_title(title)
                    if strike:
                        market['strike'] = strike
                        # Mark if this is an ABOVE market (we'll buy NO side for hedging)
                        market['is_above_market'] = 'ABOVE' in full_text or 'OVER' in full_text or 'OR ABOVE' in full_text
                        btc_markets.append(market)
                    else:
                        btc_markets_no_strike.append({'ticker': ticker, 'title': title, 'subtitle': subtitle})

            logger.info(f"Found {len(btc_markets)} BTC hedge markets with strikes")
            if btc_markets_no_strike:
                logger.info(f"Found {len(btc_markets_no_strike)} BTC markets without extractable strikes:")
                for m in btc_markets_no_strike[:5]:  # Log first 5
                    logger.info(f"  - {m['ticker']}: {m['title']}")
            return btc_markets

        except Exception as e:
            logger.error(f"Error fetching BTC hedge markets: {e}")
            return []

    def _extract_strike_from_title(self, title: str) -> Optional[float]:
        """
        Extract strike price from market title or subtitle.

        Args:
            title: Market title/subtitle like "Below $100,000" or "$130,000 or above"

        Returns:
            Strike price as float, or None if not found
        """
        import re

        # Pattern to match prices like $70,000 or $70000 or 70000
        # Try multiple patterns in order of specificity
        patterns = [
            r'\$?([\d,]+,\d{3})',              # Match $70,000 or 70,000 (with commas)
            r'\$?([\d,]+)',                     # Match $70,000 without commas requirement
            r'BELOW\s*\$?([\d,]+)',             # Match "BELOW $100,000" or "Below 100,000"
            r'ABOVE\s*\$?([\d,]+)',             # Match "ABOVE $100,000" or "Above 100,000"
            r'OR\s+ABOVE\s*\$?([\d,]+)',        # Match "$130,000 or above"
            r'(\d{5,})\s+OR\s+ABOVE',           # Match "100000 or above"
            r'\$?(\d{5,})',                     # Match $70000 or 70000 (fallback)
        ]

        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(',', '')
                try:
                    price = float(price_str)
                    # Sanity check: BTC prices should be between $1k and $10M
                    if 1000 <= price <= 10000000:
                        return price
                except:
                    continue

        return None

    def optimize_hedge(self,
                      budget_pct: float = 0.02,
                      target_coverage: float = 0.68,
                      min_coverage_drawdown: float = -0.20,
                      min_volume: int = 100) -> Dict:
        """
        Optimize the hedge ladder using linear programming.

        Args:
            budget_pct: Monthly budget as % of notional (e.g., 0.02 for 2%)
            target_coverage: Target "cents on dollar" at min_coverage_drawdown
            min_coverage_drawdown: Drawdown level for target coverage (e.g., -0.20)
            min_volume: Minimum market volume filter

        Returns:
            Dict with optimization results including optimal_weights, total_cost, coverage, etc.
        """
        # Get BTC portfolio
        portfolio = self.get_btc_portfolio()
        if not portfolio['success']:
            return {
                'success': False,
                'message': f"Failed to get portfolio: {portfolio['message']}",
                'markets_used': [],
                'total_cost': 0,
                'coverage_at_scenarios': {}
            }

        btc_balance = portfolio['btc_balance']
        btc_price = portfolio['btc_price']

        if btc_balance == 0:
            return {
                'success': False,
                'message': 'No BTC holdings to hedge',
                'markets_used': [],
                'total_cost': 0,
                'coverage_at_scenarios': {}
            }

        # Get available markets
        markets = self.get_btc_hedge_markets(min_volume=min_volume)
        if not markets:
            return {
                'success': False,
                'message': 'No suitable BTC hedge markets found on Kalshi',
                'markets_used': [],
                'total_cost': 0,
                'coverage_at_scenarios': {}
            }

        logger.info(f"Optimizing hedge for {btc_balance:.4f} BTC @ ${btc_price:.2f}")
        logger.info(f"Budget: {budget_pct*100:.1f}%, Target coverage: {target_coverage*100:.0f}% at {min_coverage_drawdown*100:.0f}% drawdown")

        # Adjust prices for ABOVE markets (we buy NO side for hedging)
        for market in markets:
            if market.get('is_above_market'):
                # For ABOVE markets, we buy NO which costs: no_price = 100 - yes_price
                yes_price = market.get('yes_price', 0)
                no_price = market.get('no_price', 100 - yes_price)
                # Override yes_price with no_price for the optimizer
                market['yes_price'] = no_price
                market['hedge_side'] = 'no'  # Mark that we're buying NO
                logger.info(f"Using ABOVE market {market.get('id')}: Strike ${market['strike']}, NO price={no_price}¢")
            else:
                market['hedge_side'] = 'yes'  # Mark that we're buying YES

        # Initialize optimizer
        optimizer = HedgeOptimizer(
            current_btc_price=btc_price,
            btc_holdings=btc_balance
        )

        # Run optimization
        result = optimizer.optimize_ladder(
            markets=markets,
            budget_pct=budget_pct,
            target_coverage=target_coverage,
            min_coverage_drawdown=min_coverage_drawdown
        )

        # If optimization failed due to infeasibility, provide helpful message
        if not result['success'] and 'infeasible' in result.get('message', '').lower():
            market_info = []
            for m in markets[:3]:  # Show first 3 markets
                strike = m.get('strike', 0)
                price = m.get('yes_price', 0)
                market_info.append(f"${strike:,.0f} @ {price}¢")

            return {
                'success': False,
                'message': f"Cannot optimize hedge: Available Kalshi markets have strikes too far from current price (${btc_price:,.0f}). Available: {', '.join(market_info)}. Need markets with strikes closer to current price for effective hedging.",
                'markets_used': [],
                'total_cost': 0,
                'coverage_at_scenarios': {},
                'available_markets': markets
            }

        if result['success']:
            self.last_optimization = {
                'timestamp': datetime.now().isoformat(),
                'result': result,
                'portfolio': portfolio
            }

        return result

    def optimize_hedge_advanced(
        self,
        budget_pct: float = 0.02,
        target_coverage: float = 0.68,
        min_coverage_drawdown: float = -0.20,
        horizon_days: int = 30,
        min_volume: int = 100,
        prefer_underpriced: bool = True,
        include_theta: bool = True,
        include_transaction_costs: bool = True,
        slippage_pct: float = 0.015,
        signal_kwargs: Dict = None
    ) -> Dict:
        """
        Advanced hedge optimization with GARCH volatility, probability-weighted
        scenarios, IV analysis, and transaction cost modeling.

        Args:
            budget_pct: Monthly budget as % of notional
            target_coverage: Target cents-on-dollar at min_coverage_drawdown
            min_coverage_drawdown: Drawdown level for target coverage
            horizon_days: Time horizon for GARCH scenarios
            min_volume: Minimum market volume filter
            prefer_underpriced: Weight toward mispriced options
            include_theta: Factor in time decay
            include_transaction_costs: Model slippage
            slippage_pct: Slippage as fraction
            signal_kwargs: Signal values for probability adjustment

        Returns:
            Enhanced dict with GARCH volatility, scenario probabilities,
            IV analysis, and mispriced options
        """
        # Get BTC portfolio
        portfolio = self.get_btc_portfolio()
        if not portfolio['success']:
            return {
                'success': False,
                'message': f"Failed to get portfolio: {portfolio['message']}",
                'markets_used': [],
                'total_cost': 0,
                'coverage_at_scenarios': {}
            }

        btc_balance = portfolio['btc_balance']
        btc_price = portfolio['btc_price']

        if btc_balance == 0:
            return {
                'success': False,
                'message': 'No BTC holdings to hedge',
                'markets_used': [],
                'total_cost': 0,
                'coverage_at_scenarios': {}
            }

        # Get available markets
        markets = self.get_btc_hedge_markets(min_volume=min_volume)
        if not markets:
            return {
                'success': False,
                'message': 'No suitable BTC hedge markets found on Kalshi',
                'markets_used': [],
                'total_cost': 0,
                'coverage_at_scenarios': {}
            }

        logger.info(f"Advanced optimization for {btc_balance:.4f} BTC @ ${btc_price:.2f}")

        # Initialize market data service and fetch historical data
        try:
            from market_data_service import get_market_data_service
            from volatility_model import GARCHVolatilityModel

            market_data = get_market_data_service()
            ohlc = market_data.fetch_ohlc_data(days=365)
            returns = market_data.calculate_log_returns()

            # Fit GARCH model
            garch_model = GARCHVolatilityModel()
            garch_params = garch_model.fit(returns)
            garch_vol = garch_model.get_current_volatility()

            logger.info(f"GARCH volatility: {garch_vol:.2%}")
            logger.info(f"GARCH params: alpha={garch_params['alpha']:.4f}, beta={garch_params['beta']:.4f}")

        except Exception as e:
            logger.warning(f"GARCH fitting failed: {e}, falling back to simple optimizer")
            # Fall back to simple optimization
            return self.optimize_hedge(
                budget_pct=budget_pct,
                target_coverage=target_coverage,
                min_coverage_drawdown=min_coverage_drawdown,
                min_volume=min_volume
            )

        # Adjust prices for ABOVE markets
        for market in markets:
            if market.get('is_above_market'):
                yes_price = market.get('yes_price', 0)
                no_price = market.get('no_price', 100 - yes_price)
                market['yes_price'] = no_price
                market['hedge_side'] = 'no'
            else:
                market['hedge_side'] = 'yes'

            # Add days_to_expiry if not present (default 30)
            if 'days_to_expiry' not in market:
                market['days_to_expiry'] = horizon_days

        # Initialize enhanced optimizer
        optimizer = EnhancedHedgeOptimizer(
            current_btc_price=btc_price,
            btc_holdings=btc_balance,
            market_data_service=market_data,
            volatility_model=garch_model
        )

        # Run advanced optimization
        result = optimizer.optimize_ladder_advanced(
            markets=markets,
            budget_pct=budget_pct,
            target_coverage=target_coverage,
            min_coverage_drawdown=min_coverage_drawdown,
            horizon_days=horizon_days,
            prefer_underpriced=prefer_underpriced,
            include_theta=include_theta,
            include_transaction_costs=include_transaction_costs,
            slippage_pct=slippage_pct,
            signal_kwargs=signal_kwargs
        )

        # Add portfolio info to result
        if result['success']:
            result['portfolio'] = portfolio
            result['historical_data'] = {
                'realized_vol_30d': float(market_data.calculate_realized_volatility(30)),
                'var_95_30d': market_data.calculate_historical_var(0.95, 30)['var_pct'],
                'drawdown_distribution': market_data.calculate_empirical_drawdown_distribution()['probabilities']
            }
            self.last_optimization = {
                'timestamp': datetime.now().isoformat(),
                'result': result,
                'portfolio': portfolio,
                'mode': 'advanced'
            }

        return result

    def get_volatility_analysis(self) -> Dict:
        """
        Get current volatility analysis including GARCH forecast and historical metrics.

        Returns:
            Dict with GARCH params, volatility forecasts, historical metrics
        """
        try:
            from market_data_service import get_market_data_service
            from volatility_model import GARCHVolatilityModel

            market_data = get_market_data_service()
            ohlc = market_data.fetch_ohlc_data(days=365)
            returns = market_data.calculate_log_returns()

            # Fit GARCH
            garch = GARCHVolatilityModel()
            params = garch.fit(returns)

            # Get forecasts
            current_vol = garch.get_current_volatility()
            forecast_df = garch.forecast_volatility(horizon=30)

            # Historical metrics
            realized_vol_30d = market_data.calculate_realized_volatility(30)
            realized_vol_7d = market_data.calculate_realized_volatility(7)
            var_result = market_data.calculate_historical_var(0.95, 30)
            drawdown_dist = market_data.calculate_empirical_drawdown_distribution()

            return {
                'success': True,
                'garch_volatility': current_vol,
                'garch_params': params,
                'realized_vol_30d': realized_vol_30d,
                'realized_vol_7d': realized_vol_7d,
                'vol_forecast_30d': float(forecast_df['volatility'].mean()) if len(forecast_df) > 0 else current_vol,
                'var_95_30d': var_result['var_pct'],
                'cvar_95_30d': var_result['cvar_pct'],
                'drawdown_probabilities': drawdown_dist['probabilities'],
                'interpretation': self._interpret_volatility(current_vol, realized_vol_30d),
                'current_price': market_data.get_current_price()
            }

        except Exception as e:
            logger.error(f"Volatility analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': str(e)
            }

    def _interpret_volatility(self, garch_vol: float, realized_vol: float) -> str:
        """Generate human-readable volatility interpretation."""
        vol_ratio = garch_vol / realized_vol if realized_vol > 0 else 1

        if vol_ratio > 1.2:
            regime = "GARCH forecasts higher vol than recent realized - expect increased volatility"
        elif vol_ratio < 0.8:
            regime = "GARCH forecasts lower vol than recent realized - volatility may be declining"
        else:
            regime = "GARCH and realized vol are aligned - stable volatility regime"

        if garch_vol > 0.8:
            level = "Extreme volatility (>80% annualized)"
        elif garch_vol > 0.6:
            level = "High volatility (60-80% annualized)"
        elif garch_vol > 0.4:
            level = "Moderate volatility (40-60% annualized)"
        else:
            level = "Low volatility (<40% annualized)"

        return f"{level}. {regime}"

    def execute_hedge(self, optimization_result: Dict, dry_run: bool = True) -> Dict:
        """
        Execute the optimized hedge by placing orders on Kalshi.

        Args:
            optimization_result: Result from optimize_hedge()
            dry_run: If True, simulate execution without placing real orders

        Returns:
            Dict with execution results
        """
        if not optimization_result.get('success'):
            return {
                'success': False,
                'message': 'Cannot execute invalid optimization result',
                'orders_placed': []
            }

        markets_used = optimization_result.get('markets_used', [])
        if not markets_used:
            return {
                'success': False,
                'message': 'No markets in optimization result',
                'orders_placed': []
            }

        if dry_run:
            logger.info("[DRY RUN] Would place the following orders:")
            for market in markets_used:
                logger.info(f"  - {market['ticker']}: {market['weight']:.2f} contracts @ {market['yes_price']:.0f}¢")

            return {
                'success': True,
                'message': f'[DRY RUN] Would place {len(markets_used)} orders',
                'orders_placed': markets_used,
                'total_cost': optimization_result['total_cost'],
                'dry_run': True
            }

        # Real execution
        if not self.kalshi_engine:
            return {
                'success': False,
                'message': 'Kalshi engine not initialized',
                'orders_placed': []
            }

        orders_placed = []
        failed_orders = []

        for market in markets_used:
            try:
                ticker = market['ticker']
                quantity = int(market['weight'])  # Round to integer contracts
                price = int(market['yes_price'])  # Price in cents

                if quantity == 0:
                    continue

                # Extract model probability and EV from optimization result
                model_prob = market.get('model_prob', 0)
                market_prob = market.get('market_prob', price / 100.0)
                ev = market.get('ev', model_prob - market_prob if model_prob else 0)

                # Determine correct side for the order
                hedge_side = market.get('hedge_side', 'yes')

                logger.info(f"Placing order: {ticker} {hedge_side.upper()} x{quantity} @ {price}¢ | model_prob={model_prob:.2%}, market_prob={market_prob:.2%}, EV={ev:.2%}")

                # Place order via Kalshi
                order_result = self.kalshi_engine.place_order(
                    ticker=ticker,
                    action='buy',
                    side=hedge_side,
                    quantity=quantity,
                    order_type='limit',
                    price=price
                )

                if order_result.get('success'):
                    orders_placed.append({
                        'ticker': ticker,
                        'quantity': quantity,
                        'price': price,
                        'side': hedge_side,
                        'order_id': order_result.get('order_id'),
                        'status': 'placed',
                        'model_prob': model_prob,
                        'market_prob': market_prob,
                        'ev': ev,
                        'placed_at': __import__('datetime').datetime.utcnow().isoformat() + 'Z'
                    })

                    # Track position for cash-out monitoring
                    self.track_new_position(
                        ticker=ticker,
                        entry_price=price,
                        quantity=quantity,
                        model_prob=model_prob,
                        market_prob=market_prob,
                        side=hedge_side
                    )
                else:
                    failed_orders.append({
                        'ticker': ticker,
                        'quantity': quantity,
                        'error': order_result.get('message')
                    })

            except Exception as e:
                logger.error(f"Error placing order for {market['ticker']}: {e}")
                failed_orders.append({
                    'ticker': market['ticker'],
                    'error': str(e)
                })

        success = len(orders_placed) > 0

        # Save trade log with model_prob and EV for analytics
        if orders_placed:
            self._save_trade_log(orders_placed)

        return {
            'success': success,
            'message': f'Placed {len(orders_placed)} orders, {len(failed_orders)} failed',
            'orders_placed': orders_placed,
            'failed_orders': failed_orders,
            'total_cost': sum(o['quantity'] * o['price'] / 100.0 for o in orders_placed),
            'dry_run': False
        }

    def _save_trade_log(self, orders: List[Dict]) -> None:
        """Save trade log with model_prob and EV for analytics tracking."""
        try:
            # Load existing log
            existing_log = []
            if os.path.exists(TRADE_LOG_FILE):
                try:
                    with open(TRADE_LOG_FILE, 'r') as f:
                        existing_log = json.load(f)
                except (json.JSONDecodeError, IOError):
                    existing_log = []

            # Append new trades
            existing_log.extend(orders)

            # Keep only last 1000 trades to prevent file bloat
            if len(existing_log) > 1000:
                existing_log = existing_log[-1000:]

            # Save updated log
            with open(TRADE_LOG_FILE, 'w') as f:
                json.dump(existing_log, f, indent=2)

            logger.info(f"Saved {len(orders)} trades to trade log (total: {len(existing_log)})")

        except Exception as e:
            logger.error(f"Failed to save trade log: {e}")

    @staticmethod
    def load_trade_log() -> List[Dict]:
        """Load trade log for analytics."""
        try:
            if os.path.exists(TRADE_LOG_FILE):
                with open(TRADE_LOG_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load trade log: {e}")
        return []

    # =========================================================================
    # SMART CASH-OUT SYSTEM
    # =========================================================================

    def _load_position_tracker(self) -> Dict:
        """Load position tracking data (entry prices, tier status)."""
        try:
            if os.path.exists(POSITION_TRACKER_FILE):
                with open(POSITION_TRACKER_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load position tracker: {e}")
        return {}

    def _save_position_tracker(self, tracker: Dict) -> None:
        """Save position tracking data."""
        try:
            with open(POSITION_TRACKER_FILE, 'w') as f:
                json.dump(tracker, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save position tracker: {e}")

    def track_new_position(self, ticker: str, entry_price: float, quantity: int,
                           model_prob: float, market_prob: float, side: str = 'yes') -> None:
        """
        Track a new position for cash-out monitoring.

        Args:
            ticker: Market ticker
            entry_price: Entry price in cents (0-100)
            quantity: Number of contracts
            model_prob: Model probability at entry (0-1)
            market_prob: Market probability at entry (0-1)
            side: 'yes' or 'no'
        """
        tracker = self._load_position_tracker()

        tracker[ticker] = {
            'ticker': ticker,
            'entry_price': entry_price,
            'entry_time': datetime.utcnow().isoformat() + 'Z',
            'original_quantity': quantity,
            'current_quantity': quantity,
            'model_prob_at_entry': model_prob,
            'market_prob_at_entry': market_prob,
            'side': side,
            'tier1_sold': False,
            'tier2_sold': False,
            'tier3_sold': False,
            'total_sold': 0,
            'realized_pnl': 0.0,
            'cash_out_history': []
        }

        self._save_position_tracker(tracker)
        logger.info(f"Tracking new position: {ticker} x{quantity} @ {entry_price}¢")

    def sync_positions_from_kalshi(self) -> Dict:
        """
        Sync current Kalshi positions to the tracker.
        - Adds any positions not already being tracked
        - Updates entry prices for existing positions (fixes 0.0 entry prices)

        Returns:
            Dict with sync results
        """
        if not self.kalshi_engine:
            return {'success': False, 'message': 'Kalshi engine not initialized', 'synced': 0}

        tracker = self._load_position_tracker()
        synced = []
        updated = []
        removed = []

        # Clean up any yearly/long-dated contracts already in tracker
        tickers_to_remove = [t for t in tracker.keys()
                            if 'MAXY' in t or 'MINY' in t or 'MAX' in t.split('-')[0]]
        for ticker in tickers_to_remove:
            del tracker[ticker]
            removed.append(ticker)
            logger.info(f"Removed yearly contract from tracker: {ticker}")

        try:
            positions = self.kalshi_engine.get_positions()
            if not positions:
                if removed:
                    self._save_position_tracker(tracker)
                return {'success': True, 'message': f'No positions to sync, removed {len(removed)} yearly', 'synced': 0}

            for pos in positions:
                ticker = pos.get('ticker', '')
                position_qty = pos.get('position', 0)

                if position_qty == 0:
                    continue

                # Skip yearly/long-dated contracts - not suitable for active cash-out monitoring
                if 'MAXY' in ticker or 'MINY' in ticker or 'MAX' in ticker.split('-')[0]:
                    logger.debug(f"Skipping yearly contract: {ticker}")
                    continue

                # Get entry_price from Kalshi (calculated from total_traded / position)
                entry_price = pos.get('entry_price', 0)
                side = pos.get('side', 'yes').lower()
                quantity = pos.get('quantity', abs(position_qty))

                # Check if already tracked
                if ticker in tracker:
                    # Update entry price if it was 0 or missing (fix old bad syncs)
                    old_entry = tracker[ticker].get('entry_price', 0)
                    if old_entry == 0 and entry_price > 0:
                        tracker[ticker]['entry_price'] = entry_price
                        # Also update market_prob_at_entry
                        tracker[ticker]['market_prob_at_entry'] = entry_price / 100.0
                        tracker[ticker]['model_prob_at_entry'] = min(0.99, entry_price / 100.0 + 0.05)
                        updated.append({
                            'ticker': ticker,
                            'old_entry': old_entry,
                            'new_entry': entry_price
                        })
                        logger.info(f"Updated entry price: {ticker} {old_entry:.1f}¢ -> {entry_price:.1f}¢")
                    # Update quantity if changed
                    tracker[ticker]['current_quantity'] = quantity
                    continue

                # Estimate model_prob (we don't have it, use entry price + edge estimate)
                market_prob = entry_price / 100.0 if entry_price > 0 else 0.5
                model_prob = min(0.99, market_prob + 0.05)  # Assume 5% edge at entry

                # Add to tracker
                tracker[ticker] = {
                    'ticker': ticker,
                    'entry_price': entry_price,
                    'entry_time': datetime.utcnow().isoformat() + 'Z',  # Unknown, use now
                    'original_quantity': quantity,
                    'current_quantity': quantity,
                    'model_prob_at_entry': model_prob,
                    'market_prob_at_entry': market_prob,
                    'side': side,
                    'tier1_sold': False,
                    'tier2_sold': False,
                    'tier3_sold': False,
                    'total_sold': 0,
                    'realized_pnl': 0.0,
                    'cash_out_history': [],
                    'synced_from_kalshi': True  # Mark as synced (not originally tracked)
                }
                synced.append({
                    'ticker': ticker,
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'side': side
                })
                logger.info(f"Synced position: {ticker} x{quantity} @ {entry_price:.1f}¢ ({side})")

            self._save_position_tracker(tracker)

            parts = []
            if synced:
                parts.append(f'{len(synced)} new')
            if updated:
                parts.append(f'{len(updated)} updated')
            if removed:
                parts.append(f'{len(removed)} yearly removed')
            message = 'Synced: ' + ', '.join(parts) if parts else 'No changes'

            return {
                'success': True,
                'message': message,
                'synced': len(synced),
                'updated': len(updated),
                'removed': len(removed),
                'positions_synced': synced,
                'positions_updated': updated
            }

        except Exception as e:
            logger.error(f"Error syncing positions: {e}")
            return {'success': False, 'message': str(e), 'synced': 0}

    def get_current_market_price(self, ticker: str, side: str = 'yes') -> Optional[float]:
        """
        Get current market price for a ticker.

        Args:
            ticker: Market ticker
            side: 'yes' or 'no' - which side's price to return

        Returns:
            Current bid price for the specified side (what you can sell for)
        """
        if not self.kalshi_engine:
            return None

        try:
            market = self.kalshi_engine.get_market(ticker)
            if market:
                # Return the bid price for the side we own (what we can sell for)
                if side.lower() == 'no':
                    price = market.get('no_bid', market.get('no_ask', 0))
                else:
                    price = market.get('yes_bid', market.get('yes_ask', 0))

                logger.debug(f"Market {ticker} ({side}): yes_bid={market.get('yes_bid')}, no_bid={market.get('no_bid')}, returning {price}")
                return price if price > 0 else None
            else:
                logger.warning(f"No market data returned for {ticker}")
        except Exception as e:
            logger.error(f"Error getting market price for {ticker}: {e}")
        return None

    def get_hours_to_expiry(self, ticker: str) -> Optional[float]:
        """Get hours until market expiry."""
        try:
            # First try to get from API
            if self.kalshi_engine:
                market = self.kalshi_engine.get_market(ticker)
                if market:
                    expiry_str = market.get('expiration_time') or market.get('close_time')
                    if expiry_str:
                        expiry = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                        now = datetime.now(expiry.tzinfo)
                        delta = expiry - now
                        return max(0, delta.total_seconds() / 3600)

            # Fallback: parse from ticker (e.g., KXBTCD-26JAN2217-T89249.99)
            # Format: 26JAN2217 = year 2026, month JAN, day 22, hour 17
            parts = ticker.split('-')
            if len(parts) >= 2:
                date_part = parts[1]  # e.g., "26JAN2217"
                if len(date_part) >= 9:
                    year = int('20' + date_part[:2])  # 26 -> 2026
                    month_str = date_part[2:5].upper()  # JAN
                    day = int(date_part[5:7])  # 22
                    hour = int(date_part[7:9])  # 17

                    months = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                             'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
                    month = months.get(month_str, 1)

                    from datetime import timezone
                    # Kalshi uses ET (Eastern Time), but for simplicity use UTC
                    expiry = datetime(year, month, day, hour, 0, 0, tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    delta = expiry - now
                    hours = max(0, delta.total_seconds() / 3600)
                    logger.debug(f"Parsed expiry from ticker {ticker}: {expiry}, hours={hours:.1f}")
                    return hours

        except Exception as e:
            logger.error(f"Error getting expiry for {ticker}: {e}")
        return None

    def recalculate_model_prob(self, ticker: str, side: str = 'yes') -> Optional[float]:
        """
        Recalculate current model probability for a position.

        Returns the probability for the side being traded.

        Contract types:
        - B (Below): YES = BTC < strike, NO = BTC >= strike
        - T (Top/Above): YES = BTC > strike, NO = BTC <= strike

        ProbabilityModel.get_probability() returns P(BTC < strike).
        """
        try:
            from market_data_service import get_market_data_service
            from volatility_model import ProbabilityModel

            # Get current BTC price
            btc_price = self.get_btc_spot_price()
            if not btc_price:
                return None

            # Parse strike and contract type from ticker
            # e.g., KXBTC-26JAN2215-B89000 -> B, 89000
            # e.g., KXBTCD-26JAN2317-T88999.99 -> T, 88999.99
            parts = ticker.split('-')
            strike = None
            contract_type = None  # 'B' = Below, 'T' = Top/Above
            for part in parts:
                if part.startswith('B') or part.startswith('T'):
                    contract_type = part[0]
                    try:
                        strike = float(part[1:])
                        break
                    except ValueError:
                        continue

            if not strike:
                logger.warning(f"Could not parse strike from ticker: {ticker}")
                return None

            # Get hours to expiry
            hours = self.get_hours_to_expiry(ticker)
            if hours is None:
                hours = 24  # Default assumption

            # Calculate model probability using ProbabilityModel
            # get_probability() returns P(BTC < strike)
            market_data = get_market_data_service()
            returns = market_data.calculate_log_returns()

            prob_model = ProbabilityModel()
            prob_model.fit(returns)

            prob_result = prob_model.get_probability(
                current_price=btc_price,
                strike=strike,
                days_to_expiry=int(hours / 24) if hours >= 24 else 1
            )

            prob_below_strike = prob_result.get('adjusted_prob', prob_result.get('base_prob', 0.5))

            # Convert P(below) to the YES probability for this contract type
            if contract_type == 'T':
                # T (Above): YES = BTC > strike = 1 - P(below)
                yes_prob = 1 - prob_below_strike
            else:
                # B (Below): YES = BTC < strike = P(below)
                yes_prob = prob_below_strike

            # Return probability for the traded side
            if side.lower() == 'yes':
                return yes_prob
            else:
                return 1 - yes_prob

        except Exception as e:
            logger.error(f"Error recalculating model prob for {ticker}: {e}")
            return None

    def check_cash_out(self, ticker: str) -> Dict:
        """
        SMART cash-out check that considers:
        - Price zone (OTM/ATM/ITM)
        - Time to expiry
        - Whether to let winners ride to $1

        Returns:
            Dict with 'action' ('SELL', 'HOLD'), 'pct' (0-1), 'reason', and analytics
        """
        tracker = self._load_position_tracker()

        if ticker not in tracker:
            return {'action': 'HOLD', 'reason': 'Position not tracked', 'ticker': ticker}

        position = tracker[ticker]
        entry_price = position['entry_price']
        current_quantity = position['current_quantity']
        side = position.get('side', 'yes')

        if current_quantity < CASH_OUT_CONFIG['min_position_size']:
            return {'action': 'HOLD', 'reason': 'Position too small', 'ticker': ticker}

        # ---------------------------------------------------------------
        # COOLDOWN: Don't sell positions that are less than N minutes old
        # Prevents selling freshly-bought positions before they have time to move
        # ---------------------------------------------------------------
        entry_time_str = position.get('entry_time', '')
        position_age_minutes = None
        if entry_time_str:
            try:
                entry_dt = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                now = datetime.now(entry_dt.tzinfo)
                position_age_minutes = (now - entry_dt).total_seconds() / 60
                cooldown = CASH_OUT_CONFIG.get('cooldown_minutes', 60)

                if position_age_minutes < cooldown:
                    return {
                        'action': 'HOLD',
                        'reason': f"Cooldown: position is {position_age_minutes:.0f}min old (need {cooldown}min)",
                        'trigger': None,
                        'ticker': ticker,
                        'entry_price': entry_price,
                        'current_quantity': current_quantity,
                    }
            except Exception:
                pass  # Can't parse time, skip cooldown check

        # Get current market price for the side we own
        current_price = self.get_current_market_price(ticker, side)
        if current_price is None:
            return {'action': 'HOLD', 'reason': 'Could not get current price', 'ticker': ticker}

        # Calculate P&L percentage
        pnl_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0

        # Get hours to expiry
        hours_to_expiry = self.get_hours_to_expiry(ticker)

        # Recalculate model probability
        current_model_prob = self.recalculate_model_prob(ticker, side)
        current_market_prob = current_price / 100.0

        # Calculate current spread (edge)
        spread = abs(current_model_prob - current_market_prob) if current_model_prob else None

        # Determine price zone
        deep_itm = current_price >= CASH_OUT_CONFIG['deep_itm_threshold']
        otm = current_price <= CASH_OUT_CONFIG['otm_threshold']
        atm = not deep_itm and not otm

        zone = 'DEEP_ITM' if deep_itm else ('OTM' if otm else 'ATM')

        # Build analytics
        analytics = {
            'ticker': ticker,
            'entry_price': entry_price,
            'current_price': current_price,
            'pnl_pct': round(pnl_pct * 100, 2),
            'pnl_dollars': round((current_price - entry_price) * current_quantity / 100, 2),
            'current_quantity': current_quantity,
            'hours_to_expiry': round(hours_to_expiry, 2) if hours_to_expiry is not None else None,
            'current_model_prob': round(current_model_prob * 100, 1) if current_model_prob else None,
            'current_market_prob': round(current_market_prob * 100, 1),
            'spread': round(spread * 100, 2) if spread else None,
            'tier1_sold': position['tier1_sold'],
            'tier2_sold': position['tier2_sold'],
            'price_zone': zone,
        }

        # =================================================================
        # PRIORITY 1: STOP LOSS (all zones)
        # =================================================================
        if pnl_pct <= CASH_OUT_CONFIG['stop_loss_pct']:
            return {
                'action': 'SELL',
                'pct': 1.0,
                'quantity': current_quantity,
                'reason': f"Stop loss ({pnl_pct*100:.1f}% loss)",
                'trigger': 'stop_loss',
                **analytics
            }

        # =================================================================
        # PRIORITY 2: NEAR-EXPIRY SMART LOGIC
        # =================================================================
        if hours_to_expiry is not None and hours_to_expiry < CASH_OUT_CONFIG['urgent_exit_hours']:
            # < 1 hour to expiry - make smart decision

            # If price > 60¢, likely to settle at $1 - HOLD and let it settle
            if current_price >= CASH_OUT_CONFIG['near_expiry_itm_hold']:
                return {
                    'action': 'HOLD',
                    'reason': f"Near expiry BUT in-the-money ({current_price}¢ > {CASH_OUT_CONFIG['near_expiry_itm_hold']}¢) - let it settle at $1",
                    'trigger': None,
                    **analytics
                }

            # If price < 40¢, theta is crushing - EXIT
            if current_price <= CASH_OUT_CONFIG['near_expiry_otm_exit']:
                return {
                    'action': 'SELL',
                    'pct': 1.0,
                    'quantity': current_quantity,
                    'reason': f"Near expiry AND out-of-money ({current_price}¢ < {CASH_OUT_CONFIG['near_expiry_otm_exit']}¢) - theta death",
                    'trigger': 'theta_urgent_otm',
                    **analytics
                }

        # =================================================================
        # PRIORITY 3: SPREAD COLLAPSE (edge gone)
        # =================================================================
        if spread is not None and spread < CASH_OUT_CONFIG['spread_collapse_threshold']:
            # Exception: Don't exit deep ITM on spread collapse - let it ride to $1
            # Exception: Don't exit if currently profitable - edge captured, let it run
            if not deep_itm and pnl_pct <= 0:
                return {
                    'action': 'SELL',
                    'pct': 1.0,
                    'quantity': current_quantity,
                    'reason': f"Spread collapsed ({spread*100:.1f}% < {CASH_OUT_CONFIG['spread_collapse_threshold']*100}% edge) and not profitable",
                    'trigger': 'spread_collapse',
                    **analytics
                }

        # =================================================================
        # PRIORITY 4: ZONE-SPECIFIC PROFIT TAKING
        # =================================================================

        # -----------------------------------------------------------------
        # DEEP IN THE MONEY (price > 70¢) - LET IT RIDE TO $1
        # -----------------------------------------------------------------
        if deep_itm:
            # Don't take profits on high-probability winners
            # Expected value of holding to $1 > selling now
            # Only sell if basically at $1 already
            if pnl_pct >= CASH_OUT_CONFIG['ditm_min_profit_to_sell']:
                return {
                    'action': 'SELL',
                    'pct': 1.0,
                    'quantity': current_quantity,
                    'reason': f"Deep ITM at {current_price}¢ with +{pnl_pct*100:.0f}% - taking guaranteed profit",
                    'trigger': 'ditm_lock_profit',
                    **analytics
                }
            # Otherwise HOLD - let it settle at $1
            return {
                'action': 'HOLD',
                'reason': f"Deep ITM ({current_price}¢) - holding for $1 payout (current P&L: +{pnl_pct*100:.1f}%)",
                'trigger': None,
                **analytics
            }

        # -----------------------------------------------------------------
        # OUT OF THE MONEY (price < 30¢) - AGGRESSIVE profit taking
        # -----------------------------------------------------------------
        if otm:
            tier1_pct = CASH_OUT_CONFIG['otm_tier1_profit_pct']
            tier2_pct = CASH_OUT_CONFIG['otm_tier2_profit_pct']
            tier3_pct = CASH_OUT_CONFIG['otm_tier3_profit_pct']
            tier1_sell = CASH_OUT_CONFIG['otm_tier1_sell_pct']
            tier2_sell = CASH_OUT_CONFIG['otm_tier2_sell_pct']

            if pnl_pct >= tier3_pct and not position['tier3_sold']:
                return {
                    'action': 'SELL',
                    'pct': 1.0,
                    'quantity': current_quantity,
                    'reason': f"OTM Tier 3: +{pnl_pct*100:.0f}% on long-shot - taking all profits",
                    'trigger': 'otm_tier3_profit',
                    **analytics
                }

            if pnl_pct >= tier2_pct and not position['tier2_sold']:
                sell_qty = max(1, int(position['original_quantity'] * tier2_sell))
                sell_qty = min(sell_qty, current_quantity)
                return {
                    'action': 'SELL',
                    'pct': tier2_sell,
                    'quantity': sell_qty,
                    'reason': f"OTM Tier 2: +{pnl_pct*100:.0f}% - selling {tier2_sell*100:.0f}%",
                    'trigger': 'otm_tier2_profit',
                    **analytics
                }

            if pnl_pct >= tier1_pct and not position['tier1_sold']:
                sell_qty = max(1, int(position['original_quantity'] * tier1_sell))
                sell_qty = min(sell_qty, current_quantity)
                return {
                    'action': 'SELL',
                    'pct': tier1_sell,
                    'quantity': sell_qty,
                    'reason': f"OTM Tier 1: +{pnl_pct*100:.0f}% on long-shot - locking in gains",
                    'trigger': 'otm_tier1_profit',
                    **analytics
                }

        # -----------------------------------------------------------------
        # AT THE MONEY (30-70¢) - NORMAL profit taking
        # -----------------------------------------------------------------
        if atm:
            tier1_pct = CASH_OUT_CONFIG['atm_tier1_profit_pct']
            tier2_pct = CASH_OUT_CONFIG['atm_tier2_profit_pct']
            tier3_pct = CASH_OUT_CONFIG['atm_tier3_profit_pct']
            tier1_sell = CASH_OUT_CONFIG['atm_tier1_sell_pct']
            tier2_sell = CASH_OUT_CONFIG['atm_tier2_sell_pct']

            if pnl_pct >= tier3_pct and not position['tier3_sold']:
                return {
                    'action': 'SELL',
                    'pct': 1.0,
                    'quantity': current_quantity,
                    'reason': f"ATM Tier 3: +{pnl_pct*100:.0f}% - taking remaining profits",
                    'trigger': 'atm_tier3_profit',
                    **analytics
                }

            if pnl_pct >= tier2_pct and not position['tier2_sold']:
                sell_qty = max(1, int(position['original_quantity'] * tier2_sell))
                sell_qty = min(sell_qty, current_quantity)
                return {
                    'action': 'SELL',
                    'pct': tier2_sell,
                    'quantity': sell_qty,
                    'reason': f"ATM Tier 2: +{pnl_pct*100:.0f}% - selling {tier2_sell*100:.0f}%",
                    'trigger': 'atm_tier2_profit',
                    **analytics
                }

            if pnl_pct >= tier1_pct and not position['tier1_sold']:
                sell_qty = max(1, int(position['original_quantity'] * tier1_sell))
                sell_qty = min(sell_qty, current_quantity)
                return {
                    'action': 'SELL',
                    'pct': tier1_sell,
                    'quantity': sell_qty,
                    'reason': f"ATM Tier 1: +{pnl_pct*100:.0f}% - locking in gains",
                    'trigger': 'atm_tier1_profit',
                    **analytics
                }

        # =================================================================
        # NO TRIGGER MET - HOLD
        # =================================================================
        return {
            'action': 'HOLD',
            'reason': f'{zone} position, no exit trigger met',
            'trigger': None,
            **analytics
        }

    def execute_cash_out(self, ticker: str, quantity: int, trigger: str, dry_run: bool = True) -> Dict:
        """
        Execute a cash-out (sell) order.

        Args:
            ticker: Market ticker to sell
            quantity: Number of contracts to sell
            trigger: The trigger that caused this cash-out
            dry_run: If True, simulate without placing real order

        Returns:
            Dict with execution results
        """
        tracker = self._load_position_tracker()

        if ticker not in tracker:
            return {'success': False, 'message': 'Position not tracked'}

        position = tracker[ticker]
        side = position.get('side', 'yes')
        current_price = self.get_current_market_price(ticker, side)

        if current_price is None:
            return {'success': False, 'message': 'Could not get current market price'}

        if dry_run:
            logger.info(f"[DRY RUN] Would sell {quantity}x {ticker} @ {current_price}¢ (trigger: {trigger})")
            return {
                'success': True,
                'dry_run': True,
                'ticker': ticker,
                'quantity': quantity,
                'price': current_price,
                'trigger': trigger,
                'message': f'[DRY RUN] Would sell {quantity} contracts'
            }

        # Execute real sell order
        if not self.kalshi_engine:
            return {'success': False, 'message': 'Kalshi engine not initialized'}

        try:
            side = position.get('side', 'yes')
            sell_price = int(current_price)

            logger.info(f"Executing cash-out: SELL {quantity}x {ticker} ({side}) @ {sell_price}¢ | Trigger: {trigger}")

            # Place sell order
            order_result = self.kalshi_engine.place_order(
                ticker=ticker,
                side=side,
                quantity=quantity,
                price=sell_price,
                action='sell',
                order_type='limit'  # Use limit order at current bid
            )

            if order_result and order_result.get('order_id'):
                # Update position tracker
                entry_price = position['entry_price']
                pnl = (current_price - entry_price) * quantity / 100.0

                position['current_quantity'] -= quantity
                position['total_sold'] += quantity
                position['realized_pnl'] += pnl

                # Mark tier as sold
                if trigger == 'tier1_profit':
                    position['tier1_sold'] = True
                elif trigger == 'tier2_profit':
                    position['tier2_sold'] = True
                elif trigger == 'tier3_profit':
                    position['tier3_sold'] = True

                # Add to cash-out history
                position['cash_out_history'].append({
                    'time': datetime.utcnow().isoformat() + 'Z',
                    'quantity': quantity,
                    'price': current_price,
                    'trigger': trigger,
                    'pnl': pnl,
                    'order_id': order_result.get('order_id')
                })

                # Remove position if fully closed
                if position['current_quantity'] <= 0:
                    del tracker[ticker]
                    logger.info(f"Position fully closed: {ticker}")
                else:
                    tracker[ticker] = position

                self._save_position_tracker(tracker)

                logger.info(f"Cash-out executed: {ticker} | Sold {quantity} @ {current_price}¢ | P&L: ${pnl:.2f} | Order: {order_result.get('order_id')}")

                return {
                    'success': True,
                    'ticker': ticker,
                    'quantity': quantity,
                    'price': current_price,
                    'trigger': trigger,
                    'pnl': pnl,
                    'order_id': order_result.get('order_id'),
                    'remaining_quantity': position.get('current_quantity', 0),
                    'message': f'Sold {quantity} contracts @ {current_price}¢ (P&L: ${pnl:.2f})'
                }
            else:
                logger.error(f"Cash-out order failed for {ticker}: {order_result}")
                return {
                    'success': False,
                    'message': f"Order failed - no order_id returned"
                }

        except Exception as e:
            logger.error(f"Error executing cash-out for {ticker}: {e}", exc_info=True)
            return {'success': False, 'message': str(e)}

    def monitor_all_positions(self, dry_run: bool = True) -> Dict:
        """
        Monitor all tracked positions and check for cash-out opportunities.

        Args:
            dry_run: If True, don't execute actual sells

        Returns:
            Dict with monitoring results and any triggered cash-outs
        """
        tracker = self._load_position_tracker()

        results = {
            'positions_checked': 0,
            'cash_outs_triggered': 0,
            'cash_outs_executed': 0,
            'total_realized_pnl': 0.0,
            'positions': [],
            'actions_taken': []
        }

        for ticker, position in list(tracker.items()):
            results['positions_checked'] += 1

            # Check if cash-out should be triggered
            check_result = self.check_cash_out(ticker)
            results['positions'].append(check_result)

            if check_result['action'] == 'SELL':
                results['cash_outs_triggered'] += 1

                # Execute the cash-out
                exec_result = self.execute_cash_out(
                    ticker=ticker,
                    quantity=check_result['quantity'],
                    trigger=check_result.get('trigger', 'manual'),
                    dry_run=dry_run
                )

                results['actions_taken'].append({
                    'ticker': ticker,
                    'trigger': check_result.get('trigger'),
                    'reason': check_result.get('reason'),
                    'quantity': check_result.get('quantity'),
                    'execution': exec_result
                })

                if exec_result.get('success'):
                    results['cash_outs_executed'] += 1
                    results['total_realized_pnl'] += exec_result.get('pnl', 0)

        results['message'] = (
            f"Checked {results['positions_checked']} positions, "
            f"{results['cash_outs_triggered']} triggers, "
            f"{results['cash_outs_executed']} executed"
        )

        return results

    def get_position_summary(self) -> Dict:
        """Get summary of all tracked positions with current status and cash-out signals."""
        tracker = self._load_position_tracker()

        positions = []
        total_unrealized_pnl = 0.0
        total_realized_pnl = 0.0
        skipped_long_dated = 0

        for ticker, position in tracker.items():
            # Skip yearly/long-dated contracts (e.g., KXBTCMAXY-26DEC31-199999.99)
            # These shouldn't be in active cash-out monitoring
            if 'MAXY' in ticker or 'MINY' in ticker or 'MAX' in ticker.split('-')[0]:
                skipped_long_dated += 1
                continue

            side = position.get('side', 'yes')
            current_price = self.get_current_market_price(ticker, side)
            entry_price = position['entry_price']
            current_qty = position['current_quantity']

            # Skip positions with no current price (likely settled/closed markets)
            if current_price is None:
                logger.warning(f"Skipping {ticker} ({side}) - no current price (market may be settled)")
                continue

            if current_price and entry_price:
                unrealized_pnl = (current_price - entry_price) * current_qty / 100.0
                pnl_pct = (current_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
            else:
                unrealized_pnl = 0
                pnl_pct = 0

            total_unrealized_pnl += unrealized_pnl
            total_realized_pnl += position.get('realized_pnl', 0)

            # Get cash-out signal for this position
            cash_out_result = self.check_cash_out(ticker)

            # Determine price zone
            price_zone = 'unknown'
            if current_price:
                if current_price >= CASH_OUT_CONFIG['deep_itm_threshold']:
                    price_zone = 'DEEP_ITM'
                elif current_price <= CASH_OUT_CONFIG['otm_threshold']:
                    price_zone = 'OTM'
                else:
                    price_zone = 'ATM'

            # Get expiry info
            hours_to_expiry = self.get_hours_to_expiry(ticker)

            # Parse expiry date from ticker for display (e.g., "26JAN2217" -> "Jan 22 5PM")
            expiry_display = None
            try:
                parts = ticker.split('-')
                if len(parts) >= 2:
                    date_part = parts[1]  # e.g., "26JAN2217"
                    if len(date_part) >= 9:
                        month_str = date_part[2:5].upper()  # JAN
                        day = int(date_part[5:7])  # 22
                        hour = int(date_part[7:9])  # 17
                        hour_display = f"{hour % 12 or 12}{'PM' if hour >= 12 else 'AM'}"
                        expiry_display = f"{month_str.title()} {day} {hour_display}"
            except:
                pass

            # Determine "what needs to happen" for this position to profit
            what_needs_to_happen = ''
            try:
                parts = ticker.split('-')
                strike_part = parts[2] if len(parts) >= 3 else ''
                contract_type = strike_part[0] if strike_part else ''  # B or T
                strike_val = float(strike_part[1:]) if len(strike_part) > 1 else 0

                btc_price = self.get_btc_spot_price() or 0
                distance = abs(btc_price - strike_val)

                if contract_type == 'B':
                    # B (Below) contract: YES = BTC < strike, NO = BTC >= strike
                    if side.lower() == 'yes':
                        what_needs_to_happen = f"BTC falls below ${strike_val:,.0f}"
                    else:
                        what_needs_to_happen = f"BTC stays above ${strike_val:,.0f}"
                elif contract_type == 'T':
                    # T (Above) contract: YES = BTC > strike, NO = BTC <= strike
                    if side.lower() == 'yes':
                        what_needs_to_happen = f"BTC rises above ${strike_val:,.0f}"
                    else:
                        what_needs_to_happen = f"BTC stays below ${strike_val:,.0f}"

                if btc_price and strike_val:
                    what_needs_to_happen += f" (${distance:,.0f} away)"
            except Exception:
                pass

            positions.append({
                'ticker': ticker,
                'entry_price': entry_price,
                'current_price': current_price,
                'current_quantity': current_qty,
                'original_quantity': position['original_quantity'],
                'unrealized_pnl': round(unrealized_pnl, 2),
                'realized_pnl': round(position.get('realized_pnl', 0), 2),
                'pnl_pct': round(pnl_pct, 2),
                'tier1_sold': position.get('tier1_sold', False),
                'tier2_sold': position.get('tier2_sold', False),
                'entry_time': position.get('entry_time'),
                'side': position.get('side', 'yes'),
                'price_zone': price_zone,
                'hours_to_expiry': round(hours_to_expiry, 1) if hours_to_expiry else None,
                'expiry_display': expiry_display,
                'what_needs_to_happen': what_needs_to_happen,
                'cash_out_signal': cash_out_result.get('action', 'HOLD'),
                'cash_out_reason': cash_out_result.get('reason', ''),
                'cash_out_pct': cash_out_result.get('pct', 0)
            })

        # Sort by P&L % descending
        positions.sort(key=lambda x: x['pnl_pct'], reverse=True)

        return {
            'positions': positions,
            'total_positions': len(positions),
            'total_unrealized_pnl': round(total_unrealized_pnl, 2),
            'total_realized_pnl': round(total_realized_pnl, 2),
            'total_pnl': round(total_unrealized_pnl + total_realized_pnl, 2)
        }

    def get_hedge_status(self) -> Dict:
        """
        Get current hedge status including positions and coverage.

        Returns:
            Dict with current hedge status
        """
        # Get portfolio
        portfolio = self.get_btc_portfolio()

        # Get active Kalshi positions
        active_positions = []
        if self.kalshi_engine:
            try:
                positions_list = self.kalshi_engine.get_positions()
                # get_positions() returns a list directly
                if positions_list and isinstance(positions_list, list):
                    # Filter for BTC-related positions
                    for pos in positions_list:
                        ticker = pos.get('ticker', '')
                        if 'BTC' in ticker.upper():
                            active_positions.append(pos)
            except Exception as e:
                logger.error(f"Error getting positions: {e}")

        # Calculate current coverage if we have positions
        current_coverage = {}
        if active_positions and portfolio['success'] and portfolio['btc_balance'] > 0:
            try:
                btc_price = portfolio['btc_price']
                btc_balance = portfolio['btc_balance']

                # Calculate coverage at various drawdown levels
                drawdowns = [-0.05, -0.10, -0.15, -0.20, -0.30, -0.40]
                for dd in drawdowns:
                    scenario_price = btc_price * (1 + dd)
                    loss = max(0, btc_price - scenario_price) * btc_balance

                    # Calculate payout from current positions
                    payout = 0
                    for pos in active_positions:
                        strike = pos.get('strike')
                        quantity = pos.get('position', 0)
                        if strike and scenario_price < strike:
                            payout += quantity  # Each contract pays $1

                    coverage = (payout / loss) if loss > 0 else 0
                    current_coverage[f"{dd*100:.0f}%"] = coverage

            except Exception as e:
                logger.error(f"Error calculating coverage: {e}")

        return {
            'success': True,
            'portfolio': portfolio,
            'active_positions': active_positions,
            'num_positions': len(active_positions),
            'current_coverage': current_coverage,
            'last_optimization': self.last_optimization,
            'timestamp': datetime.now().isoformat()
        }

    # ========================================================================
    # PERPETUALS DELTA HEDGING METHODS
    # ========================================================================

    def get_perp_positions(self) -> Dict:
        """
        Get current perpetual futures positions from Coinbase.

        Returns:
            Dict with positions list and summary
        """
        # Use derivatives client for perpetual futures
        client = self.coinbase_derivatives_client or self.coinbase_client

        if not client:
            return {'success': False, 'message': 'Coinbase client not initialized', 'positions': []}

        try:
            # Get futures positions
            positions_response = client.list_futures_positions()
            positions = []

            if positions_response and hasattr(positions_response, 'positions'):
                for pos in positions_response.positions:
                    positions.append({
                        'product_id': pos.product_id if hasattr(pos, 'product_id') else None,
                        'side': pos.side if hasattr(pos, 'side') else None,
                        'number_of_contracts': float(pos.number_of_contracts) if hasattr(pos, 'number_of_contracts') else 0,
                        'entry_price': float(pos.entry_vwap.value) if hasattr(pos, 'entry_vwap') and hasattr(pos.entry_vwap, 'value') else 0,
                        'mark_price': float(pos.mark_price.value) if hasattr(pos, 'mark_price') and hasattr(pos.mark_price, 'value') else 0,
                        'unrealized_pnl': float(pos.unrealized_pnl.value) if hasattr(pos, 'unrealized_pnl') and hasattr(pos.unrealized_pnl, 'value') else 0,
                    })

            logger.info(f"Found {len(positions)} perpetual positions")

            return {
                'success': True,
                'positions': positions,
                'num_positions': len(positions)
            }

        except Exception as e:
            logger.error(f"Error getting perp positions: {e}")
            return {'success': False, 'message': str(e), 'positions': []}

    def place_perp_order(self,
                        product_id: str,
                        side: str,
                        size: float,
                        order_type: str = 'market',
                        limit_price: float = None,
                        stop_price: float = None) -> Dict:
        """
        Place a perpetual futures order on Coinbase.

        Args:
            product_id: Product ID (e.g., 'BTC-PERP-INTX')
            side: 'buy' or 'sell'
            size: Contract size (in BTC)
            order_type: 'market', 'limit', or 'stop_limit'
            limit_price: Limit price (for limit/stop_limit orders)
            stop_price: Stop trigger price (for stop_limit orders)

        Returns:
            Dict with order result
        """
        # Use derivatives client for perpetual futures
        client = self.coinbase_derivatives_client or self.coinbase_client

        if not client:
            return {'success': False, 'message': 'Coinbase derivatives client not initialized'}

        if not self.coinbase_derivatives_client:
            logger.warning("Using spot client for derivatives - this may fail. Please set COINBASE_DERIVATIVES_API_KEY and COINBASE_DERIVATIVES_API_SECRET")

        try:
            # Build order configuration
            order_config = {
                'product_id': product_id,
                'side': side.upper(),
                'client_order_id': f"hedge_{datetime.now().timestamp()}"
            }

            if order_type == 'market':
                order_config['order_configuration'] = {
                    'market_market_ioc': {
                        'base_size': str(size)
                    }
                }
            elif order_type == 'limit':
                if not limit_price:
                    return {'success': False, 'message': 'limit_price required for limit orders'}
                order_config['order_configuration'] = {
                    'limit_limit_gtc': {
                        'base_size': str(size),
                        'limit_price': str(limit_price),
                        'post_only': False
                    }
                }
            elif order_type == 'stop_limit':
                if not stop_price or not limit_price:
                    return {'success': False, 'message': 'stop_price and limit_price required for stop_limit orders'}
                order_config['order_configuration'] = {
                    'stop_limit_stop_limit_gtc': {
                        'base_size': str(size),
                        'limit_price': str(limit_price),
                        'stop_price': str(stop_price),
                        'stop_direction': 'STOP_DIRECTION_STOP_UP' if side.lower() == 'buy' else 'STOP_DIRECTION_STOP_DOWN'
                    }
                }

            # Place order via Coinbase derivatives client
            logger.info(f"Placing {order_type} {side} order: {size} {product_id}")
            logger.info(f"Using {'derivatives' if self.coinbase_derivatives_client else 'spot'} client")
            result = client.create_order(**order_config)

            if result and hasattr(result, 'success') and result.success:
                order_id = result.order_id if hasattr(result, 'order_id') else None
                logger.info(f"Order placed successfully: {order_id}")
                return {
                    'success': True,
                    'order_id': order_id,
                    'message': f'{order_type} order placed'
                }
            else:
                error_msg = result.error_response.message if hasattr(result, 'error_response') else 'Unknown error'
                return {'success': False, 'message': error_msg}

        except Exception as e:
            logger.error(f"Error placing perp order: {e}")
            return {'success': False, 'message': str(e)}

    def calculate_total_delta(self) -> Dict:
        """
        Calculate total BTC delta exposure across spot + perps + Kalshi positions.

        Returns:
            Dict with delta breakdown
        """
        try:
            # Get spot BTC holdings
            portfolio = self.get_btc_portfolio()
            spot_btc = portfolio.get('btc_balance', 0) if portfolio.get('success') else 0

            # Get perpetual positions
            perp_positions = self.get_perp_positions()
            perp_delta = 0
            if perp_positions.get('success'):
                for pos in perp_positions.get('positions', []):
                    contracts = pos.get('number_of_contracts', 0)
                    side = pos.get('side', '')
                    # Long = positive delta, Short = negative delta
                    if side == 'LONG':
                        perp_delta += contracts
                    elif side == 'SHORT':
                        perp_delta -= contracts

            # Kalshi positions have negligible delta (binary options)
            kalshi_delta = 0

            total_delta = spot_btc + perp_delta + kalshi_delta
            delta_pct = (total_delta / spot_btc * 100) if spot_btc > 0 else 0

            logger.info(f"Delta: Spot={spot_btc:.4f}, Perp={perp_delta:.4f}, Total={total_delta:.4f} ({delta_pct:.1f}%)")

            return {
                'success': True,
                'spot_btc': spot_btc,
                'perp_delta': perp_delta,
                'kalshi_delta': kalshi_delta,
                'total_delta': total_delta,
                'delta_pct': delta_pct,
                'target_delta_min': 0.80,  # 80% target
                'target_delta_max': 1.00,  # 100% target
                'needs_rebalance': delta_pct < 80 or delta_pct > 100
            }

        except Exception as e:
            logger.error(f"Error calculating delta: {e}")
            return {'success': False, 'message': str(e)}

    def auto_hedge_delta(self,
                        target_delta_pct: float = 0.90,
                        product_id: str = 'BTC-PERP-INTX',
                        dry_run: bool = True) -> Dict:
        """
        Automatically hedge BTC delta to target percentage using perpetuals.

        Args:
            target_delta_pct: Target delta as % of spot holdings (e.g., 0.90 for 90%)
            product_id: Perpetual product to trade
            dry_run: If True, simulate without placing real orders

        Returns:
            Dict with hedge execution results
        """
        try:
            # Calculate current delta
            delta_info = self.calculate_total_delta()
            if not delta_info.get('success'):
                return delta_info

            spot_btc = delta_info['spot_btc']
            current_delta = delta_info['total_delta']
            current_delta_pct = delta_info['delta_pct'] / 100

            if spot_btc == 0:
                return {'success': False, 'message': 'No BTC to hedge'}

            # Calculate target delta and required adjustment
            target_delta = spot_btc * target_delta_pct
            delta_adjustment = target_delta - current_delta

            logger.info(f"Auto-hedge: Current={current_delta:.4f} BTC, Target={target_delta:.4f} BTC, Adjustment={delta_adjustment:.4f} BTC")

            # Determine if rebalancing is needed (threshold: 5%)
            if abs(delta_adjustment) < spot_btc * 0.05:
                return {
                    'success': True,
                    'message': 'Delta within acceptable range, no rebalancing needed',
                    'delta_adjustment': delta_adjustment,
                    'action': 'none'
                }

            # Determine order side and size
            if delta_adjustment < 0:
                # Need to reduce delta → Short perps
                side = 'sell'
                size = abs(delta_adjustment)
                action = f'Short {size:.4f} BTC perps'
            else:
                # Need to increase delta → Long perps (close shorts or go long)
                side = 'buy'
                size = abs(delta_adjustment)
                action = f'Buy {size:.4f} BTC perps'

            if dry_run:
                logger.info(f"[DRY RUN] Would {action}")
                return {
                    'success': True,
                    'message': f'[DRY RUN] Would {action}',
                    'delta_adjustment': delta_adjustment,
                    'side': side,
                    'size': size,
                    'action': action,
                    'dry_run': True
                }

            # Execute real order
            order_result = self.place_perp_order(
                product_id=product_id,
                side=side,
                size=size,
                order_type='market'
            )

            if order_result.get('success'):
                return {
                    'success': True,
                    'message': f'Delta hedge executed: {action}',
                    'delta_adjustment': delta_adjustment,
                    'side': side,
                    'size': size,
                    'order_id': order_result.get('order_id'),
                    'action': action
                }
            else:
                return {
                    'success': False,
                    'message': f'Failed to execute hedge: {order_result.get("message")}',
                    'delta_adjustment': delta_adjustment
                }

        except Exception as e:
            logger.error(f"Error in auto_hedge_delta: {e}")
            return {'success': False, 'message': str(e)}

    # ========================================================================
    # COMBINED HEDGING SIMULATION
    # ========================================================================

    def simulate_combined_hedge(self,
                               perp_delta_target_pct: float = 0.90,
                               kalshi_budget_pct: float = 0.02,
                               kalshi_coverage_target: float = 0.68) -> Dict:
        """
        Simulate combined hedging strategy using both Perpetuals and Kalshi options.

        This shows how the portfolio performs across different BTC price scenarios
        with both delta hedging (perpetuals) and tail protection (Kalshi binary options).

        Args:
            perp_delta_target_pct: Target delta % for perpetuals (e.g., 0.90 for 90%)
            kalshi_budget_pct: Monthly budget for Kalshi as % of notional (e.g., 0.02 for 2%)
            kalshi_coverage_target: Target coverage at -20% drawdown (e.g., 0.68 for 68 cents/$)

        Returns:
            Dict with simulation results including scenarios and P&L breakdown
        """
        try:
            # Get current portfolio
            portfolio = self.get_btc_portfolio()
            if not portfolio.get('success') or portfolio['btc_balance'] == 0:
                return {'success': False, 'message': 'No BTC portfolio to simulate'}

            btc_balance = portfolio['btc_balance']
            current_price = portfolio['btc_price']
            notional_value = portfolio['notional_value']

            # Get current perp positions
            perp_positions = self.get_perp_positions()
            current_perp_delta = 0.0
            perp_entry_price = current_price  # Default to current price

            if perp_positions.get('success') and perp_positions.get('positions'):
                for pos in perp_positions['positions']:
                    contracts = float(pos.get('number_of_contracts', 0))
                    side = pos.get('side', 'LONG')
                    delta_contribution = contracts if side == 'LONG' else -contracts
                    current_perp_delta += delta_contribution
                    if abs(delta_contribution) > 0:
                        perp_entry_price = float(pos.get('entry_price', current_price))

            # Get current Kalshi positions
            kalshi_positions = []
            if self.kalshi_engine:
                try:
                    positions_list = self.kalshi_engine.get_positions()
                    if positions_list and isinstance(positions_list, list):
                        for pos in positions_list:
                            ticker = pos.get('ticker', '')
                            if 'BTC' in ticker.upper():
                                kalshi_positions.append({
                                    'strike': pos.get('strike', 0),
                                    'contracts': pos.get('position', 0),
                                    'side': pos.get('side', 'yes'),
                                    'ticker': ticker
                                })
                except Exception as e:
                    logger.warning(f"Could not fetch Kalshi positions: {e}")

            # Simulate target positions if none exist
            target_perp_delta = btc_balance * perp_delta_target_pct - btc_balance
            simulated_perp_delta = target_perp_delta if abs(current_perp_delta) < 0.0001 else current_perp_delta

            # Get available Kalshi markets for simulation
            kalshi_markets = []
            if self.kalshi_engine:
                try:
                    all_markets = self.kalshi_engine.get_markets(category='crypto', limit=100)
                    if all_markets and isinstance(all_markets, list):
                        # Filter for BTC markets
                        for market in all_markets:
                            ticker = market.get('id', '')
                            title = market.get('question', '').upper()
                            subtitle = market.get('subtitle', '').upper()
                            full_text = f"{title} {subtitle}"

                            if 'BTC' in full_text or 'BITCOIN' in full_text:
                                # Try subtitle first, then title
                                strike = self._extract_strike_from_title(subtitle) or self._extract_strike_from_title(title)
                                if strike and strike < current_price * 1.5:  # Only consider relevant strikes
                                    kalshi_markets.append({
                                        'strike': strike,
                                        'yes_price': market.get('yes_price', 50),
                                        'no_price': market.get('no_price', 50),
                                        'is_above': 'ABOVE' in full_text or 'OVER' in full_text or 'OR ABOVE' in full_text
                                    })
                except Exception as e:
                    logger.warning(f"Could not fetch Kalshi markets: {e}")

            # Generate price scenarios (-50% to +30%)
            scenarios = []
            for pct_change in range(-50, 31, 5):  # -50%, -45%, ..., +25%, +30%
                scenario_price = current_price * (1 + pct_change / 100.0)

                # Calculate spot P&L
                spot_pnl = (scenario_price - current_price) * btc_balance

                # Calculate perp P&L (linear with price movement)
                # If we're short (negative delta), we profit when price drops
                perp_pnl = (scenario_price - perp_entry_price) * simulated_perp_delta

                # Calculate Kalshi P&L
                kalshi_pnl = 0.0
                for pos in kalshi_positions:
                    strike = pos['strike']
                    contracts = pos['contracts']
                    side = pos['side']

                    # Determine if option pays out
                    pays_out = scenario_price < strike
                    if pays_out:
                        kalshi_pnl += contracts if side == 'yes' else 0
                    else:
                        kalshi_pnl += contracts if side == 'no' else 0

                # If no existing positions, simulate optimized Kalshi positions
                if not kalshi_positions and kalshi_markets:
                    # Simple simulation: assume we can buy protection at strikes below current price
                    budget = notional_value * kalshi_budget_pct
                    for market in kalshi_markets:
                        if market['strike'] < current_price:
                            # Estimate contracts we could buy
                            price_per_contract = market['yes_price'] / 100.0 if not market['is_above'] else market['no_price'] / 100.0
                            if price_per_contract > 0:
                                estimated_contracts = (budget * 0.3) / price_per_contract  # Spread budget across strikes

                                # Check if this strike pays out in this scenario
                                if scenario_price < market['strike']:
                                    kalshi_pnl += estimated_contracts

                # Total P&L
                total_pnl = spot_pnl + perp_pnl + kalshi_pnl

                # Calculate hedge effectiveness
                if spot_pnl < 0:  # If we're losing on spot
                    hedge_pnl = perp_pnl + kalshi_pnl
                    hedge_effectiveness = (hedge_pnl / abs(spot_pnl)) * 100 if spot_pnl != 0 else 0
                else:
                    hedge_effectiveness = 0

                scenarios.append({
                    'price': scenario_price,
                    'price_change_pct': pct_change,
                    'spot_pnl': spot_pnl,
                    'perp_pnl': perp_pnl,
                    'kalshi_pnl': kalshi_pnl,
                    'total_pnl': total_pnl,
                    'total_pnl_pct': (total_pnl / notional_value) * 100,
                    'hedge_effectiveness': hedge_effectiveness
                })

            # Calculate strategy summary
            max_drawdown_scenario = min(scenarios, key=lambda x: x['total_pnl'])
            max_upside_scenario = max(scenarios, key=lambda x: x['total_pnl'])

            return {
                'success': True,
                'current_price': current_price,
                'btc_balance': btc_balance,
                'notional_value': notional_value,
                'current_perp_delta': current_perp_delta,
                'simulated_perp_delta': simulated_perp_delta,
                'perp_delta_target_pct': perp_delta_target_pct,
                'num_kalshi_positions': len(kalshi_positions),
                'num_kalshi_markets_available': len(kalshi_markets),
                'kalshi_budget_pct': kalshi_budget_pct,
                'scenarios': scenarios,
                'summary': {
                    'max_drawdown': {
                        'price': max_drawdown_scenario['price'],
                        'price_change_pct': max_drawdown_scenario['price_change_pct'],
                        'total_pnl': max_drawdown_scenario['total_pnl'],
                        'total_pnl_pct': max_drawdown_scenario['total_pnl_pct']
                    },
                    'max_upside': {
                        'price': max_upside_scenario['price'],
                        'price_change_pct': max_upside_scenario['price_change_pct'],
                        'total_pnl': max_upside_scenario['total_pnl'],
                        'total_pnl_pct': max_upside_scenario['total_pnl_pct']
                    }
                },
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in simulate_combined_hedge: {e}")
            return {'success': False, 'message': str(e)}

    # ========================================================================
    # DAILY KALSHI DAY TRADING SIMULATION
    # ========================================================================

    def simulate_daily_kalshi_trading(self,
                                     kalshi_budget_pct: float = 0.02,
                                     perp_delta_target_pct: float = 0.90) -> Dict:
        """
        Simulate combined hedging strategy using ONLY Kalshi markets expiring TODAY.

        Strategy:
        1. Filter for Kalshi BTC markets expiring today
        2. Run combined simulation with Coinbase perpetuals + today's Kalshi markets
        3. Show P&L across price scenarios for intraday hedging

        Args:
            kalshi_budget_pct: Budget for Kalshi as % of notional (default: 2%)
            perp_delta_target_pct: Target delta exposure with perps (default: 90% = 10% hedge)

        Returns:
            Dict with combined simulation results including scenarios and P&L breakdown
        """
        try:
            # Get current portfolio
            portfolio = self.get_btc_portfolio()
            if not portfolio.get('success'):
                return {'success': False, 'message': 'Could not fetch portfolio'}

            current_price = portfolio['btc_price']
            btc_balance = portfolio['btc_balance']
            notional_value = current_price * btc_balance

            # Get current perp positions
            current_perp_delta = 0.0
            perp_entry_price = current_price
            try:
                perp_positions = self.get_perp_positions()
                if perp_positions.get('success') and perp_positions.get('positions'):
                    for pos in perp_positions['positions']:
                        contracts = float(pos.get('number_of_contracts', 0))
                        side = pos.get('side', 'LONG')
                        delta_contribution = contracts if side == 'LONG' else -contracts
                        current_perp_delta += delta_contribution
                        if abs(delta_contribution) > 0:
                            perp_entry_price = float(pos.get('entry_price', current_price))
            except Exception as e:
                logger.warning(f"Could not fetch perp positions: {e}")

            # Get all Kalshi crypto markets (increase limit to find more BTC markets)
            all_markets = []
            if self.kalshi_engine:
                try:
                    # Get up to 1000 markets to ensure we capture all BTC markets
                    all_markets = self.kalshi_engine.get_markets(category='crypto', limit=1000)
                    logger.info(f"Fetched {len(all_markets)} total crypto markets from Kalshi")
                except Exception as e:
                    logger.warning(f"Could not fetch Kalshi markets: {e}")

            if not all_markets:
                return {
                    'success': False,
                    'message': 'No Kalshi markets available'
                }

            # Filter for BTC markets expiring TODAY
            from datetime import datetime, timedelta
            import pytz

            # Get current time in UTC
            now_utc = datetime.now(pytz.UTC)
            today_utc = now_utc.date()
            tomorrow_utc = today_utc + timedelta(days=1)

            daily_markets = []
            btc_markets_checked = 0
            for market in all_markets:
                title = market.get('question', '').upper()
                subtitle = market.get('subtitle', '').upper()
                full_text = f"{title} {subtitle}"

                # Check if it's a BTC market
                if 'BTC' not in full_text and 'BITCOIN' not in full_text:
                    continue

                btc_markets_checked += 1

                # Check if it expires today
                close_date = market.get('close_date')
                if close_date:
                    try:
                        # Parse close date (already in UTC)
                        close_dt = datetime.fromisoformat(close_date.replace('Z', '+00:00'))
                        market_date_utc = close_dt.date()

                        # Calculate hours until expiry
                        hours_until = (close_dt - now_utc).total_seconds() / 3600

                        logger.info(f"BTC market: {subtitle[:50]} | Closes: {close_dt} | Hours until: {hours_until:.1f}h")

                        # Accept markets expiring within the next 24 hours
                        # Minimum 2 hours buffer to avoid markets closing soon (Kalshi typically closes trading 1-2h before expiry)
                        if 2 <= hours_until <= 24:
                            # Extract strike
                            strike = self._extract_strike_from_title(subtitle) or self._extract_strike_from_title(title)
                            if strike and strike < current_price * 1.5:  # Only relevant strikes
                                logger.info(f"✓ Added daily market: strike=${strike}, closes in {hours_until:.1f}h")
                                daily_markets.append({
                                    'strike': strike,
                                    'yes_price': market.get('yes_price', 50),
                                    'no_price': market.get('no_price', 50),
                                    'is_above': 'ABOVE' in full_text or 'OVER' in full_text or 'OR ABOVE' in full_text,
                                    'ticker': market.get('id', ''),
                                    'question': market.get('question', ''),
                                    'subtitle': market.get('subtitle', ''),
                                    'close_time': close_dt.isoformat(),
                                    'hours_to_expiry': hours_until
                                })
                            elif not strike:
                                logger.debug(f"Skipped (no strike): {subtitle[:50]}")
                            else:
                                logger.debug(f"Skipped (strike too high): ${strike} > ${current_price * 1.5:.0f}")
                    except Exception as e:
                        logger.warning(f"Error parsing date for {subtitle[:30]}: {e}")
                        continue

            logger.info(f"Checked {btc_markets_checked} BTC markets, found {len(daily_markets)} expiring today")

            if not daily_markets:
                return {
                    'success': False,
                    'message': 'No BTC markets expiring today found',
                    'markets_checked': len(all_markets)
                }

            logger.info(f"Found {len(daily_markets)} BTC markets expiring today for combined simulation")

            # Simulate target perp position if none exists
            target_perp_delta = btc_balance * perp_delta_target_pct - btc_balance
            simulated_perp_delta = target_perp_delta if abs(current_perp_delta) < 0.0001 else current_perp_delta

            # Generate price scenarios (-50% to +30%)
            scenarios = []
            for pct_change in range(-50, 31, 5):  # -50%, -45%, ..., +25%, +30%
                scenario_price = current_price * (1 + pct_change / 100.0)

                # Calculate spot P&L
                spot_pnl = (scenario_price - current_price) * btc_balance

                # Calculate perp P&L (linear with price movement)
                # If we're short (negative delta), we profit when price drops
                perp_pnl = (scenario_price - perp_entry_price) * simulated_perp_delta

                # Calculate Kalshi P&L using TODAY'S markets
                kalshi_pnl = 0.0
                budget = notional_value * kalshi_budget_pct
                for market in daily_markets:
                    if market['strike'] < current_price:
                        # Estimate contracts we could buy for protection
                        price_per_contract = market['yes_price'] / 100.0 if not market['is_above'] else market['no_price'] / 100.0
                        if price_per_contract > 0:
                            estimated_contracts = (budget * 0.3) / price_per_contract  # Spread budget

                            # Check if this strike pays out in this scenario
                            if scenario_price < market['strike']:
                                kalshi_pnl += estimated_contracts

                # Total P&L
                total_pnl = spot_pnl + perp_pnl + kalshi_pnl

                # Calculate hedge effectiveness
                if spot_pnl < 0:  # If we're losing on spot
                    hedge_pnl = perp_pnl + kalshi_pnl
                    hedge_effectiveness = (hedge_pnl / abs(spot_pnl)) * 100 if spot_pnl != 0 else 0
                else:
                    hedge_effectiveness = 0

                scenarios.append({
                    'price': scenario_price,
                    'price_change_pct': pct_change,
                    'spot_pnl': spot_pnl,
                    'perp_pnl': perp_pnl,
                    'kalshi_pnl': kalshi_pnl,
                    'total_pnl': total_pnl,
                    'total_pnl_pct': (total_pnl / notional_value) * 100,
                    'hedge_effectiveness': hedge_effectiveness
                })

            # Calculate strategy summary
            max_drawdown_scenario = min(scenarios, key=lambda x: x['total_pnl'])
            max_upside_scenario = max(scenarios, key=lambda x: x['total_pnl'])

            # Calculate average hours to expiry
            avg_hours_to_expiry = sum(m['hours_to_expiry'] for m in daily_markets) / len(daily_markets) if daily_markets else 0

            return {
                'success': True,
                'current_price': current_price,
                'btc_balance': btc_balance,
                'notional_value': notional_value,
                'current_perp_delta': current_perp_delta,
                'simulated_perp_delta': simulated_perp_delta,
                'perp_delta_target_pct': perp_delta_target_pct,
                'markets_scanned': len(all_markets),
                'markets_expiring_today': len(daily_markets),
                'kalshi_budget_pct': kalshi_budget_pct,
                'kalshi_budget': notional_value * kalshi_budget_pct,
                'avg_hours_to_expiry': avg_hours_to_expiry,
                'daily_markets': daily_markets[:10],  # Return top 10 markets
                'scenarios': scenarios,
                'summary': {
                    'max_drawdown': {
                        'price': max_drawdown_scenario['price'],
                        'price_change_pct': max_drawdown_scenario['price_change_pct'],
                        'total_pnl': max_drawdown_scenario['total_pnl'],
                        'total_pnl_pct': max_drawdown_scenario['total_pnl_pct']
                    },
                    'max_upside': {
                        'price': max_upside_scenario['price'],
                        'price_change_pct': max_upside_scenario['price_change_pct'],
                        'total_pnl': max_upside_scenario['total_pnl'],
                        'total_pnl_pct': max_upside_scenario['total_pnl_pct']
                    }
                },
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in simulate_daily_kalshi_trading: {e}")
            return {'success': False, 'message': str(e)}

    def execute_daily_hedge(self,
                           simulation_result: Dict,
                           dry_run: bool = True,
                           product_id: str = 'BTC-PERP-INTX') -> Dict:
        """
        Execute the daily combined hedge strategy using simulation results.

        This will:
        1. Place Kalshi binary option orders for markets expiring today
        2. Place Coinbase perpetual futures order to achieve target delta
        3. Return execution confirmation with order IDs

        Args:
            simulation_result: Result from simulate_daily_kalshi_trading()
            dry_run: If True, simulate without placing real orders (default: True)
            product_id: Perpetual product to trade (default: 'BTC-PERP-INTX')

        Returns:
            Dict with execution results:
                {
                    'success': bool,
                    'message': str,
                    'kalshi_orders': List[Dict],  # List of Kalshi orders placed
                    'perp_order': Dict,           # Perpetual order details
                    'total_kalshi_cost': float,   # Total cost of Kalshi positions
                    'total_perp_size': float,     # Size of perpetual position
                    'dry_run': bool
                }
        """
        if not simulation_result.get('success'):
            return {
                'success': False,
                'message': 'Cannot execute invalid simulation result',
                'kalshi_orders': [],
                'perp_order': {},
                'dry_run': dry_run
            }

        daily_markets = simulation_result.get('daily_markets', [])
        if not daily_markets:
            return {
                'success': False,
                'message': 'No markets in simulation result',
                'kalshi_orders': [],
                'perp_order': {},
                'dry_run': dry_run
            }

        # Get execution parameters
        kalshi_budget = simulation_result.get('kalshi_budget', 0)
        simulated_perp_delta = simulation_result.get('simulated_perp_delta', 0)
        current_perp_delta = simulation_result.get('current_perp_delta', 0)
        btc_balance = simulation_result.get('btc_balance', 0)
        perp_delta_target_pct = simulation_result.get('perp_delta_target_pct', 0.90)

        logger.info(f"Executing daily hedge: Kalshi budget=${kalshi_budget:.2f}, Perp delta target={perp_delta_target_pct*100:.0f}%")

        # ====================================================================
        # PART 1: Execute Kalshi binary options orders
        # ====================================================================
        kalshi_orders = []
        kalshi_failed = []
        total_kalshi_cost = 0.0

        # Calculate how to distribute the budget across markets
        num_markets = len(daily_markets)
        budget_per_market = kalshi_budget * 0.3  # Use 30% per market as in simulation

        if dry_run:
            logger.info(f"[DRY RUN] Would place {num_markets} Kalshi orders:")
            for market in daily_markets:
                strike = market.get('strike')
                yes_price = market.get('yes_price', 50)
                no_price = market.get('no_price', 50)
                is_above = market.get('is_above', False)

                # Determine side and price
                side = 'no' if is_above else 'yes'
                price = no_price if is_above else yes_price
                price_per_contract = price / 100.0

                # Calculate quantity
                if price_per_contract > 0:
                    quantity = int(budget_per_market / price_per_contract)
                    cost = quantity * price_per_contract

                    logger.info(f"  - {market.get('ticker')}: Buy {side.upper()} x{quantity} @ {price}¢ (strike ${strike}) = ${cost:.2f}")

                    kalshi_orders.append({
                        'ticker': market.get('ticker'),
                        'side': side,
                        'quantity': quantity,
                        'price': price,
                        'strike': strike,
                        'cost': cost,
                        'status': 'dry_run'
                    })
                    total_kalshi_cost += cost
        else:
            # Real execution
            if not self.kalshi_engine:
                return {
                    'success': False,
                    'message': 'Kalshi engine not initialized',
                    'kalshi_orders': [],
                    'perp_order': {},
                    'dry_run': False
                }

            for market in daily_markets:
                try:
                    ticker = market.get('ticker')
                    strike = market.get('strike')
                    yes_price = market.get('yes_price', 50)
                    no_price = market.get('no_price', 50)
                    is_above = market.get('is_above', False)

                    # Determine side and price
                    side = 'no' if is_above else 'yes'
                    price = no_price if is_above else yes_price

                    # Validate price - Kalshi API requires price between 1 and 99 cents
                    # Markets that are closed/expired often have prices of 0 or 100
                    if price < 1 or price > 99:
                        logger.warning(f"Skipping {ticker}: price {price}¢ is outside valid range (1-99). Market likely closed.")
                        kalshi_failed.append({
                            'ticker': ticker,
                            'error': f'Price {price}¢ outside valid range (1-99) - market likely closed'
                        })
                        continue

                    price_per_contract = price / 100.0

                    # Calculate quantity
                    if price_per_contract > 0:
                        quantity = int(budget_per_market / price_per_contract)
                        if quantity == 0:
                            logger.warning(f"Skipping {ticker}: quantity would be 0")
                            continue

                        cost = quantity * price_per_contract

                        logger.info(f"Placing Kalshi order: {ticker} {side.upper()} x{quantity} @ {price}¢")

                        # Place order via Kalshi
                        order_result = self.kalshi_engine.place_order(
                            ticker=ticker,
                            side=side,
                            quantity=quantity,
                            price=int(price)
                        )

                        if order_result and order_result.get('success'):
                            kalshi_orders.append({
                                'ticker': ticker,
                                'side': side,
                                'quantity': quantity,
                                'price': price,
                                'strike': strike,
                                'cost': cost,
                                'order_id': order_result.get('order_id'),
                                'status': 'placed'
                            })
                            total_kalshi_cost += cost
                        else:
                            error_msg = order_result.get('message') if order_result else 'Order failed with no response'
                            kalshi_failed.append({
                                'ticker': ticker,
                                'error': error_msg
                            })

                except Exception as e:
                    logger.error(f"Error placing Kalshi order for {market.get('ticker')}: {e}")
                    kalshi_failed.append({
                        'ticker': market.get('ticker'),
                        'error': str(e)
                    })

        # ====================================================================
        # PART 2: Execute Coinbase perpetual futures order
        # ====================================================================
        perp_order = {}

        # Calculate required perpetual adjustment
        target_delta = btc_balance * perp_delta_target_pct
        delta_adjustment = target_delta - btc_balance - current_perp_delta

        # Determine if we need to open/adjust perp position
        if abs(delta_adjustment) < btc_balance * 0.05:  # Less than 5% adjustment needed
            perp_message = 'No perpetual adjustment needed (within 5% threshold)'
            logger.info(perp_message)
            perp_order = {
                'status': 'skipped',
                'message': perp_message,
                'delta_adjustment': delta_adjustment
            }
        else:
            # Need to adjust perp position
            if delta_adjustment < 0:
                # Need to short more (reduce delta)
                side = 'sell'
                size = abs(delta_adjustment)
                action = f'Short {size:.4f} BTC perps'
            else:
                # Need to go long (increase delta)
                side = 'buy'
                size = abs(delta_adjustment)
                action = f'Buy {size:.4f} BTC perps'

            if dry_run:
                logger.info(f"[DRY RUN] Would {action} on {product_id}")
                perp_order = {
                    'status': 'dry_run',
                    'side': side,
                    'size': size,
                    'product_id': product_id,
                    'action': action,
                    'delta_adjustment': delta_adjustment
                }
            else:
                # Real execution
                logger.info(f"Placing perpetual order: {action} on {product_id}")

                order_result = self.place_perp_order(
                    product_id=product_id,
                    side=side,
                    size=size,
                    order_type='market'
                )

                if order_result.get('success'):
                    perp_order = {
                        'status': 'placed',
                        'side': side,
                        'size': size,
                        'product_id': product_id,
                        'action': action,
                        'delta_adjustment': delta_adjustment,
                        'order_id': order_result.get('order_id')
                    }
                else:
                    perp_order = {
                        'status': 'failed',
                        'side': side,
                        'size': size,
                        'product_id': product_id,
                        'error': order_result.get('message'),
                        'delta_adjustment': delta_adjustment
                    }

        # ====================================================================
        # PART 3: Return execution summary
        # ====================================================================
        success = (len(kalshi_orders) > 0 or perp_order.get('status') in ['placed', 'skipped'])

        message_parts = []
        if dry_run:
            message_parts.append(f"[DRY RUN] Would place {len(kalshi_orders)} Kalshi orders (${total_kalshi_cost:.2f})")
            if perp_order.get('status') == 'dry_run':
                message_parts.append(f"and {perp_order.get('action')}")
        else:
            message_parts.append(f"Placed {len(kalshi_orders)} Kalshi orders (${total_kalshi_cost:.2f})")
            if kalshi_failed:
                message_parts.append(f"{len(kalshi_failed)} Kalshi orders failed")
            if perp_order.get('status') == 'placed':
                message_parts.append(f"Perpetual: {perp_order.get('action')}")
            elif perp_order.get('status') == 'failed':
                message_parts.append(f"Perpetual order failed")

        return {
            'success': success,
            'message': ', '.join(message_parts),
            'kalshi_orders': kalshi_orders,
            'kalshi_failed': kalshi_failed if not dry_run else [],
            'perp_order': perp_order,
            'total_kalshi_cost': total_kalshi_cost,
            'total_perp_size': perp_order.get('size', 0),
            'dry_run': dry_run,
            'timestamp': datetime.now().isoformat()
        }

    def get_live_hedge_positions(self) -> Dict:
        """
        Get all active hedge positions for live tracking.

        This combines:
        - BTC spot holdings
        - Coinbase perpetual positions
        - Kalshi binary option positions

        Returns:
            Dict with:
                - spot_position: BTC balance and value
                - perp_positions: List of active perpetual positions with P&L
                - kalshi_positions: List of active Kalshi positions with P&L
                - combined_pnl: Total unrealized P&L across all positions
                - current_delta: Current BTC delta exposure
                - timestamp: Current timestamp
        """
        try:
            # Get spot BTC holdings
            portfolio = self.get_btc_portfolio()
            current_price = portfolio.get('btc_price', 0)
            btc_balance = portfolio.get('btc_balance', 0)
            notional_value = portfolio.get('notional_value', 0)

            # Get perpetual positions with P&L
            perp_positions_result = self.get_perp_positions()
            perp_positions = []
            total_perp_pnl = 0.0
            perp_delta = 0.0

            if perp_positions_result.get('success'):
                positions_list = perp_positions_result.get('positions', [])
                logger.info(f"Processing {len(positions_list)} perpetual positions")

                for pos in positions_list:
                    product_id = pos.get('product_id')
                    unrealized_pnl = pos.get('unrealized_pnl', 0)
                    total_perp_pnl += unrealized_pnl

                    # Calculate delta
                    contracts = pos.get('number_of_contracts', 0)
                    side = pos.get('side', 'LONG')
                    delta_contribution = contracts if side == 'LONG' else -contracts
                    perp_delta += delta_contribution

                    logger.info(f"Perp position: {product_id} | {side} | {contracts} contracts | entry: ${pos.get('entry_price', 0):.2f} | mark: ${pos.get('mark_price', 0):.2f} | PnL: ${unrealized_pnl:.2f}")

                    perp_positions.append({
                        'product_id': product_id,
                        'side': side,
                        'size': contracts,
                        'entry_price': pos.get('entry_price', 0),
                        'mark_price': pos.get('mark_price', 0),
                        'unrealized_pnl': unrealized_pnl,
                        'delta': delta_contribution
                    })
            else:
                logger.warning(f"Failed to get perp positions: {perp_positions_result.get('message', 'Unknown error')}")

            # Get Kalshi positions with P&L
            kalshi_positions = []
            total_kalshi_pnl = 0.0

            if self.kalshi_engine:
                logger.info(f"Kalshi engine exists, is_connected: {self.kalshi_engine.is_connected}")
                try:
                    positions_list = self.kalshi_engine.get_positions()
                    logger.info(f"Got {len(positions_list) if positions_list else 0} positions from Kalshi")

                    if positions_list and isinstance(positions_list, list):
                        for pos in positions_list:
                            ticker = pos.get('ticker', '')

                            # Filter for BTC-related positions only
                            if 'BTC' not in ticker.upper():
                                logger.debug(f"Skipping non-BTC position: {ticker}")
                                continue

                            # Pass through all the enriched position data
                            pnl = pos.get('pnl', 0)
                            total_kalshi_pnl += pnl

                            # Add the position with all its fields
                            kalshi_positions.append(pos)

                        logger.info(f"Filtered to {len(kalshi_positions)} BTC-related positions")
                    else:
                        logger.warning("No Kalshi positions found or invalid format")
                except Exception as e:
                    logger.error(f"Error fetching Kalshi positions: {e}", exc_info=True)
            else:
                logger.warning("Kalshi engine not initialized")

            # Calculate total delta and P&L
            total_delta = btc_balance + perp_delta  # Spot + Perp delta
            delta_pct = (total_delta / btc_balance * 100) if btc_balance > 0 else 0
            combined_pnl = total_perp_pnl + total_kalshi_pnl

            return {
                'success': True,
                'current_price': current_price,
                'spot_position': {
                    'btc_balance': btc_balance,
                    'notional_value': notional_value,
                    'price': current_price
                },
                'perp_positions': perp_positions,
                'kalshi_positions': kalshi_positions,
                'num_perp_positions': len(perp_positions),
                'num_kalshi_positions': len(kalshi_positions),
                'total_perp_pnl': total_perp_pnl,
                'total_kalshi_pnl': total_kalshi_pnl,
                'combined_pnl': combined_pnl,
                'combined_pnl_pct': (combined_pnl / notional_value * 100) if notional_value > 0 else 0,
                'current_delta': total_delta,
                'delta_pct': delta_pct,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting live hedge positions: {e}")
            return {'success': False, 'message': str(e)}
