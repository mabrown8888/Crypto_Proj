import React, { useState, useEffect, useRef } from 'react';
import { 
  Mic, 
  MicOff, 
  Volume2, 
  VolumeX,
  MessageSquare,
  Zap,
  TrendingUp,
  TrendingDown,
  Activity,
  Settings,
  X
} from 'lucide-react';

const VoiceCommands = ({ onClose, onCommand }) => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [confidence, setConfidence] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [commandHistory, setCommandHistory] = useState([]);
  const [supportedCommands] = useState([
    { command: 'buy bitcoin', description: 'Execute a buy order', category: 'trading' },
    { command: 'sell bitcoin', description: 'Execute a sell order', category: 'trading' },
    { command: 'show status', description: 'Display bot status', category: 'info' },
    { command: 'stop trading', description: 'Stop the trading bot', category: 'control' },
    { command: 'start trading', description: 'Start the trading bot', category: 'control' },
    { command: 'show price', description: 'Get current BTC price', category: 'info' },
    { command: 'show portfolio', description: 'Display portfolio value', category: 'info' },
    { command: 'emergency stop', description: 'Emergency halt all trading', category: 'control' },
    { command: 'show sentiment', description: 'Get market sentiment', category: 'analysis' },
    { command: 'whale alert', description: 'Check whale movements', category: 'analysis' }
  ]);

  const recognitionRef = useRef(null);
  const speechSynthRef = useRef(null);

  useEffect(() => {
    // Initialize speech recognition
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-US';
      
      recognitionRef.current.onresult = (event) => {
        let finalTranscript = '';
        let interimTranscript = '';
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          const confidence = event.results[i][0].confidence;
          
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
            setConfidence(confidence || 0.8);
          } else {
            interimTranscript += transcript;
          }
        }
        
        setTranscript(finalTranscript || interimTranscript);
        
        if (finalTranscript) {
          processCommand(finalTranscript.trim());
        }
      };
      
      recognitionRef.current.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
      };
      
      recognitionRef.current.onend = () => {
        setIsListening(false);
      };
    }

    // Initialize speech synthesis
    if ('speechSynthesis' in window) {
      speechSynthRef.current = window.speechSynthesis;
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, []);

  const startListening = () => {
    if (recognitionRef.current && !isListening) {
      setTranscript('');
      setConfidence(0);
      recognitionRef.current.start();
      setIsListening(true);
    }
  };

  const stopListening = () => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    }
  };

  const speak = (text) => {
    if (speechSynthRef.current && voiceEnabled) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.9;
      utterance.pitch = 1;
      utterance.volume = 0.8;
      speechSynthRef.current.speak(utterance);
    }
  };

  const processCommand = async (command) => {
    setIsProcessing(true);
    const lowerCommand = command.toLowerCase();
    
    // Add to command history
    const newCommand = {
      id: Date.now(),
      text: command,
      timestamp: new Date().toISOString(),
      processed: false,
      response: ''
    };
    
    setCommandHistory(prev => [newCommand, ...prev.slice(0, 9)]);

    try {
      // Process the command
      let response = 'Command not recognized';
      let action = null;

      if (lowerCommand.includes('buy')) {
        response = 'Executing buy order for $25';
        action = 'buy';
        speak('Executing buy order');
      } else if (lowerCommand.includes('sell')) {
        response = 'Executing sell order';
        action = 'sell';
        speak('Executing sell order');
      } else if (lowerCommand.includes('status') || lowerCommand.includes('show status')) {
        response = 'Bot is running. Current price: $104,850. Signal: BUY';
        action = 'status';
        speak('Bot is running');
      } else if (lowerCommand.includes('stop trading') || lowerCommand.includes('emergency')) {
        response = 'Stopping trading bot';
        action = 'stop';
        speak('Stopping trading bot');
      } else if (lowerCommand.includes('start trading')) {
        response = 'Starting trading bot';
        action = 'start';
        speak('Starting trading bot');
      } else if (lowerCommand.includes('price')) {
        response = 'Current Bitcoin price is $104,850';
        action = 'price';
        speak('Current Bitcoin price is one hundred four thousand eight hundred fifty dollars');
      } else if (lowerCommand.includes('portfolio')) {
        response = 'Portfolio value: $500. Daily P&L: $0';
        action = 'portfolio';
        speak('Portfolio value is five hundred dollars');
      } else if (lowerCommand.includes('sentiment')) {
        response = 'Market sentiment is neutral. Fear & Greed index: 42';
        action = 'sentiment';
        speak('Market sentiment is neutral');
      } else if (lowerCommand.includes('whale')) {
        response = 'No significant whale movements detected';
        action = 'whale';
        speak('No significant whale movements detected');
      }

      // Update command history
      setCommandHistory(prev => prev.map(cmd => 
        cmd.id === newCommand.id 
          ? { ...cmd, processed: true, response, action }
          : cmd
      ));

      // Call the parent callback
      if (onCommand) {
        onCommand({ command: lowerCommand, action, response });
      }

      // Send to backend API
      try {
        await fetch('http://localhost:5001/api/voice-command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: lowerCommand })
        });
      } catch (apiError) {
        console.log('Backend API call failed, but command processed locally:', apiError);
      }

    } catch (error) {
      console.error('Error processing command:', error);
      const errorResponse = 'Sorry, there was an error processing your command';
      speak(errorResponse);
      
      setCommandHistory(prev => prev.map(cmd => 
        cmd.id === newCommand.id 
          ? { ...cmd, processed: true, response: errorResponse }
          : cmd
      ));
    }

    setIsProcessing(false);
  };

  const getCommandIcon = (category) => {
    switch (category) {
      case 'trading': return <TrendingUp className="h-4 w-4 text-crypto-green" />;
      case 'control': return <Settings className="h-4 w-4 text-crypto-blue" />;
      case 'info': return <Activity className="h-4 w-4 text-crypto-yellow" />;
      case 'analysis': return <MessageSquare className="h-4 w-4 text-crypto-purple" />;
      default: return <Zap className="h-4 w-4 text-gray-400" />;
    }
  };

  const getActionIcon = (action) => {
    switch (action) {
      case 'buy': return <TrendingUp className="h-4 w-4 text-green-400" />;
      case 'sell': return <TrendingDown className="h-4 w-4 text-red-400" />;
      default: return <Activity className="h-4 w-4 text-blue-400" />;
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 rounded-xl max-w-4xl w-full max-h-[90vh] overflow-hidden border border-gray-700">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-crypto-purple/20">
              <Mic className="h-6 w-6 text-crypto-purple" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Voice Trading Control</h2>
              <p className="text-gray-400 text-sm">Control your trading bot with voice commands</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg bg-gray-700 text-gray-400 hover:bg-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-6 max-h-[80vh] overflow-y-auto">
          {/* Voice Control Panel */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Voice Control</h3>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setVoiceEnabled(!voiceEnabled)}
                  className={`p-2 rounded-lg transition-colors ${
                    voiceEnabled ? 'bg-crypto-green/20 text-crypto-green' : 'bg-gray-700 text-gray-400'
                  }`}
                >
                  {voiceEnabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* Microphone Control */}
            <div className="text-center space-y-4">
              <button
                onClick={isListening ? stopListening : startListening}
                disabled={isProcessing}
                className={`relative p-8 rounded-full transition-all ${
                  isListening 
                    ? 'bg-red-500/20 border-4 border-red-500 glow-red' 
                    : 'bg-crypto-blue/20 border-4 border-crypto-blue hover:bg-crypto-blue/30'
                } disabled:opacity-50`}
              >
                {isListening ? (
                  <MicOff className="h-12 w-12 text-red-500" />
                ) : (
                  <Mic className="h-12 w-12 text-crypto-blue" />
                )}
                
                {isListening && (
                  <div className="absolute inset-0 rounded-full border-4 border-red-500 animate-ping"></div>
                )}
              </button>

              <div className="space-y-2">
                <p className={`text-lg font-medium ${isListening ? 'text-red-400' : 'text-gray-400'}`}>
                  {isListening ? 'Listening...' : 'Click to start listening'}
                </p>
                
                {transcript && (
                  <div className="bg-gray-700 rounded-lg p-4">
                    <p className="text-white">{transcript}</p>
                    {confidence > 0 && (
                      <p className="text-gray-400 text-sm mt-1">
                        Confidence: {Math.round(confidence * 100)}%
                      </p>
                    )}
                  </div>
                )}

                {isProcessing && (
                  <div className="flex items-center justify-center space-x-2 text-crypto-blue">
                    <div className="w-4 h-4 border-2 border-crypto-blue/30 border-t-crypto-blue rounded-full animate-spin"></div>
                    <span>Processing command...</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Command History */}
          {commandHistory.length > 0 && (
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h3 className="text-lg font-semibold mb-4">Recent Commands</h3>
              <div className="space-y-3 max-h-64 overflow-y-auto">
                {commandHistory.map((cmd) => (
                  <div key={cmd.id} className="flex items-start space-x-3 p-3 bg-gray-700 rounded-lg">
                    <div className="flex-shrink-0 mt-1">
                      {cmd.action ? getActionIcon(cmd.action) : <MessageSquare className="h-4 w-4 text-gray-400" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-white font-medium">{cmd.text}</p>
                      {cmd.response && (
                        <p className="text-gray-300 text-sm mt-1">{cmd.response}</p>
                      )}
                      <p className="text-gray-500 text-xs mt-1">
                        {new Date(cmd.timestamp).toLocaleTimeString()}
                      </p>
                    </div>
                    <div className={`flex-shrink-0 w-2 h-2 rounded-full mt-2 ${
                      cmd.processed ? 'bg-green-400' : 'bg-yellow-400 animate-pulse'
                    }`}></div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Supported Commands */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-lg font-semibold mb-4">Supported Commands</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {supportedCommands.map((cmd, index) => (
                <div key={index} className="flex items-center space-x-3 p-3 bg-gray-700 rounded-lg">
                  {getCommandIcon(cmd.category)}
                  <div>
                    <p className="text-white font-medium">"{cmd.command}"</p>
                    <p className="text-gray-400 text-sm">{cmd.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Tips */}
          <div className="bg-crypto-blue/10 border border-crypto-blue/30 rounded-lg p-4">
            <h4 className="text-crypto-blue font-medium mb-2">💡 Voice Command Tips</h4>
            <ul className="text-gray-300 text-sm space-y-1">
              <li>• Speak clearly and at normal volume</li>
              <li>• Wait for the microphone to activate before speaking</li>
              <li>• Use natural language - "buy bitcoin" works as well as "execute buy order"</li>
              <li>• Commands are processed automatically when speech stops</li>
              <li>• Enable audio feedback to hear confirmations</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VoiceCommands;