#!/usr/bin/env python3
"""
Kalshi ML-Powered BTC Range Trader

Combines:
1. Enhanced volatility model (time-of-day, day-of-week patterns)
2. Directional signals (RSI, momentum, MAs)
3. Machine learning predictions trained on historical outcomes
4. Smart position sizing with mutual exclusivity
5. Funding rates (market sentiment)
6. Fear & Greed Index (contrarian signals)
7. Whale movements (volatility prediction)
8. Kalshi historical outcomes (pattern learning)
"""

import os
import sys
import json
import logging
import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta
from scipy.stats import norm
import pickle
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION (Quant-Grade v2)
# =============================================================================

# OLD APPROACH (too conservative):
# MIN_EV_THRESHOLD = 0.02  # Static 2% EV gate - REPLACED

# NEW APPROACH: Risk-adjusted EV threshold
# EV_adj = (p_model - p_market) / σ_prob
# This allows smaller raw EVs with higher confidence, and larger EVs with uncertainty
MIN_EV_ADJUSTED = 0.5            # Require EV / σ_prob > 0.5 (was too strict at 0.8)
MIN_EV_RAW = 0.01                # Still require minimum 1% raw EV as sanity check

# ML CONFIDENCE: Now a SIZE SCALER, not a gate
# size_multiplier = clip(ML_score / 0.5, 0.6, 1.4)
MIN_ML_SCORE_HARD = 0.40         # Only block if ML score is very low (was 0.55 - too strict)
ML_SCALE_BASE = 0.50             # ML score at which size_multiplier = 1.0

# Probability bounds
# NOTE: These are SOFT bounds - can be overridden if edge is large enough
MIN_MODEL_PROB = 0.01            # 1% minimum (very rare events)
MAX_MODEL_PROB = 0.99            # 99% maximum (near-certainties)

# Edge override: If EV is THIS high, ignore probability bounds
# Rationale: If we're 99% sure and market says 50%, that's massive edge worth taking
HIGH_EDGE_OVERRIDE = 0.15        # 15%+ raw EV overrides probability bounds

# Market filters
MIN_VOLUME = 10                  # Low threshold to see more markets (increase to 25+ for stricter filtering)
MAX_POSITION_SIZE = 50           # Max contracts per market
MAX_TOTAL_RISK = 100.00          # Max total $ to risk per run

# Time filters - NOW ADAPTIVE via time-weighted EV
# EV_time = EV × √(hours/24) - rewards patient capital
MIN_HOURS_TO_EXPIRY = 0.1        # At least 6 minutes (for testing)
MAX_HOURS_TO_EXPIRY = 720.0      # Extended to 30 days - capture more markets

MUTUAL_EXCLUSIVITY = True        # Only bet on one range per expiry time

# NEW: Probability estimation uncertainty (for risk-adjusted EV)
# σ_prob estimates our model uncertainty
BASE_PROB_UNCERTAINTY = 0.05     # Base uncertainty in probability estimate
VOL_UNCERTAINTY_SCALE = 0.02     # Additional uncertainty per 10% vol

# ML Model paths
ML_MODEL_PATH = Path(__file__).parent / 'models' / 'kalshi_btc_model.pkl'
ML_DATA_PATH = Path(__file__).parent / 'data' / 'kalshi_historical.csv'


# =============================================================================
# QUANT UTILITY FUNCTIONS
# =============================================================================

def prob_to_logodds(p):
    """Convert probability to log-odds space."""
    p = np.clip(p, 0.001, 0.999)  # Avoid log(0)
    return np.log(p / (1 - p))

def logodds_to_prob(log_odds):
    """Convert log-odds back to probability."""
    return 1 / (1 + np.exp(-log_odds))

def adjust_prob_logodds(base_prob, signal_adjustments):
    """
    Adjust probability using log-odds space (professional approach).

    This preserves probability bounds [0,1] and models signal interactions
    correctly, unlike additive adjustments which can overflow.

    Args:
        base_prob: Base probability from lognormal model
        signal_adjustments: Dict of {signal_name: (value, weight)}
                           where value is normalized [-1, 1]

    Returns:
        Adjusted probability
    """
    base_logodds = prob_to_logodds(base_prob)

    # Apply signal adjustments in log-odds space
    adjustment = 0.0
    for signal_name, (value, weight) in signal_adjustments.items():
        adjustment += value * weight

    adjusted_logodds = base_logodds + adjustment
    return logodds_to_prob(adjusted_logodds)

def calculate_prob_uncertainty(base_vol, hours, signal_confidence):
    """
    Estimate uncertainty in our probability estimate.

    Higher vol = more uncertainty
    Shorter time = more uncertainty
    Lower signal confidence = more uncertainty
    """
    vol_factor = base_vol * VOL_UNCERTAINTY_SCALE * 10
    time_factor = 1 / np.sqrt(max(hours, 0.5))  # More certain over longer periods
    confidence_factor = 1 - signal_confidence * 0.3

    sigma = BASE_PROB_UNCERTAINTY * (1 + vol_factor) * time_factor * confidence_factor
    return np.clip(sigma, 0.02, 0.20)  # Bound between 2% and 20%

def calculate_adjusted_ev(raw_ev, prob_uncertainty):
    """
    Calculate risk-adjusted EV (EV / σ).

    This is the key insight: we want EV per unit of uncertainty,
    not just raw EV. This allows smaller edges with high confidence.
    """
    if prob_uncertainty <= 0:
        return raw_ev * 10  # Large number if somehow uncertainty is 0
    return raw_ev / prob_uncertainty

def calculate_time_weighted_ev(raw_ev, hours):
    """
    Time-weighted EV rewards patient capital.

    EV_t = EV × √(t/24)

    This means:
    - 6 hour expiry: EV × 0.5 (discount short-term noise)
    - 24 hour expiry: EV × 1.0 (baseline)
    - 96 hour expiry: EV × 2.0 (reward for patience)
    """
    time_factor = np.sqrt(max(hours, 1) / 24)
    return raw_ev * time_factor

def calculate_ml_size_multiplier(ml_score):
    """
    Convert ML confidence to position size multiplier.

    Instead of gating on ML score, we scale position size.
    This allows early entries with smaller size.
    """
    multiplier = ml_score / ML_SCALE_BASE
    return np.clip(multiplier, 0.5, 1.5)

def calculate_signal_confidence(signals):
    """
    Calculate overall confidence in our signal mix.

    Returns value in [0, 1] based on signal agreement.
    """
    direction_signals = []

    # Momentum agreement
    if signals.get('momentum_4h', 0) > 0:
        direction_signals.append(1)
    elif signals.get('momentum_4h', 0) < 0:
        direction_signals.append(-1)
    else:
        direction_signals.append(0)

    if signals.get('momentum_24h', 0) > 0:
        direction_signals.append(1)
    elif signals.get('momentum_24h', 0) < 0:
        direction_signals.append(-1)
    else:
        direction_signals.append(0)

    # RSI agreement
    rsi = signals.get('rsi', 50)
    if rsi > 60:
        direction_signals.append(1)
    elif rsi < 40:
        direction_signals.append(-1)
    else:
        direction_signals.append(0)

    # Funding rate
    funding = signals.get('funding_rate', 0)
    if funding > 0.0001:  # Positive funding = longs paying = bearish
        direction_signals.append(-1)
    elif funding < -0.0001:
        direction_signals.append(1)
    else:
        direction_signals.append(0)

    # Calculate agreement
    if len(direction_signals) == 0:
        return 0.5

    avg = np.mean(direction_signals)
    # Convert to confidence: 0 = no agreement, 1 = full agreement
    confidence = abs(avg)
    return confidence


# =============================================================================
# ENHANCED VOLATILITY MODEL
# =============================================================================

class EnhancedVolatilityModel:
    """
    Volatility model with intraday patterns and GARCH.
    """

    def __init__(self):
        self.hourly_data = None
        self.base_hourly_vol = 0.0
        self.vol_by_hour = {}
        self.vol_by_dow = {}
        self.drift_by_hour = {}
        self.drift_by_dow = {}

    def fetch_data(self, days=90):
        """Fetch hourly BTC data from Coinbase."""
        logger.info(f"Fetching {days} days of hourly data...")

        all_candles = []
        granularity = 3600  # 1 hour
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

        # Create DataFrame
        df = pd.DataFrame(all_candles, columns=['timestamp', 'low', 'high', 'open', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.sort_values('timestamp').drop_duplicates('timestamp').reset_index(drop=True)

        # Add features
        df['hour'] = df['timestamp'].dt.hour
        df['dow'] = df['timestamp'].dt.dayofweek
        df['return'] = np.log(df['close'] / df['close'].shift(1))

        self.hourly_data = df.dropna()
        logger.info(f"Loaded {len(self.hourly_data)} hourly candles")

        return self.hourly_data

    def calculate_patterns(self):
        """Calculate volatility patterns by hour and day of week."""
        if self.hourly_data is None:
            self.fetch_data()

        df = self.hourly_data

        # Base volatility
        self.base_hourly_vol = df['return'].std()

        # By hour of day
        self.vol_by_hour = df.groupby('hour')['return'].std().to_dict()
        self.drift_by_hour = df.groupby('hour')['return'].mean().to_dict()

        # By day of week
        self.vol_by_dow = df.groupby('dow')['return'].std().to_dict()
        self.drift_by_dow = df.groupby('dow')['return'].mean().to_dict()

        logger.info(f"Base hourly vol: {self.base_hourly_vol:.4%}")

    def get_adjusted_vol(self, hours_ahead, target_hour=None, target_dow=None):
        """Get volatility adjusted for time patterns."""
        if not self.vol_by_hour:
            self.calculate_patterns()

        vol = self.base_hourly_vol

        # Hour adjustment
        if target_hour is not None and target_hour in self.vol_by_hour:
            hour_mult = self.vol_by_hour[target_hour] / self.base_hourly_vol
            vol *= hour_mult

        # Day of week adjustment
        if target_dow is not None and target_dow in self.vol_by_dow:
            dow_mult = self.vol_by_dow[target_dow] / self.base_hourly_vol
            vol *= dow_mult

        # Scale for time period
        return vol * np.sqrt(hours_ahead)


# =============================================================================
# DIRECTIONAL SIGNALS
# =============================================================================

class DirectionalSignals:
    """
    Calculate directional signals to predict BTC movement.
    """

    def __init__(self, hourly_data):
        self.df = hourly_data.copy()

    def calculate_all(self, current_price=None):
        """Calculate all directional signals."""
        df = self.df

        if current_price is None:
            current_price = df['close'].iloc[-1]

        signals = {}

        # Momentum
        signals['momentum_1h'] = (df['close'].iloc[-1] / df['close'].iloc[-1] - 1) if len(df) >= 1 else 0
        signals['momentum_4h'] = (df['close'].iloc[-1] / df['close'].iloc[-4] - 1) if len(df) >= 4 else 0
        signals['momentum_24h'] = (df['close'].iloc[-1] / df['close'].iloc[-24] - 1) if len(df) >= 24 else 0

        # RSI (14-period)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        signals['rsi'] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50

        # Moving averages
        ma_20 = df['close'].rolling(20).mean().iloc[-1]
        ma_50 = df['close'].rolling(50).mean().iloc[-1]
        signals['vs_ma20'] = (current_price / ma_20 - 1) if ma_20 else 0
        signals['vs_ma50'] = (current_price / ma_50 - 1) if ma_50 else 0

        # Recent volatility regime
        recent_vol = df['return'].tail(24).std()
        avg_vol = df['return'].std()
        signals['vol_regime'] = recent_vol / avg_vol if avg_vol else 1.0

        # Combined direction score (-1 to +1)
        direction_score = 0.0

        # RSI contribution
        if signals['rsi'] > 70:
            direction_score -= 0.3  # Overbought
        elif signals['rsi'] < 30:
            direction_score += 0.3  # Oversold
        else:
            direction_score += (signals['rsi'] - 50) / 100

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


# =============================================================================
# MACHINE LEARNING MODEL
# =============================================================================

class KalshiMLModel:
    """
    Machine learning model for Kalshi BTC range predictions.

    Features:
    - Distance from current price to range (normalized)
    - Time to expiry
    - Hour of day
    - Day of week
    - Volatility regime
    - RSI
    - Momentum signals
    - Range width
    - Model probability
    - Historical win rate for similar setups
    """

    def __init__(self):
        self.model = None
        self.scaler = None
        self.feature_names = [
            'distance_pct',           # Distance from price to range center (%)
            'range_width_pct',        # Range width as % of price
            'hours_to_expiry',        # Time remaining
            'hour_of_day',            # 0-23
            'day_of_week',            # 0-6
            'vol_regime',             # Recent vol / avg vol
            'rsi',                    # RSI value
            'momentum_4h',            # 4-hour momentum
            'momentum_24h',           # 24-hour momentum
            'direction_score',        # Combined direction signal
            'model_prob',             # Base probability from vol model
            'market_prob',            # Market-implied probability
            'ev_raw',                 # Raw expected value
            # NEW: Enhanced data features
            'funding_rate',           # Perpetual funding rate (sentiment)
            'fear_greed',             # Fear & Greed index (0-100)
            'whale_activity',         # Whale transaction volume (normalized)
            'vol_adjustment',         # Volatility adjustment from whale activity
        ]

    def extract_features(self, opportunity, signals, vol_model):
        """Extract ML features from a trading opportunity."""
        current_price = opportunity['current_price']
        lower = opportunity['lower']
        upper = opportunity['upper']
        range_center = (lower + upper) / 2
        range_width = upper - lower

        # Calculate model probability
        hours = opportunity['hours']
        now = datetime.now()
        expiry = now + timedelta(hours=hours)
        target_hour = expiry.hour
        target_dow = expiry.weekday()

        period_vol = vol_model.get_adjusted_vol(hours, target_hour, target_dow)

        # Lognormal probability
        if period_vol > 0:
            z_lower = np.log(lower / current_price) / period_vol
            z_upper = np.log(upper / current_price) / period_vol
            model_prob = float(norm.cdf(z_upper) - norm.cdf(z_lower))
        else:
            model_prob = 1.0 if lower <= current_price < upper else 0.0

        market_prob = opportunity['yes_ask'] / 100.0

        features = {
            'distance_pct': (range_center - current_price) / current_price * 100,
            'range_width_pct': range_width / current_price * 100,
            'hours_to_expiry': hours,
            'hour_of_day': target_hour,
            'day_of_week': target_dow,
            'vol_regime': signals.get('vol_regime', 1.0),
            'rsi': signals.get('rsi', 50),
            'momentum_4h': signals.get('momentum_4h', 0) * 100,
            'momentum_24h': signals.get('momentum_24h', 0) * 100,
            'direction_score': signals.get('direction_score', 0),
            'model_prob': model_prob,
            'market_prob': market_prob,
            'ev_raw': model_prob - market_prob,
            # NEW: Enhanced data features
            'funding_rate': signals.get('funding_rate', 0.0001) * 10000,  # Scaled
            'fear_greed': signals.get('fear_greed', 50),
            'whale_activity': signals.get('whale_activity', 0),  # Normalized 0-1
            'vol_adjustment': signals.get('vol_adjustment', 1.0),
        }

        return features, model_prob

    def train(self, historical_data):
        """
        Train the ML model on historical Kalshi outcomes.

        historical_data should have columns:
        - All feature columns
        - 'outcome': 1 if bet won, 0 if lost
        """
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import cross_val_score

        logger.info(f"Training ML model on {len(historical_data)} samples...")

        X = historical_data[self.feature_names].values
        y = historical_data['outcome'].values

        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Train gradient boosting classifier
        self.model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            min_samples_split=10,
            random_state=42
        )

        # Cross-validation
        cv_scores = cross_val_score(self.model, X_scaled, y, cv=5, scoring='roc_auc')
        logger.info(f"Cross-validation AUC: {cv_scores.mean():.3f} (+/- {cv_scores.std()*2:.3f})")

        # Fit on all data
        self.model.fit(X_scaled, y)

        # Feature importance
        importance = dict(zip(self.feature_names, self.model.feature_importances_))
        logger.info("Feature importance:")
        for feat, imp in sorted(importance.items(), key=lambda x: -x[1])[:5]:
            logger.info(f"  {feat}: {imp:.3f}")

        return cv_scores.mean()

    def predict(self, features_dict):
        """Predict win probability for a single opportunity."""
        if self.model is None:
            return 0.5  # No model, return neutral

        X = np.array([[features_dict[f] for f in self.feature_names]])
        X_scaled = self.scaler.transform(X)

        # Return probability of winning
        prob = self.model.predict_proba(X_scaled)[0][1]
        return prob

    def save(self, path=None):
        """Save model to disk."""
        path = path or ML_MODEL_PATH
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names
            }, f)
        logger.info(f"Model saved to {path}")

    def load(self, path=None):
        """Load model from disk."""
        path = path or ML_MODEL_PATH

        if not path.exists():
            logger.warning(f"No model found at {path}")
            return False

        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.model = data['model']
            self.scaler = data['scaler']
            self.feature_names = data['feature_names']

        logger.info(f"Model loaded from {path}")
        return True


# =============================================================================
# HISTORICAL DATA COLLECTOR
# =============================================================================

class HistoricalDataCollector:
    """
    Collect and store historical Kalshi BTC market outcomes for ML training.
    """

    def __init__(self, kalshi_engine):
        self.kalshi = kalshi_engine
        self.data_path = ML_DATA_PATH

    def collect_settled_markets(self, days_back=30):
        """Fetch settled KXBTC markets from Kalshi."""
        logger.info(f"Collecting settled markets from last {days_back} days...")

        # Fetch settled markets
        result = self.kalshi._make_authenticated_request(
            'GET',
            f'/markets?series_ticker=KXBTC&status=settled&limit=1000'
        )

        markets = result.get('markets', []) if result else []
        logger.info(f"Found {len(markets)} settled markets")

        return markets

    def build_training_data(self, vol_model, signals_calculator):
        """
        Build training dataset from historical markets.

        Note: This is a simplified version. In production, you'd want to:
        1. Store snapshots of market state at various times before expiry
        2. Track the actual BTC price at expiry
        3. Record whether each bet would have won
        """
        markets = self.collect_settled_markets()

        training_data = []

        for market in markets:
            ticker = market.get('ticker', '')
            result = market.get('result', '')  # 'yes' or 'no'

            if 'KXBTC' not in ticker or not result:
                continue

            # Parse ticker for range info
            parts = ticker.split('-')
            if len(parts) < 3:
                continue

            strike_part = parts[2]
            if not strike_part.startswith('B'):
                continue

            try:
                strike = float(strike_part[1:])
                lower = strike - 125
                upper = strike + 125
            except:
                continue

            # For training, we simulate various entry points
            # In production, you'd use actual historical snapshots

            outcome = 1 if result == 'yes' else 0

            # Create synthetic training example
            # (In production, use actual historical data)
            training_data.append({
                'ticker': ticker,
                'lower': lower,
                'upper': upper,
                'outcome': outcome,
                # ... other features would come from historical snapshots
            })

        logger.info(f"Built {len(training_data)} training samples")
        return pd.DataFrame(training_data)

    def generate_synthetic_training_data(self, vol_model, n_samples=5000):
        """
        Generate synthetic training data based on historical patterns.

        This simulates what outcomes would have been for various market conditions.
        """
        logger.info(f"Generating {n_samples} synthetic training samples...")

        if vol_model.hourly_data is None:
            vol_model.fetch_data()

        df = vol_model.hourly_data

        training_data = []

        for _ in range(n_samples):
            # Random historical point
            idx = np.random.randint(100, len(df) - 10)
            row = df.iloc[idx]

            current_price = row['close']
            hour = int(row['hour'])
            dow = int(row['dow'])

            # Random time to expiry (0.5 to 6 hours)
            hours_to_expiry = np.random.uniform(0.5, 6.0)

            # Random range offset (-3% to +3% from current price)
            offset_pct = np.random.uniform(-0.03, 0.03)
            range_center = current_price * (1 + offset_pct)
            range_width = 250  # $250 range
            lower = range_center - range_width / 2
            upper = range_center + range_width / 2

            # Calculate what actually happened
            future_idx = min(idx + int(hours_to_expiry), len(df) - 1)
            future_price = df.iloc[future_idx]['close']

            # Did price end in range?
            outcome = 1 if lower <= future_price < upper else 0

            # Calculate signals at entry time
            recent_returns = df.iloc[max(0,idx-24):idx]['return']
            vol_regime = recent_returns.std() / df['return'].std() if len(recent_returns) > 0 else 1.0

            # Simple RSI calculation
            recent_prices = df.iloc[max(0,idx-14):idx]['close']
            if len(recent_prices) >= 2:
                delta = recent_prices.diff().dropna()
                gain = delta.where(delta > 0, 0).mean()
                loss = (-delta.where(delta < 0, 0)).mean()
                if loss != 0:
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                else:
                    rsi = 50
            else:
                rsi = 50

            # Momentum
            momentum_4h = (current_price / df.iloc[max(0,idx-4)]['close'] - 1) if idx >= 4 else 0
            momentum_24h = (current_price / df.iloc[max(0,idx-24)]['close'] - 1) if idx >= 24 else 0

            # Direction score
            direction_score = 0
            if rsi > 70:
                direction_score -= 0.3
            elif rsi < 30:
                direction_score += 0.3
            direction_score += np.clip(momentum_4h * 5, -0.3, 0.3)
            direction_score = np.clip(direction_score, -1, 1)

            # Model probability
            period_vol = vol_model.get_adjusted_vol(hours_to_expiry, hour, dow)
            if period_vol > 0:
                z_lower = np.log(lower / current_price) / period_vol
                z_upper = np.log(upper / current_price) / period_vol
                model_prob = float(norm.cdf(z_upper) - norm.cdf(z_lower))
            else:
                model_prob = 0.5

            # Simulated market probability (add some noise/bias)
            market_prob = model_prob * np.random.uniform(0.7, 1.3)
            market_prob = np.clip(market_prob, 0.01, 0.99)

            # Simulate enhanced data features (randomized for training)
            # In production, these would come from historical snapshots
            funding_rate = np.random.normal(0.0001, 0.0003)  # Typical funding
            fear_greed = np.random.randint(20, 80)  # Typical F&G range
            whale_activity = np.random.uniform(0, 0.5)  # Normalized
            vol_adjustment = 1.0 + np.random.uniform(-0.1, 0.2)

            training_data.append({
                'distance_pct': (range_center - current_price) / current_price * 100,
                'range_width_pct': range_width / current_price * 100,
                'hours_to_expiry': hours_to_expiry,
                'hour_of_day': hour,
                'day_of_week': dow,
                'vol_regime': vol_regime,
                'rsi': rsi,
                'momentum_4h': momentum_4h * 100,
                'momentum_24h': momentum_24h * 100,
                'direction_score': direction_score,
                'model_prob': model_prob,
                'market_prob': market_prob,
                'ev_raw': model_prob - market_prob,
                # NEW: Enhanced features
                'funding_rate': funding_rate * 10000,  # Scaled to basis points
                'fear_greed': fear_greed,
                'whale_activity': whale_activity,
                'vol_adjustment': vol_adjustment,
                'outcome': outcome,
            })

        result_df = pd.DataFrame(training_data)

        # Save for future use
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_csv(self.data_path, index=False)
        logger.info(f"Training data saved to {self.data_path}")

        # Print statistics
        win_rate = result_df['outcome'].mean()
        logger.info(f"Overall win rate in training data: {win_rate:.1%}")

        return result_df


# =============================================================================
# SMART TRADER
# =============================================================================

class SmartKalshiTrader:
    """
    ML-powered smart trader combining all signals.

    Data sources:
    - Historical BTC prices (90 days hourly)
    - Real-time BTC price
    - Kalshi market data
    - Funding rates (Binance/Bybit)
    - Fear & Greed Index
    - Whale movements
    - Kalshi historical outcomes
    """

    def __init__(self):
        self.vol_model = EnhancedVolatilityModel()
        self.ml_model = KalshiMLModel()
        self.kalshi = None
        self.current_price = None
        self.signals = None
        self.enhanced_data = None  # Enhanced data service
        self.enhanced_signals = None  # Signals from enhanced data

    def initialize(self):
        """Initialize all components."""
        from kalshi_engine import KalshiEngine
        from enhanced_data_service import EnhancedDataService

        logger.info("Initializing Smart Kalshi Trader...")

        # Initialize Kalshi
        self.kalshi = KalshiEngine()
        if not self.kalshi.is_connected:
            raise RuntimeError("Could not connect to Kalshi")

        # Load volatility model
        self.vol_model.fetch_data(days=90)
        self.vol_model.calculate_patterns()

        # Initialize enhanced data service
        logger.info("Initializing enhanced data service...")
        self.enhanced_data = EnhancedDataService(self.kalshi)
        self.enhanced_signals = self.enhanced_data.get_all_signals()

        # Load or train ML model
        if not self.ml_model.load():
            logger.info("No existing ML model found, training new one...")
            self.train_ml_model()

        # Get current BTC price
        try:
            r = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=10)
            self.current_price = float(r.json()['data']['amount'])
        except Exception as e:
            logger.error(f"Failed to get BTC price: {e}")
            raise

        # Calculate base directional signals
        signal_calc = DirectionalSignals(self.vol_model.hourly_data)
        self.signals = signal_calc.calculate_all(self.current_price)

        # Merge enhanced data signals
        self._merge_enhanced_signals()

        logger.info(f"Initialized. BTC: ${self.current_price:,.2f}, Direction: {self.signals['direction']}")
        logger.info(f"Enhanced signals: Funding={self.signals.get('funding_rate', 0)*10000:.2f}bp, "
                    f"F&G={self.signals.get('fear_greed', 50)}, "
                    f"Whales={self.signals.get('whale_activity', 0):.2f}")

    def _merge_enhanced_signals(self):
        """Merge enhanced data signals into main signals dict."""
        if not self.enhanced_signals:
            return

        # Funding rate
        funding = self.enhanced_signals.get('funding', {})
        self.signals['funding_rate'] = funding.get('current_rate', 0.0001)
        self.signals['funding_signal'] = funding.get('signal', {}).get('direction', 'NEUTRAL')

        # Fear & Greed
        fg = self.enhanced_signals.get('fear_greed', {})
        self.signals['fear_greed'] = fg.get('value', 50)
        self.signals['fear_greed_signal'] = fg.get('signal', {}).get('direction', 'NEUTRAL')

        # Whale activity
        whales = self.enhanced_signals.get('whales', {})
        # Normalize whale activity to 0-1 scale
        whale_volume = whales.get('total_volume_btc', 0)
        self.signals['whale_activity'] = min(1.0, whale_volume / 10000)  # 10k BTC = max
        self.signals['whale_signal'] = whales.get('signal', {}).get('direction', 'NEUTRAL')

        # Volatility adjustment from whale activity
        combined = self.enhanced_signals.get('combined', {})
        self.signals['vol_adjustment'] = combined.get('volatility_adjustment', 1.0)

        # Adjust direction score based on enhanced signals
        adjustment = 0.0

        # Funding contribution (contrarian)
        if self.signals['funding_signal'] == 'BULLISH':
            adjustment += 0.15  # Negative funding = bullish
        elif self.signals['funding_signal'] == 'BEARISH':
            adjustment -= 0.15  # High funding = bearish

        # Fear & Greed contribution (contrarian)
        if self.signals['fear_greed_signal'] == 'BULLISH':
            adjustment += 0.15  # Extreme fear = bullish
        elif self.signals['fear_greed_signal'] == 'BEARISH':
            adjustment -= 0.15  # Extreme greed = bearish

        # Update direction score
        self.signals['direction_score'] = np.clip(
            self.signals['direction_score'] + adjustment, -1.0, 1.0
        )

        # Update direction label
        score = self.signals['direction_score']
        if score > 0.15:
            self.signals['direction'] = 'BULLISH'
        elif score < -0.15:
            self.signals['direction'] = 'BEARISH'
        else:
            self.signals['direction'] = 'NEUTRAL'

    def train_ml_model(self):
        """Train the ML model on synthetic data."""
        collector = HistoricalDataCollector(self.kalshi)
        training_data = collector.generate_synthetic_training_data(self.vol_model, n_samples=10000)

        self.ml_model.train(training_data)
        self.ml_model.save()

    def analyze_markets(self):
        """
        Analyze all BTC markets and score opportunities.

        QUANT-GRADE v2 APPROACH:
        1. Signal adjustments in log-odds space (not additive)
        2. Risk-adjusted EV (EV / σ_prob) instead of static threshold
        3. Time-weighted EV (EV × √t) to reward patient capital
        4. ML score as size scaler, not gate
        """

        # Fetch KXBTC markets
        result = self.kalshi._make_authenticated_request(
            'GET',
            '/markets?series_ticker=KXBTC&status=open&limit=200'
        )
        markets = result.get('markets', []) if result else []

        opportunities = []

        # Calculate signal confidence for uncertainty estimation
        signal_confidence = calculate_signal_confidence(self.signals)

        for market in markets:
            ticker = market.get('ticker', '')
            subtitle = market.get('subtitle', '')

            # Parse range from subtitle
            lower, upper, is_tail = self._parse_range(subtitle)
            if lower is None or is_tail:  # Skip tail markets for now
                continue

            # Parse expiry time
            hours = self._calculate_hours_to_expiry(ticker)

            # Apply time filters
            if hours < MIN_HOURS_TO_EXPIRY or hours > MAX_HOURS_TO_EXPIRY:
                continue

            volume = market.get('volume', 0)
            if volume < MIN_VOLUME:
                continue

            yes_ask = market.get('yes_ask', 0)
            no_ask = market.get('no_ask', 0)
            if yes_ask <= 0:
                continue

            # Build opportunity dict
            opp = {
                'ticker': ticker,
                'subtitle': subtitle,
                'market_type': 'range',
                'lower': lower,
                'upper': upper,
                'hours': hours,
                'yes_bid': market.get('yes_bid', 0),
                'yes_ask': yes_ask,
                'no_ask': no_ask,
                'volume': volume,
                'current_price': self.current_price,
            }

            # Extract features and calculate base model probability
            features, base_model_prob = self.ml_model.extract_features(opp, self.signals, self.vol_model)

            # ===================================================================
            # QUANT UPGRADE #1: Signal adjustments in LOG-ODDS SPACE
            # ===================================================================
            # Build signal adjustment dict: {name: (normalized_value, weight)}
            signal_adjustments = {
                'funding': (self.signals.get('funding_rate', 0) * 10000, 0.10),  # Funding in bps
                'fear_greed': ((self.signals.get('fear_greed', 50) - 50) / 50, 0.08),  # Normalized -1 to 1
                'momentum_4h': (np.clip(self.signals.get('momentum_4h', 0) * 20, -1, 1), 0.12),
                'momentum_24h': (np.clip(self.signals.get('momentum_24h', 0) * 10, -1, 1), 0.08),
                'rsi_divergence': ((self.signals.get('rsi', 50) - 50) / 50, 0.10),
                'vol_regime': ((self.signals.get('vol_regime', 1.0) - 1.0), 0.15),  # Vol expansion/contraction
                'whale_activity': (self.signals.get('whale_activity', 0), 0.05),
            }

            # Adjust probability using log-odds space (preserves bounds, better math)
            adjusted_model_prob = adjust_prob_logodds(base_model_prob, signal_adjustments)

            # ML prediction
            ml_score = self.ml_model.predict(features)

            # ===================================================================
            # QUANT UPGRADE #2: Risk-adjusted EV
            # ===================================================================
            market_prob = yes_ask / 100.0
            raw_ev = adjusted_model_prob - market_prob

            # Get base volatility for uncertainty calculation
            base_vol = self.vol_model.get_adjusted_vol(hours) / np.sqrt(hours) if hours > 0 else 0.02

            # Calculate probability uncertainty
            prob_uncertainty = calculate_prob_uncertainty(base_vol, hours, signal_confidence)

            # Risk-adjusted EV: EV per unit of uncertainty
            ev_adjusted = calculate_adjusted_ev(raw_ev, prob_uncertainty)

            # ===================================================================
            # QUANT UPGRADE #3: Time-weighted EV
            # ===================================================================
            ev_time_weighted = calculate_time_weighted_ev(raw_ev, hours)

            # ===================================================================
            # QUANT UPGRADE #4: ML as size scaler, not gate
            # ===================================================================
            ml_size_multiplier = calculate_ml_size_multiplier(ml_score)

            # Determine side (YES or NO) based on which has positive EV
            ev_no = (1 - adjusted_model_prob) - (no_ask / 100.0) if no_ask > 0 else -1

            if raw_ev >= ev_no:
                side = 'yes'
                final_ev = raw_ev
                price = yes_ask
            else:
                side = 'no'
                final_ev = ev_no
                price = no_ask
                # Recalculate for NO side
                prob_uncertainty = calculate_prob_uncertainty(base_vol, hours, signal_confidence)
                ev_adjusted = calculate_adjusted_ev(final_ev, prob_uncertainty)
                ev_time_weighted = calculate_time_weighted_ev(final_ev, hours)

            # Store probabilities for the SIDE being traded (not always YES)
            if side == 'yes':
                side_model_prob = adjusted_model_prob
                side_market_prob = market_prob
            else:
                # NO side: convert to NO probabilities
                side_model_prob = 1 - adjusted_model_prob
                side_market_prob = 1 - market_prob

            opp.update({
                'model_prob': side_model_prob,  # Probability for the side being traded
                'base_model_prob': base_model_prob,
                'market_prob': side_market_prob,  # Market prob for the side being traded
                'yes_model_prob': adjusted_model_prob,  # Always store YES prob for reference
                'yes_market_prob': market_prob,
                'ml_score': ml_score,
                'side': side,
                'price': price,
                # Raw EV metrics
                'ev': final_ev,  # Raw EV (p_model - p_market) for the traded side
                'base_ev': final_ev,  # Alias for compatibility
                # Quant-grade metrics
                'prob_uncertainty': prob_uncertainty,
                'ev_adjusted': ev_adjusted,  # Risk-adjusted EV (EV / σ)
                'ev_time_weighted': ev_time_weighted,  # Time-weighted EV
                'ml_size_multiplier': ml_size_multiplier,  # Position size scaler
                'signal_confidence': signal_confidence,
                # Combined score for ranking (weighted combo)
                'adjusted_ev': 0.5 * ev_adjusted * 0.1 + 0.3 * ev_time_weighted + 0.2 * final_ev,
                'features': features,
            })

            # ===================================================================
            # QUANT-GRADE FILTERING
            # ===================================================================
            # Instead of static threshold, use risk-adjusted metrics

            # Debug: Log first few markets to understand why they're being filtered
            if len(opportunities) == 0 and market == markets[0]:
                logger.debug(f"Sample market {ticker}: raw_ev={final_ev:.4f}, ev_adj={ev_adjusted:.2f}, "
                            f"ml={ml_score:.3f}, prob={adjusted_model_prob:.3f}")

            # Check if high edge overrides probability bounds
            high_edge = final_ev >= HIGH_EDGE_OVERRIDE

            # Probability bounds check (can be overridden by high edge)
            prob_in_bounds = (adjusted_model_prob >= MIN_MODEL_PROB and
                             adjusted_model_prob <= MAX_MODEL_PROB)

            passes_filter = (
                # Minimum raw EV as sanity check
                final_ev >= MIN_EV_RAW and
                # Risk-adjusted EV must exceed threshold
                ev_adjusted >= MIN_EV_ADJUSTED and
                # Hard ML floor (but not a gate - it's now a size scaler)
                ml_score >= MIN_ML_SCORE_HARD and
                # Probability bounds OR high edge override
                (prob_in_bounds or high_edge)
            )

            if passes_filter:
                opp['high_edge_override'] = bool(high_edge)  # Track if we used the override
                opportunities.append(opp)
            else:
                # Store rejected opportunities for debugging
                opp['rejection_reasons'] = []
                if final_ev < MIN_EV_RAW:
                    opp['rejection_reasons'].append(f'raw_ev={final_ev:.4f} < {MIN_EV_RAW}')
                if ev_adjusted < MIN_EV_ADJUSTED:
                    opp['rejection_reasons'].append(f'ev_adj={ev_adjusted:.2f} < {MIN_EV_ADJUSTED}')
                if ml_score < MIN_ML_SCORE_HARD:
                    opp['rejection_reasons'].append(f'ml={ml_score:.3f} < {MIN_ML_SCORE_HARD}')
                if not prob_in_bounds and not high_edge:
                    if adjusted_model_prob < MIN_MODEL_PROB:
                        opp['rejection_reasons'].append(f'prob={adjusted_model_prob:.3f} < {MIN_MODEL_PROB} (edge {final_ev:.1%} < {HIGH_EDGE_OVERRIDE:.0%} override)')
                    if adjusted_model_prob > MAX_MODEL_PROB:
                        opp['rejection_reasons'].append(f'prob={adjusted_model_prob:.3f} > {MAX_MODEL_PROB} (edge {final_ev:.1%} < {HIGH_EDGE_OVERRIDE:.0%} override)')

                # Keep track of rejected for analysis (store in a class variable)
                if not hasattr(self, '_rejected_opportunities'):
                    self._rejected_opportunities = []
                self._rejected_opportunities.append(opp)

        # Sort by combined adjusted EV score
        opportunities.sort(key=lambda x: x['adjusted_ev'], reverse=True)

        # Apply mutual exclusivity (only best bet per expiry time)
        if MUTUAL_EXCLUSIVITY:
            opportunities = self._apply_mutual_exclusivity(opportunities)

        return opportunities

    def analyze_threshold_markets(self):
        """
        Analyze KXBTCD above/below threshold markets.
        These are binary bets on whether BTC will be above or below a specific price.
        Supports both YES and NO bets based on mispricing.

        QUANT-GRADE v2: Uses same risk-adjusted EV approach as range markets.
        """
        # Fetch KXBTCD markets
        result = self.kalshi._make_authenticated_request(
            'GET',
            '/markets?series_ticker=KXBTCD&status=open&limit=100'
        )
        markets = result.get('markets', []) if result else []

        opportunities = []

        # Calculate signal confidence for uncertainty estimation
        signal_confidence = calculate_signal_confidence(self.signals)

        for market in markets:
            ticker = market.get('ticker', '')
            subtitle = market.get('subtitle', '')
            volume = market.get('volume', 0)
            yes_ask = market.get('yes_ask', 0)
            no_ask = market.get('no_ask', 0)

            # Parse threshold from subtitle (e.g., "$95,500 or above")
            threshold_str = subtitle.replace(',', '').replace('$', '').replace(' or above', '').replace(' or below', '')
            try:
                threshold = float(threshold_str)
            except:
                continue

            is_above = 'above' in subtitle.lower()

            # Parse expiry time
            hours = self._calculate_hours_to_expiry(ticker)

            # Apply filters
            if hours < MIN_HOURS_TO_EXPIRY or hours > MAX_HOURS_TO_EXPIRY:
                continue

            if volume < MIN_VOLUME:
                continue

            # Calculate BASE model probability using lognormal
            period_vol = self.vol_model.get_adjusted_vol(hours)

            if period_vol > 0:
                z = np.log(threshold / self.current_price) / period_vol
                if is_above:
                    base_model_prob = float(1 - norm.cdf(z))  # P(S_T > K)
                else:
                    base_model_prob = float(norm.cdf(z))  # P(S_T < K)
            else:
                base_model_prob = 0.5

            # ===================================================================
            # QUANT UPGRADE #1: Signal adjustments in LOG-ODDS SPACE
            # ===================================================================
            signal_adjustments = {
                'funding': (self.signals.get('funding_rate', 0) * 10000, 0.10),
                'fear_greed': ((self.signals.get('fear_greed', 50) - 50) / 50, 0.08),
                'momentum_4h': (np.clip(self.signals.get('momentum_4h', 0) * 20, -1, 1), 0.12),
                'momentum_24h': (np.clip(self.signals.get('momentum_24h', 0) * 10, -1, 1), 0.08),
                'rsi_divergence': ((self.signals.get('rsi', 50) - 50) / 50, 0.10),
                'vol_regime': ((self.signals.get('vol_regime', 1.0) - 1.0), 0.15),
                'whale_activity': (self.signals.get('whale_activity', 0), 0.05),
            }

            # Adjust probability using log-odds space
            model_prob = adjust_prob_logodds(base_model_prob, signal_adjustments)

            # Market probabilities
            market_prob_yes = yes_ask / 100.0 if yes_ask > 0 else 1.0
            market_prob_no = no_ask / 100.0 if no_ask > 0 else 1.0

            # Raw EVs
            ev_yes = model_prob - market_prob_yes
            ev_no = (1 - model_prob) - market_prob_no

            # Distance from current price (for display)
            distance_pct = (threshold - self.current_price) / self.current_price * 100

            # Only consider markets within 10% of current price
            if abs(distance_pct) > 10:
                continue

            # Get base volatility for uncertainty calculation
            base_vol = period_vol / np.sqrt(hours) if hours > 0 else 0.02

            # ===================================================================
            # QUANT UPGRADES #2-4: Risk-adjusted EV, time-weighted EV, ML sizing
            # ===================================================================
            # Calculate for YES side
            prob_uncertainty_yes = calculate_prob_uncertainty(base_vol, hours, signal_confidence)
            ev_adjusted_yes = calculate_adjusted_ev(ev_yes, prob_uncertainty_yes)
            ev_time_weighted_yes = calculate_time_weighted_ev(ev_yes, hours)
            ml_size_multiplier_yes = calculate_ml_size_multiplier(model_prob)  # Use model prob as ML proxy

            # Calculate for NO side
            prob_uncertainty_no = calculate_prob_uncertainty(base_vol, hours, signal_confidence)
            ev_adjusted_no = calculate_adjusted_ev(ev_no, prob_uncertainty_no)
            ev_time_weighted_no = calculate_time_weighted_ev(ev_no, hours)
            ml_size_multiplier_no = calculate_ml_size_multiplier(1 - model_prob)

            # ===================================================================
            # QUANT-GRADE FILTERING
            # ===================================================================

            # Check YES opportunity
            high_edge_yes = ev_yes >= HIGH_EDGE_OVERRIDE
            prob_in_bounds_yes = (model_prob >= MIN_MODEL_PROB and model_prob <= MAX_MODEL_PROB)

            passes_yes = (
                ev_yes >= MIN_EV_RAW and
                ev_adjusted_yes >= MIN_EV_ADJUSTED and
                (prob_in_bounds_yes or high_edge_yes) and
                yes_ask > 0
            )

            yes_opp = {
                'ticker': ticker,
                'subtitle': subtitle,
                'market_type': 'threshold',
                'threshold': threshold,
                'is_above': is_above,
                'side': 'yes',
                'hours': hours,
                'yes_ask': yes_ask,
                'no_ask': no_ask,
                'price': yes_ask,
                'volume': volume,
                'current_price': self.current_price,
                'distance_pct': distance_pct,
                'model_prob': model_prob,
                'base_model_prob': base_model_prob,
                'market_prob': market_prob_yes,
                'ml_score': model_prob,  # Use model prob as ML proxy
                'ev': ev_yes,
                'base_ev': ev_yes,
                # Quant-grade metrics
                'prob_uncertainty': prob_uncertainty_yes,
                'ev_adjusted': ev_adjusted_yes,
                'ev_time_weighted': ev_time_weighted_yes,
                'ml_size_multiplier': ml_size_multiplier_yes,
                'signal_confidence': signal_confidence,
                # Combined score for ranking
                'adjusted_ev': 0.5 * ev_adjusted_yes * 0.1 + 0.3 * ev_time_weighted_yes + 0.2 * ev_yes,
            }

            if passes_yes:
                yes_opp['high_edge_override'] = bool(high_edge_yes)
                opportunities.append(yes_opp)
            else:
                # Track rejection reasons
                yes_opp['rejection_reasons'] = []
                if ev_yes < MIN_EV_RAW:
                    yes_opp['rejection_reasons'].append(f'raw_ev={ev_yes:.4f} < {MIN_EV_RAW}')
                if ev_adjusted_yes < MIN_EV_ADJUSTED:
                    yes_opp['rejection_reasons'].append(f'ev_adj={ev_adjusted_yes:.2f} < {MIN_EV_ADJUSTED}')
                if not prob_in_bounds_yes and not high_edge_yes:
                    if model_prob < MIN_MODEL_PROB:
                        yes_opp['rejection_reasons'].append(f'prob={model_prob:.3f} < {MIN_MODEL_PROB} (edge {ev_yes:.1%} < {HIGH_EDGE_OVERRIDE:.0%})')
                    if model_prob > MAX_MODEL_PROB:
                        yes_opp['rejection_reasons'].append(f'prob={model_prob:.3f} > {MAX_MODEL_PROB} (edge {ev_yes:.1%} < {HIGH_EDGE_OVERRIDE:.0%})')
                if not hasattr(self, '_rejected_opportunities'):
                    self._rejected_opportunities = []
                self._rejected_opportunities.append(yes_opp)

            # Check NO opportunity
            no_prob = 1 - model_prob
            high_edge_no = ev_no >= HIGH_EDGE_OVERRIDE
            prob_in_bounds_no = (no_prob >= MIN_MODEL_PROB and no_prob <= MAX_MODEL_PROB)

            passes_no = (
                ev_no >= MIN_EV_RAW and
                ev_adjusted_no >= MIN_EV_ADJUSTED and
                (prob_in_bounds_no or high_edge_no) and
                no_ask > 0
            )

            no_opp = {
                'ticker': ticker,
                'subtitle': subtitle,
                'market_type': 'threshold',
                'threshold': threshold,
                'is_above': is_above,
                'side': 'no',
                'hours': hours,
                'yes_ask': yes_ask,
                'no_ask': no_ask,
                'price': no_ask,
                'volume': volume,
                'current_price': self.current_price,
                'distance_pct': distance_pct,
                'model_prob': 1 - model_prob,  # NO probability
                'base_model_prob': 1 - base_model_prob,
                'market_prob': market_prob_no,
                'ml_score': 1 - model_prob,
                'ev': ev_no,
                'base_ev': ev_no,
                # Quant-grade metrics
                'prob_uncertainty': prob_uncertainty_no,
                'ev_adjusted': ev_adjusted_no,
                'ev_time_weighted': ev_time_weighted_no,
                'ml_size_multiplier': ml_size_multiplier_no,
                'signal_confidence': signal_confidence,
                # Combined score for ranking
                'adjusted_ev': 0.5 * ev_adjusted_no * 0.1 + 0.3 * ev_time_weighted_no + 0.2 * ev_no,
            }

            if passes_no:
                no_opp['high_edge_override'] = bool(high_edge_no)
                opportunities.append(no_opp)
            else:
                # Track rejection reasons
                no_opp['rejection_reasons'] = []
                if ev_no < MIN_EV_RAW:
                    no_opp['rejection_reasons'].append(f'raw_ev={ev_no:.4f} < {MIN_EV_RAW}')
                if ev_adjusted_no < MIN_EV_ADJUSTED:
                    no_opp['rejection_reasons'].append(f'ev_adj={ev_adjusted_no:.2f} < {MIN_EV_ADJUSTED}')
                if not prob_in_bounds_no and not high_edge_no:
                    if no_prob < MIN_MODEL_PROB:
                        no_opp['rejection_reasons'].append(f'prob={no_prob:.3f} < {MIN_MODEL_PROB} (edge {ev_no:.1%} < {HIGH_EDGE_OVERRIDE:.0%})')
                    if no_prob > MAX_MODEL_PROB:
                        no_opp['rejection_reasons'].append(f'prob={no_prob:.3f} > {MAX_MODEL_PROB} (edge {ev_no:.1%} < {HIGH_EDGE_OVERRIDE:.0%})')
                if not hasattr(self, '_rejected_opportunities'):
                    self._rejected_opportunities = []
                self._rejected_opportunities.append(no_opp)

        # Sort by combined adjusted EV score
        opportunities.sort(key=lambda x: x['adjusted_ev'], reverse=True)

        return opportunities

    def analyze_all_markets(self):
        """Analyze both range and threshold markets, return combined opportunities."""
        range_opps = self.analyze_markets()
        threshold_opps = self.analyze_threshold_markets()

        # Combine and sort
        all_opps = range_opps + threshold_opps
        all_opps.sort(key=lambda x: x['adjusted_ev'], reverse=True)

        return all_opps

    def _parse_range(self, subtitle):
        """Parse range from market subtitle."""
        if not subtitle:
            return None, None, None

        subtitle_clean = subtitle.replace(',', '').replace('$', '')

        if 'or below' in subtitle.lower():
            try:
                upper = float(subtitle_clean.split(' or ')[0])
                return 0, upper, 'low'
            except:
                pass
        elif 'or above' in subtitle.lower():
            try:
                lower = float(subtitle_clean.split(' or ')[0])
                return lower, float('inf'), 'high'
            except:
                pass
        elif ' to ' in subtitle.lower():
            try:
                parts = subtitle_clean.split(' to ')
                lower = float(parts[0])
                upper = float(parts[1])
                return lower, upper, None
            except:
                pass

        return None, None, None

    def _calculate_hours_to_expiry(self, ticker):
        """Calculate hours until expiration."""
        if not ticker:
            return 24.0

        parts = ticker.split('-')
        if len(parts) >= 2:
            date_part = parts[1]
            try:
                year = int('20' + date_part[:2])
                month_str = date_part[2:5]
                day = int(date_part[5:7])
                hour = int(date_part[7:9]) if len(date_part) >= 9 else 16

                months = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                         'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
                month = months.get(month_str.upper(), 1)

                exp_date = datetime(year, month, day, hour)
                hours = (exp_date - datetime.now()).total_seconds() / 3600
                return max(0.1, hours)
            except:
                pass

        return 24.0

    def _apply_mutual_exclusivity(self, opportunities):
        """Keep only the best opportunity per expiry time."""
        by_expiry = {}

        for opp in opportunities:
            # Group by expiry (extract from ticker)
            parts = opp['ticker'].split('-')
            if len(parts) >= 2:
                expiry_key = parts[1]  # e.g., "26JAN1416"
            else:
                expiry_key = 'unknown'

            if expiry_key not in by_expiry:
                by_expiry[expiry_key] = opp
            elif opp['adjusted_ev'] > by_expiry[expiry_key]['adjusted_ev']:
                by_expiry[expiry_key] = opp

        return list(by_expiry.values())

    def execute_trades(self, opportunities, dry_run=True):
        """Execute trades on opportunities (supports both range and threshold markets)."""

        balance_info = self.kalshi.get_balance()
        balance = balance_info['balance']

        total_risked = 0.0
        trades = []

        print("\n" + "=" * 100)
        print(f"  SMART KALSHI TRADER - {'DRY RUN' if dry_run else 'LIVE TRADING'}")
        print("=" * 100)
        print(f"  BTC Price: ${self.current_price:,.2f}")
        print(f"  Direction: {self.signals['direction']} (score: {self.signals['direction_score']:+.2f})")
        print(f"  RSI: {self.signals['rsi']:.1f}")
        print(f"  Balance: ${balance:,.2f}")
        print("=" * 100)

        if not opportunities:
            print("\n  No opportunities meeting criteria.")
            return [], 0

        print(f"\n  Found {len(opportunities)} opportunities:\n")
        print(f"  {'Ticker':<32} {'Market':<24} {'Side':<4} {'Hrs':>5} {'Price':>6} {'Model':>6} {'EV':>7}")
        print("-" * 100)

        for opp in opportunities:
            market_type = opp.get('market_type', 'range')
            side = opp.get('side', 'yes').upper()
            price = opp.get('price', opp.get('yes_ask', 0))

            if market_type == 'threshold':
                direction = '>' if opp.get('is_above') else '<'
                market_str = f"${opp['threshold']:,.0f} {direction}"
            else:
                market_str = f"${opp['lower']:,.0f}-${opp['upper']:,.0f}"

            print(f"  {opp['ticker']:<32} {market_str:<24} {side:<4} {opp['hours']:>4.1f}h "
                  f"{price:>5}c {opp['model_prob']:>5.0%} {opp['adjusted_ev']:>+6.1%}")

        print("\n" + "-" * 100)
        print("  EXECUTING TRADES")
        print("-" * 100)

        for opp in opportunities:
            if total_risked >= MAX_TOTAL_RISK:
                print(f"\n  Budget exhausted (${total_risked:.2f} / ${MAX_TOTAL_RISK:.2f})")
                break

            market_type = opp.get('market_type', 'range')
            side = opp.get('side', 'yes')
            price = opp.get('price', opp.get('yes_ask', 0))

            # Position sizing: QUANT-GRADE approach using ML size multiplier
            available = min(MAX_TOTAL_RISK - total_risked, balance * 0.1)
            cost_per_contract = price / 100.0
            max_contracts = int(available / cost_per_contract) if cost_per_contract > 0 else 0

            # Get ML size multiplier from opportunity (calculated during analysis)
            ml_size_multiplier = opp.get('ml_size_multiplier', 1.0)

            # Base sizing: Kelly-inspired fraction based on EV and uncertainty
            ev_adjusted = opp.get('ev_adjusted', 1.0)
            base_fraction = min(0.3, max(0.05, ev_adjusted * 0.1))  # Scale EV to fraction

            # Apply ML multiplier (0.5x to 1.5x based on ML confidence)
            adjusted_fraction = base_fraction * ml_size_multiplier

            position = int(max_contracts * adjusted_fraction)
            position = min(position, MAX_POSITION_SIZE)
            position = max(1, position)

            cost = position * cost_per_contract
            potential_profit = position * (1.0 - cost_per_contract)

            print(f"\n  {opp['ticker']}")
            if market_type == 'threshold':
                direction = 'ABOVE' if opp.get('is_above') else 'BELOW'
                print(f"    Threshold: ${opp['threshold']:,.0f} or {direction}")
            else:
                print(f"    Range: ${opp['lower']:,.0f} - ${opp['upper']:,.0f}")
            print(f"    Model: {opp['model_prob']:.1%} | Market: {opp['market_prob']:.1%} | Price: {price}c")
            print(f"    Raw EV: {opp.get('ev', 0):+.1%} | Risk-Adj EV: {opp.get('ev_adjusted', 0):+.2f}σ | Time-Wt EV: {opp.get('ev_time_weighted', 0):+.2%}")
            print(f"    ML Size Mult: {ml_size_multiplier:.2f}x | Signal Conf: {opp.get('signal_confidence', 0):.2f}")
            print(f"    Order: BUY {position} {side.upper()} @ {price}c = ${cost:.2f}")
            print(f"    Potential profit: ${potential_profit:.2f} ({potential_profit/cost*100:.0f}% return)")

            if not dry_run:
                result = self.kalshi.place_order(
                    ticker=opp['ticker'],
                    side=side,
                    quantity=position,
                    price=price,
                    order_type='limit'
                )

                if result:
                    print(f"    ✓ ORDER PLACED: {result.get('order_id', 'N/A')}")
                    trades.append({
                        'ticker': opp['ticker'],
                        'side': side,
                        'quantity': position,
                        'price': price,
                        'cost': cost,
                        'model_prob': opp['model_prob'],
                        'adjusted_ev': opp['adjusted_ev'],
                        'order_id': result.get('order_id')
                    })
                    total_risked += cost
                else:
                    print(f"    ✗ ORDER FAILED")
            else:
                print(f"    [DRY RUN]")
                trades.append({
                    'ticker': opp['ticker'],
                    'side': side,
                    'quantity': position,
                    'price': price,
                    'cost': cost,
                    'model_prob': opp['model_prob'],
                    'adjusted_ev': opp['adjusted_ev'],
                    'order_id': 'DRY_RUN'
                })
                total_risked += cost

        # Summary
        print("\n" + "=" * 100)
        print("  SUMMARY")
        print("=" * 100)
        print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        print(f"  Trades: {len(trades)}")
        print(f"  Total risked: ${total_risked:.2f}")

        if trades:
            avg_prob = np.mean([t['model_prob'] for t in trades])
            avg_ev = np.mean([t['adjusted_ev'] for t in trades])
            print(f"  Avg model probability: {avg_prob:.1%}")
            print(f"  Avg adjusted EV: {avg_ev:+.1%}")

        print("=" * 100 + "\n")

        return trades, total_risked


# =============================================================================
# MAIN
# =============================================================================

def main(dry_run=True, retrain=False, threshold_only=False):
    """Main entry point."""

    trader = SmartKalshiTrader()

    # Initialize
    trader.initialize()

    # Optionally retrain ML model
    if retrain:
        logger.info("Retraining ML model...")
        trader.train_ml_model()

    # Analyze markets (both range and threshold)
    if threshold_only:
        opportunities = trader.analyze_threshold_markets()
    else:
        opportunities = trader.analyze_all_markets()

    # Execute trades
    trades, total_risked = trader.execute_trades(opportunities, dry_run=dry_run)

    return trades


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Smart Kalshi BTC Trader with ML (Quant-Grade v2)')
    parser.add_argument('--live', action='store_true', help='Execute live trades')
    parser.add_argument('--retrain', action='store_true', help='Retrain ML model')
    parser.add_argument('--min-ev-adj', type=float, default=0.5, help='Minimum risk-adjusted EV (EV/σ)')
    parser.add_argument('--min-ev-raw', type=float, default=0.01, help='Minimum raw EV')
    parser.add_argument('--max-risk', type=float, default=100.0, help='Max total risk in dollars')

    args = parser.parse_args()

    if args.min_ev_adj:
        MIN_EV_ADJUSTED = args.min_ev_adj
    if args.min_ev_raw:
        MIN_EV_RAW = args.min_ev_raw
    if args.max_risk:
        MAX_TOTAL_RISK = args.max_risk

    trades = main(dry_run=not args.live, retrain=args.retrain)
