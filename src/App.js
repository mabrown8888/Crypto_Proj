import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  TrendingUp, 
  TrendingDown, 
  Bot, 
  Mic, 
  MicOff,
  Bell,
  Brain,
  DollarSign,
  BarChart3,
  Settings,
  History
} from 'lucide-react';
import TradingDashboard from './components/TradingDashboard';
import SentimentAnalysis from './components/SentimentAnalysis';
import WhaleTracker from './components/WhaleTracker';
import AIStrategies from './components/AIStrategies';
import VoiceCommands from './components/VoiceCommands';
import BotStatus from './components/BotStatus';
import TradingHistory from './components/TradingHistory';
import CryptoDashboard from './components/CryptoDashboard';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [botConnected, setBotConnected] = useState(false);
  const [voiceActive, setVoiceActive] = useState(false);

  const tabs = [
    { id: 'dashboard', name: 'Dashboard', icon: BarChart3 },
    { id: 'crypto', name: 'Multi-Crypto', icon: DollarSign },
    { id: 'history', name: 'Trading History', icon: History },
    { id: 'sentiment', name: 'Sentiment', icon: Brain },
    { id: 'whales', name: 'Whale Tracker', icon: TrendingUp },
    { id: 'ai-strategies', name: 'AI Strategies', icon: Bot },
    { id: 'voice', name: 'Voice Control', icon: Mic },
  ];

  const renderActiveComponent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <TradingDashboard />;
      case 'crypto':
        return <CryptoDashboard />;
      case 'history':
        return <TradingHistory />;
      case 'sentiment':
        return <SentimentAnalysis />;
      case 'whales':
        return <WhaleTracker />;
      case 'ai-strategies':
        return <AIStrategies />;
      case 'voice':
        return <VoiceCommands />;
      default:
        return <TradingDashboard />;
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

            <button className="p-2 rounded-lg bg-gray-700 text-gray-300 hover:bg-gray-600 transition-colors">
              <Bell className="h-5 w-5" />
            </button>

            <button className="p-2 rounded-lg bg-gray-700 text-gray-300 hover:bg-gray-600 transition-colors">
              <Settings className="h-5 w-5" />
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
    </div>
  );
}

export default App;