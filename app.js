// Trading Bot Dashboard JavaScript
class TradingBotDashboard {
    constructor() {
        this.data = {
            current_price: 67850.32,
            price_change_24h: 2.45,
            bot_status: "active",
            current_position: "long",
            account_balance: 5420.78,
            total_pnl: 342.56,
            total_pnl_percent: 6.75,
            win_rate: 68.5,
            total_trades: 47,
            daily_trades: 3,
            best_trade: 89.23,
            current_drawdown: -12.45,
            rsi: 42.3,
            sma_12: 67245.67,
            sma_26: 66980.23,
            bollinger_upper: 68500.00,
            bollinger_middle: 67850.00,
            bollinger_lower: 67200.00,
            current_signal: "HOLD",
            recent_trades: [
                {"timestamp": "2025-06-13 09:45:23", "type": "SELL", "price": 67820.45, "size": 0.00147, "pnl": 23.45},
                {"timestamp": "2025-06-13 09:32:15", "type": "BUY", "price": 67654.32, "size": 0.00148, "pnl": 0},
                {"timestamp": "2025-06-13 09:18:42", "type": "SELL", "price": 67890.12, "size": 0.00145, "pnl": 45.67},
                {"timestamp": "2025-06-13 08:56:33", "type": "BUY", "price": 67576.89, "size": 0.00148, "pnl": 0},
                {"timestamp": "2025-06-13 08:42:18", "type": "SELL", "price": 67423.55, "size": 0.00149, "pnl": -15.23},
                {"timestamp": "2025-06-13 08:29:07", "type": "BUY", "price": 67521.44, "size": 0.00148, "pnl": 0}
            ],
            stop_loss: 66253.81,
            take_profit: 69807.83,
            risk_exposure: 2.3,
            daily_trade_limit: 10,
            risk_per_trade: 1.5,
            price_history: [67450, 67520, 67380, 67600, 67720, 67850]
        };

        this.chart = null;
        this.updateInterval = null;
        this.init();
    }

    init() {
        this.populateData();
        this.initChart();
        this.setupEventListeners();
        this.startRealTimeUpdates();
    }

    populateData() {
        // Update current price and change
        document.getElementById('currentPrice').textContent = this.formatCurrency(this.data.current_price);
        const priceChangeEl = document.getElementById('priceChange');
        priceChangeEl.textContent = `${this.data.price_change_24h > 0 ? '+' : ''}${this.data.price_change_24h}%`;
        priceChangeEl.className = `price-change ${this.data.price_change_24h > 0 ? 'positive' : 'negative'}`;

        // Update bot status
        const statusEl = document.getElementById('botStatus');
        statusEl.textContent = this.data.bot_status === 'active' ? 'Active' : 'Inactive';
        statusEl.className = `status ${this.data.bot_status === 'active' ? 'status--success' : 'status--error'}`;

        // Update position
        const positionEl = document.getElementById('currentPosition');
        positionEl.textContent = this.data.current_position.charAt(0).toUpperCase() + this.data.current_position.slice(1);
        positionEl.className = `position ${this.data.current_position}`;

        // Update account balance
        document.getElementById('accountBalance').textContent = this.formatCurrency(this.data.account_balance);

        // Update performance metrics
        document.getElementById('totalPnl').textContent = this.formatCurrency(this.data.total_pnl);
        document.getElementById('totalPnlPercent').textContent = `+${this.data.total_pnl_percent}%`;
        document.getElementById('winRate').textContent = `${this.data.win_rate}%`;
        document.getElementById('totalTrades').textContent = this.data.total_trades;
        document.getElementById('dailyTrades').textContent = this.data.daily_trades;
        document.getElementById('bestTrade').textContent = this.formatCurrency(this.data.best_trade);
        document.getElementById('drawdown').textContent = this.formatCurrency(this.data.current_drawdown);

        // Update technical indicators
        document.getElementById('rsiValue').textContent = this.data.rsi;
        document.getElementById('rsiFill').style.width = `${this.data.rsi}%`;
        document.getElementById('sma12').textContent = this.formatCurrency(this.data.sma_12);
        document.getElementById('sma26').textContent = this.formatCurrency(this.data.sma_26);
        document.getElementById('bbUpper').textContent = this.formatCurrency(this.data.bollinger_upper);
        document.getElementById('bbMiddle').textContent = this.formatCurrency(this.data.bollinger_middle);
        document.getElementById('bbLower').textContent = this.formatCurrency(this.data.bollinger_lower);

        // Update signal
        const signalEl = document.getElementById('currentSignal');
        signalEl.textContent = this.data.current_signal;
        signalEl.className = `signal ${this.data.current_signal.toLowerCase()}`;

        // Update risk management
        document.getElementById('riskExposure').textContent = `${this.data.risk_exposure}%`;
        document.getElementById('stopLoss').textContent = this.formatCurrency(this.data.stop_loss);
        document.getElementById('takeProfit').textContent = this.formatCurrency(this.data.take_profit);
        document.getElementById('riskPerTrade').textContent = `${this.data.risk_per_trade}%`;

        // Update trade limit progress
        const progressPercent = (this.data.daily_trades / this.data.daily_trade_limit) * 100;
        document.getElementById('tradeLimitProgress').style.width = `${progressPercent}%`;
        document.getElementById('tradeLimitText').textContent = `${this.data.daily_trades}/${this.data.daily_trade_limit}`;

        // Populate trades table
        this.populateTradesTable();

        // Update status indicator
        this.updateStatusIndicator();
    }

    populateTradesTable() {
        const tbody = document.getElementById('tradesTableBody');
        tbody.innerHTML = '';

        this.data.recent_trades.forEach(trade => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${this.formatTimestamp(trade.timestamp)}</td>
                <td><span class="trade-type ${trade.type.toLowerCase()}">${trade.type}</span></td>
                <td>${this.formatCurrency(trade.price)}</td>
                <td>${trade.size.toFixed(5)}</td>
                <td class="trade-pnl ${trade.pnl > 0 ? 'positive' : trade.pnl < 0 ? 'negative' : ''}">${trade.pnl > 0 ? '+' : ''}${this.formatCurrency(trade.pnl)}</td>
            `;
            tbody.appendChild(row);
        });
    }

    initChart() {
        const ctx = document.getElementById('priceChart').getContext('2d');
        
        // Generate time labels for the last 6 hours
        const labels = [];
        for (let i = 5; i >= 0; i--) {
            const time = new Date();
            time.setHours(time.getHours() - i);
            labels.push(time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }));
        }

        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'BTC Price',
                    data: this.data.price_history,
                    borderColor: '#00d4ff',
                    backgroundColor: 'rgba(0, 212, 255, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#00d4ff',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.7)'
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.7)',
                            callback: function(value) {
                                return '$' + value.toLocaleString();
                            }
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                elements: {
                    point: {
                        hoverRadius: 8
                    }
                }
            }
        });
    }

    setupEventListeners() {
        // Toggle bot button
        document.getElementById('toggleBot').addEventListener('click', () => {
            this.toggleBot();
        });

        // Emergency stop button
        document.getElementById('emergencyStop').addEventListener('click', () => {
            this.emergencyStop();
        });

        // Settings button
        document.getElementById('settings').addEventListener('click', () => {
            alert('Settings panel would open here');
        });

        // Export data button
        document.getElementById('exportData').addEventListener('click', () => {
            this.exportData();
        });
    }

    toggleBot() {
        const button = document.getElementById('toggleBot');
        const statusEl = document.getElementById('botStatus');
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');

        if (this.data.bot_status === 'active') {
            this.data.bot_status = 'inactive';
            button.textContent = 'Start Bot';
            button.className = 'btn btn--primary';
            statusEl.textContent = 'Inactive';
            statusEl.className = 'status status--error';
            statusDot.className = 'status-indicator__dot stopped';
            statusText.textContent = 'Stopped';
        } else {
            this.data.bot_status = 'active';
            button.textContent = 'Stop Bot';
            button.className = 'btn btn--secondary';
            statusEl.textContent = 'Active';
            statusEl.className = 'status status--success';
            statusDot.className = 'status-indicator__dot';
            statusText.textContent = 'Running';
        }
    }

    emergencyStop() {
        if (confirm('Are you sure you want to perform an emergency stop? This will immediately stop all trading activities.')) {
            this.data.bot_status = 'inactive';
            this.data.current_position = 'none';
            
            // Update UI
            document.getElementById('toggleBot').textContent = 'Start Bot';
            document.getElementById('toggleBot').className = 'btn btn--primary';
            document.getElementById('botStatus').textContent = 'Inactive';
            document.getElementById('botStatus').className = 'status status--error';
            document.getElementById('currentPosition').textContent = 'None';
            document.getElementById('currentPosition').className = 'position';
            
            this.updateStatusIndicator();
            alert('Emergency stop executed. All positions closed.');
        }
    }

    exportData() {
        const exportData = {
            timestamp: new Date().toISOString(),
            bot_status: this.data.bot_status,
            current_price: this.data.current_price,
            account_balance: this.data.account_balance,
            total_pnl: this.data.total_pnl,
            recent_trades: this.data.recent_trades
        };

        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `trading-bot-data-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    updateStatusIndicator() {
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');

        if (this.data.bot_status === 'active') {
            statusDot.className = 'status-indicator__dot';
            statusText.textContent = 'Running';
        } else {
            statusDot.className = 'status-indicator__dot stopped';
            statusText.textContent = 'Stopped';
        }
    }

    startRealTimeUpdates() {
        this.updateInterval = setInterval(() => {
            this.simulateRealTimeData();
        }, 5000); // Update every 5 seconds
    }

    simulateRealTimeData() {
        if (this.data.bot_status === 'active') {
            // Simulate price changes
            const priceChange = (Math.random() - 0.5) * 100;
            this.data.current_price += priceChange;
            
            // Update price history
            this.data.price_history.shift();
            this.data.price_history.push(this.data.current_price);
            
            // Simulate small changes in other metrics
            this.data.rsi += (Math.random() - 0.5) * 5;
            this.data.rsi = Math.max(0, Math.min(100, this.data.rsi));
            
            // Update chart
            this.chart.data.datasets[0].data = this.data.price_history;
            this.chart.update('none');
            
            // Update current price display
            document.getElementById('currentPrice').textContent = this.formatCurrency(this.data.current_price);
            document.getElementById('rsiValue').textContent = this.data.rsi.toFixed(1);
            document.getElementById('rsiFill').style.width = `${this.data.rsi}%`;
            
            // Occasionally simulate a new trade
            if (Math.random() < 0.3) {
                this.simulateNewTrade();
            }
        }
    }

    simulateNewTrade() {
        const tradeTypes = ['BUY', 'SELL'];
        const type = tradeTypes[Math.floor(Math.random() * tradeTypes.length)];
        const pnl = (Math.random() - 0.3) * 50; // Slight bias towards positive
        
        const newTrade = {
            timestamp: new Date().toISOString().replace('T', ' ').substr(0, 19),
            type: type,
            price: this.data.current_price + (Math.random() - 0.5) * 50,
            size: 0.001 + Math.random() * 0.001,
            pnl: type === 'BUY' ? 0 : pnl
        };
        
        this.data.recent_trades.unshift(newTrade);
        this.data.recent_trades = this.data.recent_trades.slice(0, 6);
        
        // Update totals
        if (newTrade.pnl !== 0) {
            this.data.total_pnl += newTrade.pnl;
            this.data.daily_trades++;
            this.data.total_trades++;
        }
        
        this.populateTradesTable();
        document.getElementById('totalPnl').textContent = this.formatCurrency(this.data.total_pnl);
        document.getElementById('dailyTrades').textContent = this.data.daily_trades;
        document.getElementById('totalTrades').textContent = this.data.total_trades;
        
        // Update trade limit progress
        const progressPercent = (this.data.daily_trades / this.data.daily_trade_limit) * 100;
        document.getElementById('tradeLimitProgress').style.width = `${progressPercent}%`;
        document.getElementById('tradeLimitText').textContent = `${this.data.daily_trades}/${this.data.daily_trade_limit}`;
    }

    formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(amount);
    }

    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit',
            second: '2-digit'
        });
    }

    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        if (this.chart) {
            this.chart.destroy();
        }
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new TradingBotDashboard();
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        dashboard.destroy();
    });
});