"""
UI Routes - Serves the main web interface

Updated for Multi-User SaaS:
- /login serves login page
- / (dashboard) requires authentication
- Redirects unauthenticated users to login

Reference: MIGRATION_ROADMAP.md Phase 5.4
"""
from flask import Blueprint, send_file, current_app, session, redirect
import os

ui_bp = Blueprint('ui', __name__)


@ui_bp.route('/')
def index():
    """
    Serve the main dashboard - requires authentication.

    Per MIGRATION_ROADMAP.md Phase 5.4: Protect dashboard route
    """
    # Check for authentication (support both new and legacy sessions)
    if not session.get('user_id') and not session.get('auth'):
        return redirect('/login')

    try:
        static_folder = current_app.static_folder
        index_path = os.path.join(static_folder, 'index.html')

        if not os.path.exists(index_path):
            return "UI not found. Please ensure index.html exists in the static folder.", 404

        return send_file(index_path)
    except Exception as e:
        current_app.logger.error(f"[UI_ROUTES] Error serving index: {e}")
        return f"Error loading UI: {str(e)}", 500


@ui_bp.route('/login')
def login_page():
    """
    Serve the login page.

    Per MIGRATION_ROADMAP.md Phase 5.4
    """
    # Redirect to dashboard if already logged in
    if session.get('user_id') or session.get('auth'):
        return redirect('/')

    try:
        static_folder = current_app.static_folder
        login_path = os.path.join(static_folder, 'login.html')

        if not os.path.exists(login_path):
            return "Login page not found.", 404

        return send_file(login_path)
    except Exception as e:
        current_app.logger.error(f"[UI_ROUTES] Error serving login: {e}")
        return f"Error loading login page: {str(e)}", 500


@ui_bp.route('/admin')
def admin_page():
    """
    Serve the admin dashboard - admin only.

    Per MIGRATION_ROADMAP.md Phase 5.4
    """
    # Check authentication
    if not session.get('user_id') and not session.get('auth'):
        return redirect('/login')

    # Check admin privilege
    is_admin = session.get('is_admin', False)
    user_email = session.get('email', '')
    admin_email = os.getenv('ADMIN_EMAIL', '')

    if not is_admin and user_email.lower() != admin_email.lower():
        # For legacy sessions, allow access
        if not session.get('auth'):
            return "Access Denied - Admin privileges required", 403

    try:
        static_folder = current_app.static_folder
        admin_path = os.path.join(static_folder, 'admin.html')

        if not os.path.exists(admin_path):
            # Fallback to main dashboard for now
            return redirect('/')

        return send_file(admin_path)
    except Exception as e:
        current_app.logger.error(f"[UI_ROUTES] Error serving admin: {e}")
        return redirect('/')


@ui_bp.route('/favicon.ico')
def favicon():
    """Serve favicon"""
    try:
        static_folder = current_app.static_folder
        favicon_path = os.path.join(static_folder, 'favicon.ico')

        if os.path.exists(favicon_path):
            return send_file(favicon_path, mimetype='image/x-icon')
        else:
            return '', 204
    except Exception as e:
        current_app.logger.error(f"[UI_ROUTES] Error serving favicon: {e}")
        return '', 204

