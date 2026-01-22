import React, { useState, useEffect } from 'react';
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Wallet,
  AlertTriangle,
  Check,
  X,
  Activity,
  Loader2
} from 'lucide-react';
import { authUtils } from '../utils/auth';

const TradingPanel = ({ selectedPair = 'BTC-USDC', currentPrice = 0 }) => {
  const [balances, setBalances] = useState([]);
  const [quote, setQuote] = useState(null);
  const [tradeForm, setTradeForm] = useState({
    action: 'buy',
    symbol: selectedPair,
    amountType: 'usd',
    amount: 25
  });
  const [isLoading, setIsLoading] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [tradeResult, setTradeResult] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchBalances();
  }, []);

  useEffect(() => {
    setTradeForm(prev => ({ ...prev, symbol: selectedPair }));
  }, [selectedPair]);

  useEffect(() => {
    if (tradeForm.amount > 0) {
      fetchQuote();
    }
  }, [tradeForm]);

  const fetchBalances = async () => {
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/account-balances');
      if (response.ok) {
        const data = await response.json();
        setBalances(data.balances || []);
      } else if (response.status === 401) {
        authUtils.logout();
      }
    } catch (error) {
      console.error('Error fetching balances:', error);
    }
  };

  const fetchQuote = async () => {
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/get-quote', {
        method: 'POST',
        body: JSON.stringify({
          ...tradeForm,
          current_price: currentPrice // Pass current price to backend
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setQuote(data);
      } else if (response.status === 401) {
        authUtils.logout();
      } else {
        // If quote fails, create a manual quote estimate using currentPrice
        if (currentPrice > 0) {
          const cryptoAmount = tradeForm.amountType === 'usd'
            ? tradeForm.amount / currentPrice
            : tradeForm.amount;
          const usdAmount = tradeForm.amountType === 'crypto'
            ? tradeForm.amount * currentPrice
            : tradeForm.amount;
          const estimatedFee = usdAmount * 0.006; // 0.6% fee estimate

          setQuote({
            current_price: currentPrice,
            crypto_amount: cryptoAmount,
            usd_amount: usdAmount,
            estimated_fee: estimatedFee,
            total_cost: usdAmount + estimatedFee
          });
        }
      }
    } catch (error) {
      console.error('Error fetching quote:', error);
      // Fallback to manual quote
      if (currentPrice > 0) {
        const cryptoAmount = tradeForm.amountType === 'usd'
          ? tradeForm.amount / currentPrice
          : tradeForm.amount;
        const usdAmount = tradeForm.amountType === 'crypto'
          ? tradeForm.amount * currentPrice
          : tradeForm.amount;
        const estimatedFee = usdAmount * 0.006;

        setQuote({
          current_price: currentPrice,
          crypto_amount: cryptoAmount,
          usd_amount: usdAmount,
          estimated_fee: estimatedFee,
          total_cost: usdAmount + estimatedFee
        });
      }
    }
  };

  const handleInputChange = (field, value) => {
    setTradeForm(prev => ({
      ...prev,
      [field]: value
    }));
    setError('');
  };

  const handleTrade = async () => {
    setIsLoading(true);
    setError('');
    
    try {
      const response = await authUtils.authenticatedFetch('http://localhost:5001/api/execute-trade', {
        method: 'POST',
        body: JSON.stringify(tradeForm),
      });
      
      const data = await response.json();
      
      if (data.success) {
        setTradeResult(data);
        setShowConfirmation(false);
        // Refresh balances after successful trade
        setTimeout(fetchBalances, 1000);
      } else {
        setError(data.error || 'Trade failed');
        setShowConfirmation(false);
      }
    } catch (error) {
      setError('Network error occurred');
      setShowConfirmation(false);
    } finally {
      setIsLoading(false);
    }
  };

  const getAvailableBalance = (currency) => {
    const balance = balances.find(b => b.currency === currency);
    return balance ? balance.available : 0;
  };

  const validateTrade = () => {
    const cryptoSymbol = selectedPair.split('-')[0];

    if (tradeForm.action === 'buy') {
      const usdBalance = getAvailableBalance('USDC') + getAvailableBalance('USD');
      const requiredAmount = quote ? quote.total_cost : tradeForm.amount;
      return usdBalance >= requiredAmount;
    } else {
      const cryptoBalance = getAvailableBalance(cryptoSymbol);
      const requiredAmount = quote ? quote.crypto_amount : tradeForm.amount;
      return cryptoBalance >= requiredAmount;
    }
  };

  const BalanceCard = ({ currency, available, total, held }) => (
    <div className="bg-gray-700 rounded-lg p-4 border border-gray-600">
      <div className="flex items-center justify-between mb-3">
        <span className="font-medium text-crypto-blue">{currency}</span>
        <Wallet className="h-4 w-4 text-gray-400" />
      </div>
      <div className="space-y-2">
        <div>
          <div className="text-xs text-gray-400 mb-1">Available:</div>
          <div className="font-medium text-lg truncate">
            {currency === 'BTC' ? available.toFixed(8) : available.toFixed(2)}
          </div>
        </div>
        {held > 0 && (
          <div>
            <div className="text-xs text-gray-400 mb-1">Held:</div>
            <div className="text-orange-400 font-medium truncate">
              {currency === 'BTC' ? held.toFixed(8) : held.toFixed(2)}
            </div>
          </div>
        )}
      </div>
    </div>
  );

  const QuoteDisplay = ({ quote }) => {
    const cryptoSymbol = tradeForm.symbol.split('-')[0];

    return (
      <div className="bg-gray-700 rounded-lg p-4 border border-gray-600">
        <h4 className="font-medium mb-3 text-crypto-blue">Trade Preview</h4>
        <div className="space-y-2.5 text-sm">
          <div className="flex justify-between items-start gap-2">
            <span className="text-gray-400 flex-shrink-0">Current Price:</span>
            <span className="font-medium text-right break-all">${quote.current_price.toLocaleString()}</span>
          </div>
          <div className="flex justify-between items-start gap-2">
            <span className="text-gray-400 flex-shrink-0">
              {tradeForm.action === 'buy' ? 'You pay:' : 'You receive:'}
            </span>
            <span className="font-medium text-right">${quote.usd_amount.toFixed(2)}</span>
          </div>
          <div className="flex justify-between items-start gap-2">
            <span className="text-gray-400 flex-shrink-0">
              {tradeForm.action === 'buy' ? 'You receive:' : 'You pay:'}
            </span>
            <span className="font-medium text-right break-all">{quote.crypto_amount.toFixed(8)} {cryptoSymbol}</span>
          </div>
          <div className="flex justify-between items-start gap-2">
            <span className="text-gray-400 flex-shrink-0">Estimated Fee:</span>
            <span className="text-orange-400 text-right">${quote.estimated_fee.toFixed(2)}</span>
          </div>
          <div className="border-t border-gray-600 pt-2 mt-2">
            <div className="flex justify-between items-start gap-2 font-medium">
              <span className="flex-shrink-0">Total {tradeForm.action === 'buy' ? 'Cost:' : 'Received:'}</span>
              <span className={`text-right ${tradeForm.action === 'buy' ? 'text-red-400' : 'text-green-400'}`}>
                ${quote.total_cost.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  };

  if (tradeResult) {
    return (
      <div className="space-y-6">
        <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-6">
          <div className="flex items-center space-x-3 mb-4">
            <Check className="h-8 w-8 text-green-400" />
            <div>
              <h3 className="text-xl font-bold text-green-400">Trade Executed Successfully!</h3>
              <p className="text-gray-300">{tradeResult.message}</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="text-sm text-gray-400">Order ID</div>
              <div className="font-mono text-sm">{tradeResult.order_id}</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="text-sm text-gray-400">Executed Amount</div>
              <div className="font-medium">{tradeResult.executed_amount?.toFixed(8)} BTC</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="text-sm text-gray-400">Execution Price</div>
              <div className="font-medium">${tradeResult.executed_price?.toLocaleString()}</div>
            </div>
          </div>
          
          <button
            onClick={() => setTradeResult(null)}
            className="bg-crypto-blue hover:bg-blue-600 text-white px-6 py-2 rounded-lg transition-colors"
          >
            Make Another Trade
          </button>
        </div>
      </div>
    );
  }

  const getRelevantBalances = () => {
    const cryptoSymbol = selectedPair.split('-')[0];
    const usdBalances = balances.filter(b => b.currency === 'USD' || b.currency === 'USDC');
    const cryptoBalance = balances.find(b => b.currency === cryptoSymbol);

    const result = [...usdBalances];
    if (cryptoBalance) {
      result.unshift(cryptoBalance);
    } else {
      // Show placeholder if crypto balance doesn't exist
      result.unshift({
        currency: cryptoSymbol,
        available: 0,
        total: 0,
        held: 0
      });
    }

    return result;
  };

  return (
    <div className="space-y-6">
      {/* Account Balances */}
      <div>
        <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
          <Wallet className="h-5 w-5 text-crypto-blue" />
          <span>Account Balances</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {balances.length > 0 ? (
            getRelevantBalances().map((balance, index) => (
              <BalanceCard key={index} {...balance} />
            ))
          ) : (
            <div className="col-span-full text-center text-gray-400 py-8">
              Loading balances...
            </div>
          )}
        </div>
      </div>

      {/* Trading Form */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
            <Activity className="h-5 w-5 text-crypto-green" />
            <span>Place Order</span>
          </h3>
          
          <div className="space-y-4">
            {/* Buy/Sell Toggle */}
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => handleInputChange('action', 'buy')}
                className={`py-3 px-4 rounded-lg font-medium transition-colors ${
                  tradeForm.action === 'buy'
                    ? 'bg-green-500 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                <TrendingUp className="h-4 w-4 inline mr-2" />
                Buy
              </button>
              <button
                onClick={() => handleInputChange('action', 'sell')}
                className={`py-3 px-4 rounded-lg font-medium transition-colors ${
                  tradeForm.action === 'sell'
                    ? 'bg-red-500 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                <TrendingDown className="h-4 w-4 inline mr-2" />
                Sell
              </button>
            </div>

            {/* Trading Pair */}
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">
                Trading Pair
              </label>
              <div className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white">
                {tradeForm.symbol.replace('-', '/')}
              </div>
            </div>

            {/* Amount Type */}
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">
                Amount Type
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => handleInputChange('amountType', 'usd')}
                  className={`py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                    tradeForm.amountType === 'usd'
                      ? 'bg-crypto-blue text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  USD Amount
                </button>
                <button
                  onClick={() => handleInputChange('amountType', 'crypto')}
                  className={`py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                    tradeForm.amountType === 'crypto'
                      ? 'bg-crypto-blue text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  {tradeForm.symbol.split('-')[0]} Amount
                </button>
              </div>
            </div>

            {/* Amount Input */}
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">
                Amount {tradeForm.amountType === 'usd' ? '(USD)' : `(${tradeForm.symbol.split('-')[0]})`}
              </label>
              <input
                type="number"
                value={tradeForm.amount}
                onChange={(e) => handleInputChange('amount', parseFloat(e.target.value) || 0)}
                placeholder={tradeForm.amountType === 'usd' ? '25.00' : '0.0001'}
                step={tradeForm.amountType === 'usd' ? '1' : '0.0001'}
                min="0"
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-crypto-blue focus:border-transparent"
              />
            </div>

            {/* Quick Amount Buttons */}
            <div>
              <div className="text-sm text-gray-400 mb-2">Quick amounts:</div>
              <div className="grid grid-cols-4 gap-2">
                {tradeForm.amountType === 'usd' ? (
                  <>
                    <button onClick={() => handleInputChange('amount', 25)} className="py-1 px-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">$25</button>
                    <button onClick={() => handleInputChange('amount', 50)} className="py-1 px-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">$50</button>
                    <button onClick={() => handleInputChange('amount', 100)} className="py-1 px-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">$100</button>
                    <button onClick={() => handleInputChange('amount', 500)} className="py-1 px-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">$500</button>
                  </>
                ) : (
                  <>
                    <button onClick={() => handleInputChange('amount', 0.0001)} className="py-1 px-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">0.0001</button>
                    <button onClick={() => handleInputChange('amount', 0.001)} className="py-1 px-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">0.001</button>
                    <button onClick={() => handleInputChange('amount', 0.01)} className="py-1 px-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">0.01</button>
                    <button onClick={() => handleInputChange('amount', 0.1)} className="py-1 px-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">0.1</button>
                  </>
                )}
              </div>
            </div>

            {/* Error Display */}
            {error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 flex items-center space-x-2">
                <AlertTriangle className="h-4 w-4 text-red-400 flex-shrink-0" />
                <span className="text-red-400 text-sm">{error}</span>
              </div>
            )}

            {/* Place Order Button */}
            <button
              onClick={() => setShowConfirmation(true)}
              disabled={!quote || isLoading || !validateTrade()}
              className={`w-full py-3 px-4 rounded-lg font-medium transition-colors ${
                !quote || isLoading || !validateTrade()
                  ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                  : tradeForm.action === 'buy'
                  ? 'bg-green-600 hover:bg-green-700 text-white'
                  : 'bg-red-600 hover:bg-red-700 text-white'
              }`}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin inline mr-2" />
              ) : (
                <DollarSign className="h-4 w-4 inline mr-2" />
              )}
              {tradeForm.action === 'buy' ? 'Buy' : 'Sell'} {tradeForm.symbol.split('-')[0]}
            </button>
          </div>
        </div>

        {/* Quote Display */}
        <div>
          {quote ? (
            <QuoteDisplay quote={quote} />
          ) : (
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <div className="text-center text-gray-400">
                Enter trade details to see quote
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Confirmation Modal */}
      {showConfirmation && quote && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4 text-yellow-400">
              Confirm Trade
            </h3>
            
            <div className="space-y-3 mb-6">
              <div className="flex justify-between">
                <span>Action:</span>
                <span className={`font-medium ${tradeForm.action === 'buy' ? 'text-green-400' : 'text-red-400'}`}>
                  {tradeForm.action.toUpperCase()}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Amount:</span>
                <span>{quote.crypto_amount.toFixed(8)} {tradeForm.symbol.split('-')[0]}</span>
              </div>
              <div className="flex justify-between">
                <span>Price:</span>
                <span>${(quote.current_price || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span>Total Cost:</span>
                <span className="font-medium">${quote.total_cost.toFixed(2)}</span>
              </div>
            </div>

            <div className="flex space-x-3">
              <button
                onClick={() => setShowConfirmation(false)}
                className="flex-1 py-2 px-4 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleTrade}
                disabled={isLoading}
                className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                  tradeForm.action === 'buy'
                    ? 'bg-green-600 hover:bg-green-700'
                    : 'bg-red-600 hover:bg-red-700'
                } text-white`}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin inline mr-2" />
                ) : null}
                Confirm {tradeForm.action}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TradingPanel;