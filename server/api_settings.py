#!/usr/bin/env python3
"""
ServerInventory — OS Settings API
View and manage OS configuration: hostname, timezone, users, cron, etc.
"""

import os
import re
import logging
import subprocess

from flask import Blueprint, jsonify, request

from auth import jwt_required

logger = logging.getLogger('serverinventory.settings')
settings_bp = Blueprint('settings', __name__)


def _run_cmd(cmd, timeout=10):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return -1, '', str(e)


def _read_file(path):
    """Read a file and return contents."""
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except Exception:
        return ''


def _get_hostname():
    """Get hostname info."""
    _, hostname, _ = _run_cmd("hostname")
    _, fqdn, _ = _run_cmd("hostname -f 2>/dev/null")
    return {
        'hostname': hostname,
        'fqdn': fqdn or hostname,
        'static': _read_file('/etc/hostname')
    }


def _get_timezone():
    """Get timezone info."""
    _, tz, _ = _run_cmd("timedatectl show --property=Timezone --value 2>/dev/null")
    _, ntp, _ = _run_cmd("timedatectl show --property=NTPSynchronized --value 2>/dev/null")
    _, local_time, _ = _run_cmd("date '+%Y-%m-%d %H:%M:%S %Z'")

    return {
        'timezone': tz or _read_file('/etc/timezone'),
        'ntp_synced': ntp == 'yes',
        'local_time': local_time
    }


def _get_locale():
    """Get locale settings."""
    _, output, _ = _run_cmd("locale")
    locale = {}
    if output:
        for line in output.split('\n'):
            if '=' in line:
                key, _, val = line.partition('=')
                locale[key] = val.strip('"')
    return locale


def _get_users():
    """Get system users."""
    users = []
    try:
        import pwd
        for pw in pwd.getpwall():
            user = {
                'username': pw.pw_name,
                'uid': pw.pw_uid,
                'gid': pw.pw_gid,
                'home': pw.pw_dir,
                'shell': pw.pw_shell,
                'gecos': pw.pw_gecos,
                'is_system': pw.pw_uid < 1000 and pw.pw_uid != 0,
                'is_root': pw.pw_uid == 0,
                'has_login': pw.pw_shell not in ['/usr/sbin/nologin', '/bin/false', '/sbin/nologin']
            }

            # Get groups
            try:
                import grp
                user['groups'] = [g.gr_name for g in grp.getgrall() if pw.pw_name in g.gr_mem]
                primary = grp.getgrgid(pw.pw_gid).gr_name
                if primary not in user['groups']:
                    user['groups'].insert(0, primary)
            except Exception:
                user['groups'] = []

            # Last login
            _, last_login, _ = _run_cmd(f"lastlog -u {pw.pw_name} 2>/dev/null | tail -1")
            user['last_login'] = last_login.strip() if last_login and 'Never' not in last_login else 'Never'

            users.append(user)
    except Exception as e:
        logger.error(f"Error getting users: {e}")

    return users


def _get_groups():
    """Get system groups."""
    groups = []
    try:
        import grp
        for gr in grp.getgrall():
            groups.append({
                'name': gr.gr_name,
                'gid': gr.gr_gid,
                'members': gr.gr_mem
            })
    except Exception:
        pass
    return groups


def _get_cron_jobs():
    """Get cron jobs for all users."""
    jobs = []

    # System crontab
    content = _read_file('/etc/crontab')
    if content:
        jobs.append({
            'user': 'system',
            'source': '/etc/crontab',
            'entries': [l for l in content.split('\n') if l.strip() and not l.startswith('#')]
        })

    # User crontabs
    _, users_output, _ = _run_cmd("ls /var/spool/cron/crontabs/ 2>/dev/null || ls /var/spool/cron/ 2>/dev/null")
    if users_output:
        for user in users_output.split('\n'):
            user = user.strip()
            if user:
                _, cron, _ = _run_cmd(f"crontab -l -u {user} 2>/dev/null")
                if cron:
                    jobs.append({
                        'user': user,
                        'source': f'crontab -l -u {user}',
                        'entries': [l for l in cron.split('\n') if l.strip() and not l.startswith('#')]
                    })

    # Cron.d directory
    _, cron_d, _ = _run_cmd("ls /etc/cron.d/ 2>/dev/null")
    if cron_d:
        for f in cron_d.split('\n'):
            if f.strip():
                content = _read_file(f'/etc/cron.d/{f.strip()}')
                if content:
                    jobs.append({
                        'user': 'system',
                        'source': f'/etc/cron.d/{f.strip()}',
                        'entries': [l for l in content.split('\n') if l.strip() and not l.startswith('#')]
                    })

    return jobs


def _get_environment():
    """Get environment variables (safe subset)."""
    safe_keys = [
        'PATH', 'SHELL', 'HOME', 'USER', 'LANG', 'LC_ALL',
        'TERM', 'HOSTNAME', 'LOGNAME', 'DISPLAY', 'XDG_SESSION_TYPE',
        'SSH_CONNECTION', 'EDITOR', 'VISUAL'
    ]
    env = {}
    for key in safe_keys:
        val = os.environ.get(key)
        if val:
            env[key] = val
    return env


def _get_sysctl_settings():
    """Get important sysctl settings."""
    settings = {}
    important_keys = [
        'net.ipv4.ip_forward',
        'net.ipv4.tcp_syncookies',
        'net.ipv6.conf.all.disable_ipv6',
        'kernel.hostname',
        'kernel.ostype',
        'kernel.osrelease',
        'vm.swappiness',
        'vm.overcommit_memory',
        'fs.file-max',
        'net.core.somaxconn'
    ]

    for key in important_keys:
        _, val, _ = _run_cmd(f"sysctl -n {key} 2>/dev/null")
        if val:
            settings[key] = val

    return settings


def _get_security_info():
    """Get security-related settings."""
    security = {
        'selinux': '',
        'apparmor': '',
        'firewall': '',
        'ssh_config': {}
    }

    # SELinux
    _, selinux, _ = _run_cmd("getenforce 2>/dev/null")
    security['selinux'] = selinux or 'Not installed'

    # AppArmor
    _, apparmor, _ = _run_cmd("aa-status --json 2>/dev/null")
    if apparmor:
        security['apparmor'] = 'Active'
    else:
        security['apparmor'] = 'Not active'

    # Firewall
    _, ufw, _ = _run_cmd("ufw status 2>/dev/null")
    if ufw:
        security['firewall'] = ufw.split('\n')[0]
    else:
        _, firewalld, _ = _run_cmd("firewall-cmd --state 2>/dev/null")
        security['firewall'] = firewalld or 'Unknown'

    # SSH config (safe subset)
    ssh_config = _read_file('/etc/ssh/sshd_config')
    if ssh_config:
        for line in ssh_config.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    key = parts[0]
                    if key in ['Port', 'PermitRootLogin', 'PasswordAuthentication',
                               'PubkeyAuthentication', 'MaxAuthTries', 'Protocol',
                               'X11Forwarding', 'AllowUsers', 'AllowGroups']:
                        security['ssh_config'][key] = parts[1]

    return security


# ─── Routes ─────────────────────────────────────────────────────────────────

@settings_bp.route('/hostname')
@jwt_required
def hostname():
    return jsonify(_get_hostname())


@settings_bp.route('/hostname', methods=['POST'])
@jwt_required
def set_hostname():
    data = request.get_json() or {}
    new_hostname = data.get('hostname', '').strip()
    if not new_hostname or not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-]*$', new_hostname):
        return jsonify({'error': 'Invalid hostname'}), 400

    code, _, err = _run_cmd(f"hostnamectl set-hostname {new_hostname}")
    if code == 0:
        return jsonify({'success': True, 'hostname': new_hostname})
    return jsonify({'error': err or 'Failed to set hostname'}), 500


@settings_bp.route('/timezone')
@jwt_required
def timezone():
    return jsonify(_get_timezone())


@settings_bp.route('/timezone', methods=['POST'])
@jwt_required
def set_timezone():
    data = request.get_json() or {}
    tz = data.get('timezone', '').strip()
    if not tz:
        return jsonify({'error': 'Timezone is required'}), 400

    code, _, err = _run_cmd(f"timedatectl set-timezone '{tz}'")
    if code == 0:
        return jsonify({'success': True, 'timezone': tz})
    return jsonify({'error': err or 'Failed to set timezone'}), 500


@settings_bp.route('/locale')
@jwt_required
def locale():
    return jsonify(_get_locale())


@settings_bp.route('/users')
@jwt_required
def users():
    show_system = request.args.get('system', 'false').lower() == 'true'
    all_users = _get_users()
    if not show_system:
        all_users = [u for u in all_users if not u['is_system']]
    return jsonify({'users': all_users})


@settings_bp.route('/groups')
@jwt_required
def groups():
    return jsonify({'groups': _get_groups()})


@settings_bp.route('/cron')
@jwt_required
def cron():
    return jsonify({'jobs': _get_cron_jobs()})


@settings_bp.route('/environment')
@jwt_required
def environment():
    return jsonify(_get_environment())


@settings_bp.route('/sysctl')
@jwt_required
def sysctl():
    return jsonify(_get_sysctl_settings())


@settings_bp.route('/security')
@jwt_required
def security():
    return jsonify(_get_security_info())


@settings_bp.route('/overview')
@jwt_required
def overview():
    return jsonify({
        'hostname': _get_hostname(),
        'timezone': _get_timezone(),
        'locale': _get_locale(),
        'security': _get_security_info(),
        'sysctl': _get_sysctl_settings()
    })
