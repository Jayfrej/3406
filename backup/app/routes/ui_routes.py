"""
UI Routes - Serves the main web interface
"""
from flask import Blueprint, send_file, current_app
import os

ui_bp = Blueprint('ui', __name__)


@ui_bp.route('/')
def index():
    """Serve the main UI page"""
    try:
        static_folder = current_app.static_folder
        index_path = os.path.join(static_folder, 'index.html')

        if not os.path.exists(index_path):
            return "UI not found. Please ensure index.html exists in the static folder.", 404

        return send_file(index_path)
    except Exception as e:
        current_app.logger.error(f"[UI_ROUTES] Error serving index: {e}")
        return f"Error loading UI: {str(e)}", 500


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

