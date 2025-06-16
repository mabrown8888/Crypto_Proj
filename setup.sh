#!/bin/bash

echo "🚀 Setting up AI Trading Co-Pilot..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js first."
    exit 1
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

echo "✅ Node.js and Python 3 found"

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
npm install

# Install backend dependencies
echo "📦 Installing backend dependencies..."
cd backend
pip3 install -r requirements.txt
cd ..

# Create necessary directories
mkdir -p logs
mkdir -p data

# Copy environment file template
if [ ! -f ".env" ]; then
    echo "📝 Environment file already exists"
else
    echo "⚠️  Please make sure your .env file is properly configured with your Coinbase API credentials"
fi

echo "🎉 Setup complete!"
echo ""
echo "🚀 To start the application:"
echo "1. Start the backend: cd backend && python3 app.py"
echo "2. Start the frontend: npm start"
echo "3. Open http://localhost:3000 in your browser"
echo ""
echo "📚 Features included:"
echo "✅ Real-time trading dashboard"
echo "✅ Market sentiment analysis"
echo "✅ Whale movement tracking"
echo "✅ AI trading strategies"
echo "✅ Voice command interface"
echo ""
echo "🔧 Make sure your trading bot (coinbase_trading_bot.py) is configured and running!"