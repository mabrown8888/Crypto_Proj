import React, { useState, useEffect } from 'react';
import socketService from '../services/socketService';
import TradingPanel from './TradingPanel';
import { 
  TrendingUp, 
  TrendingDown, 
  DollarSign, 
  Activity,
  Clock,
  BarChart3
} from 'lucide-react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const TradingDashboard = () => {
  const [botData, setBotData] = useState({
    currentPrice: 104969.00,
    signal: 'BUY',
    reason: 'Buy signals: 1, Sell signals: 0',
    portfolio: 500.00,
    dailyPnL: 0.00,
    totalPnL: 0.00,
    dailyTrades: 0,
    position: null,
    indicators: {
      rsi: 45.2,
      sma_short: 104800,
      sma_long: 105200,
      bollinger_upper: 106000,
      bollinger_lower: 103800
    }
  });

  const [priceHistory, setPriceHistory] = useState([]);
  const [isConnected, setIsConnected] = useState(true); // Start as true since APIs are working

  // Connect to WebSocket and listen for real-time updates
  useEffect(() => {
    const socket = socketService.connect();
    
    // Listen for connection events
    socketService.on('connect', () => {
      console.log('Frontend: Connected to backend');
      setIsConnected(true);
    });
    
    socketService.on('disconnect', () => {
      console.log('Frontend: Disconnected from backend');
      setIsConnected(false);
    });
    
    socketService.on('connect_error', (error) => {
      console.log('Frontend: Connection error:', error);
      setIsConnected(false);
    });
    
    // Listen for bot updates
    socketService.on('bot_update', (data) => {
      console.log('Received bot update:', data);
      
      // Map backend data structure to frontend data structure
      const mappedData = {
        currentPrice: data.current_price || data.currentPrice || 104969.00,
        signal: data.signal || 'HOLD',
        reason: data.reason || 'Initializing...',
        portfolio: data.portfolio_value || data.portfolio || 500.00,
        dailyPnL: data.daily_pnl || data.dailyPnL || 0.00,
        totalPnL: data.total_pnl || data.totalPnL || 0.00,
        dailyTrades: data.daily_trades || data.dailyTrades || 0,
        position: data.position || null,
        indicators: data.indicators || {
          rsi: 45.2,
          sma_short: 104800,
          sma_long: 105200,
          bollinger_upper: 106000,
          bollinger_lower: 103800
        }
      };
      
      setBotData(mappedData);
      // Since we're receiving data, we're connected
      setIsConnected(true);
      
      // Update price history
      if (data.current_price || data.currentPrice) {
        const price = data.current_price || data.currentPrice;
        setPriceHistory(prev => {
          const newHistory = [...prev, {
            time: new Date().toLocaleTimeString(),
            price: price
          }];
          return newHistory.slice(-20); // Keep last 20 points
        });
      }
    });

    // Fallback: Fetch data directly from API if WebSocket fails
    const fetchData = async () => {
      try {
        const response = await fetch('http://localhost:5001/api/bot/status');
        if (response.ok) {
          const data = await response.json();
          console.log('Fetched data via API:', data);
          
          const mappedData = {
            currentPrice: data.current_price || 104969.00,
            signal: data.signal || 'HOLD',
            reason: data.reason || 'Initializing...',
            portfolio: data.portfolio_value || 500.00,
            dailyPnL: data.daily_pnl || 0.00,
            totalPnL: data.total_pnl || 0.00,
            dailyTrades: data.daily_trades || 0,
            position: data.position || null,
            indicators: data.indicators || {
              rsi: 45.2,
              sma_short: 104800,
              sma_long: 105200,
              bollinger_upper: 106000,
              bollinger_lower: 103800
            }
          };
          
          setBotData(mappedData);
          setIsConnected(true);
          
          // Update price history
          if (data.current_price) {
            setPriceHistory(prev => {
              const newHistory = [...prev, {
                time: new Date().toLocaleTimeString(),
                price: data.current_price
              }];
              return newHistory.slice(-20);
            });
          }
        }
      } catch (error) {
        console.log('API fetch failed:', error);
        setIsConnected(false);
      }
    };

    // Initial data fetch
    fetchData();

    // Set up interval to fetch data every 30 seconds as backup
    const interval = setInterval(fetchData, 30000);

    return () => {
      clearInterval(interval);
      socketService.off('connect');
      socketService.off('disconnect');
      socketService.off('connect_error');
      socketService.off('bot_update');
      socketService.disconnect();
    };
  }, []);

  const chartData = {
    labels: priceHistory.map(point => point.time),
    datasets: [
      {
        label: 'BTC Price',
        data: priceHistory.map(point => point.price),
        borderColor: '#3B82F6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.4,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: {
        display: false,
      },
      title: {
        display: false,
      },
    },
    scales: {
      x: {
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
        ticks: {
          color: '#9CA3AF',
        },
      },
      y: {
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
        ticks: {
          color: '#9CA3AF',
        },
      },
    },
  };

  const MetricCard = ({ title, value, icon: Icon, color, subtitle }) => (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-400 text-sm font-medium">{title}</p>
          <p className={`text-2xl font-bold ${color}`}>{value}</p>
          {subtitle && <p className="text-gray-500 text-xs mt-1">{subtitle}</p>}
        </div>
        <div className={`p-3 rounded-lg ${color === 'text-crypto-green' ? 'bg-crypto-green/20' : 
                                       color === 'text-crypto-red' ? 'bg-crypto-red/20' : 
                                       'bg-crypto-blue/20'}`}>
          <Icon className={`h-6 w-6 ${color}`} />
        </div>
      </div>
    </div>
  );

  const SignalIndicator = ({ signal, reason }) => {
    const getSignalColor = (signal) => {
      switch (signal) {
        case 'BUY': return 'text-crypto-green bg-crypto-green/20 border-crypto-green';
        case 'SELL': return 'text-crypto-red bg-crypto-red/20 border-crypto-red';
        case 'HOLD': return 'text-crypto-yellow bg-crypto-yellow/20 border-crypto-yellow';
        default: return 'text-gray-400 bg-gray-700 border-gray-600';
      }
    };

    return (
      <div className={`rounded-lg p-4 border-2 ${getSignalColor(signal)}`}>
        <div className="flex items-center space-x-2">
          <div className={`w-3 h-3 rounded-full ${signal === 'BUY' ? 'bg-crypto-green' : 
                                                   signal === 'SELL' ? 'bg-crypto-red' : 
                                                   'bg-crypto-yellow'} animate-pulse`}></div>
          <span className="font-bold text-lg">{signal}</span>
        </div>
        <p className="text-sm mt-1 opacity-80">{reason}</p>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Status Banner */}
      <div className={`rounded-lg p-4 ${isConnected ? 'bg-crypto-green/20 border border-crypto-green' : 'bg-crypto-red/20 border border-crypto-red'}`}>
        <div className="flex items-center space-x-2">
          <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-crypto-green' : 'bg-crypto-red'} animate-pulse`}></div>
          <span className="font-medium">
            {isConnected ? 'Trading Bot Connected' : 'Trading Bot Disconnected'}
          </span>
        </div>
      </div>

      {/* Current Signal */}
      <SignalIndicator signal={botData.signal} reason={botData.reason} />

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Current Price"
          value={`$${botData.currentPrice.toLocaleString()}`}
          icon={DollarSign}
          color="text-white"
          subtitle="BTC-USDC"
        />
        <MetricCard
          title="Portfolio Value"
          value={`$${botData.portfolio.toFixed(2)}`}
          icon={BarChart3}
          color="text-crypto-blue"
        />
        <MetricCard
          title="Daily P&L"
          value={`$${botData.dailyPnL.toFixed(2)}`}
          icon={botData.dailyPnL >= 0 ? TrendingUp : TrendingDown}
          color={botData.dailyPnL >= 0 ? 'text-crypto-green' : 'text-crypto-red'}
        />
        <MetricCard
          title="Daily Trades"
          value={botData.dailyTrades}
          icon={Activity}
          color="text-crypto-purple"
          subtitle={`/ ${15} max`}
        />
      </div>

      {/* Price Chart */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Price Chart</h3>
          <div className="flex items-center space-x-2 text-sm text-gray-400">
            <Clock className="h-4 w-4" />
            <span>Real-time</span>
          </div>
        </div>
        {priceHistory.length > 0 ? (
          <Line data={chartData} options={chartOptions} />
        ) : (
          <div className="h-64 flex items-center justify-center text-gray-500">
            Collecting price data...
          </div>
        )}
      </div>

      {/* Trading Panel */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold mb-6">Live Trading</h3>
        <TradingPanel />
      </div>

      {/* Technical Indicators */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold mb-4">Technical Indicators</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="text-center">
            <p className="text-gray-400 text-sm">RSI</p>
            <p className={`text-lg font-bold ${botData.indicators.rsi < 30 ? 'text-crypto-green' : 
                                             botData.indicators.rsi > 70 ? 'text-crypto-red' : 
                                             'text-crypto-yellow'}`}>
              {botData.indicators.rsi}
            </p>
          </div>
          <div className="text-center">
            <p className="text-gray-400 text-sm">SMA Short</p>
            <p className="text-lg font-bold text-white">${botData.indicators.sma_short?.toLocaleString()}</p>
          </div>
          <div className="text-center">
            <p className="text-gray-400 text-sm">SMA Long</p>
            <p className="text-lg font-bold text-white">${botData.indicators.sma_long?.toLocaleString()}</p>
          </div>
          <div className="text-center">
            <p className="text-gray-400 text-sm">Bollinger</p>
            <div className="text-xs text-gray-400">
              <p>Upper: ${botData.indicators.bollinger_upper?.toLocaleString()}</p>
              <p>Lower: ${botData.indicators.bollinger_lower?.toLocaleString()}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Position Info */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold mb-4">Current Position</h3>
        {botData.position ? (
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-400">Side:</span>
              <span className="text-crypto-green font-medium">{botData.position.side}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Entry Price:</span>
              <span className="text-white">${botData.position.entry_price}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Size:</span>
              <span className="text-white">{botData.position.size} BTC</span>
            </div>
          </div>
        ) : (
          <p className="text-gray-500 text-center py-4">No open position</p>
        )}
      </div>
    </div>
  );
};

export default TradingDashboard;