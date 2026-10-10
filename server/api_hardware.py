#!/usr/bin/env python3
"""
ServerInventory — Hardware Information API
Collects comprehensive hardware information from the Linux system.
"""

import os
import logging
import subprocess

import psutil
from flask import Blueprint, jsonify

from auth import jwt_required

logger = logging.getLogger('serverinventory.hardware')
hardware_bp = Blueprint('hardware', __name__)


def _run_cmd(cmd, timeout=10):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ''


def _read_file(path):
    """Read a file and return contents."""
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except Exception:
        return ''


def _get_cpu_info():
    """Get detailed CPU information."""
    info = {
        'model': '',
        'vendor': '',
        'cores_physical': psutil.cpu_count(logical=False) or 0,
        'cores_logical': psutil.cpu_count(logical=True) or 0,
        'frequency_mhz': 0,
        'frequency_max_mhz': 0,
        'cache_size': '',
        'architecture': _run_cmd('uname -m'),
        'usage_percent': psutil.cpu_percent(interval=1, percpu=False),
        'usage_per_core': psutil.cpu_percent(interval=0.1, percpu=True),
        'load_average': list(os.getloadavg()) if hasattr(os, 'getloadavg') else [],
        'flags': [],
        'temperature': None
    }

    # Parse /proc/cpuinfo
    cpuinfo = _read_file('/proc/cpuinfo')
    for line in cpuinfo.split('\n'):
        if ':' in line:
            key, _, val = line.partition(':')
            key = key.strip().lower()
            val = val.strip()
            if key == 'model name' and not info['model']:
                info['model'] = val
            elif key == 'vendor_id' and not info['vendor']:
                info['vendor'] = val
            elif key == 'cpu mhz' and not info['frequency_mhz']:
                try:
                    info['frequency_mhz'] = round(float(val), 2)
                except ValueError:
                    pass
            elif key == 'cache size' and not info['cache_size']:
                info['cache_size'] = val
            elif key == 'flags' and not info['flags']:
                info['flags'] = val.split()[:20]  # Limit flags

    # CPU frequency
    freq = psutil.cpu_freq()
    if freq:
        if not info['frequency_mhz']:
            info['frequency_mhz'] = round(freq.current, 2)
        info['frequency_max_mhz'] = round(freq.max, 2) if freq.max else 0

    # CPU temperature
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name in ['coretemp', 'k10temp', 'cpu_thermal', 'acpitz']:
                if name in temps and temps[name]:
                    info['temperature'] = {
                        'current': temps[name][0].current,
                        'high': temps[name][0].high,
                        'critical': temps[name][0].critical
                    }
                    break
    except Exception:
        pass

    return info


def _get_memory_info():
    """Get detailed memory information."""
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return {
        'ram': {
            'total': vm.total,
            'available': vm.available,
            'used': vm.used,
            'free': vm.free,
            'percent': vm.percent,
            'buffers': getattr(vm, 'buffers', 0),
            'cached': getattr(vm, 'cached', 0)
        },
        'swap': {
            'total': swap.total,
            'used': swap.used,
            'free': swap.free,
            'percent': swap.percent
        }
    }


def _get_motherboard_info():
    """Get motherboard/system information from DMI."""
    info = {
        'manufacturer': _read_file('/sys/class/dmi/id/board_vendor'),
        'product': _read_file('/sys/class/dmi/id/board_name'),
        'version': _read_file('/sys/class/dmi/id/board_version'),
        'serial': _read_file('/sys/class/dmi/id/board_serial'),
        'bios_vendor': _read_file('/sys/class/dmi/id/bios_vendor'),
        'bios_version': _read_file('/sys/class/dmi/id/bios_version'),
        'bios_date': _read_file('/sys/class/dmi/id/bios_date'),
        'system_vendor': _read_file('/sys/class/dmi/id/sys_vendor'),
        'system_product': _read_file('/sys/class/dmi/id/product_name'),
        'system_version': _read_file('/sys/class/dmi/id/product_version')
    }
    return info


def _get_gpu_info():
    """Get GPU information."""
    gpus = []

    # Try lspci
    output = _run_cmd("lspci 2>/dev/null | grep -iE 'vga|3d|display'")
    if output:
        for line in output.split('\n'):
            if line.strip():
                gpus.append({'name': line.strip(), 'driver': ''})

    # Try nvidia-smi for NVIDIA GPUs
    nvidia_info = _run_cmd("nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,temperature.gpu,utilization.gpu --format=csv,noheader,nounits 2>/dev/null")
    if nvidia_info:
        gpus = []
        for line in nvidia_info.split('\n'):
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 6:
                gpus.append({
                    'name': parts[0],
                    'driver': parts[1],
                    'memory_total_mb': int(parts[2]) if parts[2].isdigit() else 0,
                    'memory_used_mb': int(parts[3]) if parts[3].isdigit() else 0,
                    'temperature': int(parts[4]) if parts[4].isdigit() else None,
                    'utilization': int(parts[5]) if parts[5].isdigit() else 0
                })

    return gpus


def _get_usb_devices():
    """Get connected USB devices."""
    devices = []
    output = _run_cmd("lsusb 2>/dev/null")
    if output:
        for line in output.split('\n'):
            if line.strip():
                devices.append(line.strip())
    return devices


def _get_pci_devices():
    """Get PCI devices."""
    devices = []
    output = _run_cmd("lspci -mm 2>/dev/null")
    if output:
        for line in output.split('\n')[:30]:  # Limit to 30
            if line.strip():
                devices.append(line.strip())
    return devices


def _get_system_uptime():
    """Get system uptime."""
    try:
        uptime_seconds = _read_file('/proc/uptime').split()[0]
        seconds = int(float(uptime_seconds))
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        return {
            'seconds': seconds,
            'formatted': f"{days}d {hours}h {minutes}m",
            'boot_time': psutil.boot_time()
        }
    except Exception:
        return {'seconds': 0, 'formatted': 'Unknown', 'boot_time': 0}


def _get_kernel_info():
    """Get kernel and OS information."""
    return {
        'kernel': _run_cmd('uname -r'),
        'kernel_full': _run_cmd('uname -a'),
        'os_name': _read_file('/etc/os-release').split('\n')[0].replace('NAME=', '').strip('"') if os.path.exists('/etc/os-release') else '',
        'os_version': _run_cmd("cat /etc/os-release 2>/dev/null | grep VERSION_ID | cut -d= -f2 | tr -d '\"'"),
        'os_pretty': _run_cmd("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'"),
        'hostname': _run_cmd('hostname'),
        'fqdn': _run_cmd('hostname -f 2>/dev/null') or _run_cmd('hostname')
    }


# ─── Routes ─────────────────────────────────────────────────────────────────

@hardware_bp.route('/overview')
@jwt_required
def overview():
    """Get complete hardware overview."""
    return jsonify({
        'cpu': _get_cpu_info(),
        'memory': _get_memory_info(),
        'system': _get_kernel_info(),
        'uptime': _get_system_uptime()
    })


@hardware_bp.route('/cpu')
@jwt_required
def cpu_info():
    """Get detailed CPU information."""
    return jsonify(_get_cpu_info())


@hardware_bp.route('/memory')
@jwt_required
def memory_info():
    """Get detailed memory information."""
    return jsonify(_get_memory_info())


@hardware_bp.route('/motherboard')
@jwt_required
def motherboard_info():
    """Get motherboard and BIOS information."""
    return jsonify(_get_motherboard_info())


@hardware_bp.route('/gpu')
@jwt_required
def gpu_info():
    """Get GPU information."""
    return jsonify({'gpus': _get_gpu_info()})


@hardware_bp.route('/usb')
@jwt_required
def usb_info():
    """Get USB devices."""
    return jsonify({'devices': _get_usb_devices()})


@hardware_bp.route('/pci')
@jwt_required
def pci_info():
    """Get PCI devices."""
    return jsonify({'devices': _get_pci_devices()})


@hardware_bp.route('/all')
@jwt_required
def all_info():
    """Get all hardware information."""
    return jsonify({
        'cpu': _get_cpu_info(),
        'memory': _get_memory_info(),
        'motherboard': _get_motherboard_info(),
        'gpu': _get_gpu_info(),
        'usb': _get_usb_devices(),
        'pci': _get_pci_devices(),
        'system': _get_kernel_info(),
        'uptime': _get_system_uptime()
    })
