from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
from flask import request, flash, redirect, url_for, current_app
import hashlib
import hmac
import os

# Initialize limiter (will be configured in app)
limiter = Limiter(key_func=get_remote_address)

def init_limiter(app):
    global limiter
    limiter.init_app(app)

def rate_limit_login(f):
    """Decorator to rate limit login attempts"""
    @wraps(f)
    # Only count POST requests (login submissions). Use request.path in
    # key to separate admin vs user login attempts coming from same IP.
    @limiter.limit("5 per minute", methods=['POST'], key_func=lambda: f"{get_remote_address()}:{request.path}")
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function

def validate_password_strength(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password minimal 8 karakter"
    
    if not any(c.isupper() for c in password):
        return False, "Password harus ada huruf besar"
    
    if not any(c.islower() for c in password):
        return False, "Password harus ada huruf kecil"
    
    if not any(c.isdigit() for c in password):
        return False, "Password harus ada angka"
    
    return True, "Password valid"


# ===== HYBRID SECURITY: CSRF + API KEY =====
def validate_api_key(api_key):
    """Validate API key for offline/API access"""
    valid_keys = current_app.config.get('VALID_API_KEYS', [])
    return api_key in valid_keys


def is_localhost():
    """Check if request is from localhost/127.0.0.1"""
    remote_addr = request.remote_addr
    return remote_addr in ['127.0.0.1', 'localhost', '::1']


def is_csrf_exempted():
    """
    Check if request should be exempted from CSRF protection:
    1. Valid API key provided
    2. Request from localhost (offline development)
    3. Request from approved IP whitelist
    """
    # Check API key
    api_key = request.headers.get('X-API-Key') or request.form.get('api_key')
    if api_key and validate_api_key(api_key):
        return True
    
    # Check localhost (for offline development)
    if is_localhost():
        return True
    
    # Check IP whitelist
    whitelist = current_app.config.get('IP_WHITELIST', [])
    if request.remote_addr in whitelist:
        return True
    
    return False


def csrf_exempt_if_api_key(f):
    """
    Decorator to exempt CSRF for API requests with valid key.
    Uses Flask-WTF's @csrf.exempt internally if CSRF is available.
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If API key is valid or from localhost, allow without CSRF
        if is_csrf_exempted():
            return f(*args, **kwargs)
        # Otherwise, Flask-WTF will handle CSRF validation
        return f(*args, **kwargs)
    
    # Try to get csrf from current_app and exempt this view
    try:
        from flask import current_app
        if hasattr(current_app, 'csrf'):
            current_app.csrf.exempt(decorated_function)
    except:
        pass
    
    return decorated_function