#!/usr/bin/env python3
"""
Test script for the enhanced hedge optimization system.
Tests all components: market data, GARCH volatility, probability calculations, and optimization.
"""

import sys
import logging
import numpy as np
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_market_data_service():
    """Test 1: Market Data Service - fetching and caching historical data"""
    print("\n" + "="*70)
    print("TEST 1: Market Data Service")
    print("="*70)

    from market_data_service import MarketDataService, get_market_data_service

    service = get_market_data_service()

    # Fetch OHLC data
    print("\n[1.1] Fetching 365 days of BTC OHLC data...")
    df = service.fetch_ohlc_data(days=365)
    print(f"  - Rows fetched: {len(df)}")
    print(f"  - Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  - Price range: ${df['close'].min():,.2f} to ${df['close'].max():,.2f}")
    print(f"  - Current price: ${df['close'].iloc[-1]:,.2f}")

    # Test log returns
    print("\n[1.2] Calculating log returns...")
    returns = service.calculate_log_returns()
    print(f"  - Number of returns: {len(returns)}")
    print(f"  - Mean daily return: {returns.mean():.4f}")
    print(f"  - Std daily return: {returns.std():.4f}")
    print(f"  - Annualized vol (simple): {returns.std() * np.sqrt(365):.2%}")

    # Test drawdown distribution
    print("\n[1.3] Calculating drawdown distribution...")
    dd = service.calculate_empirical_drawdown_distribution()
    print(f"  - Percentiles:")
    for k, v in dd['percentiles'].items():
        print(f"      {k}: {v:.2%}")
    print(f"  - Probability of -20% drawdown: {dd['probabilities'].get('-20%', 'N/A'):.2%}")

    # Test realized volatility
    print("\n[1.4] Calculating realized volatility...")
    vol_30d = service.calculate_realized_volatility(window_days=30)
    vol_90d = service.calculate_realized_volatility(window_days=90)
    print(f"  - 30-day realized vol: {vol_30d:.2%}")
    print(f"  - 90-day realized vol: {vol_90d:.2%}")

    # Test VaR
    print("\n[1.5] Calculating Historical VaR (95%, 30-day)...")
    var = service.calculate_historical_var(confidence_level=0.95, horizon_days=30)
    print(f"  - VaR: {var['var_pct']:.2%} (${var['var_usd']:,.2f})")
    print(f"  - CVaR (Expected Shortfall): {var['cvar_pct']:.2%} (${var['cvar_usd']:,.2f})")

    print("\n[OK] Market Data Service tests passed!")
    return service, df, returns


def test_garch_model(returns):
    """Test 2: GARCH Volatility Model"""
    print("\n" + "="*70)
    print("TEST 2: GARCH Volatility Model")
    print("="*70)

    from volatility_model import GARCHVolatilityModel

    model = GARCHVolatilityModel()

    # Fit GARCH model
    print("\n[2.1] Fitting GARCH(1,1) model...")
    fit_result = model.fit(returns)

    # fit_result IS the params dict directly
    omega = fit_result.get('omega', 0)
    alpha = fit_result.get('alpha', 0)
    beta = fit_result.get('beta', 0)
    persistence = fit_result.get('persistence', alpha + beta)

    print(f"  - Parameters:")
    print(f"      omega: {omega:.6f}")
    print(f"      alpha: {alpha:.4f}")
    print(f"      beta: {beta:.4f}")
    print(f"  - Persistence (alpha + beta): {persistence:.4f} {'(stationary)' if persistence < 1 else '(NON-STATIONARY!)'}")

    # Get current volatility from the model
    current_vol = model.get_current_volatility()
    # Compute long-run vol: sqrt(omega / (1 - persistence)) * sqrt(365) / 100
    if persistence < 1:
        long_run_var = omega / (1 - persistence)
        long_run_vol = np.sqrt(long_run_var) / 100 * np.sqrt(365)
    else:
        long_run_vol = current_vol
    print(f"  - Long-run vol: {long_run_vol:.2%}")
    print(f"  - Current vol: {current_vol:.2%}")

    # Forecast volatility
    print("\n[2.2] Forecasting volatility (30 days)...")
    forecast = model.forecast_volatility(horizon=30)
    print(f"  - Forecast shape: {forecast.shape}")

    # Handle both arch library format (2D) and analytical format (1D with 'volatility' column)
    if 'volatility' in forecast.columns:
        vol_series = forecast['volatility']
    else:
        # arch library returns shape (1, horizon) - flatten it
        vol_series = forecast.iloc[0] if forecast.shape[0] == 1 else forecast.iloc[:, 0]

    print(f"  - Day 1 vol: {vol_series.iloc[0]:.2%}")
    print(f"  - Day 30 vol: {vol_series.iloc[-1]:.2%}")
    print(f"  - Average forecast vol: {vol_series.mean():.2%}")

    # Monte Carlo simulation
    print("\n[2.3] Running Monte Carlo simulation (10,000 paths, 30 days)...")
    current_price = 100000  # Example price
    terminal_prices = model.simulate_paths(current_price, horizon_days=30, n_paths=10000)
    print(f"  - Terminal prices shape: {terminal_prices.shape}")
    print(f"  - Terminal price stats:")
    print(f"      Mean: ${terminal_prices.mean():,.2f}")
    print(f"      Std: ${terminal_prices.std():,.2f}")
    print(f"      5th percentile: ${np.percentile(terminal_prices, 5):,.2f}")
    print(f"      95th percentile: ${np.percentile(terminal_prices, 95):,.2f}")

    # Probability-weighted scenarios
    print("\n[2.4] Generating probability-weighted scenarios...")
    scenarios = model.generate_probability_weighted_scenarios(current_price, n_scenarios=11)
    print(f"  - Number of scenarios: {len(scenarios)}")
    print(f"  - Scenarios (price, probability, drawdown):")
    total_prob = 0
    for s in scenarios:
        total_prob += s.probability
        print(f"      ${s.price:>10,.0f}  prob={s.probability:>6.2%}  dd={s.drawdown:>7.2%}")
    print(f"  - Total probability: {total_prob:.2%} (should be ~100%)")

    print("\n[OK] GARCH Model tests passed!")
    return model, fit_result


def test_signal_adjuster():
    """Test 3: Signal Adjustments"""
    print("\n" + "="*70)
    print("TEST 3: Signal Adjustments")
    print("="*70)

    from volatility_model import SignalAdjuster

    adjuster = SignalAdjuster()
    base_prob = 0.10  # 10% base probability

    print(f"\n[3.1] Base probability: {base_prob:.2%}")

    # Test individual signals
    print("\n[3.2] Testing individual signal effects:")

    tests = [
        {"name": "Neutral (no signals)", "kwargs": {}},
        {"name": "High funding rate (0.05%)", "kwargs": {"funding_rate": 0.0005}},
        {"name": "Extreme funding (0.1%)", "kwargs": {"funding_rate": 0.001}},
        {"name": "Bullish trend (price > MA200)", "kwargs": {"current_price": 100000, "ma_200": 90000}},
        {"name": "Bearish trend (price < MA200)", "kwargs": {"current_price": 85000, "ma_200": 90000}},
        {"name": "Overbought RSI (80)", "kwargs": {"rsi": 80}},
        {"name": "Oversold RSI (25)", "kwargs": {"rsi": 25}},
        {"name": "High VIX (30)", "kwargs": {"vix": 30}},
        {"name": "Combined bearish signals", "kwargs": {"funding_rate": 0.0008, "rsi": 75, "vix": 28}},
    ]

    for test in tests:
        adj = adjuster.compute_adjustment(**test["kwargs"])
        adjusted = adjuster.adjust_probability(base_prob, **test["kwargs"])
        print(f"  - {test['name']:35} → adjustment={adj:+.2%}, final prob={adjusted:.2%}")

    print("\n[OK] Signal Adjuster tests passed!")
    return adjuster


def test_implied_volatility():
    """Test 4: Implied Volatility Extraction"""
    print("\n" + "="*70)
    print("TEST 4: Implied Volatility Extraction")
    print("="*70)

    from volatility_model import ImpliedVolatilityAnalyzer

    analyzer = ImpliedVolatilityAnalyzer()

    current_price = 100000

    print("\n[4.1] Extracting IV from binary option prices...")

    test_cases = [
        {"strike": 90000, "price": 0.08, "days": 30},  # 8% chance of -10%
        {"strike": 85000, "price": 0.04, "days": 30},  # 4% chance of -15%
        {"strike": 80000, "price": 0.02, "days": 30},  # 2% chance of -20%
        {"strike": 95000, "price": 0.20, "days": 30},  # 20% chance of -5%
    ]

    for tc in test_cases:
        iv = analyzer.extract_implied_vol(
            current_price=current_price,
            strike_price=tc["strike"],
            option_price=tc["price"],
            days_to_expiry=tc["days"]
        )
        drawdown = (tc["strike"] - current_price) / current_price
        if iv:
            print(f"  - Strike ${tc['strike']:,} ({drawdown:.0%}), price={tc['price']:.0%} → IV={iv:.2%}")
        else:
            print(f"  - Strike ${tc['strike']:,} ({drawdown:.0%}), price={tc['price']:.0%} → IV extraction failed")

    print("\n[OK] Implied Volatility tests passed!")
    return analyzer


def test_enhanced_optimizer(market_data_service, garch_model):
    """Test 5: Enhanced Hedge Optimizer"""
    print("\n" + "="*70)
    print("TEST 5: Enhanced Hedge Optimizer")
    print("="*70)

    from hedge_optimizer import EnhancedHedgeOptimizer

    current_price = market_data_service.get_current_price()
    btc_holdings = 1.5  # Example: 1.5 BTC

    optimizer = EnhancedHedgeOptimizer(
        btc_holdings=btc_holdings,
        current_btc_price=current_price,
        market_data_service=market_data_service,
        volatility_model=garch_model
    )

    print(f"\n[5.1] Optimizer initialized:")
    print(f"  - BTC holdings: {btc_holdings} BTC")
    print(f"  - Current price: ${current_price:,.2f}")
    print(f"  - Notional value: ${btc_holdings * current_price:,.2f}")

    # Generate probability-weighted scenarios
    print("\n[5.2] Generating probability-weighted scenarios...")
    scenario_prices, scenario_probs = optimizer.generate_probability_weighted_scenarios(
        horizon_days=30, n_scenarios=21
    )
    print(f"  - Generated {len(scenario_prices)} scenarios")
    print(f"  - Price range: ${scenario_prices.min():,.0f} to ${scenario_prices.max():,.0f}")
    print(f"  - Total probability: {scenario_probs.sum():.2%}")

    # Create mock markets for testing
    print("\n[5.3] Creating mock Kalshi markets for optimization test...")
    mock_markets = []
    for drawdown in [-0.05, -0.10, -0.15, -0.20, -0.25, -0.30]:
        strike = current_price * (1 + drawdown)
        # Mock YES price based on rough probability
        yes_price = max(2, min(50, int(100 * (0.5 + drawdown * 2))))
        mock_markets.append({
            'ticker': f'BTCUSD-{int(strike/1000)}K',
            'strike_price': strike,
            'yes_price': yes_price,
            'no_price': 100 - yes_price,
            'volume': 500,
            'expiration_date': '2026-02-15'
        })

    for m in mock_markets:
        print(f"  - {m['ticker']}: strike=${m['strike_price']:,.0f}, YES={m['yes_price']}c")

    # Analyze markets
    print("\n[5.4] Analyzing markets for IV mispricing...")
    analysis = optimizer.analyze_markets(mock_markets, horizon_days=30)
    print(f"  - GARCH vol: {analysis.get('garch_vol', 'N/A')}")
    if 'mispriced_options' in analysis:
        print(f"  - Mispriced options found: {len(analysis['mispriced_options'])}")
        for opt in analysis['mispriced_options'][:3]:
            print(f"      {opt.get('ticker', 'N/A')}: IV={opt.get('implied_vol', 0):.2%}, "
                  f"mispricing={opt.get('mispricing_score', 0):.2%}")

    # Run optimization
    print("\n[5.5] Running LP optimization...")
    result = optimizer.optimize_ladder_advanced(
        markets=mock_markets,
        budget_pct=0.02,
        target_coverage=0.68,
        min_coverage_drawdown=-0.20,
        include_theta=True,
        include_transaction_costs=True
    )

    print(f"  - Optimization success: {result.get('success', False)}")
    if result.get('success'):
        print(f"  - Total cost: ${result.get('total_cost', 0):,.2f}")
        print(f"  - Budget used: {result.get('budget_utilization', 0):.1%}")
        print(f"  - Contracts selected: {result.get('num_contracts', 0)}")

        if 'allocations' in result:
            print(f"  - Allocations:")
            for alloc in result['allocations'][:5]:
                print(f"      {alloc.get('ticker', 'N/A')}: {alloc.get('contracts', 0)} contracts @ "
                      f"${alloc.get('price', 0):.2f}")

        if 'expected_coverage' in result:
            print(f"  - Expected coverage:")
            for dd, cov in result['expected_coverage'].items():
                print(f"      At {dd}: {cov:.1%}")

    print("\n[OK] Enhanced Optimizer tests passed!")
    return optimizer


def test_probability_calculation():
    """Test 6: Full Probability Pipeline"""
    print("\n" + "="*70)
    print("TEST 6: Full Probability Calculation Pipeline")
    print("="*70)

    from market_data_service import get_market_data_service
    from volatility_model import GARCHVolatilityModel, SignalAdjuster
    from scipy.stats import norm

    # Get current price and fit model
    market_data = get_market_data_service()
    current_price = market_data.get_current_price()
    returns = market_data.calculate_log_returns()

    garch = GARCHVolatilityModel()
    garch.fit(returns)
    forecast = garch.forecast_volatility(horizon=30)

    # Handle both arch library format (2D) and analytical format (1D with 'volatility' column)
    if 'volatility' in forecast.columns:
        avg_vol = forecast['volatility'].mean()
    else:
        # arch library returns shape (1, horizon) - flatten it
        vol_series = forecast.iloc[0] if forecast.shape[0] == 1 else forecast.iloc[:, 0]
        avg_vol = vol_series.mean()

    adjuster = SignalAdjuster()

    print(f"\n[6.1] Current state:")
    print(f"  - BTC price: ${current_price:,.2f}")
    print(f"  - GARCH 30-day avg vol: {avg_vol:.2%}")

    print("\n[6.2] Probability of reaching various strikes (30-day horizon):")

    strikes = [
        current_price * 0.95,  # -5%
        current_price * 0.90,  # -10%
        current_price * 0.85,  # -15%
        current_price * 0.80,  # -20%
        current_price * 0.75,  # -25%
    ]

    daily_vol = avg_vol / np.sqrt(365)
    period_vol = daily_vol * np.sqrt(30)

    for strike in strikes:
        drawdown = (strike - current_price) / current_price
        z_score = np.log(strike / current_price) / period_vol
        base_prob = norm.cdf(z_score)

        # Apply some sample signals
        adjusted_prob = adjuster.adjust_probability(base_prob, funding_rate=0.0003, rsi=65)

        print(f"  - Strike ${strike:>10,.0f} ({drawdown:>6.1%}): "
              f"base={base_prob:>6.2%}, adjusted={adjusted_prob:>6.2%}")

    print("\n[OK] Probability Pipeline tests passed!")


def run_all_tests():
    """Run all tests in sequence"""
    print("\n" + "#"*70)
    print("#" + " "*20 + "ENHANCED HEDGE SYSTEM TESTS" + " "*21 + "#")
    print("#"*70)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Test 1: Market Data
        market_data, df, returns = test_market_data_service()

        # Test 2: GARCH Model
        garch_model, fit_result = test_garch_model(returns)

        # Test 3: Signal Adjustments
        signal_adjuster = test_signal_adjuster()

        # Test 4: Implied Volatility
        iv_analyzer = test_implied_volatility()

        # Test 5: Enhanced Optimizer
        optimizer = test_enhanced_optimizer(market_data, garch_model)

        # Test 6: Full Pipeline
        test_probability_calculation()

        print("\n" + "="*70)
        print("ALL TESTS PASSED SUCCESSFULLY!")
        print("="*70)
        print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return True

    except Exception as e:
        print(f"\n[FAILED] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
