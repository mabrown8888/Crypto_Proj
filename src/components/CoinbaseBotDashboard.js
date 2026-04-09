import React, { useState, useEffect } from 'react';
import { Bot, Play, Square, TrendingUp, TrendingDown, Activity, RefreshCw } from 'lucide-react';
import { authUtils } from '../utils/auth';

const API = 'http://localhost:5001';

const CoinbaseBotDashboard = () => {
  const [status, setStatus] = useState(null);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    refresh();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await authUtils.authenticatedFetch(`${API}/api/enhanced-bot/status`);
      if (res.ok) {
        const data = await res.json();
        if (data.success) setStatus(data);
      }
    } catch (e) {}
  };

  const fetchTrades = async () => {
    try {
      const res = await authUtils.authenticatedFetch(`${API}/api/enhanced-bot/trade-history?limit=10`);
      if (res.ok) {
        const data = await res.json();
        if (data.success) setTrades(data.trades || []);
      }
    } catch (e) {}
  };

  const refresh = async () => {
    await Promise.all([fetchStatus(), fetchTrades()]);
  };

  const handleStart = async () => {
    setLoading(true);
    try {
      await authUtils.authenticatedFetch(`${API}/api/enhanced-bot/start`, { method: 'POST' });
      await fetchStatus();
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await authUtils.authenticatedFetch(`${API}/api/enhanced-bot/stop`, { method: 'POST' });
      await fetchStatus();
    } finally {
      setLoading(false);
    }
  };

  const isRunning = status?.status === 'running';
  const pnl = status?.total_pnl ?? 0;
  const winRate = status?.win_rate ?? 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Bot className="h-7 w-7 text-crypto-blue" />
          <h2 className="text-2xl font-bold text-white">Coinbase Trading Bot</h2>
        </div>
        <button
          onClick={refresh}
          className="p-2 rounded-lg bg-gray-800 text-gray-400 hover:text-white transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Status + Control */}
      <div className="bg-gray-900 rounded-xl p-6 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className={`h-3 w-3 rounded-full ${isRunning ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
          <div>
            <p className="text-white font-semibold text-lg">{isRunning ? 'Running' : 'Stopped'}</p>
            {status && (
              <p className="text-gray-400 text-sm">
                {status.cycles_completed} cycles · {status.trades_today} trades today · up {status.uptime}
              </p>
            )}
          </div>
        </div>

        <button
          onClick={isRunning ? handleStop : handleStart}
          disabled={loading}
          className={`flex items-center space-x-2 px-6 py-3 rounded-lg font-semibold transition-all ${
            isRunning
              ? 'bg-red-600 hover:bg-red-700 text-white'
              : 'bg-crypto-blue hover:bg-blue-600 text-white'
          } disabled:opacity-50`}
        >
          {isRunning ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          <span>{loading ? '...' : isRunning ? 'Stop' : 'Start'}</span>
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gray-900 rounded-xl p-5">
          <p className="text-gray-400 text-sm mb-1">Total P&L</p>
          <p className={`text-2xl font-bold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
          </p>
        </div>
        <div className="bg-gray-900 rounded-xl p-5">
          <p className="text-gray-400 text-sm mb-1">Win Rate</p>
          <p className="text-2xl font-bold text-white">{winRate.toFixed(1)}%</p>
        </div>
        <div className="bg-gray-900 rounded-xl p-5">
          <p className="text-gray-400 text-sm mb-1">Total Trades</p>
          <p className="text-2xl font-bold text-white">{status?.total_trades ?? 0}</p>
        </div>
      </div>

      {/* Active Currencies */}
      {status?.currencies && Object.keys(status.currencies).length > 0 && (
        <div className="bg-gray-900 rounded-xl p-5">
          <p className="text-gray-400 text-sm mb-3 font-medium">Monitored Pairs</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(status.currencies).map(([symbol, info]) => (
              <div
                key={symbol}
                className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-sm ${
                  info.enabled ? 'bg-blue-900/40 text-blue-300' : 'bg-gray-800 text-gray-500'
                }`}
              >
                <Activity className="h-3 w-3" />
                <span>{symbol}</span>
                {info.enabled && info.current_price && (
                  <span className="text-gray-400">${Number(info.current_price).toLocaleString()}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Trades */}
      <div className="bg-gray-900 rounded-xl p-5">
        <p className="text-gray-400 text-sm mb-4 font-medium">Recent Trades</p>
        {trades.length === 0 ? (
          <p className="text-gray-600 text-sm text-center py-6">No trades yet</p>
        ) : (
          <div className="space-y-2">
            {trades.map((trade, i) => (
              <div key={trade.id || i} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                <div className="flex items-center space-x-3">
                  {trade.action === 'BUY' ? (
                    <TrendingUp className="h-4 w-4 text-green-400" />
                  ) : (
                    <TrendingDown className="h-4 w-4 text-red-400" />
                  )}
                  <div>
                    <p className="text-white text-sm font-medium">{trade.action} {trade.symbol}</p>
                    <p className="text-gray-500 text-xs">{trade.strategy} · {new Date(trade.timestamp).toLocaleTimeString()}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-white text-sm">${trade.amount_usd?.toFixed(2)}</p>
                  {trade.pnl != null && (
                    <p className={`text-xs ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CoinbaseBotDashboard;
