#!/usr/bin/env python3
"""
ServerInventory — Configuration Module
"""

import os
import secrets
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('SERVERINVENTORY_DATA', '/var/lib/serverinventory')
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')


def _load_or_create_config():
    """Load config from file or create defaults."""
    defaults = {
        'secret_key': secrets.token_hex(32),
        'port': 9443,
        'session_timeout_minutes': 30,
        'max_upload_size_mb': 500,
        'allowed_file_roots': ['/'],
        'blocked_paths': [
            '/proc', '/sys', '/dev', '/run/lock',
            '/var/lib/serverinventory'
        ],
        'enable_terminal': True,
        'enable_file_manager': True,
        'enable_service_control': True,
        'log_level': 'INFO'
    }

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved = json.load(f)
            defaults.update(saved)
        except Exception:
            pass

    return defaults


_config = _load_or_create_config()


class Config:
    """Application configuration."""

    VERSION = '1.0.0'
    SECRET_KEY = _config.get('secret_key', secrets.token_hex(32))
    PORT = int(os.environ.get('SERVERINVENTORY_PORT', _config.get('port', 9443)))

    # SSL
    SSL_CERT = os.environ.get(
        'SERVERINVENTORY_SSL_CERT',
        os.path.join(DATA_DIR, 'certs', 'server.crt')
    )
    SSL_KEY = os.environ.get(
        'SERVERINVENTORY_SSL_KEY',
        os.path.join(DATA_DIR, 'certs', 'server.key')
    )

    # Auth
    SESSION_TIMEOUT = _config.get('session_timeout_minutes', 30)  # minutes
    JWT_ALGORITHM = 'HS256'

    # Upload
    MAX_UPLOAD_SIZE = _config.get('max_upload_size_mb', 500) * 1024 * 1024

    # File Manager
    ALLOWED_FILE_ROOTS = _config.get('allowed_file_roots', ['/'])
    BLOCKED_PATHS = _config.get('blocked_paths', [
        '/proc', '/sys', '/dev', '/run/lock'
    ])

    # Features
    ENABLE_TERMINAL = _config.get('enable_terminal', True)
    ENABLE_FILE_MANAGER = _config.get('enable_file_manager', True)
    ENABLE_SERVICE_CONTROL = _config.get('enable_service_control', True)

    # Logging
    LOG_FILE = os.environ.get(
        'SERVERINVENTORY_LOG',
        os.path.join(DATA_DIR, 'serverinventory.log')
    )
    LOG_LEVEL = _config.get('log_level', 'INFO')

    # Data
    DATA_DIR = DATA_DIR
