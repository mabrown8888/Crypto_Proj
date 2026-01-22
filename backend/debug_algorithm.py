#!/usr/bin/env python3
"""
Debug script to see exactly what the ML algorithm is doing.
Run this to understand the probability calculations and signal weights.
"""

import sys
sys.path.insert(0, '/Users/maxbrown/Desktop/CodeProjs/trading-bot-dashboard/backend')

import json
import requests
from datetime import datetime
from kalshi_ml_trader import (
    SmartKalshiTrader,
    MIN_EV_ADJUSTED, MIN_EV_RAW, MIN_ML_SCORE_HARD, MIN_VOLUME,
    MIN_MODEL_PROB, MAX_MODEL_PROB, HIGH_EDGE_OVERRIDE
)

def main():
    print("=" * 80)
    print("KALSHI ML ALGORITHM DEBUG")
    print("=" * 80)

    # Initialize trader
    print("\n[1] Initializing Smart Kalshi Trader...")
    trader = SmartKalshiTrader()
    trader.initialize()

    # Show current state
    print(f"\n[2] CURRENT MARKET STATE")
    print("-" * 40)
    print(f"BTC Price: ${trader.current_price:,.2f}")
    print(f"Direction: {trader.signals.get('direction', 'UNKNOWN')}")
    print(f"Direction Score: {trader.signals.get('direction_score', 0):.3f}")

    # Show all signals
    print(f"\n[3] ALL INPUT SIGNALS")
    print("-" * 40)
    signals = trader.signals

    # Price momentum
    print(f"RSI: {signals.get('rsi', 50):.1f}")
    print(f"Momentum 4h: {signals.get('momentum_4h', 0):.2f}%")
    print(f"Momentum 24h: {signals.get('momentum_24h', 0):.2f}%")

    # Volatility
    print(f"\nVolatility Regime: {signals.get('vol_regime', 1.0):.3f}")
    print(f"GARCH Vol (ann): {trader.vol_model.get_adjusted_vol(24) * 100:.1f}%")

    # External signals
    print(f"\nFunding Rate: {signals.get('funding_rate', 0) * 10000:.2f} bps")
    print(f"Fear & Greed: {signals.get('fear_greed', 50)}")
    print(f"Whale Activity: {signals.get('whale_activity', 0):.3f}")

    # Enhanced data signals
    print(f"\n[4] ENHANCED DATA SIGNALS")
    print("-" * 40)

    # Load cached data
    cache_dir = '/Users/maxbrown/Desktop/CodeProjs/trading-bot-dashboard/backend/cache/enhanced_data'

    try:
        with open(f'{cache_dir}/deribit_options.json') as f:
            deribit = json.load(f)
        print(f"Deribit DVOL: {deribit.get('dvol', 0):.1f}%")
        print(f"DVOL 24h Change: {deribit.get('dvol_24h_change', 0):+.2f}%")
        print(f"7d ATM IV: {deribit.get('atm_iv', {}).get('7d', {}).get('iv', 0):.1f}%")
        print(f"Signal: {deribit.get('signal', {}).get('direction', 'N/A')}")
    except Exception as e:
        print(f"Deribit data unavailable: {e}")

    try:
        with open(f'{cache_dir}/open_interest.json') as f:
            oi = json.load(f)
        print(f"\nOpen Interest: {oi.get('open_interest_btc', 0):,.0f} BTC")
        print(f"Long/Short Ratio: {oi.get('long_short_ratio', 1.0):.3f}")
        print(f"Long: {oi.get('long_pct', 50):.1f}% / Short: {oi.get('short_pct', 50):.1f}%")
    except Exception as e:
        print(f"OI data unavailable: {e}")

    try:
        with open(f'{cache_dir}/orderbook.json') as f:
            ob = json.load(f)
        print(f"\nOrder Book Imbalance: {ob.get('imbalance', 0)*100:+.1f}%")
        print(f"Bid Wall: ${ob.get('walls', {}).get('bid_wall', 0):,.0f}")
        print(f"Ask Wall: ${ob.get('walls', {}).get('ask_wall', 0):,.0f}")
    except Exception as e:
        print(f"Orderbook data unavailable: {e}")

    # Analyze markets
    print(f"\n[5] MARKET ANALYSIS (QUANT-GRADE v2)")
    print("-" * 40)
    print(f"Filters:")
    print(f"  Risk-Adjusted EV >= {MIN_EV_ADJUSTED}σ")
    print(f"  Raw EV >= {MIN_EV_RAW*100}%")
    print(f"  ML Score >= {MIN_ML_SCORE_HARD} (hard floor)")
    print(f"  Model Prob: {MIN_MODEL_PROB*100}% - {MAX_MODEL_PROB*100}%")
    print(f"  HIGH EDGE OVERRIDE: {HIGH_EDGE_OVERRIDE*100}%+ EV bypasses prob bounds")
    print(f"  Volume >= {MIN_VOLUME}")

    # Clear any previous rejected opportunities
    trader._rejected_opportunities = []

    # First, let's see raw market data before any filtering
    print("\n[5a] RAW MARKET DATA (before filtering)")
    print("-" * 40)

    # Fetch raw KXBTC markets
    result = trader.kalshi._make_authenticated_request(
        'GET',
        '/markets?series_ticker=KXBTC&status=open&limit=200'
    )
    kxbtc_markets = result.get('markets', []) if result else []
    print(f"KXBTC (range) markets: {len(kxbtc_markets)}")

    # Fetch raw KXBTCD markets
    result = trader.kalshi._make_authenticated_request(
        'GET',
        '/markets?series_ticker=KXBTCD&status=open&limit=100'
    )
    kxbtcd_markets = result.get('markets', []) if result else []
    print(f"KXBTCD (threshold) markets: {len(kxbtcd_markets)}")

    # Show sample markets
    if kxbtc_markets:
        print(f"\nSample KXBTC markets:")
        for m in kxbtc_markets[:3]:
            print(f"  {m.get('ticker')}: vol={m.get('volume', 0)}, yes_ask={m.get('yes_ask')}c, subtitle={m.get('subtitle', '')[:40]}")

    if kxbtcd_markets:
        print(f"\nSample KXBTCD markets:")
        for m in kxbtcd_markets[:3]:
            print(f"  {m.get('ticker')}: vol={m.get('volume', 0)}, yes_ask={m.get('yes_ask')}c, no_ask={m.get('no_ask')}c")

    # Count markets by volume
    vol_25_plus = sum(1 for m in kxbtc_markets + kxbtcd_markets if m.get('volume', 0) >= 25)
    vol_10_plus = sum(1 for m in kxbtc_markets + kxbtcd_markets if m.get('volume', 0) >= 10)
    vol_1_plus = sum(1 for m in kxbtc_markets + kxbtcd_markets if m.get('volume', 0) >= 1)
    print(f"\nVolume distribution:")
    print(f"  Volume >= 25: {vol_25_plus} markets")
    print(f"  Volume >= 10: {vol_10_plus} markets")
    print(f"  Volume >= 1: {vol_1_plus} markets")

    opportunities = trader.analyze_all_markets()

    print(f"\nFound {len(opportunities)} opportunities passing ALL filters")

    # Show rejected opportunities for debugging
    rejected = getattr(trader, '_rejected_opportunities', [])
    print(f"\n[5b] REJECTED BY EV/ML FILTERS: {len(rejected)} markets")

    if rejected:
        print("-" * 40)

        # Sort rejected by raw EV descending
        rejected_sorted = sorted(rejected, key=lambda x: x.get('ev', 0), reverse=True)

        print(f"Showing top 10 by raw EV:")
        for i, opp in enumerate(rejected_sorted[:10], 1):
            print(f"\n  #{i} {opp.get('ticker', 'N/A')}")
            print(f"      Subtitle: {opp.get('subtitle', 'N/A')[:50]}")
            print(f"      Model Prob: {opp.get('model_prob', 0)*100:.1f}% | Market: {opp.get('market_prob', 0)*100:.1f}%")
            print(f"      Raw EV: {opp.get('ev', 0)*100:+.2f}%")
            print(f"      Risk-Adj EV: {opp.get('ev_adjusted', 0):+.2f}σ")
            print(f"      ML Score: {opp.get('ml_score', 0):.3f}")
            print(f"      Rejection: {', '.join(opp.get('rejection_reasons', ['unknown']))}")
    else:
        print("  (No markets reached EV filtering stage - all filtered by volume/time/other early filters)")

    # Show top 10 opportunities with full details
    print(f"\n[6] TOP OPPORTUNITIES (Detailed)")
    print("=" * 80)

    for i, opp in enumerate(opportunities[:10], 1):
        override_flag = " [HIGH EDGE OVERRIDE]" if opp.get('high_edge_override') else ""
        print(f"\n--- Opportunity #{i}{override_flag} ---")
        print(f"Ticker: {opp.get('ticker', 'N/A')}")
        print(f"Type: {opp.get('market_type', 'range')}")
        print(f"Subtitle: {opp.get('subtitle', 'N/A')}")
        print(f"Side: {opp.get('side', 'YES').upper()}")

        if opp.get('market_type') == 'range':
            print(f"Range: ${opp.get('lower', 0):,.0f} - ${opp.get('upper', 0):,.0f}")
        else:
            print(f"Threshold: ${opp.get('threshold', 0):,.0f} ({'above' if opp.get('is_above') else 'below'})")

        print(f"\nProbabilities:")
        print(f"  Base Model Prob: {opp.get('base_model_prob', opp.get('model_prob', 0))*100:.2f}%")
        print(f"  Adjusted Model Prob: {opp.get('model_prob', 0)*100:.2f}% (log-odds adjusted)")
        print(f"  Market Probability: {opp.get('market_prob', 0)*100:.2f}%")

        print(f"\nQUANT-GRADE EV Metrics:")
        print(f"  Raw EV: {opp.get('ev', 0)*100:+.2f}%")
        print(f"  Risk-Adjusted EV: {opp.get('ev_adjusted', 0):+.2f}σ")
        print(f"  Time-Weighted EV: {opp.get('ev_time_weighted', 0)*100:+.2f}%")
        print(f"  Probability Uncertainty: {opp.get('prob_uncertainty', 0)*100:.1f}%")

        print(f"\nML & Sizing:")
        print(f"  ML Score: {opp.get('ml_score', 0):.3f}")
        print(f"  ML Size Multiplier: {opp.get('ml_size_multiplier', 1.0):.2f}x")
        print(f"  Signal Confidence: {opp.get('signal_confidence', 0):.2f}")

        print(f"\nMarket Data:")
        print(f"  Hours to Expiry: {opp.get('hours', 0):.1f}h")
        print(f"  Volume: {opp.get('volume', 0)}")
        print(f"  Price: {opp.get('price', opp.get('yes_ask', 0))}¢")

    # Summary
    print(f"\n[7] ALGORITHM SUMMARY (QUANT-GRADE v2)")
    print("=" * 80)

    if opportunities:
        avg_ev_raw = sum(o.get('ev', 0) for o in opportunities) / len(opportunities)
        avg_ev_adj = sum(o.get('ev_adjusted', 0) for o in opportunities) / len(opportunities)
        avg_ml = sum(o.get('ml_score', 0) for o in opportunities) / len(opportunities)
        avg_size_mult = sum(o.get('ml_size_multiplier', 1.0) for o in opportunities) / len(opportunities)
        yes_count = sum(1 for o in opportunities if o.get('side', '').lower() == 'yes')
        no_count = len(opportunities) - yes_count

        print(f"Total Opportunities: {len(opportunities)}")
        print(f"\nEV Metrics:")
        print(f"  Average Raw EV: {avg_ev_raw*100:+.2f}%")
        print(f"  Average Risk-Adjusted EV: {avg_ev_adj:+.2f}σ")
        print(f"\nML & Sizing:")
        print(f"  Average ML Score: {avg_ml:.3f}")
        print(f"  Average Size Multiplier: {avg_size_mult:.2f}x")
        print(f"\nBet Distribution:")
        print(f"  YES Bets: {yes_count}, NO Bets: {no_count}")
        print(f"\nTop Opportunity:")
        print(f"  Ticker: {opportunities[0].get('ticker', 'N/A')}")
        print(f"  Raw EV: {opportunities[0].get('ev', 0)*100:+.2f}%")
        print(f"  Risk-Adj EV: {opportunities[0].get('ev_adjusted', 0):+.2f}σ")
    else:
        print("No opportunities found. Possible reasons:")
        print(f"  - Risk-Adjusted EV < {MIN_EV_ADJUSTED}σ threshold")
        print(f"  - Raw EV < {MIN_EV_RAW*100}% minimum")
        print(f"  - ML score < {MIN_ML_SCORE_HARD} hard floor")
        print(f"  - Model probability outside {MIN_MODEL_PROB*100}%-{MAX_MODEL_PROB*100}%")
        print(f"  - Volume < {MIN_VOLUME}")

    print("\n" + "=" * 80)
    print("Debug complete. Data files are in:")
    print("  backend/data/kalshi_historical.csv")
    print("  backend/cache/enhanced_data/*.json")
    print("  backend/models/kalshi_btc_model.pkl")
    print("=" * 80)

if __name__ == "__main__":
    main()
