"""
Market Data Service
Fetches and caches historical BTC market data for the enhanced hedge optimizer.
"""

import os
import json
import logging
import requests
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class MarketDataService:
    """
    Service for fetching and caching historical BTC market data.

    Data sources:
    - Primary: CoinGecko API (free, reliable)
    - Fallback: Coinbase API
    """

    COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
    COINBASE_BASE_URL = "https://api.coinbase.com/v2"

    def __init__(
        self,
        cache_dir: str = None,
        cache_ttl_hours: int = 24
    ):
        """
        Initialize the market data service.

        Args:
            cache_dir: Directory for storing cached data
            cache_ttl_hours: Cache time-to-live in hours
        """
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), "cache")

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl_hours = cache_ttl_hours

        # Cache for in-memory data
        self._ohlc_cache: Optional[pd.DataFrame] = None
        self._cache_timestamp: Optional[datetime] = None

        logger.info(f"MarketDataService initialized with cache at {self.cache_dir}")

    def fetch_ohlc_data(
        self,
        symbol: str = "bitcoin",
        days: int = 365,
        vs_currency: str = "usd",
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Fetch historical OHLC data for BTC.

        Args:
            symbol: Coin symbol (default: bitcoin)
            days: Number of days of history (default: 365)
            vs_currency: Quote currency (default: usd)
            force_refresh: Bypass cache if True

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        cache_key = f"{symbol}_{days}d_{vs_currency}"

        # Check in-memory cache first
        if not force_refresh and self._is_cache_valid():
            logger.info("Using in-memory cached OHLC data")
            return self._ohlc_cache

        # Check file cache
        if not force_refresh:
            cached_data = self._load_from_cache(cache_key)
            if cached_data is not None:
                self._ohlc_cache = cached_data
                self._cache_timestamp = datetime.now()
                return cached_data

        # Fetch fresh data
        logger.info(f"Fetching {days} days of {symbol} data from CoinGecko")
        try:
            df = self._fetch_from_coingecko(symbol, days, vs_currency)
        except Exception as e:
            logger.warning(f"CoinGecko fetch failed: {e}, trying Coinbase fallback")
            try:
                df = self._fetch_from_coinbase(f"{symbol.upper()}-USD", days)
            except Exception as e2:
                logger.error(f"Both data sources failed: {e2}")
                raise RuntimeError(f"Failed to fetch market data: {e}, {e2}")

        # Cache the data
        self._save_to_cache(cache_key, df)
        self._ohlc_cache = df
        self._cache_timestamp = datetime.now()

        return df

    def calculate_log_returns(self, prices: pd.Series = None) -> pd.Series:
        """
        Calculate log returns from price series.

        Args:
            prices: Price series (uses cached close prices if None)

        Returns:
            Series of log returns
        """
        if prices is None:
            if self._ohlc_cache is None:
                self.fetch_ohlc_data()
            prices = self._ohlc_cache['close']

        log_returns = np.log(prices / prices.shift(1)).dropna()
        return log_returns

    def calculate_empirical_drawdown_distribution(
        self,
        prices: pd.Series = None,
        window_days: int = 30
    ) -> Dict:
        """
        Calculate empirical drawdown distribution from historical data.

        Args:
            prices: Price series
            window_days: Rolling window for drawdown calculation

        Returns:
            Dict with percentiles and probability density at various drawdown levels
        """
        if prices is None:
            if self._ohlc_cache is None:
                self.fetch_ohlc_data()
            prices = self._ohlc_cache['close']

        # Calculate rolling max and drawdowns
        rolling_max = prices.rolling(window=window_days, min_periods=1).max()
        drawdowns = (prices - rolling_max) / rolling_max

        # Calculate percentiles
        percentiles = {
            'p5': float(np.percentile(drawdowns, 5)),
            'p10': float(np.percentile(drawdowns, 10)),
            'p25': float(np.percentile(drawdowns, 25)),
            'p50': float(np.percentile(drawdowns, 50)),
            'p75': float(np.percentile(drawdowns, 75)),
            'p90': float(np.percentile(drawdowns, 90)),
            'p95': float(np.percentile(drawdowns, 95)),
        }

        # Calculate probability of reaching specific drawdown levels
        drawdown_levels = [-0.05, -0.10, -0.15, -0.20, -0.25, -0.30, -0.40, -0.50]
        probabilities = {}
        for level in drawdown_levels:
            prob = float((drawdowns <= level).mean())
            probabilities[f"{int(level*100)}%"] = prob

        # Calculate statistics
        stats = {
            'mean': float(drawdowns.mean()),
            'std': float(drawdowns.std()),
            'min': float(drawdowns.min()),
            'max': float(drawdowns.max()),
            'skew': float(drawdowns.skew()),
            'kurtosis': float(drawdowns.kurtosis()),
        }

        return {
            'percentiles': percentiles,
            'probabilities': probabilities,
            'stats': stats,
            'window_days': window_days,
            'data_points': len(drawdowns)
        }

    def get_drawdown_probability(
        self,
        drawdown_level: float,
        prices: pd.Series = None,
        window_days: int = 30
    ) -> float:
        """
        Get empirical probability of reaching a specific drawdown level.

        Args:
            drawdown_level: Target drawdown (e.g., -0.20 for -20%)
            prices: Optional price series (uses cached if None)
            window_days: Rolling window for drawdown calculation

        Returns:
            Probability (0-1) of reaching that drawdown
        """
        if prices is None:
            if self._ohlc_cache is None:
                self.fetch_ohlc_data()
            prices = self._ohlc_cache['close']

        rolling_max = prices.rolling(window=window_days, min_periods=1).max()
        drawdowns = (prices - rolling_max) / rolling_max

        return float((drawdowns <= drawdown_level).mean())

    def get_current_price(self) -> float:
        """Get the most recent BTC price from cache or fetch."""
        if self._ohlc_cache is None or len(self._ohlc_cache) == 0:
            self.fetch_ohlc_data()

        return float(self._ohlc_cache['close'].iloc[-1])

    def get_price_at_date(self, date: datetime) -> Optional[float]:
        """Get BTC price at a specific date."""
        if self._ohlc_cache is None:
            self.fetch_ohlc_data()

        df = self._ohlc_cache
        mask = df['timestamp'].dt.date == date.date()
        if mask.any():
            return float(df.loc[mask, 'close'].iloc[0])
        return None

    def calculate_realized_volatility(
        self,
        window_days: int = 30,
        annualize: bool = True
    ) -> float:
        """
        Calculate realized volatility from historical returns.

        Args:
            window_days: Number of days for volatility calculation
            annualize: If True, annualize the volatility

        Returns:
            Realized volatility (annualized if specified)
        """
        log_returns = self.calculate_log_returns()

        if len(log_returns) < window_days:
            window_days = len(log_returns)

        vol = log_returns.tail(window_days).std()

        if annualize:
            vol = vol * np.sqrt(365)  # Crypto trades 365 days

        return float(vol)

    def calculate_historical_var(
        self,
        confidence_level: float = 0.95,
        horizon_days: int = 30
    ) -> Dict:
        """
        Calculate historical Value at Risk.

        Args:
            confidence_level: VaR confidence level (e.g., 0.95 for 95%)
            horizon_days: Time horizon in days

        Returns:
            Dict with VaR metrics
        """
        if self._ohlc_cache is None:
            self.fetch_ohlc_data()

        prices = self._ohlc_cache['close']

        # Calculate returns over the horizon
        returns = (prices / prices.shift(horizon_days) - 1).dropna()

        # Calculate VaR at confidence level
        var_pct = np.percentile(returns, (1 - confidence_level) * 100)

        # Calculate CVaR (Expected Shortfall)
        cvar_pct = returns[returns <= var_pct].mean()

        current_price = float(prices.iloc[-1])

        return {
            'var_pct': float(var_pct),
            'var_usd': float(var_pct * current_price),
            'cvar_pct': float(cvar_pct),
            'cvar_usd': float(cvar_pct * current_price),
            'confidence_level': confidence_level,
            'horizon_days': horizon_days,
            'current_price': current_price
        }

    def _is_cache_valid(self) -> bool:
        """Check if in-memory cache is still valid."""
        if self._ohlc_cache is None or self._cache_timestamp is None:
            return False

        age = datetime.now() - self._cache_timestamp
        return age < timedelta(hours=self.cache_ttl_hours)

    def _load_from_cache(self, cache_key: str) -> Optional[pd.DataFrame]:
        """Load data from file cache if valid."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        meta_file = self.cache_dir / f"{cache_key}_meta.json"

        if not cache_file.exists() or not meta_file.exists():
            return None

        # Check if cache is expired
        try:
            with open(meta_file, 'r') as f:
                meta = json.load(f)

            cached_time = datetime.fromisoformat(meta['timestamp'])
            if datetime.now() - cached_time > timedelta(hours=self.cache_ttl_hours):
                logger.info("File cache expired")
                return None

            # Load the data
            with open(cache_file, 'r') as f:
                data = json.load(f)

            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            logger.info(f"Loaded {len(df)} rows from cache")
            return df

        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return None

    def _save_to_cache(self, cache_key: str, df: pd.DataFrame) -> None:
        """Save data to file cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        meta_file = self.cache_dir / f"{cache_key}_meta.json"

        try:
            # Save data
            data = df.copy()
            data['timestamp'] = data['timestamp'].astype(str)
            with open(cache_file, 'w') as f:
                json.dump(data.to_dict(orient='records'), f)

            # Save metadata
            meta = {
                'timestamp': datetime.now().isoformat(),
                'rows': len(df),
                'cache_key': cache_key
            }
            with open(meta_file, 'w') as f:
                json.dump(meta, f)

            logger.info(f"Saved {len(df)} rows to cache")

        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _fetch_from_coingecko(
        self,
        symbol: str,
        days: int,
        vs_currency: str
    ) -> pd.DataFrame:
        """Fetch data from CoinGecko API."""
        # CoinGecko market_chart endpoint
        url = f"{self.COINGECKO_BASE_URL}/coins/{symbol}/market_chart"
        params = {
            'vs_currency': vs_currency,
            'days': days,
            'interval': 'daily'
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Parse prices
        prices = data.get('prices', [])
        if not prices:
            raise ValueError("No price data returned from CoinGecko")

        # Create DataFrame
        df = pd.DataFrame(prices, columns=['timestamp', 'close'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # For OHLC, we'll use close as approximation for daily data
        # CoinGecko doesn't provide full OHLC for free
        df['open'] = df['close'].shift(1).fillna(df['close'])
        df['high'] = df['close']
        df['low'] = df['close']

        # Add volume if available
        volumes = data.get('total_volumes', [])
        if volumes:
            vol_df = pd.DataFrame(volumes, columns=['timestamp', 'volume'])
            vol_df['timestamp'] = pd.to_datetime(vol_df['timestamp'], unit='ms')
            df = df.merge(vol_df, on='timestamp', how='left')
        else:
            df['volume'] = 0

        df = df.sort_values('timestamp').reset_index(drop=True)

        logger.info(f"Fetched {len(df)} days from CoinGecko")
        return df

    def _fetch_from_coinbase(self, product_id: str, days: int) -> pd.DataFrame:
        """Fetch data from Coinbase API as fallback."""
        # Coinbase historic rates endpoint
        url = f"https://api.exchange.coinbase.com/products/{product_id}/candles"

        # Coinbase returns max 300 candles per request
        # For daily granularity (86400 seconds)
        granularity = 86400

        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)

        params = {
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
            'granularity': granularity
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        candles = response.json()

        if not candles:
            raise ValueError("No candle data returned from Coinbase")

        # Coinbase returns: [timestamp, low, high, open, close, volume]
        df = pd.DataFrame(candles, columns=['timestamp', 'low', 'high', 'open', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.sort_values('timestamp').reset_index(drop=True)

        logger.info(f"Fetched {len(df)} days from Coinbase")
        return df

    def get_summary(self) -> Dict:
        """Get a summary of the current market data state."""
        if self._ohlc_cache is None:
            return {'status': 'no_data', 'message': 'No data loaded'}

        df = self._ohlc_cache

        return {
            'status': 'loaded',
            'rows': len(df),
            'date_range': {
                'start': str(df['timestamp'].min()),
                'end': str(df['timestamp'].max())
            },
            'price_range': {
                'min': float(df['close'].min()),
                'max': float(df['close'].max()),
                'current': float(df['close'].iloc[-1])
            },
            'cache_age_hours': (
                (datetime.now() - self._cache_timestamp).total_seconds() / 3600
                if self._cache_timestamp else None
            )
        }


# Singleton instance for easy access
_market_data_service: Optional[MarketDataService] = None


def get_market_data_service() -> MarketDataService:
    """Get or create the singleton MarketDataService instance."""
    global _market_data_service
    if _market_data_service is None:
        _market_data_service = MarketDataService()
    return _market_data_service


if __name__ == "__main__":
    # Test the service
    logging.basicConfig(level=logging.INFO)

    service = MarketDataService()

    print("Fetching OHLC data...")
    df = service.fetch_ohlc_data(days=365)
    print(f"Fetched {len(df)} rows")
    print(df.tail())

    print("\nLog returns:")
    returns = service.calculate_log_returns()
    print(f"Mean: {returns.mean():.4f}, Std: {returns.std():.4f}")

    print("\nDrawdown distribution:")
    dd = service.calculate_empirical_drawdown_distribution()
    print(f"Percentiles: {dd['percentiles']}")
    print(f"Probabilities: {dd['probabilities']}")

    print("\nRealized volatility (30d, annualized):")
    vol = service.calculate_realized_volatility()
    print(f"Vol: {vol:.2%}")

    print("\nHistorical VaR (95%, 30d):")
    var = service.calculate_historical_var()
    print(f"VaR: {var['var_pct']:.2%}, CVaR: {var['cvar_pct']:.2%}")
