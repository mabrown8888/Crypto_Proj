import React, { useState, useEffect, useCallback } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
  ComposedChart
} from 'recharts';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Target,
  Zap,
  BarChart3,
  PieChart,
  RefreshCw,
  Info,
  AlertTriangle,
  CheckCircle
} from 'lucide-react';

const AlgorithmAnalytics = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeframe, setTimeframe] = useState('7d');

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`http://localhost:5001/api/algorithm/analytics?timeframe=${timeframe}`);
      if (!response.ok) throw new Error('Failed to fetch analytics');
      const result = await response.json();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [timeframe]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const formatPercent = (val) => `${(val * 100).toFixed(2)}%`;
  const formatDollar = (val) => `$${val?.toFixed(2) || '0.00'}`;

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
        <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <p className="text-red-400">{error}</p>
        <button onClick={fetchAnalytics} className="mt-4 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg">
          Retry
        </button>
      </div>
    );
  }

  const {
    summary = {},
    equity_curve = [],
    daily_returns = [],
    win_rate_over_time = [],
    ev_distribution = [],
    signal_performance = {},
    model_calibration = [],
    recent_trades = []
  } = data || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-crypto-purple" />
            Algorithm Analytics
          </h2>
          <p className="text-gray-400 text-sm mt-1">
            Performance metrics, Sharpe ratio, and model calibration for the Kalshi ML trading algorithm
          </p>
        </div>

        <div className="flex items-center gap-4">
          {/* Timeframe selector */}
          <div className="flex gap-2">
            {['24h', '7d', '30d', 'all'].map(tf => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  timeframe === tf
                    ? 'bg-crypto-purple text-white'
                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                }`}
              >
                {tf.toUpperCase()}
              </button>
            ))}
          </div>

          <button
            onClick={fetchAnalytics}
            className="flex items-center gap-2 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Key Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {/* Sharpe Ratio */}
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-xs">Sharpe Ratio</span>
            <Zap className={`h-4 w-4 ${summary.sharpe_ratio >= 1.5 ? 'text-crypto-green' : summary.sharpe_ratio >= 1 ? 'text-yellow-500' : 'text-red-500'}`} />
          </div>
          <div className="text-2xl font-bold text-white">{summary.sharpe_ratio?.toFixed(2) || '-'}</div>
          <div className="text-xs text-gray-500 mt-1">
            {summary.sharpe_ratio >= 2 ? 'Excellent' : summary.sharpe_ratio >= 1.5 ? 'Very Good' : summary.sharpe_ratio >= 1 ? 'Good' : 'Needs Work'}
          </div>
        </div>

        {/* Win Rate */}
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-xs">Win Rate</span>
            <Target className={`h-4 w-4 ${summary.win_rate >= 0.55 ? 'text-crypto-green' : 'text-yellow-500'}`} />
          </div>
          <div className="text-2xl font-bold text-white">{formatPercent(summary.win_rate || 0)}</div>
          <div className="text-xs text-gray-500 mt-1">
            {summary.total_trades || 0} total trades
          </div>
        </div>

        {/* Total P&L */}
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-xs">Total P&L</span>
            {summary.total_pnl >= 0 ? (
              <TrendingUp className="h-4 w-4 text-crypto-green" />
            ) : (
              <TrendingDown className="h-4 w-4 text-crypto-red" />
            )}
          </div>
          <div className={`text-2xl font-bold ${summary.total_pnl >= 0 ? 'text-crypto-green' : 'text-crypto-red'}`}>
            {formatDollar(summary.total_pnl)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            ROI: {formatPercent(summary.roi || 0)}
          </div>
        </div>

        {/* Max Drawdown */}
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-xs">Max Drawdown</span>
            <AlertTriangle className={`h-4 w-4 ${Math.abs(summary.max_drawdown || 0) < 0.15 ? 'text-crypto-green' : 'text-red-500'}`} />
          </div>
          <div className="text-2xl font-bold text-red-400">
            {formatPercent(summary.max_drawdown || 0)}
          </div>
          <div className="text-xs text-gray-500 mt-1">Peak to trough</div>
        </div>

        {/* Profit Factor */}
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-xs">Profit Factor</span>
            <Activity className={`h-4 w-4 ${summary.profit_factor >= 1.5 ? 'text-crypto-green' : 'text-yellow-500'}`} />
          </div>
          <div className="text-2xl font-bold text-white">{summary.profit_factor?.toFixed(2) || '-'}</div>
          <div className="text-xs text-gray-500 mt-1">Gross profit / loss</div>
        </div>

        {/* Avg EV per Trade */}
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-xs">Avg EV/Trade</span>
            <PieChart className="h-4 w-4 text-crypto-blue" />
          </div>
          <div className="text-2xl font-bold text-crypto-blue">
            {formatPercent(summary.avg_ev_per_trade || 0)}
          </div>
          <div className="text-xs text-gray-500 mt-1">Expected value</div>
        </div>
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Equity Curve */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-crypto-green" />
            Equity Curve
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={equity_curve}>
                <defs>
                  <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10B981" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#10B981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="date" stroke="#9CA3AF" fontSize={10} />
                <YAxis stroke="#9CA3AF" fontSize={10} tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                  formatter={(value) => [`$${value.toFixed(2)}`, 'Equity']}
                />
                <Area
                  type="monotone"
                  dataKey="equity"
                  stroke="#10B981"
                  fill="url(#equityGradient)"
                  strokeWidth={2}
                />
                <ReferenceLine y={summary.initial_equity || 0} stroke="#6B7280" strokeDasharray="3 3" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Daily Returns Distribution */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-crypto-blue" />
            Daily Returns Distribution
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={daily_returns}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="date" stroke="#9CA3AF" fontSize={10} />
                <YAxis stroke="#9CA3AF" fontSize={10} tickFormatter={(v) => `${(v * 100).toFixed(1)}%`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                  formatter={(value) => [`${(value * 100).toFixed(2)}%`, 'Return']}
                />
                <Bar
                  dataKey="return"
                  fill={(entry) => entry.return >= 0 ? '#10B981' : '#EF4444'}
                >
                  {daily_returns.map((entry, index) => (
                    <rect key={index} fill={entry.return >= 0 ? '#10B981' : '#EF4444'} />
                  ))}
                </Bar>
                <ReferenceLine y={0} stroke="#6B7280" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Win Rate Over Time */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Target className="h-5 w-5 text-crypto-purple" />
            Rolling Win Rate (20 trades)
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={win_rate_over_time}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="trade_num" stroke="#9CA3AF" fontSize={10} />
                <YAxis stroke="#9CA3AF" fontSize={10} domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                  formatter={(value) => [`${(value * 100).toFixed(1)}%`, 'Win Rate']}
                />
                <ReferenceLine y={0.5} stroke="#EF4444" strokeDasharray="3 3" label="Break Even" />
                <ReferenceLine y={0.55} stroke="#10B981" strokeDasharray="3 3" label="Target" />
                <Line
                  type="monotone"
                  dataKey="win_rate"
                  stroke="#A855F7"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Model Calibration */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Info className="h-5 w-5 text-yellow-500" />
            Model Calibration (Predicted vs Actual)
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={model_calibration}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="predicted_bucket" stroke="#9CA3AF" fontSize={10} />
                <YAxis stroke="#9CA3AF" fontSize={10} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                  formatter={(value, name) => [`${(value * 100).toFixed(1)}%`, name === 'predicted' ? 'Predicted' : 'Actual']}
                />
                <Legend />
                <Bar dataKey="predicted" fill="#3B82F6" name="Predicted" opacity={0.7} />
                <Line type="monotone" dataKey="actual" stroke="#10B981" strokeWidth={2} name="Actual" dot />
                <ReferenceLine
                  segment={[{ x: '0-10%', y: 0.05 }, { x: '90-100%', y: 0.95 }]}
                  stroke="#6B7280"
                  strokeDasharray="3 3"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Perfect calibration: bars and line should overlap. Deviation indicates model over/under-confidence.
          </p>
        </div>
      </div>

      {/* Signal Performance Table */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">Signal Performance Breakdown</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-900">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Signal</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase">Trades</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase">Win Rate</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase">Avg EV</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase">P&L</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase">Contribution</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {Object.entries(signal_performance).map(([signal, perf]) => (
                <tr key={signal}>
                  <td className="px-4 py-3 text-white font-medium">{signal}</td>
                  <td className="px-4 py-3 text-center text-gray-300">{perf.trades}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={perf.win_rate >= 0.55 ? 'text-crypto-green' : 'text-yellow-500'}>
                      {formatPercent(perf.win_rate)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center text-crypto-blue">{formatPercent(perf.avg_ev)}</td>
                  <td className={`px-4 py-3 text-center ${perf.pnl >= 0 ? 'text-crypto-green' : 'text-crypto-red'}`}>
                    {formatDollar(perf.pnl)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <div className="w-16 h-2 bg-gray-700 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${perf.contribution >= 0 ? 'bg-crypto-green' : 'bg-crypto-red'}`}
                          style={{ width: `${Math.min(100, Math.abs(perf.contribution) * 100)}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-400">{formatPercent(perf.contribution)}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent Trades */}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">Recent Trades</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-900">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Time</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Market</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase">Side</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase">Model Prob</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase">Market Prob</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase">EV</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase">Result</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase">P&L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {recent_trades.map((trade, idx) => (
                <tr key={idx} className={trade.won ? 'bg-green-900/10' : ''}>
                  <td className="px-4 py-3 text-gray-400 text-sm">{trade.time}</td>
                  <td className="px-4 py-3 text-white text-sm">{trade.ticker}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      trade.side === 'YES' ? 'bg-green-900/50 text-green-400' : 'bg-blue-900/50 text-blue-400'
                    }`}>
                      {trade.side}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center text-crypto-blue">{formatPercent(trade.model_prob)}</td>
                  <td className="px-4 py-3 text-center text-gray-400">{formatPercent(trade.market_prob)}</td>
                  <td className="px-4 py-3 text-center text-crypto-green">{formatPercent(trade.ev)}</td>
                  <td className="px-4 py-3 text-center">
                    {trade.settled ? (
                      trade.won ? (
                        <CheckCircle className="h-5 w-5 text-crypto-green inline" />
                      ) : (
                        <AlertTriangle className="h-5 w-5 text-crypto-red inline" />
                      )
                    ) : (
                      <span className="text-yellow-500 text-xs">Pending</span>
                    )}
                  </td>
                  <td className={`px-4 py-3 text-right font-medium ${
                    trade.pnl >= 0 ? 'text-crypto-green' : 'text-crypto-red'
                  }`}>
                    {trade.settled ? formatDollar(trade.pnl) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Algorithm Details */}
      <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-4">
        <h4 className="text-gray-400 font-medium mb-2">Algorithm Details</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Model:</span>
            <span className="text-white ml-2">GARCH(1,1) + Log-Odds ML</span>
          </div>
          <div>
            <span className="text-gray-500">Min Risk-Adj EV:</span>
            <span className="text-crypto-blue ml-2">0.5σ</span>
          </div>
          <div>
            <span className="text-gray-500">Min Raw EV:</span>
            <span className="text-crypto-green ml-2">1%</span>
          </div>
          <div>
            <span className="text-gray-500">High Edge Override:</span>
            <span className="text-crypto-purple ml-2">15%+ EV</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AlgorithmAnalytics;
