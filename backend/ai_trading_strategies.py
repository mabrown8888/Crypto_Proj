#!/usr/bin/env python3
"""
AI Trading Strategies for Automatic Day Trading Bot
"""

import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import requests
from coinbase_jwt import get_coinbase_headers

class SignalStrength(Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"

@dataclass
class TradingSignal:
    action: SignalStrength
    confidence: float  # 0.0 to 1.0
    reason: str
    price: float
    timestamp: datetime
    amount_usd: Optional[float] = None

@dataclass
class StrategyConfig:
    name: str
    description: str
    risk_level: str  # "Conservative", "Moderate", "Aggressive"
    max_trade_amount: float
    max_daily_trades: int
    stop_loss_percent: float
    take_profit_percent: float
    enabled: bool = False

class TradingStrategy:
    """Base class for all trading strategies"""
    
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.trades_today = 0
        self.last_reset_date = datetime.now().date()
        
    def reset_daily_counters(self):
        """Reset daily counters"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.trades_today = 0
            self.last_reset_date = today
            
    def can_trade(self) -> bool:
        """Check if strategy can place more trades today"""
        self.reset_daily_counters()
        return (self.config.enabled and 
                self.trades_today < self.config.max_daily_trades)
    
    def analyze_market(self, price_data: List[float], volume_data: List[float] = None) -> TradingSignal:
        """Analyze market and return trading signal"""
        raise NotImplementedError("Subclasses must implement analyze_market")

class ScalpingStrategy(TradingStrategy):
    """Quick profit scalping strategy - High frequency, small profits"""
    
    def __init__(self):
        config = StrategyConfig(
            name="Lightning Scalper",
            description="High-frequency trading for quick 0.5-1% profits. Makes many small trades throughout the day.",
            risk_level="Aggressive", 
            max_trade_amount=50.0,
            max_daily_trades=20,
            stop_loss_percent=0.3,
            take_profit_percent=0.8
        )
        super().__init__(config)
        self.last_price = None
        self.price_momentum = []
        
    def analyze_market(self, price_data: List[float], volume_data: List[float] = None) -> TradingSignal:
        if len(price_data) < 5:
            return TradingSignal(SignalStrength.HOLD, 0.0, "Insufficient data", price_data[-1], datetime.now())
            
        current_price = price_data[-1]
        price_change_1min = ((current_price - price_data[-2]) / price_data[-2]) * 100 if len(price_data) >= 2 else 0
        price_change_5min = ((current_price - price_data[-5]) / price_data[-5]) * 100 if len(price_data) >= 5 else 0
        
        # Look for quick momentum changes
        if price_change_1min > 0.2 and price_change_5min > 0.1:
            return TradingSignal(
                SignalStrength.BUY, 
                0.8, 
                f"Quick upward momentum: +{price_change_1min:.2f}% (1min), +{price_change_5min:.2f}% (5min)",
                current_price,
                datetime.now(),
                self.config.max_trade_amount
            )
        elif price_change_1min < -0.2 and price_change_5min < -0.1:
            return TradingSignal(
                SignalStrength.SELL,
                0.8,
                f"Quick downward momentum: {price_change_1min:.2f}% (1min), {price_change_5min:.2f}% (5min)",
                current_price,
                datetime.now()
            )
        
        return TradingSignal(SignalStrength.HOLD, 0.3, "No significant momentum", current_price, datetime.now())

class TrendFollowingStrategy(TradingStrategy):
    """Medium-term trend following strategy"""
    
    def __init__(self):
        config = StrategyConfig(
            name="Trend Rider",
            description="Follows medium-term trends using moving averages and momentum indicators. Balanced risk/reward.",
            risk_level="Moderate",
            max_trade_amount=100.0,
            max_daily_trades=8,
            stop_loss_percent=1.5,
            take_profit_percent=3.0
        )
        super().__init__(config)
        
    def calculate_sma(self, prices: List[float], period: int) -> float:
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
        
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        # Use shorter period if not enough data
        period = min(period, len(prices) - 1)
        if len(prices) < 5:  # Need at least 5 prices for basic RSI
            return None
            
        price_changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [change if change > 0 else 0 for change in price_changes]
        losses = [-change if change < 0 else 0 for change in price_changes]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
            
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
        
    def analyze_market(self, price_data: List[float], volume_data: List[float] = None) -> TradingSignal:
        # Reduced from 20 to 10 for faster trading
        if len(price_data) < 10:
            return TradingSignal(SignalStrength.HOLD, 0.0, "Insufficient data for trend analysis", price_data[-1], datetime.now())
            
        current_price = price_data[-1]
        sma_5 = self.calculate_sma(price_data, 5)
        # Use 10-period MA instead of 20 if we don't have enough data
        sma_20 = self.calculate_sma(price_data, min(20, len(price_data)))
        rsi = self.calculate_rsi(price_data)
        
        signals = []
        confidence = 0.5
        
        # Moving average crossover
        if sma_5 and sma_20:
            if sma_5 > sma_20 * 1.002:  # 0.2% above
                signals.append("MA_BULLISH")
                confidence += 0.2
            elif sma_5 < sma_20 * 0.998:  # 0.2% below  
                signals.append("MA_BEARISH")
                confidence += 0.2
                
        # RSI signals (more sensitive)
        if rsi:
            if rsi < 35:  # Was 30, now more sensitive
                signals.append("RSI_OVERSOLD")
                confidence += 0.25
            elif rsi > 65:  # Was 70, now more sensitive
                signals.append("RSI_OVERBOUGHT") 
                confidence += 0.25
                
        # Price momentum
        if len(price_data) >= 10:
            momentum = ((current_price - price_data[-10]) / price_data[-10]) * 100
            if momentum > 2:
                signals.append("STRONG_MOMENTUM_UP")
                confidence += 0.1
            elif momentum < -2:
                signals.append("STRONG_MOMENTUM_DOWN")
                confidence += 0.1
                
        # Generate signal
        bullish_signals = ["MA_BULLISH", "RSI_OVERSOLD", "STRONG_MOMENTUM_UP"]
        bearish_signals = ["MA_BEARISH", "RSI_OVERBOUGHT", "STRONG_MOMENTUM_DOWN"]
        
        bull_count = sum(1 for s in signals if s in bullish_signals)
        bear_count = sum(1 for s in signals if s in bearish_signals)
        
        # More aggressive: Trade with 1 signal if confidence is high enough
        if bull_count >= 2 or (bull_count >= 1 and confidence >= 0.7):
            return TradingSignal(
                SignalStrength.BUY if bull_count == 1 else SignalStrength.STRONG_BUY,
                min(confidence, 0.9),
                f"Trend following BUY: {', '.join(signals)}",
                current_price,
                datetime.now(),
                self.config.max_trade_amount
            )
        elif bear_count >= 2 or (bear_count >= 1 and confidence >= 0.7):
            return TradingSignal(
                SignalStrength.SELL if bear_count == 1 else SignalStrength.STRONG_SELL,
                min(confidence, 0.9),
                f"Trend following SELL: {', '.join(signals)}",
                current_price,
                datetime.now()
            )
            
        return TradingSignal(
            SignalStrength.HOLD, 
            confidence,
            f"Mixed signals: {', '.join(signals) if signals else 'No clear trend'}",
            current_price,
            datetime.now()
        )

class ConservativeStrategy(TradingStrategy):
    """Conservative long-term strategy with tight risk management"""
    
    def __init__(self):
        config = StrategyConfig(
            name="Steady Gains",
            description="Conservative strategy focusing on steady, low-risk gains with strong risk management.",
            risk_level="Conservative",
            max_trade_amount=75.0,
            max_daily_trades=3,
            stop_loss_percent=1.0,
            take_profit_percent=2.5
        )
        super().__init__(config)
        
    def analyze_market(self, price_data: List[float], volume_data: List[float] = None) -> TradingSignal:
        if len(price_data) < 30:
            return TradingSignal(SignalStrength.HOLD, 0.0, "Insufficient data for conservative analysis", price_data[-1], datetime.now())
            
        current_price = price_data[-1]
        
        # Only trade on very strong, confirmed signals
        sma_10 = sum(price_data[-10:]) / 10
        sma_30 = sum(price_data[-30:]) / 30
        
        # Calculate volatility
        price_changes = [abs(price_data[i] - price_data[i-1]) / price_data[i-1] for i in range(1, min(len(price_data), 10))]
        avg_volatility = sum(price_changes) / len(price_changes) * 100
        
        # Only trade in low volatility environments
        if avg_volatility > 3.0:
            return TradingSignal(
                SignalStrength.HOLD,
                0.8,
                f"High volatility ({avg_volatility:.2f}%) - staying safe",
                current_price,
                datetime.now()
            )
            
        # Strong uptrend confirmation needed
        if sma_10 > sma_30 * 1.005 and current_price > sma_10 * 1.002:
            return TradingSignal(
                SignalStrength.BUY,
                0.7,
                f"Conservative BUY: Strong uptrend confirmed, low volatility ({avg_volatility:.2f}%)",
                current_price,
                datetime.now(),
                self.config.max_trade_amount
            )
        elif sma_10 < sma_30 * 0.995 and current_price < sma_10 * 0.998:
            return TradingSignal(
                SignalStrength.SELL,
                0.7,
                f"Conservative SELL: Strong downtrend confirmed, low volatility ({avg_volatility:.2f}%)",
                current_price,
                datetime.now()
            )
            
        return TradingSignal(
            SignalStrength.HOLD,
            0.6,
            f"Conservative HOLD: Waiting for stronger confirmation (vol: {avg_volatility:.2f}%)",
            current_price,
            datetime.now()
        )

class AITradingStrategyManager:
    """Manages multiple AI trading strategies"""
    
    def __init__(self):
        self.strategies = {
            'scalping': ScalpingStrategy(),
            'trend_following': TrendFollowingStrategy(), 
            'conservative': ConservativeStrategy()
        }
        self.active_strategy = None
        self.price_history = []
        self.is_running = False
        
    def get_available_strategies(self) -> List[Dict]:
        """Get list of available strategies"""
        return [
            {
                'id': key,
                'name': strategy.config.name,
                'description': strategy.config.description,
                'risk_level': strategy.config.risk_level,
                'max_trade_amount': strategy.config.max_trade_amount,
                'max_daily_trades': strategy.config.max_daily_trades,
                'stop_loss_percent': strategy.config.stop_loss_percent,
                'take_profit_percent': strategy.config.take_profit_percent,
                'enabled': strategy.config.enabled
            }
            for key, strategy in self.strategies.items()
        ]
        
    def set_active_strategy(self, strategy_id: str) -> bool:
        """Set the active trading strategy"""
        if strategy_id in self.strategies:
            # Disable all strategies first
            for strategy in self.strategies.values():
                strategy.config.enabled = False
                
            # Enable selected strategy
            self.strategies[strategy_id].config.enabled = True
            self.active_strategy = strategy_id
            return True
        return False
        
    def get_trading_signal(self, price_data: List[float]) -> Optional[TradingSignal]:
        """Get trading signal from active strategy"""
        if not self.active_strategy or self.active_strategy not in self.strategies:
            return None
            
        strategy = self.strategies[self.active_strategy]
        if not strategy.can_trade():
            return TradingSignal(
                SignalStrength.HOLD,
                0.0,
                f"Daily trade limit reached ({strategy.trades_today}/{strategy.config.max_daily_trades})",
                price_data[-1] if price_data else 0,
                datetime.now()
            )
            
        return strategy.analyze_market(price_data)
        
    def record_trade(self):
        """Record that a trade was executed"""
        if self.active_strategy and self.active_strategy in self.strategies:
            self.strategies[self.active_strategy].trades_today += 1