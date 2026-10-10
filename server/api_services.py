#!/usr/bin/env python3
"""
ServerInventory — Services Management API
Start, stop, restart, enable, disable systemd services.
"""

import os
import logging
import subprocess

from flask import Blueprint, jsonify, request

from auth import jwt_required
from descriptions import get_description

logger = logging.getLogger('serverinventory.services')
services_bp = Blueprint('services', __name__)


def _run_cmd(cmd, timeout=30):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, '', 'Command timed out'
    except Exception as e:
        return -1, '', str(e)


def _get_all_services():
    """Get all systemd services with their status."""
    services = []

    code, output, _ = _run_cmd(
        "systemctl list-units --type=service --all --no-pager --plain --no-legend 2>/dev/null"
    )

    if output:
        for line in output.split('\n'):
            parts = line.split(None, 4)
            if len(parts) >= 4:
                name = parts[0].replace('.service', '')
                load = parts[1]
                active = parts[2]
                sub = parts[3]
                desc = parts[4] if len(parts) > 4 else ''

                services.append({
                    'name': name,
                    'load': load,
                    'active': active,
                    'sub': sub,
                    'description_short': desc,
                    'description': get_description(name)
                })

    return services


def _get_service_detail(name):
    """Get detailed status of a specific service."""
    code, output, _ = _run_cmd(f"systemctl status {name}.service --no-pager 2>/dev/null")

    detail = {
        'name': name,
        'status_output': output,
        'active': '',
        'enabled': '',
        'pid': None,
        'memory': '',
        'cpu': '',
        'tasks': '',
        'logs': [],
        'description': get_description(name)
    }

    # Get active state
    code, active, _ = _run_cmd(f"systemctl is-active {name}.service 2>/dev/null")
    detail['active'] = active

    # Get enabled state
    code, enabled, _ = _run_cmd(f"systemctl is-enabled {name}.service 2>/dev/null")
    detail['enabled'] = enabled

    # Parse status output for details
    for line in output.split('\n'):
        line = line.strip()
        if line.startswith('Main PID:'):
            try:
                detail['pid'] = int(line.split(':')[1].strip().split()[0])
            except (ValueError, IndexError):
                pass
        elif line.startswith('Memory:'):
            detail['memory'] = line.split(':', 1)[1].strip()
        elif line.startswith('CPU:'):
            detail['cpu'] = line.split(':', 1)[1].strip()
        elif line.startswith('Tasks:'):
            detail['tasks'] = line.split(':', 1)[1].strip()

    # Get recent logs
    code, logs, _ = _run_cmd(
        f"journalctl -u {name}.service --no-pager -n 20 --output=short-iso 2>/dev/null"
    )
    if logs:
        detail['logs'] = logs.split('\n')

    return detail


def _control_service(name, action):
    """Control a systemd service (start, stop, restart, reload, enable, disable)."""
    allowed_actions = ['start', 'stop', 'restart', 'reload', 'enable', 'disable']

    if action not in allowed_actions:
        return False, f"Invalid action '{action}'. Allowed: {', '.join(allowed_actions)}"

    # Security: sanitize service name
    if not name.replace('-', '').replace('_', '').replace('.', '').isalnum():
        return False, "Invalid service name"

    cmd = f"systemctl {action} {name}.service 2>&1"
    code, output, error = _run_cmd(cmd)

    if code == 0:
        logger.info(f"Service '{name}' action '{action}' succeeded")
        return True, f"Service {name} {action} successful"
    else:
        logger.warning(f"Service '{name}' action '{action}' failed: {error or output}")
        return False, error or output or f"Failed to {action} {name}"


def _get_service_logs(name, lines=50):
    """Get service logs from journalctl."""
    lines = min(int(lines), 500)
    code, output, _ = _run_cmd(
        f"journalctl -u {name}.service --no-pager -n {lines} --output=short-iso 2>/dev/null"
    )
    return output.split('\n') if output else []


def _get_failed_services():
    """Get list of failed services."""
    code, output, _ = _run_cmd(
        "systemctl list-units --type=service --state=failed --no-pager --plain --no-legend 2>/dev/null"
    )
    failed = []
    if output:
        for line in output.split('\n'):
            parts = line.split(None, 4)
            if len(parts) >= 1:
                name = parts[0].replace('.service', '')
                failed.append({
                    'name': name,
                    'description': get_description(name)
                })
    return failed


# ─── Routes ─────────────────────────────────────────────────────────────────

@services_bp.route('/list')
@jwt_required
def list_services():
    """Get all services."""
    search = request.args.get('search', '').lower()
    state = request.args.get('state', '')  # active, inactive, failed

    services = _get_all_services()

    if search:
        services = [s for s in services
                     if search in s['name'].lower() or search in s.get('description_short', '').lower()]

    if state:
        services = [s for s in services if s['active'] == state]

    return jsonify({
        'services': services,
        'total': len(services)
    })


@services_bp.route('/<name>/status')
@jwt_required
def service_status(name):
    """Get detailed service status."""
    return jsonify(_get_service_detail(name))


@services_bp.route('/<name>/logs')
@jwt_required
def service_logs(name):
    """Get service logs."""
    lines = request.args.get('lines', 50)
    return jsonify({'logs': _get_service_logs(name, lines)})


@services_bp.route('/<name>/control', methods=['POST'])
@jwt_required
def control_service(name):
    """Control a service (start/stop/restart/enable/disable)."""
    data = request.get_json() or {}
    action = data.get('action', '')

    if not action:
        return jsonify({'error': 'Action is required'}), 400

    success, message = _control_service(name, action)

    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'error': message}), 400


@services_bp.route('/failed')
@jwt_required
def failed_services():
    """Get failed services."""
    return jsonify({'services': _get_failed_services()})
