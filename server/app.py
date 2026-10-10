#!/usr/bin/env python3
"""
ServerInventory — Main Application Entry Point
A professional Linux server management application.
"""

import os
import sys
import ssl
import json
import logging
import signal
from datetime import datetime

from flask import Flask, send_from_directory, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Add server directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from config import Config
from auth import auth_bp, jwt_required_socket
from api_hardware import hardware_bp
from api_software import software_bp
from api_network import network_bp
from api_storage import storage_bp
from api_services import services_bp
from api_files import files_bp
from api_settings import settings_bp
from api_terminal import register_terminal_events
from api_system import system_bp

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Config.LOG_FILE)
    ]
)
logger = logging.getLogger('serverinventory')

# ─── Flask App ──────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, '..', 'web'),
    static_url_path=''
)

app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_UPLOAD_SIZE

# ─── Extensions ─────────────────────────────────────────────────────────────
CORS(app, supports_credentials=True)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='gevent',
    max_http_buffer_size=Config.MAX_UPLOAD_SIZE,
    ping_timeout=60,
    ping_interval=25
)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri="memory://"
)

# ─── Register Blueprints ────────────────────────────────────────────────────
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(hardware_bp, url_prefix='/api/hardware')
app.register_blueprint(software_bp, url_prefix='/api/software')
app.register_blueprint(network_bp, url_prefix='/api/network')
app.register_blueprint(storage_bp, url_prefix='/api/storage')
app.register_blueprint(services_bp, url_prefix='/api/services')
app.register_blueprint(files_bp, url_prefix='/api/files')
app.register_blueprint(settings_bp, url_prefix='/api/settings')
app.register_blueprint(system_bp, url_prefix='/api/system')

# Apply rate limiting to auth
limiter.limit("5 per minute")(auth_bp)

# ─── Register WebSocket Events ──────────────────────────────────────────────
register_terminal_events(socketio)

# ─── Serve Frontend ─────────────────────────────────────────────────────────
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    file_path = os.path.join(app.static_folder, path)
    if os.path.isfile(file_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

# ─── Health Check ────────────────────────────────────────────────────────────
@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'online',
        'service': 'ServerInventory',
        'version': Config.VERSION,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

# ─── Error Handlers ─────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large'}), 413

@app.errorhandler(429)
def rate_limit_exceeded(e):
    return jsonify({'error': 'Too many requests. Please try again later.'}), 429

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

# ─── Signal Handling ─────────────────────────────────────────────────────────
def signal_handler(sig, frame):
    logger.info("Shutting down ServerInventory...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ─── Main ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    logger.info(f"╔══════════════════════════════════════════╗")
    logger.info(f"║     ServerInventory v{Config.VERSION}            ║")
    logger.info(f"║     https://0.0.0.0:{Config.PORT}               ║")
    logger.info(f"╚══════════════════════════════════════════╝")

    ssl_context = None
    if Config.SSL_CERT and Config.SSL_KEY:
        if os.path.exists(Config.SSL_CERT) and os.path.exists(Config.SSL_KEY):
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(Config.SSL_CERT, Config.SSL_KEY)
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            logger.info("SSL/TLS enabled")
        else:
            logger.warning("SSL certificate files not found. Running without HTTPS.")
            logger.warning("Run 'serverinventory --generate-cert' to create certificates.")

    socketio.run(
        app,
        host='0.0.0.0',
        port=Config.PORT,
        ssl=ssl_context,
        debug=False,
        log_output=True,
        use_reloader=False
    )
