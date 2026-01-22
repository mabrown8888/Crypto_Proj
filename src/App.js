import React, { useState, useEffect } from 'react';
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Bot,
  Mic,
  MicOff,
  Bell,
  DollarSign,
  BarChart3,
  Settings,
  History,
  LogOut
} from 'lucide-react';
import Portfolio from './components/Portfolio';
import Trade from './components/Trade';
import VoiceCommands from './components/VoiceCommands';
import BotStatus from './components/BotStatus';
import TradingHistory from './components/TradingHistory';
import NotificationsModal from './components/NotificationsModal';
import SettingsModal from './components/SettingsModal';
import LoginForm from './components/LoginForm';
import EnhancedAutoTradingBot from './components/EnhancedAutoTradingBot';
import KalshiDashboard from './components/KalshiDashboard';
import HedgeDashboard from './components/HedgeDashboard';
import BTCMonitor from './components/BTCMonitor';
import AlgorithmAnalytics from './components/AlgorithmAnalytics';
import { authUtils, setupTokenRefresh } from './utils/auth';

function App() {
  const [activeTab, setActiveTab] = useState('portfolio');
  const [botConnected] = useState(false);
  const [voiceActive, setVoiceActive] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState('');

  useEffect(() => {
    // Check authentication status on app load
    const authenticated = authUtils.isAuthenticated();
    setIsAuthenticated(authenticated);
    
    if (authenticated) {
      setUsername(authUtils.getUsername() || 'User');
      setupTokenRefresh(); // Setup automatic token refresh
    }
  }, []);

  const handleLogin = (loginData) => {
    setIsAuthenticated(true);
    setUsername(loginData.username);
    setupTokenRefresh();
  };

  const handleLogout = () => {
    authUtils.logout();
    setIsAuthenticated(false);
    setUsername('');
  };

  // If not authenticated, show login form
  if (!isAuthenticated) {
    return <LoginForm onLogin={handleLogin} />;
  }

  const tabs = [
    { id: 'portfolio', name: 'Portfolio', icon: DollarSign },
    { id: 'trade', name: 'Trade', icon: BarChart3 },
    { id: 'auto-trading', name: 'Coinbase Trading Bot', icon: Bot },
    { id: 'history', name: 'Trading History', icon: History },
    { id: 'kalshi', name: 'Kalshi Markets', icon: TrendingUp },
    { id: 'btc-monitor', name: 'BTC Monitor', icon: Activity },
    { id: 'hedge', name: 'Kalshi Trading Bot', icon: TrendingDown },
    { id: 'analytics', name: 'Algorithm Analytics', icon: Activity },
  ];

  const renderActiveComponent = () => {
    switch (activeTab) {
      case 'portfolio':
        return <Portfolio />;
      case 'trade':
        return <Trade />;
      case 'auto-trading':
        return <EnhancedAutoTradingBot />;
      case 'history':
        return <TradingHistory />;
      case 'kalshi':
        return <KalshiDashboard />;
      case 'btc-monitor':
        return <BTCMonitor />;
      case 'hedge':
        return <HedgeDashboard />;
      case 'analytics':
        return <AlgorithmAnalytics />;
      default:
        return <Portfolio />;
    }
  };

  return (
    <div className="min-h-screen bg-crypto-dark text-white">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <Bot className="h-8 w-8 text-crypto-blue" />
              <h1 className="text-2xl font-bold bg-gradient-to-r from-crypto-blue to-crypto-purple bg-clip-text text-transparent">
                AI Trading Co-Pilot
              </h1>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div className="text-sm text-gray-400">
              Welcome, <span className="text-crypto-blue font-medium">{username}</span>
            </div>
            
            <BotStatus connected={botConnected} />
            
            <button 
              onClick={() => setVoiceActive(!voiceActive)}
              className={`p-2 rounded-lg transition-all ${
                voiceActive 
                  ? 'bg-crypto-green text-white glow-green' 
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {voiceActive ? <Mic className="h-5 w-5" /> : <MicOff className="h-5 w-5" />}
            </button>

            <button 
              onClick={() => setNotificationsOpen(true)}
              className="p-2 rounded-lg bg-gray-700 text-gray-300 hover:bg-gray-600 transition-colors"
            >
              <Bell className="h-5 w-5" />
            </button>

            <button 
              onClick={() => setSettingsOpen(true)}
              className="p-2 rounded-lg bg-gray-700 text-gray-300 hover:bg-gray-600 transition-colors"
            >
              <Settings className="h-5 w-5" />
            </button>

            <button 
              onClick={handleLogout}
              className="p-2 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors"
              title="Logout"
            >
              <LogOut className="h-5 w-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-gray-900 border-b border-gray-800">
        <div className="px-6">
          <div className="flex space-x-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-2 px-4 py-3 text-sm font-medium transition-all ${
                    activeTab === tab.id
                      ? 'text-crypto-blue border-b-2 border-crypto-blue bg-gray-800'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{tab.name}</span>
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="p-6">
        {renderActiveComponent()}
      </main>

      {/* Voice Commands Overlay */}
      {voiceActive && (
        <VoiceCommands 
          onClose={() => setVoiceActive(false)} 
          onCommand={(command) => console.log('Voice command:', command)}
        />
      )}

      {/* Notifications Modal */}
      {notificationsOpen && (
        <NotificationsModal 
          onClose={() => setNotificationsOpen(false)} 
        />
      )}

      {/* Settings Modal */}
      {settingsOpen && (
        <SettingsModal 
          onClose={() => setSettingsOpen(false)} 
        />
      )}
    </div>
  );
}

export default App;