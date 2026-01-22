#!/usr/bin/env python3
"""
Test script to fetch real Kalshi BTC markets and calculate model probabilities.
Compares GARCH-based model probabilities to market prices to find edge.
"""

import os
import sys
import logging
import numpy as np
import re
from datetime import datetime, timedelta
from scipy.stats import norm

# Reduce logging noise
logging.basicConfig(level=logging.WARNING, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def extract_range_from_ticker(ticker: str, subtitle: str = None) -> tuple:
    """
    Extract price range from Kalshi ticker + subtitle.

    Kalshi BTC hourly markets are RANGE markets:
    - KXBTC-26JAN1416-B96875 -> "$96,750 to 96,999.99" (YES if BTC in this range)
    - KXBTC-26JAN1416-T83000 -> "$82,999.99 or below" (tail market)

    Returns: (lower_bound, upper_bound, is_tail) where:
        - is_tail='low' for "X or below" markets
        - is_tail='high' for "X or above" markets
        - is_tail=None for standard range markets
    """
    if not ticker:
        return None, None, None

    # Parse subtitle to get exact range
    if subtitle:
        # Pattern: "$96,750 to 96,999.99" or "$82,999.99 or below"
        subtitle_clean = subtitle.replace(',', '').replace('$', '')

        if 'or below' in subtitle.lower():
            # Tail market (low end) - e.g., "$82,999.99 or below"
            try:
                upper = float(subtitle_clean.split(' or ')[0])
                return 0, upper, 'low'
            except:
                pass
        elif 'or above' in subtitle.lower():
            # Tail market (high end) - e.g., "$110,000 or above"
            try:
                lower = float(subtitle_clean.split(' or ')[0])
                return lower, float('inf'), 'high'
            except:
                pass
        elif ' to ' in subtitle.lower():
            # Standard range - e.g., "$96,750 to 96,999.99"
            try:
                parts = subtitle_clean.split(' to ')
                lower = float(parts[0])
                upper = float(parts[1])
                return lower, upper, None
            except:
                pass

    # Fallback: extract strike from ticker and assume $250 range
    parts = ticker.split('-')
    if len(parts) < 3:
        return None, None, None

    strike_part = parts[-1]  # e.g., "B96875" or "T83000"

    if strike_part.startswith('T'):
        # Tail market (usually the lowest range)
        strike_str = strike_part[1:]
        try:
            upper = float(strike_str)
            return 0, upper, 'low'
        except:
            pass
    elif strike_part.startswith('B'):
        # Range bracket - assume $250 range centered on strike
        strike_str = strike_part[1:]
        try:
            strike = float(strike_str)
            # Typical Kalshi ranges are $250 wide
            lower = strike - 125
            upper = strike + 125
            return lower, upper, None
        except:
            pass

    return None, None, None


def calculate_hours_to_expiry(ticker: str, close_date: str = None) -> float:
    """
    Calculate hours until expiration from ticker.

    Kalshi ticker format: KXBTCD-26JAN1416-T99999
    - 26 = year (2026)
    - JAN = month
    - 14 = day
    - 16 = hour (16:00)

    Returns hours as float (e.g., 2.5 for 2.5 hours)
    """
    # First try to parse from close_date if provided
    if close_date:
        try:
            for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                try:
                    exp_date = datetime.strptime(close_date.split('.')[0].replace('Z', ''), fmt)
                    hours = (exp_date - datetime.now()).total_seconds() / 3600
                    return max(0.1, hours)
                except ValueError:
                    continue
        except:
            pass

    # Parse from ticker (e.g., KXBTCD-26JAN1416-T99999)
    # Format: YYMMMDDYY where YY=year, MMM=month, DD=day, HH=hour
    if ticker:
        parts = ticker.split('-')
        if len(parts) >= 2:
            date_part = parts[1]  # e.g., "26JAN1416"
            try:
                # Year is first 2 digits
                year = int('20' + date_part[:2])
                month_str = date_part[2:5]
                day = int(date_part[5:7])
                hour = int(date_part[7:9]) if len(date_part) >= 9 else 16  # Default 4 PM

                months = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                         'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
                month = months.get(month_str.upper(), 1)

                exp_date = datetime(year, month, day, hour)
                hours = (exp_date - datetime.now()).total_seconds() / 3600
                return max(0.1, hours)  # Minimum 0.1 hours (6 minutes)
            except Exception as e:
                pass

    return 24.0  # Default to 24 hours


def main():
    print("\n" + "="*100)
    print("          KALSHI BTC RANGE MARKETS - GARCH PROBABILITY ANALYSIS")
    print("="*100)

    # Import our modules
    from kalshi_engine import KalshiEngine
    from market_data_service import get_market_data_service
    from volatility_model import GARCHVolatilityModel, SignalAdjuster

    # Step 1: Initialize Kalshi connection
    print("\n[1] CONNECTING TO KALSHI...")
    kalshi = KalshiEngine()

    if not kalshi.is_connected:
        print("    ERROR: Could not connect to Kalshi. Check your API credentials.")
        return

    balance = kalshi.get_balance()
    print(f"    Connected! Balance: ${balance['balance']:,.2f}")

    # Step 2: Fetch market data and fit GARCH
    print("\n[2] FITTING GARCH MODEL...")
    market_data = get_market_data_service()
    df = market_data.fetch_ohlc_data(days=365)
    current_btc_price = float(df['close'].iloc[-1])

    returns = market_data.calculate_log_returns()
    garch = GARCHVolatilityModel()
    fit_result = garch.fit(returns)

    current_vol = garch.get_current_volatility()
    print(f"    Current BTC: ${current_btc_price:,.2f}")
    print(f"    GARCH Vol: {current_vol:.1%} annualized ({current_vol/np.sqrt(365):.2%} daily)")
    print(f"    Params: alpha={fit_result['alpha']:.3f}, beta={fit_result['beta']:.3f}, persistence={fit_result['persistence']:.3f}")

    # Step 3: Fetch KXBTC series directly (hourly BTC range markets)
    print("\n[3] FETCHING KALSHI BTC RANGE MARKETS...")

    # Fetch from KXBTC series (hourly range markets)
    result = kalshi._make_authenticated_request('GET', '/markets?series_ticker=KXBTC&status=open&limit=200')
    kxbtc_markets = result.get('markets', []) if result else []

    # Also fetch from KXBTC daily series
    result2 = kalshi._make_authenticated_request('GET', '/markets?series_ticker=KXBTCD&status=open&limit=200')
    kxbtcd_markets = result2.get('markets', []) if result2 else []

    all_btc_markets = kxbtc_markets + kxbtcd_markets
    print(f"    Found {len(kxbtc_markets)} hourly KXBTC markets")
    print(f"    Found {len(kxbtcd_markets)} daily KXBTCD markets")

    # Step 4: Analyze BTC range markets
    range_markets = []
    tail_low_markets = []
    tail_high_markets = []
    skipped = 0

    for market in all_btc_markets:
        ticker = market.get('ticker', '')
        subtitle = market.get('subtitle', '')

        # Parse range from subtitle
        lower, upper, is_tail = extract_range_from_ticker(ticker, subtitle)

        if lower is None:
            skipped += 1
            continue

        # Get market price from bid/ask (in cents, convert to probability)
        yes_bid = market.get('yes_bid', 0)
        yes_ask = market.get('yes_ask', 0)

        # Use mid-price if both available, otherwise use what we have
        if yes_bid > 0 and yes_ask > 0:
            yes_price_cents = (yes_bid + yes_ask) / 2
        elif yes_ask > 0:
            yes_price_cents = yes_ask
        elif yes_bid > 0:
            yes_price_cents = yes_bid
        else:
            yes_price_cents = 0

        market_prob = yes_price_cents / 100  # Convert cents to probability

        # Skip if no price data
        if market_prob <= 0:
            continue

        # Calculate hours to expiry
        hours_to_expiry = calculate_hours_to_expiry(ticker, market.get('close_time'))

        market_info = {
            'ticker': ticker,
            'subtitle': subtitle,
            'lower': lower,
            'upper': upper,
            'is_tail': is_tail,
            'yes_bid': yes_bid,
            'yes_ask': yes_ask,
            'market_prob': market_prob,
            'hours_to_expiry': hours_to_expiry,
            'volume': market.get('volume', 0),
            'open_interest': market.get('open_interest', 0),
        }

        if is_tail == 'low':
            tail_low_markets.append(market_info)
        elif is_tail == 'high':
            tail_high_markets.append(market_info)
        else:
            range_markets.append(market_info)

    print(f"    Found {len(range_markets)} range markets")
    print(f"    Found {len(tail_low_markets)} tail-low markets ('X or below')")
    print(f"    Found {len(tail_high_markets)} tail-high markets ('X or above')")
    print(f"    Skipped {skipped} markets (no data)")

    # Step 5: Calculate probabilities
    print("\n[4] CALCULATING MODEL PROBABILITIES...")

    # Hourly volatility from annualized (365 days * 24 hours)
    hourly_vol = current_vol / np.sqrt(365 * 24)
    print(f"    Hourly vol: {hourly_vol:.3%}")

    all_analyzed = []

    # Process range markets
    for market in range_markets:
        lower = market['lower']
        upper = market['upper']
        hours = market['hours_to_expiry']
        market_prob = market['market_prob']

        # Period volatility
        period_vol = hourly_vol * np.sqrt(hours)

        # P(lower < S_T < upper) = P(S_T < upper) - P(S_T < lower)
        if period_vol > 0:
            z_lower = np.log(lower / current_btc_price) / period_vol
            z_upper = np.log(upper / current_btc_price) / period_vol
            prob_in_range = float(norm.cdf(z_upper) - norm.cdf(z_lower))
        else:
            prob_in_range = 1.0 if lower <= current_btc_price < upper else 0.0

        # Expected value
        ev = prob_in_range - market_prob

        market['model_prob'] = prob_in_range
        market['ev'] = ev
        market['midpoint'] = (lower + upper) / 2

        # Signal based on EV threshold
        if ev >= 0.04:
            market['signal'] = 'BUY'
        elif ev <= -0.04:
            market['signal'] = 'SELL'
        else:
            market['signal'] = '-'

        all_analyzed.append(market)

    # Process tail-low markets ("X or below")
    for market in tail_low_markets:
        upper = market['upper']
        hours = market['hours_to_expiry']
        market_prob = market['market_prob']

        period_vol = hourly_vol * np.sqrt(hours)

        if period_vol > 0:
            z = np.log(upper / current_btc_price) / period_vol
            prob_below = float(norm.cdf(z))
        else:
            prob_below = 1.0 if current_btc_price <= upper else 0.0

        ev = prob_below - market_prob

        market['model_prob'] = prob_below
        market['ev'] = ev
        market['midpoint'] = upper

        if ev >= 0.04:
            market['signal'] = 'BUY'
        elif ev <= -0.04:
            market['signal'] = 'SELL'
        else:
            market['signal'] = '-'

        all_analyzed.append(market)

    # Process tail-high markets ("X or above")
    for market in tail_high_markets:
        lower = market['lower']
        hours = market['hours_to_expiry']
        market_prob = market['market_prob']

        period_vol = hourly_vol * np.sqrt(hours)

        if period_vol > 0:
            z = np.log(lower / current_btc_price) / period_vol
            prob_above = float(1 - norm.cdf(z))
        else:
            prob_above = 1.0 if current_btc_price >= lower else 0.0

        ev = prob_above - market_prob

        market['model_prob'] = prob_above
        market['ev'] = ev
        market['midpoint'] = lower

        if ev >= 0.04:
            market['signal'] = 'BUY'
        elif ev <= -0.04:
            market['signal'] = 'SELL'
        else:
            market['signal'] = '-'

        all_analyzed.append(market)

    # Sort by midpoint (price level)
    range_markets.sort(key=lambda x: x['midpoint'], reverse=True)
    tail_low_markets.sort(key=lambda x: x['midpoint'], reverse=True)
    tail_high_markets.sort(key=lambda x: x['midpoint'], reverse=True)

    # Print Range Markets
    print("\n" + "-"*115)
    print("  RANGE MARKETS - YES = BTC settles within range")
    print("-"*115)
    print(f"  {'Ticker':<28} {'Range':<22} {'Hrs':>4} {'Bid/Ask':>9} {'Model':>6} {'EV':>6} {'Vol':>5} {'Signal':<6}")
    print("-"*115)

    for m in range_markets[:40]:
        ticker_short = m['ticker'][-27:] if len(m['ticker']) > 27 else m['ticker']
        range_str = f"${m['lower']:,.0f}-{m['upper']:,.0f}"
        bid_ask = f"{m.get('yes_bid',0):>2}/{m.get('yes_ask',0):<2}¢"
        print(f"  {ticker_short:<28} {range_str:<22} {m['hours_to_expiry']:>3.1f}h {bid_ask:>9} {m['model_prob']:>5.0%} {m['ev']:>+5.0%} {m['volume']:>5} {m['signal']:<6}")

    # Print Tail Markets
    if tail_low_markets:
        print("\n" + "-"*115)
        print("  TAIL-LOW MARKETS - YES = BTC settles at or below threshold")
        print("-"*115)
        print(f"  {'Ticker':<28} {'Threshold':<22} {'Hrs':>4} {'Bid/Ask':>9} {'Model':>6} {'EV':>6} {'Vol':>5} {'Signal':<6}")
        print("-"*115)

        for m in tail_low_markets[:20]:
            ticker_short = m['ticker'][-27:] if len(m['ticker']) > 27 else m['ticker']
            thresh_str = f"<= ${m['upper']:,.0f}"
            bid_ask = f"{m.get('yes_bid',0):>2}/{m.get('yes_ask',0):<2}¢"
            print(f"  {ticker_short:<28} {thresh_str:<22} {m['hours_to_expiry']:>3.1f}h {bid_ask:>9} {m['model_prob']:>5.0%} {m['ev']:>+5.0%} {m['volume']:>5} {m['signal']:<6}")

    if tail_high_markets:
        print("\n" + "-"*115)
        print("  TAIL-HIGH MARKETS - YES = BTC settles at or above threshold")
        print("-"*115)
        print(f"  {'Ticker':<28} {'Threshold':<22} {'Hrs':>4} {'Bid/Ask':>9} {'Model':>6} {'EV':>6} {'Vol':>5} {'Signal':<6}")
        print("-"*115)

        for m in tail_high_markets[:20]:
            ticker_short = m['ticker'][-27:] if len(m['ticker']) > 27 else m['ticker']
            thresh_str = f">= ${m['lower']:,.0f}"
            bid_ask = f"{m.get('yes_bid',0):>2}/{m.get('yes_ask',0):<2}¢"
            print(f"  {ticker_short:<28} {thresh_str:<22} {m['hours_to_expiry']:>3.1f}h {bid_ask:>9} {m['model_prob']:>5.0%} {m['ev']:>+5.0%} {m['volume']:>5} {m['signal']:<6}")

    # Summary
    print("\n" + "="*100)
    print("  SUMMARY")
    print("="*100)

    buy_opps = [m for m in all_analyzed if m['ev'] >= 0.04]
    sell_opps = [m for m in all_analyzed if m['ev'] <= -0.04]

    print(f"\n  Current BTC Price: ${current_btc_price:,.2f}")
    print(f"  GARCH Volatility: {current_vol:.1%} annualized ({hourly_vol:.3%} hourly)")
    print(f"  Total Markets Analyzed: {len(all_analyzed)}")
    print(f"  BUY Opportunities (EV >= 4%): {len(buy_opps)}")
    print(f"  SELL/Avoid (EV <= -4%): {len(sell_opps)}")

    # Top BUY opportunities (highest volume with positive EV)
    buy_with_volume = [m for m in buy_opps if m['volume'] > 100]
    buy_with_volume.sort(key=lambda x: x['ev'], reverse=True)

    if buy_with_volume:
        print("\n  --- TOP BUY OPPORTUNITIES (volume > 100) ---")
        for i, m in enumerate(buy_with_volume[:10], 1):
            dist = (m['midpoint'] - current_btc_price) / current_btc_price
            print(f"  {i:>2}. {m['ticker']}")
            print(f"      {m['subtitle']} ({dist:+.1%} from current)")
            print(f"      Market: {m['market_prob']:.0%} | Model: {m['model_prob']:.0%} | EV: {m['ev']:+.0%} | Vol: {m['volume']}")
            print()

    # Reference: Model probability distribution
    print("\n  --- MODEL RANGE PROBABILITIES (Current: ${:,.0f}) ---".format(current_btc_price))

    median_hours = 1.0
    if all_analyzed:
        hours_list = sorted([m['hours_to_expiry'] for m in all_analyzed])
        median_hours = hours_list[len(hours_list) // 2] if hours_list else 1.0

    period_vol = hourly_vol * np.sqrt(median_hours)
    print(f"  (Using {median_hours:.1f}-hour horizon, period vol = {period_vol:.2%})")
    print()

    # Show probability distribution across $250 ranges
    range_width = 250
    center = int(current_btc_price / range_width) * range_width
    for offset in range(-5, 6):
        lower = center + offset * range_width
        upper = lower + range_width
        z_lower = np.log(lower / current_btc_price) / period_vol
        z_upper = np.log(upper / current_btc_price) / period_vol
        prob = norm.cdf(z_upper) - norm.cdf(z_lower)
        marker = " <-- CURRENT" if lower <= current_btc_price < upper else ""
        print(f"  ${lower:>7,.0f} - ${upper:<7,.0f}  {prob:>6.1%}{marker}")

    print("\n" + "="*100)
    print("  Analysis complete!")
    print("="*100 + "\n")

    return all_analyzed


if __name__ == "__main__":
    results = main()
