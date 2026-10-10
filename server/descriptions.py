#!/usr/bin/env python3
"""
ServerInventory — Service & Process Descriptions
Provides human-readable descriptions for common Linux services and processes.
"""

# Comprehensive descriptions for common Linux services and processes
DESCRIPTIONS = {
    # ─── SSH & Remote Access ────────────────────────────────────────────
    'sshd': {
        'name': 'OpenSSH Server',
        'short': 'Secure Shell daemon for encrypted remote access',
        'description': 'OpenSSH (Secure Shell) is a suite of networking tools that provides '
                        'encrypted communication over a network. The SSH daemon (sshd) listens for '
                        'incoming connections from SSH clients, authenticates users via passwords or '
                        'public keys, and provides secure remote shell access, file transfers (SCP/SFTP), '
                        'and port forwarding. It is the primary method for remotely administering Linux servers.',
        'category': 'Remote Access'
    },
    'ssh': {
        'name': 'OpenSSH Client',
        'short': 'Secure Shell client for remote connections',
        'description': 'The SSH client connects to remote machines running an SSH server, providing '
                        'secure, encrypted terminal access.',
        'category': 'Remote Access'
    },

    # ─── Web Servers ────────────────────────────────────────────────────
    'nginx': {
        'name': 'Nginx',
        'short': 'High-performance web server and reverse proxy',
        'description': 'Nginx is a high-performance HTTP server and reverse proxy, known for its '
                        'stability, rich feature set, simple configuration, and low resource consumption. '
                        'It can serve static content, act as a load balancer, HTTP cache, and mail proxy. '
                        'Nginx is widely used to serve websites and APIs at scale.',
        'category': 'Web Server'
    },
    'apache2': {
        'name': 'Apache HTTP Server',
        'short': 'Full-featured open-source web server',
        'description': 'Apache HTTP Server is the world\'s most widely used web server software. '
                        'It supports a wide variety of features including URL rewriting, SSL/TLS, '
                        'virtual hosting, authentication modules, and more through its modular architecture.',
        'category': 'Web Server'
    },
    'httpd': {
        'name': 'Apache HTTP Server',
        'short': 'Full-featured open-source web server (RHEL/CentOS)',
        'description': 'Apache HTTP Server (httpd) is the world\'s most widely used web server. '
                        'On RHEL/CentOS systems, it is referred to as httpd.',
        'category': 'Web Server'
    },
    'haproxy': {
        'name': 'HAProxy',
        'short': 'High-performance TCP/HTTP load balancer',
        'description': 'HAProxy is a free, open-source high-availability load balancer and proxy '
                        'for TCP and HTTP-based applications. It distributes incoming requests across '
                        'multiple backend servers, improving reliability and performance.',
        'category': 'Web Server'
    },

    # ─── Databases ──────────────────────────────────────────────────────
    'mysql': {
        'name': 'MySQL',
        'short': 'Popular relational database management system',
        'description': 'MySQL is an open-source relational database management system (RDBMS) '
                        'that uses SQL (Structured Query Language) for managing data. It is widely '
                        'used for web applications, data warehousing, and logging.',
        'category': 'Database'
    },
    'mysqld': {
        'name': 'MySQL Server',
        'short': 'MySQL database server daemon',
        'description': 'The MySQL server daemon that handles all database operations, connections, '
                        'and queries.',
        'category': 'Database'
    },
    'mariadb': {
        'name': 'MariaDB',
        'short': 'Community-developed fork of MySQL',
        'description': 'MariaDB is a community-developed, commercially supported fork of MySQL, '
                        'intended to remain free and open-source. It is highly compatible with MySQL '
                        'and provides additional features and performance improvements.',
        'category': 'Database'
    },
    'postgres': {
        'name': 'PostgreSQL',
        'short': 'Advanced open-source relational database',
        'description': 'PostgreSQL is a powerful, open-source object-relational database system '
                        'known for reliability, feature robustness, and performance. It supports '
                        'advanced data types, full-text search, and JSON querying.',
        'category': 'Database'
    },
    'postgresql': {
        'name': 'PostgreSQL',
        'short': 'Advanced open-source relational database',
        'description': 'PostgreSQL is a powerful, open-source object-relational database system.',
        'category': 'Database'
    },
    'mongod': {
        'name': 'MongoDB',
        'short': 'NoSQL document database',
        'description': 'MongoDB is a source-available cross-platform document-oriented NoSQL database. '
                        'It stores data in flexible, JSON-like documents and is designed for scalability '
                        'and developer agility.',
        'category': 'Database'
    },
    'redis-server': {
        'name': 'Redis',
        'short': 'In-memory data structure store and cache',
        'description': 'Redis is an open-source, in-memory data structure store used as a database, '
                        'cache, message broker, and queue. It supports strings, hashes, lists, sets, '
                        'and sorted sets with range queries.',
        'category': 'Database'
    },

    # ─── Networking ─────────────────────────────────────────────────────
    'NetworkManager': {
        'name': 'NetworkManager',
        'short': 'Dynamic network configuration manager',
        'description': 'NetworkManager is a system daemon that manages network connections, including '
                        'Wi-Fi, Ethernet, VPN, mobile broadband, and more. It provides automatic '
                        'network configuration and seamless switching between connections.',
        'category': 'Network'
    },
    'systemd-networkd': {
        'name': 'systemd-networkd',
        'short': 'System network manager from systemd',
        'description': 'systemd-networkd is a system daemon that manages network configurations. '
                        'It detects and configures network devices as they appear.',
        'category': 'Network'
    },
    'dnsmasq': {
        'name': 'Dnsmasq',
        'short': 'Lightweight DNS forwarder and DHCP server',
        'description': 'Dnsmasq is a lightweight, easy-to-configure DNS forwarder, DHCP server, '
                        'and TFTP server designed for small networks. It caches DNS queries for speed.',
        'category': 'Network'
    },
    'named': {
        'name': 'BIND DNS Server',
        'short': 'Authoritative DNS server',
        'description': 'BIND (Berkeley Internet Name Domain) is the most widely used DNS software '
                        'on the Internet, providing an authoritative DNS server and resolver.',
        'category': 'Network'
    },
    'bind9': {
        'name': 'BIND9 DNS Server',
        'short': 'Authoritative DNS server (Debian/Ubuntu)',
        'description': 'BIND9 is the Debian/Ubuntu package name for the BIND DNS server.',
        'category': 'Network'
    },
    'dhcpd': {
        'name': 'DHCP Server',
        'short': 'Dynamic Host Configuration Protocol server',
        'description': 'The DHCP server automatically assigns IP addresses and network configuration '
                        'to devices on the network, simplifying network administration.',
        'category': 'Network'
    },

    # ─── Security ───────────────────────────────────────────────────────
    'fail2ban': {
        'name': 'Fail2ban',
        'short': 'Intrusion prevention scanning log files',
        'description': 'Fail2ban scans log files for malicious signs (too many password failures, '
                        'exploit attempts, etc.) and bans the offending IP addresses by updating '
                        'firewall rules. It helps protect against brute-force attacks.',
        'category': 'Security'
    },
    'firewalld': {
        'name': 'Firewalld',
        'short': 'Dynamic firewall manager',
        'description': 'Firewalld provides a dynamically managed firewall with support for network '
                        'zones that define the trust level of network connections.',
        'category': 'Security'
    },
    'ufw': {
        'name': 'Uncomplicated Firewall',
        'short': 'Simple interface for managing iptables rules',
        'description': 'UFW is a user-friendly frontend for managing iptables firewall rules. '
                        'It provides a simple way to create and manage firewall configurations.',
        'category': 'Security'
    },
    'iptables': {
        'name': 'iptables',
        'short': 'Linux kernel packet filtering firewall',
        'description': 'iptables is a command-line firewall utility that uses policy chains to '
                        'allow or block traffic. It is the traditional Linux firewall tool.',
        'category': 'Security'
    },
    'apparmor': {
        'name': 'AppArmor',
        'short': 'Mandatory access control security system',
        'description': 'AppArmor is a Linux kernel security module that allows restricting programs\' '
                        'capabilities with per-program profiles.',
        'category': 'Security'
    },

    # ─── VPN ────────────────────────────────────────────────────────────
    'openvpn': {
        'name': 'OpenVPN',
        'short': 'Open-source VPN solution',
        'description': 'OpenVPN is a full-featured open-source VPN solution that creates secure '
                        'point-to-point or site-to-site connections using SSL/TLS.',
        'category': 'VPN'
    },
    'wireguard': {
        'name': 'WireGuard',
        'short': 'Modern, fast VPN tunnel',
        'description': 'WireGuard is an extremely simple yet fast modern VPN that utilizes '
                        'state-of-the-art cryptography. It is designed to be faster and leaner '
                        'than other VPN protocols.',
        'category': 'VPN'
    },

    # ─── Mail ───────────────────────────────────────────────────────────
    'postfix': {
        'name': 'Postfix',
        'short': 'High-performance mail transfer agent',
        'description': 'Postfix is a free and open-source MTA (Mail Transfer Agent) that routes '
                        'and delivers electronic mail. It is designed as an alternative to Sendmail.',
        'category': 'Mail'
    },
    'dovecot': {
        'name': 'Dovecot',
        'short': 'IMAP and POP3 email server',
        'description': 'Dovecot is an open-source IMAP and POP3 server for Linux. It provides '
                        'mailbox access for email clients.',
        'category': 'Mail'
    },

    # ─── File Sharing ───────────────────────────────────────────────────
    'smbd': {
        'name': 'Samba',
        'short': 'Windows-compatible file and print sharing',
        'description': 'Samba allows Linux machines to share files and printers with Windows clients. '
                        'It implements the SMB/CIFS networking protocol.',
        'category': 'File Sharing'
    },
    'nmbd': {
        'name': 'Samba NetBIOS',
        'short': 'NetBIOS name service for Samba',
        'description': 'NMB provides NetBIOS over IP naming services to clients, enabling name '
                        'resolution for Samba file sharing.',
        'category': 'File Sharing'
    },
    'vsftpd': {
        'name': 'vsftpd',
        'short': 'Very Secure FTP daemon',
        'description': 'vsftpd is a lightweight, stable, and secure FTP server for Linux, '
                        'supporting virtual users, SSL/TLS, and bandwidth throttling.',
        'category': 'File Sharing'
    },
    'proftpd': {
        'name': 'ProFTPD',
        'short': 'Flexible FTP server',
        'description': 'ProFTPD is a highly configurable FTP server with Apache-style configuration.',
        'category': 'File Sharing'
    },
    'nfs-server': {
        'name': 'NFS Server',
        'short': 'Network File System server',
        'description': 'NFS allows sharing directories and files with others over a network. '
                        'Users and programs can access files on remote systems as if they were local.',
        'category': 'File Sharing'
    },

    # ─── Monitoring ─────────────────────────────────────────────────────
    'snmpd': {
        'name': 'SNMP Daemon',
        'short': 'Simple Network Management Protocol agent',
        'description': 'SNMP daemon responds to SNMP requests from management stations, providing '
                        'system and network monitoring data.',
        'category': 'Monitoring'
    },
    'prometheus': {
        'name': 'Prometheus',
        'short': 'Systems monitoring and alerting toolkit',
        'description': 'Prometheus is an open-source systems monitoring and alerting toolkit '
                        'that collects and stores metrics as time series data.',
        'category': 'Monitoring'
    },
    'grafana-server': {
        'name': 'Grafana',
        'short': 'Analytics and monitoring visualization platform',
        'description': 'Grafana is an open-source analytics and monitoring platform that allows '
                        'creating dashboards for visualizing metrics from various data sources.',
        'category': 'Monitoring'
    },
    'node_exporter': {
        'name': 'Node Exporter',
        'short': 'Prometheus exporter for hardware metrics',
        'description': 'Node Exporter exposes hardware and OS metrics for Prometheus to scrape.',
        'category': 'Monitoring'
    },
    'zabbix-agent': {
        'name': 'Zabbix Agent',
        'short': 'Zabbix monitoring agent',
        'description': 'Zabbix Agent collects system data for the Zabbix monitoring server.',
        'category': 'Monitoring'
    },

    # ─── Containers ─────────────────────────────────────────────────────
    'dockerd': {
        'name': 'Docker Daemon',
        'short': 'Container runtime engine',
        'description': 'Docker daemon is the background service that manages building, running, '
                        'and distributing Docker containers. Containers package applications with '
                        'their dependencies for consistent deployment.',
        'category': 'Containers'
    },
    'docker': {
        'name': 'Docker',
        'short': 'Container platform',
        'description': 'Docker is a platform for developing, shipping, and running applications '
                        'in containers.',
        'category': 'Containers'
    },
    'containerd': {
        'name': 'containerd',
        'short': 'Container runtime',
        'description': 'containerd is an industry-standard core container runtime used by Docker '
                        'and Kubernetes.',
        'category': 'Containers'
    },
    'kubelet': {
        'name': 'Kubelet',
        'short': 'Kubernetes node agent',
        'description': 'Kubelet is the primary node agent in Kubernetes that ensures containers '
                        'are running in a pod as expected.',
        'category': 'Containers'
    },

    # ─── Time Sync ──────────────────────────────────────────────────────
    'ntpd': {
        'name': 'NTP Daemon',
        'short': 'Network Time Protocol synchronization',
        'description': 'NTP daemon synchronizes the system clock with internet time servers, '
                        'ensuring accurate timekeeping across all systems.',
        'category': 'System'
    },
    'chronyd': {
        'name': 'Chrony',
        'short': 'Network Time Protocol client/server',
        'description': 'Chrony is a versatile implementation of NTP that can synchronize system '
                        'clocks more accurately and quickly than the classic NTP daemon.',
        'category': 'System'
    },
    'systemd-timesyncd': {
        'name': 'systemd-timesyncd',
        'short': 'Simple NTP client from systemd',
        'description': 'systemd-timesyncd is a lightweight NTP client that synchronizes the local '
                        'system clock with a remote NTP server.',
        'category': 'System'
    },

    # ─── System Core ────────────────────────────────────────────────────
    'systemd': {
        'name': 'systemd',
        'short': 'System and service manager',
        'description': 'systemd is the init system and service manager for modern Linux distributions. '
                        'It manages the boot process, services, logging, and system state.',
        'category': 'System'
    },
    'systemd-journald': {
        'name': 'Journal Daemon',
        'short': 'System logging service',
        'description': 'systemd-journald collects and stores logging data from the kernel, user '
                        'processes, and syslog messages in a structured, indexed journal.',
        'category': 'System'
    },
    'systemd-logind': {
        'name': 'Login Manager',
        'short': 'User login management service',
        'description': 'systemd-logind manages user logins, tracks active sessions, and handles '
                        'seat and device access management.',
        'category': 'System'
    },
    'systemd-resolved': {
        'name': 'Resolved',
        'short': 'Network name resolution manager',
        'description': 'systemd-resolved provides DNS resolution services for local applications, '
                        'implementing a caching DNS stub resolver.',
        'category': 'System'
    },
    'rsyslogd': {
        'name': 'Rsyslog',
        'short': 'System logging daemon',
        'description': 'Rsyslog is a high-performance log processing system that accepts input from '
                        'multiple sources and routes log messages to various destinations.',
        'category': 'System'
    },
    'cron': {
        'name': 'Cron',
        'short': 'Task scheduler daemon',
        'description': 'Cron is a time-based job scheduler that runs commands or scripts at specified '
                        'intervals. It is used for automating system maintenance tasks.',
        'category': 'System'
    },
    'crond': {
        'name': 'Cron Daemon',
        'short': 'Task scheduler daemon (RHEL/CentOS)',
        'description': 'Cron daemon schedules and executes tasks at specified times and intervals.',
        'category': 'System'
    },
    'atd': {
        'name': 'at Daemon',
        'short': 'One-time task scheduler',
        'description': 'The at daemon executes commands scheduled by the at utility for one-time '
                        'execution at a specified time.',
        'category': 'System'
    },

    # ─── Audio/Display ──────────────────────────────────────────────────
    'pulseaudio': {
        'name': 'PulseAudio',
        'short': 'Sound server for Linux',
        'description': 'PulseAudio is a general-purpose sound server that manages audio input and '
                        'output for applications.',
        'category': 'Desktop'
    },
    'pipewire': {
        'name': 'PipeWire',
        'short': 'Multimedia processing server',
        'description': 'PipeWire is a server for handling multimedia on Linux, including audio '
                        'and video streams.',
        'category': 'Desktop'
    },

    # ─── Proxy ──────────────────────────────────────────────────────────
    'squid': {
        'name': 'Squid',
        'short': 'Web caching proxy server',
        'description': 'Squid is a caching and forwarding HTTP web proxy that reduces bandwidth '
                        'and improves response times by caching frequently requested web content.',
        'category': 'Proxy'
    },

    # ─── Message Queues ─────────────────────────────────────────────────
    'rabbitmq-server': {
        'name': 'RabbitMQ',
        'short': 'Open-source message broker',
        'description': 'RabbitMQ is an open-source message broker that implements AMQP and other '
                        'messaging protocols for reliable message queuing.',
        'category': 'Message Queue'
    },

    # ─── Misc ───────────────────────────────────────────────────────────
    'cups': {
        'name': 'CUPS',
        'short': 'Common UNIX Printing System',
        'description': 'CUPS manages print jobs, queues, and printer drivers, providing a portable '
                        'printing layer for UNIX-like operating systems.',
        'category': 'Printing'
    },
    'bluetooth': {
        'name': 'Bluetooth',
        'short': 'Bluetooth device manager',
        'description': 'The Bluetooth service manages Bluetooth device pairing, connections, '
                        'and data transfer.',
        'category': 'Hardware'
    },
    'avahi-daemon': {
        'name': 'Avahi',
        'short': 'mDNS/DNS-SD service discovery',
        'description': 'Avahi is a system that facilitates service discovery on a local network '
                        'via mDNS/DNS-SD (Bonjour/Zeroconf).',
        'category': 'Network'
    },
    'serverinventory': {
        'name': 'ServerInventory',
        'short': 'This server management application',
        'description': 'ServerInventory is the application you are currently using to manage and '
                        'monitor this server through the web interface.',
        'category': 'Management'
    },
}


def get_description(name):
    """Get a human-readable description for a service/process name."""
    if not name:
        return ''

    # Direct lookup
    if name in DESCRIPTIONS:
        return DESCRIPTIONS[name].get('short', '')

    # Remove common suffixes and try again
    cleaned = name.replace('.service', '').replace('-daemon', '').replace('d', '', 1) if name.endswith('d') else name
    if cleaned in DESCRIPTIONS:
        return DESCRIPTIONS[cleaned].get('short', '')

    return ''


def get_full_description(name):
    """Get full description info for a service/process."""
    if not name:
        return None

    # Direct lookup
    if name in DESCRIPTIONS:
        return DESCRIPTIONS[name]

    # Try without .service suffix
    clean = name.replace('.service', '')
    if clean in DESCRIPTIONS:
        return DESCRIPTIONS[clean]

    return None
