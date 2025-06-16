#!/usr/bin/env python3
"""Test script to verify backend integration"""

import requests
import json

def test_backend():
    base_url = "http://localhost:5001"
    
    print("Testing AI Trading Co-Pilot Backend...")
    
    # Test bot status endpoint
    try:
        response = requests.get(f"{base_url}/api/bot/status")
        if response.status_code == 200:
            data = response.json()
            print("✅ Bot Status API working")
            print(f"   Current Price: ${data.get('current_price', 'N/A')}")
            print(f"   Connected: {data.get('connected', 'N/A')}")
            print(f"   Signal: {data.get('signal', 'N/A')}")
        else:
            print(f"❌ Bot Status API failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Bot Status API error: {e}")
    
    # Test sentiment endpoint
    try:
        response = requests.get(f"{base_url}/api/sentiment")
        if response.status_code == 200:
            data = response.json()
            print("✅ Sentiment API working")
            print(f"   Fear & Greed Index: {data.get('fear_greed_index', 'N/A')}")
        else:
            print(f"❌ Sentiment API failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Sentiment API error: {e}")
    
    # Test whale endpoint
    try:
        response = requests.get(f"{base_url}/api/whales")
        if response.status_code == 200:
            print("✅ Whale API working")
        else:
            print(f"❌ Whale API failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Whale API error: {e}")

if __name__ == "__main__":
    test_backend()