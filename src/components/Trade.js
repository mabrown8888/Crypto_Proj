import React, { useState, useEffect } from 'react';
import socketService from '../services/socketService';
import TradingPanel from './TradingPanel';
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Activity,
  Clock,
  BarChart3,
  RefreshCw,
  ChevronDown
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

const Trade = () => {
  const [selectedPair, setSelectedPair] = useState('BTC-USDC');
  const [cryptoData, setCryptoData] = useState({});
  const [botData, setBotData] = useState({
    currentPrice: 0,
    signal: 'HOLD',
    reason: 'Initializing...',
    position: null,
    indicators: {
      rsi: 0,
      sma_short: 0,
      sma_long: 0,
      bollinger_upper: 0,
      bollinger_lower: 0
    }
  });
  const [priceHistory, setPriceHistory] = useState([]);
  const [isConnected, setIsConnected] = useState(true);

  const availablePairs = [
    { id: 'BTC-USDC', name: 'Bitcoin', symbol: 'BTC' },
    { id: 'ETH-USDC', name: 'Ethereum', symbol: 'ETH' },
    { id: 'SOL-USDC', name: 'Solana', symbol: 'SOL' },
    { id: 'ADA-USDC', name: 'Cardano', symbol: 'ADA' },
    { id: 'DOGE-USDC', name: 'Dogecoin', symbol: 'DOGE' },
    { id: 'AVAX-USDC', name: 'Avalanche', symbol: 'AVAX' },
    { id: 'MATIC-USDC', name: 'Polygon', symbol: 'MATIC' },
    { id: 'LINK-USDC', name: 'Chainlink', symbol: 'LINK' },
    { id: 'DOT-USDC', name: 'Polkadot', symbol: 'DOT' },
    { id: 'UNI-USDC', name: 'Uniswap', symbol: 'UNI' },
    { id: 'XRP-USDC', name: 'Ripple', symbol: 'XRP' },
    { id: 'ATOM-USDC', name: 'Cosmos', symbol: 'ATOM' },
    { id: 'LTC-USDC', name: 'Litecoin', symbol: 'LTC' },
    { id: 'BCH-USDC', name: 'Bitcoin Cash', symbol: 'BCH' },
    { id: 'XLM-USDC', name: 'Stellar', symbol: 'XLM' },
    { id: 'ALGO-USDC', name: 'Algorand', symbol: 'ALGO' },
    { id: 'NEAR-USDC', name: 'NEAR Protocol', symbol: 'NEAR' },
    { id: 'APT-USDC', name: 'Aptos', symbol: 'APT' },
    { id: 'ARB-USDC', name: 'Arbitrum', symbol: 'ARB' },
    { id: 'OP-USDC', name: 'Optimism', symbol: 'OP' },
    { id: 'FIL-USDC', name: 'Filecoin', symbol: 'FIL' },
    { id: 'HBAR-USDC', name: 'Hedera', symbol: 'HBAR' },
    { id: 'VET-USDC', name: 'VeChain', symbol: 'VET' },
    { id: 'ICP-USDC', name: 'Internet Computer', symbol: 'ICP' },
    { id: 'AAVE-USDC', name: 'Aave', symbol: 'AAVE' },
    { id: 'MKR-USDC', name: 'Maker', symbol: 'MKR' },
    { id: 'GRT-USDC', name: 'The Graph', symbol: 'GRT' },
    { id: 'SNX-USDC', name: 'Synthetix', symbol: 'SNX' },
    { id: 'COMP-USDC', name: 'Compound', symbol: 'COMP' },
    { id: 'CRV-USDC', name: 'Curve DAO', symbol: 'CRV' },
    { id: 'SAND-USDC', name: 'The Sandbox', symbol: 'SAND' },
    { id: 'MANA-USDC', name: 'Decentraland', symbol: 'MANA' },
    { id: 'AXS-USDC', name: 'Axie Infinity', symbol: 'AXS' },
    { id: 'FTM-USDC', name: 'Fantom', symbol: 'FTM' },
    { id: 'ONE-USDC', name: 'Harmony', symbol: 'ONE' },
    { id: 'ROSE-USDC', name: 'Oasis Network', symbol: 'ROSE' },
    { id: 'ENJ-USDC', name: 'Enjin Coin', symbol: 'ENJ' },
    { id: 'CHZ-USDC', name: 'Chiliz', symbol: 'CHZ' },
    { id: 'SHIB-USDC', name: 'Shiba Inu', symbol: 'SHIB' },
    { id: 'PEPE-USDC', name: 'Pepe', symbol: 'PEPE' },
  ];

  // Connect to WebSocket and listen for real-time updates
  useEffect(() => {
    const socket = socketService.connect();

    socketService.on('connect', () => {
      console.log('Trade page: Connected to backend');
      setIsConnected(true);
    });

    socketService.on('disconnect', () => {
      console.log('Trade page: Disconnected from backend');
      setIsConnected(false);
    });

    socketService.on('bot_update', (data) => {
      console.log('Received bot update:', data);

      // Only update if BTC is selected (bot data is only for BTC)
      if (selectedPair === 'BTC-USDC') {
        const mappedData = {
          currentPrice: data.current_price || data.currentPrice || 0,
          signal: data.signal || 'HOLD',
          reason: data.reason || 'Initializing...',
          position: data.position || null,
          indicators: data.indicators || {
            rsi: 0,
            sma_short: 0,
            sma_long: 0,
            bollinger_upper: 0,
            bollinger_lower: 0
          }
        };

        setBotData(mappedData);
        setIsConnected(true);

        if (data.current_price || data.currentPrice) {
          const price = data.current_price || data.currentPrice;
          setPriceHistory(prev => {
            const newHistory = [...prev, {
              time: new Date().toLocaleTimeString(),
              price: price
            }];
            return newHistory.slice(-20);
          });
        }
      }
    });

    fetchBotData();
    fetchCryptoData();

    const interval = setInterval(() => {
      fetchBotData();
      fetchCryptoData();
    }, 30000);

    return () => {
      clearInterval(interval);
      socketService.off('connect');
      socketService.off('disconnect');
      socketService.off('bot_update');
    };
  }, [selectedPair]);

  // Update price history when selected crypto changes
  useEffect(() => {
    // Clear price history when switching cryptos
    setPriceHistory([]);

    // Get initial price for the selected crypto
    const currentData = getCurrentData();
    if (currentData.price > 0) {
      setPriceHistory([{
        time: new Date().toLocaleTimeString(),
        price: currentData.price
      }]);
    }
  }, [selectedPair, cryptoData]);

  const fetchBotData = async () => {
    try {
      const response = await fetch('http://localhost:5001/api/bot/status');
      if (response.ok) {
        const data = await response.json();
        console.log('Fetched bot data via API:', data);

        const mappedData = {
          currentPrice: data.current_price || 0,
          signal: data.signal || 'HOLD',
          reason: data.reason || 'Initializing...',
          position: data.position || null,
          indicators: data.indicators || {
            rsi: 0,
            sma_short: 0,
            sma_long: 0,
            bollinger_upper: 0,
            bollinger_lower: 0
          }
        };

        setBotData(mappedData);
        setIsConnected(true);

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

  const fetchCryptoData = async () => {
    try {
      const response = await fetch('http://localhost:5001/api/crypto');
      if (response.ok) {
        const data = await response.json();
        setCryptoData(data.crypto_data || {});
      }
    } catch (error) {
      console.error('Error fetching crypto data:', error);
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

  const getCurrentPrice = () => {
    if (selectedPair === 'BTC-USDC' && botData.currentPrice > 0) {
      return botData.currentPrice;
    }
    return cryptoData[selectedPair]?.price || 0;
  };

  const getCurrentPriceForDisplay = () => {
    const price = getCurrentPrice();
    return price > 0 ? price : (cryptoData[selectedPair]?.price || 0);
  };

  const getCurrentData = () => {
    if (selectedPair === 'BTC-USDC') {
      return {
        price: botData.currentPrice,
        change_24h: 0,
        volume_24h: 0,
        market_cap: 0
      };
    }
    return cryptoData[selectedPair] || {
      price: 0,
      change_24h: 0,
      volume_24h: 0,
      market_cap: 0
    };
  };

  const chartData = {
    labels: priceHistory.map(point => point.time),
    datasets: [
      {
        label: `${selectedPair} Price`,
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
    maintainAspectRatio: false,
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
          callback: function(value) {
            return '$' + value.toLocaleString();
          }
        },
      },
    },
  };

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
          <span className="font-bold text-lg">AI Signal: {signal}</span>
        </div>
        <p className="text-sm mt-1 opacity-80">{reason}</p>
      </div>
    );
  };

  const currentData = getCurrentData();

  return (
    <div className="space-y-6">
      {/* Header with Crypto Selector */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h2 className="text-2xl font-bold">Trade</h2>

          {/* Crypto Selector Dropdown */}
          <div className="relative">
            <select
              value={selectedPair}
              onChange={(e) => setSelectedPair(e.target.value)}
              className="appearance-none bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 pr-10 text-white font-medium hover:bg-gray-700 transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-crypto-blue"
            >
              {availablePairs.map(pair => (
                <option key={pair.id} value={pair.id}>
                  {pair.name} ({pair.symbol})
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
          </div>
        </div>

        <button
          onClick={() => {
            fetchBotData();
            fetchCryptoData();
          }}
          className="flex items-center space-x-2 px-4 py-2 bg-crypto-blue hover:bg-crypto-blue/80 rounded-lg transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Connection Status */}
      <div className={`rounded-lg p-4 ${isConnected ? 'bg-crypto-green/20 border border-crypto-green' : 'bg-crypto-red/20 border border-crypto-red'}`}>
        <div className="flex items-center space-x-2">
          <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-crypto-green' : 'bg-crypto-red'} animate-pulse`}></div>
          <span className="font-medium">
            {isConnected ? 'Trading Bot Connected' : 'Trading Bot Disconnected'}
          </span>
        </div>
      </div>

      {/* AI Signal (only for BTC) */}
      {selectedPair === 'BTC-USDC' && (
        <SignalIndicator signal={botData.signal} reason={botData.reason} />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Price Chart & Stats */}
        <div className="lg:col-span-2 space-y-6">
          {/* Current Price Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <p className="text-gray-400 text-sm">Price</p>
              <p className="text-xl font-bold text-white">{formatCurrency(currentData.price)}</p>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <p className="text-gray-400 text-sm">24h Change</p>
              <p className="text-lg font-bold">{formatPercentage(currentData.change_24h)}</p>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <p className="text-gray-400 text-sm">24h Volume</p>
              <p className="text-lg font-bold text-white">
                {currentData.volume_24h >= 1e9 ? `$${(currentData.volume_24h / 1e9).toFixed(2)}B` :
                 currentData.volume_24h >= 1e6 ? `$${(currentData.volume_24h / 1e6).toFixed(2)}M` :
                 formatCurrency(currentData.volume_24h, 0)}
              </p>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <p className="text-gray-400 text-sm">Market Cap</p>
              <p className="text-lg font-bold text-white">
                {currentData.market_cap >= 1e9 ? `$${(currentData.market_cap / 1e9).toFixed(2)}B` :
                 currentData.market_cap >= 1e6 ? `$${(currentData.market_cap / 1e6).toFixed(2)}M` :
                 formatCurrency(currentData.market_cap, 0)}
              </p>
            </div>
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
            <div className="h-80">
              {priceHistory.length > 0 ? (
                <Line data={chartData} options={chartOptions} />
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500">
                  Collecting price data...
                </div>
              )}
            </div>
          </div>

          {/* Technical Indicators (BTC only) */}
          {selectedPair === 'BTC-USDC' && (
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h3 className="text-lg font-semibold mb-4">Technical Indicators</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <p className="text-gray-400 text-sm">RSI</p>
                  <p className={`text-lg font-bold ${botData.indicators.rsi < 30 ? 'text-crypto-green' :
                                                   botData.indicators.rsi > 70 ? 'text-crypto-red' :
                                                   'text-crypto-yellow'}`}>
                    {botData.indicators.rsi || 0}
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-gray-400 text-sm">SMA Short</p>
                  <p className="text-lg font-bold text-white">${botData.indicators.sma_short?.toLocaleString() || 0}</p>
                </div>
                <div className="text-center">
                  <p className="text-gray-400 text-sm">SMA Long</p>
                  <p className="text-lg font-bold text-white">${botData.indicators.sma_long?.toLocaleString() || 0}</p>
                </div>
                <div className="text-center">
                  <p className="text-gray-400 text-sm">Bollinger</p>
                  <div className="text-xs text-gray-400">
                    <p>U: ${botData.indicators.bollinger_upper?.toLocaleString() || 0}</p>
                    <p>L: ${botData.indicators.bollinger_lower?.toLocaleString() || 0}</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Current Position */}
          {selectedPair === 'BTC-USDC' && (
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
                    <span className="text-white">{botData.position.size} {selectedPair.split('-')[0]}</span>
                  </div>
                </div>
              ) : (
                <p className="text-gray-500 text-center py-4">No open position</p>
              )}
            </div>
          )}
        </div>

        {/* Right Column - Trading Panel */}
        <div className="lg:col-span-1">
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 sticky top-6">
            <h3 className="text-lg font-semibold mb-6">Live Trading</h3>
            <TradingPanel selectedPair={selectedPair} currentPrice={getCurrentPriceForDisplay()} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Trade;
