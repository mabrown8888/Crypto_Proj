
# Project Overview

This project is an AI-powered cryptocurrency trading dashboard that extends an existing trading bot with advanced features. It provides a user-friendly interface to monitor the bot's performance, analyze market sentiment, track large transactions (whale movements), and even control the bot using voice commands.

## Key Features

- **Real-time Trading Dashboard**: Monitors the bot's signals, trades, and performance.
- **AI-Powered Sentiment Analysis**: Tracks market sentiment from social media and news sources.
- **Whale Movement Tracker**: Monitors large cryptocurrency transactions and exchange flows.
- **AI Strategy Generator**: Provides multiple AI-driven trading strategies with performance metrics.
- **Voice Command Interface**: Allows users to control the trading bot using voice commands.

## How to Run the Project

### Prerequisites

- Node.js 18+ and npm
- Python 3.8+
- Coinbase Advanced Trade API credentials

### Installation and Setup

1. **Automated Setup**: Run the `setup.sh` script to install dependencies.
2. **Environment Configuration**: Create a `.env` file in the project root and add your Coinbase API key and secret.
   ```
   COINBASE_API_KEY=your_api_key_here
   COINBASE_API_SECRET=your_private_key_here
   ```

### Running the Application

1. **Start the Backend**:
   ```bash
   cd backend
   python3 app.py
   ```
2. **Start the Frontend**:
   ```bash
   npm start
   ```
3. **Access the Dashboard**: Open your browser and navigate to `http://localhost:3000`.

## Project Structure

- **`backend/`**: Contains the Python Flask backend that handles data aggregation, sentiment analysis, and communication with the trading bot.
- **`src/`**: Contains the React frontend, including all components, services, and styles.
- **`coinbase_trading_bot.py`**: The core trading bot logic.
- **`setup.sh`**: The setup script for easy installation.
- **`start.sh`**: A script to start the application.
- **`.env`**: The file for storing API keys and other environment variables.
