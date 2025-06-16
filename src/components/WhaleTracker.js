import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  ArrowUpRight, 
  ArrowDownLeft,
  AlertTriangle,
  Eye,
  Wallet,
  DollarSign,
  Clock,
  Activity
} from 'lucide-react';

const WhaleTracker = () => {
  const [whaleData, setWhaleData] = useState({
    large_transactions: [],
    whale_alerts: [],
    flow_summary: {
      inflow: 0,
      outflow: 0,
      net_flow: 0
    },
    top_whales: [],
    exchange_flows: []
  });

  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Simulate whale data updates
    const generateWhaleData = () => {
      const transactions = Array.from({ length: 5 }, (_, i) => ({
        id: `tx_${Date.now()}_${i}`,
        hash: `0x${Math.random().toString(16).substr(2, 8)}...${Math.random().toString(16).substr(2, 8)}`,
        amount: Math.floor(Math.random() * 5000) + 100,
        from: `${Math.random().toString(16).substr(2, 6)}...${Math.random().toString(16).substr(2, 6)}`,
        to: `${Math.random().toString(16).substr(2, 6)}...${Math.random().toString(16).substr(2, 6)}`,
        timestamp: new Date(Date.now() - Math.random() * 3600000).toISOString(),
        usd_value: (Math.floor(Math.random() * 5000) + 100) * 104000,
        type: Math.random() > 0.5 ? 'exchange_deposit' : 'exchange_withdrawal',
        exchange: ['Binance', 'Coinbase', 'Kraken', 'Unknown'][Math.floor(Math.random() * 4)]
      }));

      const alerts = Array.from({ length: 3 }, (_, i) => ({
        id: `alert_${Date.now()}_${i}`,
        type: ['large_transfer', 'exchange_deposit', 'whale_accumulation'][Math.floor(Math.random() * 3)],
        message: [
          'Large BTC transfer detected from unknown wallet',
          'Significant deposit to major exchange',
          'Whale wallet showing accumulation pattern'
        ][Math.floor(Math.random() * 3)],
        timestamp: new Date(Date.now() - Math.random() * 1800000).toISOString(),
        impact: ['low', 'medium', 'high'][Math.floor(Math.random() * 3)],
        amount: Math.floor(Math.random() * 2000) + 100
      }));

      const topWhales = Array.from({ length: 5 }, (_, i) => ({
        id: `whale_${i}`,
        address: `${Math.random().toString(16).substr(2, 6)}...${Math.random().toString(16).substr(2, 6)}`,
        balance: Math.floor(Math.random() * 50000) + 10000,
        change_24h: (Math.random() - 0.5) * 1000,
        rank: i + 1,
        label: ['Satoshi Wallet', 'Exchange Cold Storage', 'Mining Pool', 'Institution', 'Unknown'][i]
      }));

      const exchangeFlows = [
        { exchange: 'Binance', inflow: 15420, outflow: 12300, net: 3120 },
        { exchange: 'Coinbase', inflow: 8900, outflow: 11200, net: -2300 },
        { exchange: 'Kraken', inflow: 5600, outflow: 4800, net: 800 },
        { exchange: 'Bitfinex', inflow: 3200, outflow: 3900, net: -700 }
      ];

      setWhaleData({
        large_transactions: transactions,
        whale_alerts: alerts,
        flow_summary: {
          inflow: exchangeFlows.reduce((sum, ex) => sum + ex.inflow, 0),
          outflow: exchangeFlows.reduce((sum, ex) => sum + ex.outflow, 0),
          net_flow: exchangeFlows.reduce((sum, ex) => sum + ex.net, 0)
        },
        top_whales: topWhales,
        exchange_flows: exchangeFlows
      });
    };

    generateWhaleData();
    setIsLoading(false);

    const interval = setInterval(generateWhaleData, 45000); // Update every 45 seconds
    return () => clearInterval(interval);
  }, []);

  const formatAmount = (amount) => {
    if (amount >= 1000) {
      return `${(amount / 1000).toFixed(1)}K`;
    }
    return amount.toFixed(1);
  };

  const formatUSD = (amount) => {
    if (amount >= 1000000000) {
      return `$${(amount / 1000000000).toFixed(1)}B`;
    } else if (amount >= 1000000) {
      return `$${(amount / 1000000).toFixed(1)}M`;
    }
    return `$${(amount / 1000).toFixed(0)}K`;
  };

  const getTimeAgo = (timestamp) => {
    const now = new Date();
    const time = new Date(timestamp);
    const diffMs = now - time;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${Math.floor(diffHours / 24)}d ago`;
  };

  const getImpactColor = (impact) => {
    switch (impact) {
      case 'high': return 'text-red-400 bg-red-400/20';
      case 'medium': return 'text-yellow-400 bg-yellow-400/20';
      case 'low': return 'text-green-400 bg-green-400/20';
      default: return 'text-gray-400 bg-gray-400/20';
    }
  };

  const getTransactionTypeIcon = (type) => {
    switch (type) {
      case 'exchange_deposit':
        return <ArrowDownLeft className="h-4 w-4 text-red-400" />;
      case 'exchange_withdrawal':
        return <ArrowUpRight className="h-4 w-4 text-green-400" />;
      default:
        return <Activity className="h-4 w-4 text-blue-400" />;
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-crypto-blue"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Flow Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm font-medium">Total Inflow</p>
              <p className="text-2xl font-bold text-green-400">
                {formatAmount(whaleData.flow_summary.inflow)} BTC
              </p>
              <p className="text-gray-500 text-xs">24h</p>
            </div>
            <div className="p-3 rounded-lg bg-green-400/20">
              <ArrowDownLeft className="h-6 w-6 text-green-400" />
            </div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm font-medium">Total Outflow</p>
              <p className="text-2xl font-bold text-red-400">
                {formatAmount(whaleData.flow_summary.outflow)} BTC
              </p>
              <p className="text-gray-500 text-xs">24h</p>
            </div>
            <div className="p-3 rounded-lg bg-red-400/20">
              <ArrowUpRight className="h-6 w-6 text-red-400" />
            </div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm font-medium">Net Flow</p>
              <p className={`text-2xl font-bold ${whaleData.flow_summary.net_flow >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {whaleData.flow_summary.net_flow >= 0 ? '+' : ''}{formatAmount(whaleData.flow_summary.net_flow)} BTC
              </p>
              <p className="text-gray-500 text-xs">24h</p>
            </div>
            <div className={`p-3 rounded-lg ${whaleData.flow_summary.net_flow >= 0 ? 'bg-green-400/20' : 'bg-red-400/20'}`}>
              {whaleData.flow_summary.net_flow >= 0 ? 
                <TrendingUp className="h-6 w-6 text-green-400" /> : 
                <TrendingDown className="h-6 w-6 text-red-400" />
              }
            </div>
          </div>
        </div>
      </div>

      {/* Whale Alerts */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
          <AlertTriangle className="h-5 w-5 text-yellow-400" />
          <span>Whale Alerts</span>
        </h3>
        <div className="space-y-3">
          {whaleData.whale_alerts.map((alert) => (
            <div key={alert.id} className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
              <div className="flex items-center space-x-3">
                <div className={`px-2 py-1 rounded text-xs font-medium ${getImpactColor(alert.impact)}`}>
                  {alert.impact.toUpperCase()}
                </div>
                <div>
                  <p className="text-white font-medium">{alert.message}</p>
                  <p className="text-gray-400 text-sm">{formatAmount(alert.amount)} BTC • {getTimeAgo(alert.timestamp)}</p>
                </div>
              </div>
              <Eye className="h-5 w-5 text-gray-400 hover:text-white cursor-pointer" />
            </div>
          ))}
        </div>
      </div>

      {/* Large Transactions */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
          <Activity className="h-5 w-5 text-crypto-blue" />
          <span>Large Transactions</span>
        </h3>
        <div className="space-y-3">
          {whaleData.large_transactions.map((tx) => (
            <div key={tx.id} className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
              <div className="flex items-center space-x-4">
                {getTransactionTypeIcon(tx.type)}
                <div>
                  <div className="flex items-center space-x-2">
                    <p className="text-white font-medium">{formatAmount(tx.amount)} BTC</p>
                    <span className="text-gray-400">•</span>
                    <p className="text-gray-400 text-sm">{formatUSD(tx.usd_value)}</p>
                  </div>
                  <p className="text-gray-500 text-xs">
                    {tx.from} → {tx.to}
                  </p>
                  <p className="text-gray-500 text-xs">
                    {tx.exchange} • {getTimeAgo(tx.timestamp)}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-gray-400 text-xs">{tx.hash}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Exchange Flows and Top Whales */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Exchange Flows */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">Exchange Flows (24h)</h3>
          <div className="space-y-3">
            {whaleData.exchange_flows.map((exchange) => (
              <div key={exchange.exchange} className="flex items-center justify-between">
                <span className="text-white font-medium">{exchange.exchange}</span>
                <div className="flex items-center space-x-4 text-sm">
                  <span className="text-green-400">↓{formatAmount(exchange.inflow)}</span>
                  <span className="text-red-400">↑{formatAmount(exchange.outflow)}</span>
                  <span className={`font-medium ${exchange.net >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {exchange.net >= 0 ? '+' : ''}{formatAmount(exchange.net)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Top Whales */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">Top Whale Wallets</h3>
          <div className="space-y-3">
            {whaleData.top_whales.map((whale) => (
              <div key={whale.id} className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 bg-crypto-blue/20 rounded-lg flex items-center justify-center">
                    <span className="text-crypto-blue font-bold text-sm">#{whale.rank}</span>
                  </div>
                  <div>
                    <p className="text-white font-medium text-sm">{whale.label}</p>
                    <p className="text-gray-400 text-xs">{whale.address}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-white font-medium text-sm">{formatAmount(whale.balance)} BTC</p>
                  <p className={`text-xs ${whale.change_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {whale.change_24h >= 0 ? '+' : ''}{formatAmount(whale.change_24h)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default WhaleTracker;