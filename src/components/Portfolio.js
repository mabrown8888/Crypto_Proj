import React, { useState, useEffect } from 'react';
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  DollarSign,
  PieChart,
  BarChart3,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  Clock,
  Target
} from 'lucide-react';
import { Doughnut, Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ArcElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import socketService from '../services/socketService';

ChartJS.register(
  ArcElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const Portfolio = () => {
  const [portfolioData, setPortfolioData] = useState({
    total_value: 0,
    allocations: {},
    last_updated: null
  });
  const [botData, setBotData] = useState({
    portfolio_value: 0,
    daily_pnl: 0,
    total_pnl: 0,
    daily_trades: 0
  });
  const [loading, setLoading] = useState(true);
  const [portfolioHistory, setPortfolioHistory] = useState([]);

  useEffect(() => {
    fetchPortfolioData();
    fetchBotData();

    // Connect to WebSocket for real-time updates
    const socket = socketService.connect();

    socketService.on('portfolio_update', (data) => {
      console.log('Portfolio update received:', data);
      setPortfolioData(data);

      // Update history
      if (data.total_value) {
        setPortfolioHistory(prev => {
          const newHistory = [...prev, {
            time: new Date().toLocaleTimeString(),
            value: data.total_value
          }];
          return newHistory.slice(-20); // Keep last 20 points
        });
      }
    });

    socketService.on('bot_update', (data) => {
      setBotData({
        portfolio_value: data.portfolio_value || data.portfolio || 0,
        daily_pnl: data.daily_pnl || data.dailyPnL || 0,
        total_pnl: data.total_pnl || data.totalPnL || 0,
        daily_trades: data.daily_trades || data.dailyTrades || 0
      });
    });

    // Set up interval for periodic updates
    const interval = setInterval(() => {
      fetchPortfolioData();
      fetchBotData();
    }, 30000);

    return () => {
      clearInterval(interval);
      socketService.off('portfolio_update');
      socketService.off('bot_update');
    };
  }, []);

  const fetchPortfolioData = async () => {
    try {
      const response = await fetch('http://localhost:5001/api/portfolio');
      if (response.ok) {
        const data = await response.json();
        setPortfolioData(data.portfolio || {});

        // Update history on fetch
        if (data.portfolio && data.portfolio.total_value) {
          setPortfolioHistory(prev => {
            const newHistory = [...prev, {
              time: new Date().toLocaleTimeString(),
              value: data.portfolio.total_value
            }];
            return newHistory.slice(-20);
          });
        }
      }
    } catch (error) {
      console.error('Error fetching portfolio data:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchBotData = async () => {
    try {
      const response = await fetch('http://localhost:5001/api/bot/status');
      if (response.ok) {
        const data = await response.json();
        setBotData({
          portfolio_value: data.portfolio_value || 0,
          daily_pnl: data.daily_pnl || 0,
          total_pnl: data.total_pnl || 0,
          daily_trades: data.daily_trades || 0
        });
      }
    } catch (error) {
      console.error('Error fetching bot data:', error);
    }
  };

  const formatCurrency = (amount, decimals = 2) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    }).format(amount);
  };

  const formatPercentage = (percentage) => {
    const color = percentage >= 0 ? 'text-crypto-green' : 'text-crypto-red';
    const icon = percentage >= 0 ? '↗' : '↘';
    return (
      <span className={`${color} font-medium`}>
        {icon} {Math.abs(percentage).toFixed(2)}%
      </span>
    );
  };

  // Prepare doughnut chart data
  const getDoughnutData = () => {
    if (!portfolioData.allocations || Object.keys(portfolioData.allocations).length === 0) {
      return null;
    }

    const labels = Object.keys(portfolioData.allocations);
    const values = Object.values(portfolioData.allocations).map(a => a.usd_value);
    const percentages = Object.values(portfolioData.allocations).map(a => a.percentage);

    return {
      labels: labels,
      datasets: [
        {
          data: values,
          backgroundColor: [
            '#3B82F6', // blue
            '#8B5CF6', // purple
            '#10B981', // green
            '#F59E0B', // yellow
            '#EF4444', // red
            '#06B6D4', // cyan
            '#EC4899', // pink
            '#6366F1', // indigo
          ],
          borderColor: '#1F2937',
          borderWidth: 2,
        },
      ],
    };
  };

  const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'right',
        labels: {
          color: '#9CA3AF',
          padding: 15,
          font: {
            size: 12
          }
        }
      },
      tooltip: {
        callbacks: {
          label: function(context) {
            const label = context.label || '';
            const value = formatCurrency(context.parsed);
            const percentage = portfolioData.allocations[label]?.percentage.toFixed(2);
            return `${label}: ${value} (${percentage}%)`;
          }
        }
      }
    }
  };

  // Portfolio value history chart
  const getHistoryChartData = () => {
    if (portfolioHistory.length === 0) {
      return null;
    }

    return {
      labels: portfolioHistory.map(point => point.time),
      datasets: [
        {
          label: 'Portfolio Value',
          data: portfolioHistory.map(point => point.value),
          borderColor: '#8B5CF6',
          backgroundColor: 'rgba(139, 92, 246, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
        },
      ],
    };
  };

  const historyChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
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
          callback: function(value) {
            return '$' + value.toFixed(0);
          }
        },
      },
    },
  };

  const MetricCard = ({ title, value, icon: Icon, color, subtitle, trend }) => (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-gray-400 text-sm font-medium mb-1">{title}</p>
          <p className={`text-2xl font-bold ${color}`}>{value}</p>
          {subtitle && <p className="text-gray-500 text-xs mt-1">{subtitle}</p>}
          {trend !== undefined && (
            <div className="mt-2">
              {formatPercentage(trend)}
            </div>
          )}
        </div>
        <div className={`p-3 rounded-lg ${
          color === 'text-crypto-green' ? 'bg-crypto-green/20' :
          color === 'text-crypto-red' ? 'bg-crypto-red/20' :
          color === 'text-crypto-purple' ? 'bg-crypto-purple/20' :
          'bg-crypto-blue/20'
        }`}>
          <Icon className={`h-6 w-6 ${color}`} />
        </div>
      </div>
    </div>
  );

  const AssetRow = ({ currency, allocation }) => {
    const symbol = currency === 'USDC' || currency === 'USD' ? 'USD' : currency;
    const cryptoNames = {
      'BTC': 'Bitcoin',
      'ETH': 'Ethereum',
      'SOL': 'Solana',
      'ADA': 'Cardano',
      'USDC': 'USD Coin',
      'USD': 'US Dollar'
    };

    return (
      <div className="flex items-center justify-between p-4 bg-gray-800 rounded-lg border border-gray-700 hover:bg-gray-750 transition-colors">
        <div className="flex items-center space-x-4">
          <div className="w-10 h-10 bg-crypto-purple rounded-full flex items-center justify-center text-white font-bold">
            {symbol.charAt(0)}
          </div>
          <div>
            <div className="font-semibold text-white">{symbol}</div>
            <div className="text-sm text-gray-400">{cryptoNames[symbol] || symbol}</div>
          </div>
        </div>

        <div className="text-right">
          <div className="font-semibold text-white">
            {allocation.balance.toFixed(symbol === 'USD' || symbol === 'USDC' ? 2 : 6)} {symbol}
          </div>
          <div className="text-sm text-gray-400">
            {formatCurrency(allocation.usd_value)}
          </div>
        </div>

        <div className="text-right">
          <div className="font-semibold text-crypto-blue">
            {allocation.percentage.toFixed(2)}%
          </div>
          <div className="text-sm text-gray-400">of portfolio</div>
        </div>

        <div className="w-32">
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-crypto-purple h-2 rounded-full transition-all"
              style={{ width: `${Math.min(allocation.percentage, 100)}%` }}
            ></div>
          </div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="h-8 w-8 animate-spin text-crypto-blue" />
        <span className="ml-2 text-lg">Loading portfolio...</span>
      </div>
    );
  }

  const totalValue = portfolioData.total_value || botData.portfolio_value || 0;
  const dailyPnL = botData.daily_pnl || 0;
  const totalPnL = botData.total_pnl || 0;
  const dailyPnLPercentage = totalValue > 0 ? (dailyPnL / totalValue) * 100 : 0;
  const totalPnLPercentage = totalValue > 0 ? (totalPnL / totalValue) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center">
            <Wallet className="h-8 w-8 mr-2 text-crypto-purple" />
            Portfolio Overview
          </h2>
          <p className="text-gray-400 text-sm mt-1">
            Track your complete portfolio value and performance
          </p>
        </div>
        <button
          onClick={() => {
            fetchPortfolioData();
            fetchBotData();
          }}
          className="flex items-center space-x-2 px-4 py-2 bg-crypto-blue hover:bg-crypto-blue/80 rounded-lg transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Total Portfolio Value"
          value={formatCurrency(totalValue)}
          icon={Wallet}
          color="text-crypto-purple"
          subtitle="All assets combined"
        />
        <MetricCard
          title="Daily P&L"
          value={formatCurrency(dailyPnL)}
          icon={dailyPnL >= 0 ? TrendingUp : TrendingDown}
          color={dailyPnL >= 0 ? 'text-crypto-green' : 'text-crypto-red'}
          trend={dailyPnLPercentage}
        />
        <MetricCard
          title="Total P&L"
          value={formatCurrency(totalPnL)}
          icon={totalPnL >= 0 ? ArrowUpRight : ArrowDownRight}
          color={totalPnL >= 0 ? 'text-crypto-green' : 'text-crypto-red'}
          trend={totalPnLPercentage}
        />
        <MetricCard
          title="Daily Trades"
          value={botData.daily_trades}
          icon={Activity}
          color="text-crypto-blue"
          subtitle="Transactions today"
        />
      </div>

      {/* Portfolio Distribution and History */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Asset Allocation Chart */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            <PieChart className="h-5 w-5 mr-2 text-crypto-purple" />
            Asset Allocation
          </h3>
          {getDoughnutData() ? (
            <div className="h-64">
              <Doughnut data={getDoughnutData()} options={doughnutOptions} />
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              No portfolio data available
            </div>
          )}
        </div>

        {/* Portfolio Value History */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            <BarChart3 className="h-5 w-5 mr-2 text-crypto-purple" />
            Portfolio Value History
          </h3>
          {getHistoryChartData() ? (
            <div className="h-64">
              <Line data={getHistoryChartData()} options={historyChartOptions} />
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              <div className="text-center">
                <Clock className="h-8 w-8 mx-auto mb-2 text-gray-600" />
                <p>Collecting portfolio history...</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Holdings Breakdown */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold mb-4 flex items-center">
          <Target className="h-5 w-5 mr-2 text-crypto-purple" />
          Holdings Breakdown
        </h3>

        {portfolioData.allocations && Object.keys(portfolioData.allocations).length > 0 ? (
          <div className="space-y-3">
            {Object.entries(portfolioData.allocations)
              .sort((a, b) => b[1].usd_value - a[1].usd_value)
              .map(([currency, allocation]) => (
                <AssetRow key={currency} currency={currency} allocation={allocation} />
              ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <Wallet className="h-12 w-12 mx-auto mb-3 text-gray-600" />
            <p>No holdings data available</p>
            <p className="text-sm mt-1">Your portfolio holdings will appear here</p>
          </div>
        )}
      </div>

      {/* Portfolio Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center space-x-2 mb-2">
            <DollarSign className="h-4 w-4 text-crypto-blue" />
            <span className="text-sm text-gray-400">Number of Assets</span>
          </div>
          <div className="text-2xl font-bold text-white">
            {portfolioData.allocations ? Object.keys(portfolioData.allocations).length : 0}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center space-x-2 mb-2">
            <Activity className="h-4 w-4 text-crypto-green" />
            <span className="text-sm text-gray-400">Largest Holding</span>
          </div>
          <div className="text-2xl font-bold text-white">
            {portfolioData.allocations && Object.keys(portfolioData.allocations).length > 0
              ? Object.entries(portfolioData.allocations).sort((a, b) => b[1].usd_value - a[1].usd_value)[0][0]
              : 'N/A'}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center space-x-2 mb-2">
            <Clock className="h-4 w-4 text-crypto-purple" />
            <span className="text-sm text-gray-400">Last Updated</span>
          </div>
          <div className="text-lg font-bold text-white">
            {portfolioData.last_updated
              ? new Date(portfolioData.last_updated).toLocaleTimeString()
              : 'Just now'}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Portfolio;
