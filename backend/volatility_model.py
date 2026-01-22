"""
Volatility Model
GARCH volatility modeling, implied volatility extraction, and signal adjustments
for the enhanced hedge optimizer.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scipy.stats import norm
from scipy.optimize import brentq

logger = logging.getLogger(__name__)


@dataclass
class ProbabilityScenario:
    """A price scenario with associated probability."""
    price: float
    drawdown: float
    probability: float


class GARCHVolatilityModel:
    """
    GARCH(1,1) volatility model for BTC.

    σ²_t = ω + α·r²_{t-1} + β·σ²_{t-1}

    Where:
        ω = long-run variance weight
        α = ARCH coefficient (shock impact)
        β = GARCH coefficient (persistence)
    """

    def __init__(self, returns: pd.Series = None):
        """
        Initialize GARCH model.

        Args:
            returns: Log returns series for fitting
        """
        self.model = None
        self.fitted_model = None
        self.params = None
        self._returns = returns
        self._current_vol = None

    def fit(
        self,
        returns: pd.Series = None,
        p: int = 1,
        q: int = 1,
        dist: str = "normal"
    ) -> Dict:
        """
        Fit GARCH(p,q) model to returns.

        Args:
            returns: Log returns series (will be scaled to percentage)
            p: GARCH lag order
            q: ARCH lag order
            dist: Error distribution ("normal", "t", "skewt")

        Returns:
            Dict with fitted parameters: omega, alpha, beta, persistence
        """
        if returns is not None:
            self._returns = returns

        if self._returns is None:
            raise ValueError("No returns data provided for fitting")

        # Scale returns to percentage for numerical stability
        returns_pct = self._returns * 100

        try:
            # Try to use arch library if available
            from arch import arch_model

            self.model = arch_model(
                returns_pct,
                vol='Garch',
                p=p,
                q=q,
                dist=dist,
                mean='Zero'
            )

            self.fitted_model = self.model.fit(disp='off')

            self.params = {
                'omega': float(self.fitted_model.params.get('omega', 0)),
                'alpha': float(self.fitted_model.params.get('alpha[1]', 0)),
                'beta': float(self.fitted_model.params.get('beta[1]', 0)),
            }

            self.params['persistence'] = self.params['alpha'] + self.params['beta']

            # Get current volatility (annualized)
            conditional_vol = self.fitted_model.conditional_volatility
            self._current_vol = float(conditional_vol.iloc[-1]) / 100 * np.sqrt(365)

            logger.info(f"GARCH fitted: alpha={self.params['alpha']:.4f}, "
                       f"beta={self.params['beta']:.4f}, "
                       f"persistence={self.params['persistence']:.4f}")

        except ImportError:
            logger.warning("arch library not available, using simple volatility estimation")
            self._fit_simple(returns_pct)

        return self.params

    def _fit_simple(self, returns_pct: pd.Series) -> None:
        """
        Simple volatility estimation fallback when arch library is unavailable.
        Uses exponentially weighted moving average (EWMA).
        """
        # EWMA with lambda = 0.94 (RiskMetrics standard)
        lambda_param = 0.94

        variance = returns_pct.ewm(alpha=1-lambda_param, adjust=False).var()

        # Estimate GARCH-like parameters
        self.params = {
            'omega': float(variance.mean() * (1 - lambda_param)),
            'alpha': 1 - lambda_param,
            'beta': lambda_param,
            'persistence': lambda_param + (1 - lambda_param)
        }

        # Current volatility (annualized)
        self._current_vol = float(np.sqrt(variance.iloc[-1])) / 100 * np.sqrt(365)

        logger.info("Using EWMA fallback for volatility estimation")

    def forecast_volatility(
        self,
        horizon: int = 30,
        start: int = None
    ) -> pd.DataFrame:
        """
        Forecast volatility h-steps ahead.

        Args:
            horizon: Forecast horizon in days
            start: Starting observation index

        Returns:
            DataFrame with variance/volatility forecasts
        """
        if self.params is None:
            raise ValueError("Model must be fitted first")

        if self.fitted_model is not None:
            # Use arch library forecast
            try:
                forecast = self.fitted_model.forecast(horizon=horizon, start=start)
                vol_forecast = np.sqrt(forecast.variance.dropna())
                # Convert back from percentage and annualize
                vol_forecast = vol_forecast / 100 * np.sqrt(365)
                return vol_forecast
            except Exception as e:
                logger.warning(f"Forecast failed: {e}, using analytical forecast")

        # Analytical GARCH forecast
        omega = self.params['omega']
        alpha = self.params['alpha']
        beta = self.params['beta']
        persistence = alpha + beta

        # Long-run variance
        long_run_var = omega / (1 - persistence) if persistence < 1 else omega

        # Current variance (from last observation)
        current_var = (self._current_vol * 100 / np.sqrt(365)) ** 2

        forecasts = []
        var_t = current_var

        for h in range(1, horizon + 1):
            # Variance forecast h steps ahead
            if persistence < 1:
                var_h = long_run_var + (persistence ** h) * (var_t - long_run_var)
            else:
                var_h = var_t + h * omega

            # Convert to annualized volatility
            vol_h = np.sqrt(var_h) / 100 * np.sqrt(365)
            forecasts.append({'horizon': h, 'volatility': vol_h})

        return pd.DataFrame(forecasts).set_index('horizon')

    def get_current_volatility(self) -> float:
        """Get current (most recent) annualized volatility estimate."""
        if self._current_vol is None:
            if self.params is None:
                raise ValueError("Model must be fitted first")
            # Use long-run volatility as fallback
            omega = self.params['omega']
            persistence = self.params['persistence']
            long_run_var = omega / (1 - persistence) if persistence < 1 else omega
            self._current_vol = np.sqrt(long_run_var) / 100 * np.sqrt(365)

        return self._current_vol

    def simulate_paths(
        self,
        current_price: float,
        horizon_days: int = 30,
        n_paths: int = 10000,
        seed: int = None
    ) -> np.ndarray:
        """
        Simulate price paths using GARCH volatility.

        Args:
            current_price: Current BTC price
            horizon_days: Simulation horizon
            n_paths: Number of Monte Carlo paths
            seed: Random seed for reproducibility

        Returns:
            Array of shape (n_paths,) with terminal prices
        """
        if seed is not None:
            np.random.seed(seed)

        # Get current volatility (daily)
        annual_vol = self.get_current_volatility()
        daily_vol = annual_vol / np.sqrt(365)

        # Simulate with GBM using GARCH volatility
        # For simplicity, we use constant vol from GARCH forecast
        # A more sophisticated version would simulate GARCH process itself

        dt = 1.0  # Daily
        drift = 0  # Assume zero drift for short horizon

        # Generate random shocks
        Z = np.random.standard_normal((n_paths, horizon_days))

        # Simulate log prices
        log_prices = np.zeros((n_paths, horizon_days + 1))
        log_prices[:, 0] = np.log(current_price)

        for t in range(1, horizon_days + 1):
            log_prices[:, t] = (
                log_prices[:, t-1] +
                (drift - 0.5 * daily_vol**2) * dt +
                daily_vol * np.sqrt(dt) * Z[:, t-1]
            )

        # Return terminal prices
        terminal_prices = np.exp(log_prices[:, -1])

        return terminal_prices

    def generate_probability_weighted_scenarios(
        self,
        current_price: float,
        horizon_days: int = 30,
        n_scenarios: int = 21,
        n_paths: int = 10000,
        min_drawdown: float = -0.40,
        max_drawdown: float = 0.10
    ) -> List[ProbabilityScenario]:
        """
        Generate probability-weighted scenarios from Monte Carlo simulation.

        Args:
            current_price: Current BTC price
            horizon_days: Time horizon for scenarios
            n_scenarios: Number of discrete scenarios to generate
            n_paths: Number of MC paths for probability estimation
            min_drawdown: Minimum drawdown to consider
            max_drawdown: Maximum return to consider

        Returns:
            List of ProbabilityScenario objects with prices and probabilities
        """
        # Simulate terminal prices
        terminal_prices = self.simulate_paths(current_price, horizon_days, n_paths)

        # Calculate returns
        returns = (terminal_prices - current_price) / current_price

        # Create bins for scenarios
        bins = np.linspace(min_drawdown, max_drawdown, n_scenarios + 1)
        bin_centers = (bins[:-1] + bins[1:]) / 2

        # Count occurrences in each bin
        counts, _ = np.histogram(returns, bins=bins)
        probabilities = counts / n_paths

        # Ensure probabilities sum to less than 1 (some returns may be outside range)
        # Redistribute to tails if needed
        total_prob = probabilities.sum()
        if total_prob < 0.95:
            # Some mass is in the tails, add to extremes
            below_min = (returns < min_drawdown).mean()
            above_max = (returns > max_drawdown).mean()
            probabilities[0] += below_min
            probabilities[-1] += above_max

        scenarios = []
        for i, (drawdown, prob) in enumerate(zip(bin_centers, probabilities)):
            if prob > 0.001:  # Filter out very unlikely scenarios
                price = current_price * (1 + drawdown)
                scenarios.append(ProbabilityScenario(
                    price=price,
                    drawdown=drawdown,
                    probability=prob
                ))

        # Normalize probabilities to sum to 1
        total = sum(s.probability for s in scenarios)
        for s in scenarios:
            s.probability /= total

        logger.info(f"Generated {len(scenarios)} probability-weighted scenarios")
        return scenarios


class SignalAdjuster:
    """
    Adjusts base probabilities based on market signals.

    Signals include:
    - Funding rate
    - Trend (price vs MA)
    - Volatility term structure
    - RSI
    - Macro indicators
    """

    # Signal weights (how much each signal adjusts probability)
    SIGNAL_WEIGHTS = {
        'funding_extreme': 0.15,      # High funding → higher crash risk
        'trend_bullish': -0.10,       # Above MA → lower crash risk
        'trend_bearish': 0.08,        # Below MA → higher crash risk
        'vol_inverted': 0.08,         # Inverted term structure → higher risk
        'rsi_overbought': 0.06,       # RSI > 70 → higher mean reversion
        'rsi_oversold': -0.05,        # RSI < 30 → lower crash risk
        'macro_risk_off': 0.12,       # VIX > 25 → higher crash risk
    }

    def __init__(self):
        """Initialize the signal adjuster."""
        self.current_signals = {}

    def compute_adjustment(
        self,
        funding_rate: float = None,
        current_price: float = None,
        ma_200: float = None,
        rsi: float = None,
        vix: float = None,
        vol_near: float = None,
        vol_far: float = None
    ) -> float:
        """
        Compute total probability adjustment based on signals.

        Args:
            funding_rate: Perpetual funding rate (e.g., 0.01 = 1%)
            current_price: Current BTC price
            ma_200: 200-day moving average
            rsi: RSI value (0-100)
            vix: VIX index value
            vol_near: Near-term implied volatility
            vol_far: Far-term implied volatility

        Returns:
            Total adjustment factor (e.g., 0.05 means +5% to crash probability)
        """
        adjustment = 0.0
        self.current_signals = {}

        # Funding rate signal
        if funding_rate is not None:
            if funding_rate > 0.0005:  # 0.05% = elevated
                adj = self.SIGNAL_WEIGHTS['funding_extreme'] * min(funding_rate / 0.001, 2.0)
                adjustment += adj
                self.current_signals['funding'] = {
                    'value': funding_rate,
                    'adjustment': adj,
                    'interpretation': 'Elevated funding increases crash risk'
                }

        # Trend signal
        if current_price is not None and ma_200 is not None:
            if current_price > ma_200 * 1.05:  # 5% above MA
                adjustment += self.SIGNAL_WEIGHTS['trend_bullish']
                self.current_signals['trend'] = {
                    'value': (current_price / ma_200 - 1),
                    'adjustment': self.SIGNAL_WEIGHTS['trend_bullish'],
                    'interpretation': 'Bullish trend reduces crash risk'
                }
            elif current_price < ma_200 * 0.95:  # 5% below MA
                adjustment += self.SIGNAL_WEIGHTS['trend_bearish']
                self.current_signals['trend'] = {
                    'value': (current_price / ma_200 - 1),
                    'adjustment': self.SIGNAL_WEIGHTS['trend_bearish'],
                    'interpretation': 'Bearish trend increases crash risk'
                }

        # RSI signal
        if rsi is not None:
            if rsi > 70:
                adj = self.SIGNAL_WEIGHTS['rsi_overbought'] * ((rsi - 70) / 30)
                adjustment += adj
                self.current_signals['rsi'] = {
                    'value': rsi,
                    'adjustment': adj,
                    'interpretation': 'Overbought RSI increases mean reversion risk'
                }
            elif rsi < 30:
                adj = self.SIGNAL_WEIGHTS['rsi_oversold'] * ((30 - rsi) / 30)
                adjustment += adj
                self.current_signals['rsi'] = {
                    'value': rsi,
                    'adjustment': adj,
                    'interpretation': 'Oversold RSI reduces further downside'
                }

        # Macro signal (VIX)
        if vix is not None:
            if vix > 25:
                adj = self.SIGNAL_WEIGHTS['macro_risk_off'] * min((vix - 25) / 15, 1.0)
                adjustment += adj
                self.current_signals['vix'] = {
                    'value': vix,
                    'adjustment': adj,
                    'interpretation': 'Elevated VIX indicates risk-off environment'
                }

        # Vol term structure
        if vol_near is not None and vol_far is not None:
            if vol_near > vol_far * 1.05:  # Inverted
                adjustment += self.SIGNAL_WEIGHTS['vol_inverted']
                self.current_signals['vol_structure'] = {
                    'value': vol_near / vol_far,
                    'adjustment': self.SIGNAL_WEIGHTS['vol_inverted'],
                    'interpretation': 'Inverted vol structure signals near-term stress'
                }

        # Clamp adjustment to reasonable range
        adjustment = max(-0.30, min(0.30, adjustment))

        logger.info(f"Signal adjustment: {adjustment:.2%}")
        return adjustment

    def adjust_probability(
        self,
        base_prob: float,
        **signal_kwargs
    ) -> float:
        """
        Adjust a base probability using market signals.

        Args:
            base_prob: Base probability from lognormal/GARCH model
            **signal_kwargs: Signal values to pass to compute_adjustment

        Returns:
            Adjusted probability
        """
        adjustment = self.compute_adjustment(**signal_kwargs)

        # Apply adjustment multiplicatively
        adjusted_prob = base_prob * (1 + adjustment)

        # Clamp to valid probability range
        return max(0.001, min(0.999, adjusted_prob))


class ImpliedVolatilityAnalyzer:
    """
    Analyze implied volatility from Kalshi/Polymarket option prices.

    For binary options:
    P(BTC < K) = N(-d₂) where d₂ = (ln(S/K) - σ²T/2) / (σ√T)
    """

    def __init__(self):
        """Initialize the IV analyzer."""
        pass

    def extract_implied_vol(
        self,
        current_price: float,
        strike_price: float,
        option_price: float,
        days_to_expiry: float,
        risk_free_rate: float = 0.0
    ) -> Optional[float]:
        """
        Back out implied volatility from binary option price.

        Args:
            current_price: Current BTC spot price
            strike_price: Strike price K
            option_price: Market price of binary option (0-100 cents, or 0-1)
            days_to_expiry: Time to expiration in days
            risk_free_rate: Annual risk-free rate

        Returns:
            Annualized implied volatility, or None if extraction fails
        """
        # Normalize option price to 0-1 range
        if option_price > 1:
            option_price = option_price / 100

        # Handle edge cases
        if option_price <= 0.01 or option_price >= 0.99:
            return None  # Can't extract vol from extreme prices

        if days_to_expiry <= 0:
            return None

        T = days_to_expiry / 365  # Convert to years
        S = current_price
        K = strike_price
        r = risk_free_rate

        # For a binary put (pays $1 if S_T < K):
        # P = e^(-rT) * N(-d2)
        # We need to solve for sigma in d2

        # Target probability from market price
        target_prob = option_price * np.exp(r * T)

        # Solve for sigma using Brent's method
        def objective(sigma):
            if sigma <= 0:
                return float('inf')
            d2 = (np.log(S / K) + (r - 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            model_prob = norm.cdf(-d2)
            return model_prob - target_prob

        try:
            # Search for IV between 10% and 300%
            implied_vol = brentq(objective, 0.10, 3.00, xtol=0.001)
            return implied_vol
        except ValueError:
            # Brent's method failed to converge
            logger.warning(f"IV extraction failed for K={strike_price}, P={option_price}")
            return None

    def analyze_vol_surface(
        self,
        current_price: float,
        markets: List[Dict],
        default_days: float = 30
    ) -> Dict:
        """
        Analyze implied volatility across strikes (vol smile/skew).

        Args:
            current_price: Current BTC spot price
            markets: List of market dicts with strike, yes_price, days_to_expiry
            default_days: Default days to expiry if not provided

        Returns:
            Dict with implied_vols, atm_vol, skew, average_vol
        """
        implied_vols = []

        for market in markets:
            strike = market.get('strike_price')
            yes_price = market.get('yes_price', 0)
            days = market.get('days_to_expiry', default_days)

            if strike is None or yes_price <= 0:
                continue

            iv = self.extract_implied_vol(current_price, strike, yes_price, days)

            if iv is not None:
                moneyness = np.log(strike / current_price)
                implied_vols.append({
                    'strike': strike,
                    'moneyness': moneyness,
                    'implied_vol': iv,
                    'yes_price': yes_price
                })

        if not implied_vols:
            return {
                'implied_vols': [],
                'atm_vol': None,
                'skew': None,
                'average_vol': None
            }

        # Sort by moneyness
        implied_vols.sort(key=lambda x: x['moneyness'])

        # Calculate ATM vol (closest to moneyness = 0)
        atm_vol = min(implied_vols, key=lambda x: abs(x['moneyness']))['implied_vol']

        # Calculate skew (difference between OTM puts and ATM)
        otm_puts = [v for v in implied_vols if v['moneyness'] < -0.10]
        if otm_puts and atm_vol:
            skew = np.mean([v['implied_vol'] for v in otm_puts]) - atm_vol
        else:
            skew = 0

        # Volume-weighted average
        total_weight = sum(v['yes_price'] for v in implied_vols)
        if total_weight > 0:
            avg_vol = sum(v['implied_vol'] * v['yes_price'] for v in implied_vols) / total_weight
        else:
            avg_vol = np.mean([v['implied_vol'] for v in implied_vols])

        return {
            'implied_vols': implied_vols,
            'atm_vol': atm_vol,
            'skew': skew,
            'average_vol': avg_vol
        }

    def find_mispriced_options(
        self,
        markets: List[Dict],
        garch_forecast_vol: float,
        current_price: float,
        default_days: float = 30,
        min_mispricing: float = 0.04
    ) -> List[Dict]:
        """
        Find options that are cheap relative to GARCH forecast.

        Args:
            markets: List of market dicts with strike, yes_price
            garch_forecast_vol: GARCH model volatility forecast
            current_price: Current BTC price
            default_days: Default days to expiry
            min_mispricing: Minimum EV threshold (0.04 = 4%)

        Returns:
            List of markets sorted by mispricing (most underpriced first)
        """
        mispriced = []

        for market in markets:
            strike = market.get('strike_price')
            yes_price = market.get('yes_price', 0)
            days = market.get('days_to_expiry', default_days)

            if strike is None or yes_price <= 0:
                continue

            # Extract implied vol
            iv = self.extract_implied_vol(current_price, strike, yes_price, days)

            if iv is None:
                continue

            # Calculate mispricing score
            mispricing_score = (garch_forecast_vol - iv) / garch_forecast_vol

            # Calculate model probability using GARCH vol
            T = days / 365
            d2 = (np.log(current_price / strike) - 0.5 * garch_forecast_vol**2 * T) / (garch_forecast_vol * np.sqrt(T))
            model_prob = norm.cdf(-d2)

            # Market probability
            market_prob = yes_price / 100 if yes_price > 1 else yes_price

            # Expected value
            ev = model_prob - market_prob

            if ev >= min_mispricing:
                mispriced.append({
                    **market,
                    'implied_vol': iv,
                    'garch_vol': garch_forecast_vol,
                    'mispricing_score': mispricing_score,
                    'model_prob': model_prob,
                    'market_prob': market_prob,
                    'expected_value': ev
                })

        # Sort by expected value (highest first)
        mispriced.sort(key=lambda x: x['expected_value'], reverse=True)

        logger.info(f"Found {len(mispriced)} mispriced options with EV >= {min_mispricing:.0%}")
        return mispriced


class ProbabilityModel:
    """
    Complete probability model combining GARCH, signals, and scenario generation.
    """

    def __init__(self, returns: pd.Series = None):
        """
        Initialize the probability model.

        Args:
            returns: Historical log returns for GARCH fitting
        """
        self.garch = GARCHVolatilityModel(returns)
        self.signals = SignalAdjuster()
        self.iv_analyzer = ImpliedVolatilityAnalyzer()

        self._is_fitted = False

    def fit(self, returns: pd.Series = None) -> Dict:
        """Fit the GARCH model to returns data."""
        params = self.garch.fit(returns)
        self._is_fitted = True
        return params

    def get_probability(
        self,
        current_price: float,
        strike: float,
        days_to_expiry: int = 30,
        signal_kwargs: Dict = None
    ) -> Dict:
        """
        Get probability of price ending below strike.

        Args:
            current_price: Current BTC price
            strike: Strike price
            days_to_expiry: Days until expiry
            signal_kwargs: Optional signal values for adjustment

        Returns:
            Dict with base_prob, adjusted_prob, volatility, signals
        """
        if not self._is_fitted:
            raise ValueError("Model must be fitted first")

        # Get GARCH volatility
        vol = self.garch.get_current_volatility()

        # Calculate base lognormal probability
        T = days_to_expiry / 365
        d2 = (np.log(current_price / strike) - 0.5 * vol**2 * T) / (vol * np.sqrt(T))
        base_prob = float(norm.cdf(-d2))

        # Apply signal adjustments
        if signal_kwargs:
            adjusted_prob = self.signals.adjust_probability(base_prob, **signal_kwargs)
        else:
            adjusted_prob = base_prob

        return {
            'base_prob': base_prob,
            'adjusted_prob': adjusted_prob,
            'volatility': vol,
            'strike': strike,
            'current_price': current_price,
            'days_to_expiry': days_to_expiry,
            'signals': self.signals.current_signals
        }

    def generate_scenarios(
        self,
        current_price: float,
        horizon_days: int = 30,
        n_scenarios: int = 21
    ) -> List[ProbabilityScenario]:
        """Generate probability-weighted scenarios."""
        if not self._is_fitted:
            raise ValueError("Model must be fitted first")

        return self.garch.generate_probability_weighted_scenarios(
            current_price, horizon_days, n_scenarios
        )


if __name__ == "__main__":
    # Test the volatility model
    logging.basicConfig(level=logging.INFO)

    # Generate sample returns
    np.random.seed(42)
    n_days = 365
    daily_returns = np.random.normal(0.0005, 0.03, n_days)  # ~50% annual vol
    returns = pd.Series(daily_returns)

    print("Testing GARCH Model...")
    garch = GARCHVolatilityModel()
    params = garch.fit(returns)
    print(f"GARCH params: {params}")

    vol = garch.get_current_volatility()
    print(f"Current annualized vol: {vol:.2%}")

    print("\nTesting Monte Carlo Scenarios...")
    current_price = 100000
    scenarios = garch.generate_probability_weighted_scenarios(current_price, 30, 21)
    print(f"Generated {len(scenarios)} scenarios")
    for s in scenarios[:5]:
        print(f"  Price: ${s.price:,.0f}, Drawdown: {s.drawdown:.1%}, Prob: {s.probability:.2%}")

    print("\nTesting Signal Adjuster...")
    signals = SignalAdjuster()
    adj = signals.compute_adjustment(
        funding_rate=0.001,
        current_price=100000,
        ma_200=95000,
        rsi=75,
        vix=28
    )
    print(f"Total adjustment: {adj:.2%}")
    print(f"Signals: {signals.current_signals}")

    print("\nTesting IV Analyzer...")
    iv_analyzer = ImpliedVolatilityAnalyzer()
    iv = iv_analyzer.extract_implied_vol(
        current_price=100000,
        strike_price=90000,
        option_price=0.08,  # 8%
        days_to_expiry=30
    )
    print(f"Implied vol: {iv:.2%}" if iv else "IV extraction failed")
