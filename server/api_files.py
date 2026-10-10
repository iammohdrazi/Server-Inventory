#!/usr/bin/env python3
"""
ServerInventory — File Manager API
Browse, upload, download, delete, move, copy, and share files.
"""

import os
import shutil
import mimetypes
import logging
import hashlib
import secrets
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, send_file

from auth import jwt_required
from config import Config

logger = logging.getLogger('serverinventory.files')
files_bp = Blueprint('files', __name__)

# Shared file links (in-memory, would use DB in production)
_shared_links = {}  # token -> {'path': str, 'expires': datetime, 'created_by': str}


def _format_bytes(size):
    """Format bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _is_safe_path(path):
    """Check if path is safe to access."""
    try:
        real = os.path.realpath(path)
        for blocked in Config.BLOCKED_PATHS:
            if real.startswith(blocked):
                return False

        # Check if within allowed roots
        allowed = False
        for root in Config.ALLOWED_FILE_ROOTS:
            if real.startswith(root):
                allowed = True
                break

        return allowed
    except Exception:
        return False


def _get_file_info(path):
    """Get detailed file information."""
    try:
        stat = os.stat(path)
        is_dir = os.path.isdir(path)

        info = {
            'name': os.path.basename(path),
            'path': path,
            'is_dir': is_dir,
            'size': stat.st_size if not is_dir else 0,
            'size_human': _format_bytes(stat.st_size) if not is_dir else '-',
            'modified': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            'created': datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
            'accessed': datetime.fromtimestamp(stat.st_atime, tz=timezone.utc).isoformat(),
            'permissions': oct(stat.st_mode)[-3:],
            'owner_uid': stat.st_uid,
            'group_gid': stat.st_gid,
            'is_symlink': os.path.islink(path)
        }

        # Get owner/group names
        try:
            import pwd
            import grp
            info['owner'] = pwd.getpwuid(stat.st_uid).pw_name
            info['group'] = grp.getgrgid(stat.st_gid).gr_name
        except Exception:
            info['owner'] = str(stat.st_uid)
            info['group'] = str(stat.st_gid)

        # MIME type for files
        if not is_dir:
            mime, _ = mimetypes.guess_type(path)
            info['mime_type'] = mime or 'application/octet-stream'
            info['extension'] = os.path.splitext(path)[1].lower()

        return info
    except PermissionError:
        return {
            'name': os.path.basename(path),
            'path': path,
            'error': 'Permission denied'
        }
    except Exception as e:
        return {
            'name': os.path.basename(path),
            'path': path,
            'error': str(e)
        }


# ─── Routes ─────────────────────────────────────────────────────────────────

@files_bp.route('/browse')
@jwt_required
def browse():
    """Browse directory contents."""
    if not Config.ENABLE_FILE_MANAGER:
        return jsonify({'error': 'File manager is disabled'}), 403

    path = request.args.get('path', '/')
    show_hidden = request.args.get('hidden', 'false').lower() == 'true'
    sort_by = request.args.get('sort', 'name')

    if not _is_safe_path(path):
        return jsonify({'error': 'Access denied to this path'}), 403

    if not os.path.isdir(path):
        return jsonify({'error': 'Path is not a directory'}), 400

    try:
        entries = []
        for name in os.listdir(path):
            if not show_hidden and name.startswith('.'):
                continue
            full_path = os.path.join(path, name)
            entries.append(_get_file_info(full_path))

        # Sort
        if sort_by == 'name':
            entries.sort(key=lambda x: (not x.get('is_dir', False), x.get('name', '').lower()))
        elif sort_by == 'size':
            entries.sort(key=lambda x: x.get('size', 0), reverse=True)
        elif sort_by == 'modified':
            entries.sort(key=lambda x: x.get('modified', ''), reverse=True)
        elif sort_by == 'type':
            entries.sort(key=lambda x: x.get('extension', ''))

        return jsonify({
            'path': path,
            'parent': os.path.dirname(path),
            'entries': entries,
            'total': len(entries)
        })
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403


@files_bp.route('/info')
@jwt_required
def file_info():
    """Get detailed file information."""
    path = request.args.get('path', '')

    if not path or not _is_safe_path(path):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.exists(path):
        return jsonify({'error': 'File not found'}), 404

    info = _get_file_info(path)

    # Add file hash for files
    if not os.path.isdir(path) and os.path.getsize(path) < 100 * 1024 * 1024:  # < 100MB
        try:
            h = hashlib.sha256()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            info['sha256'] = h.hexdigest()
        except Exception:
            pass

    return jsonify(info)


@files_bp.route('/read')
@jwt_required
def read_file():
    """Read text file contents (for preview)."""
    path = request.args.get('path', '')

    if not path or not _is_safe_path(path):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.isfile(path):
        return jsonify({'error': 'Not a file'}), 400

    # Check size limit (5MB for text preview)
    if os.path.getsize(path) > 5 * 1024 * 1024:
        return jsonify({'error': 'File too large for preview'}), 400

    try:
        with open(path, 'r', errors='replace') as f:
            content = f.read()
        mime, _ = mimetypes.guess_type(path)
        return jsonify({
            'content': content,
            'mime_type': mime or 'text/plain',
            'size': os.path.getsize(path)
        })
    except UnicodeDecodeError:
        return jsonify({'error': 'Binary file cannot be previewed as text'}), 400
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403


@files_bp.route('/download')
@jwt_required
def download():
    """Download a file."""
    path = request.args.get('path', '')

    if not path or not _is_safe_path(path):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.isfile(path):
        return jsonify({'error': 'File not found'}), 404

    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@files_bp.route('/upload', methods=['POST'])
@jwt_required
def upload():
    """Upload files to a directory."""
    target_dir = request.form.get('path', '')

    if not target_dir or not _is_safe_path(target_dir):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.isdir(target_dir):
        return jsonify({'error': 'Target directory not found'}), 404

    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files provided'}), 400

    uploaded = []
    errors = []

    for file in files:
        if file.filename:
            # Sanitize filename
            safe_name = os.path.basename(file.filename)
            target_path = os.path.join(target_dir, safe_name)

            try:
                file.save(target_path)
                uploaded.append(safe_name)
            except Exception as e:
                errors.append({'file': safe_name, 'error': str(e)})

    return jsonify({
        'uploaded': uploaded,
        'errors': errors,
        'success': len(uploaded) > 0
    })


@files_bp.route('/delete', methods=['POST'])
@jwt_required
def delete():
    """Delete a file or directory."""
    data = request.get_json() or {}
    path = data.get('path', '')

    if not path or not _is_safe_path(path):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.exists(path):
        return jsonify({'error': 'Path not found'}), 404

    # Prevent deleting critical paths
    critical = ['/', '/bin', '/sbin', '/usr', '/etc', '/boot', '/var', '/home', '/root', '/lib', '/lib64']
    if os.path.realpath(path) in critical:
        return jsonify({'error': 'Cannot delete critical system path'}), 403

    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

        logger.info(f"Deleted: {path} by {request.current_user}")
        return jsonify({'success': True, 'message': f'Deleted {os.path.basename(path)}'})
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@files_bp.route('/move', methods=['POST'])
@jwt_required
def move():
    """Move or rename a file/directory."""
    data = request.get_json() or {}
    source = data.get('source', '')
    destination = data.get('destination', '')

    if not source or not destination:
        return jsonify({'error': 'Source and destination required'}), 400

    if not _is_safe_path(source) or not _is_safe_path(destination):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.exists(source):
        return jsonify({'error': 'Source not found'}), 404

    try:
        shutil.move(source, destination)
        logger.info(f"Moved: {source} -> {destination} by {request.current_user}")
        return jsonify({'success': True, 'message': 'File moved successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@files_bp.route('/copy', methods=['POST'])
@jwt_required
def copy():
    """Copy a file or directory."""
    data = request.get_json() or {}
    source = data.get('source', '')
    destination = data.get('destination', '')

    if not source or not destination:
        return jsonify({'error': 'Source and destination required'}), 400

    if not _is_safe_path(source) or not _is_safe_path(destination):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.exists(source):
        return jsonify({'error': 'Source not found'}), 404

    try:
        if os.path.isdir(source):
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)

        logger.info(f"Copied: {source} -> {destination} by {request.current_user}")
        return jsonify({'success': True, 'message': 'File copied successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@files_bp.route('/mkdir', methods=['POST'])
@jwt_required
def mkdir():
    """Create a new directory."""
    data = request.get_json() or {}
    path = data.get('path', '')

    if not path or not _is_safe_path(os.path.dirname(path)):
        return jsonify({'error': 'Access denied'}), 403

    try:
        os.makedirs(path, exist_ok=True)
        return jsonify({'success': True, 'message': f'Directory created: {os.path.basename(path)}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@files_bp.route('/chmod', methods=['POST'])
@jwt_required
def chmod():
    """Change file permissions."""
    data = request.get_json() or {}
    path = data.get('path', '')
    mode = data.get('mode', '')

    if not path or not mode or not _is_safe_path(path):
        return jsonify({'error': 'Path and mode required'}), 400

    try:
        os.chmod(path, int(mode, 8))
        return jsonify({'success': True, 'message': f'Permissions changed to {mode}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@files_bp.route('/share', methods=['POST'])
@jwt_required
def create_share():
    """Create a shareable download link for a file."""
    data = request.get_json() or {}
    path = data.get('path', '')
    expires_hours = data.get('expires_hours', 24)

    if not path or not _is_safe_path(path):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.isfile(path):
        return jsonify({'error': 'Only files can be shared'}), 400

    token = secrets.token_urlsafe(32)
    from datetime import timedelta
    _shared_links[token] = {
        'path': path,
        'expires': datetime.now(timezone.utc) + timedelta(hours=expires_hours),
        'created_by': request.current_user
    }

    return jsonify({
        'success': True,
        'token': token,
        'url': f'/api/files/shared/{token}',
        'expires_in': f'{expires_hours} hours'
    })


@files_bp.route('/shared/<token>')
def download_shared(token):
    """Download a shared file (no auth required, uses token)."""
    if token not in _shared_links:
        return jsonify({'error': 'Invalid or expired link'}), 404

    link = _shared_links[token]

    if datetime.now(timezone.utc) > link['expires']:
        del _shared_links[token]
        return jsonify({'error': 'Link has expired'}), 410

    if not os.path.isfile(link['path']):
        return jsonify({'error': 'File no longer exists'}), 404

    return send_file(link['path'], as_attachment=True, download_name=os.path.basename(link['path']))


@files_bp.route('/search')
@jwt_required
def search():
    """Search for files in a directory."""
    path = request.args.get('path', '/')
    query = request.args.get('q', '')
    max_results = min(int(request.args.get('limit', 100)), 500)

    if not query or not _is_safe_path(path):
        return jsonify({'error': 'Query and valid path required'}), 400

    results = []
    try:
        for root, dirs, files in os.walk(path):
            # Respect blocked paths
            if not _is_safe_path(root):
                dirs.clear()
                continue

            for name in files + dirs:
                if query.lower() in name.lower():
                    full_path = os.path.join(root, name)
                    results.append(_get_file_info(full_path))
                    if len(results) >= max_results:
                        return jsonify({'results': results, 'total': len(results), 'truncated': True})

            # Limit directory depth
            if root.count(os.sep) - path.count(os.sep) > 5:
                dirs.clear()
    except PermissionError:
        pass

    return jsonify({'results': results, 'total': len(results), 'truncated': False})
