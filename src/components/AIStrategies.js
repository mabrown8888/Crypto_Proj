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
    fetchStrategies();
    generateAIInsights();
  }, []);

  const fetchStrategies = async () => {
    try {
      const response = await fetch('http://localhost:5001/api/strategies');
      const data = await response.json();
      if (data.success) {
        setStrategies(data.strategies);
        setActiveStrategy(data.strategies.find(s => s.active));
      }
    } catch (error) {
      console.error("Error fetching strategies:", error);
    }
  };

  const generateAIInsights = async () => {
    setIsGenerating(true);
    try {
      const response = await fetch('http://localhost:5001/api/insights');
      const data = await response.json();
      if (data.success) {
        setAiInsights(data.insights);
      }
    } catch (error) {
      console.error("Error fetching insights:", error);
    }
    setIsGenerating(false);
  };

  const toggleStrategy = async (strategyId) => {
    const strategy = strategies.find(s => s.id === strategyId);
    if (!strategy) return;

    const newActiveState = !strategy.active;

    try {
      const response = await fetch('http://localhost:5001/api/strategies/active', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ strategy_id: newActiveState ? strategyId : null }),
      });
      const data = await response.json();
      if (data.success) {
        setStrategies(prev => prev.map(s => (
          s.id === strategyId ? { ...s, active: newActiveState } : { ...s, active: false }
        )));
        setActiveStrategy(newActiveState ? strategy : null);
      }
    } catch (error) {
      console.error("Error setting active strategy:", error);
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