"""
API Routes untuk Notification Management
Admin dapat melihat log notifikasi dan mengatur pengaturan notifikasi
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from .notification_manager import NotificationManager
from .models import db, TelegramNotificationLog, Admin

notification_api = Blueprint('notification_api', __name__, url_prefix='/api/notifications')

# ============================================================================
# ADMIN AUTH DECORATOR
# ============================================================================

def admin_required(f):
    """Decorator untuk memastikan user adalah admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_username' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# API ENDPOINTS
# ============================================================================

@notification_api.route('/test', methods=['GET', 'POST'])
@admin_required
def test_notification():
    """
    Send test notification
    GET /api/notifications/test
    """
    try:
        results = NotificationManager.test_notification()
        return jsonify({
            'success': True,
            'message': 'Test notifikasi telah dikirim',
            'results': results
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@notification_api.route('/logs', methods=['GET'])
@admin_required
def get_notification_logs():
    """
    Get notification logs
    GET /api/notifications/logs?type=new_registration&limit=50
    """
    try:
        notification_type = request.args.get('type')
        limit = request.args.get('limit', 50, type=int)

        logs = NotificationManager.get_notification_logs(notification_type, limit)

        # Convert to JSON-serializable format
        logs_data = []
        for log in logs:
            logs_data.append({
                'id': log.id,
                'admin_id': log.admin_id,
                'type': log.notification_type,
                'title': log.title,
                'message': log.message,
                'status': log.status,
                'created_at': log.created_at.isoformat(),
                'error': log.error_message
            })

        return jsonify({
            'success': True,
            'count': len(logs_data),
            'logs': logs_data
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@notification_api.route('/stats', methods=['GET'])
@admin_required
def get_notification_stats():
    """
    Get notification statistics
    GET /api/notifications/stats
    """
    try:
        stats = NotificationManager.get_notification_stats()
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@notification_api.route('/send-manual', methods=['POST'])
@admin_required
def send_manual_notification():
    """
    Send manual notification to all admins
    POST /api/notifications/send-manual

    Request body:
    {
        "title": "Alert Title",
        "message": "Alert message",
        "severity": "INFO|WARNING|ERROR|CRITICAL"
    }
    """
    try:
        data = request.get_json()

        if not data or 'title' not in data or 'message' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: title, message'
            }), 400

        title = data.get('title')
        message = data.get('message')
        severity = data.get('severity', 'INFO')

        results = NotificationManager.notify_system_alert(title, message, severity)

        return jsonify({
            'success': True,
            'message': 'Notifikasi manual telah dikirim',
            'results': results
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@notification_api.route('/clear-logs', methods=['POST'])
@admin_required
def clear_notification_logs():
    """
    Clear notification logs
    POST /api/notifications/clear-logs
    """
    try:
        TelegramNotificationLog.query.delete()
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Notification logs telah dihapus'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@notification_api.route('/settings', methods=['GET', 'POST'])
@admin_required
def notification_settings():
    """
    Get or update notification settings
    GET /api/notifications/settings
    POST /api/notifications/settings
    """
    try:
        if request.method == 'GET':
            from .telegram_notifications import TelegramNotificationService

            return jsonify({
                'success': True,
                'settings': {
                    'admin_ids': TelegramNotificationService.ADMIN_IDS,
                    'bot_token': '***' if TelegramNotificationService.TELEGRAM_BOT_TOKEN else 'Not configured'
                }
            }), 200

        else:  # POST
            # For now, we can't change settings via API
            # Settings are defined in the class
            return jsonify({
                'success': False,
                'error': 'Settings cannot be changed via API. Edit telegram_notifications.py instead.'
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# HTML ADMIN DASHBOARD FOR NOTIFICATIONS
# ============================================================================

@notification_api.route('/dashboard', methods=['GET'])
@admin_required
def notification_dashboard():
    """
    Admin dashboard untuk monitoring notifikasi
    GET /api/notifications/dashboard
    """
    try:
        stats = NotificationManager.get_notification_stats()
        recent_logs = NotificationManager.get_notification_logs(limit=20)

        return jsonify({
            'success': True,
            'stats': stats,
            'recent_logs': [
                {
                    'id': log.id,
                    'type': log.notification_type,
                    'title': log.title,
                    'status': log.status,
                    'created_at': log.created_at.isoformat()
                }
                for log in recent_logs
            ]
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
