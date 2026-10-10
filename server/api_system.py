#!/usr/bin/env python3
"""
ServerInventory — System Overview API
General system information and dashboard data.
"""

import os
import logging
import subprocess
from datetime import datetime, timezone

import psutil
from flask import Blueprint, jsonify

from auth import jwt_required

logger = logging.getLogger('serverinventory.system')
system_bp = Blueprint('system', __name__)


def _run_cmd(cmd, timeout=10):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except Exception:
        return ''


def _format_bytes(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


@system_bp.route('/dashboard')
@jwt_required
def dashboard():
    """Get dashboard overview data."""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count()

    # Memory
    mem = psutil.virtual_memory()

    # Disk
    disk_total = 0
    disk_used = 0
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disk_total += usage.total
            disk_used += usage.used
        except (PermissionError, OSError):
            pass

    # Network
    net = psutil.net_io_counters()

    # Uptime
    boot = psutil.boot_time()
    uptime_secs = int((datetime.now(timezone.utc).timestamp()) - boot)
    days = uptime_secs // 86400
    hours = (uptime_secs % 86400) // 3600
    mins = (uptime_secs % 3600) // 60

    # Processes
    proc_count = len(psutil.pids())

    # Users logged in
    users = len(psutil.users())

    # Load average
    load_avg = list(os.getloadavg()) if hasattr(os, 'getloadavg') else [0, 0, 0]

    # OS info
    os_pretty = _run_cmd("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'")
    kernel = _run_cmd('uname -r')
    hostname = _run_cmd('hostname')

    # Services summary
    active_services = _run_cmd("systemctl list-units --type=service --state=active --no-pager --no-legend 2>/dev/null | wc -l")
    failed_services = _run_cmd("systemctl list-units --type=service --state=failed --no-pager --no-legend 2>/dev/null | wc -l")

    return jsonify({
        'hostname': hostname,
        'os': os_pretty or 'Linux',
        'kernel': kernel,
        'uptime': {
            'seconds': uptime_secs,
            'formatted': f"{days}d {hours}h {mins}m",
            'boot_time': boot
        },
        'cpu': {
            'percent': cpu_percent,
            'cores': cpu_count,
            'load_avg': [round(val, 2) for val in load_avg]
        },
        'memory': {
            'total': mem.total,
            'used': mem.used,
            'percent': mem.percent,
            'total_human': _format_bytes(mem.total),
            'used_human': _format_bytes(mem.used)
        },
        'disk': {
            'total': disk_total,
            'used': disk_used,
            'percent': round((disk_used / disk_total * 100) if disk_total else 0, 1),
            'total_human': _format_bytes(disk_total),
            'used_human': _format_bytes(disk_used)
        },
        'network': {
            'bytes_sent': net.bytes_sent,
            'bytes_recv': net.bytes_recv,
            'sent_human': _format_bytes(net.bytes_sent),
            'recv_human': _format_bytes(net.bytes_recv)
        },
        'processes': proc_count,
        'users_logged_in': users,
        'services': {
            'active': int(active_services) if active_services.isdigit() else 0,
            'failed': int(failed_services) if failed_services.isdigit() else 0
        },
        'timestamp': datetime.now(timezone.utc).isoformat() + 'Z'
    })


@system_bp.route('/live')
@jwt_required
def live_stats():
    """Get live stats for real-time monitoring (lightweight)."""
    cpu = psutil.cpu_percent(interval=0.3, percpu=True)
    mem = psutil.virtual_memory()
    net = psutil.net_io_counters()

    return jsonify({
        'cpu_percent': round(sum(cpu) / len(cpu), 1) if cpu else 0,
        'cpu_per_core': cpu,
        'memory_percent': mem.percent,
        'memory_used': mem.used,
        'net_sent': net.bytes_sent,
        'net_recv': net.bytes_recv,
        'timestamp': datetime.now(timezone.utc).isoformat() + 'Z'
    })
