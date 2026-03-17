from flask import Flask
import os
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

def create_app():
    app = Flask(__name__)

    # Environment detection
    is_codespaces = 'GITHUB_CODESPACES_PORT' in os.environ
    is_production = os.getenv('FLASK_ENV') == 'production' and not is_codespaces
    is_development = not is_production

    print(f"Environment: {'Development' if is_development else 'Codespaces' if is_codespaces else 'Production'}")

    # Proxy fix for production behind nginx/load balancer
    # This properly handles X-Forwarded-For, X-Forwarded-Proto, etc.
    if is_production or os.getenv('ENABLE_PROXY_FIX', 'False').lower() == 'true':
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=int(os.getenv('PROXY_FIX_X_FOR', 1)),  # # of proxies for X-Forwarded-For
            x_proto=int(os.getenv('PROXY_FIX_X_PROTO', 1)),  # # of proxies for X-Forwarded-Proto
            x_host=int(os.getenv('PROXY_FIX_X_HOST', 1)),  # # of proxies for X-Forwarded-Host
            x_port=int(os.getenv('PROXY_FIX_X_PORT', 1))  # # of proxies for X-Forwarded-Port
        )
        print("✅ Reverse Proxy (ProxyFix) enabled - X-Forwarded-* headers will be processed")

    # SECRET_KEY configuration - Using a static key for development to ensure session stability.
    secret_key = os.getenv('SECRET_KEY', 'a-stable-development-secret-key')
    if 'dev-secret' in secret_key and is_production:
        raise ValueError("Cannot use development secret key in production!")

    app.config['SECRET_KEY'] = secret_key

    # Session configuration
    app.config['PERMANENT_SESSION_LIFETIME'] = 7200  # 2 hours
    app.config['SESSION_COOKIE_SECURE'] = is_production  # Secure cookie only in production
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Template configuration for development
    if is_development:
        # Enable auto-reload so template changes are reflected immediately during development
        app.config['TEMPLATES_AUTO_RELOAD'] = True
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600  # Cache static files 1 hour
        app.jinja_env.auto_reload = True

    # Database configuration with connection pooling
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 5,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 10
    }

    # Database configuration
    db_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'users.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Upload configuration
    upload_folder = os.path.join(os.path.dirname(__file__), '..', 'instance', 'uploads')
    upload_folder = os.path.abspath(upload_folder)
    app.config['UPLOAD_FOLDER'] = upload_folder
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB

    # API Keys Configuration (for offline/API access without CSRF)
    api_keys = os.getenv('API_KEYS', 'offline-dev-key-123').split(',')
    app.config['VALID_API_KEYS'] = [key.strip() for key in api_keys]
    app.config['IP_WHITELIST'] = [ip.strip() for ip in os.getenv('IP_WHITELIST', '127.0.0.1,localhost').split(',')]

    # CSRF Protection - can be disabled with WTF_CSRF_ENABLED=False
    csrf_enabled = os.getenv('WTF_CSRF_ENABLED', 'True').lower() != 'false'
    app.config['WTF_CSRF_ENABLED'] = csrf_enabled
    app.config['WTF_CSRF_TIME_LIMIT'] = None  # CSRF tokens tidak kadaluarsa
    app.config['WTF_CSRF_SSL_STRICT'] = False  # Disable strict SSL check for dev/GitHub Codespace
    # Allow GitHub Codespace and localhost origins for CSRF
    # Also allow production domains from environment variable
    csrf_trusted_hosts = [
        '127.0.0.1',
        'localhost',
        '*.app.github.dev',  # GitHub Codespace URLs
        '*.github.dev',      # GitHub Codespace
    ]

    # Add production domains from environment
    prod_domains = os.getenv('CSRF_TRUSTED_HOSTS', '').strip()
    if prod_domains:
        csrf_trusted_hosts.extend([h.strip() for h in prod_domains.split(',') if h.strip()])

    app.config['WTF_CSRF_TRUSTED_HOSTS'] = csrf_trusted_hosts

    if csrf_enabled:
        print("✅ CSRF Protection: ENABLED (with GitHub Codespace support)")
    else:
        print("⚠️  CSRF Protection: DISABLED (Development/Testing only)")

    # Custom CSRF protection that allows API key exemption
    class FlexibleCSRFProtect(CSRFProtect):
        """CSRF Protection with API key exemption"""
        def protect(self):
            from .security import is_csrf_exempted
            # Check if request should be exempt
            if is_csrf_exempted():
                return  # Skip CSRF validation
            # Otherwise, use default CSRF protection
            return super().protect()

    csrf = FlexibleCSRFProtect(app)

    # Export csrf object for use in blueprint decorators
    app.csrf = csrf


    # Rate limiting
    from .security import init_limiter
    init_limiter(app)

    # Database initialization
    from .models import db
    db.init_app(app)

    with app.app_context():
        # Ensure upload folder exists
        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create upload folder: {e}")

        db.create_all()

        # Initialize Chroma Vector Store (Cloud atau Local) - LAZY LOAD
        # Skip during startup to avoid blocking worker initialization
        # Chroma will be initialized on first use in routes
        print("⏳ Chroma will be lazy-loaded on first use (not blocking startup)")

    # Security headers configured for Bootstrap CDN compatibility
    @app.after_request
    def add_security_headers(response):
        # Allow Bootstrap from Bootstrap CDN and Font Awesome from cdnjs/cloudflare
        response.headers['Content-Security-Policy'] = (
            "default-src 'self' https:; "
            "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
            "frame-src https://docs.google.com https://drive.google.com https://accounts.google.com; "
            "connect-src 'self' https:;"
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    from .routes import main
    app.register_blueprint(main)

    # Register chat routes
    try:
        from .routes_chat import register_chat_routes
        register_chat_routes(app)
    except Exception as e:
        print(f"⚠️  Chat routes could not be registered: {e}")
        import traceback
        traceback.print_exc()

    # Register admin Chroma routes
    try:
        from .routes_admin_chroma import register_admin_chroma_routes
        register_admin_chroma_routes(app)
    except Exception as e:
        print(f"⚠️  Admin Chroma routes could not be registered: {e}")
        import traceback
        traceback.print_exc()

    # Register learning chatbot routes
    try:
        from .routes_learning import learning, init_learning_system
        app.register_blueprint(learning, url_prefix='/api/learning')
        # DISABLED: init_learning_system() - can hang on Chroma initialization
        # init_learning_system()
        # Will be initialized lazy on first API call instead
        print("✅ Learning Chatbot routes: REGISTERED (lazy load)")
    except Exception as e:
        print(f"⚠️  Learning chatbot routes could not be registered: {e}")
        import traceback
        traceback.print_exc()

    # Register notification routes
    try:
        from .routes_notifications import notification_api
        app.register_blueprint(notification_api)
        print("✅ Notification API routes: REGISTERED")
    except Exception as e:
        print(f"⚠️  Notification API routes could not be registered: {e}")
        import traceback
        traceback.print_exc()

    # Register API keys management routes
    try:
        from .routes_api_keys import api_keys_bp
        app.register_blueprint(api_keys_bp)
        print("✅ API Keys Management routes: REGISTERED")
    except Exception as e:
        print(f"⚠️  API Keys Management routes could not be registered: {e}")
        import traceback
        traceback.print_exc()

    # Error handler untuk CSRF errors
    @app.errorhandler(400)
    def handle_csrf_error(e):
        # Cek apakah error dari CSRF
        if 'CSRF' in str(e):
            # Check if it's an API request with valid API key
            from .security import is_csrf_exempted
            if is_csrf_exempted():
                # Allow API requests with valid key - need to re-process the request
                # For now, return error but in production, could use csrf.exempt() for specific routes
                pass

            return f"""
            <!DOCTYPE html>
            <html>
            <head><title>Error CSRF</title></head>
            <body style="font-family:Arial; padding:20px;">
                <h2>❌ CSRF Token Error</h2>
                <p>Kemungkinan:</p>
                <ul>
                    <li>Session sudah kadaluarsa, coba reload halaman</li>
                    <li>Cookies tidak aktif di browser Anda</li>
                    <li>Buka di private/incognito window</li>
                </ul>
                <a href="/admin">← Kembali ke Login</a>
            </body>
            </html>
            """, 400
        return str(e), 400

    # Setup scheduler untuk auto-sync Google Drive
    try:
        from .drive_sync import setup_scheduler
        scheduler = setup_scheduler()
        scheduler.start()
        print("✅ Google Drive Auto-Sync: SCHEDULED (setiap Minggu pukul 02:00)")
        print("✅ Payment Proof Cleanup: SCHEDULED (setiap jam)")
    except Exception as e:
        print(f"⚠️  Could not setup scheduler: {e}")

    return app
