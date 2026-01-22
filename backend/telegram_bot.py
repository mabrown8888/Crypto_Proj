#!/usr/bin/env python3
"""
Telegram Bot for Remote Monitoring
Monitor and control your trading bot from your phone!
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# You'll need to create a Telegram bot:
# 1. Message @BotFather on Telegram
# 2. Send /newbot and follow instructions
# 3. Get your bot token
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ALLOWED_USER_IDS = [int(id) for id in os.getenv('ALLOWED_TELEGRAM_USERS', '').split(',') if id]

class TradingBotMonitor:
    def __init__(self):
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.setup_handlers()
        
    def setup_handlers(self):
        """Setup command handlers"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("status", self.status))
        self.app.add_handler(CommandHandler("performance", self.performance))
        self.app.add_handler(CommandHandler("pause", self.pause_bot))
        self.app.add_handler(CommandHandler("resume", self.resume_bot))
        self.app.add_handler(CommandHandler("trades", self.recent_trades))
        self.app.add_handler(CommandHandler("help", self.help))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
    
    def check_authorized(self, user_id):
        """Check if user is authorized"""
        if not ALLOWED_USER_IDS:
            return True  # No restrictions if not configured
        return user_id in ALLOWED_USER_IDS
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        user = update.effective_user
        if not self.check_authorized(user.id):
            await update.message.reply_text("⛔ Unauthorized. Your user ID: " + str(user.id))
            return
            
        keyboard = [
            [InlineKeyboardButton("📊 Status", callback_data='status'),
             InlineKeyboardButton("💰 Performance", callback_data='performance')],
            [InlineKeyboardButton("⏸️ Pause Bot", callback_data='pause'),
             InlineKeyboardButton("▶️ Resume Bot", callback_data='resume')],
            [InlineKeyboardButton("📈 Recent Trades", callback_data='trades')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_msg = (
            "🤖 *Trading Bot Monitor*\n\n"
            f"Welcome {user.first_name}! I'll help you monitor your trading bot.\n\n"
            "Choose an option below or use commands:\n"
            "/status - Current bot status\n"
            "/performance - Trading performance\n"
            "/trades - Recent trades\n"
            "/pause - Pause trading\n"
            "/resume - Resume trading"
        )
        
        await update.message.reply_text(
            welcome_msg,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get bot status"""
        try:
            # Import here to avoid circular imports
            from app import auto_trading_engine
            
            status = auto_trading_engine.get_status()
            price_count = len(auto_trading_engine.price_history)
            latest_price = auto_trading_engine.price_history[-1] if auto_trading_engine.price_history else 0
            
            status_emoji = "🟢" if status['status'] == 'running' else "🔴"
            
            msg = f"""
{status_emoji} *Bot Status*

*Status:* {status['status'].upper()}
*Strategy:* {status['active_strategy'] or 'None'}
*Price Points:* {price_count}
*Latest BTC:* ${latest_price:,.2f}

*Today's Performance:*
• Trades: {status['performance']['totalTrades']}
• P&L: ${status['performance']['todayPnL']:.2f}
• Win Rate: {status['performance']['winRate']:.1f}%
            """
            
            if status.get('current_signal'):
                sig = status['current_signal']
                msg += f"\n*Current Signal:*\n{sig['action']} ({sig['confidence']*100:.0f}% confidence)"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error getting status: {str(e)}")
    
    async def performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get performance metrics"""
        try:
            from app import auto_trading_engine
            
            status = auto_trading_engine.get_status()
            perf = status['performance']
            
            msg = f"""
💰 *Trading Performance*

*Total Trades:* {perf['totalTrades']}
*Profitable:* {perf['profitableTrades']}
*Total P&L:* ${perf['totalPnL']:.2f}
*Today P&L:* ${perf['todayPnL']:.2f}
*Win Rate:* {perf['winRate']:.1f}%

*Risk Settings:*
• Max Daily Loss: $100
• Min Confidence: 60%
• Check Interval: 30s
            """
            
            await update.message.reply_text(msg, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def pause_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pause the bot"""
        try:
            from app import auto_trading_engine
            
            if auto_trading_engine.pause():
                await update.message.reply_text("⏸️ Bot paused successfully")
            else:
                await update.message.reply_text("❌ Failed to pause bot")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def resume_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Resume the bot"""
        try:
            from app import auto_trading_engine
            
            if auto_trading_engine.start():
                await update.message.reply_text("▶️ Bot resumed successfully")
            else:
                await update.message.reply_text("❌ Failed to resume bot")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def recent_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent trades"""
        try:
            from app import auto_trading_engine
            
            trades = auto_trading_engine.get_trading_history(limit=5)
            
            if not trades:
                await update.message.reply_text("📊 No trades yet")
                return
            
            msg = "📈 *Recent Trades*\n\n"
            for trade in trades:
                emoji = "🟢" if trade['pnl'] > 0 else "🔴"
                msg += f"{emoji} {trade['action']} ${trade['amount']:.2f}\n"
                msg += f"   P&L: ${trade['pnl']:.2f}\n"
                msg += f"   {trade['timestamp']}\n\n"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help"""
        help_text = """
🤖 *Trading Bot Commands*

/status - Current bot status
/performance - Trading performance
/trades - Recent trades
/pause - Pause trading
/resume - Resume trading
/help - Show this message

*Auto Alerts:*
• Trade executions
• Daily summary at 9 AM
• Error notifications
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button presses"""
        query = update.callback_query
        await query.answer()
        
        # Map callbacks to functions
        callbacks = {
            'status': self.status,
            'performance': self.performance,
            'trades': self.recent_trades,
            'pause': self.pause_bot,
            'resume': self.resume_bot
        }
        
        handler = callbacks.get(query.data)
        if handler:
            # Create a fake update with message
            fake_update = Update(update_id=update.update_id)
            fake_update._effective_message = query.message
            await handler(fake_update, context)
    
    def run(self):
        """Start the bot"""
        print("🤖 Telegram Bot Started!")
        print(f"Send /start to your bot to begin monitoring")
        self.app.run_polling()

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    bot = TradingBotMonitor()
    bot.run()