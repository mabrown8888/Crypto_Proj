"""
BTC Hedging Optimizer using Linear Programming

This module optimizes a ladder of Kalshi binary options ("BTC < K" contracts)
to minimize cost while achieving target coverage at various downside scenarios.

Mathematical formulation:
    minimize: Σ(p_i × w_i)  [total cost in cents]
    subject to:
        - Σ(payoff_ij × w_i) >= coverage_target_j × loss_j  for all scenarios j
        - w_i >= 0  [no short positions]
        - Σ(p_i × w_i) <= budget  [monthly budget constraint]

    where:
        p_i = market price (probability) for strike K_i
        w_i = weight/allocation for strike K_i (decision variables)
        payoff_ij = payout of strike K_i at scenario j (1 if S_j < K_i, else 0)
        loss_j = BTC dollar loss at scenario j: max(0, S_0 - S_j)
        coverage_target_j = desired "cents on dollar" coverage (e.g., 0.68)
"""

import numpy as np
from scipy.optimize import linprog
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class HedgeOptimizer:
    """Optimizes Kalshi BTC binary options ladder using linear programming."""

    def __init__(self, current_btc_price: float, btc_holdings: float):
        """
        Initialize optimizer.

        Args:
            current_btc_price: Current BTC spot price in USD
            btc_holdings: Amount of BTC to hedge
        """
        self.current_price = current_btc_price
        self.btc_holdings = btc_holdings
        self.notional_value = current_btc_price * btc_holdings

    def generate_scenarios(self,
                          min_drawdown: float = -0.40,
                          max_drawdown: float = 0.0,
                          step: float = 0.02) -> np.ndarray:
        """
        Generate price scenario grid.

        Args:
            min_drawdown: Minimum drawdown to consider (e.g., -0.40 for -40%)
            max_drawdown: Maximum drawdown (typically 0 for current price)
            step: Step size in drawdown terms (e.g., 0.02 for 2% intervals)

        Returns:
            Array of scenario prices
        """
        drawdowns = np.arange(max_drawdown, min_drawdown - step, -step)
        scenarios = self.current_price * (1 + drawdowns)
        return scenarios

    def calculate_loss_at_scenario(self, scenario_price: float) -> float:
        """
        Calculate dollar loss at a given scenario price.

        Args:
            scenario_price: BTC price in the scenario

        Returns:
            Dollar loss (positive number)
        """
        price_drop = max(0, self.current_price - scenario_price)
        return price_drop * self.btc_holdings

    def calculate_payoff(self,
                        strike_price: float,
                        scenario_price: float,
                        contract_size: float = 1.0) -> float:
        """
        Calculate payoff of a binary option at a scenario.

        Args:
            strike_price: Strike price K for "BTC < K" contract
            scenario_price: BTC price in the scenario
            contract_size: Size of each contract (typically $1)

        Returns:
            Payoff in dollars
        """
        if scenario_price < strike_price:
            return contract_size  # Binary pays $1 if condition met
        return 0.0

    def optimize_ladder(self,
                       markets: List[Dict],
                       budget_pct: float = 0.02,
                       target_coverage: float = 0.68,
                       min_coverage_drawdown: float = -0.20) -> Dict:
        """
        Optimize the hedge ladder using linear programming.

        Args:
            markets: List of Kalshi markets with structure:
                     [{'strike': K, 'yes_price': p, 'ticker': 'BTCUSD-...', ...}, ...]
                     where yes_price is in cents (0-100)
            budget_pct: Monthly budget as % of notional (e.g., 0.02 for 2%)
            target_coverage: Target "cents on dollar" at min_coverage_drawdown (e.g., 0.68)
            min_coverage_drawdown: Drawdown level where target coverage applies (e.g., -0.20)

        Returns:
            Dict with optimization results:
                {
                    'optimal_weights': List[float],  # Weight for each market
                    'total_cost': float,  # Total cost in dollars
                    'cost_pct': float,  # Cost as % of notional
                    'coverage_at_scenarios': Dict[float, float],  # scenario_price -> coverage
                    'markets_used': List[Dict],  # Markets with non-zero weights
                    'success': bool,
                    'message': str
                }
        """
        if not markets:
            return {
                'success': False,
                'message': 'No markets provided',
                'optimal_weights': [],
                'total_cost': 0,
                'cost_pct': 0,
                'coverage_at_scenarios': {},
                'markets_used': []
            }

        # Filter out markets with missing data
        valid_markets = [m for m in markets if m.get('strike') and m.get('yes_price')]
        if not valid_markets:
            return {
                'success': False,
                'message': 'No valid markets with strike and price data',
                'optimal_weights': [],
                'total_cost': 0,
                'cost_pct': 0,
                'coverage_at_scenarios': {},
                'markets_used': []
            }

        n_markets = len(valid_markets)

        # Generate scenarios
        scenarios = self.generate_scenarios(min_drawdown=-0.40, max_drawdown=0.0, step=0.02)
        n_scenarios = len(scenarios)

        logger.info(f"Optimizing with {n_markets} markets across {n_scenarios} scenarios")
        logger.info(f"Budget: {budget_pct*100:.1f}% of ${self.notional_value:.2f} = ${budget_pct*self.notional_value:.2f}")

        # Build cost vector (objective function coefficients)
        # Cost in dollars = yes_price (in cents) / 100
        costs = np.array([m['yes_price'] / 100.0 for m in valid_markets])

        # Build payoff matrix: A[j, i] = payoff of market i at scenario j
        payoff_matrix = np.zeros((n_scenarios, n_markets))
        for j, scenario_price in enumerate(scenarios):
            for i, market in enumerate(valid_markets):
                strike = market['strike']
                payoff_matrix[j, i] = self.calculate_payoff(strike, scenario_price)

        # Build inequality constraints: A_ub @ w <= b_ub
        # We want: payoff >= coverage * loss, which is -payoff <= -coverage * loss
        A_ub = []
        b_ub = []

        for j, scenario_price in enumerate(scenarios):
            loss = self.calculate_loss_at_scenario(scenario_price)
            drawdown = (scenario_price - self.current_price) / self.current_price

            # Apply target coverage only for scenarios at or below min_coverage_drawdown
            if drawdown <= min_coverage_drawdown:
                required_payout = target_coverage * loss
            else:
                # For smaller drawdowns, scale coverage linearly (less protection needed)
                if min_coverage_drawdown < 0:
                    scaled_coverage = target_coverage * (drawdown / min_coverage_drawdown)
                else:
                    scaled_coverage = 0
                required_payout = scaled_coverage * loss

            if required_payout > 0:
                # Constraint: Σ(payoff_ij × w_i) >= required_payout
                # Convert to: -Σ(payoff_ij × w_i) <= -required_payout
                A_ub.append(-payoff_matrix[j, :])
                b_ub.append(-required_payout)

        # Budget constraint: Σ(p_i × w_i) <= budget
        budget = budget_pct * self.notional_value
        A_ub.append(costs)
        b_ub.append(budget)

        A_ub = np.array(A_ub)
        b_ub = np.array(b_ub)

        # Bounds: w_i >= 0 (no short selling)
        bounds = [(0, None) for _ in range(n_markets)]

        # Solve LP: minimize cost
        try:
            result = linprog(
                c=costs,
                A_ub=A_ub,
                b_ub=b_ub,
                bounds=bounds,
                method='highs',
                options={'presolve': True, 'disp': False}
            )

            if not result.success:
                logger.warning(f"LP solver did not converge: {result.message}")
                return {
                    'success': False,
                    'message': f'Optimization failed: {result.message}',
                    'optimal_weights': [],
                    'total_cost': 0,
                    'cost_pct': 0,
                    'coverage_at_scenarios': {},
                    'markets_used': []
                }

            optimal_weights = result.x
            total_cost = result.fun

            # Calculate actual coverage at each scenario
            coverage_at_scenarios = {}
            for j, scenario_price in enumerate(scenarios):
                loss = self.calculate_loss_at_scenario(scenario_price)
                if loss > 0:
                    payout = np.dot(payoff_matrix[j, :], optimal_weights)
                    coverage = payout / loss
                    coverage_at_scenarios[scenario_price] = coverage
                else:
                    coverage_at_scenarios[scenario_price] = 0.0

            # Filter markets with non-zero weights (> $0.01)
            markets_used = []
            for i, weight in enumerate(optimal_weights):
                if weight > 0.01:
                    market_info = valid_markets[i].copy()
                    market_info['weight'] = weight
                    market_info['cost'] = weight * costs[i]
                    markets_used.append(market_info)

            # Sort by strike price
            markets_used = sorted(markets_used, key=lambda x: x['strike'])

            logger.info(f"Optimization successful: {len(markets_used)} markets, cost=${total_cost:.2f}")

            return {
                'success': True,
                'message': f'Optimized ladder with {len(markets_used)} strikes',
                'optimal_weights': optimal_weights.tolist(),
                'total_cost': total_cost,
                'cost_pct': (total_cost / self.notional_value) * 100,
                'coverage_at_scenarios': coverage_at_scenarios,
                'markets_used': markets_used,
                'target_coverage': target_coverage,
                'budget_used': total_cost,
                'budget_limit': budget
            }

        except Exception as e:
            logger.error(f"Optimization error: {str(e)}")
            return {
                'success': False,
                'message': f'Optimization error: {str(e)}',
                'optimal_weights': [],
                'total_cost': 0,
                'cost_pct': 0,
                'coverage_at_scenarios': {},
                'markets_used': []
            }

    def calculate_coverage_at_drawdown(self,
                                       optimal_weights: List[float],
                                       markets: List[Dict],
                                       target_drawdown: float = -0.20) -> float:
        """
        Calculate coverage ("cents on dollar") at a specific drawdown level.

        Args:
            optimal_weights: Weights from optimization
            markets: List of markets used
            target_drawdown: Drawdown to evaluate (e.g., -0.20 for -20%)

        Returns:
            Coverage ratio (e.g., 0.68 for 68 cents on the dollar)
        """
        scenario_price = self.current_price * (1 + target_drawdown)
        loss = self.calculate_loss_at_scenario(scenario_price)

        if loss == 0:
            return 0.0

        total_payout = 0.0
        for i, weight in enumerate(optimal_weights):
            if i < len(markets):
                strike = markets[i]['strike']
                payoff = self.calculate_payoff(strike, scenario_price)
                total_payout += weight * payoff

        return total_payout / loss


class EnhancedHedgeOptimizer(HedgeOptimizer):
    """
    Enhanced hedge optimizer with GARCH volatility, probability weighting,
    implied volatility analysis, and transaction cost modeling.

    Key improvements over base HedgeOptimizer:
    1. Probability-weighted scenarios from GARCH Monte Carlo
    2. Implied volatility extraction and mispricing detection
    3. Transaction cost (slippage) modeling
    4. Theta/time decay scoring
    5. Signal-adjusted probabilities
    """

    def __init__(
        self,
        current_btc_price: float,
        btc_holdings: float,
        market_data_service: 'MarketDataService' = None,
        volatility_model: 'GARCHVolatilityModel' = None
    ):
        """
        Initialize enhanced optimizer.

        Args:
            current_btc_price: Current BTC spot price
            btc_holdings: Amount of BTC to hedge
            market_data_service: Service for historical data (optional)
            volatility_model: Pre-fitted GARCH model (optional)
        """
        super().__init__(current_btc_price, btc_holdings)
        self.market_data_service = market_data_service
        self.volatility_model = volatility_model

        # Lazy imports to avoid circular dependencies
        self._iv_analyzer = None
        self._signal_adjuster = None

    @property
    def iv_analyzer(self):
        """Lazy load ImpliedVolatilityAnalyzer."""
        if self._iv_analyzer is None:
            from volatility_model import ImpliedVolatilityAnalyzer
            self._iv_analyzer = ImpliedVolatilityAnalyzer()
        return self._iv_analyzer

    @property
    def signal_adjuster(self):
        """Lazy load SignalAdjuster."""
        if self._signal_adjuster is None:
            from volatility_model import SignalAdjuster
            self._signal_adjuster = SignalAdjuster()
        return self._signal_adjuster

    def generate_probability_weighted_scenarios(
        self,
        horizon_days: int = 30,
        n_scenarios: int = 21
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate scenarios with probability weights using GARCH Monte Carlo.

        Returns:
            Tuple of (scenario_prices, probability_weights)
        """
        if self.volatility_model is None:
            # Fall back to uniform distribution
            logger.warning("No GARCH model provided, using uniform scenario weights")
            scenarios = self.generate_scenarios()
            weights = np.ones(len(scenarios)) / len(scenarios)
            return scenarios, weights

        # Generate probability-weighted scenarios from GARCH MC
        mc_scenarios = self.volatility_model.generate_probability_weighted_scenarios(
            self.current_price,
            horizon_days,
            n_scenarios
        )

        prices = np.array([s.price for s in mc_scenarios])
        probs = np.array([s.probability for s in mc_scenarios])

        return prices, probs

    def calculate_transaction_costs(
        self,
        markets: List[Dict],
        slippage_pct: float = 0.015,
        fee_pct: float = 0.0
    ) -> List[Dict]:
        """
        Adjust market prices for transaction costs.

        Args:
            markets: List of market dicts with yes_price
            slippage_pct: Expected slippage as fraction (1.5% default)
            fee_pct: Exchange fees as fraction

        Returns:
            Markets with adjusted effective prices
        """
        adjusted_markets = []
        for market in markets:
            market_copy = market.copy()
            yes_price = market.get('yes_price', 0)

            # Effective price = ask price * (1 + slippage) + fees
            effective_price = yes_price * (1 + slippage_pct) + (yes_price * fee_pct)

            market_copy['effective_price'] = effective_price
            market_copy['slippage_adjustment'] = effective_price - yes_price
            adjusted_markets.append(market_copy)

        return adjusted_markets

    def calculate_theta_score(
        self,
        market: Dict,
        implied_vol: float = None,
        garch_vol: float = None
    ) -> float:
        """
        Calculate theta/cost ratio for an option.

        Higher score = better value (less time decay relative to cost)

        Args:
            market: Market dict with days_to_expiry, yes_price
            implied_vol: Implied vol (if known)
            garch_vol: GARCH forecast vol

        Returns:
            Theta efficiency score (higher is better)
        """
        days = market.get('days_to_expiry', 30)
        yes_price = market.get('yes_price', 50)

        if yes_price <= 0 or days <= 0:
            return 0.0

        # Simple theta score: price / sqrt(days)
        # Options with more time have more value, but theta accelerates near expiry
        # We prefer options where time value hasn't decayed too much yet
        base_score = (100 - yes_price) / np.sqrt(max(days, 1))

        # Bonus if option is underpriced (garch_vol > implied_vol)
        if garch_vol and implied_vol and garch_vol > implied_vol:
            mispricing_bonus = (garch_vol - implied_vol) / garch_vol
            base_score *= (1 + mispricing_bonus)

        return base_score

    def analyze_markets(
        self,
        markets: List[Dict],
        horizon_days: int = 30
    ) -> Dict:
        """
        Analyze markets for implied volatility and mispricing.

        Args:
            markets: List of market dicts
            horizon_days: Time horizon

        Returns:
            Analysis dict with IV surface and mispriced options
        """
        # Get GARCH volatility
        garch_vol = None
        if self.volatility_model is not None:
            try:
                garch_vol = self.volatility_model.get_current_volatility()
            except Exception as e:
                logger.warning(f"Could not get GARCH vol: {e}")

        # Analyze IV surface
        vol_surface = self.iv_analyzer.analyze_vol_surface(
            self.current_price,
            markets,
            default_days=horizon_days
        )

        # Find mispriced options
        mispriced = []
        if garch_vol:
            mispriced = self.iv_analyzer.find_mispriced_options(
                markets,
                garch_vol,
                self.current_price,
                default_days=horizon_days,
                min_mispricing=0.04  # 4% minimum EV
            )

        return {
            'garch_vol': garch_vol,
            'vol_surface': vol_surface,
            'mispriced_options': mispriced,
            'atm_implied_vol': vol_surface.get('atm_vol'),
            'vol_skew': vol_surface.get('skew')
        }

    def optimize_ladder_advanced(
        self,
        markets: List[Dict],
        budget_pct: float = 0.02,
        target_coverage: float = 0.68,
        min_coverage_drawdown: float = -0.20,
        horizon_days: int = 30,
        prefer_underpriced: bool = True,
        include_theta: bool = True,
        include_transaction_costs: bool = True,
        slippage_pct: float = 0.015,
        ev_threshold: float = 0.04,
        signal_kwargs: Dict = None
    ) -> Dict:
        """
        Enhanced optimization with all advanced features.

        Args:
            markets: List of Kalshi markets
            budget_pct: Budget as % of notional
            target_coverage: Target cents-on-dollar coverage
            min_coverage_drawdown: Drawdown where target applies
            horizon_days: Time horizon for scenarios
            prefer_underpriced: Weight toward mispriced options
            include_theta: Factor in time decay
            include_transaction_costs: Model slippage
            slippage_pct: Slippage as fraction
            ev_threshold: Minimum expected value to consider
            signal_kwargs: Signal values for probability adjustment

        Returns:
            Enhanced result dict with additional analytics
        """
        if not markets:
            return {
                'success': False,
                'message': 'No markets provided',
                'optimal_weights': [],
                'total_cost': 0,
                'cost_pct': 0,
                'coverage_at_scenarios': {},
                'markets_used': []
            }

        # Filter valid markets
        valid_markets = [m for m in markets if m.get('strike') and m.get('yes_price')]
        if not valid_markets:
            return {
                'success': False,
                'message': 'No valid markets',
                'optimal_weights': [],
                'total_cost': 0,
                'cost_pct': 0,
                'coverage_at_scenarios': {},
                'markets_used': []
            }

        # Analyze markets for IV and mispricing
        market_analysis = self.analyze_markets(valid_markets, horizon_days)
        garch_vol = market_analysis.get('garch_vol')

        # Adjust for transaction costs
        if include_transaction_costs:
            valid_markets = self.calculate_transaction_costs(valid_markets, slippage_pct)

        # Generate probability-weighted scenarios
        try:
            scenario_prices, scenario_probs = self.generate_probability_weighted_scenarios(
                horizon_days, n_scenarios=21
            )
        except Exception as e:
            logger.warning(f"GARCH scenario generation failed: {e}, using uniform")
            scenario_prices = self.generate_scenarios()
            scenario_probs = np.ones(len(scenario_prices)) / len(scenario_prices)

        n_markets = len(valid_markets)
        n_scenarios = len(scenario_prices)

        logger.info(f"Enhanced optimization: {n_markets} markets, {n_scenarios} prob-weighted scenarios")

        # Use effective price if transaction costs included
        if include_transaction_costs:
            costs = np.array([m.get('effective_price', m['yes_price']) / 100.0 for m in valid_markets])
        else:
            costs = np.array([m['yes_price'] / 100.0 for m in valid_markets])

        # Adjust costs for mispricing preference
        if prefer_underpriced and garch_vol:
            cost_adjustments = np.ones(n_markets)
            for i, market in enumerate(valid_markets):
                strike = market.get('strike')
                yes_price = market.get('yes_price', 50)

                # Extract IV and check mispricing
                iv = self.iv_analyzer.extract_implied_vol(
                    self.current_price, strike, yes_price, horizon_days
                )
                if iv and garch_vol > iv:
                    # Option is underpriced, reduce effective cost in objective
                    mispricing = (garch_vol - iv) / garch_vol
                    cost_adjustments[i] = 1 - (0.5 * mispricing)  # Up to 50% discount

            costs = costs * cost_adjustments

        # Build payoff matrix
        payoff_matrix = np.zeros((n_scenarios, n_markets))
        for j, scenario_price in enumerate(scenario_prices):
            for i, market in enumerate(valid_markets):
                strike = market['strike']
                payoff_matrix[j, i] = self.calculate_payoff(strike, scenario_price)

        # Build probability-weighted constraints
        A_ub = []
        b_ub = []

        for j, scenario_price in enumerate(scenario_prices):
            loss = self.calculate_loss_at_scenario(scenario_price)
            drawdown = (scenario_price - self.current_price) / self.current_price
            prob = scenario_probs[j]

            # Skip very unlikely scenarios (prob < 0.1%)
            if prob < 0.001:
                continue

            # Determine coverage target based on drawdown
            if drawdown <= min_coverage_drawdown:
                required_coverage = target_coverage
            elif min_coverage_drawdown < 0:
                required_coverage = target_coverage * (drawdown / min_coverage_drawdown)
            else:
                required_coverage = 0

            # Weight by probability for importance sampling
            required_payout = required_coverage * loss * prob

            if required_payout > 0.001:
                # Constraint: Σ(payoff_ij × w_i) >= required_payout
                A_ub.append(-payoff_matrix[j, :] * prob)
                b_ub.append(-required_payout)

        # Budget constraint (with reserve for execution uncertainty)
        budget = budget_pct * self.notional_value * 0.98  # 2% reserve
        A_ub.append(costs)
        b_ub.append(budget)

        A_ub = np.array(A_ub) if A_ub else np.zeros((1, n_markets))
        b_ub = np.array(b_ub) if b_ub else np.zeros(1)

        # Bounds
        bounds = [(0, None) for _ in range(n_markets)]

        # Solve LP
        try:
            result = linprog(
                c=costs,
                A_ub=A_ub,
                b_ub=b_ub,
                bounds=bounds,
                method='highs',
                options={'presolve': True, 'disp': False}
            )

            if not result.success:
                # Try relaxing constraints
                logger.warning(f"LP failed: {result.message}, trying relaxed constraints")
                return self._optimize_relaxed(
                    valid_markets, costs, payoff_matrix, scenario_prices,
                    scenario_probs, budget, target_coverage, min_coverage_drawdown
                )

            optimal_weights = result.x
            total_cost = np.dot(optimal_weights, np.array([m['yes_price'] / 100.0 for m in valid_markets]))

            # Calculate coverage at scenarios
            coverage_at_scenarios = {}
            for j, scenario_price in enumerate(scenario_prices):
                loss = self.calculate_loss_at_scenario(scenario_price)
                if loss > 0:
                    payout = np.dot(payoff_matrix[j, :], optimal_weights)
                    coverage_at_scenarios[float(scenario_price)] = payout / loss
                else:
                    coverage_at_scenarios[float(scenario_price)] = 0.0

            # Build markets_used with analytics
            markets_used = []
            for i, weight in enumerate(optimal_weights):
                if weight > 0.01:
                    market_info = valid_markets[i].copy()
                    market_info['weight'] = weight
                    market_info['cost'] = weight * (valid_markets[i]['yes_price'] / 100.0)

                    # Calculate model probability and EV for this market
                    strike = market_info.get('strike', 0)
                    yes_price = market_info.get('yes_price', 50)
                    market_prob = yes_price / 100.0  # Market probability from price

                    # Use volatility model to get GARCH-based probability
                    if self.volatility_model and self.volatility_model._is_fitted:
                        try:
                            prob_result = self.volatility_model.get_probability(
                                current_price=self.current_price,
                                strike=strike,
                                days_to_expiry=horizon_days,
                                signal_kwargs=signal_kwargs
                            )
                            model_prob = prob_result.get('adjusted_prob', prob_result.get('base_prob', market_prob))
                        except Exception as e:
                            logger.warning(f"Could not calculate model prob for strike {strike}: {e}")
                            model_prob = market_prob + 0.05  # Fallback: assume 5% edge
                    else:
                        model_prob = market_prob + 0.05  # Fallback estimate

                    # EV = model_prob - market_prob (the edge we're trading on)
                    ev = model_prob - market_prob

                    market_info['model_prob'] = round(model_prob, 4)
                    market_info['market_prob'] = round(market_prob, 4)
                    market_info['ev'] = round(ev, 4)

                    # Add theta score
                    if include_theta:
                        market_info['theta_score'] = self.calculate_theta_score(
                            market_info,
                            garch_vol=garch_vol
                        )

                    markets_used.append(market_info)

            markets_used = sorted(markets_used, key=lambda x: x['strike'])

            # Calculate effective cost with slippage
            effective_cost = total_cost * (1 + slippage_pct) if include_transaction_costs else total_cost

            logger.info(f"Enhanced optimization success: {len(markets_used)} markets, "
                       f"cost=${total_cost:.2f}, effective=${effective_cost:.2f}")

            return {
                'success': True,
                'message': f'Optimized with {len(markets_used)} strikes (enhanced)',
                'optimal_weights': optimal_weights.tolist(),
                'total_cost': total_cost,
                'effective_cost_with_slippage': effective_cost,
                'cost_pct': (total_cost / self.notional_value) * 100,
                'coverage_at_scenarios': coverage_at_scenarios,
                'markets_used': markets_used,
                'target_coverage': target_coverage,
                'budget_used': total_cost,
                'budget_limit': budget,
                # Enhanced analytics
                'garch_volatility': garch_vol,
                'scenario_probabilities': {
                    float(p): float(prob)
                    for p, prob in zip(scenario_prices, scenario_probs)
                },
                'implied_vol_analysis': {
                    'atm_vol': market_analysis.get('atm_implied_vol'),
                    'skew': market_analysis.get('vol_skew')
                },
                'mispriced_options': market_analysis.get('mispriced_options', [])[:5],
                'mode': 'advanced'
            }

        except Exception as e:
            logger.error(f"Enhanced optimization error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'Optimization error: {str(e)}',
                'optimal_weights': [],
                'total_cost': 0,
                'cost_pct': 0,
                'coverage_at_scenarios': {},
                'markets_used': []
            }

    def _optimize_relaxed(
        self,
        valid_markets: List[Dict],
        costs: np.ndarray,
        payoff_matrix: np.ndarray,
        scenario_prices: np.ndarray,
        scenario_probs: np.ndarray,
        budget: float,
        target_coverage: float,
        min_coverage_drawdown: float
    ) -> Dict:
        """
        Try optimization with relaxed constraints when primary fails.
        """
        # Try with lower coverage target
        relaxed_coverage = target_coverage * 0.7

        A_ub = []
        b_ub = []

        for j, scenario_price in enumerate(scenario_prices):
            loss = self.calculate_loss_at_scenario(scenario_price)
            drawdown = (scenario_price - self.current_price) / self.current_price
            prob = scenario_probs[j]

            if prob < 0.001:
                continue

            if drawdown <= min_coverage_drawdown:
                required_coverage = relaxed_coverage
            elif min_coverage_drawdown < 0:
                required_coverage = relaxed_coverage * (drawdown / min_coverage_drawdown)
            else:
                required_coverage = 0

            required_payout = required_coverage * loss * prob

            if required_payout > 0.001:
                A_ub.append(-payoff_matrix[j, :] * prob)
                b_ub.append(-required_payout)

        # Relaxed budget (full amount)
        budget_relaxed = budget / 0.98  # Remove reserve
        A_ub.append(costs)
        b_ub.append(budget_relaxed)

        A_ub = np.array(A_ub)
        b_ub = np.array(b_ub)
        bounds = [(0, None) for _ in range(len(valid_markets))]

        try:
            result = linprog(
                c=costs,
                A_ub=A_ub,
                b_ub=b_ub,
                bounds=bounds,
                method='highs'
            )

            if result.success:
                logger.info("Relaxed optimization succeeded")
                optimal_weights = result.x
                total_cost = np.dot(optimal_weights, np.array([m['yes_price'] / 100.0 for m in valid_markets]))

                markets_used = []
                for i, weight in enumerate(optimal_weights):
                    if weight > 0.01:
                        market_info = valid_markets[i].copy()
                        market_info['weight'] = weight
                        markets_used.append(market_info)

                return {
                    'success': True,
                    'message': f'Optimized with relaxed constraints ({relaxed_coverage:.0%} coverage)',
                    'optimal_weights': optimal_weights.tolist(),
                    'total_cost': total_cost,
                    'cost_pct': (total_cost / self.notional_value) * 100,
                    'coverage_at_scenarios': {},
                    'markets_used': sorted(markets_used, key=lambda x: x['strike']),
                    'target_coverage': relaxed_coverage,
                    'mode': 'relaxed'
                }
        except Exception as e:
            pass

        return {
            'success': False,
            'message': 'Could not find feasible solution even with relaxed constraints',
            'optimal_weights': [],
            'total_cost': 0,
            'cost_pct': 0,
            'coverage_at_scenarios': {},
            'markets_used': []
        }
