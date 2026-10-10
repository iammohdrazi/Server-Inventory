#!/usr/bin/env python3
"""
ServerInventory — Network Information API
Network interfaces, connections, firewall, DNS, and routing info.
"""

import logging
import subprocess
import socket

import psutil
from flask import Blueprint, jsonify, request

from auth import jwt_required
from descriptions import get_description

logger = logging.getLogger('serverinventory.network')
network_bp = Blueprint('network', __name__)


def _run_cmd(cmd, timeout=10):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ''


def _get_interfaces():
    """Get network interface information."""
    interfaces = []
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    io = psutil.net_io_counters(pernic=True)

    for name, stat in stats.items():
        iface = {
            'name': name,
            'is_up': stat.isup,
            'speed_mbps': stat.speed,
            'mtu': stat.mtu,
            'duplex': str(stat.duplex) if stat.duplex else 'unknown',
            'addresses': [],
            'io': None
        }

        # Addresses
        if name in addrs:
            for addr in addrs[name]:
                addr_info = {
                    'family': str(addr.family),
                    'address': addr.address,
                    'netmask': addr.netmask,
                    'broadcast': addr.broadcast
                }
                if addr.family == socket.AF_INET:
                    addr_info['type'] = 'IPv4'
                elif addr.family == socket.AF_INET6:
                    addr_info['type'] = 'IPv6'
                elif addr.family == psutil.AF_LINK:
                    addr_info['type'] = 'MAC'
                iface['addresses'].append(addr_info)

        # I/O counters
        if name in io:
            counter = io[name]
            iface['io'] = {
                'bytes_sent': counter.bytes_sent,
                'bytes_recv': counter.bytes_recv,
                'packets_sent': counter.packets_sent,
                'packets_recv': counter.packets_recv,
                'errors_in': counter.errin,
                'errors_out': counter.errout,
                'drop_in': counter.dropin,
                'drop_out': counter.dropout
            }

        interfaces.append(iface)

    return interfaces


def _get_connections(kind='all'):
    """Get active network connections."""
    connections = []
    try:
        conns = psutil.net_connections(kind=kind)
        for conn in conns[:200]:  # Limit
            c = {
                'fd': conn.fd,
                'family': str(conn.family),
                'type': str(conn.type),
                'local_addr': f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else '',
                'remote_addr': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else '',
                'status': conn.status,
                'pid': conn.pid
            }
            # Try to get process name
            if conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    c['process'] = proc.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    c['process'] = 'unknown'
            else:
                c['process'] = ''

            connections.append(c)
    except psutil.AccessDenied:
        logger.warning("Access denied when reading network connections")

    return connections


def _get_listening_ports():
    """Get listening ports and their services."""
    ports = []
    try:
        conns = psutil.net_connections(kind='inet')
        seen = set()
        for conn in conns:
            if conn.status == 'LISTEN' and conn.laddr:
                key = (conn.laddr.ip, conn.laddr.port)
                if key in seen:
                    continue
                seen.add(key)

                port_info = {
                    'address': conn.laddr.ip,
                    'port': conn.laddr.port,
                    'pid': conn.pid,
                    'process': '',
                    'description': ''
                }

                if conn.pid:
                    try:
                        proc = psutil.Process(conn.pid)
                        port_info['process'] = proc.name()
                        port_info['description'] = get_description(proc.name())
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                ports.append(port_info)

        ports.sort(key=lambda x: x['port'])
    except psutil.AccessDenied:
        pass

    return ports


def _get_dns_info():
    """Get DNS configuration."""
    dns = {
        'nameservers': [],
        'search_domains': [],
        'hostname': socket.gethostname(),
        'fqdn': socket.getfqdn()
    }

    # Parse /etc/resolv.conf
    try:
        with open('/etc/resolv.conf', 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('nameserver'):
                    dns['nameservers'].append(line.split()[1])
                elif line.startswith('search') or line.startswith('domain'):
                    dns['search_domains'].extend(line.split()[1:])
    except Exception:
        pass

    return dns


def _get_routes():
    """Get routing table."""
    routes = []
    output = _run_cmd("ip route show 2>/dev/null")
    if output:
        for line in output.split('\n'):
            if line.strip():
                routes.append(line.strip())
    return routes


def _get_firewall_rules():
    """Get firewall rules (iptables or nftables)."""
    rules = {'tool': '', 'rules': []}

    # Try nftables first
    output = _run_cmd("nft list ruleset 2>/dev/null")
    if output:
        rules['tool'] = 'nftables'
        rules['rules'] = output.split('\n')
        return rules

    # Try iptables
    output = _run_cmd("iptables -L -n --line-numbers 2>/dev/null")
    if output:
        rules['tool'] = 'iptables'
        rules['rules'] = output.split('\n')
        return rules

    # Try ufw
    output = _run_cmd("ufw status verbose 2>/dev/null")
    if output:
        rules['tool'] = 'ufw'
        rules['rules'] = output.split('\n')
        return rules

    return rules


def _get_network_services():
    """Get network-related services."""
    services = []
    # Common network services to check
    common_services = [
        'sshd', 'nginx', 'apache2', 'httpd', 'haproxy',
        'named', 'bind9', 'dnsmasq', 'dhcpd', 'NetworkManager',
        'firewalld', 'ufw', 'iptables', 'fail2ban',
        'openvpn', 'wireguard', 'squid', 'postfix',
        'dovecot', 'vsftpd', 'proftpd', 'nfs-server',
        'smbd', 'nmbd', 'snmpd', 'ntpd', 'chronyd'
    ]

    for svc in common_services:
        status = _run_cmd(f"systemctl is-active {svc} 2>/dev/null")
        if status:
            enabled = _run_cmd(f"systemctl is-enabled {svc} 2>/dev/null")
            services.append({
                'name': svc,
                'status': status,
                'enabled': enabled == 'enabled',
                'description': get_description(svc)
            })

    return services


def _get_bandwidth():
    """Get current bandwidth usage."""
    io = psutil.net_io_counters()
    return {
        'bytes_sent': io.bytes_sent,
        'bytes_recv': io.bytes_recv,
        'packets_sent': io.packets_sent,
        'packets_recv': io.packets_recv,
        'errors_in': io.errin,
        'errors_out': io.errout
    }


# ─── Routes ─────────────────────────────────────────────────────────────────

@network_bp.route('/interfaces')
@jwt_required
def interfaces():
    """Get network interfaces."""
    return jsonify({'interfaces': _get_interfaces()})


@network_bp.route('/connections')
@jwt_required
def connections():
    """Get active connections."""
    kind = request.args.get('kind', 'all')
    return jsonify({'connections': _get_connections(kind)})


@network_bp.route('/ports')
@jwt_required
def listening_ports():
    """Get listening ports."""
    return jsonify({'ports': _get_listening_ports()})


@network_bp.route('/dns')
@jwt_required
def dns():
    """Get DNS configuration."""
    return jsonify(_get_dns_info())


@network_bp.route('/routes')
@jwt_required
def routes():
    """Get routing table."""
    return jsonify({'routes': _get_routes()})


@network_bp.route('/firewall')
@jwt_required
def firewall():
    """Get firewall rules."""
    return jsonify(_get_firewall_rules())


@network_bp.route('/services')
@jwt_required
def network_services():
    """Get network services."""
    return jsonify({'services': _get_network_services()})


@network_bp.route('/bandwidth')
@jwt_required
def bandwidth():
    """Get bandwidth usage."""
    return jsonify(_get_bandwidth())


@network_bp.route('/overview')
@jwt_required
def overview():
    """Get network overview."""
    return jsonify({
        'interfaces': _get_interfaces(),
        'listening_ports': _get_listening_ports(),
        'dns': _get_dns_info(),
        'bandwidth': _get_bandwidth(),
        'services': _get_network_services()
    })
