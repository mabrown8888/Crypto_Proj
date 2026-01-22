#!/usr/bin/env python3
"""
Kalshi BTC Range Market Trader
Uses GARCH probability model to identify and trade mispriced BTC range markets.
"""

import os
import sys
import logging
import numpy as np
from datetime import datetime
from scipy.stats import norm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Trading parameters
MIN_EV_THRESHOLD = 0.08          # Minimum 8% EV to trade
MIN_VOLUME = 500                  # Minimum market volume
MAX_POSITION_SIZE = 50            # Max contracts per market
MAX_TOTAL_RISK = 50.00            # Max total $ to risk per run
MIN_HOURS_TO_EXPIRY = 0.25        # At least 15 minutes to expiry
MAX_HOURS_TO_EXPIRY = 8.0         # Only trade markets expiring within 8 hours


def extract_range_from_subtitle(subtitle: str) -> tuple:
    """Extract price range from Kalshi market subtitle."""
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


def calculate_hours_to_expiry(ticker: str) -> float:
    """Calculate hours until expiration from ticker."""
    if not ticker:
        return 24.0

    parts = ticker.split('-')
    if len(parts) >= 2:
        date_part = parts[1]  # e.g., "26JAN1416"
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


def calculate_model_probability(lower: float, upper: float, is_tail: str,
                                current_price: float, hourly_vol: float, hours: float) -> float:
    """Calculate model probability for a range market."""
    period_vol = hourly_vol * np.sqrt(hours)

    if period_vol <= 0:
        return 0.0

    if is_tail == 'low':
        # P(S_T <= upper)
        z = np.log(upper / current_price) / period_vol
        return float(norm.cdf(z))
    elif is_tail == 'high':
        # P(S_T >= lower)
        z = np.log(lower / current_price) / period_vol
        return float(1 - norm.cdf(z))
    else:
        # P(lower < S_T < upper)
        z_lower = np.log(lower / current_price) / period_vol
        z_upper = np.log(upper / current_price) / period_vol
        return float(norm.cdf(z_upper) - norm.cdf(z_lower))


def analyze_markets(kalshi, current_btc_price: float, hourly_vol: float):
    """Analyze all BTC markets and return trading opportunities."""

    # Fetch KXBTC hourly markets
    result = kalshi._make_authenticated_request('GET', '/markets?series_ticker=KXBTC&status=open&limit=200')
    markets = result.get('markets', []) if result else []

    opportunities = []

    for market in markets:
        ticker = market.get('ticker', '')
        subtitle = market.get('subtitle', '')

        # Parse range
        lower, upper, is_tail = extract_range_from_subtitle(subtitle)
        if lower is None:
            continue

        # Get hours to expiry
        hours = calculate_hours_to_expiry(ticker)

        # Filter by expiry time
        if hours < MIN_HOURS_TO_EXPIRY or hours > MAX_HOURS_TO_EXPIRY:
            continue

        # Get market prices (in cents)
        yes_bid = market.get('yes_bid', 0)
        yes_ask = market.get('yes_ask', 0)
        volume = market.get('volume', 0)

        # Skip low volume markets
        if volume < MIN_VOLUME:
            continue

        # Skip if no ask (can't buy)
        if yes_ask <= 0:
            continue

        # Calculate model probability
        model_prob = calculate_model_probability(lower, upper, is_tail,
                                                  current_btc_price, hourly_vol, hours)

        # Market probability (using ask price for buying)
        market_prob = yes_ask / 100.0

        # Calculate EV
        ev = model_prob - market_prob

        # Only consider BUY opportunities with sufficient EV
        if ev >= MIN_EV_THRESHOLD:
            opportunities.append({
                'ticker': ticker,
                'subtitle': subtitle,
                'lower': lower,
                'upper': upper,
                'is_tail': is_tail,
                'hours': hours,
                'yes_bid': yes_bid,
                'yes_ask': yes_ask,
                'volume': volume,
                'model_prob': model_prob,
                'market_prob': market_prob,
                'ev': ev,
            })

    # Sort by EV descending
    opportunities.sort(key=lambda x: x['ev'], reverse=True)

    return opportunities


def calculate_position_size(ev: float, ask_price: int, balance: float,
                            total_risked: float) -> int:
    """
    Calculate position size using Kelly-inspired sizing.
    More conservative than full Kelly.
    """
    # Available budget
    available = min(MAX_TOTAL_RISK - total_risked, balance * 0.1)  # Max 10% of balance per run

    if available <= 0:
        return 0

    # Cost per contract in dollars
    cost_per_contract = ask_price / 100.0

    # Max contracts we can afford
    max_affordable = int(available / cost_per_contract)

    # Kelly fraction (using 1/4 Kelly for safety)
    # f* = (bp - q) / b where b = (1-p)/p, p = model_prob
    # Simplified: position proportional to EV
    kelly_fraction = 0.25
    suggested = int(max_affordable * min(ev * 2, 0.5) * kelly_fraction)

    # Apply position limits
    position = min(suggested, MAX_POSITION_SIZE, max_affordable)

    return max(1, position) if position > 0 else 0


def execute_trades(kalshi, opportunities: list, balance: float, dry_run: bool = True):
    """Execute trades on the best opportunities."""

    total_risked = 0.0
    trades_executed = []

    print("\n" + "="*80)
    print("  TRADE EXECUTION" + (" (DRY RUN)" if dry_run else " (LIVE)"))
    print("="*80)

    for opp in opportunities:
        # Check budget
        if total_risked >= MAX_TOTAL_RISK:
            print(f"\n  Budget exhausted (${total_risked:.2f} / ${MAX_TOTAL_RISK:.2f})")
            break

        # Calculate position size
        position = calculate_position_size(
            opp['ev'],
            opp['yes_ask'],
            balance,
            total_risked
        )

        if position <= 0:
            continue

        cost = position * opp['yes_ask'] / 100.0
        potential_profit = position * (1.0 - opp['yes_ask'] / 100.0)

        print(f"\n  Opportunity: {opp['ticker']}")
        print(f"    Range: {opp['subtitle']}")
        print(f"    Expiry: {opp['hours']:.1f} hours")
        print(f"    Model: {opp['model_prob']:.1%} | Ask: {opp['yes_ask']}¢ | EV: {opp['ev']:+.1%}")
        print(f"    Volume: {opp['volume']:,}")
        print(f"    Order: BUY {position} YES @ {opp['yes_ask']}¢ = ${cost:.2f}")
        print(f"    Potential profit if YES: ${potential_profit:.2f} ({potential_profit/cost*100:.0f}% return)")

        if not dry_run:
            # Place the order
            result = kalshi.place_order(
                ticker=opp['ticker'],
                side='yes',
                quantity=position,
                price=opp['yes_ask'],
                order_type='limit'
            )

            if result:
                print(f"    ✓ ORDER PLACED: {result.get('order_id', 'N/A')}")
                trades_executed.append({
                    'ticker': opp['ticker'],
                    'side': 'yes',
                    'quantity': position,
                    'price': opp['yes_ask'],
                    'cost': cost,
                    'ev': opp['ev'],
                    'order_id': result.get('order_id')
                })
                total_risked += cost
            else:
                print(f"    ✗ ORDER FAILED")
        else:
            print(f"    [DRY RUN - no order placed]")
            trades_executed.append({
                'ticker': opp['ticker'],
                'side': 'yes',
                'quantity': position,
                'price': opp['yes_ask'],
                'cost': cost,
                'ev': opp['ev'],
                'order_id': 'DRY_RUN'
            })
            total_risked += cost

    return trades_executed, total_risked


def main(dry_run: bool = True):
    """Main trading function."""

    print("\n" + "="*80)
    print("       KALSHI BTC RANGE MARKET TRADER - GARCH PROBABILITY MODEL")
    print("="*80)

    # Import modules
    from kalshi_engine import KalshiEngine
    from market_data_service import get_market_data_service
    from volatility_model import GARCHVolatilityModel

    # Initialize Kalshi
    print("\n[1] CONNECTING TO KALSHI...")
    kalshi = KalshiEngine()

    if not kalshi.is_connected:
        print("    ERROR: Could not connect to Kalshi")
        return None

    balance_info = kalshi.get_balance()
    balance = balance_info['balance']
    print(f"    Connected! Balance: ${balance:,.2f}")

    # Get REAL-TIME BTC price from Coinbase (not cached data!)
    print("\n[2] FETCHING REAL-TIME BTC PRICE...")
    import requests
    try:
        r = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=10)
        current_btc_price = float(r.json()['data']['amount'])
        print(f"    Real-time BTC (Coinbase): ${current_btc_price:,.2f}")
    except Exception as e:
        print(f"    WARNING: Could not get real-time price: {e}")
        print(f"    Falling back to cached data...")
        market_data = get_market_data_service()
        df = market_data.fetch_ohlc_data(days=1)
        current_btc_price = float(df['close'].iloc[-1])
        print(f"    Cached BTC price: ${current_btc_price:,.2f}")

    # Fit GARCH model for volatility estimation
    print("\n[3] FITTING GARCH MODEL...")
    market_data = get_market_data_service()
    df = market_data.fetch_ohlc_data(days=365)

    returns = market_data.calculate_log_returns()
    garch = GARCHVolatilityModel()
    fit_result = garch.fit(returns)

    current_vol = garch.get_current_volatility()
    hourly_vol = current_vol / np.sqrt(365 * 24)

    print(f"    GARCH Vol: {current_vol:.1%} annualized ({hourly_vol:.3%} hourly)")

    # Analyze markets
    print("\n[4] ANALYZING MARKETS...")
    print(f"    Filters: EV >= {MIN_EV_THRESHOLD:.0%}, Volume >= {MIN_VOLUME}, "
          f"Expiry: {MIN_HOURS_TO_EXPIRY:.1f}-{MAX_HOURS_TO_EXPIRY:.1f}h")

    opportunities = analyze_markets(kalshi, current_btc_price, hourly_vol)

    print(f"    Found {len(opportunities)} trading opportunities")

    if not opportunities:
        print("\n    No opportunities meeting criteria. Market may be efficiently priced.")
        return []

    # Show top opportunities
    print("\n" + "-"*80)
    print("  TOP OPPORTUNITIES")
    print("-"*80)
    print(f"  {'Ticker':<28} {'Range':<20} {'Hrs':>4} {'Ask':>5} {'Model':>6} {'EV':>6} {'Vol':>6}")
    print("-"*80)

    for opp in opportunities[:10]:
        range_str = opp['subtitle'][:19] if len(opp['subtitle']) > 19 else opp['subtitle']
        print(f"  {opp['ticker']:<28} {range_str:<20} {opp['hours']:>3.1f}h "
              f"{opp['yes_ask']:>4}¢ {opp['model_prob']:>5.0%} {opp['ev']:>+5.0%} {opp['volume']:>6}")

    # Execute trades
    print("\n[5] EXECUTING TRADES...")
    trades, total_risked = execute_trades(kalshi, opportunities, balance, dry_run=dry_run)

    # Summary
    print("\n" + "="*80)
    print("  SUMMARY")
    print("="*80)
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE TRADING'}")
    print(f"  Trades: {len(trades)}")
    print(f"  Total risked: ${total_risked:.2f}")
    print(f"  Remaining balance: ${balance - total_risked:.2f}")

    if trades:
        avg_ev = np.mean([t['ev'] for t in trades])
        print(f"  Average EV: {avg_ev:+.1%}")

        expected_profit = sum(t['cost'] * t['ev'] / (1 - t['price']/100) for t in trades)
        print(f"  Expected profit (if model correct): ${expected_profit:.2f}")

    print("="*80 + "\n")

    return trades


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Kalshi BTC Range Market Trader')
    parser.add_argument('--live', action='store_true', help='Execute live trades (default: dry run)')
    parser.add_argument('--min-ev', type=float, default=0.08, help='Minimum EV threshold (default: 0.08)')
    parser.add_argument('--max-risk', type=float, default=50.0, help='Max total risk in dollars (default: 50)')

    args = parser.parse_args()

    # Update parameters if provided
    if args.min_ev:
        MIN_EV_THRESHOLD = args.min_ev
    if args.max_risk:
        MAX_TOTAL_RISK = args.max_risk

    # Run trader
    trades = main(dry_run=not args.live)
