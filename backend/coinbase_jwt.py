import jwt
import time
import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from urllib.parse import urlencode

class CoinbaseJWTGenerator:
    """Generate JWT tokens for Coinbase Advanced Trade API authentication"""
    
    def __init__(self, api_key=None, api_secret=None):
        self.api_key = api_key or os.getenv('COINBASE_API_KEY')
        self.api_secret = api_secret or os.getenv('COINBASE_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Coinbase API key and secret are required")
    
    def _load_private_key(self):
        """Load the private key from the API secret"""
        try:
            # Handle the key format from environment variable
            private_key_str = self.api_secret.replace('\\n', '\n')
            
            # Load the private key
            private_key = serialization.load_pem_private_key(
                private_key_str.encode(),
                password=None
            )
            return private_key
        except Exception as e:
            raise ValueError(f"Failed to load private key: {e}")
    
    def build_jwt(self, method, path, body=""):
        """
        Build JWT token for Coinbase API request
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path (e.g., "/api/v3/brokerage/orders")
            body: Request body (for POST/PUT requests)
        
        Returns:
            JWT token string
        """
        private_key = self._load_private_key()
        
        # Current time
        now = int(time.time())
        
        # JWT payload
        payload = {
            'sub': self.api_key,
            'iss': "cdp", 
            'nbf': now,
            'exp': now + 120,  # Expires in 2 minutes
            'aud': ["retail_rest_api_proxy"],
        }
        
        # Create URI for signing - Coinbase format
        # Format: "METHOD hostname/path" (no body in URI for Coinbase)
        uri = f"{method} api.coinbase.com{path}"
        payload['uri'] = uri
        
        # Generate JWT token using ES256 algorithm
        token = jwt.encode(
            payload, 
            private_key, 
            algorithm='ES256',
            headers={'kid': self.api_key}
        )
        
        return token
    
    def get_headers(self, method, path, body=""):
        """
        Get headers for Coinbase API request
        
        Args:
            method: HTTP method
            path: API endpoint path
            body: Request body
            
        Returns:
            Dictionary of headers
        """
        jwt_token = self.build_jwt(method, path, body)
        
        return {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }

# Convenience functions
def get_coinbase_headers(method, path, body=""):
    """Get authenticated headers for Coinbase API request"""
    generator = CoinbaseJWTGenerator()
    return generator.get_headers(method, path, body)

def build_coinbase_jwt(method, path, body=""):
    """Build JWT token for Coinbase API request"""
    generator = CoinbaseJWTGenerator()
    return generator.build_jwt(method, path, body)