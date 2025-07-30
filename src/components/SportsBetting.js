import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { 
  TrendingUp, 
  TrendingDown, 
  Target, 
  Brain, 
  RefreshCw,
  Calendar,
  Trophy,
  AlertCircle,
  CheckCircle,
  Star,
  DollarSign,
  BarChart3,
  Activity
} from 'lucide-react';

const SportsBetting = () => {
  const [games, setGames] = useState([]);
  const [aiAnalysis, setAiAnalysis] = useState({});
  const [loading, setLoading] = useState(false);
  const [selectedSport, setSelectedSport] = useState('all');
  const [confidence, setConfidence] = useState('high');

  useEffect(() => {
    fetchGamesAndAnalysis();
  }, [selectedSport, confidence]);

  const fetchGamesAndAnalysis = async () => {
    setLoading(true);
    try {
      const response = await fetch(`http://localhost:5001/api/sports-analysis?sport=${selectedSport}&confidence=${confidence}`);
      const data = await response.json();
      
      if (data.success) {
        setGames(data.games);
        setAiAnalysis(data.analysis);
      }
    } catch (error) {
      console.error('Error fetching sports analysis:', error);
    }
    setLoading(false);
  };

  const getConfidenceColor = (conf) => {
    if (conf >= 80) return 'text-green-400 bg-green-400/20';
    if (conf >= 60) return 'text-yellow-400 bg-yellow-400/20';
    return 'text-red-400 bg-red-400/20';
  };

  const getBetTypeIcon = (type) => {
    switch (type) {
      case 'moneyline': return <Target className="h-4 w-4" />;
      case 'spread': return <TrendingUp className="h-4 w-4" />;
      case 'over_under': return <BarChart3 className="h-4 w-4" />;
      default: return <Activity className="h-4 w-4" />;
    }
  };

  const GameCard = ({ game }) => {
    const analysis = aiAnalysis[game.id] || {};
    const recommendation = analysis.recommendation || {};
    
    return (
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 hover:border-gray-600 transition-colors">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-crypto-blue/20">
              <Trophy className="h-5 w-5 text-crypto-blue" />
            </div>
            <div>
              <h3 className="font-semibold text-white">{game.away_team} @ {game.home_team}</h3>
              <p className="text-sm text-gray-400">{game.sport} • {new Date(game.time).toLocaleDateString()}</p>
            </div>
          </div>
          <div className={`px-3 py-1 rounded-full text-xs font-medium ${getConfidenceColor(analysis.confidence || 0)}`}>
            {analysis.confidence || 0}% Confidence
          </div>
        </div>

        {/* AI Recommendation */}
        {recommendation.bet && (
          <div className="mb-4 p-4 bg-crypto-blue/10 rounded-lg border border-crypto-blue/20">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <Brain className="h-5 w-5 text-crypto-blue" />
                <span className="font-medium text-white">AI Recommendation</span>
              </div>
              <div className="flex items-center space-x-1">
                {getBetTypeIcon(recommendation.type)}
                <span className="text-sm text-gray-300">{recommendation.type}</span>
              </div>
            </div>
            <p className="text-crypto-blue font-medium">{recommendation.bet}</p>
            <p className="text-sm text-gray-300 mt-1">{recommendation.reasoning}</p>
            
            {recommendation.value && (
              <div className="flex items-center space-x-4 mt-3 text-sm">
                <span className="text-green-400">Expected Value: +{recommendation.value}%</span>
                <span className="text-gray-400">Risk Level: {recommendation.risk}</span>
              </div>
            )}
          </div>
        )}

        {/* Odds and Stats */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="bg-gray-700 rounded-lg p-3">
            <h4 className="text-sm font-medium text-gray-300 mb-2">Moneyline Odds</h4>
            <div className="space-y-1">
              <div className="flex justify-between">
                <span className="text-white">{game.away_team}</span>
                <span className="text-crypto-green">{game.odds?.away || 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white">{game.home_team}</span>
                <span className="text-crypto-green">{game.odds?.home || 'N/A'}</span>
              </div>
            </div>
          </div>

          <div className="bg-gray-700 rounded-lg p-3">
            <h4 className="text-sm font-medium text-gray-300 mb-2">Betting Percentages</h4>
            <div className="space-y-1">
              <div className="flex justify-between">
                <span className="text-white">Public %</span>
                <span className="text-yellow-400">{analysis.public_percentage || 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white">Sharp %</span>
                <span className="text-blue-400">{analysis.sharp_percentage || 'N/A'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* AI Analysis Factors */}
        {analysis.factors && (
          <div className="mb-4">
            <h4 className="text-sm font-medium text-gray-300 mb-2">Analysis Factors</h4>
            <div className="flex flex-wrap gap-2">
              {analysis.factors.map((factor, index) => (
                <span key={index} className="px-2 py-1 bg-gray-700 text-xs rounded text-gray-300">
                  {factor}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex space-x-3">
          <button className="flex-1 py-2 px-4 bg-crypto-green/20 text-crypto-green rounded-lg hover:bg-crypto-green/30 transition-colors text-sm font-medium">
            Place Bet
          </button>
          <button className="flex-1 py-2 px-4 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors text-sm font-medium">
            More Details
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">AI Sports Betting Analysis</h1>
          <p className="text-gray-400">AI-powered recommendations based on statistics and betting percentages</p>
        </div>
        <button
          onClick={fetchGamesAndAnalysis}
          disabled={loading}
          className="flex items-center space-x-2 px-4 py-2 bg-crypto-blue rounded-lg hover:bg-crypto-blue/80 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          <span>{loading ? 'Analyzing...' : 'Refresh'}</span>
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center space-x-4 p-4 bg-gray-800 rounded-lg">
        <div className="flex items-center space-x-2">
          <Calendar className="h-4 w-4 text-gray-400" />
          <span className="text-sm text-gray-300">Today's Games</span>
        </div>
        
        <select
          value={selectedSport}
          onChange={(e) => setSelectedSport(e.target.value)}
          className="bg-gray-700 text-white px-3 py-2 rounded-lg border border-gray-600 focus:border-crypto-blue focus:outline-none"
        >
          <option value="all">All Sports</option>
          <option value="nfl">NFL</option>
          <option value="nba">NBA</option>
          <option value="mlb">MLB</option>
          <option value="nhl">NHL</option>
          <option value="soccer">Soccer</option>
        </select>

        <select
          value={confidence}
          onChange={(e) => setConfidence(e.target.value)}
          className="bg-gray-700 text-white px-3 py-2 rounded-lg border border-gray-600 focus:border-crypto-blue focus:outline-none"
        >
          <option value="all">All Confidence</option>
          <option value="high">High (80%+)</option>
          <option value="medium">Medium (60%+)</option>
          <option value="low">Low (&lt;60%)</option>
        </select>
      </div>

      {/* AI Summary */}
      {aiAnalysis.summary && (
        <div className="bg-gradient-to-r from-crypto-purple/20 to-crypto-blue/20 border border-crypto-purple/30 rounded-lg p-6">
          <div className="flex items-center space-x-3 mb-4">
            <Brain className="h-6 w-6 text-crypto-purple" />
            <h2 className="text-xl font-bold text-white">Today's AI Summary</h2>
          </div>
          <p className="text-gray-300 mb-4">{aiAnalysis.summary}</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-green-400">{aiAnalysis.high_confidence_bets || 0}</div>
              <div className="text-sm text-gray-400">High Confidence Bets</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-crypto-blue">{aiAnalysis.avg_confidence || 0}%</div>
              <div className="text-sm text-gray-400">Average Confidence</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-crypto-yellow">{aiAnalysis.total_value || 0}%</div>
              <div className="text-sm text-gray-400">Total Expected Value</div>
            </div>
          </div>
        </div>
      )}

      {/* Games Grid */}
      {loading ? (
        <div className="text-center py-12">
          <RefreshCw className="h-8 w-8 animate-spin text-crypto-blue mx-auto mb-4" />
          <p className="text-gray-400">AI is analyzing today's games...</p>
        </div>
      ) : games.length === 0 ? (
        <div className="text-center py-12">
          <AlertCircle className="h-8 w-8 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-400">No games found for selected criteria</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {games.map((game) => (
            <GameCard key={game.id} game={game} />
          ))}
        </div>
      )}
    </div>
  );
};

export default SportsBetting;
