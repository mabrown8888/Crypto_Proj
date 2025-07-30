import React, { useState } from 'react';
import { 
  Bell, 
  BellOff, 
  X, 
  Volume2, 
  VolumeX,
  Smartphone,
  Mail,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  DollarSign,
  Target
} from 'lucide-react';

const NotificationsModal = ({ onClose = () => {} }) => {
  const [notifications, setNotifications] = useState({
    enabled: true,
    sound: true,
    browser: true,
    email: false,
    trading: {
      orders: true,
      fills: true,
      failures: true,
      portfolio: true
    },
    market: {
      priceAlerts: true,
      volatility: true,
      news: false,
      sentiment: true
    },
    system: {
      botStatus: true,
      connections: true,
      errors: true
    }
  });

  const updateNotification = (category, key, value) => {
    if (category) {
      setNotifications(prev => ({
        ...prev,
        [category]: {
          ...prev[category],
          [key]: value
        }
      }));
    } else {
      setNotifications(prev => ({
        ...prev,
        [key]: value
      }));
    }
  };

  const NotificationToggle = ({ enabled, onChange, label, description, icon: Icon }) => (
    <div className="flex items-center justify-between p-4 bg-gray-800 rounded-lg">
      <div className="flex items-center space-x-3">
        <Icon className="h-5 w-5 text-gray-400" />
        <div>
          <h4 className="font-medium text-white">{label}</h4>
          <p className="text-sm text-gray-400">{description}</p>
        </div>
      </div>
      <button
        onClick={() => onChange(!enabled)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          enabled ? 'bg-crypto-blue' : 'bg-gray-600'
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            enabled ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );

  return (
    <div 
      className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-gray-900 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-hidden border border-gray-700">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-crypto-yellow/20">
              <Bell className="h-6 w-6 text-crypto-yellow" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Notifications</h2>
              <p className="text-gray-400 text-sm">Manage your trading alerts and notifications</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-3 rounded-lg bg-red-600 hover:bg-red-700 text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-6 max-h-[80vh] overflow-y-auto">
          {/* General Settings */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white">General Settings</h3>
            
            <NotificationToggle
              enabled={notifications.enabled}
              onChange={(value) => updateNotification(null, 'enabled', value)}
              label="Enable Notifications"
              description="Turn all notifications on or off"
              icon={notifications.enabled ? Bell : BellOff}
            />

            <NotificationToggle
              enabled={notifications.sound}
              onChange={(value) => updateNotification(null, 'sound', value)}
              label="Sound Alerts"
              description="Play sound for important notifications"
              icon={notifications.sound ? Volume2 : VolumeX}
            />

            <NotificationToggle
              enabled={notifications.browser}
              onChange={(value) => updateNotification(null, 'browser', value)}
              label="Browser Notifications"
              description="Show desktop notifications in browser"
              icon={Smartphone}
            />

            <NotificationToggle
              enabled={notifications.email}
              onChange={(value) => updateNotification(null, 'email', value)}
              label="Email Notifications"
              description="Send important alerts to your email"
              icon={Mail}
            />
          </div>

          {/* Trading Notifications */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white">Trading Notifications</h3>
            
            <NotificationToggle
              enabled={notifications.trading.orders}
              onChange={(value) => updateNotification('trading', 'orders', value)}
              label="Order Notifications"
              description="Alerts when orders are placed or modified"
              icon={Target}
            />

            <NotificationToggle
              enabled={notifications.trading.fills}
              onChange={(value) => updateNotification('trading', 'fills', value)}
              label="Order Fills"
              description="Notify when orders are executed"
              icon={TrendingUp}
            />

            <NotificationToggle
              enabled={notifications.trading.failures}
              onChange={(value) => updateNotification('trading', 'failures', value)}
              label="Trade Failures"
              description="Alert on failed or rejected orders"
              icon={AlertTriangle}
            />

            <NotificationToggle
              enabled={notifications.trading.portfolio}
              onChange={(value) => updateNotification('trading', 'portfolio', value)}
              label="Portfolio Changes"
              description="Notify on significant portfolio value changes"
              icon={DollarSign}
            />
          </div>

          {/* Market Notifications */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white">Market Notifications</h3>
            
            <NotificationToggle
              enabled={notifications.market.priceAlerts}
              onChange={(value) => updateNotification('market', 'priceAlerts', value)}
              label="Price Alerts"
              description="Notify on significant price movements"
              icon={TrendingUp}
            />

            <NotificationToggle
              enabled={notifications.market.volatility}
              onChange={(value) => updateNotification('market', 'volatility', value)}
              label="High Volatility"
              description="Alert during periods of high market volatility"
              icon={TrendingDown}
            />

            <NotificationToggle
              enabled={notifications.market.sentiment}
              onChange={(value) => updateNotification('market', 'sentiment', value)}
              label="Sentiment Changes"
              description="Notify on major sentiment shifts"
              icon={AlertTriangle}
            />
          </div>

          {/* System Notifications */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white">System Notifications</h3>
            
            <NotificationToggle
              enabled={notifications.system.botStatus}
              onChange={(value) => updateNotification('system', 'botStatus', value)}
              label="Bot Status"
              description="Notify when bot connects or disconnects"
              icon={AlertTriangle}
            />

            <NotificationToggle
              enabled={notifications.system.connections}
              onChange={(value) => updateNotification('system', 'connections', value)}
              label="Connection Issues"
              description="Alert on API or network connection problems"
              icon={AlertTriangle}
            />

            <NotificationToggle
              enabled={notifications.system.errors}
              onChange={(value) => updateNotification('system', 'errors', value)}
              label="System Errors"
              description="Notify on critical system errors"
              icon={AlertTriangle}
            />
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end space-x-3 pt-4 border-t border-gray-700">
            <button
              onClick={onClose}
              className="px-6 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                console.log('Saving notification settings:', notifications);
                onClose();
              }}
              className="px-6 py-2 bg-crypto-blue text-white rounded-lg hover:bg-crypto-blue/80 transition-colors"
            >
              Save Settings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NotificationsModal;