#!/usr/bin/env python3
"""
ServerInventory — Storage Information API
Disk usage, partitions, mount points, SMART data, and I/O stats.
"""

import os
import logging
import subprocess

import psutil
from flask import Blueprint, jsonify

from auth import jwt_required

logger = logging.getLogger('serverinventory.storage')
storage_bp = Blueprint('storage', __name__)


def _run_cmd(cmd, timeout=10):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ''


def _format_bytes(size):
    """Format bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def _get_disk_usage():
    """Get disk usage for all mounted partitions."""
    disks = []
    partitions = psutil.disk_partitions(all=False)

    for part in partitions:
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                'device': part.device,
                'mountpoint': part.mountpoint,
                'fstype': part.fstype,
                'opts': part.opts,
                'total': usage.total,
                'used': usage.used,
                'free': usage.free,
                'percent': usage.percent,
                'total_human': _format_bytes(usage.total),
                'used_human': _format_bytes(usage.used),
                'free_human': _format_bytes(usage.free)
            })
        except (PermissionError, OSError):
            continue

    return disks


def _get_block_devices():
    """Get block device information using lsblk."""
    devices = []
    output = _run_cmd("lsblk -J -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,SERIAL,ROTA,RM,RO,STATE,TRAN 2>/dev/null")

    if output:
        try:
            import json
            data = json.loads(output)
            devices = data.get('blockdevices', [])
        except Exception:
            pass

    # Fallback
    if not devices:
        output = _run_cmd("lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT 2>/dev/null")
        if output:
            lines = output.strip().split('\n')
            if lines:
                for line in lines[1:]:  # Skip header
                    devices.append({'raw': line.strip()})

    return devices


def _get_disk_io():
    """Get disk I/O statistics."""
    io = psutil.disk_io_counters(perdisk=True)
    result = {}

    for name, counters in io.items():
        result[name] = {
            'read_count': counters.read_count,
            'write_count': counters.write_count,
            'read_bytes': counters.read_bytes,
            'write_bytes': counters.write_bytes,
            'read_time_ms': counters.read_time,
            'write_time_ms': counters.write_time,
            'read_bytes_human': _format_bytes(counters.read_bytes),
            'write_bytes_human': _format_bytes(counters.write_bytes)
        }

    return result


def _get_smart_data():
    """Get SMART data for drives."""
    smart = []
    output = _run_cmd("lsblk -d -o NAME -n 2>/dev/null")

    if output:
        for disk in output.split('\n'):
            disk = disk.strip()
            if not disk or disk.startswith('loop') or disk.startswith('sr'):
                continue

            device = f"/dev/{disk}"
            data = _run_cmd(f"smartctl -H -A {device} 2>/dev/null")
            if data:
                health = 'UNKNOWN'
                if 'PASSED' in data:
                    health = 'PASSED'
                elif 'FAILED' in data:
                    health = 'FAILED'

                attrs = []
                in_attrs = False
                for line in data.split('\n'):
                    if 'ID#' in line:
                        in_attrs = True
                        continue
                    if in_attrs and line.strip():
                        parts = line.split()
                        if len(parts) >= 10:
                            attrs.append({
                                'id': parts[0],
                                'name': parts[1],
                                'value': parts[3],
                                'worst': parts[4],
                                'threshold': parts[5],
                                'raw_value': parts[9]
                            })

                smart.append({
                    'device': device,
                    'health': health,
                    'attributes': attrs[:15]  # Limit attributes
                })

    return smart


def _get_lvm_info():
    """Get LVM information if available."""
    lvm = {'volume_groups': [], 'logical_volumes': [], 'physical_volumes': []}

    # Volume Groups
    output = _run_cmd("vgs --noheadings --nosuffix --units g -o vg_name,vg_size,vg_free,pv_count,lv_count 2>/dev/null")
    if output:
        for line in output.split('\n'):
            parts = line.split()
            if len(parts) >= 5:
                lvm['volume_groups'].append({
                    'name': parts[0],
                    'size': parts[1] + ' GB',
                    'free': parts[2] + ' GB',
                    'pv_count': parts[3],
                    'lv_count': parts[4]
                })

    # Logical Volumes
    output = _run_cmd("lvs --noheadings --nosuffix --units g -o lv_name,vg_name,lv_size,lv_attr 2>/dev/null")
    if output:
        for line in output.split('\n'):
            parts = line.split()
            if len(parts) >= 4:
                lvm['logical_volumes'].append({
                    'name': parts[0],
                    'vg': parts[1],
                    'size': parts[2] + ' GB',
                    'attrs': parts[3]
                })

    return lvm


def _get_raid_info():
    """Get RAID information."""
    raid = []
    output = _run_cmd("cat /proc/mdstat 2>/dev/null")
    if output and 'Personalities' in output:
        raid.append({'source': 'mdstat', 'data': output})

    return raid


# ─── Routes ─────────────────────────────────────────────────────────────────

@storage_bp.route('/usage')
@jwt_required
def disk_usage():
    """Get disk usage for all mounted partitions."""
    return jsonify({'disks': _get_disk_usage()})


@storage_bp.route('/devices')
@jwt_required
def block_devices():
    """Get block device information."""
    return jsonify({'devices': _get_block_devices()})


@storage_bp.route('/io')
@jwt_required
def disk_io():
    """Get disk I/O statistics."""
    return jsonify({'io': _get_disk_io()})


@storage_bp.route('/smart')
@jwt_required
def smart():
    """Get SMART data."""
    return jsonify({'smart': _get_smart_data()})


@storage_bp.route('/lvm')
@jwt_required
def lvm():
    """Get LVM information."""
    return jsonify(_get_lvm_info())


@storage_bp.route('/raid')
@jwt_required
def raid():
    """Get RAID information."""
    return jsonify({'raid': _get_raid_info()})


@storage_bp.route('/overview')
@jwt_required
def overview():
    """Get storage overview."""
    return jsonify({
        'disks': _get_disk_usage(),
        'devices': _get_block_devices(),
        'io': _get_disk_io()
    })
