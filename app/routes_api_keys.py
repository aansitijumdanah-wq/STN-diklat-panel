"""
Admin routes untuk manage API Keys dan monitor quota status
Supports multi-key management dengan automatic failover
"""

from flask import Blueprint, request, jsonify
from functools import wraps
from datetime import datetime
import os
from .api_key_manager import (
    get_manager,
    APIProvider,
    APIKeyStatus
)

api_keys_bp = Blueprint('api_keys', __name__, url_prefix='/api/admin/api-keys')

# Admin authentication decorator
def require_admin(f):
    """Decorator untuk memastikan admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-Admin-Key')
        expected_key = os.getenv('ADMIN_API_KEY', 'admin-key-change-me')

        if api_key != expected_key:
            return jsonify({'error': 'Unauthorized', 'message': 'Invalid admin API key'}), 401

        return f(*args, **kwargs)
    return decorated_function


@api_keys_bp.route('/status', methods=['GET'])
@require_admin
def get_api_keys_status():
    """
    Get status of all API keys across providers

    Returns:
        {
            'success': bool,
            'timestamp': ISO timestamp,
            'providers': {
                'gemini': {
                    'available': bool,
                    'keys': [
                        {
                            'key_id': 1,
                            'status': 'ACTIVE|QUOTA_EXCEEDED|RATE_LIMITED|ERROR',
                            'last_used': ISO timestamp,
                            'error_count': int,
                            'last_error': str or null
                        },
                        ...
                    ]
                },
                'groq': {...},
                'chroma': {...}
            }
        }
    """
    try:
        manager = get_manager()

        # Get status for each provider
        status_data = {
            'success': True,
            'timestamp': datetime.utcnow().isoformat(),
            'providers': {}
        }

        for provider in APIProvider:
            provider_name = provider.value.lower()
            provider_keys = []

            # Get all keys for this provider (1 and 2)
            for key_id in [1, 2]:
                try:
                    key_status = manager.get_status(provider_name, key_id=key_id)
                    provider_keys.append({
                        'key_id': key_id,
                        'status': key_status.get('status', 'UNKNOWN'),
                        'available': key_status.get('available', False),
                        'last_used': key_status.get('last_used'),
                        'error_count': key_status.get('error_count', 0),
                        'last_error': key_status.get('last_error'),
                        'quota_exceeded': key_status.get('quota_exceeded', False),
                        'rate_limited': key_status.get('rate_limited', False)
                    })
                except:
                    # Key might not be configured
                    continue

            if provider_keys:
                status_data['providers'][provider_name] = {
                    'available': any(k['available'] for k in provider_keys),
                    'keys': provider_keys
                }

        return jsonify(status_data), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@api_keys_bp.route('/health-check', methods=['GET'])
@require_admin
def health_check_api_keys():
    """
    Perform health check on all API keys
    Tests connectivity and returns availability status

    Returns:
        {
            'success': bool,
            'timestamp': ISO timestamp,
            'health': {
                'gemini': {
                    'ok': bool,
                    'message': str,
                    'available_keys': int
                },
                'groq': {...},
                'chroma': {...}
            }
        }
    """
    try:
        manager = get_manager()

        health_data = {
            'success': True,
            'timestamp': datetime.utcnow().isoformat(),
            'health': {}
        }

        for provider_name in ['gemini', 'groq', 'chroma']:
            try:
                # Perform health check
                result = manager.health_check(provider_name)

                health_data['health'][provider_name] = {
                    'ok': result.get('ok', False),
                    'message': result.get('message', 'Unknown'),
                    'available_keys': result.get('available_keys', 0),
                    'total_keys': result.get('total_keys', 0),
                    'keys': result.get('keys', [])
                }
            except Exception as e:
                health_data['health'][provider_name] = {
                    'ok': False,
                    'message': f'Health check failed: {str(e)}',
                    'available_keys': 0
                }

        return jsonify(health_data), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@api_keys_bp.route('/reset-error/<provider>', methods=['POST'])
@require_admin
def reset_error_state(provider):
    """
    Reset error state for a specific provider
    Useful if an API key was temporarily blocked

    Args:
        provider: 'gemini', 'groq', or 'chroma'

    Returns:
        {
            'success': bool,
            'message': str,
            'provider': str,
            'timestamp': ISO timestamp
        }
    """
    try:
        valid_providers = ['gemini', 'groq', 'chroma']

        if provider.lower() not in valid_providers:
            return jsonify({
                'success': False,
                'error': f'Invalid provider. Must be one of: {", ".join(valid_providers)}'
            }), 400

        manager = get_manager()

        # Reset error counters for all keys of this provider
        results = []
        for key_id in [1, 2]:
            try:
                # Get current status and reset
                manager._reset_error_state(provider.lower(), key_id)
                results.append({
                    'key_id': key_id,
                    'reset': True
                })
            except:
                results.append({
                    'key_id': key_id,
                    'reset': False
                })

        return jsonify({
            'success': True,
            'message': f'Error state reset for {provider}',
            'provider': provider.lower(),
            'keys_reset': results,
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@api_keys_bp.route('/report-error/<provider>', methods=['POST'])
@require_admin
def report_api_error_endpoint(provider):
    """
    Manually report an API error for a key
    Useful for marking a key as problematic without waiting for automatic detection

    Request body:
        {
            'key_id': 1 or 2 (optional, defaults to current),
            'error_type': 'quota_exceeded|rate_limited|timeout|api_error',
            'error_message': 'Optional error details'
        }

    Returns:
        {
            'success': bool,
            'message': str,
            'provider': str,
            'timestamp': ISO timestamp
        }
    """
    try:
        valid_providers = ['gemini', 'groq', 'chroma']

        if provider.lower() not in valid_providers:
            return jsonify({
                'success': False,
                'error': f'Invalid provider. Must be one of: {", ".join(valid_providers)}'
            }), 400

        data = request.get_json() or {}
        error_type = data.get('error_type', 'api_error')
        error_message = data.get('error_message', 'Manual error report')

        from .api_key_manager import report_api_error

        # Report the error
        report_api_error(provider.lower(), error_type=error_type)

        return jsonify({
            'success': True,
            'message': f'Error reported for {provider}: {error_type}',
            'provider': provider.lower(),
            'error_type': error_type,
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@api_keys_bp.route('/stats', methods=['GET'])
@require_admin
def get_api_keys_stats():
    """
    Get comprehensive statistics about API key usage

    Returns:
        {
            'success': bool,
            'timestamp': ISO timestamp,
            'summary': {
                'total_providers': int,
                'total_keys': int,
                'keys_healthy': int,
                'keys_problematic': int
            },
            'detailed': {
                'provider_name': {
                    'keys_configured': int,
                    'keys_active': int,
                    'keys_quota_exceeded': int,
                    'keys_rate_limited': int,
                    'keys_errored': int
                },
                ...
            }
        }
    """
    try:
        manager = get_manager()

        stats_data = {
            'success': True,
            'timestamp': datetime.utcnow().isoformat(),
            'summary': {
                'total_providers': 0,
                'total_keys': 0,
                'keys_healthy': 0,
                'keys_problematic': 0
            },
            'detailed': {}
        }

        for provider in APIProvider:
            provider_name = provider.value.lower()
            provider_stats = {
                'keys_configured': 0,
                'keys_active': 0,
                'keys_quota_exceeded': 0,
                'keys_rate_limited': 0,
                'keys_errored': 0
            }

            # Check both keys for this provider
            for key_id in [1, 2]:
                try:
                    key_status = manager.get_status(provider_name, key_id=key_id)
                    provider_stats['keys_configured'] += 1
                    stats_data['summary']['total_keys'] += 1

                    status = key_status.get('status', 'UNKNOWN')
                    if status == 'ACTIVE':
                        provider_stats['keys_active'] += 1
                        stats_data['summary']['keys_healthy'] += 1
                    elif status == 'QUOTA_EXCEEDED':
                        provider_stats['keys_quota_exceeded'] += 1
                        stats_data['summary']['keys_problematic'] += 1
                    elif status == 'RATE_LIMITED':
                        provider_stats['keys_rate_limited'] += 1
                        stats_data['summary']['keys_problematic'] += 1
                    elif status == 'ERROR':
                        provider_stats['keys_errored'] += 1
                        stats_data['summary']['keys_problematic'] += 1
                except:
                    continue

            if provider_stats['keys_configured'] > 0:
                stats_data['detailed'][provider_name] = provider_stats
                stats_data['summary']['total_providers'] += 1

        return jsonify(stats_data), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500
