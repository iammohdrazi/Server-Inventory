# 🖥️ ServerInventory

**A professional Linux server management application accessible via your web browser.**

ServerInventory lets you monitor, manage, and control your Linux servers from anywhere on your network through a secure HTTPS web interface. No SSH client needed — just open your browser.

---

## ✨ Features

| Tab | Description |
|-----|-------------|
| **🖥️ Hardware** | CPU, Memory, Motherboard, GPU, and full system specs with live gauges |
| **📦 Software** | Installed packages, running processes, with descriptions and management |
| **🌐 Network** | Interfaces, connections, firewall rules, DNS, and network services |
| **💾 Storage** | Disk usage visualization, mount points, SMART data, and partition info |
| **📁 Files** | Full file explorer — browse, upload, download, move, delete, and share |
| **⚙️ Settings** | OS configuration, hostname, timezone, users, and system settings |
| **🔌 Services** | Start, stop, restart, enable, disable systemd services |
| **💻 Terminal** | Full interactive terminal right in your browser |

## 🚀 Quick Install

```bash
curl -sSL https://raw.githubusercontent.com/YOUR_ORG/ServerInventory/main/install.sh | sudo bash
```

Or download the latest release:

```bash
wget https://github.com/YOUR_ORG/ServerInventory/releases/latest/download/serverinventory.tar.gz
sudo tar -xzf serverinventory.tar.gz -C /opt/
sudo /opt/serverinventory/install.sh --local
```

## 🔒 Security

- **HTTPS** with auto-generated SSL certificates
- **PAM Authentication** — uses your Linux system credentials
- **JWT Sessions** with secure httpOnly cookies
- **Rate Limiting** on login attempts
- **CSRF Protection** on all state-changing operations
- **Session Timeout** with automatic logout

## 🖥️ Requirements

- Linux (Ubuntu 18.04+, Debian 10+, CentOS 7+, RHEL 7+, Fedora 30+)
- Python 3.8+
- systemd

## 📖 Usage

After installation, access the web interface at:

```
https://<your-server-ip>:9443
```

Log in with your Linux system credentials (any user with shell access).

## 🛑 Uninstall

```bash
sudo /opt/serverinventory/uninstall.sh
```

## 📄 License

MIT License — See [LICENSE](LICENSE) for details.
