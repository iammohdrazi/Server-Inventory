#!/usr/bin/env python3
"""
ServerInventory — Authentication Module
Uses Linux PAM for system-level authentication with JWT sessions.
"""

import os
import pwd
import logging
import functools
from datetime import datetime, timedelta, timezone

import jwt
from flask import Blueprint, request, jsonify, make_response

from config import Config

logger = logging.getLogger('serverinventory.auth')
auth_bp = Blueprint('auth', __name__)

# Track failed login attempts for additional security
_failed_attempts = {}  # ip -> {'count': int, 'last': datetime}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


def _authenticate_pam(username, password):
    """Authenticate user using Linux PAM."""
    try:
        import pam
        p = pam.pam()
        return p.authenticate(username, password, service='login')
    except ImportError:
        logger.warning("python-pam not available, falling back to shadow auth")
        return _authenticate_shadow(username, password)
    except Exception as e:
        logger.error(f"PAM authentication error: {e}")
        return False


def _authenticate_shadow(username, password):
    """Fallback authentication using crypt and shadow passwords."""
    try:
        import crypt
        import spwd
        shadow = spwd.getspnam(username)
        return crypt.crypt(password, shadow.sp_pwdp) == shadow.sp_pwdp
    except Exception as e:
        logger.error(f"Shadow auth error: {e}")
        return False


def _get_user_info(username):
    """Get user information from the system."""
    try:
        pw = pwd.getpwnam(username)
        groups = []
        try:
            import grp
            groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
            # Add primary group
            primary_group = grp.getgrgid(pw.pw_gid).gr_name
            if primary_group not in groups:
                groups.insert(0, primary_group)
        except Exception:
            pass

        return {
            'username': username,
            'uid': pw.pw_uid,
            'gid': pw.pw_gid,
            'home': pw.pw_dir,
            'shell': pw.pw_shell,
            'groups': groups,
            'is_root': pw.pw_uid == 0
        }
    except KeyError:
        return None


def create_token(username):
    """Create a JWT token for the authenticated user."""
    now = datetime.now(timezone.utc)
    payload = {
        'sub': username,
        'iat': now,
        'exp': now + timedelta(minutes=Config.SESSION_TIMEOUT),
        'type': 'access'
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm=Config.JWT_ALGORITHM)


def create_refresh_token(username):
    """Create a refresh token with longer expiry."""
    now = datetime.now(timezone.utc)
    payload = {
        'sub': username,
        'iat': now,
        'exp': now + timedelta(hours=24),
        'type': 'refresh'
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm=Config.JWT_ALGORITHM)


def verify_token(token):
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(
            token,
            Config.SECRET_KEY,
            algorithms=[Config.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def jwt_required(f):
    """Decorator to require JWT authentication for routes."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Check Authorization header
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]

        # Check cookie
        if not token:
            token = request.cookies.get('si_token')

        if not token:
            return jsonify({'error': 'Authentication required'}), 401

        payload = verify_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401

        if payload.get('type') != 'access':
            return jsonify({'error': 'Invalid token type'}), 401

        # Attach user info to request
        request.current_user = payload['sub']
        request.user_info = _get_user_info(payload['sub'])

        return f(*args, **kwargs)
    return decorated


def jwt_required_socket(token):
    """Verify JWT for WebSocket connections."""
    if not token:
        return None
    payload = verify_token(token)
    if not payload or payload.get('type') != 'access':
        return None
    return payload['sub']


def _check_lockout(ip):
    """Check if an IP is locked out due to failed attempts."""
    if ip in _failed_attempts:
        entry = _failed_attempts[ip]
        if entry['count'] >= MAX_FAILED_ATTEMPTS:
            if datetime.now(timezone.utc) - entry['last'] < LOCKOUT_DURATION:
                return True
            else:
                # Lockout expired, reset
                del _failed_attempts[ip]
    return False


def _record_failed_attempt(ip):
    """Record a failed login attempt."""
    now = datetime.now(timezone.utc)
    if ip not in _failed_attempts:
        _failed_attempts[ip] = {'count': 0, 'last': now}
    _failed_attempts[ip]['count'] += 1
    _failed_attempts[ip]['last'] = now


def _clear_failed_attempts(ip):
    """Clear failed attempts for an IP after successful login."""
    _failed_attempts.pop(ip, None)


# ─── Routes ─────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return JWT tokens."""
    ip = request.remote_addr

    # Check lockout
    if _check_lockout(ip):
        remaining = LOCKOUT_DURATION.total_seconds() - \
            (datetime.now(timezone.utc) - _failed_attempts[ip]['last']).total_seconds()
        return jsonify({
            'error': f'Too many failed attempts. Try again in {int(remaining / 60)} minutes.'
        }), 429

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    # Authenticate
    if not _authenticate_pam(username, password):
        _record_failed_attempt(ip)
        attempts_left = MAX_FAILED_ATTEMPTS - _failed_attempts.get(ip, {}).get('count', 0)
        logger.warning(f"Failed login attempt for '{username}' from {ip}")
        return jsonify({
            'error': 'Invalid credentials',
            'attempts_remaining': max(0, attempts_left)
        }), 401

    _clear_failed_attempts(ip)

    # Get user info
    user_info = _get_user_info(username)
    if not user_info:
        return jsonify({'error': 'User account not found'}), 401

    # Generate tokens
    access_token = create_token(username)
    refresh_token = create_refresh_token(username)

    logger.info(f"User '{username}' logged in from {ip}")

    response = make_response(jsonify({
        'success': True,
        'user': user_info,
        'token': access_token,
        'expires_in': Config.SESSION_TIMEOUT * 60
    }))

    # Set secure cookies
    response.set_cookie(
        'si_token',
        access_token,
        httponly=True,
        secure=True,
        samesite='Strict',
        max_age=Config.SESSION_TIMEOUT * 60
    )
    response.set_cookie(
        'si_refresh',
        refresh_token,
        httponly=True,
        secure=True,
        samesite='Strict',
        max_age=86400,
        path='/api/auth/refresh'
    )

    return response


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """Refresh an expired access token using the refresh token."""
    refresh_token = request.cookies.get('si_refresh')
    if not refresh_token:
        data = request.get_json() or {}
        refresh_token = data.get('refresh_token')

    if not refresh_token:
        return jsonify({'error': 'Refresh token required'}), 401

    payload = verify_token(refresh_token)
    if not payload or payload.get('type') != 'refresh':
        return jsonify({'error': 'Invalid refresh token'}), 401

    username = payload['sub']
    user_info = _get_user_info(username)
    if not user_info:
        return jsonify({'error': 'User not found'}), 401

    # Issue new access token
    new_token = create_token(username)

    response = make_response(jsonify({
        'success': True,
        'token': new_token,
        'user': user_info,
        'expires_in': Config.SESSION_TIMEOUT * 60
    }))

    response.set_cookie(
        'si_token',
        new_token,
        httponly=True,
        secure=True,
        samesite='Strict',
        max_age=Config.SESSION_TIMEOUT * 60
    )

    return response


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Log out the user by clearing session cookies."""
    response = make_response(jsonify({'success': True, 'message': 'Logged out'}))
    response.delete_cookie('si_token')
    response.delete_cookie('si_refresh', path='/api/auth/refresh')
    logger.info(f"User logged out from {request.remote_addr}")
    return response


@auth_bp.route('/verify', methods=['GET'])
def verify():
    """Verify if current token is valid."""
    token = None
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get('si_token')

    if not token:
        return jsonify({'authenticated': False}), 401

    payload = verify_token(token)
    if not payload or payload.get('type') != 'access':
        return jsonify({'authenticated': False}), 401

    user_info = _get_user_info(payload['sub'])
    return jsonify({
        'authenticated': True,
        'user': user_info
    })
