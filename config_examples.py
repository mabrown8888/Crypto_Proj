# Coinbase Trading Bot Configuration Guide
# This file contains example configurations and explanations

import os
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class TradingConfig:
    """
    Comprehensive trading configuration class
    Modify these values according to your risk tolerance and trading strategy
    """

    # ===== API CREDENTIALS =====
    # SECURITY NOTE: Never commit real API keys to version control
    # Use environment variables or a separate config file that's not tracked
    api_key: str = os.getenv('COINBASE_API_KEY', 'your_api_key_here')
    api_secret: str = os.getenv('COINBASE_API_SECRET', 'your_api_secret_here')

    # ===== TRADING PAIR CONFIGURATION =====
    base_currency: str = "BTC"          # Currency to trade
    quote_currency: str = "USDC"        # Currency to trade against

    # ===== RISK MANAGEMENT =====
    trade_amount_usd: float = 100.0     # Amount per trade in USD
    max_position_size: float = 1000.0   # Maximum total position size
    stop_loss_percentage: float = 2.0   # Stop loss as % of entry price
    take_profit_percentage: float = 3.0 # Take profit as % of entry price
    risk_per_trade_percent: float = 1.0 # Risk per trade as % of portfolio
    max_daily_trades: int = 10          # Maximum trades per day

    # ===== TECHNICAL INDICATORS =====
    # RSI Settings
    rsi_period: int = 14
    rsi_oversold: int = 30              # RSI level for oversold condition
    rsi_overbought: int = 70            # RSI level for overbought condition

    # Moving Average Settings
    sma_short_period: int = 12          # Short-term moving average period
    sma_long_period: int = 26           # Long-term moving average period

    # Bollinger Bands Settings
    bb_period: int = 20
    bb_std_dev: int = 2

    # ===== TIMING CONFIGURATION =====
    check_interval: int = 300           # Check market every 5 minutes (300 seconds)
    data_refresh_interval: int = 60     # Refresh data every minute

    # ===== TRADING STRATEGY =====
    # Signal confirmation requirements
    min_signal_strength: int = 2        # Minimum number of confirming indicators

    # Strategy weights (for multi-indicator strategies)
    strategy_weights: Dict[str, float] = None

    def __post_init__(self):
        if self.strategy_weights is None:
            self.strategy_weights = {
                'moving_average': 1.0,
                'rsi': 1.0,
                'bollinger_bands': 0.8,
                'volume': 0.5
            }

# ===== ENVIRONMENT-SPECIFIC CONFIGURATIONS =====

class DevelopmentConfig(TradingConfig):
    """Configuration for development/testing"""
    trade_amount_usd: float = 10.0      # Smaller trades for testing
    max_daily_trades: int = 3
    check_interval: int = 60            # Check more frequently for testing

class ProductionConfig(TradingConfig):
    """Configuration for live trading"""
    trade_amount_usd: float = 100.0
    max_daily_trades: int = 10
    check_interval: int = 300

class ConservativeConfig(TradingConfig):
    """Conservative trading configuration"""
    trade_amount_usd: float = 50.0
    stop_loss_percentage: float = 1.5
    take_profit_percentage: float = 2.0
    risk_per_trade_percent: float = 0.5
    max_daily_trades: int = 5
    min_signal_strength: int = 3        # Require more confirmation

class AggressiveConfig(TradingConfig):
    """Aggressive trading configuration"""
    trade_amount_usd: float = 200.0
    stop_loss_percentage: float = 3.0
    take_profit_percentage: float = 5.0
    risk_per_trade_percent: float = 2.0
    max_daily_trades: int = 20
    min_signal_strength: int = 1

# ===== SECURITY BEST PRACTICES =====
"""
IMPORTANT SECURITY NOTES:

1. API Key Management:
   - Never hardcode API keys in your source code
   - Use environment variables or secure configuration files
   - Set API key permissions to "Trade" only (no withdraw permissions)
   - Enable IP whitelisting for your API keys
   - Regularly rotate your API keys

2. Risk Management:
   - Start with small amounts while testing
   - Never risk more than you can afford to lose
   - Set conservative stop losses
   - Monitor your bot's performance regularly
   - Have a kill switch to stop trading immediately

3. Environment Setup:
   - Use a virtual environment for Python dependencies
   - Keep your bot updated with latest security patches
   - Run on a secure, dedicated server if possible
   - Enable 2FA on your Coinbase account

4. Testing:
   - Thoroughly test with small amounts first
   - Use paper trading or simulation mode when available
   - Backtest your strategies before live deployment
   - Monitor logs and performance metrics continuously

5. Compliance:
   - Understand tax implications of algorithmic trading
   - Comply with your local financial regulations
   - Keep detailed records of all trades
   - Consult with financial advisors as needed
"""

# ===== EXAMPLE USAGE =====
def get_config(environment: str = 'development') -> TradingConfig:
    """
    Get configuration based on environment

    Args:
        environment: 'development', 'production', 'conservative', or 'aggressive'

    Returns:
        TradingConfig instance
    """
    configs = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'conservative': ConservativeConfig,
        'aggressive': AggressiveConfig
    }

    config_class = configs.get(environment, DevelopmentConfig)
    return config_class()

# Example of loading configuration
if __name__ == "__main__":
    # Load development configuration
    config = get_config('development')
    print(f"Trading pair: {config.base_currency}-{config.quote_currency}")
    print(f"Trade amount: ${config.trade_amount_usd}")
    print(f"Check interval: {config.check_interval} seconds")
