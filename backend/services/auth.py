"""
Authentication Module
Handles user authentication, session management, and authorization
"""

import json
import hashlib
import secrets
import time
import os
from pathlib import Path

# Session storage (in production, use Redis or database)
active_sessions = {}
failed_attempts = {}

# Load auth configuration
def load_auth_config():
    """Load authentication configuration from auth.json"""
    # Auth file is in project root (parent of backend/)
    auth_file = Path(__file__).parent.parent.parent / "auth.json"
    
    if not auth_file.exists():
        # Create default auth.json if not exists
        default_config = {
            "users": [
                {
                    "username": "admin",
                    "password": "admin123",
                    "role": "admin"
                }
            ],
            "session": {
                "timeout": 3600,
                "secret_key": "change-this-to-a-secure-random-string"
            },
            "security": {
                "max_login_attempts": 5,
                "lockout_duration": 300
            }
        }
        with open(auth_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        return default_config
    
    with open(auth_file, 'r') as f:
        return json.load(f)


def hash_password(password):
    """Hash password using SHA-256 (in production, use bcrypt or argon2)"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_credentials(username, password):
    """Verify username and password against auth.json"""
    config = load_auth_config()
    
    for user in config.get('users', []):
        if user['username'] == username:
            # Support both plain text (for backward compatibility) and hashed passwords
            stored_password = user['password']
            
            # Check if password is already hashed (64 chars for SHA-256)
            if len(stored_password) == 64:
                return stored_password == hash_password(password)
            else:
                # Plain text comparison
                return stored_password == password
    
    return False


def get_user_info(username):
    """Get user information"""
    config = load_auth_config()
    
    for user in config.get('users', []):
        if user['username'] == username:
            return {
                'username': user['username'],
                'role': user.get('role', 'user')
            }
    
    return None


def check_login_attempts(username):
    """Check if user is locked out due to failed attempts"""
    config = load_auth_config()
    security = config.get('security', {})
    max_attempts = security.get('max_login_attempts', 5)
    lockout_duration = security.get('lockout_duration', 300)
    
    if username not in failed_attempts:
        return True
    
    attempts, last_attempt_time = failed_attempts[username]
    
    # Check if lockout period has passed
    if time.time() - last_attempt_time > lockout_duration:
        del failed_attempts[username]
        return True
    
    # Check if max attempts exceeded
    if attempts >= max_attempts:
        return False
    
    return True


def record_failed_attempt(username):
    """Record a failed login attempt"""
    if username not in failed_attempts:
        failed_attempts[username] = [1, time.time()]
    else:
        attempts, _ = failed_attempts[username]
        failed_attempts[username] = [attempts + 1, time.time()]


def clear_failed_attempts(username):
    """Clear failed login attempts after successful login"""
    if username in failed_attempts:
        del failed_attempts[username]


def create_session(username):
    """Create a new session for authenticated user"""
    session_token = secrets.token_urlsafe(32)
    config = load_auth_config()
    timeout = config.get('session', {}).get('timeout', 3600)
    
    active_sessions[session_token] = {
        'username': username,
        'created_at': time.time(),
        'expires_at': time.time() + timeout,
        'user_info': get_user_info(username)
    }
    
    return session_token


def validate_session(session_token):
    """Validate session token and return user info if valid"""
    if not session_token or session_token not in active_sessions:
        return None
    
    session = active_sessions[session_token]
    
    # Check if session expired
    if time.time() > session['expires_at']:
        del active_sessions[session_token]
        return None
    
    # Extend session timeout on activity
    config = load_auth_config()
    timeout = config.get('session', {}).get('timeout', 3600)
    session['expires_at'] = time.time() + timeout
    
    return session['user_info']


def destroy_session(session_token):
    """Destroy a session (logout)"""
    if session_token in active_sessions:
        del active_sessions[session_token]
        return True
    return False


def authenticate_user(username, password):
    """
    Authenticate user and return session token if successful
    Returns: (success, session_token_or_error_message)
    """
    # Check if user is locked out
    if not check_login_attempts(username):
        config = load_auth_config()
        lockout_duration = config.get('security', {}).get('lockout_duration', 300)
        return False, f"Too many failed attempts. Try again in {lockout_duration // 60} minutes."
    
    # Verify credentials
    if verify_credentials(username, password):
        clear_failed_attempts(username)
        session_token = create_session(username)
        return True, session_token
    else:
        record_failed_attempt(username)
        return False, "Invalid username or password"
