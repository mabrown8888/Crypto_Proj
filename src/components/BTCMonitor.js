import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Clock,
  DollarSign,
  Target,
  AlertCircle,
  CheckCircle,
  RefreshCw,
  Filter
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea
} from 'recharts';

const BTCMonitor = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [expiryFilter, setExpiryFilter] = useState('all'); // 'all', '1h', '4h', '24h', 'week', 'month', 'year'

  const fetchData = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:5001/api/btc-monitor');
      if (!response.ok) throw new Error('Failed to fetch data');
      const result = await response.json();
      setData(result);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();

    // Auto-refresh every 10 seconds
    let interval;
    if (autoRefresh) {
      interval = setInterval(fetchData, 10000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [fetchData, autoRefresh]);

  const formatTime = (seconds) => {
    if (seconds <= 0) return 'Expired';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (mins >= 60) {
      const hrs = Math.floor(mins / 60);
      const remainMins = mins % 60;
      return `${hrs}h ${remainMins}m`;
    }
    return `${mins}m ${secs}s`;
  };

  const formatPrice = (price) => {
    if (!price) return '-';
    return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  // Custom tooltip for chart
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const tooltipData = payload[0].payload;
      return (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 shadow-lg">
          <p className="text-gray-400 text-xs">
            {new Date(tooltipData.timestamp).toLocaleTimeString()}
          </p>
          <p className="text-white font-bold">
            {formatPrice(tooltipData.price)}
          </p>
          <p className="text-gray-400 text-xs">
            H: {formatPrice(tooltipData.high)} / L: {formatPrice(tooltipData.low)}
          </p>
        </div>
      );
    }
    return null;
  };

  // Extract data (always runs, even when loading)
  const { btc_price, price_history, positions, summary } = data || {};

  // Get unique expiry times for filter dropdown (must be before early returns)
  const expiryOptions = useMemo(() => {
    if (!positions) return [];
    const expiries = [...new Set(positions.map(p => p.expiry))];
    return expiries.sort((a, b) => {
      const posA = positions.find(p => p.expiry === a);
      const posB = positions.find(p => p.expiry === b);
      return (posA?.time_to_expiry_seconds || 0) - (posB?.time_to_expiry_seconds || 0);
    });
  }, [positions]);

  // Filter positions by expiry (must be before early returns)
  const filteredPositions = useMemo(() => {
    if (!positions) return [];
    if (expiryFilter === 'all') return positions;

    const filterSeconds = {
      '1h': 3600,
      '4h': 14400,
      '24h': 86400,
      'week': 604800,
      'month': 2592000,
      'year': 31536000
    };

    if (filterSeconds[expiryFilter]) {
      return positions.filter(p => p.time_to_expiry_seconds <= filterSeconds[expiryFilter]);
    }

    // Filter by specific expiry time
    return positions.filter(p => p.expiry === expiryFilter);
  }, [positions, expiryFilter]);

  // Calculate filtered summary (must be before early returns)
  const filteredSummary = useMemo(() => {
    if (!filteredPositions.length) return summary;
    const totalCost = filteredPositions.reduce((sum, p) => sum + (p.cost || 0), 0);
    const totalPayout = filteredPositions.reduce((sum, p) => sum + (p.potential_payout || 0), 0);
    const winning = filteredPositions.filter(p => p.in_range);
    const winningPayout = winning.reduce((sum, p) => sum + (p.potential_payout || 0), 0);
    return {
      total_positions: filteredPositions.length,
      total_cost: totalCost,
      total_potential_payout: totalPayout,
      winning_positions: winning.length,
      current_pnl: winning.length > 0 ? winningPayout - totalCost : -totalCost
    };
  }, [filteredPositions, summary]);

  // Calculate chart domain - optimized to focus on relevant price action
  const allPrices = price_history?.map(p => p.price) || [];
  const priceMin = allPrices.length > 0 ? Math.min(...allPrices) : btc_price || 90000;
  const priceMax = allPrices.length > 0 ? Math.max(...allPrices) : btc_price || 90000;
  const priceRange = priceMax - priceMin;

  // Only include position thresholds that are within a reasonable visual range (20% of current price)
  const visualThreshold = (btc_price || 90000) * 0.20;
  const relevantPositionValues = filteredPositions?.flatMap(p => {
    const values = [];
    if (p.lower && Math.abs(p.lower - btc_price) < visualThreshold) values.push(p.lower);
    if (p.upper && Math.abs(p.upper - btc_price) < visualThreshold) values.push(p.upper);
    if (p.threshold && Math.abs(p.threshold - btc_price) < visualThreshold) values.push(p.threshold);
    return values;
  }).filter(Boolean) || [];

  // Chart domain: focus on price history with padding, include nearby thresholds
  const chartValues = [...allPrices, ...relevantPositionValues, btc_price].filter(Boolean);
  const minPrice = chartValues.length > 0 ? Math.min(...chartValues) - Math.max(500, priceRange * 0.1) : 85000;
  const maxPrice = chartValues.length > 0 ? Math.max(...chartValues) + Math.max(500, priceRange * 0.1) : 95000;

  // Positions that are visible on chart (within chart bounds)
  const visiblePositions = filteredPositions?.filter(pos => {
    if (pos.market_type === 'range') {
      return pos.lower >= minPrice && pos.upper <= maxPrice;
    }
    if (pos.threshold) {
      return pos.threshold >= minPrice && pos.threshold <= maxPrice;
    }
    return false;
  }) || [];

  // Positions that are off-chart (for showing in a separate indicator)
  const offChartPositions = filteredPositions?.filter(pos => {
    if (pos.market_type === 'range') {
      return pos.lower < minPrice || pos.upper > maxPrice;
    }
    if (pos.threshold) {
      return pos.threshold < minPrice || pos.threshold > maxPrice;
    }
    return false;
  }) || [];

  // Early returns AFTER all hooks
  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-crypto-blue"></div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="bg-red-900/20 border border-red-500 rounded-lg p-6 text-center">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <p className="text-red-400">{error}</p>
        <button
          onClick={fetchData}
          className="mt-4 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-white flex items-center gap-2">
              <Activity className="h-6 w-6 text-crypto-blue" />
              BTC Position Monitor
            </h2>
            <p className="text-gray-400 text-sm mt-1 max-w-2xl">
              The algorithm uses GARCH volatility modeling to estimate the probability of BTC reaching specific price levels.
              When our model probability differs from Kalshi's market price by 4%+ (positive EV), we flag it as a trade opportunity.
              Green "IN RANGE" badges indicate positions currently winning based on live BTC price.
            </p>
          </div>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-gray-400">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded border-gray-600 bg-gray-700 text-crypto-blue focus:ring-crypto-blue"
              />
              Auto-refresh
            </label>

            <button
              onClick={fetchData}
              className="flex items-center gap-2 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>

            {lastUpdate && (
              <span className="text-gray-500 text-xs">
                Updated: {lastUpdate.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>

        {/* Expiry Filter */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-gray-400" />
            <span className="text-gray-400 text-sm">Filter:</span>
          </div>

          {/* Quick time filters */}
          <div className="flex gap-1">
            {[
              { value: 'all', label: 'All' },
              { value: '4h', label: '< 4h' },
              { value: '24h', label: 'Today' },
              { value: 'week', label: 'Week' },
            ].map(opt => (
              <button
                key={opt.value}
                onClick={() => setExpiryFilter(opt.value)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  expiryFilter === opt.value
                    ? 'bg-crypto-blue text-white'
                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Specific expiry selector */}
          {expiryOptions.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-gray-600 text-xs">|</span>
              <span className="text-gray-500 text-xs">Specific:</span>
              <div className="flex flex-wrap gap-1">
                {expiryOptions.slice(0, 5).map(exp => (
                  <button
                    key={exp}
                    onClick={() => setExpiryFilter(exp)}
                    className={`px-2 py-1 rounded text-xs transition-colors ${
                      expiryFilter === exp
                        ? 'bg-crypto-purple text-white'
                        : 'bg-gray-700/50 text-gray-400 hover:bg-gray-600'
                    }`}
                  >
                    {exp}
                  </button>
                ))}
                {expiryOptions.length > 5 && (
                  <select
                    value={expiryOptions.includes(expiryFilter) ? expiryFilter : ''}
                    onChange={(e) => e.target.value && setExpiryFilter(e.target.value)}
                    className="px-2 py-1 rounded bg-gray-700/50 text-gray-400 text-xs border-0 focus:outline-none focus:ring-1 focus:ring-crypto-purple"
                  >
                    <option value="">+{expiryOptions.length - 5} more</option>
                    {expiryOptions.slice(5).map(exp => (
                      <option key={exp} value={exp}>{exp}</option>
                    ))}
                  </select>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* BTC Price & Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Current BTC Price */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center justify-between">
            <span className="text-gray-400 text-sm">BTC Price</span>
            <Activity className="h-5 w-5 text-crypto-yellow" />
          </div>
          <div className="mt-2">
            <span className="text-3xl font-bold text-white">
              {formatPrice(btc_price)}
            </span>
          </div>
        </div>

        {/* Total Invested */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center justify-between">
            <span className="text-gray-400 text-sm">Total Invested{expiryFilter !== 'all' ? ' (Filtered)' : ''}</span>
            <DollarSign className="h-5 w-5 text-crypto-blue" />
          </div>
          <div className="mt-2">
            <span className="text-3xl font-bold text-white">
              ${filteredSummary?.total_cost?.toFixed(2) || '0.00'}
            </span>
          </div>
        </div>

        {/* Current P&L */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center justify-between">
            <span className="text-gray-400 text-sm">Projected P&L{expiryFilter !== 'all' ? ' (Filtered)' : ''}</span>
            {filteredSummary?.current_pnl >= 0 ? (
              <TrendingUp className="h-5 w-5 text-crypto-green" />
            ) : (
              <TrendingDown className="h-5 w-5 text-crypto-red" />
            )}
          </div>
          <div className="mt-2">
            <span className={`text-3xl font-bold ${
              filteredSummary?.current_pnl >= 0 ? 'text-crypto-green' : 'text-crypto-red'
            }`}>
              {filteredSummary?.current_pnl >= 0 ? '+' : ''}${filteredSummary?.current_pnl?.toFixed(2) || '0.00'}
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            If current winners expire in-range
          </div>
        </div>

        {/* Positions Status */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center justify-between">
            <span className="text-gray-400 text-sm">Positions{expiryFilter !== 'all' ? ' (Filtered)' : ''}</span>
            <Target className="h-5 w-5 text-crypto-purple" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-crypto-green">
              {filteredSummary?.winning_positions || 0}
            </span>
            <span className="text-gray-500">/</span>
            <span className="text-xl text-gray-400">
              {filteredSummary?.total_positions || 0}
            </span>
            <span className="text-sm text-gray-500">in-range</span>
          </div>
        </div>
      </div>

      {/* BTC Price Chart with Position Ranges */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">
            BTC Price (Last 4 Hours) with Position Thresholds
          </h3>
          {offChartPositions.length > 0 && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-gray-500">
                {offChartPositions.length} position{offChartPositions.length > 1 ? 's' : ''} off-chart:
              </span>
              {offChartPositions.filter(p => p.threshold > maxPrice).length > 0 && (
                <span className="px-2 py-1 bg-purple-900/30 text-purple-400 rounded">
                  ↑ {offChartPositions.filter(p => p.threshold > maxPrice).map(p => `$${(p.threshold/1000).toFixed(0)}k`).join(', ')}
                </span>
              )}
              {offChartPositions.filter(p => p.threshold < minPrice).length > 0 && (
                <span className="px-2 py-1 bg-blue-900/30 text-blue-400 rounded">
                  ↓ {offChartPositions.filter(p => p.threshold < minPrice).map(p => `$${(p.threshold/1000).toFixed(0)}k`).join(', ')}
                </span>
              )}
            </div>
          )}
        </div>

        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={price_history} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.5} />
              <XAxis
                dataKey="timestamp"
                tickFormatter={(ts) => new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                stroke="#6B7280"
                fontSize={11}
                tickLine={false}
              />
              <YAxis
                domain={[minPrice, maxPrice]}
                tickFormatter={(val) => `$${(val/1000).toFixed(1)}k`}
                stroke="#6B7280"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                width={55}
              />
              <Tooltip content={<CustomTooltip />} />

              {/* Position range areas (for range markets) - only visible ones */}
              {visiblePositions?.filter(pos => pos.market_type === 'range' && pos.lower && pos.upper).map((pos) => (
                <ReferenceArea
                  key={pos.ticker}
                  y1={pos.lower}
                  y2={pos.upper}
                  fill={pos.in_range ? '#10B981' : '#EF4444'}
                  fillOpacity={0.15}
                />
              ))}

              {/* Position threshold lines (for threshold markets) - only visible ones */}
              {visiblePositions?.filter(pos => pos.market_type === 'threshold' && pos.threshold).map((pos, idx) => (
                <ReferenceLine
                  key={pos.ticker}
                  y={pos.threshold}
                  stroke={pos.in_range ? '#10B981' : '#EF4444'}
                  strokeDasharray="4 4"
                  strokeWidth={1.5}
                  strokeOpacity={0.8}
                />
              ))}

              {/* Current BTC price line - prominent */}
              <ReferenceLine
                y={btc_price}
                stroke="#F59E0B"
                strokeWidth={2}
                label={{
                  value: `$${btc_price?.toLocaleString()}`,
                  fill: '#F59E0B',
                  fontSize: 11,
                  fontWeight: 'bold',
                  position: 'right'
                }}
              />

              {/* Price line */}
              <Line
                type="monotone"
                dataKey="price"
                stroke="#3B82F6"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 5, fill: '#3B82F6', stroke: '#1E40AF', strokeWidth: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Compact Legend */}
        <div className="flex flex-wrap items-center gap-4 mt-3 text-xs text-gray-500">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-green-500/20 border border-green-500"></div>
            <span>Winning</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-red-500/20 border border-red-500"></div>
            <span>Losing</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-4 h-0.5 bg-yellow-500"></div>
            <span>Current Price</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-4 h-0.5 bg-blue-500"></div>
            <span>Price History</span>
          </div>
        </div>
      </div>

      {/* Positions Table */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div className="p-4 border-b border-gray-700 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">
            Active Positions
            {expiryFilter !== 'all' && (
              <span className="ml-2 text-sm font-normal text-gray-400">
                ({filteredPositions?.length} of {positions?.length} shown)
              </span>
            )}
          </h3>
        </div>

        {filteredPositions?.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            {positions?.length > 0
              ? 'No positions match the current filter'
              : 'No active BTC positions found'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-900">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Range / Threshold
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Side / Qty
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Cost
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Payout
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Expiry
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    What Needs to Happen
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {filteredPositions?.map((pos) => (
                  <tr key={pos.ticker} className={`${pos.in_range ? 'bg-green-900/10' : ''}`}>
                    <td className="px-4 py-4">
                      <div className="flex flex-col">
                        <span className="text-white font-medium">
                          {pos.market_type === 'yearly' ? (
                            <>
                              <span className="text-purple-400">🎯 Yearly Max:</span> ${pos.threshold?.toLocaleString()}
                            </>
                          ) : pos.market_type === 'threshold' ? (
                            <>
                              {pos.threshold_direction === 'above' ? '↑ Above' : '↓ Below'} ${pos.threshold?.toLocaleString()}
                            </>
                          ) : (
                            <>${pos.lower?.toLocaleString()} - ${pos.upper?.toLocaleString()}</>
                          )}
                        </span>
                        <span className="text-gray-500 text-xs">{pos.ticker}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className={`inline-flex items-center gap-1 ${
                        pos.side === 'YES' ? 'text-crypto-green' : 'text-crypto-blue'
                      }`}>
                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                          pos.side === 'YES' ? 'bg-green-900/50' : 'bg-blue-900/50'
                        }`}>
                          {pos.side}
                        </span>
                        <span className="text-white">{pos.quantity}</span>
                      </span>
                    </td>
                    <td className="px-4 py-4 text-right text-white">
                      ${pos.cost?.toFixed(2)}
                    </td>
                    <td className="px-4 py-4 text-right">
                      <span className="text-crypto-green font-medium">
                        ${pos.potential_payout?.toFixed(2)}
                      </span>
                      <span className="text-gray-500 text-xs ml-1">
                        ({((pos.potential_payout / pos.cost - 1) * 100).toFixed(0)}%)
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <div className="flex flex-col items-center">
                        <span className="text-white">{pos.expiry}</span>
                        <span className={`text-xs ${
                          pos.time_to_expiry_seconds < 300 ? 'text-red-400 animate-pulse' : 'text-gray-500'
                        }`}>
                          <Clock className="inline h-3 w-3 mr-1" />
                          {formatTime(pos.time_to_expiry_seconds)}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-center">
                      {pos.in_range ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-green-900/50 text-green-400 text-xs font-medium">
                          <CheckCircle className="h-3 w-3" />
                          IN RANGE
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-red-900/50 text-red-400 text-xs font-medium">
                          <AlertCircle className="h-3 w-3" />
                          OUT
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex flex-col">
                        <span className={`text-sm ${pos.in_range ? 'text-green-400' : 'text-yellow-400'}`}>
                          {pos.what_needs_to_happen}
                        </span>
                        {pos.distance !== null && pos.distance > 0 && (
                          <div className="mt-1">
                            {/* Visual distance indicator */}
                            <div className="flex items-center gap-2">
                              <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                                <div
                                  className={`h-full ${pos.distance < 500 ? 'bg-yellow-500' : 'bg-red-500'}`}
                                  style={{ width: `${Math.min(100, (pos.distance / 1000) * 100)}%` }}
                                ></div>
                              </div>
                              <span className="text-xs text-gray-500">
                                ${pos.distance?.toLocaleString()} away
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Outcome Scenarios */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">
          Outcome Scenarios
          {expiryFilter !== 'all' && <span className="ml-2 text-sm font-normal text-gray-400">(Filtered)</span>}
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Best Case */}
          <div className="bg-green-900/20 rounded-lg p-4 border border-green-800">
            <div className="text-green-400 text-sm font-medium mb-2">Best Case (All Win)</div>
            <div className="text-2xl font-bold text-white">
              +${((filteredSummary?.total_potential_payout || 0) - (filteredSummary?.total_cost || 0)).toFixed(2)}
            </div>
            <div className="text-gray-400 text-xs mt-1">
              Payout: ${filteredSummary?.total_potential_payout?.toFixed(2)}
            </div>
          </div>

          {/* Current Projection */}
          <div className={`${filteredSummary?.current_pnl >= 0 ? 'bg-blue-900/20 border-blue-800' : 'bg-yellow-900/20 border-yellow-800'} rounded-lg p-4 border`}>
            <div className={`${filteredSummary?.current_pnl >= 0 ? 'text-blue-400' : 'text-yellow-400'} text-sm font-medium mb-2`}>
              Current Projection
            </div>
            <div className="text-2xl font-bold text-white">
              {filteredSummary?.current_pnl >= 0 ? '+' : ''}${filteredSummary?.current_pnl?.toFixed(2)}
            </div>
            <div className="text-gray-400 text-xs mt-1">
              {filteredSummary?.winning_positions} of {filteredSummary?.total_positions} positions winning
            </div>
          </div>

          {/* Worst Case */}
          <div className="bg-red-900/20 rounded-lg p-4 border border-red-800">
            <div className="text-red-400 text-sm font-medium mb-2">Worst Case (All Lose)</div>
            <div className="text-2xl font-bold text-white">
              -${filteredSummary?.total_cost?.toFixed(2)}
            </div>
            <div className="text-gray-400 text-xs mt-1">
              Total amount at risk
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BTCMonitor;
