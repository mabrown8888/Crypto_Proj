#!/usr/bin/env python3
"""
Test what accounts API returns
"""
import os
from dotenv import load_dotenv
load_dotenv()

from coinbase.rest import RESTClient

api_key = os.getenv('COINBASE_API_KEY')
api_secret = os.getenv('COINBASE_API_SECRET')

print("=" * 80)
print("TESTING COINBASE get_accounts() API")
print("=" * 80)

client = RESTClient(api_key=api_key, api_secret=api_secret)

try:
    accounts = client.get_accounts()
    print(f"\nAPI Response Type: {type(accounts)}")
    print(f"Has 'accounts' attribute: {hasattr(accounts, 'accounts')}")
    
    if hasattr(accounts, 'accounts'):
        print(f"\nTotal accounts returned: {len(accounts.accounts)}\n")
        
        for i, account in enumerate(accounts.accounts):
            print(f"Account #{i+1}:")
            print(f"  Type: {type(account)}")
            print(f"  Currency: {getattr(account, 'currency', 'N/A')}")
            
            # Try different balance fields
            if hasattr(account, 'available_balance'):
                avail_bal = account.available_balance
                print(f"  Available Balance Type: {type(avail_bal)}")
                if hasattr(avail_bal, 'value'):
                    print(f"  Available Balance Value: {avail_bal.value}")
                else:
                    print(f"  Available Balance: {avail_bal}")
            
            # Check for other balance fields
            if hasattr(account, 'balance'):
                print(f"  Balance: {account.balance}")
            
            # Print all attributes
            print(f"  All attributes: {dir(account)}")
            print()
            
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
