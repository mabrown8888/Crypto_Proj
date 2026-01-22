#!/usr/bin/env python3
"""
Quick live bot status checker
"""
import requests
import json
import sys
import os

# Load token for authentication
def get_token():
    token_file = os.path.expanduser('~/.trading_bot_token')
    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            return f.read().strip()
    
    # Try to get from recent login
    try:
        # Simulate a quick login to get token
        login_response = requests.post('http://localhost:5001/api/login', 
                                      json={'username': 'admin', 'password': 'admin123'})
        if login_response.ok:
            token = login_response.json().get('access_token')
            if token:
                with open(token_file, 'w') as f:
                    f.write(token)
                return token
    except:
        pass
    return None

def check_bot():
    print("🤖 LIVE BOT STATUS")
    print("=" * 60)
    
    token = get_token()
    if not token:
        print("❌ No authentication token. Please login first.")
        return
    
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        # Check bot monitor endpoint
        response = requests.get('http://localhost:5001/api/bot-monitor', headers=headers)
        
        if response.ok:
            data = response.json()
            print(f"✅ Bot Status: {data.get('status', 'unknown')}")
            print(f"📊 Strategy: {data.get('strategy', 'none')}")
            print(f"🔄 Thread Active: {data.get('thread_alive', False)}")
            print(f"📈 Price Points: {data.get('price_history_count', 0)}")
            
            if data.get('latest_price'):
                print(f"💰 Latest Price: ${data['latest_price']:,.2f}")
            
            if data.get('last_signal'):
                sig = data['last_signal']
                print(f"\n📊 Last Signal:")
                print(f"   Action: {sig.get('action', 'none')}")
                print(f"   Confidence: {sig.get('confidence', 0)*100:.1f}%")
                print(f"   Reason: {sig.get('reason', 'none')}")
            else:
                print("\n⏳ No signals yet (need more price data)")
            
            perf = data.get('performance', {})
            print(f"\n💼 Performance:")
            print(f"   Total Trades: {perf.get('totalTrades', 0)}")
            print(f"   Today's P&L: ${perf.get('todayPnL', 0):.2f}")
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Flask server. Is it running?")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_bot()