/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
    extend: {
      colors: {
        'crypto-dark': '#0B1426',
        'crypto-blue': '#1E40AF',
        'crypto-green': '#10B981',
        'crypto-red': '#EF4444',
        'crypto-yellow': '#F59E0B',
        'crypto-purple': '#8B5CF6'
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bounce-slow': 'bounce 2s infinite',
      }
    },
  },
  plugins: [],
}