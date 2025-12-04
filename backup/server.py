#!/usr/bin/env python3
"""
MT5 Trading Bot Server - Application Entry Point

This file is now a minimal entry point (~50 lines).
All business logic has been refactored into:
- app/services/     - Business logic layer
- app/routes/       - API endpoints
- app/core/         - Application factory
- app/              - Core modules (session_manager, email_handler, etc.)
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging with UTF-8 encoding for Windows
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Fix StreamHandler encoding for Windows console
import sys
if sys.platform == 'win32':
    # Force UTF-8 for console output on Windows
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

logger = logging.getLogger(__name__)


def main():
    """Main application entry point"""
    logger.info("=" * 80)
    logger.info("MT5 TRADING BOT SERVER - STARTING")
    logger.info("=" * 80)

    # Import application factory
    from app.core.app_factory import create_app

    # Create Flask application with all services and routes
    app = create_app()

    # Get configuration from environment
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'

    logger.info(f"[SERVER] Starting on {host}:{port}")
    logger.info(f"[SERVER] Debug mode: {debug}")
    logger.info("=" * 80)

    # Run the application
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n[SERVER] Shutting down gracefully...")
    except Exception as e:
        logger.error(f"[SERVER] Fatal error: {e}", exc_info=True)
        raise

