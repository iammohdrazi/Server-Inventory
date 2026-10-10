#!/usr/bin/env python3
"""
ServerInventory — Software Information API
Lists installed packages, running processes, and provides descriptions.
"""

import logging
import subprocess

import psutil
from flask import Blueprint, jsonify, request

from auth import jwt_required
from descriptions import get_description

logger = logging.getLogger('serverinventory.software')
software_bp = Blueprint('software', __name__)


def _run_cmd(cmd, timeout=30):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ''


def _get_package_manager():
    """Detect the system's package manager."""
    managers = [
        ('dpkg', 'dpkg-query'),
        ('rpm', 'rpm'),
        ('pacman', 'pacman'),
        ('apk', 'apk')
    ]
    for name, cmd in managers:
        if _run_cmd(f"which {cmd} 2>/dev/null"):
            return name
    return None


def _get_installed_packages(search=None, limit=100, offset=0):
    """Get list of installed packages."""
    pm = _get_package_manager()
    packages = []

    if pm == 'dpkg':
        cmd = "dpkg-query -W -f='${Package}\t${Version}\t${Installed-Size}\t${Status}\t${Description}\n'"
        output = _run_cmd(cmd, timeout=60)
        for line in output.split('\n'):
            parts = line.split('\t')
            if len(parts) >= 4 and 'installed' in parts[3].lower():
                pkg = {
                    'name': parts[0],
                    'version': parts[1],
                    'size': f"{int(parts[2]) if parts[2].isdigit() else 0} KB",
                    'description': parts[4] if len(parts) > 4 else '',
                    'manager': 'apt/dpkg'
                }
                if search:
                    if search.lower() in pkg['name'].lower() or search.lower() in pkg.get('description', '').lower():
                        packages.append(pkg)
                else:
                    packages.append(pkg)

    elif pm == 'rpm':
        cmd = "rpm -qa --queryformat '%{NAME}\t%{VERSION}-%{RELEASE}\t%{SIZE}\t%{SUMMARY}\n'"
        output = _run_cmd(cmd, timeout=60)
        for line in output.split('\n'):
            parts = line.split('\t')
            if len(parts) >= 3:
                pkg = {
                    'name': parts[0],
                    'version': parts[1],
                    'size': _format_bytes(int(parts[2])) if parts[2].isdigit() else '0 B',
                    'description': parts[3] if len(parts) > 3 else '',
                    'manager': 'rpm/yum'
                }
                if search:
                    if search.lower() in pkg['name'].lower() or search.lower() in pkg.get('description', '').lower():
                        packages.append(pkg)
                else:
                    packages.append(pkg)

    elif pm == 'pacman':
        cmd = "pacman -Q"
        output = _run_cmd(cmd, timeout=60)
        for line in output.split('\n'):
            parts = line.split()
            if len(parts) >= 2:
                pkg = {
                    'name': parts[0],
                    'version': parts[1],
                    'size': '',
                    'description': '',
                    'manager': 'pacman'
                }
                if search:
                    if search.lower() in pkg['name'].lower():
                        packages.append(pkg)
                else:
                    packages.append(pkg)

    total = len(packages)
    packages.sort(key=lambda x: x['name'])
    packages = packages[offset:offset + limit]

    return {'packages': packages, 'total': total, 'offset': offset, 'limit': limit}


def _get_running_processes(sort_by='cpu', limit=50):
    """Get list of running processes."""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'status',
                                      'cpu_percent', 'memory_percent',
                                      'create_time', 'cmdline', 'num_threads']):
        try:
            info = proc.info
            processes.append({
                'pid': info['pid'],
                'name': info['name'],
                'user': info['username'] or 'root',
                'status': info['status'],
                'cpu_percent': round(info['cpu_percent'] or 0, 1),
                'memory_percent': round(info['memory_percent'] or 0, 1),
                'threads': info['num_threads'] or 0,
                'command': ' '.join(info['cmdline'][:5]) if info['cmdline'] else info['name'],
                'description': get_description(info['name'])
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # Sort
    if sort_by == 'cpu':
        processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
    elif sort_by == 'memory':
        processes.sort(key=lambda x: x['memory_percent'], reverse=True)
    elif sort_by == 'name':
        processes.sort(key=lambda x: x['name'].lower())
    elif sort_by == 'pid':
        processes.sort(key=lambda x: x['pid'])

    return processes[:limit]


def _get_startup_programs():
    """Get startup/init programs."""
    programs = []

    # Systemd enabled services
    output = _run_cmd("systemctl list-unit-files --type=service --state=enabled --no-pager --plain 2>/dev/null")
    if output:
        for line in output.split('\n'):
            parts = line.split()
            if len(parts) >= 2 and parts[1] == 'enabled':
                name = parts[0].replace('.service', '')
                programs.append({
                    'name': name,
                    'type': 'systemd',
                    'state': 'enabled',
                    'description': get_description(name)
                })

    return programs


def _format_bytes(size):
    """Format bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


# ─── Routes ─────────────────────────────────────────────────────────────────

@software_bp.route('/packages')
@jwt_required
def packages():
    """Get installed packages."""
    search = request.args.get('search', None)
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))
    return jsonify(_get_installed_packages(search=search, limit=limit, offset=offset))


@software_bp.route('/processes')
@jwt_required
def processes():
    """Get running processes."""
    sort_by = request.args.get('sort', 'cpu')
    limit = min(int(request.args.get('limit', 50)), 200)
    return jsonify({'processes': _get_running_processes(sort_by=sort_by, limit=limit)})


@software_bp.route('/processes/<int:pid>/kill', methods=['POST'])
@jwt_required
def kill_process(pid):
    """Kill a process by PID."""
    try:
        proc = psutil.Process(pid)
        data = request.get_json() or {}
        force = data.get('force', False)

        if force:
            proc.kill()
        else:
            proc.terminate()

        return jsonify({'success': True, 'message': f'Process {pid} {"killed" if force else "terminated"}'})
    except psutil.NoSuchProcess:
        return jsonify({'error': 'Process not found'}), 404
    except psutil.AccessDenied:
        return jsonify({'error': 'Access denied. Insufficient permissions.'}), 403


@software_bp.route('/startup')
@jwt_required
def startup():
    """Get startup programs."""
    return jsonify({'programs': _get_startup_programs()})


@software_bp.route('/updates')
@jwt_required
def available_updates():
    """Check for available package updates."""
    pm = _get_package_manager()
    updates = []

    if pm == 'dpkg':
        _run_cmd("apt-get update -qq 2>/dev/null", timeout=60)
        output = _run_cmd("apt list --upgradable 2>/dev/null", timeout=30)
        if output:
            for line in output.split('\n'):
                if '/' in line and 'upgradable' in line.lower():
                    name = line.split('/')[0]
                    updates.append({'name': name, 'line': line.strip()})

    elif pm == 'rpm':
        output = _run_cmd("yum check-update 2>/dev/null", timeout=60)
        if output:
            for line in output.split('\n'):
                parts = line.split()
                if len(parts) >= 3 and '.' in parts[0]:
                    updates.append({'name': parts[0], 'version': parts[1]})

    return jsonify({'updates': updates, 'count': len(updates)})
