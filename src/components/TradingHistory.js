import React, { useState, useEffect } from 'react';
import { 
  Clock, 
  TrendingUp, 
  TrendingDown, 
  DollarSign,
  Activity,
  Filter,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertCircle,
  BarChart3
} from 'lucide-react';

const TradingHistory = () => {
  const [orders, setOrders] = useState([]);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('trades'); // 'orders' or 'trades'
  const [filter, setFilter] = useState('all'); // 'all', 'buy', 'sell'
  const [stats, setStats] = useState({
    totalTrades: 0,
    totalVolume: 0,
    totalFees: 0,
    avgPrice: 0,
    profitLoss: 0
  });

  useEffect(() => {
    fetchTradingHistory();
  }, []);

  useEffect(() => {
    calculateStats();
  }, [trades]);

  const fetchTradingHistory = async () => {
    setLoading(true);
    try {
      // Fetch both orders and trades
      const [ordersResponse, tradesResponse] = await Promise.all([
        fetch('http://localhost:5001/api/orders?limit=100'),
        fetch('http://localhost:5001/api/trades?limit=100')
      ]);

      if (ordersResponse.ok) {
        const ordersData = await ordersResponse.json();
        setOrders(ordersData.orders || []);
      }

      if (tradesResponse.ok) {
        const tradesData = await tradesResponse.json();
        setTrades(tradesData.trades || []);
      }
    } catch (error) {
      console.error('Error fetching trading history:', error);
    } finally {
      setLoading(false);
    }
  };

  const calculateStats = () => {
    if (trades.length === 0) return;

    const totalTrades = trades.length;
    const totalVolume = trades.reduce((sum, trade) => sum + trade.total_value, 0);
    const totalFees = trades.reduce((sum, trade) => sum + trade.fee, 0);
    const avgPrice = trades.reduce((sum, trade) => sum + trade.price, 0) / totalTrades;

    // Simple P&L calculation (this would be more complex in reality)
    let profitLoss = 0;
    const buyTrades = trades.filter(t => t.side === 'buy');
    const sellTrades = trades.filter(t => t.side === 'sell');
    
    if (buyTrades.length > 0 && sellTrades.length > 0) {
      const avgBuyPrice = buyTrades.reduce((sum, t) => sum + t.price, 0) / buyTrades.length;
      const avgSellPrice = sellTrades.reduce((sum, t) => sum + t.price, 0) / sellTrades.length;
      const minSize = Math.min(
        buyTrades.reduce((sum, t) => sum + t.size, 0),
        sellTrades.reduce((sum, t) => sum + t.size, 0)
      );
      profitLoss = (avgSellPrice - avgBuyPrice) * minSize;
    }

    setStats({
      totalTrades,
      totalVolume,
      totalFees,
      avgPrice,
      profitLoss
    });
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    }).format(amount);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusIcon = (status) => {
    switch (status?.toLowerCase()) {
      case 'filled':
      case 'done':
        return <CheckCircle className="h-4 w-4 text-crypto-green" />;
      case 'cancelled':
      case 'canceled':
        return <XCircle className="h-4 w-4 text-crypto-red" />;
      case 'pending':
      case 'open':
        return <AlertCircle className="h-4 w-4 text-crypto-yellow" />;
      default:
        return <Activity className="h-4 w-4 text-gray-400" />;
    }
  };

  const getSideColor = (side) => {
    return side?.toLowerCase() === 'buy' ? 'text-crypto-green' : 'text-crypto-red';
  };

  const getSideIcon = (side) => {
    return side?.toLowerCase() === 'buy' ? 
      <TrendingUp className="h-4 w-4" /> : 
      <TrendingDown className="h-4 w-4" />;
  };

  const filteredData = () => {
    const data = activeTab === 'orders' ? orders : trades;
    if (filter === 'all') return data;
    return data.filter(item => item.side?.toLowerCase() === filter);
  };

  const StatCard = ({ title, value, icon: Icon, color = 'text-white', subtitle }) => (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-400 text-sm font-medium">{title}</p>
          <p className={`text-xl font-bold ${color}`}>{value}</p>
          {subtitle && <p className="text-gray-500 text-xs mt-1">{subtitle}</p>}
        </div>
        <div className={`p-2 rounded-lg ${color === 'text-crypto-green' ? 'bg-crypto-green/20' : 
                                       color === 'text-crypto-red' ? 'bg-crypto-red/20' : 
                                       'bg-gray-700'}`}>
          <Icon className={`h-5 w-5 ${color}`} />
        </div>
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="h-8 w-8 animate-spin text-crypto-blue" />
          <span className="ml-2 text-lg">Loading trading history...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Trading History</h2>
        <button
          onClick={fetchTradingHistory}
          className="flex items-center space-x-2 px-4 py-2 bg-crypto-blue hover:bg-crypto-blue/80 rounded-lg transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Total Trades"
          value={stats.totalTrades}
          icon={Activity}
          color="text-crypto-blue"
        />
        <StatCard
          title="Total Volume"
          value={formatCurrency(stats.totalVolume)}
          icon={BarChart3}
          color="text-white"
        />
        <StatCard
          title="Total Fees"
          value={formatCurrency(stats.totalFees)}
          icon={DollarSign}
          color="text-crypto-yellow"
        />
        <StatCard
          title="Avg Price"
          value={formatCurrency(stats.avgPrice)}
          icon={TrendingUp}
          color="text-white"
        />
        <StatCard
          title="Est. P&L"
          value={formatCurrency(stats.profitLoss)}
          icon={stats.profitLoss >= 0 ? TrendingUp : TrendingDown}
          color={stats.profitLoss >= 0 ? 'text-crypto-green' : 'text-crypto-red'}
          subtitle="Simplified calc"
        />
      </div>

      {/* Tabs and Filters */}
      <div className="flex items-center justify-between">
        <div className="flex space-x-1 bg-gray-800 rounded-lg p-1">
          <button
            onClick={() => setActiveTab('trades')}
            className={`px-4 py-2 rounded-md transition-colors ${
              activeTab === 'trades' 
                ? 'bg-crypto-blue text-white' 
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Executed Trades
          </button>
          <button
            onClick={() => setActiveTab('orders')}
            className={`px-4 py-2 rounded-md transition-colors ${
              activeTab === 'orders' 
                ? 'bg-crypto-blue text-white' 
                : 'text-gray-400 hover:text-white'
            }`}
          >
            All Orders
          </button>
        </div>

        <div className="flex items-center space-x-2">
          <Filter className="h-4 w-4 text-gray-400" />
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-crypto-blue"
          >
            <option value="all">All Trades</option>
            <option value="buy">Buy Orders</option>
            <option value="sell">Sell Orders</option>
          </select>
        </div>
      </div>

      {/* Trading History Table */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-900">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Time
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Pair
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Side
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Size
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Price
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Total Value
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Fee
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {filteredData().slice(0, 50).map((item, index) => (
                <tr key={item.id || item.trade_id || index} className="hover:bg-gray-700/50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      {getStatusIcon(item.status || 'filled')}
                      <span className="ml-2 text-sm text-gray-300">
                        {(item.status || 'filled').toUpperCase()}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                    <div className="flex items-center">
                      <Clock className="h-4 w-4 text-gray-400 mr-2" />
                      {formatDate(item.created_time || item.created_at)}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-white">
                    {item.product_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className={`flex items-center ${getSideColor(item.side)}`}>
                      {getSideIcon(item.side)}
                      <span className="ml-2 text-sm font-medium">
                        {(item.side || 'unknown').toUpperCase()}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                    {activeTab === 'orders' ? 
                      `${item.filled_size?.toFixed(6)} / ${item.size?.toFixed(6)}` :
                      item.size?.toFixed(6)
                    }
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                    {item.price ? formatCurrency(item.price) : 'Market'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-white">
                    {formatCurrency(item.total_value || 0)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
                    {formatCurrency(item.fee || 0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {filteredData().length === 0 && (
          <div className="text-center py-12">
            <Activity className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-400">No trading history found</p>
            <p className="text-gray-500 text-sm mt-1">
              {activeTab === 'trades' ? 'Execute some trades to see them here' : 'No orders placed yet'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default TradingHistory;