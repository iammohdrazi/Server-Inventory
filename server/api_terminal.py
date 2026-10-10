#!/usr/bin/env python3
"""
ServerInventory — Terminal WebSocket API
Provides interactive terminal access through WebSocket using pty.
"""

import os
import pty
import select
import signal
import struct
import fcntl
import termios
import logging

from auth import jwt_required_socket

logger = logging.getLogger('serverinventory.terminal')

# Active terminal sessions
_sessions = {}  # sid -> {'fd': int, 'pid': int, 'user': str}


def register_terminal_events(socketio):
    """Register WebSocket events for terminal functionality."""

    @socketio.on('terminal_connect')
    def handle_connect(data):
        """Start a new terminal session."""
        from flask_socketio import emit
        from flask import request

        token = data.get('token', '')
        username = jwt_required_socket(token)

        if not username:
            emit('terminal_error', {'error': 'Authentication required'})
            return

        sid = request.sid
        logger.info(f"Terminal session requested by '{username}' (sid: {sid})")

        try:
            # Get user's shell
            import pwd
            try:
                pw = pwd.getpwnam(username)
                shell = pw.pw_shell or '/bin/bash'
                home = pw.pw_dir or '/tmp'
            except KeyError:
                shell = '/bin/bash'
                home = '/tmp'

            # Create pseudo-terminal
            master_fd, slave_fd = pty.openpty()

            # Fork process
            pid = os.fork()

            if pid == 0:
                # Child process
                os.close(master_fd)
                os.setsid()

                # Set controlling terminal
                fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

                # Redirect stdin/stdout/stderr
                os.dup2(slave_fd, 0)
                os.dup2(slave_fd, 1)
                os.dup2(slave_fd, 2)

                if slave_fd > 2:
                    os.close(slave_fd)

                # Set environment
                env = os.environ.copy()
                env.update({
                    'TERM': 'xterm-256color',
                    'HOME': home,
                    'USER': username,
                    'SHELL': shell,
                    'LANG': 'en_US.UTF-8',
                    'LC_ALL': 'en_US.UTF-8'
                })

                # Switch to user if not root
                try:
                    if os.getuid() == 0 and pw.pw_uid != 0:
                        os.setgid(pw.pw_gid)
                        os.initgroups(username, pw.pw_gid)
                        os.setuid(pw.pw_uid)
                except Exception:
                    pass

                os.chdir(home)
                os.execvpe(shell, [shell, '-l'], env)

            else:
                # Parent process
                os.close(slave_fd)

                # Set master fd non-blocking
                flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
                fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

                # Store session
                _sessions[sid] = {
                    'fd': master_fd,
                    'pid': pid,
                    'user': username
                }

                # Set initial terminal size
                cols = data.get('cols', 80)
                rows = data.get('rows', 24)
                _resize_terminal(master_fd, rows, cols)

                emit('terminal_ready', {'message': 'Terminal connected'})
                logger.info(f"Terminal session started for '{username}' (pid: {pid})")

                # Start reading output in background
                socketio.start_background_task(
                    _read_terminal_output, socketio, sid, master_fd
                )

        except Exception as e:
            logger.error(f"Failed to create terminal: {e}")
            emit('terminal_error', {'error': f'Failed to create terminal: {str(e)}'})

    @socketio.on('terminal_input')
    def handle_input(data):
        """Handle terminal input from client."""
        from flask import request
        sid = request.sid

        if sid not in _sessions:
            return

        input_data = data.get('input', '')
        if input_data:
            try:
                fd = _sessions[sid]['fd']
                os.write(fd, input_data.encode('utf-8', errors='replace'))
            except OSError:
                _cleanup_session(sid)

    @socketio.on('terminal_resize')
    def handle_resize(data):
        """Handle terminal resize."""
        from flask import request
        sid = request.sid

        if sid not in _sessions:
            return

        cols = data.get('cols', 80)
        rows = data.get('rows', 24)

        try:
            _resize_terminal(_sessions[sid]['fd'], rows, cols)
        except Exception:
            pass

    @socketio.on('terminal_disconnect')
    def handle_terminal_disconnect(data=None):
        """Handle terminal disconnect."""
        from flask import request
        sid = request.sid
        _cleanup_session(sid)

    @socketio.on('disconnect')
    def handle_disconnect():
        """Clean up on WebSocket disconnect."""
        from flask import request
        sid = request.sid
        _cleanup_session(sid)


def _resize_terminal(fd, rows, cols):
    """Resize the terminal."""
    try:
        winsize = struct.pack('HHHH', rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
    except Exception:
        pass


def _read_terminal_output(socketio, sid, fd):
    """Read terminal output and send to client."""
    while sid in _sessions:
        try:
            ready, _, _ = select.select([fd], [], [], 0.1)
            if ready:
                try:
                    data = os.read(fd, 4096)
                    if data:
                        socketio.emit('terminal_output', {
                            'output': data.decode('utf-8', errors='replace')
                        }, room=sid)
                    else:
                        # EOF - process exited
                        socketio.emit('terminal_exit', {
                            'message': 'Terminal session ended'
                        }, room=sid)
                        _cleanup_session(sid)
                        break
                except OSError:
                    socketio.emit('terminal_exit', {
                        'message': 'Terminal session ended'
                    }, room=sid)
                    _cleanup_session(sid)
                    break
        except Exception:
            break

    logger.info(f"Terminal output reader stopped for session {sid}")


def _cleanup_session(sid):
    """Clean up a terminal session."""
    if sid in _sessions:
        session = _sessions[sid]
        try:
            os.close(session['fd'])
        except Exception:
            pass
        try:
            os.kill(session['pid'], signal.SIGTERM)
            os.waitpid(session['pid'], os.WNOHANG)
        except Exception:
            pass

        logger.info(f"Terminal session cleaned up for '{session['user']}' (sid: {sid})")
        del _sessions[sid]
