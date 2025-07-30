require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { Coinbase, Wallet } = require('@coinbase/coinbase-sdk');

const app = express();
const port = 3001;

app.use(cors());
app.use(express.json());

// Initialize Coinbase CDP client
const apiKeyName = process.env.COINBASE_API_KEY;
const privateKey = process.env.COINBASE_API_SECRET;

let coinbase;
let portfolio;

// Initialize CDP client
async function initializeCDP() {
    try {
        coinbase = new Coinbase({
            apiKeyName: apiKeyName,
            privateKey: privateKey,
        });
        console.log('CDP client initialized successfully');

        // The API is portfolio-centric. We'll use the portfolio object for operations.
        portfolio = coinbase.portfolio;
        console.log('Portfolio access configured.');
        
    } catch (error) {
        console.error('Failed to initialize CDP client:', error);
    }
}

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({ 
        status: 'ok', 
        cdp_initialized: !!coinbase,
        portfolio_available: !!portfolio
    });
});

// Get portfolio balances
app.get('/portfolio/balances', async (req, res) => {
    try {
        if (!portfolio) {
            return res.status(400).json({
                success: false,
                error: 'Portfolio not available'
            });
        }
        
        const portfolioId = process.env.COINBASE_PORTFOLIO_ID;
        const balances = await portfolio.getBalances(portfolioId);
        res.json({
            success: true,
            balances: balances.balances
        });
        
    } catch (error) {
        console.error('Error getting balances:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// Execute trade
app.post('/trade', async (req, res) => {
    try {
        const { side, amount, product_id } = req.body; // side: 'BUY' or 'SELL', product_id: e.g., 'BTC-USD'
        
        if (!portfolio) {
            return res.status(400).json({
                success: false,
                error: 'Portfolio not available for trading'
            });
        }
        
        console.log(`Executing ${side} trade: ${amount} of ${product_id}`);
        
        const order = {
            product_id: product_id,
            side: side,
            order_configuration: {
                market_market_ioc: {
                    [side === 'BUY' ? 'quote_size' : 'base_size']: amount,
                }
            }
        };

        const result = await coinbase.rest.order.createOrder(order);

        res.json({
            success: true,
            message: `Trade executed successfully`,
            order_id: result.order_id,
            status: 'SUBMITTED'
        });
        
    } catch (error) {
        console.error('Trade execution error:', error);
        res.status(500).json({
            success: false,
            error: error.message,
            error_details: error.response ? error.response.data : null
        });
    }
});

// Get trade quote - Disabling as it's not the priority and requires more info.
app.post('/quote', async (req, res) => {
    res.status(501).json({ success: false, error: 'Quoting not implemented yet.' });
});

// Create new wallet - Disabling as it's not applicable to the CDP API.
app.post('/wallet/create', async (req, res) => {
    res.status(501).json({ success: false, error: 'Wallet creation is not supported. Portfolios are used instead.' });
});

// Start server
app.listen(port, async () => {
    console.log(`CDP service running on port ${port}`);
    await initializeCDP();
});