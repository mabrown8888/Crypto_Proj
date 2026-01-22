import React, { useState, useEffect } from 'react';
import {
  Bot,
  Play,
  Pause,
  Square,
  TrendingUp,
  TrendingDown,
  Shield,
  Zap,
  BarChart3,
  AlertTriangle,
  CheckCircle,
  DollarSign,
  Clock
} from 'lucide-react';
import { authUtils } from '../utils/auth';

const AutoTradingBot = () => {
  const [strategies, setStrategies] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [botStatus, setBotStatus] = useState('stopped'); // stopped, running, paused
  const [tradingHistory, setTradingHistory] = useState([]);
  const [performance, setPerformance] = useState({
    totalTrades: 0,
    profitableTrades: 0,
    totalPnL: 0,
    todayPnL: 0,
    winRate: 0
  });
  const [currentSignal, setCurrentSignal] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchStrategies();
    fetchTradingHistory();
    fetchPerformance();
    fetchBotMonitor(); // Initial monitor check
  }, []);

  useEffect(() => {
    let interval;
    if (botStatus === 'running') {
      // Fetch monitor data every 10 seconds for better visibility
      interval = setInterval(() => {
        fetchCurrentSignal();
        fetchBotMonitor();
        fetchPerformance();
      }, 10000); // Check every 10 seconds
    }
    return () => clearInterval(interval);
  }, [botStatus]);

  const fetchStrategies = async () => {
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/trading-strategies');
      if (response.ok) {
        const data = await response.json();
        setStrategies(data.strategies || []);
      }
    } catch (error) {
      console.error('Error fetching strategies:', error);
    }
  };

  const fetchTradingHistory = async () => {
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/auto-trading-history');
      if (response.ok) {
        const data = await response.json();
        setTradingHistory(data.trades || []);
      }
    } catch (error) {
      console.error('Error fetching trading history:', error);
    }
  };

  const fetchPerformance = async () => {
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/auto-trading-performance');
      if (response.ok) {
        const data = await response.json();
        setPerformance(data);
      }
    } catch (error) {
      console.error('Error fetching performance:', error);
    }
  };

  const fetchCurrentSignal = async () => {
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/current-trading-signal');
      if (response.ok) {
        const data = await response.json();
        setCurrentSignal(data.signal);
      }
    } catch (error) {
      console.error('Error fetching current signal:', error);
    }
  };

  const fetchBotMonitor = async () => {
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/bot-monitor');
      if (response.ok) {
        const data = await response.json();
        console.log('🤖 Bot Monitor:', {
          status: data.status,
          priceCount: data.price_history_count,
          threadAlive: data.thread_alive,
          lastSignal: data.last_signal,
          latestPrice: data.latest_price
        });
        return data;
      }
    } catch (error) {
      console.error('Error fetching bot monitor:', error);
    }
  };

  const handleStrategySelect = async (strategyId) => {
    setLoading(true);
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/set-trading-strategy', {
        method: 'POST',
        body: JSON.stringify({ strategy_id: strategyId })
      });

      if (response.ok) {
        setSelectedStrategy(strategyId);
        const selectedStrat = strategies.find(s => s.id === strategyId);
        console.log(`Selected strategy: ${selectedStrat?.name}`);
      } else {
        console.error('Failed to set strategy');
      }
    } catch (error) {
      console.error('Error setting strategy:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleBotControl = async (action) => {
    if (action === 'start' && !selectedStrategy) {
      alert('Please select a trading strategy first!');
      return;
    }

    setLoading(true);
    try {
      const response = await authUtils.authenticatedFetch(`http://localhost:5001/api/trading-bot/${action}`, {
        method: 'POST'
      });

      if (response.ok) {
        setBotStatus(action === 'stop' ? 'stopped' : action === 'start' ? 'running' : 'paused');
        if (action === 'start') {
          fetchCurrentSignal();
        }
      } else {
        console.error(`Failed to ${action} bot`);
      }
    } catch (error) {
      console.error(`Error ${action}ing bot:`, error);
    } finally {
      setLoading(false);
    }
  };

  const getRiskIcon = (riskLevel) => {
    switch (riskLevel) {
      case 'Conservative': return <Shield className="h-4 w-4 text-green-400" />;
      case 'Moderate': return <BarChart3 className="h-4 w-4 text-yellow-400" />;
      case 'Aggressive': return <Zap className="h-4 w-4 text-red-400" />;
      default: return <BarChart3 className="h-4 w-4 text-gray-400" />;
    }
  };

  const getRiskColor = (riskLevel) => {
    switch (riskLevel) {
      case 'Conservative': return 'text-green-400 bg-green-400/10 border-green-400/20';
      case 'Moderate': return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20';
      case 'Aggressive': return 'text-red-400 bg-red-400/10 border-red-400/20';
      default: return 'text-gray-400 bg-gray-400/10 border-gray-400/20';
    }
  };

  const getSignalColor = (signal) => {
    switch (signal) {
      case 'STRONG_BUY': return 'text-green-400 bg-green-400/20';
      case 'BUY': return 'text-green-300 bg-green-400/10';
      case 'HOLD': return 'text-gray-400 bg-gray-400/10';
      case 'SELL': return 'text-red-300 bg-red-400/10';
      case 'STRONG_SELL': return 'text-red-400 bg-red-400/20';
      default: return 'text-gray-400 bg-gray-400/10';
    }
  };

  const StrategyCard = ({ strategy }) => (
    <div 
      className={`bg-gray-800 rounded-lg p-4 border cursor-pointer transition-all ${
        selectedStrategy === strategy.id 
          ? 'border-crypto-blue bg-crypto-blue/5' 
          : 'border-gray-700 hover:border-gray-600'
      }`}
      onClick={() => handleStrategySelect(strategy.id)}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-white">{strategy.name}</h3>
        <div className={`px-2 py-1 rounded-full text-xs border ${getRiskColor(strategy.risk_level)}`}>
          {getRiskIcon(strategy.risk_level)}
          <span className="ml-1">{strategy.risk_level}</span>
        </div>
      </div>
      
      <p className="text-gray-400 text-sm mb-3">{strategy.description}</p>
      
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <span className="text-gray-500">Max Trade:</span>
          <span className="text-white ml-1">${strategy.max_trade_amount}</span>
        </div>
        <div>
          <span className="text-gray-500">Daily Trades:</span>
          <span className="text-white ml-1">{strategy.max_daily_trades}</span>
        </div>
        <div>
          <span className="text-gray-500">Stop Loss:</span>
          <span className="text-red-400 ml-1">{strategy.stop_loss_percent}%</span>
        </div>
        <div>
          <span className="text-gray-500">Take Profit:</span>
          <span className="text-green-400 ml-1">{strategy.take_profit_percent}%</span>
        </div>
      </div>
      
      {selectedStrategy === strategy.id && (
        <div className="mt-3 pt-3 border-t border-gray-700">
          <CheckCircle className="h-4 w-4 text-crypto-blue inline mr-2" />
          <span className="text-crypto-blue text-sm">Selected Strategy</span>
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Bot className="h-8 w-8 text-crypto-blue" />
          <div>
            <h1 className="text-2xl font-bold text-white">AI Auto-Trading Bot</h1>
            <p className="text-gray-400">Automated cryptocurrency trading with AI strategies</p>
          </div>
        </div>
        
        <div className={`px-4 py-2 rounded-full text-sm font-medium ${
          botStatus === 'running' ? 'bg-green-500/20 text-green-400' :
          botStatus === 'paused' ? 'bg-yellow-500/20 text-yellow-400' :
          'bg-gray-500/20 text-gray-400'
        }`}>
          {botStatus === 'running' ? '🟢 Running' : 
           botStatus === 'paused' ? '🟡 Paused' : '🔴 Stopped'}
        </div>
      </div>

      {/* Performance Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center space-x-2">
            <BarChart3 className="h-5 w-5 text-crypto-blue" />
            <span className="text-gray-400">Total Trades</span>
          </div>
          <div className="text-2xl font-bold text-white mt-1">{performance.totalTrades}</div>
        </div>
        
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center space-x-2">
            <TrendingUp className="h-5 w-5 text-green-400" />
            <span className="text-gray-400">Win Rate</span>
          </div>
          <div className="text-2xl font-bold text-green-400 mt-1">{performance.winRate.toFixed(1)}%</div>
        </div>
        
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center space-x-2">
            <DollarSign className="h-5 w-5 text-crypto-blue" />
            <span className="text-gray-400">Total P&L</span>
          </div>
          <div className={`text-2xl font-bold mt-1 ${performance.totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            ${performance.totalPnL.toFixed(2)}
          </div>
        </div>
        
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center space-x-2">
            <Clock className="h-5 w-5 text-yellow-400" />
            <span className="text-gray-400">Today P&L</span>
          </div>
          <div className={`text-2xl font-bold mt-1 ${performance.todayPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            ${performance.todayPnL.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Current Signal */}
      {currentSignal && botStatus === 'running' && (
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="font-semibold text-white mb-3">Current AI Signal</h3>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className={`px-3 py-1 rounded-full text-sm font-medium ${getSignalColor(currentSignal.action)}`}>
                {currentSignal.action}
              </div>
              <div className="text-gray-400">
                Confidence: <span className="text-white">{(currentSignal.confidence * 100).toFixed(1)}%</span>
              </div>
              <div className="text-gray-400">
                Price: <span className="text-white">${currentSignal.price?.toFixed(2)}</span>
              </div>
            </div>
            <div className="text-sm text-gray-400 max-w-md">
              {currentSignal.reason}
            </div>
          </div>
        </div>
      )}

      {/* Strategy Selection */}
      <div>
        <h2 className="text-xl font-bold text-white mb-4">Choose AI Trading Strategy</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {strategies.map((strategy) => (
            <StrategyCard key={strategy.id} strategy={strategy} />
          ))}
        </div>
      </div>

      {/* Bot Controls */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="font-semibold text-white mb-4">Bot Controls</h3>
        
        {!selectedStrategy && (
          <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3 mb-4">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="h-4 w-4 text-yellow-400" />
              <span className="text-yellow-400 text-sm">Please select a trading strategy before starting the bot</span>
            </div>
          </div>
        )}
        
        <div className="flex space-x-3">
          <button
            onClick={() => handleBotControl('start')}
            disabled={loading || botStatus === 'running' || !selectedStrategy}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              botStatus === 'running' || !selectedStrategy
                ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                : 'bg-green-600 hover:bg-green-700 text-white'
            }`}
          >
            <Play className="h-4 w-4" />
            <span>Start Bot</span>
          </button>
          
          <button
            onClick={() => handleBotControl('pause')}
            disabled={loading || botStatus !== 'running'}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              botStatus !== 'running'
                ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                : 'bg-yellow-600 hover:bg-yellow-700 text-white'
            }`}
          >
            <Pause className="h-4 w-4" />
            <span>Pause</span>
          </button>
          
          <button
            onClick={() => handleBotControl('stop')}
            disabled={loading || botStatus === 'stopped'}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              botStatus === 'stopped'
                ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                : 'bg-red-600 hover:bg-red-700 text-white'
            }`}
          >
            <Square className="h-4 w-4" />
            <span>Stop Bot</span>
          </button>
        </div>
      </div>

      {/* Recent Trading Activity */}
      {tradingHistory.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="font-semibold text-white mb-4">Recent Auto-Trading Activity</h3>
          <div className="space-y-3">
            {tradingHistory.slice(0, 5).map((trade, index) => (
              <div key={index} className="flex items-center justify-between py-2 border-b border-gray-700 last:border-b-0">
                <div className="flex items-center space-x-3">
                  <div className={`w-2 h-2 rounded-full ${trade.action === 'BUY' ? 'bg-green-400' : 'bg-red-400'}`}></div>
                  <span className="text-white font-medium">{trade.action}</span>
                  <span className="text-gray-400">${trade.amount}</span>
                  <span className="text-gray-500 text-sm">{trade.strategy}</span>
                </div>
                <div className="text-right">
                  <div className={`text-sm font-medium ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {trade.pnl >= 0 ? '+' : ''}${trade.pnl?.toFixed(2)}
                  </div>
                  <div className="text-gray-500 text-xs">{trade.timestamp}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default AutoTradingBot;