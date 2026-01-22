#!/usr/bin/env python3
"""
Monitor active Kalshi BTC positions and current BTC price.
Run this periodically to track position P&L.
"""

from datetime import datetime
import sys

def main():
    from kalshi_engine import KalshiEngine
    from market_data_service import get_market_data_service

    print("\n" + "=" * 75)
    print(f"  BTC POSITION MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 75)

    # Get current BTC price
    market_data = get_market_data_service()
    df = market_data.fetch_ohlc_data(days=1)
    btc_price = float(df['close'].iloc[-1])
    print(f"\n  Current BTC Price: ${btc_price:,.2f}")

    # Connect to Kalshi
    kalshi = KalshiEngine()
    if not kalshi.is_connected:
        print("  ERROR: Could not connect to Kalshi")
        return

    # Get positions
    result = kalshi._make_authenticated_request("GET", "/portfolio/positions")

    if not result or "market_positions" not in result:
        print("  No positions found")
        return

    # Filter for today's BTC markets
    btc_positions = []
    for p in result["market_positions"]:
        ticker = p.get("ticker", "")
        pos = p.get("position", 0)
        if "KXBTC-26JAN14" in ticker and pos != 0:
            btc_positions.append(p)

    if not btc_positions:
        print("\n  No active BTC positions for today")
        return

    print("\n" + "-" * 75)
    print(f"  {'Position':<28} {'Range':<20} {'Qty':>5} {'Cost':>7} {'Value':>7} {'P&L':>7}")
    print("-" * 75)

    total_cost = 0
    total_value = 0
    potential_win = 0

    for p in btc_positions:
        ticker = p.get("ticker")
        pos = p.get("position")
        cost = p.get("total_traded", 0) / 100
        value = p.get("market_exposure", 0) / 100
        pnl = value - cost

        total_cost += cost
        total_value += value

        # Parse range from ticker
        ticker_parts = ticker.split('-')
        if len(ticker_parts) >= 3:
            strike_part = ticker_parts[2]
            if strike_part.startswith('B'):
                strike = float(strike_part[1:])
                lower = strike - 125
                upper = strike + 125
                range_str = f"${lower:,.0f}-{upper:,.0f}"

                # Check if current price is in range
                in_range = lower <= btc_price < upper
                status = "IN RANGE" if in_range else ""

                # If we win, we get $1 per contract
                if in_range:
                    potential_win += pos * 1.0 - cost
            else:
                range_str = strike_part
                status = ""
        else:
            range_str = "?"
            status = ""

        print(f"  {ticker:<28} {range_str:<20} {pos:>5} ${cost:>6.2f} ${value:>6.2f} ${pnl:>+6.2f} {status}")

    print("-" * 75)
    print(f"  {'TOTAL':<28} {'':<20} {'':<5} ${total_cost:>6.2f} ${total_value:>6.2f} ${total_value - total_cost:>+6.2f}")

    # Calculate outcome scenarios
    print("\n" + "=" * 75)
    print("  OUTCOME SCENARIOS")
    print("=" * 75)

    # Check which positions are currently "in the money"
    winning_contracts = 0
    for p in btc_positions:
        ticker = p.get("ticker")
        pos = p.get("position")
        ticker_parts = ticker.split('-')
        if len(ticker_parts) >= 3:
            strike_part = ticker_parts[2]
            if strike_part.startswith('B'):
                strike = float(strike_part[1:])
                lower = strike - 125
                upper = strike + 125
                if lower <= btc_price < upper:
                    winning_contracts += pos

    print(f"\n  If BTC stays at ${btc_price:,.2f}:")
    print(f"    Winning contracts: {winning_contracts}")
    print(f"    Payout: ${winning_contracts * 1.0:.2f}")
    print(f"    Net P&L: ${winning_contracts * 1.0 - total_cost:+.2f}")

    # Show breakeven range
    print(f"\n  Positions expire in ~{(datetime(2026,1,14,16,16) - datetime.now()).total_seconds()/60:.0f} minutes (4:16 PM)")

    print("\n" + "=" * 75 + "\n")


if __name__ == "__main__":
    main()
