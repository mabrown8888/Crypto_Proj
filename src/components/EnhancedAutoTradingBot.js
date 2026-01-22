import React, { useState, useEffect } from 'react';
import {
  Bot,
  Play,
  Square,
  TrendingUp,
  TrendingDown,
  Shield,
  Zap,
  BarChart3,
  CheckCircle,
  XCircle,
  DollarSign,
  Clock,
  Activity,
  Eye,
  EyeOff,
  RefreshCw
} from 'lucide-react';
import { authUtils } from '../utils/auth';

const EnhancedAutoTradingBot = () => {
  const [botStatus, setBotStatus] = useState({
    status: 'stopped',
    uptime: '0h 0m',
    cycles_completed: 0,
    trades_today: 0,
    total_trades: 0,
    successful_trades: 0,
    failed_trades: 0,
    win_rate: 0,
    total_pnl: 0,
    today_pnl: 0,
    currencies: {},
    supported_currencies: []
  });

  const [tradesHistory, setTradesHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchBotStatus();
    fetchTradeHistory();

    // Auto-refresh every 10 seconds
    const interval = setInterval(() => {
      fetchBotStatus();
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  const fetchBotStatus = async () => {
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/enhanced-bot/status');
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setBotStatus(data);
        }
      }
    } catch (error) {
      console.error('Error fetching bot status:', error);
    }
  };

  const fetchTradeHistory = async () => {
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/enhanced-bot/trade-history?limit=20');
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setTradesHistory(data.trades || []);
        }
      }
    } catch (error) {
      console.error('Error fetching trade history:', error);
    }
  };

  const handleStartBot = async () => {
    setLoading(true);
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/enhanced-bot/start', {
        method: 'POST'
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          await fetchBotStatus();
        }
      }
    } catch (error) {
      console.error('Error starting bot:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStopBot = async () => {
    setLoading(true);
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/enhanced-bot/stop', {
        method: 'POST'
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          await fetchBotStatus();
        }
      }
    } catch (error) {
      console.error('Error stopping bot:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleCurrency = async (symbol, enabled) => {
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/enhanced-bot/toggle-currency', {
        method: 'POST',
        body: JSON.stringify({ symbol, enabled: !enabled })
      });

      if (response.ok) {
        await fetchBotStatus();
      }
    } catch (error) {
      console.error('Error toggling currency:', error);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([fetchBotStatus(), fetchTradeHistory()]);
    setRefreshing(false);
  };

  const handleSyncPositions = async () => {
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/enhanced-bot/sync-positions', {
        method: 'POST'
      });

      if (response.ok) {
        await fetchBotStatus();
      }
    } catch (error) {
      console.error('Error syncing positions:', error);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount);
  };

  const getCurrencyDisplayName = (symbol) => {
    const mapping = {
      'BTC-USD': 'Bitcoin',
      'ETH-USD': 'Ethereum',
      'SOL-USD': 'Solana',
      'ADA-USD': 'Cardano',
      'DOGE-USD': 'Dogecoin',
      'AVAX-USD': 'Avalanche',
      'MATIC-USD': 'Polygon',
      'LINK-USD': 'Chainlink'
    };
    return mapping[symbol] || symbol;
  };

  const isRunning = botStatus.status === 'running';

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Bot className="h-8 w-8 text-crypto-blue" />
          <div>
            <h1 className="text-3xl font-bold">Enhanced AI Trading Bot</h1>
            <p className="text-gray-400 text-sm">Multi-Currency Automated Trading</p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleSyncPositions}
            className="flex items-center space-x-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg transition-colors"
          >
            <Activity className="h-4 w-4" />
            <span>Sync Positions</span>
          </button>

          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center space-x-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>

          {!isRunning ? (
            <button
              onClick={handleStartBot}
              disabled={loading}
              className="flex items-center space-x-2 px-6 py-3 bg-crypto-green hover:bg-green-600 rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              <Play className="h-5 w-5" />
              <span>Start Bot</span>
            </button>
          ) : (
            <button
              onClick={handleStopBot}
              disabled={loading}
              className="flex items-center space-x-2 px-6 py-3 bg-crypto-red hover:bg-red-600 rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              <Square className="h-5 w-5" />
              <span>Stop Bot</span>
            </button>
          )}
        </div>
      </div>

      {/* Status Banner */}
      <div className={`rounded-lg p-4 border-2 ${
        isRunning
          ? 'bg-crypto-green/20 border-crypto-green'
          : 'bg-gray-700 border-gray-600'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`w-3 h-3 rounded-full ${
              isRunning ? 'bg-crypto-green animate-pulse' : 'bg-gray-500'
            }`}></div>
            <span className="font-bold text-lg">
              {isRunning ? 'Bot is Running' : 'Bot is Stopped'}
            </span>
          </div>

          {isRunning && (
            <div className="flex items-center space-x-6 text-sm">
              <div className="flex items-center space-x-2">
                <Clock className="h-4 w-4 text-gray-400" />
                <span>Uptime: {botStatus.uptime}</span>
              </div>
              <div className="flex items-center space-x-2">
                <Activity className="h-4 w-4 text-gray-400" />
                <span>Cycles: {botStatus.cycles_completed}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Performance Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Today's Trades"
          value={botStatus.trades_today}
          icon={Activity}
          color="text-crypto-blue"
        />
        <StatCard
          title="Total Trades"
          value={botStatus.total_trades}
          icon={BarChart3}
          color="text-purple-400"
        />
        <StatCard
          title="Win Rate"
          value={`${(botStatus.win_rate * 100).toFixed(1)}%`}
          icon={TrendingUp}
          color="text-crypto-green"
        />
        <StatCard
          title="Today's P&L"
          value={formatCurrency(botStatus.today_pnl)}
          icon={DollarSign}
          color={botStatus.today_pnl >= 0 ? 'text-crypto-green' : 'text-crypto-red'}
        />
      </div>

      {/* Currency Grid */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
          <Zap className="h-5 w-5 text-yellow-400" />
          <span>Trading Currencies</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {botStatus.supported_currencies && botStatus.supported_currencies.map((symbol) => {
            const currencyData = botStatus.currencies[symbol] || {};
            const enabled = currencyData.enabled !== undefined ? currencyData.enabled : true;

            return (
              <div
                key={symbol}
                className={`rounded-lg p-4 border-2 transition-all ${
                  enabled
                    ? 'bg-gray-700 border-crypto-blue'
                    : 'bg-gray-800 border-gray-600 opacity-50'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <div className="font-bold text-sm">{symbol.split('-')[0]}</div>
                    <div className="text-xs text-gray-400">{getCurrencyDisplayName(symbol)}</div>
                  </div>
                  <button
                    onClick={() => handleToggleCurrency(symbol, enabled)}
                    className={`p-2 rounded-lg transition-colors ${
                      enabled
                        ? 'bg-crypto-green/20 hover:bg-crypto-green/30 text-crypto-green'
                        : 'bg-gray-600 hover:bg-gray-500 text-gray-400'
                    }`}
                  >
                    {enabled ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                  </button>
                </div>

                {enabled && (
                  <div className="space-y-2">
                    {/* Current Signal */}
                    <div className={`rounded-lg p-2 mb-2 border ${
                      currencyData.current_action === 'BUY'
                        ? 'bg-crypto-green/10 border-crypto-green'
                        : currencyData.current_action === 'SELL'
                        ? 'bg-crypto-red/10 border-crypto-red'
                        : 'bg-gray-700 border-gray-600'
                    }`}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold">{currencyData.current_action || 'HOLD'}</span>
                        <span className="text-xs font-bold">
                          {((currencyData.current_confidence || 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="text-xs text-gray-400 line-clamp-2">
                        {currencyData.current_reason || 'Analyzing...'}
                      </div>
                    </div>

                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between">
                        <span className="text-gray-400">Price:</span>
                        <span className="font-medium">${currencyData.last_price?.toLocaleString() || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Trades Today:</span>
                        <span className="font-medium">{currencyData.trades_today || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Open Positions:</span>
                        <span className="font-medium">{currencyData.open_positions || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">P&L Today:</span>
                        <span className={`font-medium ${
                          (currencyData.pnl_today || 0) >= 0 ? 'text-crypto-green' : 'text-crypto-red'
                        }`}>
                          {formatCurrency(currencyData.pnl_today || 0)}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent Trades */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
          <BarChart3 className="h-5 w-5 text-crypto-blue" />
          <span>Recent Trades</span>
        </h2>

        {tradesHistory.length === 0 ? (
          <div className="text-center text-gray-400 py-8">
            No trades yet. Start the bot to begin trading.
          </div>
        ) : (
          <div className="space-y-3">
            {tradesHistory.map((trade, index) => (
              <div
                key={trade.id || index}
                className="flex items-center justify-between p-4 bg-gray-700 rounded-lg border border-gray-600"
              >
                <div className="flex items-center space-x-4">
                  <div className={`p-2 rounded-lg ${
                    trade.action === 'BUY'
                      ? 'bg-crypto-green/20 text-crypto-green'
                      : 'bg-crypto-red/20 text-crypto-red'
                  }`}>
                    {trade.action === 'BUY' ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                  </div>

                  <div>
                    <div className="font-bold">{trade.symbol}</div>
                    <div className="text-sm text-gray-400">
                      {trade.action} {trade.crypto_amount?.toFixed(8)} @ ${trade.price?.toFixed(2)}
                    </div>
                  </div>
                </div>

                <div className="text-right">
                  <div className="font-medium">{formatCurrency(trade.amount_usd)}</div>
                  <div className="text-xs text-gray-400">
                    {new Date(trade.timestamp).toLocaleTimeString()}
                  </div>
                </div>

                <div>
                  {trade.status === 'EXECUTED' ? (
                    <CheckCircle className="h-5 w-5 text-crypto-green" />
                  ) : trade.status === 'FAILED' ? (
                    <XCircle className="h-5 w-5 text-crypto-red" />
                  ) : (
                    <Clock className="h-5 w-5 text-yellow-400" />
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Strategy Info */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
          <Shield className="h-5 w-5 text-purple-400" />
          <span>Strategy Information</span>
        </h2>

        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-400">Algorithm:</span>
            <span className="font-medium">Advanced Multi-Indicator AI</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Indicators:</span>
            <span className="font-medium">RSI, MACD, Bollinger Bands, MA, Momentum</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Min Confidence:</span>
            <span className="font-medium">65%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Check Interval:</span>
            <span className="font-medium">45 seconds</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Max Position Size:</span>
            <span className="font-medium">$100 per trade</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Daily Loss Limit:</span>
            <span className="font-medium">$200</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const StatCard = ({ title, value, icon: Icon, color }) => (
  <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
    <div className="flex items-center justify-between mb-2">
      <span className="text-gray-400 text-sm">{title}</span>
      <Icon className={`h-4 w-4 ${color}`} />
    </div>
    <div className={`text-2xl font-bold ${color}`}>{value}</div>
  </div>
);

export default EnhancedAutoTradingBot;
