"""
Routes untuk Chroma DB Synchronization
API endpoints untuk manage sinkronisasi local dan cloud
"""

from flask import Blueprint, request, jsonify
from functools import wraps
from datetime import datetime
import os
import logging

from app.chroma_sync import ChromaSyncManager, quick_sync, check_sync_status
from app.security import require_admin_auth

# Create blueprint
chroma_sync_bp = Blueprint(
    'chroma_sync',
    __name__,
    url_prefix='/api/admin/chroma-sync'
)

logger = logging.getLogger(__name__)


def get_chroma_clients():
    """Helper untuk get local dan cloud Chroma clients"""
    try:
        from app import db_instance

        # Get local client
        local_client = db_instance.client if hasattr(db_instance, 'client') else None

        if not local_client:
            return None, None

        # Cloud credentials dari env
        cloud_api_key = os.getenv('CHROMA_API_KEY')

        return local_client, cloud_api_key
    except Exception as e:
        logger.error(f"Error getting Chroma clients: {e}")
        return None, None


@chroma_sync_bp.route('/status', methods=['GET'])
@require_admin_auth
def get_sync_status():
    """
    Get current synchronization status

    Returns:
        JSON dengan status local vs cloud
    """
    try:
        local_client, cloud_api_key = get_chroma_clients()

        if not local_client:
            return jsonify({
                'error': 'Chroma client not initialized',
                'status': 'error'
            }), 500

        status = check_sync_status(local_client, cloud_api_key)

        return jsonify({
            'status': 'success',
            'data': status,
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@chroma_sync_bp.route('/detect-changes', methods=['GET'])
@require_admin_auth
def detect_changes():
    """
    Detect perubahan antara local dan cloud

    Returns:
        JSON dengan list perubahan yang terdeteksi
    """
    try:
        local_client, cloud_api_key = get_chroma_clients()

        if not local_client:
            return jsonify({
                'error': 'Chroma client not initialized'
            }), 500

        manager = ChromaSyncManager(
            local_client=local_client,
            cloud_api_key=cloud_api_key
        )

        changes = manager.detect_changes()

        return jsonify({
            'status': 'success',
            'changes': changes,
            'summary': {
                'local_only': len(changes.get('local_only', [])),
                'cloud_only': len(changes.get('cloud_only', [])),
                'modified': len(changes.get('modified', [])),
                'conflicts': len(changes.get('conflicts', []))
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error detecting changes: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@chroma_sync_bp.route('/push', methods=['POST'])
@require_admin_auth
def push_to_cloud():
    """
    Push local changes ke cloud

    Request JSON:
        - override_conflicts (bool, optional): Override cloud version jika ada konflik

    Returns:
        JSON dengan hasil push operation
    """
    try:
        local_client, cloud_api_key = get_chroma_clients()

        if not local_client:
            return jsonify({
                'error': 'Chroma client not initialized'
            }), 500

        data = request.get_json() or {}
        override_conflicts = data.get('override_conflicts', False)

        manager = ChromaSyncManager(
            local_client=local_client,
            cloud_api_key=cloud_api_key
        )

        result = manager.push_to_cloud(override_conflicts=override_conflicts)

        return jsonify({
            'status': 'success',
            'operation': 'push',
            'result': result,
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error pushing to cloud: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@chroma_sync_bp.route('/pull', methods=['POST'])
@require_admin_auth
def pull_from_cloud():
    """
    Pull cloud changes ke local

    Returns:
        JSON dengan hasil pull operation
    """
    try:
        local_client, cloud_api_key = get_chroma_clients()

        if not local_client:
            return jsonify({
                'error': 'Chroma client not initialized'
            }), 500

        manager = ChromaSyncManager(
            local_client=local_client,
            cloud_api_key=cloud_api_key
        )

        result = manager.pull_from_cloud()

        return jsonify({
            'status': 'success',
            'operation': 'pull',
            'result': result,
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error pulling from cloud: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@chroma_sync_bp.route('/sync', methods=['POST'])
@require_admin_auth
def bidirectional_sync():
    """
    Two-way synchronization antara local dan cloud

    Request JSON:
        - conflict_resolution (str): "cloud_wins", "local_wins", atau "manual"

    Returns:
        JSON dengan detailed sync result
    """
    try:
        local_client, cloud_api_key = get_chroma_clients()

        if not local_client:
            return jsonify({
                'error': 'Chroma client not initialized'
            }), 500

        data = request.get_json() or {}
        conflict_resolution = data.get('conflict_resolution', 'cloud_wins')

        # Validate conflict resolution strategy
        valid_strategies = ['cloud_wins', 'local_wins', 'manual']
        if conflict_resolution not in valid_strategies:
            return jsonify({
                'error': f'Invalid conflict_resolution. Must be one of: {valid_strategies}',
                'status': 'error'
            }), 400

        manager = ChromaSyncManager(
            local_client=local_client,
            cloud_api_key=cloud_api_key
        )

        result = manager.bidirectional_sync(conflict_resolution=conflict_resolution)

        return jsonify({
            'status': 'success',
            'operation': 'bidirectional_sync',
            'result': result,
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error in bidirectional sync: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@chroma_sync_bp.route('/enable-auto-sync', methods=['POST'])
@require_admin_auth
def enable_auto_sync():
    """
    Enable automatic synchronization

    Request JSON:
        - interval_seconds (int): Interval sync dalam detik (default: 3600)
        - direction (str): "bidirectional", "push-only", atau "pull-only"

    Returns:
        JSON confirmation
    """
    try:
        local_client, cloud_api_key = get_chroma_clients()

        if not local_client:
            return jsonify({
                'error': 'Chroma client not initialized'
            }), 500

        data = request.get_json() or {}
        interval_seconds = data.get('interval_seconds', 3600)
        direction = data.get('direction', 'bidirectional')

        # Validate direction
        valid_directions = ['bidirectional', 'push-only', 'pull-only']
        if direction not in valid_directions:
            return jsonify({
                'error': f'Invalid direction. Must be one of: {valid_directions}',
                'status': 'error'
            }), 400

        manager = ChromaSyncManager(
            local_client=local_client,
            cloud_api_key=cloud_api_key
        )

        manager.enable_auto_sync(interval_seconds, direction)

        return jsonify({
            'status': 'success',
            'message': f'Auto-sync enabled ({direction}, interval: {interval_seconds}s)',
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error enabling auto-sync: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@chroma_sync_bp.route('/sync-logs', methods=['GET'])
@require_admin_auth
def get_sync_logs():
    """
    Get sync operation logs

    Query parameters:
        - days (int): Number of days to show (default: 1)
        - limit (int): Number of logs to return (default: 100)

    Returns:
        JSON dengan recent sync logs
    """
    try:
        import os
        from pathlib import Path

        days = request.args.get('days', 1, type=int)
        limit = request.args.get('limit', 100, type=int)

        # Get sync logs directory
        sync_logs_dir = os.path.join(
            os.path.dirname(__file__), '..', 'chroma_data', '.sync', 'logs'
        )

        if not os.path.exists(sync_logs_dir):
            return jsonify({
                'status': 'success',
                'logs': [],
                'message': 'No sync logs found'
            }), 200

        # Get recent log files
        log_files = list(Path(sync_logs_dir).glob('sync_*.log'))
        log_files.sort(reverse=True)

        logs = []
        cutoff_date = datetime.now() - \
            __import__('datetime').timedelta(days=days)

        for log_file in log_files:
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()

                    for line in reversed(lines[-limit:]):
                        logs.append(line.strip())

                # Check if we have enough logs
                if len(logs) >= limit:
                    break

            except Exception as e:
                logger.warning(f"Error reading log file {log_file}: {e}")

        return jsonify({
            'status': 'success',
            'logs': logs[-limit:],
            'total_logs': len(logs),
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error getting sync logs: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@chroma_sync_bp.route('/health-check', methods=['GET'])
@require_admin_auth
def health_check():
    """
    Check sync system health

    Returns:
        JSON dengan health status
    """
    try:
        local_client, cloud_api_key = get_chroma_clients()

        health_status = {
            'local_client': 'ok' if local_client else 'error',
            'cloud_configured': 'ok' if cloud_api_key else 'not_configured',
            'timestamp': datetime.utcnow().isoformat()
        }

        # Try to connect to managers
        if local_client:
            manager = ChromaSyncManager(
                local_client=local_client,
                cloud_api_key=cloud_api_key
            )

            health_status['cloud_connection'] = 'ok' if manager.cloud_client else 'failed'

        return jsonify({
            'status': 'success',
            'health': health_status
        }), 200

    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500
