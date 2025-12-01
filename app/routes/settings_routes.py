"""
Settings Routes
Handles application settings management (rate limits, email configuration)
"""
import re
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from app.middleware.auth import session_login_required

logger = logging.getLogger(__name__)

# Create blueprint
settings_bp = Blueprint('settings', __name__)

# These will be injected by the app factory
settings_service = None
system_logs_service = None
email_handler = None
email_send_alert_fn = None


def init_settings_routes(ss, sls, eh, esa_fn):
    """
    Initialize settings routes with dependencies

    Args:
        ss: SettingsService instance
        sls: SystemLogsService instance
        eh: EmailHandler instance
        esa_fn: _email_send_alert function
    """
    global settings_service, system_logs_service, email_handler, email_send_alert_fn

    settings_service = ss
    system_logs_service = sls
    email_handler = eh
    email_send_alert_fn = esa_fn


@settings_bp.route('/api/settings', methods=['GET'])
@session_login_required
def get_all_settings():
    """ดึง settings ทั้งหมด"""
    try:
        settings = settings_service.load_settings()
        return jsonify(settings), 200
    except Exception as e:
        logger.error(f"[SETTINGS_API] Error getting settings: {e}")
        return jsonify({'error': str(e)}), 500


@settings_bp.route('/api/settings/rate-limits', methods=['POST'])
@session_login_required
def save_rate_limit_settings():
    """บันทึก Rate Limit Settings"""
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
            system_logs_service.add_log('error', f'❌ [400] Rate limit update failed - Invalid webhook format: {webhook_limit}')
            return jsonify({'error': 'Invalid webhook rate limit format'}), 400
        if not re.match(pattern, api_limit, re.IGNORECASE):
            system_logs_service.add_log('error', f'❌ [400] Rate limit update failed - Invalid API format: {api_limit}')
            return jsonify({'error': 'Invalid API rate limit format'}), 400
        if not re.match(pattern, command_api_limit, re.IGNORECASE):
            system_logs_service.add_log('error', f'❌ [400] Rate limit update failed - Invalid command API format: {command_api_limit}')
            return jsonify({'error': 'Invalid command API rate limit format'}), 400

        # Load current settings
        settings = settings_service.load_settings()

        # Update rate limits
        settings['rate_limits'] = {
            'webhook': webhook_limit,
            'api': api_limit,
            'command_api': command_api_limit,
            'last_updated': datetime.now().isoformat()
        }

        # Save settings
        if settings_service.save_settings(settings):
            logger.info(f"[SETTINGS] Rate limits updated: webhook={webhook_limit}, api={api_limit}, command_api={command_api_limit}")
            system_logs_service.add_log('info', f'⚙️ [200] Rate limits updated - Webhook: {webhook_limit}, API: {api_limit}, Command API: {command_api_limit}')
            return jsonify({
                'success': True,
                'rate_limits': settings['rate_limits']
            }), 200
        else:
            return jsonify({'error': 'Failed to save settings'}), 500

    except Exception as e:
        logger.error(f"[SETTINGS_API] Error saving rate limits: {e}")
        return jsonify({'error': str(e)}), 500


@settings_bp.route('/api/settings/email', methods=['GET'])
@session_login_required
def get_email_settings():
    """ดึง Email Settings"""
    try:
        settings = settings_service.load_settings()
        email_settings = settings.get('email', {})

        # ไม่ส่ง password กลับไปให้ frontend
        email_settings_safe = email_settings.copy()
        if 'smtp_pass' in email_settings_safe:
            email_settings_safe['smtp_pass'] = '********' if email_settings.get('smtp_pass') else ''

        return jsonify(email_settings_safe), 200
    except Exception as e:
        logger.error(f"[SETTINGS_API] Error getting email settings: {e}")
        return jsonify({'error': str(e)}), 500


@settings_bp.route('/api/settings/email', methods=['POST'])
@session_login_required
def save_email_settings():
    """บันทึก Email Settings"""
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
                system_logs_service.add_log('error', '❌ [400] Email config failed - Missing required fields')
                return jsonify({'error': 'Missing required email configuration'}), 400

            if not to_emails or len(to_emails) == 0:
                system_logs_service.add_log('error', '❌ [400] Email config failed - No recipients specified')
                return jsonify({'error': 'At least one recipient email is required'}), 400

        # Load current settings
        settings = settings_service.load_settings()

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
        if settings_service.save_settings(settings):
            # Update email_handler instance
            try:
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
            system_logs_service.add_log('info', f'📧 [200] Email {status} - Server: {smtp_server}:{smtp_port}, Recipients: {recipients}')
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'Failed to save settings'}), 500

    except Exception as e:
        logger.error(f"[SETTINGS_API] Error saving email settings: {e}")
        return jsonify({'error': str(e)}), 500


@settings_bp.route('/api/settings/email/test', methods=['POST'])
@session_login_required
def test_email_settings():
    """ทดสอบส่ง Email"""
    try:
        settings = settings_service.load_settings()
        email_settings = settings.get('email', {})

        if not email_settings.get('enabled'):
            system_logs_service.add_log('warning', '⚠️ [400] Test email failed - Email notifications not enabled')
            return jsonify({'error': 'Email is not enabled'}), 400

        # อัพเดต email_handler ด้วย settings ปัจจุบัน
        try:
            email_handler.enabled = email_settings.get('enabled', False)
            email_handler.smtp_server = email_settings.get('smtp_server', 'smtp.gmail.com')
            email_handler.smtp_port = email_settings.get('smtp_port', 587)
            email_handler.sender_email = email_settings.get('smtp_user', '')
            email_handler.sender_password = email_settings.get('smtp_pass', '')
            email_handler.to_emails = email_settings.get('to_emails', [])
        except Exception as handler_error:
            logger.warning(f"[SETTINGS] Could not update email_handler: {handler_error}")

        # ส่ง test email
        test_subject = "MT5 Trading Bot - Test Email"
        test_message = f"This is a test email sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nIf you receive this email, your email configuration is working correctly!"

        # เรียกใช้ฟังก์ชันส่ง email
        success = email_send_alert_fn(test_subject, test_message)

        if success:
            logger.info("[SETTINGS] Test email sent successfully")
            recipients = len(email_settings.get('to_emails', []))
            system_logs_service.add_log('success', f'📧 [200] Test email sent successfully to {recipients} recipient(s)')
            return jsonify({'success': True, 'message': 'Test email sent'}), 200
        else:
            system_logs_service.add_log('error', '❌ [500] Test email failed - Check SMTP configuration')
            return jsonify({'error': 'Failed to send test email'}), 500

    except Exception as e:
        logger.error(f"[SETTINGS_API] Error testing email: {e}")
        return jsonify({'error': str(e)}), 500

