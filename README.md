# 🤖 AI Trading Co-Pilot

An advanced cryptocurrency trading dashboard that extends your existing trading bot with AI-powered features, real-time sentiment analysis, whale tracking, and voice commands.

## ✨ Features

### 🎯 Core Features
- **Real-time Trading Dashboard** - Monitor your bot's performance, signals, and trades
- **Market Sentiment Analysis** - AI-powered sentiment tracking from social media and news
- **Whale Movement Tracker** - Monitor large transactions and exchange flows
- **AI Strategy Generator** - Multiple AI trading strategies with performance metrics
- **Voice Command Interface** - Control your trading bot with voice commands

### 🔧 Technical Features
- **Real-time Updates** - WebSocket connections for live data
- **Integration with Existing Bot** - Works with your `coinbase_trading_bot.py`
- **Responsive Design** - Modern, crypto-themed UI with dark mode
- **Security** - Environment-based API key management
- **Extensible** - Modular architecture for easy feature additions

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ and npm
- Python 3.8+
- Coinbase Advanced Trade API credentials

### Installation

1. **Clone and setup**
   ```bash
   # Run the automated setup
   ./setup.sh
   ```

2. **Configure environment**
   ```bash
   # Your .env file should already contain:
   COINBASE_API_KEY=your_api_key_here
   COINBASE_API_SECRET=your_private_key_here
   ```

3. **Start the application**
   ```bash
   # Terminal 1: Start backend
   cd backend
   python3 app.py
   
   # Terminal 2: Start frontend  
   npm start
   ```

4. **Open your browser**
   ```
   http://localhost:3000
   ```

## 📊 Dashboard Overview

### Trading Dashboard
- **Live Price Chart** - Real-time BTC price with technical indicators
- **Bot Status** - Connection status and trading signals
- **Portfolio Metrics** - Balance, P&L, and trade statistics
- **Technical Indicators** - RSI, Moving Averages, Bollinger Bands

### Sentiment Analysis
- **Fear & Greed Index** - Real-time market psychology gauge
- **Social Metrics** - Twitter mentions, Reddit posts, news articles
- **AI Insights** - Sentiment-based trading recommendations
- **Trending Topics** - Popular crypto hashtags and discussions

### Whale Tracker
- **Large Transactions** - Monitor 100+ BTC movements
- **Exchange Flows** - Track deposits/withdrawals from major exchanges
- **Whale Alerts** - Real-time notifications for significant movements
- **Top Wallets** - Monitor largest Bitcoin holders

### AI Strategies
- **Strategy Library** - Pre-built AI trading strategies
- **Performance Metrics** - Win rates, returns, and risk analysis
- **Real-time Execution** - Activate/deactivate strategies
- **Custom Insights** - AI-generated trading recommendations

### Voice Commands
- **Natural Language** - Speak commands naturally
- **Trading Control** - "Buy Bitcoin", "Sell Bitcoin", "Stop trading"
- **Status Queries** - "Show status", "What's the price?"
- **Audio Feedback** - Spoken confirmations and responses

## 🎯 Voice Commands

| Command | Description |
|---------|-------------|
| "buy bitcoin" | Execute a buy order |
| "sell bitcoin" | Execute a sell order |
| "show status" | Display bot status |
| "stop trading" | Stop the trading bot |
| "show price" | Get current BTC price |
| "show portfolio" | Display portfolio value |
| "emergency stop" | Emergency halt all trading |
| "show sentiment" | Get market sentiment |
| "whale alert" | Check whale movements |

## 🔧 Configuration

### Trading Bot Integration
The dashboard automatically connects to your existing `coinbase_trading_bot.py`. Make sure:
- Your bot is running with the same API credentials
- The bot uses the same `.env` file for consistency
- WebSocket connections are enabled for real-time updates

### API Configuration
```env
# Coinbase Advanced Trade API
COINBASE_API_KEY=organizations/xxx/apiKeys/xxx
COINBASE_API_SECRET=-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----

# Optional: External APIs for enhanced features
TWITTER_API_KEY=your_twitter_api_key
NEWS_API_KEY=your_news_api_key
```

### Customization
- **Trading Parameters** - Modify in `coinbase_trading_bot.py`
- **UI Theme** - Customize colors in `tailwind.config.js`
- **AI Strategies** - Add new strategies in `AIStrategies.js`
- **Voice Commands** - Extend commands in `VoiceCommands.js`

## 📈 Performance

### Optimized for Speed
- **30-second updates** - Fast response to market changes
- **Efficient data handling** - Minimal API calls with caching
- **Real-time WebSockets** - Instant updates without polling
- **Responsive UI** - Smooth animations and interactions

### Resource Usage
- **Frontend** - ~50MB RAM, minimal CPU
- **Backend** - ~100MB RAM, low CPU
- **Trading Bot** - Existing resource usage unchanged

## 🛡️ Security

### API Security
- Environment-based credential storage
- No hardcoded API keys in source code
- Secure WebSocket connections
- Input validation and sanitization

### Trading Safety
- Confirmation dialogs for voice commands
- Emergency stop functionality
- Rate limiting on API calls
- Position size limits and risk management

## 🎨 Technology Stack

### Frontend
- **React 18** - Modern component-based UI
- **Tailwind CSS** - Responsive, crypto-themed design
- **Chart.js** - Real-time price charts
- **Web Speech API** - Voice recognition and synthesis
- **WebSocket Client** - Real-time data connections

### Backend
- **Flask** - Python web framework
- **Socket.IO** - Real-time bidirectional communication
- **Requests** - HTTP client for external APIs
- **Threading** - Concurrent data processing

### External Integrations
- **Coinbase Advanced Trade API** - Trading and market data
- **Alternative.me API** - Fear & Greed Index
- **CoinGecko API** - Additional price data
- **Social Media APIs** - Sentiment analysis data

## 🔄 Data Flow

1. **Trading Bot** → Generates signals and executes trades
2. **Backend API** → Aggregates data from bot + external sources
3. **WebSocket** → Streams real-time updates to frontend
4. **Frontend** → Displays data and handles user interactions
5. **Voice Interface** → Processes commands and sends to backend

## 🐛 Troubleshooting

### Common Issues

**Backend won't start**
```bash
# Check Python dependencies
pip3 install -r backend/requirements.txt

# Verify .env file exists and has correct format
cat .env
```

**Frontend build fails**
```bash
# Clear npm cache and reinstall
npm cache clean --force
rm -rf node_modules
npm install
```

**Voice commands not working**
- Enable microphone permissions in browser
- Use HTTPS in production (required for Web Speech API)
- Check browser compatibility (Chrome/Edge recommended)

**Trading bot connection issues**
- Verify API credentials in `.env`
- Check Coinbase API key permissions
- Ensure bot and dashboard use same credentials

### Debug Mode
```bash
# Backend with debug logging
cd backend
python3 app.py --debug

# Frontend with verbose logging
npm start -- --verbose
```

## 🚧 Development

### Adding New Features
1. **Backend** - Add new endpoints in `backend/app.py`
2. **Frontend** - Create new components in `src/components/`
3. **Integration** - Update WebSocket handlers for real-time data
4. **Testing** - Test with your trading bot running

### Contributing
- Follow existing code structure and naming conventions
- Add comments for complex logic
- Test all features with real trading bot
- Update documentation for new features

## 📜 License

This project is provided as-is for educational and personal use. Trading cryptocurrency involves significant risk. Use at your own risk.

## 🆘 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review your trading bot logs
3. Verify API credentials and permissions
4. Test with minimal configuration first

---

**⚠️ Risk Warning**: Cryptocurrency trading involves substantial risk. This software is for educational purposes. Never risk more than you can afford to lose.