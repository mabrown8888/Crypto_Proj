#!/usr/bin/env python3
"""
Enhanced Data Service for Kalshi ML Trader

Fetches and processes:
1. Funding Rates (Binance Perpetuals)
2. Fear & Greed Index
3. Kalshi Historical Outcomes
4. Whale Movements (large BTC transactions)
"""

import os
import json
import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache directory
CACHE_DIR = Path(__file__).parent / 'cache' / 'enhanced_data'
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# 1. FUNDING RATES
# =============================================================================

class FundingRateService:
    """
    Fetch perpetual futures funding rates.

    Funding rates indicate market sentiment:
    - Positive funding = longs pay shorts = market is bullish (crowded long)
    - Negative funding = shorts pay longs = market is bearish (crowded short)

    Extreme funding often leads to reversals.
    """

    def __init__(self):
        self.cache_file = CACHE_DIR / 'funding_rates.json'
        self.cache_duration = 300  # 5 minutes

    def get_coingecko_funding(self) -> Dict:
        """Get funding rate from CoinGecko derivatives API (free, no API key needed)."""
        try:
            url = "https://api.coingecko.com/api/v3/derivatives"
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()

            # Find Binance BTCUSDT perpetual
            for item in data:
                if item.get('market') == 'Binance (Futures)' and item.get('symbol') == 'BTCUSDT':
                    funding_rate = item.get('funding_rate', 0) / 100  # Convert from percentage

                    return {
                        'current_rate': funding_rate,
                        'rate_8h_pct': funding_rate * 100,
                        'rate_annual_pct': funding_rate * 100 * 3 * 365,
                        'open_interest': item.get('open_interest', 0),
                        'volume_24h': item.get('volume_24h', 0),
                        'signal': self._interpret_funding(funding_rate),
                        'source': 'coingecko'
                    }

            logger.warning("BTCUSDT not found in CoinGecko derivatives")
            return self._get_fallback_funding()

        except Exception as e:
            logger.warning(f"Failed to get CoinGecko funding: {e}")
            return self._get_fallback_funding()

    def get_binance_funding(self) -> Dict:
        """Get current funding rate from Binance (may be geo-blocked)."""
        try:
            # Current funding rate
            url = "https://fapi.binance.com/fapi/v1/fundingRate"
            params = {'symbol': 'BTCUSDT', 'limit': 1}
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()

            if data:
                current_rate = float(data[0]['fundingRate'])
                funding_time = datetime.fromtimestamp(data[0]['fundingTime'] / 1000)
            else:
                current_rate = 0
                funding_time = None

            # Get predicted/mark funding rate
            url_premium = "https://fapi.binance.com/fapi/v1/premiumIndex"
            params = {'symbol': 'BTCUSDT'}
            r = requests.get(url_premium, params=params, timeout=10)
            r.raise_for_status()
            premium_data = r.json()

            predicted_rate = float(premium_data.get('lastFundingRate', 0))

            return {
                'current_rate': current_rate,
                'predicted_rate': predicted_rate,
                'funding_time': funding_time.isoformat() if funding_time else None,
                'rate_8h_pct': current_rate * 100,  # As percentage
                'rate_annual_pct': current_rate * 100 * 3 * 365,  # Annualized
                'signal': self._interpret_funding(current_rate),
                'source': 'binance'
            }

        except Exception as e:
            logger.warning(f"Failed to get Binance funding: {e}")
            # Try CoinGecko as fallback
            return self.get_coingecko_funding()

    def get_bybit_funding(self) -> Dict:
        """Get funding rate from Bybit as backup."""
        try:
            url = "https://api.bybit.com/v5/market/tickers"
            params = {'category': 'linear', 'symbol': 'BTCUSDT'}
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()

            if data.get('result', {}).get('list'):
                ticker = data['result']['list'][0]
                funding_rate = float(ticker.get('fundingRate', 0))

                return {
                    'current_rate': funding_rate,
                    'rate_8h_pct': funding_rate * 100,
                    'rate_annual_pct': funding_rate * 100 * 3 * 365,
                    'signal': self._interpret_funding(funding_rate),
                    'source': 'bybit'
                }
        except Exception as e:
            logger.warning(f"Failed to get Bybit funding: {e}")

        return self._get_fallback_funding()

    def _interpret_funding(self, rate: float) -> Dict:
        """Interpret funding rate signal."""
        # Typical funding is 0.01% (0.0001)
        # Extreme is > 0.05% or < -0.02%

        if rate > 0.001:  # > 0.1%
            return {'direction': 'BEARISH', 'strength': 'extreme', 'reason': 'Extremely crowded longs, expect pullback'}
        elif rate > 0.0005:  # > 0.05%
            return {'direction': 'BEARISH', 'strength': 'strong', 'reason': 'High funding, longs overextended'}
        elif rate > 0.0001:  # > 0.01%
            return {'direction': 'NEUTRAL', 'strength': 'normal', 'reason': 'Normal positive funding'}
        elif rate > -0.0001:
            return {'direction': 'NEUTRAL', 'strength': 'low', 'reason': 'Neutral funding'}
        elif rate > -0.0005:
            return {'direction': 'BULLISH', 'strength': 'strong', 'reason': 'Negative funding, shorts overextended'}
        else:
            return {'direction': 'BULLISH', 'strength': 'extreme', 'reason': 'Extremely negative funding, expect bounce'}

    def _get_fallback_funding(self) -> Dict:
        """Return neutral funding if APIs fail."""
        return {
            'current_rate': 0.0001,
            'rate_8h_pct': 0.01,
            'rate_annual_pct': 10.95,
            'signal': {'direction': 'NEUTRAL', 'strength': 'unknown', 'reason': 'API unavailable'},
            'source': 'fallback'
        }

    def get_funding(self) -> Dict:
        """Get funding rate with caching. Prioritizes working APIs."""
        # Check cache
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    cached = json.load(f)
                cache_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
                if (datetime.now() - cache_time).total_seconds() < self.cache_duration:
                    # Only use cache if it's real data (not fallback)
                    if cached.get('source') != 'fallback':
                        return cached
            except:
                pass

        # Try CoinGecko first (most reliable, free, no geo-blocking)
        data = self.get_coingecko_funding()

        # If CoinGecko failed, try Binance
        if data.get('source') == 'fallback':
            data = self.get_binance_funding()

        # If still fallback, try Bybit
        if data.get('source') == 'fallback':
            data = self.get_bybit_funding()

        data['timestamp'] = datetime.now().isoformat()

        # Only cache if we got real data
        if data.get('source') != 'fallback':
            with open(self.cache_file, 'w') as f:
                json.dump(data, f)

        return data


# =============================================================================
# 2. FEAR & GREED INDEX
# =============================================================================

class FearGreedService:
    """
    Fetch Crypto Fear & Greed Index.

    Scale: 0-100
    - 0-25: Extreme Fear (potential buy signal)
    - 25-45: Fear
    - 45-55: Neutral
    - 55-75: Greed
    - 75-100: Extreme Greed (potential sell signal)
    """

    def __init__(self):
        self.cache_file = CACHE_DIR / 'fear_greed.json'
        self.cache_duration = 3600  # 1 hour (updates daily anyway)

    def fetch_fear_greed(self) -> Dict:
        """Fetch Fear & Greed Index from alternative.me."""
        try:
            url = "https://api.alternative.me/fng/"
            params = {'limit': 7}  # Get last 7 days for trend
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()

            if data.get('data'):
                current = data['data'][0]
                value = int(current['value'])
                classification = current['value_classification']

                # Calculate trend (is fear/greed increasing or decreasing?)
                if len(data['data']) >= 3:
                    recent_values = [int(d['value']) for d in data['data'][:3]]
                    trend = recent_values[0] - recent_values[2]  # Positive = increasing greed
                else:
                    trend = 0

                # 7-day average
                all_values = [int(d['value']) for d in data['data']]
                avg_7d = np.mean(all_values)

                return {
                    'value': value,
                    'classification': classification,
                    'trend_3d': trend,
                    'avg_7d': avg_7d,
                    'signal': self._interpret_fear_greed(value, trend),
                    'timestamp': datetime.now().isoformat(),
                    'source': 'alternative.me'
                }

        except Exception as e:
            logger.warning(f"Failed to get Fear & Greed: {e}")

        return {
            'value': 50,
            'classification': 'Neutral',
            'trend_3d': 0,
            'avg_7d': 50,
            'signal': {'direction': 'NEUTRAL', 'strength': 'unknown'},
            'timestamp': datetime.now().isoformat(),
            'source': 'fallback'
        }

    def _interpret_fear_greed(self, value: int, trend: int) -> Dict:
        """Interpret Fear & Greed signal."""
        if value <= 20:
            direction = 'BULLISH'
            strength = 'extreme'
            reason = 'Extreme fear - historically good buying opportunity'
        elif value <= 35:
            direction = 'BULLISH'
            strength = 'strong'
            reason = 'Fear in market - contrarian bullish'
        elif value <= 50:
            direction = 'NEUTRAL'
            strength = 'mild_bearish' if trend < -5 else 'neutral'
            reason = 'Neutral to fearful'
        elif value <= 65:
            direction = 'NEUTRAL'
            strength = 'mild_bullish' if trend > 5 else 'neutral'
            reason = 'Neutral to greedy'
        elif value <= 80:
            direction = 'BEARISH'
            strength = 'strong'
            reason = 'Greed in market - contrarian bearish'
        else:
            direction = 'BEARISH'
            strength = 'extreme'
            reason = 'Extreme greed - historically good selling point'

        return {'direction': direction, 'strength': strength, 'reason': reason}

    def get_fear_greed(self) -> Dict:
        """Get Fear & Greed with caching."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    cached = json.load(f)
                cache_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
                if (datetime.now() - cache_time).total_seconds() < self.cache_duration:
                    return cached
            except:
                pass

        data = self.fetch_fear_greed()

        with open(self.cache_file, 'w') as f:
            json.dump(data, f)

        return data


# =============================================================================
# 3. KALSHI HISTORICAL OUTCOMES
# =============================================================================

class KalshiHistoricalService:
    """
    Fetch and analyze historical Kalshi BTC market outcomes.
    """

    def __init__(self, kalshi_engine=None):
        self.kalshi = kalshi_engine
        self.cache_file = CACHE_DIR / 'kalshi_historical.json'
        self.cache_duration = 3600  # 1 hour

    def fetch_settled_markets(self, days_back: int = 30) -> List[Dict]:
        """Fetch settled KXBTC and KXBTCD markets."""
        if not self.kalshi:
            logger.warning("No Kalshi engine provided")
            return []

        all_markets = []

        for series in ['KXBTC', 'KXBTCD']:
            try:
                result = self.kalshi._make_authenticated_request(
                    'GET',
                    f'/markets?series_ticker={series}&status=settled&limit=500'
                )
                markets = result.get('markets', []) if result else []
                all_markets.extend(markets)
                logger.info(f"Fetched {len(markets)} settled {series} markets")
            except Exception as e:
                logger.warning(f"Failed to fetch {series} settled markets: {e}")

        return all_markets

    def analyze_historical_patterns(self, markets: List[Dict]) -> Dict:
        """Analyze patterns in historical outcomes."""
        if not markets:
            return {}

        # Parse outcomes
        outcomes = []
        for m in markets:
            ticker = m.get('ticker', '')
            result = m.get('result', '')  # 'yes' or 'no'

            if not result:
                continue

            # Parse ticker for info
            parts = ticker.split('-')
            if len(parts) < 3:
                continue

            series = parts[0]
            date_part = parts[1]
            strike_part = parts[2]

            # Extract hour of day
            try:
                hour = int(date_part[7:9]) if len(date_part) >= 9 else 16
            except:
                hour = 16

            # Extract day of week (would need actual date parsing)
            # For now, just use the data we have

            # Determine market type
            if strike_part.startswith('B'):
                market_type = 'range'
            elif strike_part.startswith('T'):
                market_type = 'directional'
            else:
                market_type = 'unknown'

            outcomes.append({
                'ticker': ticker,
                'series': series,
                'market_type': market_type,
                'hour': hour,
                'result': 1 if result == 'yes' else 0,
            })

        df = pd.DataFrame(outcomes)

        if df.empty:
            return {}

        # Calculate statistics
        stats = {
            'total_markets': len(df),
            'overall_yes_rate': df['result'].mean(),
            'by_type': {},
            'by_hour': {},
        }

        # By market type
        for mtype in df['market_type'].unique():
            subset = df[df['market_type'] == mtype]
            stats['by_type'][mtype] = {
                'count': len(subset),
                'yes_rate': subset['result'].mean()
            }

        # By hour
        for hour in sorted(df['hour'].unique()):
            subset = df[df['hour'] == hour]
            if len(subset) >= 10:  # Only if we have enough data
                stats['by_hour'][int(hour)] = {
                    'count': len(subset),
                    'yes_rate': subset['result'].mean()
                }

        return stats

    def get_historical_stats(self) -> Dict:
        """Get historical statistics with caching."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    cached = json.load(f)
                cache_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
                if (datetime.now() - cache_time).total_seconds() < self.cache_duration:
                    return cached
            except:
                pass

        markets = self.fetch_settled_markets()
        stats = self.analyze_historical_patterns(markets)
        stats['timestamp'] = datetime.now().isoformat()

        with open(self.cache_file, 'w') as f:
            json.dump(stats, f)

        return stats


# =============================================================================
# 4. WHALE MOVEMENTS
# =============================================================================

class WhaleTrackingService:
    """
    Track large BTC transactions (whale movements).

    Large inflows to exchanges = bearish (selling pressure)
    Large outflows from exchanges = bullish (accumulation)
    """

    def __init__(self):
        self.cache_file = CACHE_DIR / 'whale_data.json'
        self.cache_duration = 300  # 5 minutes

        # Known exchange addresses (simplified - in production use comprehensive list)
        self.exchange_addresses = {
            'binance', 'coinbase', 'kraken', 'bitfinex', 'huobi',
            'okex', 'bybit', 'kucoin', 'gemini', 'bitstamp'
        }

    def fetch_whale_alert_data(self) -> Dict:
        """
        Fetch large transactions from public APIs.
        Uses blockchain.com mempool and Blockchair for real data.
        """
        transactions = []
        mempool_stats = {}

        # 1. Get Blockchair mempool stats (always works)
        try:
            url = "https://api.blockchair.com/bitcoin/stats"
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            data = r.json().get('data', {})

            mempool_stats = {
                'mempool_transactions': data.get('mempool_transactions', 0),
                'mempool_size_mb': data.get('mempool_size', 0) / 1e6,
                'mempool_tps': data.get('mempool_tps', 0),
                'mempool_total_fee_usd': data.get('mempool_total_fee_usd', 0),
                'volume_24h_btc': data.get('volume_24h', 0) / 1e8,
                'transactions_24h': data.get('transactions_24h', 0),
            }
            logger.info(f"Blockchair: {mempool_stats['mempool_transactions']} mempool txs, "
                       f"{mempool_stats['volume_24h_btc']:,.0f} BTC 24h volume")

        except Exception as e:
            logger.warning(f"Failed to fetch Blockchair stats: {e}")

        # 2. Get blockchain.com unconfirmed transactions for large txs
        try:
            url = "https://blockchain.info/unconfirmed-transactions?format=json"
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            data = r.json()

            # Get current BTC price for USD conversion
            try:
                price_r = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=5)
                btc_price = float(price_r.json()['data']['amount'])
            except:
                btc_price = 95000

            for tx in data.get('txs', [])[:200]:
                # Calculate total output value
                total_value = sum(out.get('value', 0) for out in tx.get('out', []))
                total_btc = total_value / 1e8

                if total_btc >= 50:  # 50+ BTC transactions (lowered threshold)
                    tx_time = tx.get('time', 0)
                    transactions.append({
                        'hash': tx.get('hash', '')[:16] + '...',
                        'value_btc': total_btc,
                        'value_usd': total_btc * btc_price,
                        'time': datetime.fromtimestamp(tx_time).isoformat() if tx_time else None,
                        'inputs': len(tx.get('inputs', [])),
                        'outputs': len(tx.get('out', [])),
                    })

            logger.info(f"Blockchain.com: Found {len(transactions)} large transactions (50+ BTC)")

        except Exception as e:
            logger.warning(f"Failed to fetch blockchain.info data: {e}")

        # Analyze the transactions
        if transactions:
            total_volume = sum(t['value_btc'] for t in transactions)
            avg_size = np.mean([t['value_btc'] for t in transactions])
            large_tx_count = len([t for t in transactions if t['value_btc'] >= 500])
            very_large_count = len([t for t in transactions if t['value_btc'] >= 1000])

            return {
                'recent_large_txs': len(transactions),
                'total_volume_btc': total_volume,
                'avg_tx_size_btc': avg_size,
                'large_txs_500plus': large_tx_count,
                'very_large_txs_1000plus': very_large_count,
                'transactions': sorted(transactions, key=lambda x: -x['value_btc'])[:10],
                'mempool_stats': mempool_stats,
                'signal': self._interpret_whale_activity(transactions),
                'timestamp': datetime.now().isoformat(),
                'source': 'blockchain.info + blockchair'
            }

        # If no large transactions found, still return mempool stats
        return {
            'recent_large_txs': 0,
            'total_volume_btc': 0,
            'avg_tx_size_btc': 0,
            'large_txs_500plus': 0,
            'very_large_txs_1000plus': 0,
            'transactions': [],
            'mempool_stats': mempool_stats,
            'signal': {'direction': 'NEUTRAL', 'strength': 'normal', 'reason': 'No large transactions in mempool'},
            'timestamp': datetime.now().isoformat(),
            'source': 'blockchair'
        }

    def fetch_exchange_flows(self) -> Dict:
        """
        Fetch exchange inflow/outflow data.
        Uses CryptoQuant-style metrics from public sources.
        """
        try:
            # Try Glassnode public endpoints or alternatives
            # For now, we'll estimate based on mempool activity

            # This would normally come from a paid API like:
            # - CryptoQuant
            # - Glassnode
            # - IntoTheBlock

            return {
                'net_flow_btc': 0,  # Positive = inflow (bearish), Negative = outflow (bullish)
                'inflow_btc': 0,
                'outflow_btc': 0,
                'signal': {'direction': 'NEUTRAL', 'reason': 'Exchange flow data unavailable'},
                'source': 'estimated'
            }

        except Exception as e:
            logger.warning(f"Failed to fetch exchange flows: {e}")
            return {}

    def _interpret_whale_activity(self, transactions: List[Dict]) -> Dict:
        """Interpret whale activity signal."""
        if not transactions:
            return {'direction': 'NEUTRAL', 'strength': 'unknown', 'reason': 'No data'}

        total_volume = sum(t['value_btc'] for t in transactions)
        large_count = len([t for t in transactions if t['value_btc'] >= 500])

        # High whale activity often precedes volatility
        if large_count >= 5:
            return {
                'direction': 'VOLATILE',
                'strength': 'high',
                'reason': f'{large_count} very large transactions detected - expect volatility'
            }
        elif total_volume >= 5000:
            return {
                'direction': 'VOLATILE',
                'strength': 'medium',
                'reason': f'High whale volume ({total_volume:.0f} BTC) - increased volatility likely'
            }
        else:
            return {
                'direction': 'NEUTRAL',
                'strength': 'normal',
                'reason': 'Normal whale activity'
            }

    def _get_fallback_whale_data(self) -> Dict:
        """Return neutral data if APIs fail."""
        return {
            'recent_large_txs': 0,
            'total_volume_btc': 0,
            'avg_tx_size_btc': 0,
            'very_large_txs': 0,
            'transactions': [],
            'signal': {'direction': 'NEUTRAL', 'strength': 'unknown', 'reason': 'API unavailable'},
            'timestamp': datetime.now().isoformat(),
            'source': 'fallback'
        }

    def get_whale_data(self) -> Dict:
        """Get whale data with caching."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    cached = json.load(f)
                cache_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
                if (datetime.now() - cache_time).total_seconds() < self.cache_duration:
                    return cached
            except:
                pass

        data = self.fetch_whale_alert_data()

        # Add exchange flow data
        exchange_flows = self.fetch_exchange_flows()
        data['exchange_flows'] = exchange_flows

        with open(self.cache_file, 'w') as f:
            json.dump(data, f)

        return data


# =============================================================================
# 5. DERIBIT OPTIONS DATA (IV, Skew)
# =============================================================================

class DeribitOptionsService:
    """
    Fetch options implied volatility and skew from Deribit.

    Deribit is the largest crypto options exchange.
    IV tells us what professionals expect for volatility.
    Skew tells us directional bias (put vs call pricing).
    """

    def __init__(self):
        self.cache_file = CACHE_DIR / 'deribit_options.json'
        self.cache_duration = 300  # 5 minutes
        self.base_url = "https://www.deribit.com/api/v2/public"

    def fetch_btc_index(self) -> float:
        """Get current BTC index price from Deribit."""
        try:
            url = f"{self.base_url}/get_index_price"
            params = {'index_name': 'btc_usd'}
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            return r.json()['result']['index_price']
        except:
            return 95000  # Fallback

    def fetch_dvol_index(self) -> Dict:
        """
        Fetch Deribit Volatility Index (DVOL) - the VIX of crypto.
        This is a 30-day implied volatility measure.
        """
        try:
            url = f"{self.base_url}/get_volatility_index_data"
            params = {
                'currency': 'BTC',
                'resolution': '3600',  # Hourly
                'start_timestamp': int((datetime.now() - timedelta(hours=24)).timestamp() * 1000),
                'end_timestamp': int(datetime.now().timestamp() * 1000)
            }
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()['result']['data']

            if data:
                # Data format: [timestamp, open, high, low, close]
                latest = data[-1]
                current_dvol = latest[4]  # close

                # Calculate 24h change
                if len(data) >= 24:
                    dvol_24h_ago = data[0][4]
                    change_24h = current_dvol - dvol_24h_ago
                else:
                    change_24h = 0

                # Get high/low for the day
                highs = [d[2] for d in data]
                lows = [d[3] for d in data]

                return {
                    'dvol': current_dvol,
                    'dvol_24h_change': change_24h,
                    'dvol_24h_high': max(highs),
                    'dvol_24h_low': min(lows),
                    'source': 'deribit'
                }
        except Exception as e:
            logger.warning(f"Failed to fetch DVOL: {e}")

        return {'dvol': 50, 'dvol_24h_change': 0, 'source': 'fallback'}

    def fetch_atm_iv(self) -> Dict:
        """
        Fetch ATM (at-the-money) implied volatility for different expirations.
        """
        try:
            btc_price = self.fetch_btc_index()

            # Get available instruments
            url = f"{self.base_url}/get_instruments"
            params = {'currency': 'BTC', 'kind': 'option', 'expired': 'false'}
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            instruments = r.json()['result']

            # Find ATM options for each expiry
            expirations = {}
            for inst in instruments:
                strike = inst['strike']
                expiry = inst['expiration_timestamp']
                option_type = inst['option_type']
                instrument_name = inst['instrument_name']

                # Check if near ATM (within 5% of current price)
                if abs(strike - btc_price) / btc_price < 0.05:
                    expiry_date = datetime.fromtimestamp(expiry / 1000)
                    days_to_expiry = (expiry_date - datetime.now()).days

                    if days_to_expiry > 0:
                        key = f"{days_to_expiry}d"
                        if key not in expirations:
                            expirations[key] = {'calls': [], 'puts': [], 'days': days_to_expiry}

                        if option_type == 'call':
                            expirations[key]['calls'].append(instrument_name)
                        else:
                            expirations[key]['puts'].append(instrument_name)

            # Get IV for closest expirations
            iv_by_expiry = {}
            target_expiries = ['7d', '14d', '30d']

            for target in target_expiries:
                # Find closest expiry to target
                closest = None
                closest_diff = float('inf')
                target_days = int(target.replace('d', ''))

                for key, data in expirations.items():
                    diff = abs(data['days'] - target_days)
                    if diff < closest_diff:
                        closest_diff = diff
                        closest = key

                if closest and expirations[closest]['calls']:
                    # Get IV from order book
                    inst_name = expirations[closest]['calls'][0]
                    try:
                        url = f"{self.base_url}/ticker"
                        params = {'instrument_name': inst_name}
                        r = requests.get(url, params=params, timeout=10)
                        r.raise_for_status()
                        ticker = r.json()['result']

                        iv_by_expiry[target] = {
                            'iv': ticker.get('mark_iv', 0),
                            'actual_days': expirations[closest]['days'],
                            'instrument': inst_name
                        }
                    except:
                        pass

            return {
                'atm_iv': iv_by_expiry,
                'btc_index': btc_price,
                'source': 'deribit'
            }

        except Exception as e:
            logger.warning(f"Failed to fetch ATM IV: {e}")
            return {'atm_iv': {}, 'source': 'fallback'}

    def fetch_option_skew(self) -> Dict:
        """
        Calculate put/call skew - tells us directional bias.

        Positive skew = puts more expensive = market fears downside
        Negative skew = calls more expensive = market expects upside
        """
        try:
            btc_price = self.fetch_btc_index()

            # Get instruments
            url = f"{self.base_url}/get_instruments"
            params = {'currency': 'BTC', 'kind': 'option', 'expired': 'false'}
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            instruments = r.json()['result']

            # Find 25-delta options (standard for skew calculation)
            # We'll approximate by looking at options ~5% OTM
            skew_data = {}

            for inst in instruments:
                strike = inst['strike']
                expiry = inst['expiration_timestamp']
                option_type = inst['option_type']
                instrument_name = inst['instrument_name']

                expiry_date = datetime.fromtimestamp(expiry / 1000)
                days_to_expiry = (expiry_date - datetime.now()).days

                # Look for 7-day and 30-day expirations
                if days_to_expiry in range(5, 10) or days_to_expiry in range(25, 35):
                    expiry_key = '7d' if days_to_expiry < 15 else '30d'

                    # 5% OTM puts (strike below spot)
                    if option_type == 'put' and 0.93 < strike / btc_price < 0.97:
                        if expiry_key not in skew_data:
                            skew_data[expiry_key] = {'put_iv': None, 'call_iv': None}

                        # Get IV
                        try:
                            url = f"{self.base_url}/ticker"
                            params = {'instrument_name': instrument_name}
                            r = requests.get(url, params=params, timeout=10)
                            r.raise_for_status()
                            iv = r.json()['result'].get('mark_iv', 0)
                            if skew_data[expiry_key]['put_iv'] is None or iv > 0:
                                skew_data[expiry_key]['put_iv'] = iv
                        except:
                            pass

                    # 5% OTM calls (strike above spot)
                    elif option_type == 'call' and 1.03 < strike / btc_price < 1.07:
                        if expiry_key not in skew_data:
                            skew_data[expiry_key] = {'put_iv': None, 'call_iv': None}

                        try:
                            url = f"{self.base_url}/ticker"
                            params = {'instrument_name': instrument_name}
                            r = requests.get(url, params=params, timeout=10)
                            r.raise_for_status()
                            iv = r.json()['result'].get('mark_iv', 0)
                            if skew_data[expiry_key]['call_iv'] is None or iv > 0:
                                skew_data[expiry_key]['call_iv'] = iv
                        except:
                            pass

            # Calculate skew
            result = {}
            for expiry, data in skew_data.items():
                if data['put_iv'] and data['call_iv']:
                    skew = data['put_iv'] - data['call_iv']
                    result[expiry] = {
                        'put_iv': data['put_iv'],
                        'call_iv': data['call_iv'],
                        'skew': skew,
                        'interpretation': 'bearish' if skew > 5 else ('bullish' if skew < -5 else 'neutral')
                    }

            return {
                'skew': result,
                'btc_index': btc_price,
                'source': 'deribit'
            }

        except Exception as e:
            logger.warning(f"Failed to fetch option skew: {e}")
            return {'skew': {}, 'source': 'fallback'}

    def get_options_data(self) -> Dict:
        """Get all options data with caching."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    cached = json.load(f)
                cache_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
                if (datetime.now() - cache_time).total_seconds() < self.cache_duration:
                    return cached
            except:
                pass

        # Fetch all data
        dvol = self.fetch_dvol_index()
        atm_iv = self.fetch_atm_iv()
        skew = self.fetch_option_skew()

        data = {
            'dvol': dvol.get('dvol', 50),
            'dvol_24h_change': dvol.get('dvol_24h_change', 0),
            'atm_iv': atm_iv.get('atm_iv', {}),
            'skew': skew.get('skew', {}),
            'btc_index': atm_iv.get('btc_index', 95000),
            'signal': self._interpret_options_data(dvol, atm_iv, skew),
            'timestamp': datetime.now().isoformat(),
            'source': 'deribit'
        }

        with open(self.cache_file, 'w') as f:
            json.dump(data, f)

        return data

    def _interpret_options_data(self, dvol: Dict, atm_iv: Dict, skew: Dict) -> Dict:
        """Interpret options data for trading signals."""
        signals = []
        vol_adjustment = 1.0
        direction_score = 0

        # DVOL interpretation
        dvol_val = dvol.get('dvol', 50)
        if dvol_val > 80:
            signals.append(f"DVOL very high ({dvol_val:.0f}) - expect high volatility")
            vol_adjustment *= 1.3
        elif dvol_val > 60:
            signals.append(f"DVOL elevated ({dvol_val:.0f})")
            vol_adjustment *= 1.15
        elif dvol_val < 40:
            signals.append(f"DVOL low ({dvol_val:.0f}) - calm market")
            vol_adjustment *= 0.9

        # DVOL change interpretation
        dvol_change = dvol.get('dvol_24h_change', 0)
        if dvol_change > 5:
            signals.append(f"DVOL rising fast (+{dvol_change:.1f}) - fear increasing")
            vol_adjustment *= 1.1
        elif dvol_change < -5:
            signals.append(f"DVOL falling ({dvol_change:.1f}) - fear subsiding")

        # Skew interpretation
        skew_data = skew.get('skew', {})
        if '7d' in skew_data:
            skew_7d = skew_data['7d'].get('skew', 0)
            if skew_7d > 5:
                signals.append(f"Put skew +{skew_7d:.1f} (bearish bias)")
                direction_score -= 0.2
            elif skew_7d < -5:
                signals.append(f"Call skew {skew_7d:.1f} (bullish bias)")
                direction_score += 0.2

        direction = 'BULLISH' if direction_score > 0.1 else ('BEARISH' if direction_score < -0.1 else 'NEUTRAL')

        return {
            'direction': direction,
            'direction_score': direction_score,
            'volatility_adjustment': vol_adjustment,
            'reasons': signals
        }


# =============================================================================
# 6. OPEN INTEREST & LIQUIDATIONS
# =============================================================================

class OpenInterestService:
    """
    Fetch open interest and liquidation data.

    Rising OI + rising price = new longs (trend continuation)
    Rising OI + falling price = new shorts (trend continuation)
    Falling OI + rising price = short covering (weaker rally)
    Falling OI + falling price = long liquidation (weaker selloff)

    Liquidation cascades predict big moves.
    """

    def __init__(self):
        self.cache_file = CACHE_DIR / 'open_interest.json'
        self.cache_duration = 300  # 5 minutes

    def fetch_coinglass_oi(self) -> Dict:
        """
        Fetch OI data from public endpoints.
        Uses CoinGecko derivatives data (works globally, no geo-blocking).
        """
        # Use CoinGecko derivatives API (same as funding rate service)
        try:
            url = "https://api.coingecko.com/api/v3/derivatives"
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()

            # Find Binance BTCUSDT perpetual
            for item in data:
                if item.get('market') == 'Binance (Futures)' and item.get('symbol') == 'BTCUSDT':
                    oi_usd = item.get('open_interest', 0)

                    # Get BTC price to convert OI to BTC
                    try:
                        price_r = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=5)
                        btc_price = float(price_r.json()['data']['amount'])
                    except:
                        btc_price = 95000

                    oi_btc = oi_usd / btc_price if btc_price > 0 else 0

                    return {
                        'oi_btc': oi_btc,
                        'oi_usd': oi_usd,
                        'oi_change_24h_pct': 0,  # CoinGecko doesn't provide historical OI
                        'source': 'coingecko'
                    }

            logger.warning("BTCUSDT not found in CoinGecko derivatives")

        except Exception as e:
            logger.warning(f"Failed to fetch CoinGecko OI: {e}")

        return {'oi_btc': 0, 'oi_change_24h_pct': 0, 'source': 'fallback'}

    def fetch_liquidations(self) -> Dict:
        """
        Fetch recent liquidation data.
        Uses public aggregated data when available.
        """
        try:
            # Try Binance liquidation stream (requires websocket, so we'll estimate)
            # For now, estimate from price volatility and OI changes

            # Get recent price action
            url = "https://api.binance.com/api/v3/klines"
            params = {'symbol': 'BTCUSDT', 'interval': '1h', 'limit': 24}
            r = requests.get(url, params=params, timeout=10)

            if r.status_code == 200:
                klines = r.json()

                # Calculate hourly returns
                returns = []
                for i in range(1, len(klines)):
                    close_prev = float(klines[i-1][4])
                    close_curr = float(klines[i][4])
                    ret = (close_curr - close_prev) / close_prev * 100
                    returns.append(ret)

                # Large moves likely caused liquidations
                large_moves = [r for r in returns if abs(r) > 1]

                # Estimate liquidation intensity
                if len(large_moves) >= 3:
                    intensity = 'high'
                elif len(large_moves) >= 1:
                    intensity = 'moderate'
                else:
                    intensity = 'low'

                # Direction of liquidations
                down_moves = [r for r in returns if r < -1]
                up_moves = [r for r in returns if r > 1]

                if len(down_moves) > len(up_moves):
                    liq_direction = 'long_liquidations'
                elif len(up_moves) > len(down_moves):
                    liq_direction = 'short_liquidations'
                else:
                    liq_direction = 'balanced'

                return {
                    'intensity': intensity,
                    'direction': liq_direction,
                    'large_moves_24h': len(large_moves),
                    'max_hourly_move': max([abs(r) for r in returns]) if returns else 0,
                    'source': 'estimated'
                }
        except Exception as e:
            logger.warning(f"Failed to estimate liquidations: {e}")

        return {
            'intensity': 'unknown',
            'direction': 'unknown',
            'large_moves_24h': 0,
            'source': 'fallback'
        }

    def fetch_long_short_ratio(self) -> Dict:
        """
        Fetch long/short ratio.
        Uses CoinGecko derivatives data which includes funding rate as a proxy.
        Positive funding = more longs, negative funding = more shorts.
        """
        try:
            url = "https://api.coingecko.com/api/v3/derivatives"
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()

            # Find Binance BTCUSDT perpetual
            for item in data:
                if item.get('market') == 'Binance (Futures)' and item.get('symbol') == 'BTCUSDT':
                    funding_rate = item.get('funding_rate', 0) / 100  # Convert from percentage

                    # Estimate L/S ratio from funding rate
                    # Positive funding = longs pay shorts = more longs
                    # Typical range: -0.1% to +0.1%
                    # Convert to ratio: 0% funding = 1.0, +0.05% = ~1.2, -0.05% = ~0.8
                    ratio = 1.0 + (funding_rate * 100 * 4)  # Scale factor
                    ratio = max(0.5, min(2.0, ratio))  # Clamp

                    long_pct = ratio / (1 + ratio) * 100
                    short_pct = 100 - long_pct

                    return {
                        'long_short_ratio': ratio,
                        'long_pct': long_pct,
                        'short_pct': short_pct,
                        'funding_based': True,
                        'source': 'coingecko'
                    }

        except Exception as e:
            logger.warning(f"Failed to fetch long/short ratio: {e}")

        return {'long_short_ratio': 1.0, 'long_pct': 50, 'short_pct': 50, 'source': 'fallback'}

    def get_oi_data(self) -> Dict:
        """Get all OI/liquidation data with caching."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    cached = json.load(f)
                cache_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
                if (datetime.now() - cache_time).total_seconds() < self.cache_duration:
                    return cached
            except:
                pass

        oi = self.fetch_coinglass_oi()
        liqs = self.fetch_liquidations()
        ls_ratio = self.fetch_long_short_ratio()

        data = {
            'open_interest_btc': oi.get('oi_btc', 0),
            'oi_change_24h_pct': oi.get('oi_change_24h_pct', 0),
            'liquidation_intensity': liqs.get('intensity', 'unknown'),
            'liquidation_direction': liqs.get('direction', 'unknown'),
            'large_moves_24h': liqs.get('large_moves_24h', 0),
            'long_short_ratio': ls_ratio.get('long_short_ratio', 1.0),
            'long_pct': ls_ratio.get('long_pct', 50),
            'short_pct': ls_ratio.get('short_pct', 50),
            'signal': self._interpret_oi_data(oi, liqs, ls_ratio),
            'timestamp': datetime.now().isoformat(),
            'source': oi.get('source', 'unknown')
        }

        with open(self.cache_file, 'w') as f:
            json.dump(data, f)

        return data

    def _interpret_oi_data(self, oi: Dict, liqs: Dict, ls_ratio: Dict) -> Dict:
        """Interpret OI/liquidation data."""
        signals = []
        direction_score = 0
        vol_adjustment = 1.0

        # OI change interpretation
        oi_change = oi.get('oi_change_24h_pct', 0)
        if oi_change > 10:
            signals.append(f"OI rising fast (+{oi_change:.1f}%) - new positions building")
            vol_adjustment *= 1.1
        elif oi_change < -10:
            signals.append(f"OI falling ({oi_change:.1f}%) - positions closing")

        # Long/short ratio
        ratio = ls_ratio.get('long_short_ratio', 1.0)
        if ratio > 1.5:
            signals.append(f"Crowded longs ({ratio:.2f}) - contrarian bearish")
            direction_score -= 0.2
        elif ratio < 0.7:
            signals.append(f"Crowded shorts ({ratio:.2f}) - contrarian bullish")
            direction_score += 0.2

        # Liquidation intensity
        intensity = liqs.get('intensity', 'low')
        if intensity == 'high':
            signals.append("High liquidation activity - volatile")
            vol_adjustment *= 1.2

        direction = 'BULLISH' if direction_score > 0.1 else ('BEARISH' if direction_score < -0.1 else 'NEUTRAL')

        return {
            'direction': direction,
            'direction_score': direction_score,
            'volatility_adjustment': vol_adjustment,
            'reasons': signals
        }


# =============================================================================
# 7. ORDER BOOK DATA
# =============================================================================

class OrderBookService:
    """
    Fetch order book depth and imbalance.

    Bid/ask imbalance indicates short-term directional pressure.
    Large walls indicate support/resistance levels.
    """

    def __init__(self):
        self.cache_file = CACHE_DIR / 'orderbook.json'
        self.cache_duration = 60  # 1 minute (changes fast)

    def fetch_coinbase_orderbook(self, depth: int = 50) -> Dict:
        """Fetch order book from Coinbase."""
        try:
            url = f"https://api.exchange.coinbase.com/products/BTC-USD/book"
            params = {'level': 2}  # Level 2 = top 50 bids/asks
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()

            bids = [(float(b[0]), float(b[1])) for b in data.get('bids', [])[:depth]]
            asks = [(float(a[0]), float(a[1])) for a in data.get('asks', [])[:depth]]

            return {'bids': bids, 'asks': asks, 'source': 'coinbase'}
        except Exception as e:
            logger.warning(f"Failed to fetch Coinbase orderbook: {e}")
            return {'bids': [], 'asks': [], 'source': 'fallback'}

    def fetch_binance_orderbook(self, depth: int = 50) -> Dict:
        """Fetch order book from Binance."""
        try:
            url = "https://api.binance.com/api/v3/depth"
            params = {'symbol': 'BTCUSDT', 'limit': depth}
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()

            bids = [(float(b[0]), float(b[1])) for b in data.get('bids', [])]
            asks = [(float(a[0]), float(a[1])) for a in data.get('asks', [])]

            return {'bids': bids, 'asks': asks, 'source': 'binance'}
        except Exception as e:
            logger.warning(f"Failed to fetch Binance orderbook: {e}")
            return {'bids': [], 'asks': [], 'source': 'fallback'}

    def calculate_imbalance(self, bids: List, asks: List, pct_range: float = 0.01) -> Dict:
        """
        Calculate bid/ask imbalance within a price range.

        pct_range: percentage from mid price to consider (e.g., 0.01 = 1%)
        """
        if not bids or not asks:
            return {'imbalance': 0, 'interpretation': 'neutral'}

        mid_price = (bids[0][0] + asks[0][0]) / 2
        range_lower = mid_price * (1 - pct_range)
        range_upper = mid_price * (1 + pct_range)

        # Sum volume within range
        bid_volume = sum(b[1] for b in bids if b[0] >= range_lower)
        ask_volume = sum(a[1] for a in asks if a[0] <= range_upper)

        total_volume = bid_volume + ask_volume
        if total_volume == 0:
            return {'imbalance': 0, 'interpretation': 'neutral'}

        # Imbalance: positive = more bids (bullish), negative = more asks (bearish)
        imbalance = (bid_volume - ask_volume) / total_volume

        if imbalance > 0.3:
            interpretation = 'strong_bid'
        elif imbalance > 0.1:
            interpretation = 'mild_bid'
        elif imbalance < -0.3:
            interpretation = 'strong_ask'
        elif imbalance < -0.1:
            interpretation = 'mild_ask'
        else:
            interpretation = 'neutral'

        return {
            'imbalance': imbalance,
            'bid_volume': bid_volume,
            'ask_volume': ask_volume,
            'mid_price': mid_price,
            'interpretation': interpretation
        }

    def find_walls(self, bids: List, asks: List, threshold_btc: float = 10) -> Dict:
        """
        Find large orders (walls) that may act as support/resistance.
        """
        bid_walls = [(price, size) for price, size in bids if size >= threshold_btc]
        ask_walls = [(price, size) for price, size in asks if size >= threshold_btc]

        # Find strongest walls
        strongest_bid = max(bids, key=lambda x: x[1]) if bids else (0, 0)
        strongest_ask = max(asks, key=lambda x: x[1]) if asks else (0, 0)

        return {
            'bid_walls': bid_walls[:5],  # Top 5
            'ask_walls': ask_walls[:5],
            'strongest_support': {'price': strongest_bid[0], 'size': strongest_bid[1]},
            'strongest_resistance': {'price': strongest_ask[0], 'size': strongest_ask[1]}
        }

    def get_orderbook_data(self) -> Dict:
        """Get order book analysis with caching."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    cached = json.load(f)
                cache_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
                if (datetime.now() - cache_time).total_seconds() < self.cache_duration:
                    return cached
            except:
                pass

        # Try Coinbase first, then Binance
        ob = self.fetch_coinbase_orderbook()
        if ob['source'] == 'fallback':
            ob = self.fetch_binance_orderbook()

        bids = ob.get('bids', [])
        asks = ob.get('asks', [])

        imbalance = self.calculate_imbalance(bids, asks)
        walls = self.find_walls(bids, asks)

        data = {
            'imbalance': imbalance.get('imbalance', 0),
            'imbalance_interpretation': imbalance.get('interpretation', 'neutral'),
            'bid_volume': imbalance.get('bid_volume', 0),
            'ask_volume': imbalance.get('ask_volume', 0),
            'mid_price': imbalance.get('mid_price', 0),
            'strongest_support': walls.get('strongest_support', {}),
            'strongest_resistance': walls.get('strongest_resistance', {}),
            'signal': self._interpret_orderbook(imbalance, walls),
            'timestamp': datetime.now().isoformat(),
            'source': ob.get('source', 'unknown')
        }

        with open(self.cache_file, 'w') as f:
            json.dump(data, f)

        return data

    def _interpret_orderbook(self, imbalance: Dict, walls: Dict) -> Dict:
        """Interpret order book data."""
        direction_score = 0
        signals = []

        imb = imbalance.get('imbalance', 0)
        if imb > 0.2:
            signals.append(f"Strong bid pressure ({imb:.1%})")
            direction_score += 0.15
        elif imb < -0.2:
            signals.append(f"Strong ask pressure ({imb:.1%})")
            direction_score -= 0.15

        # Wall analysis
        support = walls.get('strongest_support', {})
        resistance = walls.get('strongest_resistance', {})
        mid = imbalance.get('mid_price', 0)

        if support.get('size', 0) > 20 and mid > 0:
            pct_to_support = (mid - support['price']) / mid * 100
            if pct_to_support < 1:
                signals.append(f"Strong support nearby at ${support['price']:,.0f}")

        if resistance.get('size', 0) > 20 and mid > 0:
            pct_to_resistance = (resistance['price'] - mid) / mid * 100
            if pct_to_resistance < 1:
                signals.append(f"Strong resistance nearby at ${resistance['price']:,.0f}")

        direction = 'BULLISH' if direction_score > 0.1 else ('BEARISH' if direction_score < -0.1 else 'NEUTRAL')

        return {
            'direction': direction,
            'direction_score': direction_score,
            'reasons': signals
        }


# =============================================================================
# UNIFIED DATA SERVICE
# =============================================================================

class EnhancedDataService:
    """
    Unified service that combines all data sources.
    """

    def __init__(self, kalshi_engine=None):
        self.funding_service = FundingRateService()
        self.fear_greed_service = FearGreedService()
        self.kalshi_historical = KalshiHistoricalService(kalshi_engine)
        self.whale_service = WhaleTrackingService()
        # New services
        self.deribit_service = DeribitOptionsService()
        self.oi_service = OpenInterestService()
        self.orderbook_service = OrderBookService()

    def get_all_signals(self) -> Dict:
        """Fetch all signals and combine into unified view."""
        logger.info("Fetching all enhanced data signals...")

        signals = {}

        # 1. Funding rates
        try:
            signals['funding'] = self.funding_service.get_funding()
            logger.info(f"Funding rate: {signals['funding'].get('rate_8h_pct', 0):.3f}%")
        except Exception as e:
            logger.error(f"Failed to get funding: {e}")
            signals['funding'] = {'signal': {'direction': 'NEUTRAL'}}

        # 2. Fear & Greed
        try:
            signals['fear_greed'] = self.fear_greed_service.get_fear_greed()
            logger.info(f"Fear & Greed: {signals['fear_greed'].get('value', 50)} ({signals['fear_greed'].get('classification', 'Unknown')})")
        except Exception as e:
            logger.error(f"Failed to get fear/greed: {e}")
            signals['fear_greed'] = {'value': 50, 'signal': {'direction': 'NEUTRAL'}}

        # 3. Kalshi historical
        try:
            signals['kalshi_historical'] = self.kalshi_historical.get_historical_stats()
            total = signals['kalshi_historical'].get('total_markets', 0)
            logger.info(f"Kalshi historical: {total} markets analyzed")
        except Exception as e:
            logger.error(f"Failed to get Kalshi historical: {e}")
            signals['kalshi_historical'] = {}

        # 4. Whale movements
        try:
            signals['whales'] = self.whale_service.get_whale_data()
            whale_count = signals['whales'].get('recent_large_txs', 0)
            logger.info(f"Whale activity: {whale_count} large transactions")
        except Exception as e:
            logger.error(f"Failed to get whale data: {e}")
            signals['whales'] = {'signal': {'direction': 'NEUTRAL'}}

        # 5. Deribit Options (IV, Skew)
        try:
            signals['options'] = self.deribit_service.get_options_data()
            dvol = signals['options'].get('dvol', 0)
            logger.info(f"Deribit DVOL: {dvol:.1f}%")
        except Exception as e:
            logger.error(f"Failed to get Deribit options: {e}")
            signals['options'] = {'dvol': 50, 'signal': {'direction': 'NEUTRAL', 'volatility_adjustment': 1.0}}

        # 6. Open Interest & Liquidations
        try:
            signals['open_interest'] = self.oi_service.get_oi_data()
            oi = signals['open_interest'].get('open_interest_btc', 0)
            ls_ratio = signals['open_interest'].get('long_short_ratio', 1.0)
            logger.info(f"Open Interest: {oi:,.0f} BTC, L/S ratio: {ls_ratio:.2f}")
        except Exception as e:
            logger.error(f"Failed to get OI data: {e}")
            signals['open_interest'] = {'signal': {'direction': 'NEUTRAL', 'volatility_adjustment': 1.0}}

        # 7. Order Book
        try:
            signals['orderbook'] = self.orderbook_service.get_orderbook_data()
            imb = signals['orderbook'].get('imbalance', 0)
            logger.info(f"Order book imbalance: {imb:+.1%}")
        except Exception as e:
            logger.error(f"Failed to get orderbook: {e}")
            signals['orderbook'] = {'imbalance': 0, 'signal': {'direction': 'NEUTRAL'}}

        # Calculate combined signal
        signals['combined'] = self._calculate_combined_signal(signals)

        return signals

    def _calculate_combined_signal(self, signals: Dict) -> Dict:
        """Calculate a combined directional signal from all sources."""
        score = 0.0
        vol_adjustment = 1.0
        weights = {
            'funding': 0.15,
            'fear_greed': 0.15,
            'whales': 0.10,
            'options': 0.20,       # Deribit IV/skew - high weight (professional market)
            'open_interest': 0.20, # OI and L/S ratio - high weight
            'orderbook': 0.10,     # Order book imbalance
            'kalshi_historical': 0.10,
        }

        reasons = []

        # 1. Funding signal
        funding_dir = signals.get('funding', {}).get('signal', {}).get('direction', 'NEUTRAL')
        if funding_dir == 'BULLISH':
            score += weights['funding']
            reasons.append("Negative funding (bullish)")
        elif funding_dir == 'BEARISH':
            score -= weights['funding']
            reasons.append("High funding (bearish)")

        # 2. Fear & Greed signal
        fg_dir = signals.get('fear_greed', {}).get('signal', {}).get('direction', 'NEUTRAL')
        if fg_dir == 'BULLISH':
            score += weights['fear_greed']
            reasons.append(f"Fear in market ({signals['fear_greed'].get('value', 50)})")
        elif fg_dir == 'BEARISH':
            score -= weights['fear_greed']
            reasons.append(f"Greed in market ({signals['fear_greed'].get('value', 50)})")

        # 3. Whale signal (primarily affects volatility)
        whale_dir = signals.get('whales', {}).get('signal', {}).get('direction', 'NEUTRAL')
        if whale_dir == 'VOLATILE':
            reasons.append("High whale activity (volatile)")
            vol_adjustment *= 1.15

        # 4. Options signal (IV and skew from Deribit)
        options_signal = signals.get('options', {}).get('signal', {})
        options_dir = options_signal.get('direction', 'NEUTRAL')
        options_vol_adj = options_signal.get('volatility_adjustment', 1.0)
        options_score = options_signal.get('direction_score', 0)

        score += options_score * weights['options']
        vol_adjustment *= options_vol_adj

        if options_dir == 'BULLISH':
            reasons.append("Options skew bullish")
        elif options_dir == 'BEARISH':
            reasons.append("Options skew bearish")

        # Add DVOL info
        dvol = signals.get('options', {}).get('dvol', 50)
        if dvol > 70:
            reasons.append(f"DVOL high ({dvol:.0f}%)")
        elif dvol < 40:
            reasons.append(f"DVOL low ({dvol:.0f}%)")

        # 5. Open Interest signal
        oi_signal = signals.get('open_interest', {}).get('signal', {})
        oi_dir = oi_signal.get('direction', 'NEUTRAL')
        oi_score = oi_signal.get('direction_score', 0)
        oi_vol_adj = oi_signal.get('volatility_adjustment', 1.0)

        score += oi_score * weights['open_interest']
        vol_adjustment *= oi_vol_adj

        if oi_dir == 'BULLISH':
            reasons.append("OI/positioning bullish")
        elif oi_dir == 'BEARISH':
            reasons.append("OI/positioning bearish")

        # Add L/S ratio info
        ls_ratio = signals.get('open_interest', {}).get('long_short_ratio', 1.0)
        if ls_ratio > 1.3:
            reasons.append(f"Crowded longs ({ls_ratio:.2f})")
        elif ls_ratio < 0.8:
            reasons.append(f"Crowded shorts ({ls_ratio:.2f})")

        # 6. Order book signal
        ob_signal = signals.get('orderbook', {}).get('signal', {})
        ob_score = ob_signal.get('direction_score', 0)
        score += ob_score * weights['orderbook']

        imb = signals.get('orderbook', {}).get('imbalance', 0)
        if abs(imb) > 0.2:
            side = "bid" if imb > 0 else "ask"
            reasons.append(f"Order book {side} pressure ({imb:+.0%})")

        # Normalize score to -1 to 1
        combined_score = np.clip(score, -1, 1)

        if combined_score > 0.15:
            direction = 'BULLISH'
        elif combined_score < -0.15:
            direction = 'BEARISH'
        else:
            direction = 'NEUTRAL'

        return {
            'score': combined_score,
            'direction': direction,
            'reasons': reasons,
            'volatility_adjustment': vol_adjustment,
        }

    def print_report(self):
        """Print a formatted report of all signals."""
        signals = self.get_all_signals()

        print("\n" + "=" * 80)
        print("  ENHANCED DATA SIGNALS REPORT")
        print("=" * 80)

        # Funding
        funding = signals.get('funding', {})
        print(f"\n  1. FUNDING RATE ({funding.get('source', 'unknown')})")
        print(f"     Current: {funding.get('rate_8h_pct', 0):.4f}% (8h)")
        print(f"     Annualized: {funding.get('rate_annual_pct', 0):.1f}%")
        print(f"     Signal: {funding.get('signal', {}).get('direction', 'N/A')}")

        # Fear & Greed
        fg = signals.get('fear_greed', {})
        print(f"\n  2. FEAR & GREED INDEX")
        print(f"     Value: {fg.get('value', 'N/A')} ({fg.get('classification', 'N/A')})")
        print(f"     3-day trend: {fg.get('trend_3d', 0):+d}")
        print(f"     Signal: {fg.get('signal', {}).get('direction', 'N/A')}")

        # Whales
        whales = signals.get('whales', {})
        print(f"\n  3. WHALE ACTIVITY ({whales.get('source', 'unknown')})")
        print(f"     Large txs (50+ BTC): {whales.get('recent_large_txs', 0)}")
        print(f"     Total volume: {whales.get('total_volume_btc', 0):,.0f} BTC")
        print(f"     Signal: {whales.get('signal', {}).get('direction', 'N/A')}")

        # Options (NEW)
        options = signals.get('options', {})
        print(f"\n  4. DERIBIT OPTIONS ({options.get('source', 'unknown')})")
        print(f"     DVOL (30d IV): {options.get('dvol', 0):.1f}%")
        print(f"     DVOL 24h change: {options.get('dvol_24h_change', 0):+.1f}")
        atm_iv = options.get('atm_iv', {})
        if atm_iv:
            for expiry, data in atm_iv.items():
                print(f"     ATM IV ({expiry}): {data.get('iv', 0):.1f}%")
        skew = options.get('skew', {})
        if skew:
            for expiry, data in skew.items():
                print(f"     Skew ({expiry}): {data.get('skew', 0):+.1f} ({data.get('interpretation', 'N/A')})")
        print(f"     Signal: {options.get('signal', {}).get('direction', 'N/A')}")
        print(f"     Vol adjustment: {options.get('signal', {}).get('volatility_adjustment', 1.0):.2f}x")

        # Open Interest (NEW)
        oi = signals.get('open_interest', {})
        print(f"\n  5. OPEN INTEREST ({oi.get('source', 'unknown')})")
        print(f"     OI: {oi.get('open_interest_btc', 0):,.0f} BTC")
        print(f"     OI 24h change: {oi.get('oi_change_24h_pct', 0):+.1f}%")
        print(f"     Long/Short ratio: {oi.get('long_short_ratio', 1.0):.2f}")
        print(f"     Longs: {oi.get('long_pct', 50):.1f}% | Shorts: {oi.get('short_pct', 50):.1f}%")
        print(f"     Liquidation intensity: {oi.get('liquidation_intensity', 'unknown')}")
        print(f"     Signal: {oi.get('signal', {}).get('direction', 'N/A')}")

        # Order Book (NEW)
        ob = signals.get('orderbook', {})
        print(f"\n  6. ORDER BOOK ({ob.get('source', 'unknown')})")
        print(f"     Mid price: ${ob.get('mid_price', 0):,.2f}")
        print(f"     Imbalance: {ob.get('imbalance', 0):+.1%} ({ob.get('imbalance_interpretation', 'neutral')})")
        print(f"     Bid volume: {ob.get('bid_volume', 0):.2f} BTC")
        print(f"     Ask volume: {ob.get('ask_volume', 0):.2f} BTC")
        support = ob.get('strongest_support', {})
        resistance = ob.get('strongest_resistance', {})
        if support.get('price'):
            print(f"     Support wall: ${support['price']:,.0f} ({support['size']:.1f} BTC)")
        if resistance.get('price'):
            print(f"     Resistance wall: ${resistance['price']:,.0f} ({resistance['size']:.1f} BTC)")
        print(f"     Signal: {ob.get('signal', {}).get('direction', 'N/A')}")

        # Kalshi Historical
        kalshi = signals.get('kalshi_historical', {})
        print(f"\n  7. KALSHI HISTORICAL")
        print(f"     Markets analyzed: {kalshi.get('total_markets', 0)}")
        print(f"     Overall YES rate: {kalshi.get('overall_yes_rate', 0):.1%}")

        # Combined
        combined = signals.get('combined', {})
        print(f"\n  " + "-" * 76)
        print(f"  COMBINED SIGNAL")
        print(f"  " + "-" * 76)
        print(f"     Direction: {combined.get('direction', 'N/A')}")
        print(f"     Score: {combined.get('score', 0):+.2f}")
        print(f"     Vol adjustment: {combined.get('volatility_adjustment', 1.0):.2f}x")
        if combined.get('reasons'):
            print(f"     Reasons:")
            for reason in combined.get('reasons', []):
                print(f"       - {reason}")

        print("\n" + "=" * 80)

        return signals


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Test the service
    print("Testing Enhanced Data Service...")

    # Initialize without Kalshi for basic test
    service = EnhancedDataService()
    service.print_report()
