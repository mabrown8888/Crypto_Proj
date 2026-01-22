#!/usr/bin/env python3
"""
Enhanced BTC Prediction Model

Features:
1. Intraday volatility patterns (hour of day)
2. Day of week volatility patterns
3. Directional signals (momentum, trend, funding rate proxy)
4. Combined probability model for Kalshi range markets
"""

import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta
from scipy.stats import norm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedBTCModel:
    """
    Enhanced BTC model with intraday patterns and directional signals.
    """

    def __init__(self):
        self.hourly_data = None
        self.hourly_vol_by_hour = {}      # Volatility by hour of day
        self.hourly_vol_by_dow = {}       # Volatility by day of week
        self.hourly_drift_by_hour = {}    # Average return by hour
        self.hourly_drift_by_dow = {}     # Average return by day of week
        self.base_hourly_vol = 0.0

    def fetch_hourly_data(self, days: int = 365) -> pd.DataFrame:
        """Fetch hourly BTC data from Coinbase."""
        logger.info(f"Fetching {days} days of hourly data...")

        all_candles = []
        granularity = 3600  # 1 hour

        # Coinbase limits to 300 candles per request
        # Fetch in chunks
        end_time = datetime.now()

        while len(all_candles) < days * 24:
            start_time = end_time - timedelta(hours=300)

            url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
            params = {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'granularity': granularity
            }

            try:
                r = requests.get(url, params=params, timeout=30)
                r.raise_for_status()
                candles = r.json()

                if not candles:
                    break

                all_candles.extend(candles)
                end_time = start_time

            except Exception as e:
                logger.warning(f"Error fetching data: {e}")
                break

        if not all_candles:
            raise ValueError("No data fetched")

        # Create DataFrame [timestamp, low, high, open, close, volume]
        df = pd.DataFrame(all_candles, columns=['timestamp', 'low', 'high', 'open', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.sort_values('timestamp').drop_duplicates('timestamp').reset_index(drop=True)

        # Add time features
        df['hour'] = df['timestamp'].dt.hour
        df['dow'] = df['timestamp'].dt.dayofweek  # 0=Monday, 6=Sunday
        df['dow_name'] = df['timestamp'].dt.day_name()

        # Calculate hourly returns
        df['return'] = np.log(df['close'] / df['close'].shift(1))
        df['abs_return'] = df['return'].abs()

        self.hourly_data = df.dropna()
        logger.info(f"Loaded {len(self.hourly_data)} hourly candles")

        return self.hourly_data

    def calculate_intraday_patterns(self) -> dict:
        """Calculate volatility and drift patterns by hour and day of week."""
        if self.hourly_data is None:
            self.fetch_hourly_data()

        df = self.hourly_data

        # Base hourly volatility
        self.base_hourly_vol = df['return'].std()

        # Volatility by hour of day
        hourly_vol = df.groupby('hour')['return'].std()
        self.hourly_vol_by_hour = hourly_vol.to_dict()

        # Volatility by day of week
        dow_vol = df.groupby('dow')['return'].std()
        self.hourly_vol_by_dow = dow_vol.to_dict()

        # Average return (drift) by hour of day
        hourly_drift = df.groupby('hour')['return'].mean()
        self.hourly_drift_by_hour = hourly_drift.to_dict()

        # Average return by day of week
        dow_drift = df.groupby('dow')['return'].mean()
        self.hourly_drift_by_dow = dow_drift.to_dict()

        # Calculate relative volatility (vs average)
        vol_multipliers_hour = {h: v / self.base_hourly_vol for h, v in self.hourly_vol_by_hour.items()}
        vol_multipliers_dow = {d: v / self.base_hourly_vol for d, v in self.hourly_vol_by_dow.items()}

        return {
            'base_hourly_vol': self.base_hourly_vol,
            'vol_by_hour': self.hourly_vol_by_hour,
            'vol_by_dow': self.hourly_vol_by_dow,
            'drift_by_hour': self.hourly_drift_by_hour,
            'drift_by_dow': self.hourly_drift_by_dow,
            'vol_multipliers_hour': vol_multipliers_hour,
            'vol_multipliers_dow': vol_multipliers_dow,
        }

    def calculate_directional_signals(self, current_price: float = None) -> dict:
        """
        Calculate directional signals to predict if BTC will go up or down.

        Signals:
        1. Short-term momentum (last 4 hours vs last 24 hours)
        2. RSI (14-period)
        3. Price vs moving averages
        4. Recent volatility regime
        """
        if self.hourly_data is None:
            self.fetch_hourly_data()

        df = self.hourly_data.copy()

        if current_price is None:
            current_price = df['close'].iloc[-1]

        signals = {}

        # 1. Short-term momentum
        last_4h_return = (df['close'].iloc[-1] / df['close'].iloc[-4] - 1) if len(df) >= 4 else 0
        last_24h_return = (df['close'].iloc[-1] / df['close'].iloc[-24] - 1) if len(df) >= 24 else 0
        signals['momentum_4h'] = last_4h_return
        signals['momentum_24h'] = last_24h_return

        # 2. RSI (14-period)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        signals['rsi'] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50

        # 3. Price vs moving averages
        ma_20 = df['close'].rolling(20).mean().iloc[-1]
        ma_50 = df['close'].rolling(50).mean().iloc[-1]
        ma_200 = df['close'].rolling(200).mean().iloc[-1]

        signals['vs_ma20'] = (current_price / ma_20 - 1) if ma_20 else 0
        signals['vs_ma50'] = (current_price / ma_50 - 1) if ma_50 else 0
        signals['vs_ma200'] = (current_price / ma_200 - 1) if ma_200 else 0

        # 4. Recent volatility (is it elevated?)
        recent_vol = df['return'].tail(24).std()
        avg_vol = df['return'].std()
        signals['vol_regime'] = recent_vol / avg_vol if avg_vol else 1.0

        # 5. Trend strength (ADX proxy - simplified)
        high_low_range = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        avg_range = (df['high'] - df['low']).mean()
        signals['trend_strength'] = high_low_range / avg_range if avg_range else 1.0

        # Combined directional score (-1 to +1)
        # Positive = bullish, Negative = bearish
        direction_score = 0.0

        # RSI contribution
        if signals['rsi'] > 70:
            direction_score -= 0.3  # Overbought, expect pullback
        elif signals['rsi'] < 30:
            direction_score += 0.3  # Oversold, expect bounce
        else:
            direction_score += (signals['rsi'] - 50) / 100  # Neutral zone

        # Momentum contribution
        direction_score += np.clip(signals['momentum_4h'] * 5, -0.3, 0.3)

        # MA contribution
        if signals['vs_ma20'] > 0:
            direction_score += 0.1
        else:
            direction_score -= 0.1

        signals['direction_score'] = np.clip(direction_score, -1.0, 1.0)
        signals['direction'] = 'BULLISH' if direction_score > 0.1 else ('BEARISH' if direction_score < -0.1 else 'NEUTRAL')

        return signals

    def get_adjusted_volatility(self, hours_ahead: float, target_hour: int = None, target_dow: int = None) -> float:
        """
        Get volatility adjusted for time of day and day of week.

        Args:
            hours_ahead: Hours until expiry
            target_hour: Hour when market expires (0-23)
            target_dow: Day of week when market expires (0=Mon, 6=Sun)
        """
        if not self.hourly_vol_by_hour:
            self.calculate_intraday_patterns()

        # Start with base hourly vol
        vol = self.base_hourly_vol

        # Adjust for hour of day if provided
        if target_hour is not None and target_hour in self.hourly_vol_by_hour:
            hour_vol = self.hourly_vol_by_hour[target_hour]
            hour_multiplier = hour_vol / self.base_hourly_vol
            vol *= hour_multiplier

        # Adjust for day of week if provided
        if target_dow is not None and target_dow in self.hourly_vol_by_dow:
            dow_vol = self.hourly_vol_by_dow[target_dow]
            dow_multiplier = dow_vol / self.base_hourly_vol
            vol *= dow_multiplier

        # Scale for time period
        period_vol = vol * np.sqrt(hours_ahead)

        return period_vol

    def get_adjusted_drift(self, hours_ahead: float, target_hour: int = None, target_dow: int = None) -> float:
        """
        Get expected drift (directional move) adjusted for time patterns.
        """
        if not self.hourly_drift_by_hour:
            self.calculate_intraday_patterns()

        drift = 0.0

        # Add hour-of-day drift
        if target_hour is not None and target_hour in self.hourly_drift_by_hour:
            drift += self.hourly_drift_by_hour[target_hour]

        # Add day-of-week drift
        if target_dow is not None and target_dow in self.hourly_drift_by_dow:
            drift += self.hourly_drift_by_dow[target_dow]

        # Scale for time period
        return drift * hours_ahead

    def calculate_range_probability(
        self,
        current_price: float,
        lower: float,
        upper: float,
        hours_ahead: float,
        use_direction: bool = True
    ) -> dict:
        """
        Calculate probability that BTC will be in a price range at expiry.

        Uses:
        1. Time-adjusted volatility
        2. Directional drift from signals
        3. Intraday patterns
        """
        now = datetime.now()
        expiry = now + timedelta(hours=hours_ahead)
        target_hour = expiry.hour
        target_dow = expiry.weekday()

        # Get adjusted volatility
        period_vol = self.get_adjusted_volatility(hours_ahead, target_hour, target_dow)

        # Get drift from intraday patterns
        pattern_drift = self.get_adjusted_drift(hours_ahead, target_hour, target_dow)

        # Get directional signals
        signals = self.calculate_directional_signals(current_price)

        # Combine drifts
        if use_direction:
            # Add directional bias from signals (scaled)
            signal_drift = signals['direction_score'] * period_vol * 0.5  # Max 50% of vol as drift
            total_drift = pattern_drift + signal_drift
        else:
            total_drift = pattern_drift

        # Calculate probability using lognormal with drift
        # P(lower < S_T < upper) where S_T = S_0 * exp(drift - vol^2/2 + vol*Z)
        if period_vol > 0:
            # Adjusted z-scores including drift
            z_lower = (np.log(lower / current_price) - total_drift + period_vol**2/2) / period_vol
            z_upper = (np.log(upper / current_price) - total_drift + period_vol**2/2) / period_vol

            prob = float(norm.cdf(z_upper) - norm.cdf(z_lower))
        else:
            prob = 1.0 if lower <= current_price < upper else 0.0

        # Also calculate probability without directional adjustment for comparison
        if period_vol > 0:
            z_lower_base = np.log(lower / current_price) / period_vol
            z_upper_base = np.log(upper / current_price) / period_vol
            prob_base = float(norm.cdf(z_upper_base) - norm.cdf(z_lower_base))
        else:
            prob_base = prob

        return {
            'probability': prob,
            'probability_base': prob_base,
            'period_vol': period_vol,
            'total_drift': total_drift,
            'direction_score': signals['direction_score'],
            'direction': signals['direction'],
            'rsi': signals['rsi'],
            'momentum_4h': signals['momentum_4h'],
            'target_hour': target_hour,
            'target_dow': target_dow,
        }

    def print_patterns_report(self):
        """Print a report of discovered patterns."""
        patterns = self.calculate_intraday_patterns()
        signals = self.calculate_directional_signals()

        print("\n" + "=" * 80)
        print("  ENHANCED BTC MODEL - PATTERN ANALYSIS")
        print("=" * 80)

        print(f"\n  Base Hourly Volatility: {patterns['base_hourly_vol']:.3%}")

        print("\n  VOLATILITY BY HOUR OF DAY:")
        print("  " + "-" * 60)
        hours_sorted = sorted(patterns['vol_by_hour'].items())
        for hour, vol in hours_sorted:
            mult = patterns['vol_multipliers_hour'][hour]
            bar = "█" * int(mult * 20)
            print(f"    {hour:02d}:00  {vol:.3%}  ({mult:.2f}x) {bar}")

        print("\n  VOLATILITY BY DAY OF WEEK:")
        print("  " + "-" * 60)
        dow_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for dow in range(7):
            if dow in patterns['vol_by_dow']:
                vol = patterns['vol_by_dow'][dow]
                mult = patterns['vol_multipliers_dow'][dow]
                bar = "█" * int(mult * 20)
                print(f"    {dow_names[dow]}  {vol:.3%}  ({mult:.2f}x) {bar}")

        print("\n  AVERAGE DRIFT BY HOUR (Annualized %):")
        print("  " + "-" * 60)
        for hour, drift in sorted(patterns['drift_by_hour'].items()):
            annual_drift = drift * 24 * 365 * 100  # Annualized percentage
            direction = "↑" if drift > 0 else "↓" if drift < 0 else "→"
            print(f"    {hour:02d}:00  {direction} {annual_drift:+.1f}%")

        print("\n  CURRENT DIRECTIONAL SIGNALS:")
        print("  " + "-" * 60)
        print(f"    RSI (14): {signals['rsi']:.1f}")
        print(f"    Momentum (4h): {signals['momentum_4h']*100:+.2f}%")
        print(f"    Momentum (24h): {signals['momentum_24h']*100:+.2f}%")
        print(f"    vs MA20: {signals['vs_ma20']*100:+.2f}%")
        print(f"    vs MA50: {signals['vs_ma50']*100:+.2f}%")
        print(f"    Vol Regime: {signals['vol_regime']:.2f}x")
        print(f"    Direction Score: {signals['direction_score']:+.2f}")
        print(f"    Direction: {signals['direction']}")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    model = EnhancedBTCModel()
    model.fetch_hourly_data(days=90)  # Use 90 days for faster testing
    model.print_patterns_report()

    # Test probability calculation
    print("\n  TEST: Range probability for $97,000-$97,500 in 1 hour")
    result = model.calculate_range_probability(
        current_price=97500,
        lower=97000,
        upper=97500,
        hours_ahead=1.0
    )
    print(f"    Base prob (no direction): {result['probability_base']:.1%}")
    print(f"    Adjusted prob: {result['probability']:.1%}")
    print(f"    Direction: {result['direction']} ({result['direction_score']:+.2f})")
