import React from 'react';
import { Bot, Wifi, WifiOff } from 'lucide-react';

const BotStatus = ({ connected }) => {
  return (
    <div className="flex items-center space-x-2">
      <div className={`flex items-center space-x-2 px-3 py-1 rounded-full text-sm ${
        connected 
          ? 'bg-crypto-green/20 text-crypto-green border border-crypto-green/30' 
          : 'bg-crypto-red/20 text-crypto-red border border-crypto-red/30'
      }`}>
        <div className={`w-2 h-2 rounded-full ${connected ? 'bg-crypto-green' : 'bg-crypto-red'} animate-pulse`}></div>
        <Bot className="h-4 w-4" />
        <span className="font-medium">
          {connected ? 'Connected' : 'Disconnected'}
        </span>
        {connected ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
      </div>
    </div>
  );
};

export default BotStatus;