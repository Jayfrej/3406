"""
System Routes - Flask Blueprint

System-wide management endpoints:
- Settings Management (GET/POST)
- Rate Limits Configuration
- Email Configuration
- System Logs (GET/POST/CLEAR)
- System Information

Note: SSE endpoints remain in server.py for connection management
"""

import os
import json
import re
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app

logger = logging.getLogger(__name__)

# Create Blueprint
system_bp = Blueprint('system', __name__)

# Settings file path
SETTINGS_FILE = 'data/settings.json'


# =================== Settings Helper Functions ===================

def load_settings():
    """Load settings from file"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Default settings
            return {
                'rate_limits': {
                    'webhook': '10 per minute',
                    'api': '100 per hour',
                    'command_api': '60 per minute',
                    'last_updated': None
                },
                'email': {
                    'enabled': False,
                    'smtp_server': '',
                    'smtp_port': 587,
                    'smtp_user': '',
                    'smtp_pass': '',
                    'from_email': '',
                    'to_emails': []
                }
            }
    except Exception as e:
        logger.error(f"[SETTINGS] Error loading settings: {e}")
        return {}


def save_settings(settings_data):
    """Save settings to file"""
    try:
        os.makedirs('data', exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings_data, f, indent=2, ensure_ascii=False)
        logger.info("[SETTINGS] Settings saved successfully")
        return True
    except Exception as e:
        logger.error(f"[SETTINGS] Error saving settings: {e}")
        return False


# =================== Settings Endpoints ===================

@system_bp.get('/api/settings')
def get_all_settings():
    """Get all settings"""
    try:
        settings = load_settings()
        return jsonify(settings), 200
    except Exception as e:
        logger.error(f"[SETTINGS_API] Error getting settings: {e}")
        return jsonify({'error': str(e)}), 500


@system_bp.post('/api/settings/rate-limits')
def save_rate_limit_settings():
    """Save rate limit settings"""
    try:
        data = request.get_json() or {}
        webhook_limit = data.get('webhook', '').strip()
        api_limit = data.get('api', '').strip()
        command_api_limit = data.get('command_api', '').strip()

        if not webhook_limit or not api_limit or not command_api_limit:
            return jsonify({'error': 'Missing webhook, api, or command_api limit'}), 400

        # Validate format
        pattern = r'^\d+\s+per\s+(minute|hour|day)$'
        if not re.match(pattern, webhook_limit, re.IGNORECASE):
            try:
                from server import add_system_log
                add_system_log('error', f'❌ [400] Rate limit update failed - Invalid webhook format: {webhook_limit}')
            except:
                pass
            return jsonify({'error': 'Invalid webhook rate limit format'}), 400
        if not re.match(pattern, api_limit, re.IGNORECASE):
            try:
                from server import add_system_log
                add_system_log('error', f'❌ [400] Rate limit update failed - Invalid API format: {api_limit}')
            except:
                pass
            return jsonify({'error': 'Invalid API rate limit format'}), 400
        if not re.match(pattern, command_api_limit, re.IGNORECASE):
            try:
                from server import add_system_log
                add_system_log('error', f'❌ [400] Rate limit update failed - Invalid command API format: {command_api_limit}')
            except:
                pass
            return jsonify({'error': 'Invalid command API rate limit format'}), 400

        # Load current settings
        settings = load_settings()

        # Update rate limits
        settings['rate_limits'] = {
            'webhook': webhook_limit,
            'api': api_limit,
            'command_api': command_api_limit,
            'last_updated': datetime.now().isoformat()
        }

        # Save settings
        if save_settings(settings):
            logger.info(f"[SETTINGS] Rate limits updated: webhook={webhook_limit}, api={api_limit}, command_api={command_api_limit}")
            try:
                from server import add_system_log
                add_system_log('info', f'⚙️ [200] Rate limits updated - Webhook: {webhook_limit}, API: {api_limit}, Command API: {command_api_limit}')
            except:
                pass
            return jsonify({
                'success': True,
                'rate_limits': settings['rate_limits']
            }), 200
        else:
            return jsonify({'error': 'Failed to save settings'}), 500

    except Exception as e:
        logger.error(f"[SETTINGS_API] Error saving rate limits: {e}")
        return jsonify({'error': str(e)}), 500


@system_bp.get('/api/settings/email')
def get_email_settings():
    """Get email settings (password masked)"""
    try:
        settings = load_settings()
        email_settings = settings.get('email', {})

        # Don't send password to frontend
        email_settings_safe = email_settings.copy()
        if 'smtp_pass' in email_settings_safe:
            email_settings_safe['smtp_pass'] = '********' if email_settings.get('smtp_pass') else ''

        return jsonify(email_settings_safe), 200
    except Exception as e:
        logger.error(f"[SETTINGS_API] Error getting email settings: {e}")
        return jsonify({'error': str(e)}), 500


@system_bp.post('/api/settings/email')
def save_email_settings():
    """Save email settings"""
    try:
        data = request.get_json() or {}

        enabled = data.get('enabled', False)
        smtp_server = data.get('smtp_server', '').strip()
        smtp_port = data.get('smtp_port', 587)
        smtp_user = data.get('smtp_user', '').strip()
        smtp_pass = data.get('smtp_pass', '').strip()
        from_email = data.get('from_email', '').strip()
        to_emails = data.get('to_emails', [])

        # Validate if enabled
        if enabled:
            if not smtp_server or not smtp_user or not from_email:
                try:
                    from server import add_system_log
                    add_system_log('error', '❌ [400] Email config failed - Missing required fields')
                except:
                    pass
                return jsonify({'error': 'Missing required email configuration'}), 400

            if not to_emails or len(to_emails) == 0:
                try:
                    from server import add_system_log
                    add_system_log('error', '❌ [400] Email config failed - No recipients specified')
                except:
                    pass
                return jsonify({'error': 'At least one recipient email is required'}), 400

        # Load current settings
        settings = load_settings()

        # Get existing password if new password is not provided or is masked
        existing_email = settings.get('email', {})
        if smtp_pass == '********' or not smtp_pass:
            smtp_pass = existing_email.get('smtp_pass', '')

        # Update email settings
        settings['email'] = {
            'enabled': enabled,
            'smtp_server': smtp_server,
            'smtp_port': smtp_port,
            'smtp_user': smtp_user,
            'smtp_pass': smtp_pass,
            'from_email': from_email,
            'to_emails': to_emails
        }

        # Save settings
        if save_settings(settings):
            # Update email_handler instance if accessible
            try:
                from app.core.email import EmailHandler
                email_handler = EmailHandler()
                email_handler.enabled = enabled
                email_handler.smtp_server = smtp_server
                email_handler.smtp_port = smtp_port
                email_handler.smtp_user = smtp_user
                email_handler.smtp_pass = smtp_pass
                email_handler.from_email = from_email
                email_handler.to_emails = to_emails
            except Exception as handler_error:
                logger.warning(f"[SETTINGS] Could not update email_handler: {handler_error}")

            logger.info(f"[SETTINGS] Email settings updated: enabled={enabled}")
            status = "enabled" if enabled else "disabled"
            recipients = len(to_emails)

            try:
                from server import add_system_log
                add_system_log('info', f'📧 [200] Email {status} - Server: {smtp_server}:{smtp_port}, Recipients: {recipients}')
            except:
                pass

            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'Failed to save settings'}), 500

    except Exception as e:
        logger.error(f"[SETTINGS_API] Error saving email settings: {e}")
        return jsonify({'error': str(e)}), 500


@system_bp.post('/api/settings/email/test')
def test_email_settings():
    """Test email configuration"""
    try:
        settings = load_settings()
        email_settings = settings.get('email', {})

        if not email_settings.get('enabled'):
            try:
                from server import add_system_log
                add_system_log('warning', '⚠️ [400] Test email failed - Email notifications not enabled')
            except:
                pass
            return jsonify({'error': 'Email is not enabled'}), 400

        # Update email_handler with current settings
        try:
            from app.core.email import EmailHandler
            email_handler = EmailHandler()
            email_handler.enabled = email_settings.get('enabled', False)
            email_handler.smtp_server = email_settings.get('smtp_server', 'smtp.gmail.com')
            email_handler.smtp_port = email_settings.get('smtp_port', 587)
            email_handler.sender_email = email_settings.get('smtp_user', '')
            email_handler.sender_password = email_settings.get('smtp_pass', '')
            email_handler.to_emails = email_settings.get('to_emails', [])
        except Exception as handler_error:
            logger.warning(f"[SETTINGS] Could not update email_handler: {handler_error}")

        # Send test email
        test_subject = "MT5 Trading Bot - Test Email"
        test_message = f"This is a test email sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nIf you receive this email, your email configuration is working correctly!"

        # Try to send via email handler
        try:
            from server import _email_send_alert
            success = _email_send_alert(test_subject, test_message)
        except:
            # Fallback: try direct send
            try:
                email_handler.send_alert(test_subject, test_message)
                success = True
            except:
                success = False

        if success:
            logger.info("[SETTINGS] Test email sent successfully")
            recipients = len(email_settings.get('to_emails', []))
            try:
                from server import add_system_log
                add_system_log('success', f'📧 [200] Test email sent successfully to {recipients} recipient(s)')
            except:
                pass
            return jsonify({'success': True, 'message': 'Test email sent'}), 200
        else:
            try:
                from server import add_system_log
                add_system_log('error', '❌ [500] Test email failed - Check SMTP configuration')
            except:
                pass
            return jsonify({'error': 'Failed to send test email'}), 500

    except Exception as e:
        logger.error(f"[SETTINGS_API] Error testing email: {e}")
        return jsonify({'error': str(e)}), 500


# =================== System Logs Endpoints ===================

@system_bp.get('/api/system/logs')
def get_system_logs():
    """Get system logs"""
    try:
        # Import system logs from server
        from server import system_logs, system_logs_lock, MAX_SYSTEM_LOGS

        limit = int(request.args.get('limit', 300))
        limit = max(1, min(limit, MAX_SYSTEM_LOGS))

        with system_logs_lock:
            logs = system_logs[:limit]

        return jsonify({
            'success': True,
            'logs': logs,
            'total': len(logs)
        }), 200
    except Exception as e:
        logger.error(f"[SYSTEM_LOGS] Error getting logs: {e}")
        return jsonify({'error': str(e)}), 500


@system_bp.post('/api/system/logs/clear')
def clear_system_logs():
    """Clear all system logs"""
    try:
        # Import system logs from server
        from server import system_logs, system_logs_lock, add_system_log

        with system_logs_lock:
            system_logs.clear()

        add_system_log('info', 'System logs cleared')

        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f"[SYSTEM_LOGS] Error clearing logs: {e}")
        return jsonify({'error': str(e)}), 500

