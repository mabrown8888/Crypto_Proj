import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Activity,
  AlertCircle,
  CheckCircle,
  Shield,
  Play,
  RefreshCw,
  Zap,
  Clock,
  Target
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';

const HedgeDashboard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [executionResult, setExecutionResult] = useState(null);
  const [dryRun, setDryRun] = useState(true);
  const [maxRisk, setMaxRisk] = useState(50);
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Cash-out monitor state
  const [cashOutRunning, setCashOutRunning] = useState(false);
  const [cashOutStatus, setCashOutStatus] = useState(null);
  const [cashOutLoading, setCashOutLoading] = useState(false);

  const API_BASE = 'http://localhost:5001/api/kalshi';
  const HEDGE_API = 'http://localhost:5001/api/hedge';

  const fetchOpportunities = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(`${API_BASE}/opportunities`);
      if (response.data.success) {
        setData(response.data);
        setLastUpdate(new Date());
      } else {
        setError(response.data.error || 'Failed to fetch opportunities');
      }
    } catch (err) {
      console.error('Failed to fetch opportunities:', err);
      setError(err.response?.data?.error || 'Failed to connect to server');
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-refresh every 30 seconds if enabled
  useEffect(() => {
    let interval;
    if (autoRefresh) {
      interval = setInterval(fetchOpportunities, 30000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh, fetchOpportunities]);

  const executeRecommendedTrades = async () => {
    if (!data?.recommended_trades?.length) {
      setError('No recommended trades to execute');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${API_BASE}/execute-trades`, {
        trades: data.recommended_trades,
        dry_run: dryRun,
        max_risk: maxRisk
      });

      if (response.data.success) {
        setExecutionResult(response.data);
        // Refresh opportunities after execution
        if (!dryRun) {
          setTimeout(fetchOpportunities, 2000);
        }
      } else {
        setError(response.data.error || 'Execution failed');
      }
    } catch (err) {
      console.error('Execution failed:', err);
      setError(err.response?.data?.error || 'Execution failed');
    } finally {
      setLoading(false);
    }
  };

  const formatPrice = (price) => {
    if (!price) return '-';
    return `$${price.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  };

  // Custom tooltip for chart
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const d = payload[0].payload;
      return (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 shadow-lg">
          <p className="text-gray-400 text-xs">
            {new Date(d.timestamp).toLocaleTimeString()}
          </p>
          <p className="text-white font-bold">
            ${d.price?.toLocaleString()}
          </p>
        </div>
      );
    }
    return null;
  };

  const getEvColor = (ev) => {
    if (ev >= 8) return 'text-green-400';
    if (ev >= 4) return 'text-yellow-400';
    return 'text-gray-400';
  };

  // =========================================================================
  // CASH-OUT MONITOR FUNCTIONS
  // =========================================================================

  // Check if monitor is running on component mount
  useEffect(() => {
    const checkMonitorStatus = async () => {
      try {
        const response = await axios.get(`${HEDGE_API}/cash-out/monitor/status`);
        if (response.data.success) {
          setCashOutRunning(response.data.running);
        }
      } catch (err) {
        console.error('Failed to check cash-out monitor status:', err);
      }
    };
    checkMonitorStatus();
  }, []);

  // Fetch cash-out status periodically when running
  useEffect(() => {
    let interval;
    if (cashOutRunning) {
      const fetchCashOutStatus = async () => {
        try {
          const response = await axios.get(`${HEDGE_API}/cash-out/status`);
          if (response.data.success) {
            setCashOutStatus(response.data);
          }
        } catch (err) {
          console.error('Failed to fetch cash-out status:', err);
        }
      };
      fetchCashOutStatus();
      interval = setInterval(fetchCashOutStatus, 5000); // Update status every 5s
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [cashOutRunning]);

  const startCashOutMonitor = async () => {
    setCashOutLoading(true);
    setError(null);
    try {
      const response = await axios.post(`${HEDGE_API}/cash-out/monitor/start`);
      if (response.data.success) {
        setCashOutRunning(true);
        // User sees button state change to "Stop Cash-Outs"
      }
    } catch (err) {
      console.error('Failed to start cash-out monitor:', err);
      setError('Failed to start cash-out monitor');
    } finally {
      setCashOutLoading(false);
    }
  };

  const stopCashOutMonitor = async () => {
    setCashOutLoading(true);
    setError(null);
    try {
      const response = await axios.post(`${HEDGE_API}/cash-out/monitor/stop`);
      if (response.data.success) {
        setCashOutRunning(false);
        setCashOutStatus(null);
        // User sees button state change to "Start Cash-Outs"
      }
    } catch (err) {
      console.error('Failed to stop cash-out monitor:', err);
      setError('Failed to stop cash-out monitor');
    } finally {
      setCashOutLoading(false);
    }
  };

  const syncPositions = async () => {
    setCashOutLoading(true);
    setError(null);
    try {
      const response = await axios.post(`${HEDGE_API}/cash-out/sync`);
      if (response.data.success) {
        // Don't set executionResult for sync - it's not a trade execution
        // Just refresh the status which will show updated position count
        const statusResponse = await axios.get(`${HEDGE_API}/cash-out/status`);
        if (statusResponse.data.success) {
          setCashOutStatus(statusResponse.data);
        }
        // Show brief success in console, user sees updated position count
        console.log(`Synced ${response.data.synced} positions from Kalshi`);
      }
    } catch (err) {
      console.error('Failed to sync positions:', err);
      setError('Failed to sync positions');
    } finally {
      setCashOutLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <Shield className="text-crypto-blue" size={32} />
            Kalshi Trading Bot
          </h1>
          <p className="text-gray-400 mt-1">ML-powered probability arbitrage on Kalshi markets</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-gray-600 bg-gray-700 text-crypto-blue"
            />
            Auto-refresh
          </label>
          {lastUpdate && (
            <span className="text-gray-500 text-xs">
              Updated: {lastUpdate.toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-500/20 border border-red-500 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="text-red-400 flex-shrink-0" size={20} />
          <div>
            <p className="text-red-400 font-medium">Error</p>
            <p className="text-gray-300 text-sm mt-1">{error}</p>
          </div>
        </div>
      )}

      {/* Cash-Out Monitor Control */}
      <div className={`rounded-xl p-4 border ${cashOutRunning ? 'bg-green-900/20 border-green-500' : 'bg-gray-800 border-gray-700'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-lg ${cashOutRunning ? 'bg-green-500/20' : 'bg-gray-700'}`}>
              <Target className={cashOutRunning ? 'text-green-400' : 'text-gray-400'} size={24} />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                Smart Cash-Out Monitor
                {cashOutRunning && (
                  <span className="flex items-center gap-1 text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded-full">
                    <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                    RUNNING
                  </span>
                )}
              </h3>
              <p className="text-gray-400 text-sm">
                {cashOutRunning
                  ? 'Checking positions every 30s for exit triggers'
                  : 'Click Start to begin monitoring positions for auto cash-out'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={syncPositions}
              disabled={cashOutLoading}
              className="flex items-center gap-2 px-4 py-2 bg-gray-600 hover:bg-gray-500 disabled:bg-gray-700 rounded-lg font-medium transition-colors"
              title="Import existing Kalshi positions into tracker"
            >
              {cashOutLoading ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              Sync Positions
            </button>
            {cashOutRunning ? (
              <button
                onClick={stopCashOutMonitor}
                disabled={cashOutLoading}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-700 rounded-lg font-medium transition-colors"
              >
                {cashOutLoading ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <AlertCircle className="h-4 w-4" />
                )}
                Stop Cash-Outs
              </button>
            ) : (
              <button
                onClick={startCashOutMonitor}
                disabled={cashOutLoading}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-700 rounded-lg font-medium transition-colors"
              >
                {cashOutLoading ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                Start Cash-Outs
              </button>
            )}
          </div>
        </div>

        {/* Cash-Out Status */}
        {cashOutRunning && cashOutStatus && (
          <div className="mt-4 pt-4 border-t border-gray-700">
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center">
                <p className="text-2xl font-bold text-white">{cashOutStatus.total_positions || 0}</p>
                <p className="text-gray-400 text-xs">Positions Tracked</p>
              </div>
              <div className="text-center">
                <p className={`text-2xl font-bold ${(cashOutStatus.total_unrealized_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  ${(cashOutStatus.total_unrealized_pnl || 0).toFixed(2)}
                </p>
                <p className="text-gray-400 text-xs">Unrealized P&L</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-crypto-blue">${(cashOutStatus.total_realized_pnl || 0).toFixed(2)}</p>
                <p className="text-gray-400 text-xs">Realized P&L</p>
              </div>
              <div className="text-center">
                <p className={`text-2xl font-bold ${(cashOutStatus.total_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  ${(cashOutStatus.total_pnl || 0).toFixed(2)}
                </p>
                <p className="text-gray-400 text-xs">Total P&L</p>
              </div>
            </div>

            {/* Positions Table */}
            {cashOutStatus.positions && cashOutStatus.positions.length > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-700">
                <h4 className="text-sm font-medium text-gray-400 mb-3">Position Details</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-gray-500 text-xs uppercase tracking-wider">
                        <th className="text-left pb-2 pr-4">Contract</th>
                        <th className="text-right pb-2 px-3">Entry</th>
                        <th className="text-right pb-2 px-3">Current</th>
                        <th className="text-right pb-2 px-3">P&L</th>
                        <th className="text-center pb-2 px-3">Zone</th>
                        <th className="text-left pb-2 px-3">Needs to Happen</th>
                        <th className="text-right pb-2 px-3">Expiry</th>
                        <th className="text-left pb-2 pl-4">Signal</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-700/50">
                      {cashOutStatus.positions.map((pos, idx) => {
                        // Parse ticker to get strike info (e.g., KXBTCD-26JAN2217-T86749.99 -> T86749)
                        const tickerParts = pos.ticker.split('-');
                        const shortTicker = tickerParts.length >= 3
                          ? `${tickerParts[1]} ${tickerParts[2].substring(0, 6)}...`
                          : pos.ticker.substring(0, 15);

                        const zoneColors = {
                          'DEEP_ITM': 'bg-green-500/20 text-green-400',
                          'ATM': 'bg-yellow-500/20 text-yellow-400',
                          'OTM': 'bg-red-500/20 text-red-400',
                          'unknown': 'bg-gray-500/20 text-gray-400'
                        };

                        const signalColors = {
                          'SELL': 'text-red-400',
                          'HOLD': 'text-gray-400'
                        };

                        return (
                          <tr key={idx} className="hover:bg-gray-700/30">
                            <td className="py-2 pr-4">
                              <div className="flex flex-col">
                                <span className="text-white font-medium">{shortTicker}</span>
                                <span className="text-gray-500 text-xs">{pos.side.toUpperCase()} x{pos.current_quantity}</span>
                              </div>
                            </td>
                            <td className="text-right py-2 px-3">
                              <span className="text-gray-300">{pos.entry_price?.toFixed(1)}¢</span>
                            </td>
                            <td className="text-right py-2 px-3">
                              <span className="text-white font-medium">
                                {pos.current_price ? `${pos.current_price.toFixed(1)}¢` : '—'}
                              </span>
                            </td>
                            <td className="text-right py-2 px-3">
                              <span className={`font-medium ${pos.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {pos.pnl_pct >= 0 ? '+' : ''}{pos.pnl_pct?.toFixed(1)}%
                              </span>
                            </td>
                            <td className="text-center py-2 px-3">
                              <span className={`px-2 py-0.5 rounded text-xs font-medium ${zoneColors[pos.price_zone] || zoneColors['unknown']}`}>
                                {pos.price_zone === 'DEEP_ITM' ? 'ITM' : pos.price_zone}
                              </span>
                            </td>
                            <td className="py-2 px-3">
                              <span className="text-xs text-blue-300" title={pos.what_needs_to_happen}>
                                {pos.what_needs_to_happen || '—'}
                              </span>
                            </td>
                            <td className="text-right py-2 px-3">
                              <span className={`text-xs ${pos.hours_to_expiry && pos.hours_to_expiry < 2 ? 'text-yellow-400 font-medium' : 'text-gray-400'}`}>
                                {pos.expiry_display || '—'}
                              </span>
                            </td>
                            <td className="py-2 pl-4">
                              <div className="flex flex-col">
                                <span className={`font-medium ${signalColors[pos.cash_out_signal] || 'text-gray-400'}`}>
                                  {pos.cash_out_signal}
                                </span>
                                <span className="text-gray-500 text-xs truncate max-w-[150px]" title={pos.cash_out_reason}>
                                  {pos.cash_out_reason}
                                </span>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* BTC Price Chart */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Activity className="text-crypto-yellow" size={20} />
              BTC Price
            </h3>
            {data?.btc_price && (
              <p className="text-3xl font-bold text-white mt-1">
                ${data.btc_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </p>
            )}
          </div>
          <button
            onClick={fetchOpportunities}
            disabled={loading}
            className="flex items-center gap-2 px-6 py-3 bg-crypto-blue hover:bg-blue-600 disabled:bg-gray-700 rounded-lg font-bold transition-colors"
          >
            {loading ? (
              <RefreshCw className="h-5 w-5 animate-spin" />
            ) : (
              <Play className="h-5 w-5" />
            )}
            Find Mispriced Markets
          </button>
        </div>

        {data?.price_history?.length > 0 && (
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.price_history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={(ts) => new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  stroke="#9CA3AF"
                  fontSize={11}
                />
                <YAxis
                  domain={['auto', 'auto']}
                  tickFormatter={(val) => `$${(val/1000).toFixed(1)}k`}
                  stroke="#9CA3AF"
                  fontSize={11}
                />
                <Tooltip content={<CustomTooltip />} />
                {data?.btc_price && (
                  <ReferenceLine
                    y={data.btc_price}
                    stroke="#F59E0B"
                    strokeDasharray="5 5"
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="price"
                  stroke="#3B82F6"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Summary Stats */}
      {data && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
              <Target size={16} />
              Markets Analyzed
            </div>
            <p className="text-2xl font-bold text-white">{data.total_markets_scanned || 0}</p>
          </div>
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
              <TrendingUp size={16} className="text-green-400" />
              Opportunities Found
            </div>
            <p className="text-2xl font-bold text-white">{data.opportunities?.length || 0}</p>
          </div>
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
              <Zap size={16} className="text-yellow-400" />
              Recommended Trades
            </div>
            <p className="text-2xl font-bold text-green-400">{data.recommended_trades?.length || 0}</p>
          </div>
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
              <DollarSign size={16} className="text-crypto-blue" />
              Best EV
            </div>
            <p className="text-2xl font-bold text-green-400">
              {data.opportunities?.[0]?.ev ? `+${data.opportunities[0].ev.toFixed(1)}%` : '-'}
            </p>
          </div>
        </div>
      )}

      {/* Algorithm Summary */}
      {data?.algorithm_summary && (
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Activity size={20} className="text-purple-400" />
            Algorithm Analysis
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {/* Direction */}
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-gray-500 text-xs uppercase mb-1">Direction</p>
              <p className={`text-lg font-bold ${
                data.algorithm_summary.direction === 'BULLISH' ? 'text-green-400' :
                data.algorithm_summary.direction === 'BEARISH' ? 'text-red-400' : 'text-gray-400'
              }`}>
                {data.algorithm_summary.direction}
              </p>
              <p className="text-gray-500 text-xs">
                Score: {data.algorithm_summary.direction_score}
              </p>
            </div>

            {/* RSI */}
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-gray-500 text-xs uppercase mb-1">RSI</p>
              <p className={`text-lg font-bold ${
                data.algorithm_summary.rsi > 70 ? 'text-red-400' :
                data.algorithm_summary.rsi < 30 ? 'text-green-400' : 'text-white'
              }`}>
                {data.algorithm_summary.rsi}
              </p>
              <p className="text-gray-500 text-xs">
                {data.algorithm_summary.rsi > 70 ? 'Overbought' :
                 data.algorithm_summary.rsi < 30 ? 'Oversold' : 'Neutral'}
              </p>
            </div>

            {/* Volatility */}
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-gray-500 text-xs uppercase mb-1">GARCH Vol</p>
              <p className="text-lg font-bold text-white">
                {data.algorithm_summary.garch_vol_annual}%
              </p>
              <p className="text-gray-500 text-xs">Annualized</p>
            </div>

            {/* DVOL */}
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-gray-500 text-xs uppercase mb-1">Deribit DVOL</p>
              <p className="text-lg font-bold text-white">
                {data.algorithm_summary.dvol || '-'}%
              </p>
              <p className="text-gray-500 text-xs">
                {data.algorithm_summary.dvol_signal || 'N/A'}
              </p>
            </div>

            {/* Fear & Greed */}
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-gray-500 text-xs uppercase mb-1">Fear & Greed</p>
              <p className={`text-lg font-bold ${
                data.algorithm_summary.fear_greed > 75 ? 'text-green-400' :
                data.algorithm_summary.fear_greed < 25 ? 'text-red-400' : 'text-yellow-400'
              }`}>
                {data.algorithm_summary.fear_greed}
              </p>
              <p className="text-gray-500 text-xs">
                {data.algorithm_summary.fear_greed > 75 ? 'Extreme Greed' :
                 data.algorithm_summary.fear_greed > 55 ? 'Greed' :
                 data.algorithm_summary.fear_greed > 45 ? 'Neutral' :
                 data.algorithm_summary.fear_greed > 25 ? 'Fear' : 'Extreme Fear'}
              </p>
            </div>

            {/* Funding Rate */}
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-gray-500 text-xs uppercase mb-1">Funding</p>
              <p className={`text-lg font-bold ${
                data.algorithm_summary.funding_rate_bps > 5 ? 'text-red-400' :
                data.algorithm_summary.funding_rate_bps < -5 ? 'text-green-400' : 'text-white'
              }`}>
                {data.algorithm_summary.funding_rate_bps > 0 ? '+' : ''}{data.algorithm_summary.funding_rate_bps} bps
              </p>
              <p className="text-gray-500 text-xs">
                {data.algorithm_summary.funding_rate_bps > 5 ? 'Longs pay' :
                 data.algorithm_summary.funding_rate_bps < -5 ? 'Shorts pay' : 'Neutral'}
              </p>
            </div>

            {/* Open Interest */}
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-gray-500 text-xs uppercase mb-1">Open Interest</p>
              <p className="text-lg font-bold text-white">
                {data.algorithm_summary.open_interest_btc?.toLocaleString() || '-'}
              </p>
              <p className="text-gray-500 text-xs">BTC</p>
            </div>

            {/* Long/Short Ratio */}
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-gray-500 text-xs uppercase mb-1">L/S Ratio</p>
              <p className={`text-lg font-bold ${
                data.algorithm_summary.long_short_ratio > 1.1 ? 'text-green-400' :
                data.algorithm_summary.long_short_ratio < 0.9 ? 'text-red-400' : 'text-white'
              }`}>
                {data.algorithm_summary.long_short_ratio?.toFixed(2) || '-'}
              </p>
              <p className="text-gray-500 text-xs">
                {data.algorithm_summary.long_short_ratio > 1.1 ? 'Long heavy' :
                 data.algorithm_summary.long_short_ratio < 0.9 ? 'Short heavy' : 'Balanced'}
              </p>
            </div>

            {/* Order Book */}
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-gray-500 text-xs uppercase mb-1">Order Book</p>
              <p className={`text-lg font-bold ${
                data.algorithm_summary.orderbook_imbalance > 10 ? 'text-green-400' :
                data.algorithm_summary.orderbook_imbalance < -10 ? 'text-red-400' : 'text-white'
              }`}>
                {data.algorithm_summary.orderbook_imbalance > 0 ? '+' : ''}{data.algorithm_summary.orderbook_imbalance}%
              </p>
              <p className="text-gray-500 text-xs">
                {data.algorithm_summary.orderbook_imbalance > 10 ? 'Bid heavy' :
                 data.algorithm_summary.orderbook_imbalance < -10 ? 'Ask heavy' : 'Balanced'}
              </p>
            </div>

            {/* Momentum 4h */}
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-gray-500 text-xs uppercase mb-1">4h Momentum</p>
              <p className={`text-lg font-bold ${
                data.algorithm_summary.momentum_4h > 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {data.algorithm_summary.momentum_4h > 0 ? '+' : ''}{data.algorithm_summary.momentum_4h}%
              </p>
              <p className="text-gray-500 text-xs">Price change</p>
            </div>

            {/* Momentum 24h */}
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-gray-500 text-xs uppercase mb-1">24h Momentum</p>
              <p className={`text-lg font-bold ${
                data.algorithm_summary.momentum_24h > 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {data.algorithm_summary.momentum_24h > 0 ? '+' : ''}{data.algorithm_summary.momentum_24h}%
              </p>
              <p className="text-gray-500 text-xs">Price change</p>
            </div>

            {/* Whale Activity */}
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-gray-500 text-xs uppercase mb-1">Whale Activity</p>
              <p className={`text-lg font-bold ${
                data.algorithm_summary.whale_activity > 0.5 ? 'text-yellow-400' : 'text-white'
              }`}>
                {data.algorithm_summary.whale_activity?.toFixed(2) || '0'}
              </p>
              <p className="text-gray-500 text-xs">
                {data.algorithm_summary.whale_activity > 0.5 ? 'Elevated' : 'Normal'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Opportunities Table */}
      {data?.opportunities?.length > 0 && (
        <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          <div className="p-4 border-b border-gray-700">
            <h3 className="text-lg font-semibold text-white">All Opportunities</h3>
            <p className="text-gray-400 text-sm">Sorted by Expected Value (EV)</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-900">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Market</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase">Side</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase">Market Odds</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase">Model Odds</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase">EV</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase">Price</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase">Expiry</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase">Volume</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {data.opportunities.map((opp, idx) => (
                  <tr key={opp.ticker} className={opp.recommended ? 'bg-green-900/10' : ''}>
                    <td className="px-4 py-3">
                      <div>
                        <p className="text-white font-medium text-sm">
                          {opp.subtitle || opp.ticker}
                        </p>
                        <p className="text-gray-500 text-xs">{opp.ticker}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-1 rounded text-xs font-bold ${
                        opp.side === 'YES'
                          ? 'bg-green-500/20 text-green-400'
                          : 'bg-red-500/20 text-red-400'
                      }`}>
                        {opp.side}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-300">
                      {opp.market_odds.toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right text-white font-medium">
                      {opp.model_odds.toFixed(1)}%
                    </td>
                    <td className={`px-4 py-3 text-right font-bold ${getEvColor(opp.ev)}`}>
                      +{opp.ev.toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right text-gray-300">
                      {opp.side === 'YES' ? opp.yes_ask : opp.no_ask}¢
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1 text-gray-400 text-sm">
                        <Clock size={14} />
                        {opp.hours_to_expiry}h
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-400">
                      {opp.volume}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {opp.recommended ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-green-900/50 text-green-400 text-xs font-medium">
                          <CheckCircle size={12} />
                          TRADE
                        </span>
                      ) : (
                        <span className="text-gray-500 text-xs">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recommended Trades Execution */}
      {data?.recommended_trades?.length > 0 && (
        <div className="bg-gradient-to-br from-green-900/20 to-emerald-900/20 border border-green-500/30 rounded-xl p-6">
          <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
            <Zap className="text-yellow-400" size={24} />
            Recommended Trades ({data.recommended_trades.length})
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            {data.recommended_trades.slice(0, 6).map((trade) => (
              <div key={trade.ticker} className="bg-gray-800/50 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className={`px-2 py-1 rounded text-xs font-bold ${
                    trade.side === 'YES'
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-red-500/20 text-red-400'
                  }`}>
                    {trade.side}
                  </span>
                  <span className="text-green-400 font-bold">+{trade.ev.toFixed(1)}% EV</span>
                </div>
                <p className="text-white text-sm font-medium mb-1">{trade.subtitle}</p>
                <div className="flex justify-between text-xs text-gray-400">
                  <span>Model: {trade.model_odds.toFixed(1)}%</span>
                  <span>Market: {trade.market_odds.toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>

          {/* Execution Controls */}
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-gray-400 text-sm">Max Risk:</label>
              <input
                type="number"
                min="10"
                max="500"
                step="10"
                value={maxRisk}
                onChange={(e) => setMaxRisk(parseFloat(e.target.value))}
                className="w-24 bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm"
              />
              <span className="text-gray-500 text-sm">USD</span>
            </div>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                className="w-4 h-4 rounded bg-gray-900 border-gray-700"
              />
              <span className="text-gray-300 text-sm">Dry Run (Simulate)</span>
            </label>

            <button
              onClick={executeRecommendedTrades}
              disabled={loading}
              className={`flex-1 md:flex-none px-6 py-3 rounded-lg font-bold transition-colors flex items-center justify-center gap-2 ${
                dryRun
                  ? 'bg-blue-600 hover:bg-blue-700 text-white'
                  : 'bg-green-600 hover:bg-green-700 text-white'
              } disabled:bg-gray-700`}
            >
              <Zap size={18} />
              {dryRun ? 'Test Execution' : 'Execute All Trades'}
            </button>
          </div>

          {!dryRun && (
            <p className="text-yellow-400 text-sm mt-3">
              Warning: Live trades will be placed on Kalshi (Demo Mode active)
            </p>
          )}
        </div>
      )}

      {/* No opportunities message */}
      {data && data.opportunities?.length === 0 && (
        <div className="bg-gray-800/50 rounded-xl p-8 text-center">
          <Target size={48} className="mx-auto mb-4 text-gray-500" />
          <p className="text-gray-400 text-lg">No mispriced markets found</p>
          <p className="text-gray-500 text-sm mt-2">
            The ML model didn't find any opportunities with 2%+ EV edge right now.
            Markets may be efficiently priced or outside trading parameters.
          </p>
        </div>
      )}

      {/* Execution Result - only show for actual trade executions */}
      {executionResult && executionResult.trades_executed !== undefined && (
        <div className={`border rounded-lg p-6 ${
          executionResult.success
            ? 'bg-green-500/10 border-green-500/30'
            : 'bg-red-500/10 border-red-500/30'
        }`}>
          <h3 className={`font-bold text-lg mb-4 flex items-center gap-2 ${
            executionResult.success ? 'text-green-400' : 'text-red-400'
          }`}>
            {executionResult.success ? <CheckCircle size={20} /> : <AlertCircle size={20} />}
            {executionResult.dry_run ? 'Dry Run Result' : 'Execution Result'}
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div>
              <p className="text-gray-400 text-sm">Trades</p>
              <p className="text-white font-bold">{executionResult.trades_executed}</p>
            </div>
            <div>
              <p className="text-gray-400 text-sm">Total Cost</p>
              <p className="text-white font-bold">${executionResult.total_cost?.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-gray-400 text-sm">Status</p>
              <p className="text-green-400 font-bold">
                {executionResult.dry_run ? 'Simulated' : 'Executed'}
              </p>
            </div>
            <div>
              <p className="text-gray-400 text-sm">Time</p>
              <p className="text-white font-bold">
                {new Date(executionResult.timestamp).toLocaleTimeString()}
              </p>
            </div>
          </div>

          {executionResult.results?.length > 0 && (
            <div className="space-y-2">
              {executionResult.results.map((result, idx) => (
                <div key={idx} className="bg-gray-900/50 rounded p-3 flex justify-between items-center">
                  <div>
                    <p className="text-white text-sm font-medium">{result.ticker}</p>
                    <p className="text-gray-400 text-xs">
                      {result.side} x{result.quantity} @ {result.price_cents}¢
                    </p>
                  </div>
                  <div className="text-right">
                    <p className={`font-bold ${
                      result.status === 'executed' || result.status === 'simulated'
                        ? 'text-green-400'
                        : 'text-red-400'
                    }`}>
                      {result.status.toUpperCase()}
                    </p>
                    <p className="text-gray-400 text-xs">${result.cost?.toFixed(2)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Algorithm Explanation */}
      <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-4">
        <h4 className="text-gray-400 font-medium mb-2">How it works</h4>
        <p className="text-gray-500 text-sm leading-relaxed">
          The algorithm uses <span className="text-blue-400">GARCH(1,1) volatility modeling</span> combined with market signals
          (RSI, funding rates, open interest, order book imbalance) adjusted in <span className="text-blue-400">log-odds space</span> to
          estimate conditional probabilities. When our model probability differs from Kalshi's market price, we calculate
          <span className="text-green-400"> risk-adjusted EV</span> (raw EV ÷ probability uncertainty) and
          <span className="text-green-400"> time-weighted EV</span> (EV × √hours). Trades passing 0.5σ risk-adjusted EV,
          1% raw EV, and 40% ML confidence are flagged. The ML score scales position size (0.5x-1.5x) rather than acting as a hard gate.
          Positions with 15%+ raw edge bypass probability bounds entirely.
        </p>
      </div>
    </div>
  );
};

export default HedgeDashboard;
