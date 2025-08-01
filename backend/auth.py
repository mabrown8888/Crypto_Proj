import jwt
import bcrypt
import os
import json
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app

# Simple user storage (in production, use a proper database)
USERS_FILE = 'users.json'

def load_users():
    """Load users from JSON file"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_users(users):
    """Save users to JSON file"""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        print(f"Error saving users: {e}")

def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_token(user_id):
    """Generate JWT token for user"""
    # Try to load from environment first, then parent directory .env
    from dotenv import load_dotenv
    load_dotenv('../.env')
    
    secret_key = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-this')
    
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=24),  # Token expires in 24 hours
        'iat': datetime.utcnow()
    }
    
    return jwt.encode(payload, secret_key, algorithm='HS256')

def verify_token(token):
    """Verify JWT token and return user_id"""
    try:
        # Try to load from environment first, then parent directory .env
        from dotenv import load_dotenv
        load_dotenv('../.env')
        
        secret_key = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-this')
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def token_required(f):
    """Decorator to require JWT token for routes"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        # Verify token
        user_id = verify_token(token)
        if user_id is None:
            return jsonify({'error': 'Token is invalid or expired'}), 401
        
        # Add user_id to request context
        request.current_user_id = user_id
        return f(*args, **kwargs)
    
    return decorated

def register_user(username, password, email=None):
    """Register a new user"""
    users = load_users()
    
    if username in users:
        return {'success': False, 'error': 'Username already exists'}
    
    hashed_password = hash_password(password)
    users[username] = {
        'password': hashed_password,
        'email': email,
        'created_at': datetime.utcnow().isoformat()
    }
    
    save_users(users)
    return {'success': True, 'message': 'User registered successfully'}

def authenticate_user(username, password):
    """Authenticate user and return JWT token"""
    users = load_users()
    
    if username not in users:
        return {'success': False, 'error': 'Invalid username or password'}
    
    user = users[username]
    if not verify_password(password, user['password']):
        return {'success': False, 'error': 'Invalid username or password'}
    
    token = generate_token(username)
    return {
        'success': True,
        'token': token,
        'username': username,
        'expires_in': 24 * 3600  # 24 hours in seconds
    }

def refresh_token(old_token):
    """Refresh JWT token"""
    user_id = verify_token(old_token)
    if user_id is None:
        return {'success': False, 'error': 'Invalid or expired token'}
    
    new_token = generate_token(user_id)
    return {
        'success': True,
        'token': new_token,
        'expires_in': 24 * 3600
    }