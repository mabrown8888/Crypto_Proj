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
let defaultWallet;

// Initialize CDP client
async function initializeCDP() {
    try {
        coinbase = new Coinbase({
            apiKeyName: apiKeyName,
            privateKey: privateKey
        });
        
        console.log('CDP client initialized successfully');
        
        // Note: Wallet creation will be done on-demand for now
        console.log('CDP client ready. Wallets will be created on-demand.');
        
    } catch (error) {
        console.error('Failed to initialize CDP client:', error);
    }
}

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({ 
        status: 'ok', 
        cdp_initialized: !!coinbase,
        wallet_available: !!defaultWallet 
    });
});

// Get wallet balances
app.get('/wallet/balances', async (req, res) => {
    try {
        if (!defaultWallet) {
            return res.status(400).json({
                success: false,
                error: 'No wallet available'
            });
        }
        
        const balances = await defaultWallet.listBalances();
        res.json({
            success: true,
            balances: balances
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
        const { action, amount, fromAsset, toAsset } = req.body;
        
        if (!defaultWallet) {
            return res.status(400).json({
                success: false,
                error: 'No wallet available for trading'
            });
        }
        
        console.log(`Executing ${action}: ${amount} ${fromAsset} -> ${toAsset}`);
        
        // Execute the trade
        const trade = await defaultWallet.trade(amount, fromAsset, toAsset);
        
        // Wait for the trade to complete
        await trade.wait();
        
        res.json({
            success: true,
            message: `${action} trade executed successfully`,
            trade_id: trade.getId(),
            status: trade.getStatus(),
            transaction_hash: trade.getTransactionHash()
        });
        
    } catch (error) {
        console.error('Trade execution error:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// Get trade quote
app.post('/quote', async (req, res) => {
    try {
        const { amount, fromAsset, toAsset } = req.body;
        
        if (!defaultWallet) {
            return res.status(400).json({
                success: false,
                error: 'No wallet available for quote'
            });
        }
        
        // Create a trade quote (doesn't execute)
        const trade = await defaultWallet.trade(amount, fromAsset, toAsset);
        
        res.json({
            success: true,
            quote: {
                from_amount: amount,
                from_asset: fromAsset,
                to_asset: toAsset,
                estimated_to_amount: trade.getToAmount(),
                trade_id: trade.getId()
            }
        });
        
    } catch (error) {
        console.error('Quote error:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// Create new wallet
app.post('/wallet/create', async (req, res) => {
    try {
        const newWallet = await Wallet.create();
        res.json({
            success: true,
            wallet_id: newWallet.getId(),
            message: 'Wallet created successfully'
        });
    } catch (error) {
        console.error('Wallet creation error:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// Start server
app.listen(port, async () => {
    console.log(`CDP service running on port ${port}`);
    await initializeCDP();
});