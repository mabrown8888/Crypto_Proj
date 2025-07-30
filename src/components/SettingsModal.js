import React, { useState } from 'react';
import { 
  Settings, 
  X, 
  Palette,
  Globe,
  Shield,
  Database,
  Zap,
  DollarSign,
  Clock,
  Monitor,
  Smartphone,
  Key,
  AlertCircle,
  Save,
  RefreshCw
} from 'lucide-react';

const SettingsModal = ({ onClose = () => {} }) => {
  const [settings, setSettings] = useState({
    // Display Settings
    theme: 'dark',
    currency: 'USD',
    timezone: 'UTC',
    dateFormat: 'MM/DD/YYYY',
    numberFormat: 'en-US',
    
    // Trading Settings
    defaultOrderSize: 25,
    riskPercentage: 2,
    stopLossPercentage: 5,
    takeProfitPercentage: 10,
    autoConfirmOrders: false,
    
    // API Settings
    apiTimeout: 30,
    retryAttempts: 3,
    rateLimitBuffer: 100,
    
    // Performance Settings
    updateInterval: 5,
    chartDataPoints: 100,
    cacheEnabled: true,
    
    // Security Settings
    sessionTimeout: 60,
    requireConfirmation: true,
    logLevel: 'info'
  });

  const updateSetting = (key, value) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const SettingRow = ({ label, description, children }) => (
    <div className="flex items-center justify-between p-4 bg-gray-800 rounded-lg">
      <div className="flex-1">
        <h4 className="font-medium text-white">{label}</h4>
        <p className="text-sm text-gray-400">{description}</p>
      </div>
      <div className="ml-4">
        {children}
      </div>
    </div>
  );

  const Toggle = ({ enabled, onChange }) => (
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
  );

  const Select = ({ value, onChange, options }) => (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-gray-700 text-white px-3 py-2 rounded-lg border border-gray-600 focus:border-crypto-blue focus:outline-none"
    >
      {options.map(option => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );

  const NumberInput = ({ value, onChange, min, max, step = 1 }) => (
    <input
      type="number"
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      min={min}
      max={max}
      step={step}
      className="bg-gray-700 text-white px-3 py-2 rounded-lg border border-gray-600 focus:border-crypto-blue focus:outline-none w-24"
    />
  );

  const resetToDefaults = () => {
    if (window.confirm('Reset all settings to default values?')) {
      setSettings({
        theme: 'dark',
        currency: 'USD',
        timezone: 'UTC',
        dateFormat: 'MM/DD/YYYY',
        numberFormat: 'en-US',
        defaultOrderSize: 25,
        riskPercentage: 2,
        stopLossPercentage: 5,
        takeProfitPercentage: 10,
        autoConfirmOrders: false,
        apiTimeout: 30,
        retryAttempts: 3,
        rateLimitBuffer: 100,
        updateInterval: 5,
        chartDataPoints: 100,
        cacheEnabled: true,
        sessionTimeout: 60,
        requireConfirmation: true,
        logLevel: 'info'
      });
    }
  };

  const saveSettings = () => {
    // Save to localStorage or send to backend
    localStorage.setItem('tradingBotSettings', JSON.stringify(settings));
    console.log('Settings saved:', settings);
    onClose();
  };

  return (
    <div 
      className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-gray-900 rounded-xl max-w-4xl w-full max-h-[90vh] overflow-hidden border border-gray-700">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-crypto-purple/20">
              <Settings className="h-6 w-6 text-crypto-purple" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Settings</h2>
              <p className="text-gray-400 text-sm">Configure your trading bot preferences</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={resetToDefaults}
              className="p-2 rounded-lg bg-gray-700 text-gray-400 hover:bg-gray-600 transition-colors"
              title="Reset to defaults"
            >
              <RefreshCw className="h-5 w-5" />
            </button>
            <button
              onClick={onClose}
              className="p-3 rounded-lg bg-red-600 hover:bg-red-700 text-white transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-8 max-h-[80vh] overflow-y-auto">
          {/* Display Settings */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
              <Palette className="h-5 w-5 text-crypto-blue" />
              <span>Display Settings</span>
            </h3>
            
            <SettingRow
              label="Theme"
              description="Choose your preferred color scheme"
            >
              <Select
                value={settings.theme}
                onChange={(value) => updateSetting('theme', value)}
                options={[
                  { value: 'dark', label: 'Dark' },
                  { value: 'light', label: 'Light' },
                  { value: 'auto', label: 'Auto' }
                ]}
              />
            </SettingRow>

            <SettingRow
              label="Currency"
              description="Primary currency for display"
            >
              <Select
                value={settings.currency}
                onChange={(value) => updateSetting('currency', value)}
                options={[
                  { value: 'USD', label: 'USD' },
                  { value: 'EUR', label: 'EUR' },
                  { value: 'GBP', label: 'GBP' },
                  { value: 'JPY', label: 'JPY' }
                ]}
              />
            </SettingRow>

            <SettingRow
              label="Timezone"
              description="Display timezone for timestamps"
            >
              <Select
                value={settings.timezone}
                onChange={(value) => updateSetting('timezone', value)}
                options={[
                  { value: 'UTC', label: 'UTC' },
                  { value: 'America/New_York', label: 'Eastern' },
                  { value: 'America/Chicago', label: 'Central' },
                  { value: 'America/Los_Angeles', label: 'Pacific' }
                ]}
              />
            </SettingRow>
          </div>

          {/* Trading Settings */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
              <DollarSign className="h-5 w-5 text-crypto-green" />
              <span>Trading Settings</span>
            </h3>
            
            <SettingRow
              label="Default Order Size"
              description="Default amount in USD for new orders"
            >
              <div className="flex items-center space-x-2">
                <span className="text-gray-400">$</span>
                <NumberInput
                  value={settings.defaultOrderSize}
                  onChange={(value) => updateSetting('defaultOrderSize', value)}
                  min={1}
                  max={10000}
                />
              </div>
            </SettingRow>

            <SettingRow
              label="Risk Percentage"
              description="Maximum risk per trade as percentage of portfolio"
            >
              <div className="flex items-center space-x-2">
                <NumberInput
                  value={settings.riskPercentage}
                  onChange={(value) => updateSetting('riskPercentage', value)}
                  min={0.1}
                  max={10}
                  step={0.1}
                />
                <span className="text-gray-400">%</span>
              </div>
            </SettingRow>

            <SettingRow
              label="Stop Loss Percentage"
              description="Default stop loss percentage"
            >
              <div className="flex items-center space-x-2">
                <NumberInput
                  value={settings.stopLossPercentage}
                  onChange={(value) => updateSetting('stopLossPercentage', value)}
                  min={0.5}
                  max={20}
                  step={0.5}
                />
                <span className="text-gray-400">%</span>
              </div>
            </SettingRow>

            <SettingRow
              label="Auto-Confirm Orders"
              description="Automatically confirm orders without manual approval"
            >
              <Toggle
                enabled={settings.autoConfirmOrders}
                onChange={(value) => updateSetting('autoConfirmOrders', value)}
              />
            </SettingRow>
          </div>

          {/* API Settings */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
              <Key className="h-5 w-5 text-crypto-yellow" />
              <span>API Settings</span>
            </h3>
            
            <SettingRow
              label="API Timeout"
              description="Request timeout in seconds"
            >
              <div className="flex items-center space-x-2">
                <NumberInput
                  value={settings.apiTimeout}
                  onChange={(value) => updateSetting('apiTimeout', value)}
                  min={5}
                  max={120}
                />
                <span className="text-gray-400">sec</span>
              </div>
            </SettingRow>

            <SettingRow
              label="Retry Attempts"
              description="Number of retry attempts for failed requests"
            >
              <NumberInput
                value={settings.retryAttempts}
                onChange={(value) => updateSetting('retryAttempts', value)}
                min={0}
                max={10}
              />
            </SettingRow>
          </div>

          {/* Performance Settings */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
              <Zap className="h-5 w-5 text-crypto-purple" />
              <span>Performance Settings</span>
            </h3>
            
            <SettingRow
              label="Update Interval"
              description="How often to refresh data (seconds)"
            >
              <div className="flex items-center space-x-2">
                <NumberInput
                  value={settings.updateInterval}
                  onChange={(value) => updateSetting('updateInterval', value)}
                  min={1}
                  max={60}
                />
                <span className="text-gray-400">sec</span>
              </div>
            </SettingRow>

            <SettingRow
              label="Chart Data Points"
              description="Maximum number of data points on charts"
            >
              <NumberInput
                value={settings.chartDataPoints}
                onChange={(value) => updateSetting('chartDataPoints', value)}
                min={50}
                max={1000}
                step={50}
              />
            </SettingRow>

            <SettingRow
              label="Enable Caching"
              description="Cache API responses to improve performance"
            >
              <Toggle
                enabled={settings.cacheEnabled}
                onChange={(value) => updateSetting('cacheEnabled', value)}
              />
            </SettingRow>
          </div>

          {/* Security Settings */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
              <Shield className="h-5 w-5 text-red-400" />
              <span>Security Settings</span>
            </h3>
            
            <SettingRow
              label="Session Timeout"
              description="Auto-logout after inactivity (minutes)"
            >
              <div className="flex items-center space-x-2">
                <NumberInput
                  value={settings.sessionTimeout}
                  onChange={(value) => updateSetting('sessionTimeout', value)}
                  min={5}
                  max={480}
                />
                <span className="text-gray-400">min</span>
              </div>
            </SettingRow>

            <SettingRow
              label="Require Confirmation"
              description="Require confirmation for high-risk actions"
            >
              <Toggle
                enabled={settings.requireConfirmation}
                onChange={(value) => updateSetting('requireConfirmation', value)}
              />
            </SettingRow>

            <SettingRow
              label="Log Level"
              description="System logging verbosity"
            >
              <Select
                value={settings.logLevel}
                onChange={(value) => updateSetting('logLevel', value)}
                options={[
                  { value: 'error', label: 'Error Only' },
                  { value: 'warn', label: 'Warnings' },
                  { value: 'info', label: 'Info' },
                  { value: 'debug', label: 'Debug' }
                ]}
              />
            </SettingRow>
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
              onClick={saveSettings}
              className="px-6 py-2 bg-crypto-blue text-white rounded-lg hover:bg-crypto-blue/80 transition-colors flex items-center space-x-2"
            >
              <Save className="h-4 w-4" />
              <span>Save Settings</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;