import React, { useState, useEffect } from 'react';
import { 
  Brain, 
  TrendingUp, 
  TrendingDown, 
  Target, 
  Zap,
  Settings,
  Play,
  Pause,
  BarChart3,
  Lightbulb,
  Star,
  Clock
} from 'lucide-react';

const AIStrategies = () => {
  const [strategies, setStrategies] = useState([]);
  const [activeStrategy, setActiveStrategy] = useState(null);
  const [aiInsights, setAiInsights] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    // Initialize with sample strategies
    const sampleStrategies = [
      {
        id: 'momentum_scalper',
        name: 'AI Momentum Scalper',
        description: 'High-frequency strategy based on price momentum and volume analysis',
        type: 'aggressive',
        confidence: 85,
        expected_return: '15-25%',
        risk_level: 'high',
        timeframe: '1-5 minutes',
        conditions: ['High volume', 'Strong momentum', 'Clear trend'],
        performance: {
          win_rate: 72,
          avg_return: 1.8,
          max_drawdown: -5.2,
          trades_24h: 45
        },
        signals: {
          entry: 'RSI divergence + volume spike',
          exit: 'Momentum reversal or 2% target',
          stop_loss: '1.5% from entry'
        },
        active: false
      },
      {
        id: 'sentiment_rider',
        name: 'Sentiment Momentum Rider',
        description: 'Combines social sentiment with technical analysis for medium-term trades',
        type: 'balanced',
        confidence: 78,
        expected_return: '8-15%',
        risk_level: 'medium',
        timeframe: '1-4 hours',
        conditions: ['Positive sentiment shift', 'Technical confirmation', 'Volume support'],
        performance: {
          win_rate: 68,
          avg_return: 3.2,
          max_drawdown: -8.1,
          trades_24h: 12
        },
        signals: {
          entry: 'Sentiment score > 0.6 + breakout',
          exit: 'Sentiment reversal or profit target',
          stop_loss: '2.5% from entry'
        },
        active: true
      },
      {
        id: 'whale_follower',
        name: 'Whale Movement Tracker',
        description: 'Follows large wallet movements and exchange flows for position sizing',
        type: 'conservative',
        confidence: 71,
        expected_return: '5-12%',
        risk_level: 'low',
        timeframe: '4-24 hours',
        conditions: ['Large whale transactions', 'Exchange flow changes', 'Technical support'],
        performance: {
          win_rate: 75,
          avg_return: 2.1,
          max_drawdown: -3.8,
          trades_24h: 6
        },
        signals: {
          entry: 'Whale accumulation + technical setup',
          exit: 'Whale distribution or target hit',
          stop_loss: '2% from entry'
        },
        active: false
      }
    ];

    setStrategies(sampleStrategies);
    setActiveStrategy(sampleStrategies.find(s => s.active));
    generateAIInsights();
  }, []);

  const generateAIInsights = () => {
    setIsGenerating(true);
    
    // Simulate AI insight generation
    setTimeout(() => {
      const insights = [
        {
          id: 1,
          type: 'opportunity',
          title: 'Bullish Momentum Building',
          description: 'AI detects accumulation pattern with 73% probability of upward movement in next 2-4 hours',
          confidence: 73,
          action: 'Consider increasing position size',
          timestamp: new Date().toISOString()
        },
        {
          id: 2,
          type: 'warning',
          title: 'Whale Distribution Alert',
          description: 'Large wallet showing distribution pattern. Reduce risk exposure.',
          confidence: 81,
          action: 'Implement tighter stop losses',
          timestamp: new Date(Date.now() - 15 * 60000).toISOString()
        },
        {
          id: 3,
          type: 'strategy',
          title: 'Optimal Entry Window',
          description: 'Technical indicators align for optimal entry in next 30 minutes',
          confidence: 67,
          action: 'Prepare for position entry',
          timestamp: new Date(Date.now() - 30 * 60000).toISOString()
        }
      ];
      
      setAiInsights(insights);
      setIsGenerating(false);
    }, 2000);
  };

  const toggleStrategy = (strategyId) => {
    setStrategies(prev => prev.map(strategy => ({
      ...strategy,
      active: strategy.id === strategyId ? !strategy.active : strategy.active
    })));
    
    const strategy = strategies.find(s => s.id === strategyId);
    if (strategy && !strategy.active) {
      setActiveStrategy(strategy);
    }
  };

  const getStrategyTypeColor = (type) => {
    switch (type) {
      case 'aggressive': return 'text-red-400 bg-red-400/20 border-red-400';
      case 'balanced': return 'text-yellow-400 bg-yellow-400/20 border-yellow-400';
      case 'conservative': return 'text-green-400 bg-green-400/20 border-green-400';
      default: return 'text-gray-400 bg-gray-400/20 border-gray-400';
    }
  };

  const getRiskColor = (risk) => {
    switch (risk) {
      case 'high': return 'text-red-400';
      case 'medium': return 'text-yellow-400';
      case 'low': return 'text-green-400';
      default: return 'text-gray-400';
    }
  };

  const getInsightIcon = (type) => {
    switch (type) {
      case 'opportunity': return <TrendingUp className="h-5 w-5 text-green-400" />;
      case 'warning': return <TrendingDown className="h-5 w-5 text-red-400" />;
      case 'strategy': return <Lightbulb className="h-5 w-5 text-yellow-400" />;
      default: return <Brain className="h-5 w-5 text-blue-400" />;
    }
  };

  const StrategyCard = ({ strategy }) => (
    <div className={`bg-gray-800 rounded-lg p-6 border-2 transition-all cursor-pointer ${
      strategy.active ? 'border-crypto-blue glow-blue' : 'border-gray-700 hover:border-gray-600'
    }`}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center space-x-3 mb-2">
            <h3 className="text-lg font-semibold text-white">{strategy.name}</h3>
            <div className={`px-2 py-1 rounded text-xs font-medium border ${getStrategyTypeColor(strategy.type)}`}>
              {strategy.type.toUpperCase()}
            </div>
          </div>
          <p className="text-gray-400 text-sm mb-3">{strategy.description}</p>
        </div>
        <button
          onClick={() => toggleStrategy(strategy.id)}
          className={`p-2 rounded-lg transition-colors ${
            strategy.active 
              ? 'bg-crypto-blue text-white' 
              : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
          }`}
        >
          {strategy.active ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className="text-center">
          <p className="text-gray-400 text-xs">Confidence</p>
          <p className="text-lg font-bold text-crypto-blue">{strategy.confidence}%</p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Win Rate</p>
          <p className="text-lg font-bold text-green-400">{strategy.performance.win_rate}%</p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Risk Level</p>
          <p className={`text-lg font-bold ${getRiskColor(strategy.risk_level)}`}>
            {strategy.risk_level.toUpperCase()}
          </p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Timeframe</p>
          <p className="text-lg font-bold text-white">{strategy.timeframe}</p>
        </div>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-400">Expected Return:</span>
          <span className="text-white font-medium">{strategy.expected_return}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">24h Trades:</span>
          <span className="text-white font-medium">{strategy.performance.trades_24h}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Max Drawdown:</span>
          <span className="text-red-400 font-medium">{strategy.performance.max_drawdown}%</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Active Strategy Banner */}
      {activeStrategy && (
        <div className="bg-gradient-to-r from-crypto-blue/20 to-crypto-purple/20 border-2 border-crypto-blue/30 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="p-3 rounded-lg bg-crypto-blue/20">
                <Brain className="h-8 w-8 text-crypto-blue" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white">Active Strategy</h2>
                <p className="text-crypto-blue font-medium">{activeStrategy.name}</p>
                <p className="text-gray-400 text-sm">{activeStrategy.description}</p>
              </div>
            </div>
            <div className="text-right">
              <div className="flex items-center space-x-2 text-green-400 mb-1">
                <div className="w-3 h-3 rounded-full bg-green-400 animate-pulse"></div>
                <span className="font-medium">RUNNING</span>
              </div>
              <p className="text-gray-400 text-sm">Win Rate: {activeStrategy.performance.win_rate}%</p>
            </div>
          </div>
        </div>
      )}

      {/* AI Insights */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center space-x-2">
            <Brain className="h-5 w-5 text-crypto-purple" />
            <span>AI Insights</span>
          </h3>
          <button
            onClick={generateAIInsights}
            disabled={isGenerating}
            className="px-4 py-2 bg-crypto-purple/20 text-crypto-purple rounded-lg hover:bg-crypto-purple/30 transition-colors disabled:opacity-50"
          >
            {isGenerating ? (
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 border-2 border-crypto-purple/30 border-t-crypto-purple rounded-full animate-spin"></div>
                <span>Generating...</span>
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <Zap className="h-4 w-4" />
                <span>Refresh Insights</span>
              </div>
            )}
          </button>
        </div>

        <div className="space-y-3">
          {aiInsights.map((insight) => (
            <div key={insight.id} className="p-4 bg-gray-700 rounded-lg">
              <div className="flex items-start space-x-3">
                {getInsightIcon(insight.type)}
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-medium text-white">{insight.title}</h4>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs text-gray-400">
                        {Math.floor((Date.now() - new Date(insight.timestamp)) / 60000)}m ago
                      </span>
                      <span className="text-xs bg-crypto-blue/20 text-crypto-blue px-2 py-1 rounded">
                        {insight.confidence}% confidence
                      </span>
                    </div>
                  </div>
                  <p className="text-gray-300 text-sm mb-2">{insight.description}</p>
                  <p className="text-crypto-blue text-sm font-medium">💡 {insight.action}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Strategy Library */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
          <BarChart3 className="h-5 w-5 text-crypto-blue" />
          <span>AI Strategy Library</span>
        </h3>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {strategies.map((strategy) => (
            <StrategyCard key={strategy.id} strategy={strategy} />
          ))}
        </div>
      </div>

      {/* Strategy Performance */}
      {activeStrategy && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">Strategy Performance Details</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium text-white mb-3">Trading Signals</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Entry Signal:</span>
                  <span className="text-green-400">{activeStrategy.signals.entry}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Exit Signal:</span>
                  <span className="text-red-400">{activeStrategy.signals.exit}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Stop Loss:</span>
                  <span className="text-yellow-400">{activeStrategy.signals.stop_loss}</span>
                </div>
              </div>
            </div>

            <div>
              <h4 className="font-medium text-white mb-3">Required Conditions</h4>
              <div className="space-y-2">
                {activeStrategy.conditions.map((condition, index) => (
                  <div key={index} className="flex items-center space-x-2">
                    <div className="w-2 h-2 rounded-full bg-crypto-blue"></div>
                    <span className="text-gray-300 text-sm">{condition}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIStrategies;