import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Activity,
  Clock,
  BarChart3,
  AlertCircle,
  CheckCircle,
  XCircle
} from 'lucide-react';

const PolymarketDashboard = () => {
  const [status, setStatus] = useState({ connected: false });
  const [markets, setMarkets] = useState([]);
  const [positions, setPositions] = useState([]);
  const [balance, setBalance] = useState(null);
  const [selectedMarket, setSelectedMarket] = useState(null);
  const [orderForm, setOrderForm] = useState({
    token_id: '',
    side: 'BUY',
    size: '',
    price: ''
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const API_BASE = 'http://localhost:5001/api/polymarket';

  // Fetch status on mount
  useEffect(() => {
    fetchStatus();
    fetchMarkets();
    const interval = setInterval(() => {
      fetchStatus();
      fetchMarkets();
    }, 30000); // Refresh every 30 seconds

    return () => clearInterval(interval);
  }, []);

  // Fetch positions and balance when connected
  useEffect(() => {
    if (status.connected) {
      fetchPositions();
      fetchBalance();
    }
  }, [status.connected]);

  const fetchStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE}/status`);
      setStatus(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch status:', err);
      setError('Failed to connect to Polymarket');
    } finally {
      setLoading(false);
    }
  };

  const fetchMarkets = async () => {
    try {
      const response = await axios.get(`${API_BASE}/markets?limit=20`);
      setMarkets(response.data.markets || []);
    } catch (err) {
      console.error('Failed to fetch markets:', err);
    }
  };

  const fetchPositions = async () => {
    try {
      const response = await axios.get(`${API_BASE}/positions`);
      setPositions(response.data.positions || []);
    } catch (err) {
      console.error('Failed to fetch positions:', err);
    }
  };

  const fetchBalance = async () => {
    try {
      const response = await axios.get(`${API_BASE}/balance`);
      setBalance(response.data);
    } catch (err) {
      console.error('Failed to fetch balance:', err);
    }
  };

  const handlePlaceOrder = async (e) => {
    e.preventDefault();

    if (!status.connected) {
      alert('Not connected to Polymarket');
      return;
    }

    try {
      const response = await axios.post(`${API_BASE}/order`, orderForm);
      if (response.data.success) {
        alert('Order placed successfully!');
        setOrderForm({ token_id: '', side: 'BUY', size: '', price: '' });
        fetchPositions();
        fetchBalance();
      }
    } catch (err) {
      alert(`Failed to place order: ${err.response?.data?.error || err.message}`);
    }
  };

  const getMarketCategoryColor = (category) => {
    const colors = {
      'Politics': 'bg-blue-500',
      'Sports': 'bg-green-500',
      'Crypto': 'bg-purple-500',
      'Entertainment': 'bg-pink-500',
      'Business': 'bg-yellow-500',
      'Other': 'bg-gray-500'
    };
    return colors[category] || colors['Other'];
  };

  const getProbabilityColor = (prob) => {
    if (prob > 0.7) return 'text-green-400';
    if (prob > 0.5) return 'text-yellow-400';
    return 'text-red-400';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-white">Loading Polymarket...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-white">Polymarket Dashboard</h1>
        <div className="flex items-center gap-2">
          {status.connected ? (
            <>
              <CheckCircle className="text-green-400" size={20} />
              <span className="text-green-400">Connected</span>
            </>
          ) : (
            <>
              <XCircle className="text-red-400" size={20} />
              <span className="text-red-400">Not Connected</span>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-500/20 border border-red-500 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="text-red-400" size={20} />
          <span className="text-red-400">{error}</span>
        </div>
      )}

      {/* Balance and Stats */}
      {status.connected && balance && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">USDC Balance</p>
                <p className="text-2xl font-bold text-white">${balance.usdc?.toFixed(2) || '0.00'}</p>
              </div>
              <DollarSign className="text-green-400" size={32} />
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Active Positions</p>
                <p className="text-2xl font-bold text-white">{positions.length}</p>
              </div>
              <Activity className="text-blue-400" size={32} />
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Total P&L</p>
                <p className={`text-2xl font-bold ${positions.reduce((sum, p) => sum + p.pnl, 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  ${positions.reduce((sum, p) => sum + p.pnl, 0).toFixed(2)}
                </p>
              </div>
              <BarChart3 className={positions.reduce((sum, p) => sum + p.pnl, 0) >= 0 ? 'text-green-400' : 'text-red-400'} size={32} />
            </div>
          </div>
        </div>
      )}

      {/* Active Positions */}
      {status.connected && positions.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-bold text-white mb-4">Your Positions</h2>
          <div className="space-y-3">
            {positions.map((position, idx) => (
              <div key={idx} className="bg-gray-900 rounded-lg p-4 border border-gray-700">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-white font-medium">{position.side} Position</p>
                    <p className="text-gray-400 text-sm">Size: {position.size}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-white">Avg: ${position.avg_price?.toFixed(3)}</p>
                    <p className={position.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                      P&L: ${position.pnl?.toFixed(2)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Markets Grid */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-bold text-white mb-4">Active Prediction Markets</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {markets.map((market, idx) => (
            <div
              key={idx}
              className="bg-gray-900 rounded-lg p-4 border border-gray-700 hover:border-blue-500 transition-colors cursor-pointer"
              onClick={() => setSelectedMarket(market)}
            >
              {/* Category Badge */}
              <div className="flex items-start justify-between mb-2">
                <span className={`text-xs px-2 py-1 rounded ${getMarketCategoryColor(market.category)} text-white`}>
                  {market.category}
                </span>
                {market.end_date && (
                  <span className="text-xs text-gray-400 flex items-center gap-1">
                    <Clock size={12} />
                    {new Date(market.end_date).toLocaleDateString()}
                  </span>
                )}
              </div>

              {/* Question */}
              <h3 className="text-white font-medium mb-3 line-clamp-2">
                {market.question}
              </h3>

              {/* Probabilities */}
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div className="bg-gray-800 rounded p-2">
                  <p className="text-xs text-gray-400 mb-1">YES</p>
                  <p className={`text-lg font-bold ${getProbabilityColor(market.yes_price)}`}>
                    ${market.yes_price?.toFixed(2)}
                    <span className="text-xs ml-1">({(market.yes_price * 100).toFixed(0)}%)</span>
                  </p>
                </div>
                <div className="bg-gray-800 rounded p-2">
                  <p className="text-xs text-gray-400 mb-1">NO</p>
                  <p className={`text-lg font-bold ${getProbabilityColor(market.no_price)}`}>
                    ${market.no_price?.toFixed(2)}
                    <span className="text-xs ml-1">({(market.no_price * 100).toFixed(0)}%)</span>
                  </p>
                </div>
              </div>

              {/* Volume */}
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-400">Volume: ${(market.volume || 0).toLocaleString()}</span>
                <span className="text-gray-400">Liquidity: ${(market.liquidity || 0).toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Order Form */}
      {status.connected && selectedMarket && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-bold text-white mb-4">Place Order</h2>
          <p className="text-gray-400 mb-4">{selectedMarket.question}</p>

          <form onSubmit={handlePlaceOrder} className="space-y-4">
            <div>
              <label className="block text-gray-400 mb-2">Token ID</label>
              <input
                type="text"
                value={orderForm.token_id}
                onChange={(e) => setOrderForm({...orderForm, token_id: e.target.value})}
                placeholder="Enter token ID"
                className="w-full bg-gray-900 border border-gray-700 rounded px-4 py-2 text-white"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-gray-400 mb-2">Side</label>
                <select
                  value={orderForm.side}
                  onChange={(e) => setOrderForm({...orderForm, side: e.target.value})}
                  className="w-full bg-gray-900 border border-gray-700 rounded px-4 py-2 text-white"
                >
                  <option value="BUY">BUY (YES)</option>
                  <option value="SELL">SELL (NO)</option>
                </select>
              </div>

              <div>
                <label className="block text-gray-400 mb-2">Size (USDC)</label>
                <input
                  type="number"
                  step="0.01"
                  value={orderForm.size}
                  onChange={(e) => setOrderForm({...orderForm, size: e.target.value})}
                  placeholder="Amount"
                  className="w-full bg-gray-900 border border-gray-700 rounded px-4 py-2 text-white"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-gray-400 mb-2">Price (0.0 - 1.0)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={orderForm.price}
                onChange={(e) => setOrderForm({...orderForm, price: e.target.value})}
                placeholder="0.50"
                className="w-full bg-gray-900 border border-gray-700 rounded px-4 py-2 text-white"
                required
              />
            </div>

            <button
              type="submit"
              className="w-full bg-blue-500 hover:bg-blue-600 text-white font-bold py-3 px-4 rounded transition-colors"
            >
              Place Order
            </button>
          </form>
        </div>
      )}

      {/* Setup Instructions */}
      {!status.connected && (
        <div className="bg-yellow-500/20 border border-yellow-500 rounded-lg p-6">
          <h3 className="text-yellow-400 font-bold mb-2 flex items-center gap-2">
            <AlertCircle size={20} />
            Setup Required
          </h3>
          <p className="text-gray-300 mb-4">
            To use Polymarket, you need to configure your credentials in the .env file:
          </p>
          <ol className="list-decimal list-inside text-gray-300 space-y-2 ml-4">
            <li>Get your private key from Magic.link or your Web3 wallet</li>
            <li>Find your Polymarket proxy address (below your profile picture on Polymarket.com)</li>
            <li>Add these to your .env file:
              <pre className="bg-gray-900 p-3 rounded mt-2 text-xs">
                POLYMARKET_PRIVATE_KEY=your_private_key{'\n'}
                POLYMARKET_PROXY_ADDRESS=your_proxy_address{'\n'}
                POLYMARKET_SIGNATURE_TYPE=1
              </pre>
            </li>
            <li>Restart the backend server</li>
          </ol>
        </div>
      )}
    </div>
  );
};

export default PolymarketDashboard;
