import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  Brain, 
  Twitter, 
  MessageCircle, 
  Hash,
  Gauge,
  Activity,
  Newspaper,
  BarChart3,
  Target,
  AlertTriangle,
  ExternalLink,
  Clock
} from 'lucide-react';

const SentimentAnalysis = () => {
  const [sentimentData, setSentimentData] = useState({
    overall_sentiment: 'neutral',
    sentiment_score: 0.0,
    social_volume: 1250,
    fear_greed_index: 42,
    trending_topics: ['#Bitcoin', '#BTC', '#Crypto', '#DeFi', '#Trading'],
    social_metrics: {
      twitter_mentions: 15420,
      reddit_posts: 892,
      news_articles: 156,
      sentiment_change_24h: 5.2
    },
    news_sentiment: {
      articles: [],
      average_sentiment: 0.0,
      positive_count: 0,
      negative_count: 0,
      neutral_count: 0
    },
    social_sentiment: {
      twitter_sentiment: 0.0,
      reddit_sentiment: 0.0,
      mentions_24h: 0,
      trending_hashtags: []
    },
    market_indicators: {
      volatility_index: 0.0,
      sentiment_vs_price_correlation: 0.0,
      market_momentum: 'neutral'
    },
    trading_signals: {
      sentiment_signal: 'HOLD',
      confidence: 0.0,
      reasoning: ''
    },
    sentiment_history: []
  });

  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Fetch initial sentiment data
    fetchSentimentData();
    
    // Set up real-time updates via WebSocket or periodic fetching
    const interval = setInterval(fetchSentimentData, 30000); // Update every 30 seconds

    setIsLoading(false);
    return () => clearInterval(interval);
  }, []);
  
  const fetchSentimentData = async () => {
    try {
      const response = await fetch('http://localhost:5001/api/sentiment');
      if (response.ok) {
        const data = await response.json();
        setSentimentData(data);
      }
    } catch (error) {
      console.error('Error fetching sentiment data:', error);
    }
  };

  const getSentimentColor = (sentiment) => {
    switch (sentiment) {
      case 'extreme_fear': return 'text-red-500 bg-red-500/20 border-red-500';
      case 'fear': return 'text-orange-500 bg-orange-500/20 border-orange-500';
      case 'neutral': return 'text-yellow-500 bg-yellow-500/20 border-yellow-500';
      case 'greed': return 'text-green-400 bg-green-400/20 border-green-400';
      case 'extreme_greed': return 'text-green-600 bg-green-600/20 border-green-600';
      default: return 'text-gray-400 bg-gray-400/20 border-gray-400';
    }
  };

  const getSentimentLabel = (sentiment) => {
    return sentiment.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  const FearGreedGauge = ({ value }) => {
    const getColor = (val) => {
      if (val < 25) return '#ef4444';
      if (val < 45) return '#f97316';
      if (val < 55) return '#eab308';
      if (val < 75) return '#22c55e';
      return '#16a34a';
    };

    const circumference = 2 * Math.PI * 45;
    const strokeDasharray = `${(value / 100) * circumference} ${circumference}`;

    return (
      <div className="relative w-32 h-32">
        <svg className="w-32 h-32 transform -rotate-90" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r="45"
            stroke="rgba(255,255,255,0.1)"
            strokeWidth="10"
            fill="none"
          />
          <circle
            cx="50"
            cy="50"
            r="45"
            stroke={getColor(value)}
            strokeWidth="10"
            fill="none"
            strokeDasharray={strokeDasharray}
            strokeLinecap="round"
            className="transition-all duration-1000"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <div className="text-2xl font-bold">{value}</div>
            <div className="text-xs text-gray-400">F&G Index</div>
          </div>
        </div>
      </div>
    );
  };

  const MetricCard = ({ title, value, icon: Icon, color, subtitle, change }) => (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-gray-400 text-sm font-medium">{title}</p>
          <p className={`text-2xl font-bold ${color}`}>{value}</p>
          {subtitle && <p className="text-gray-500 text-xs mt-1">{subtitle}</p>}
          {change !== undefined && (
            <div className={`flex items-center space-x-1 mt-2 ${change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {change >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              <span className="text-xs">{change >= 0 ? '+' : ''}{change.toFixed(1)}%</span>
            </div>
          )}
        </div>
        <div className={`p-3 rounded-lg ${color === 'text-crypto-green' ? 'bg-crypto-green/20' : 
                                       color === 'text-crypto-red' ? 'bg-crypto-red/20' : 
                                       'bg-crypto-blue/20'}`}>
          <Icon className={`h-6 w-6 ${color}`} />
        </div>
      </div>
    </div>
  );

  const NewsCard = ({ article }) => (
    <div className="bg-gray-700 rounded-lg p-4 border border-gray-600">
      <div className="flex items-start justify-between mb-2">
        <h4 className="font-medium text-sm leading-tight flex-1">{article.title}</h4>
        <span className={`ml-2 px-2 py-1 rounded text-xs whitespace-nowrap ${
          article.sentiment_score > 0.1 ? 'bg-green-500/20 text-green-400' :
          article.sentiment_score < -0.1 ? 'bg-red-500/20 text-red-400' :
          'bg-yellow-500/20 text-yellow-400'
        }`}>
          {article.sentiment_label}
        </span>
      </div>
      <div className="flex items-center justify-between text-xs text-gray-400">
        <span>{article.source}</span>
        <div className="flex items-center space-x-2">
          <Clock className="h-3 w-3" />
          <span>{new Date(article.published_on).toLocaleDateString()}</span>
          <a href={article.url} target="_blank" rel="noopener noreferrer" className="text-crypto-blue hover:text-blue-400">
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>
    </div>
  );

  const TradingSignalCard = ({ signal, confidence, reasoning }) => {
    const getSignalColor = (sig) => {
      switch (sig) {
        case 'BUY': return 'text-green-400 bg-green-400/20 border-green-400';
        case 'SELL': return 'text-red-400 bg-red-400/20 border-red-400';
        default: return 'text-yellow-400 bg-yellow-400/20 border-yellow-400';
      }
    };

    return (
      <div className={`rounded-lg p-4 border-2 ${getSignalColor(signal)}`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <Target className="h-5 w-5" />
            <span className="font-semibold">Sentiment Signal</span>
          </div>
          <div className="text-right">
            <div className="text-xl font-bold">{signal}</div>
            <div className="text-sm opacity-80">Confidence: {(confidence * 100).toFixed(0)}%</div>
          </div>
        </div>
        <p className="text-sm opacity-90">{reasoning}</p>
      </div>
    );
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
      {/* Overall Sentiment Banner */}
      <div className={`rounded-lg p-6 border-2 ${getSentimentColor(sentimentData.overall_sentiment)}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Brain className="h-8 w-8" />
            <div>
              <h2 className="text-2xl font-bold">{getSentimentLabel(sentimentData.overall_sentiment)}</h2>
              <p className="opacity-80">Overall Market Sentiment</p>
              <p className="text-sm opacity-70">Score: {sentimentData.sentiment_score > 0 ? '+' : ''}{sentimentData.sentiment_score.toFixed(3)}</p>
            </div>
          </div>
          <FearGreedGauge value={sentimentData.fear_greed_index} />
        </div>
      </div>

      {/* Trading Signal */}
      <TradingSignalCard 
        signal={sentimentData.trading_signals.sentiment_signal}
        confidence={sentimentData.trading_signals.confidence}
        reasoning={sentimentData.trading_signals.reasoning}
      />

      {/* Sentiment Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="News Sentiment"
          value={sentimentData.news_sentiment.average_sentiment > 0 ? `+${sentimentData.news_sentiment.average_sentiment.toFixed(3)}` : sentimentData.news_sentiment.average_sentiment.toFixed(3)}
          icon={Newspaper}
          color={sentimentData.news_sentiment.average_sentiment >= 0 ? 'text-crypto-green' : 'text-crypto-red'}
          subtitle={`${sentimentData.news_sentiment.articles.length} articles analyzed`}
        />
        <MetricCard
          title="Social Volume"
          value={sentimentData.social_sentiment.mentions_24h.toLocaleString()}
          icon={MessageCircle}
          color="text-crypto-blue"
          subtitle="mentions in 24h"
        />
        <MetricCard
          title="Market Volatility"
          value={`${sentimentData.market_indicators.volatility_index.toFixed(1)}%`}
          icon={BarChart3}
          color="text-crypto-purple"
          subtitle="price volatility"
        />
        <MetricCard
          title="Market Momentum"
          value={sentimentData.market_indicators.market_momentum.replace('_', ' ')}
          icon={Activity}
          color={
            sentimentData.market_indicators.market_momentum.includes('bullish') ? 'text-crypto-green' :
            sentimentData.market_indicators.market_momentum.includes('bearish') ? 'text-crypto-red' :
            'text-crypto-yellow'
          }
          subtitle="trend direction"
        />
      </div>

      {/* News & Social Sentiment */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent News */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
            <Newspaper className="h-5 w-5" />
            <span>Latest News Sentiment</span>
          </h3>
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {sentimentData.news_sentiment.articles.length > 0 ? (
              sentimentData.news_sentiment.articles.map((article, index) => (
                <NewsCard key={index} article={article} />
              ))
            ) : (
              <p className="text-gray-400 text-sm">Loading news articles...</p>
            )}
          </div>
          {sentimentData.news_sentiment.articles.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-700">
              <div className="flex justify-between text-sm">
                <span className="text-green-400">Positive: {sentimentData.news_sentiment.positive_count}</span>
                <span className="text-yellow-400">Neutral: {sentimentData.news_sentiment.neutral_count}</span>
                <span className="text-red-400">Negative: {sentimentData.news_sentiment.negative_count}</span>
              </div>
            </div>
          )}
        </div>

        {/* Social Media Metrics */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">Social Media Sentiment</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Twitter className="h-5 w-5 text-blue-400" />
                <span>Twitter Sentiment</span>
              </div>
              <span className={`font-bold ${sentimentData.social_sentiment.twitter_sentiment >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {sentimentData.social_sentiment.twitter_sentiment > 0 ? '+' : ''}{sentimentData.social_sentiment.twitter_sentiment.toFixed(3)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <MessageCircle className="h-5 w-5 text-orange-500" />
                <span>Reddit Sentiment</span>
              </div>
              <span className={`font-bold ${sentimentData.social_sentiment.reddit_sentiment >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {sentimentData.social_sentiment.reddit_sentiment > 0 ? '+' : ''}{sentimentData.social_sentiment.reddit_sentiment.toFixed(3)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Activity className="h-5 w-5 text-green-400" />
                <span>Total Mentions</span>
              </div>
              <span className="font-bold">{sentimentData.social_sentiment.mentions_24h.toLocaleString()}</span>
            </div>
          </div>
          
          {/* Correlation Indicator */}
          <div className="mt-4 pt-4 border-t border-gray-700">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">Sentiment-Price Correlation</span>
              <span className={`text-sm font-medium ${
                sentimentData.market_indicators.sentiment_vs_price_correlation > 0.3 ? 'text-green-400' :
                sentimentData.market_indicators.sentiment_vs_price_correlation < -0.3 ? 'text-red-400' :
                'text-yellow-400'
              }`}>
                {sentimentData.market_indicators.sentiment_vs_price_correlation > 0 ? '+' : ''}
                {sentimentData.market_indicators.sentiment_vs_price_correlation.toFixed(3)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Trending Topics */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
          <Hash className="h-5 w-5" />
          <span>Trending Hashtags & Topics</span>
        </h3>
        <div className="flex flex-wrap gap-2">
          {sentimentData.social_sentiment.trending_hashtags.length > 0 ? 
            sentimentData.social_sentiment.trending_hashtags.map((topic, index) => (
              <span
                key={index}
                className="px-3 py-1 bg-crypto-blue/20 text-crypto-blue rounded-full text-sm border border-crypto-blue/30"
              >
                {topic}
              </span>
            )) :
            sentimentData.trending_topics.map((topic, index) => (
              <span
                key={index}
                className="px-3 py-1 bg-crypto-blue/20 text-crypto-blue rounded-full text-sm border border-crypto-blue/30"
              >
                {topic}
              </span>
            ))
          }
        </div>
      </div>

      {/* Advanced Market Indicators */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
          <Brain className="h-5 w-5 text-crypto-purple" />
          <span>Advanced Sentiment Analysis</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <h4 className="font-medium text-crypto-blue">News Sentiment Breakdown</h4>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm">Positive Articles</span>
                <span className="text-green-400">{sentimentData.news_sentiment.positive_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm">Neutral Articles</span>
                <span className="text-yellow-400">{sentimentData.news_sentiment.neutral_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm">Negative Articles</span>
                <span className="text-red-400">{sentimentData.news_sentiment.negative_count}</span>
              </div>
            </div>
          </div>
          
          <div className="space-y-4">
            <h4 className="font-medium text-crypto-blue">Investment Insights</h4>
            <div className="space-y-2 text-sm text-gray-300">
              {sentimentData.fear_greed_index < 30 && (
                <div className="p-3 bg-green-500/10 rounded border border-green-500/20">
                  💡 <strong>Contrarian Opportunity:</strong> Extreme fear may present buying opportunities for long-term investors.
                </div>
              )}
              {sentimentData.fear_greed_index > 70 && (
                <div className="p-3 bg-red-500/10 rounded border border-red-500/20">
                  ⚠️ <strong>Caution:</strong> Extreme greed suggests potential market overextension. Consider taking profits.
                </div>
              )}
              {sentimentData.news_sentiment.average_sentiment > 0.2 && (
                <div className="p-3 bg-blue-500/10 rounded border border-blue-500/20">
                  📈 <strong>Positive News Flow:</strong> Strong positive sentiment in news could support price momentum.
                </div>
              )}
              {sentimentData.news_sentiment.average_sentiment < -0.2 && (
                <div className="p-3 bg-orange-500/10 rounded border border-orange-500/20">
                  📉 <strong>Negative Sentiment:</strong> Bearish news sentiment may create downward pressure on prices.
                </div>
              )}
              {Math.abs(sentimentData.market_indicators.sentiment_vs_price_correlation) > 0.5 && (
                <div className="p-3 bg-purple-500/10 rounded border border-purple-500/20">
                  🔗 <strong>Strong Correlation:</strong> Sentiment and price movements are highly correlated - sentiment changes may predict price moves.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SentimentAnalysis;