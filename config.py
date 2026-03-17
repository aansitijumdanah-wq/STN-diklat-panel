"""
Production-optimized configuration untuk STN-DIKLAT application
"""
import os
from datetime import timedelta


class BaseConfig:
    """Base configuration"""
    
    # Flask core
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = False
    TESTING = False
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Database optimization - OPTIMIZED untuk performa
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 15,  # OPTIMIZED: 5 → 15 untuk menangani lebih banyak concurrent requests
        'pool_recycle': 1800,  # OPTIMIZED: 3600 → 1800 detik, hindari stale connections
        'pool_pre_ping': True,
        'max_overflow': 20,  # OPTIMIZED: 10 → 20, allow lebih banyak temp connections
        'connect_args': {
            'timeout': 30,
            'check_same_thread': False  # SQLite only
        }
    }
    
    # Upload configuration
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB max file size
    UPLOAD_FOLDER_SIZE_LIMIT = 1024 * 1024 * 1024  # 1 GB total upload folder
    
    # Cache settings for static files
    SEND_FILE_MAX_AGE_DEFAULT = 3600  # 1 hour static file cache
    
    # JWT/CSRF optimization
    CSRF_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_TIME_LIMIT = None  # No CSRF token expiry in this app
    WTF_CSRF_SSL_STRICT = False  # For GitHub Codespaces
    
    # Rate limiter settings (in-memory, change for production)
    RATELIMIT_STORAGE_URL = None  # In-memory storage (change to Redis for production)
    RATELIMIT_DEFAULT = "100/hour"  # Default rate limit
    RATELIMIT_STORAGE_OPTIONS = {}
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'logs/app.log'
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per log file
    LOG_BACKUP_COUNT = 5
    
    # API settings
    JSON_SORT_KEYS = False  # Don't sort JSON keys (faster)
    JSONIFY_PRETTYPRINT_REGULAR = False  # Disable pretty printing (faster)
    
    # Timeout settings
    REQUEST_TIMEOUT = 120  # 2 minute request timeout
    
    # Google Drive settings
    GDRIVE_BATCH_SIZE = 10  # Process in batches
    GDRIVE_API_TIMEOUT = 30  # 30 second API timeout
    
    # Chroma settings 
    CHROMA_LAZY_LOAD = True  # Lazy load embedding model
    CHROMA_BATCH_SIZE = 50  # Batch size for vector operations
    CHROMA_CACHE_COLLECTIONS = True  # Cache collection objects


class DevelopmentConfig(BaseConfig):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_ECHO = False
    SEND_FILE_MAX_AGE_DEFAULT = 0  # No caching in development
    LOG_LEVEL = 'DEBUG'
    TEMPLATES_AUTO_RELOAD = False  # Disable for efficiency


class ProductionConfig(BaseConfig):
    """Production configuration - OPTIMIZED untuk high traffic"""
    DEBUG = False
    TESTING = False
    # Override with environment variables
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 40,  # OPTIMIZED: 20 → 40 untuk production dengan traffic tinggi
        'pool_recycle': 1800,  # OPTIMIZED: 3600 → 1800 detik, hindari stale connections
        'pool_pre_ping': True,
        'max_overflow': 50,  # OPTIMIZED: 30 → 50 untuk production
        'connect_args': {'timeout': 30}
    }
    RATELIMIT_DEFAULT = "1000/hour"


class TestingConfig(BaseConfig):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    RATELIMIT_ENABLED = False
    WTF_CSRF_ENABLED = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env=None):
    """Get configuration based on environment"""
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default'])
