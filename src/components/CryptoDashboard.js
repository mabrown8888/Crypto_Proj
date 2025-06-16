import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  DollarSign,
  Activity,
  BarChart3,
  RefreshCw,
  Star,
  ArrowUpRight,
  ArrowDownRight,
  Wallet,
  PieChart
} from 'lucide-react';
import { Line } from 'react-chartjs-2';

const CryptoDashboard = () => {
  const [cryptoData, setCryptoData] = useState({});
  const [portfolioData, setPortfolioData] = useState({});
  const [loading, setLoading] = useState(true);
  const [selectedCrypto, setSelectedCrypto] = useState('BTC-USDC');
  const [watchlist, setWatchlist] = useState(['BTC-USDC', 'ETH-USDC', 'SOL-USDC', 'ADA-USDC']);

  useEffect(() => {
    fetchCryptoData();
    fetchPortfolioData();
    
    // Set up interval for updates
    const interval = setInterval(() => {
      fetchCryptoData();
      fetchPortfolioData();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  const fetchCryptoData = async () => {
    try {
      const response = await fetch('http://localhost:5001/api/crypto');
      if (response.ok) {
        const data = await response.json();
        setCryptoData(data.crypto_data || {});
      }
    } catch (error) {
      console.error('Error fetching crypto data:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchPortfolioData = async () => {
    try {
      const response = await fetch('http://localhost:5001/api/portfolio');
      if (response.ok) {
        const data = await response.json();
        setPortfolioData(data.portfolio || {});
      }
    } catch (error) {
      console.error('Error fetching portfolio data:', error);
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

  const formatNumber = (num) => {
    if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
    if (num >= 1e3) return `$${(num / 1e3).toFixed(2)}K`;
    return formatCurrency(num);
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

  const getCryptoSymbol = (pair) => {
    return pair.split('-')[0];
  };

  const getCryptoName = (symbol) => {
    const names = {
      'BTC': 'Bitcoin',
      'ETH': 'Ethereum',
      'SOL': 'Solana',
      'ADA': 'Cardano',
      'DOGE': 'Dogecoin',
      'AVAX': 'Avalanche',
      'MATIC': 'Polygon',
      'LINK': 'Chainlink'
    };
    return names[symbol] || symbol;
  };

  const getChartData = (crypto) => {
    if (!crypto || !crypto.price_history || crypto.price_history.length === 0) {
      return null;
    }

    return {
      labels: crypto.price_history.map((_, index) => index.toString()),
      datasets: [
        {
          data: crypto.price_history.map(point => point.price),
          borderColor: crypto.change_24h >= 0 ? '#10B981' : '#EF4444',
          backgroundColor: `${crypto.change_24h >= 0 ? '#10B981' : '#EF4444'}20`,
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 0,
        },
      ],
    };
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { enabled: false },
    },
    scales: {
      x: { display: false },
      y: { display: false },
    },
    interaction: { intersect: false },
  };

  const CryptoCard = ({ pair, data, isSelected = false }) => {
    const symbol = getCryptoSymbol(pair);
    const name = getCryptoName(symbol);
    const chartData = getChartData(data);

    return (
      <div 
        className={`bg-gray-800 rounded-lg p-4 border cursor-pointer transition-all hover:bg-gray-700 ${
          isSelected ? 'border-crypto-blue bg-gray-700' : 'border-gray-700'
        }`}
        onClick={() => setSelectedCrypto(pair)}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-crypto-blue rounded-full flex items-center justify-center text-white font-bold text-sm">
              {symbol.charAt(0)}
            </div>
            <div>
              <h3 className="font-semibold text-white">{symbol}</h3>
              <p className="text-xs text-gray-400">{name}</p>
            </div>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              const newWatchlist = watchlist.includes(pair) 
                ? watchlist.filter(w => w !== pair)
                : [...watchlist, pair];
              setWatchlist(newWatchlist);
            }}
            className="p-1 hover:bg-gray-600 rounded"
          >
            <Star className={`h-4 w-4 ${watchlist.includes(pair) ? 'text-crypto-yellow fill-current' : 'text-gray-400'}`} />
          </button>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-lg font-bold text-white">
              {formatCurrency(data.price)}
            </span>
            {formatPercentage(data.change_24h)}
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs text-gray-400">
            <div>
              <span>Volume 24h</span>
              <div className="text-white font-medium">{formatNumber(data.volume_24h)}</div>
            </div>
            <div>
              <span>Market Cap</span>
              <div className="text-white font-medium">{formatNumber(data.market_cap)}</div>
            </div>
          </div>

          {chartData && (
            <div className="h-12 mt-3">
              <Line data={chartData} options={chartOptions} />
            </div>
          )}
        </div>
      </div>
    );
  };

  const PortfolioCard = ({ currency, allocation }) => {
    const symbol = currency === 'USDC' || currency === 'USD' ? 'USD' : currency;
    
    return (
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <div className="w-6 h-6 bg-crypto-purple rounded-full flex items-center justify-center text-white font-bold text-xs">
              {symbol.charAt(0)}
            </div>
            <span className="font-medium text-white">{symbol}</span>
          </div>
          <span className="text-sm text-gray-400">{allocation.percentage.toFixed(1)}%</span>
        </div>
        
        <div className="space-y-1">
          <div className="text-lg font-bold text-white">
            {formatCurrency(allocation.usd_value)}
          </div>
          <div className="text-sm text-gray-400">
            {allocation.balance.toFixed(symbol === 'USD' ? 2 : 6)} {symbol}
          </div>
        </div>
        
        <div className="w-full bg-gray-700 rounded-full h-1 mt-2">
          <div 
            className="bg-crypto-purple h-1 rounded-full" 
            style={{ width: `${Math.min(allocation.percentage, 100)}%` }}
          ></div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="h-8 w-8 animate-spin text-crypto-blue" />
          <span className="ml-2 text-lg">Loading cryptocurrency data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Cryptocurrency Dashboard</h2>
        <button
          onClick={() => {
            fetchCryptoData();
            fetchPortfolioData();
          }}
          className="flex items-center space-x-2 px-4 py-2 bg-crypto-blue hover:bg-crypto-blue/80 rounded-lg transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Portfolio Overview */}
      {portfolioData.allocations && Object.keys(portfolioData.allocations).length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold flex items-center">
              <Wallet className="h-5 w-5 mr-2 text-crypto-purple" />
              Portfolio Overview
            </h3>
            <div className="text-right">
              <div className="text-2xl font-bold text-white">
                {formatCurrency(portfolioData.total_value)}
              </div>
              <div className="text-sm text-gray-400">Total Value</div>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.entries(portfolioData.allocations).map(([currency, allocation]) => (
              <PortfolioCard key={currency} currency={currency} allocation={allocation} />
            ))}
          </div>
        </div>
      )}

      {/* Crypto Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(cryptoData).map(([pair, data]) => (
          <CryptoCard 
            key={pair} 
            pair={pair} 
            data={data} 
            isSelected={selectedCrypto === pair}
          />
        ))}
      </div>

      {/* Selected Crypto Detail */}
      {selectedCrypto && cryptoData[selectedCrypto] && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 bg-crypto-blue rounded-full flex items-center justify-center text-white font-bold">
                {getCryptoSymbol(selectedCrypto).charAt(0)}
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">
                  {getCryptoName(getCryptoSymbol(selectedCrypto))}
                </h3>
                <p className="text-gray-400">{selectedCrypto}</p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-white">
                {formatCurrency(cryptoData[selectedCrypto].price)}
              </div>
              <div className="text-lg">
                {formatPercentage(cryptoData[selectedCrypto].change_24h)}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-gray-900 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <BarChart3 className="h-4 w-4 text-crypto-blue" />
                <span className="text-sm text-gray-400">Market Cap</span>
              </div>
              <div className="text-xl font-bold text-white">
                {formatNumber(cryptoData[selectedCrypto].market_cap)}
              </div>
            </div>

            <div className="bg-gray-900 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <Activity className="h-4 w-4 text-crypto-green" />
                <span className="text-sm text-gray-400">24h Volume</span>
              </div>
              <div className="text-xl font-bold text-white">
                {formatNumber(cryptoData[selectedCrypto].volume_24h)}
              </div>
            </div>

            <div className="bg-gray-900 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <TrendingUp className="h-4 w-4 text-crypto-purple" />
                <span className="text-sm text-gray-400">24h Change</span>
              </div>
              <div className="text-xl font-bold">
                {formatPercentage(cryptoData[selectedCrypto].change_24h)}
              </div>
            </div>
          </div>

          {/* Price Chart */}
          {getChartData(cryptoData[selectedCrypto]) && (
            <div className="mt-6">
              <h4 className="text-lg font-semibold mb-4">Price History</h4>
              <div className="h-64">
                <Line 
                  data={getChartData(cryptoData[selectedCrypto])} 
                  options={{
                    ...chartOptions,
                    plugins: { ...chartOptions.plugins, tooltip: { enabled: true } },
                    scales: { 
                      x: { display: true, grid: { color: 'rgba(255,255,255,0.1)' } },
                      y: { display: true, grid: { color: 'rgba(255,255,255,0.1)' } }
                    }
                  }} 
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CryptoDashboard;