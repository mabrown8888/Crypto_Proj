#!/usr/bin/env python3
"""Debug script to see why opportunities are being filtered out."""

import sys
sys.path.insert(0, '/Users/maxbrown/Desktop/CodeProjs/trading-bot-dashboard/backend')

from kalshi_engine import KalshiEngine
from datetime import datetime
import requests

# Thresholds from kalshi_ml_trader.py
MIN_EV_THRESHOLD = 0.05
MIN_ML_SCORE = 0.55
MIN_MODEL_PROB = 0.08
MIN_VOLUME = 100  # This might be the problem
MIN_HOURS_TO_EXPIRY = 0.25
MAX_HOURS_TO_EXPIRY = 6.0

def calculate_hours(ticker):
    """Calculate hours until expiration."""
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

def parse_range(subtitle):
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

# Get current BTC price
r = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=10)
btc_price = float(r.json()['data']['amount'])
print(f"Current BTC: ${btc_price:,.2f}")
print("=" * 100)

# Initialize Kalshi
kalshi = KalshiEngine()

# Fetch markets
result = kalshi._make_authenticated_request('GET', '/markets?series_ticker=KXBTC&status=open&limit=200')
markets = result.get('markets', []) if result else []

print(f"\nFound {len(markets)} total KXBTC markets\n")

# Track filter stats
total = 0
filtered_time = 0
filtered_volume = 0
filtered_tail = 0
filtered_no_ask = 0
passed_filters = 0

print(f"{'Ticker':<32} {'Range':<22} {'Hours':>6} {'Vol':>6} {'Ask':>5} {'Reason':<20}")
print("-" * 100)

# Find markets where current price is IN the range
relevant_markets = []

for market in markets:
    ticker = market.get('ticker', '')
    subtitle = market.get('subtitle', '')
    volume = market.get('volume', 0)
    yes_ask = market.get('yes_ask', 0)

    lower, upper, is_tail = parse_range(subtitle)
    if lower is None:
        continue

    total += 1
    hours = calculate_hours(ticker)

    # Check if price is in range
    price_in_range = lower <= btc_price < upper if upper != float('inf') else btc_price >= lower

    range_str = f"${lower:,.0f}-${upper:,.0f}" if upper != float('inf') else f">${lower:,.0f}"

    reasons = []

    if is_tail:
        filtered_tail += 1
        reasons.append("tail market")

    if hours < MIN_HOURS_TO_EXPIRY:
        filtered_time += 1
        reasons.append(f"hours<{MIN_HOURS_TO_EXPIRY}")
    elif hours > MAX_HOURS_TO_EXPIRY:
        filtered_time += 1
        reasons.append(f"hours>{MAX_HOURS_TO_EXPIRY}")

    if volume < MIN_VOLUME:
        filtered_volume += 1
        reasons.append(f"vol<{MIN_VOLUME}")

    if yes_ask <= 0:
        filtered_no_ask += 1
        reasons.append("no ask")

    reason_str = ", ".join(reasons) if reasons else "PASSES ALL"

    # Highlight markets where price is in range
    marker = " *** PRICE IN RANGE ***" if price_in_range and not is_tail else ""

    if not reasons:
        passed_filters += 1

    if price_in_range or not reasons:
        print(f"{ticker:<32} {range_str:<22} {hours:>5.1f}h {volume:>6} {yes_ask:>4}c {reason_str}{marker}")
        if price_in_range and not is_tail:
            relevant_markets.append({
                'ticker': ticker,
                'lower': lower,
                'upper': upper,
                'hours': hours,
                'volume': volume,
                'yes_ask': yes_ask,
                'reasons': reasons
            })

print("\n" + "=" * 100)
print(f"\nSUMMARY:")
print(f"  Total markets: {total}")
print(f"  Filtered by time: {filtered_time}")
print(f"  Filtered by volume: {filtered_volume}")
print(f"  Filtered by tail: {filtered_tail}")
print(f"  Filtered by no ask: {filtered_no_ask}")
print(f"  Passed all filters: {passed_filters}")

print(f"\n\nMARKETS WHERE BTC (${btc_price:,.2f}) IS IN RANGE:")
print("-" * 100)
for m in relevant_markets:
    status = "PASSES" if not m['reasons'] else f"BLOCKED: {', '.join(m['reasons'])}"
    print(f"  {m['ticker']}: ${m['lower']:,.0f}-${m['upper']:,.0f}, {m['hours']:.1f}h, vol={m['volume']}, ask={m['yes_ask']}c")
    print(f"    -> {status}")
