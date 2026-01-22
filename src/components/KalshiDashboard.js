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
  XCircle,
  Award
} from 'lucide-react';

const KalshiDashboard = () => {
  const [status, setStatus] = useState({ connected: false });
  const [markets, setMarkets] = useState([]);
  const [positions, setPositions] = useState([]);
  const [balance, setBalance] = useState(null);
  const [selectedMarket, setSelectedMarket] = useState(null);
  const [orderForm, setOrderForm] = useState({
    ticker: '',
    side: 'yes',
    quantity: 1,
    price: 50,
    totalAmount: ''
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const API_BASE = 'http://localhost:5001/api/kalshi';

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
      setError('Failed to connect to Kalshi');
    } finally {
      setLoading(false);
    }
  };

  const fetchMarkets = async () => {
    try {
      const response = await axios.get(`${API_BASE}/markets?limit=100&status=open`);
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
      alert('Not connected to Kalshi');
      return;
    }

    try {
      const totalAmount = parseFloat(orderForm.totalAmount) || 0;

      if (totalAmount <= 0) {
        alert('Please enter a valid total amount');
        return;
      }

      if (!selectedMarket) {
        alert('Please select a market first');
        return;
      }

      // Use market's current price
      const marketPrice = orderForm.side === 'yes' ? selectedMarket.yes_price : selectedMarket.no_price;

      if (!marketPrice || marketPrice <= 0) {
        alert('Market price unavailable. Please try a different market.');
        return;
      }

      // Calculate contracts based on total amount and market price
      const quantity = Math.floor(totalAmount / (marketPrice / 100));

      if (quantity <= 0) {
        alert('Total amount too small. Please increase the amount.');
        return;
      }

      const orderData = {
        ticker: orderForm.ticker,
        side: orderForm.side,
        quantity: quantity,
        price: Math.round(marketPrice)
      };

      const response = await axios.post(`${API_BASE}/order`, orderData);
      if (response.data.success) {
        const payout = quantity * 1.0;
        const profit = payout - totalAmount;
        alert(`Order placed! 🎯\n\n${quantity} contracts @ ${marketPrice}¢\nCost: $${totalAmount}\nIf you win: $${payout.toFixed(2)} (profit: $${profit.toFixed(2)})`);
        setOrderForm({ ticker: '', side: 'yes', quantity: 1, price: 50, totalAmount: '' });
        setSelectedMarket(null);
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
      'Economics': 'bg-green-500',
      'Climate': 'bg-teal-500',
      'Sports': 'bg-orange-500',
      'Tech': 'bg-purple-500',
      'Crypto': 'bg-purple-600',
      'Other': 'bg-gray-500'
    };
    return colors[category] || colors['Crypto'];
  };

  const getProbabilityColor = (prob) => {
    if (prob > 0.7) return 'text-green-400';
    if (prob > 0.5) return 'text-yellow-400';
    return 'text-red-400';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-white">Loading Kalshi...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <Award className="text-blue-400" size={36} />
            Kalshi Dashboard
          </h1>
          <p className="text-gray-400 mt-1">CFTC-Regulated Prediction Markets (US-Legal)</p>
        </div>
        <div className="flex items-center gap-2">
          {status.connected ? (
            <>
              <CheckCircle className="text-green-400" size={20} />
              <span className="text-green-400">Connected</span>
              {status.demo_mode && (
                <span className="ml-2 px-2 py-1 bg-yellow-500/20 text-yellow-400 text-xs rounded">DEMO MODE</span>
              )}
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
                <p className="text-gray-400 text-sm">Account Balance</p>
                <p className="text-2xl font-bold text-white">${balance.balance?.toFixed(2) || '0.00'}</p>
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
                    <p className="text-white font-medium">{position.ticker}</p>
                    <p className="text-gray-400 text-sm">Quantity: {position.quantity}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-white">Cost: ${position.total_cost?.toFixed(2)}</p>
                    <p className="text-gray-400 text-sm">Value: ${position.current_value?.toFixed(2)}</p>
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
        <h2 className="text-xl font-bold text-white mb-4">
          Active Prediction Markets
          <span className="text-sm text-gray-400 ml-3 font-normal">
            ({markets.length} markets)
          </span>
        </h2>
        {markets.length === 0 && !loading && (
          <p className="text-gray-400 text-center py-8">
            No markets available right now. Check back later or try refreshing.
          </p>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {markets.map((market, idx) => (
            <div
              key={idx}
              className="bg-gray-900 rounded-lg p-4 border border-gray-700 hover:border-blue-500 transition-colors cursor-pointer"
              onClick={() => {
                setSelectedMarket(market);
                setOrderForm({...orderForm, ticker: market.id});
              }}
            >
              {/* Category Badge */}
              <div className="flex items-start justify-between mb-2">
                <span className={`text-xs px-2 py-1 rounded ${getMarketCategoryColor(market.category)} text-white`}>
                  {market.category}
                </span>
                {market.close_date && (
                  <span className="text-xs text-gray-400 flex items-center gap-1">
                    <Clock size={12} />
                    {new Date(market.close_date).toLocaleDateString()}
                  </span>
                )}
              </div>

              {/* Question */}
              <h3 className="text-white font-medium mb-2 line-clamp-2">
                {market.question}
              </h3>
              {market.subtitle && (
                <p className="text-gray-400 text-sm mb-3 line-clamp-1">{market.subtitle}</p>
              )}

              {/* Probabilities */}
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div className="bg-gray-800 rounded p-2">
                  <p className="text-xs text-gray-400 mb-1">YES</p>
                  <p className={`text-lg font-bold ${getProbabilityColor(market.yes_price / 100)}`}>
                    {market.yes_price?.toFixed(0)}%
                    {market.has_liquidity && <span className="text-xs ml-1 text-green-400">✓</span>}
                  </p>
                  {market.yes_bid > 0 && market.yes_ask > 0 && (
                    <p className="text-xs text-gray-500">
                      Bid: {market.yes_bid}¢ / Ask: {market.yes_ask}¢
                    </p>
                  )}
                </div>
                <div className="bg-gray-800 rounded p-2">
                  <p className="text-xs text-gray-400 mb-1">NO</p>
                  <p className={`text-lg font-bold ${getProbabilityColor(market.no_price / 100)}`}>
                    {market.no_price?.toFixed(0)}%
                    {market.has_liquidity && <span className="text-xs ml-1 text-green-400">✓</span>}
                  </p>
                  {market.no_bid > 0 && market.no_ask > 0 && (
                    <p className="text-xs text-gray-500">
                      Bid: {market.no_bid}¢ / Ask: {market.no_ask}¢
                    </p>
                  )}
                </div>
              </div>

              {/* Volume */}
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-400">Volume: {(market.volume || 0).toLocaleString()}</span>
                <span className={market.has_liquidity ? "text-green-400" : "text-gray-400"}>
                  OI: {(market.liquidity || 0).toLocaleString()}
                </span>
              </div>
              {market.has_liquidity && (
                <div className="mt-2 text-xs text-green-400">
                  ✓ High liquidity - orders likely to fill immediately
                </div>
              )}
              {!market.has_liquidity && market.volume < 1000 && (
                <div className="mt-2 text-xs text-yellow-400">
                  ⚠ Low liquidity - order may rest
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Order Form */}
      {status.connected && selectedMarket && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-bold text-white mb-4">Place Order</h2>
          <p className="text-gray-400 mb-2">{selectedMarket.question}</p>
          {selectedMarket.subtitle && (
            <p className="text-gray-500 text-sm mb-4">{selectedMarket.subtitle}</p>
          )}

          <form onSubmit={handlePlaceOrder} className="space-y-4">
            <div>
              <label className="block text-gray-400 mb-2">Market Ticker</label>
              <input
                type="text"
                value={orderForm.ticker}
                readOnly
                className="w-full bg-gray-900 border border-gray-700 rounded px-4 py-2 text-white"
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
                  <option value="yes">YES</option>
                  <option value="no">NO</option>
                </select>
              </div>

              <div>
                <label className="block text-gray-400 mb-2">Total Amount ($)</label>
                <input
                  type="number"
                  min="1"
                  step="0.01"
                  value={orderForm.totalAmount || ''}
                  onChange={(e) => {
                    setOrderForm({...orderForm, totalAmount: e.target.value});
                  }}
                  placeholder="100.00"
                  className="w-full bg-gray-900 border border-gray-700 rounded px-4 py-2 text-white"
                  required
                />
                <p className="text-gray-500 text-xs mt-1">Total dollar amount to bet (no limit)</p>
              </div>
            </div>

            <div className="bg-gray-800 rounded p-4">
              <div className="flex justify-between mb-3">
                <span className="text-gray-400">You're betting:</span>
                <span className="text-white font-bold text-xl">${orderForm.totalAmount || '0.00'}</span>
              </div>

              {selectedMarket && (
                <>
                  <div className="flex justify-between text-sm text-gray-400 mb-1">
                    <span>Current {orderForm.side.toUpperCase()} price:</span>
                    <span>{orderForm.side === 'yes' ? selectedMarket.yes_price : selectedMarket.no_price}¢</span>
                  </div>
                  <div className="flex justify-between text-sm text-gray-400">
                    <span>You'll get approx:</span>
                    <span className="text-green-400 font-medium">
                      ~{orderForm.totalAmount ? Math.floor((parseFloat(orderForm.totalAmount) || 0) / ((orderForm.side === 'yes' ? selectedMarket.yes_price : selectedMarket.no_price) / 100)) : 0} contracts
                    </span>
                  </div>
                  <div className="flex justify-between text-sm text-gray-400 mt-2 pt-2 border-t border-gray-700">
                    <span>If you win:</span>
                    <span className="text-green-400 font-bold">
                      ${orderForm.totalAmount ? (Math.floor((parseFloat(orderForm.totalAmount) || 0) / ((orderForm.side === 'yes' ? selectedMarket.yes_price : selectedMarket.no_price) / 100))).toFixed(2) : '0.00'}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm text-gray-400">
                    <span>Profit:</span>
                    <span className="text-green-400 font-bold">
                      ${orderForm.totalAmount ? (Math.floor((parseFloat(orderForm.totalAmount) || 0) / ((orderForm.side === 'yes' ? selectedMarket.yes_price : selectedMarket.no_price) / 100)) - parseFloat(orderForm.totalAmount)).toFixed(2) : '0.00'}
                    </span>
                  </div>
                </>
              )}
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
        <div className="bg-blue-500/20 border border-blue-500 rounded-lg p-6">
          <h3 className="text-blue-400 font-bold mb-2 flex items-center gap-2">
            <AlertCircle size={20} />
            Setup Required - Get Your Kalshi API Keys
          </h3>
          <p className="text-gray-300 mb-4">
            Kalshi is a CFTC-regulated prediction market platform, legal for US residents. Follow these steps:
          </p>
          <ol className="list-decimal list-inside text-gray-300 space-y-2 ml-4">
            <li>
              Create an account at{' '}
              <a href="https://kalshi.com" target="_blank" rel="noopener noreferrer" className="text-blue-400 underline">
                kalshi.com
              </a>
              {' '}(or{' '}
              <a href="https://demo.kalshi.com" target="_blank" rel="noopener noreferrer" className="text-blue-400 underline">
                demo.kalshi.com
              </a>
              {' '}for practice)
            </li>
            <li>Login and go to Settings → API Keys</li>
            <li>Click "Create New API Key"</li>
            <li>Download the <code className="bg-gray-900 px-2 py-1 rounded">.key</code> file</li>
            <li>Save it as <code className="bg-gray-900 px-2 py-1 rounded">backend/kalshi_private.key</code></li>
            <li>Copy the API Key ID and add to your .env file:
              <pre className="bg-gray-900 p-3 rounded mt-2 text-xs">
                KALSHI_API_KEY_ID=your-api-key-id-here{'\n'}
                KALSHI_PRIVATE_KEY_PATH=backend/kalshi_private.key{'\n'}
                KALSHI_DEMO_MODE=false
              </pre>
            </li>
            <li>Restart the backend server</li>
          </ol>
          <div className="mt-4 p-3 bg-green-500/20 border border-green-500 rounded">
            <p className="text-green-400 text-sm">
              ✓ US-Legal • ✓ CFTC-Regulated • ✓ Michigan Approved
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default KalshiDashboard;
