#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# ServerInventory — Installation Script
# Supports Ubuntu/Debian, CentOS/RHEL/Fedora, Arch Linux, Alpine
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Configuration ──────────────────────────────────────────────────────
INSTALL_DIR="/opt/serverinventory"
DATA_DIR="/var/lib/serverinventory"
SERVICE_NAME="serverinventory"
VERSION="1.0.0"
REPO_URL="https://github.com/iammohdrazi/Server-Inventory"
MIN_PYTHON_VERSION="3.8"
PORT=9443

# ─── Colors ─────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ─── Functions ──────────────────────────────────────────────────────────
log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[  OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[FAIL]${NC} $1"; }

banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════╗"
    echo "║                                                  ║"
    echo "║          🖥️  ServerInventory Installer            ║"
    echo "║             Version ${VERSION}                      ║"
    echo "║                                                  ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="$ID"
        OS_VERSION="${VERSION_ID:-unknown}"
        OS_NAME="${PRETTY_NAME:-$ID}"
    elif [ -f /etc/redhat-release ]; then
        OS_ID="rhel"
        OS_NAME=$(cat /etc/redhat-release)
    else
        OS_ID="unknown"
        OS_NAME="Unknown Linux"
    fi
    log_info "Detected OS: ${OS_NAME}"
}

check_python() {
    local python_cmd=""

    # Try python3 first
    if command -v python3 &>/dev/null; then
        python_cmd="python3"
    elif command -v python &>/dev/null; then
        python_cmd="python"
    fi

    if [ -z "$python_cmd" ]; then
        log_warn "Python not found. Installing..."
        install_python
        python_cmd="python3"
    fi

    # Check version
    local version=$($python_cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
    if [ -z "$version" ]; then
        log_error "Cannot determine Python version"
        exit 1
    fi

    local major=$(echo "$version" | cut -d. -f1)
    local minor=$(echo "$version" | cut -d. -f2)
    local req_major=$(echo "$MIN_PYTHON_VERSION" | cut -d. -f1)
    local req_minor=$(echo "$MIN_PYTHON_VERSION" | cut -d. -f2)

    if [ "$major" -lt "$req_major" ] || ([ "$major" -eq "$req_major" ] && [ "$minor" -lt "$req_minor" ]); then
        log_error "Python $MIN_PYTHON_VERSION+ required (found $version)"
        exit 1
    fi

    PYTHON_CMD="$python_cmd"
    log_success "Python $version found ($python_cmd)"
}

install_python() {
    case "$OS_ID" in
        ubuntu|debian|linuxmint|pop)
            rm -f /etc/apt/sources.list.d/*cdrom* 2>/dev/null || true
            sed -i 's/^deb cdrom:/# deb cdrom:/' /etc/apt/sources.list 2>/dev/null || true
            apt-get update -qq || true
            apt-get install -y -qq python3 python3-pip python3-venv python3-dev libpam0g-dev
            ;;
        centos|rhel|rocky|almalinux|ol)
            if command -v dnf &>/dev/null; then
                dnf install -y python3 python3-pip python3-devel pam-devel
            else
                yum install -y python3 python3-pip python3-devel pam-devel
            fi
            ;;
        fedora)
            dnf install -y python3 python3-pip python3-devel pam-devel
            ;;
        arch|manjaro)
            pacman -Sy --noconfirm python python-pip pam
            ;;
        alpine)
            apk add python3 py3-pip python3-dev linux-pam-dev gcc musl-dev
            ;;
        opensuse*|sles)
            zypper install -y python3 python3-pip python3-devel pam-devel
            ;;
        *)
            log_error "Unsupported OS: $OS_ID. Please install Python 3.8+ manually."
            exit 1
            ;;
    esac
}

install_system_deps() {
    log_info "Installing system dependencies..."
    case "$OS_ID" in
        ubuntu|debian|linuxmint|pop)
            rm -f /etc/apt/sources.list.d/*cdrom* 2>/dev/null || true
            sed -i 's/^deb cdrom:/# deb cdrom:/' /etc/apt/sources.list 2>/dev/null || true
            apt-get update -qq || true
            apt-get install -y -qq python3-venv python3-dev libpam0g-dev openssl curl
            ;;
        centos|rhel|rocky|almalinux|ol)
            if command -v dnf &>/dev/null; then
                dnf install -y python3-devel pam-devel openssl curl
            else
                yum install -y python3-devel pam-devel openssl curl
            fi
            ;;
        fedora)
            dnf install -y python3-devel pam-devel openssl curl
            ;;
        arch|manjaro)
            pacman -Sy --noconfirm openssl curl
            ;;
        alpine)
            apk add openssl curl linux-pam-dev gcc musl-dev python3-dev
            ;;
        *)
            log_warn "Could not install system deps automatically for $OS_ID"
            ;;
    esac
    log_success "System dependencies installed"
}

create_directories() {
    log_info "Creating directories..."
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "$DATA_DIR/certs"
    mkdir -p "$DATA_DIR/logs"
    log_success "Directories created"
}

install_application() {
    log_info "Installing ServerInventory to ${INSTALL_DIR}..."

    local SCRIPT_DIR
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    local SRC_DIR=""

    # Check multiple locations for local repository files
    for dir in "$SCRIPT_DIR" "$(pwd)" "$SCRIPT_DIR/Server-Inventory" "$(pwd)/Server-Inventory" "$SCRIPT_DIR/.." "$(pwd)/.."; do
        if [ -f "$dir/server/app.py" ]; then
            SRC_DIR="$(cd "$dir" && pwd)"
            break
        fi
    done

    if [ -n "$SRC_DIR" ]; then
        log_info "Local installation detected from ${SRC_DIR}"
        cp -r "$SRC_DIR/server" "$INSTALL_DIR/"
        cp -r "$SRC_DIR/web" "$INSTALL_DIR/"
        cp "$SRC_DIR/requirements.txt" "$INSTALL_DIR/"
        [ -f "$SRC_DIR/uninstall.sh" ] && cp "$SRC_DIR/uninstall.sh" "$INSTALL_DIR/"
    else
        log_info "Fetching application files..."
        local COPIED=false
        local TEMP_DIR="/tmp/serverinventory-src"

        # 1. Try git clone
        if command -v git &>/dev/null; then
            rm -rf "$TEMP_DIR"
            if git clone --depth 1 "https://github.com/iammohdrazi/Server-Inventory.git" "$TEMP_DIR" 2>/dev/null; then
                cp -r "$TEMP_DIR/server" "$INSTALL_DIR/"
                cp -r "$TEMP_DIR/web" "$INSTALL_DIR/"
                cp "$TEMP_DIR/requirements.txt" "$INSTALL_DIR/"
                [ -f "$TEMP_DIR/uninstall.sh" ] && cp "$TEMP_DIR/uninstall.sh" "$INSTALL_DIR/"
                rm -rf "$TEMP_DIR"
                COPIED=true
            fi
        fi

        # 2. Try release tarball or main branch archive
        if [ "$COPIED" = false ]; then
            local TEMP_FILE="/tmp/serverinventory-download.tar.gz"
            local DOWNLOADED=false

            if curl -fsSL -o "$TEMP_FILE" "${REPO_URL}/releases/latest/download/serverinventory.tar.gz" 2>/dev/null; then
                DOWNLOADED=true
            elif curl -fsSL -o "$TEMP_FILE" "https://github.com/iammohdrazi/Server-Inventory/archive/refs/heads/main.tar.gz" 2>/dev/null; then
                DOWNLOADED=true
            fi

            if [ "$DOWNLOADED" = true ]; then
                tar -xzf "$TEMP_FILE" -C "$INSTALL_DIR" --strip-components=1
                rm -f "$TEMP_FILE"
                COPIED=true
            fi
        fi

        if [ "$COPIED" = false ]; then
            log_error "Could not fetch application files automatically."
            log_info "Please clone the repository and run the installer locally:"
            log_info "  git clone https://github.com/iammohdrazi/Server-Inventory.git"
            log_info "  cd Server-Inventory && sudo bash install.sh --local"
            exit 1
        fi
    fi

    log_success "Application files installed"
}

setup_virtualenv() {
    log_info "Setting up Python virtual environment..."
    $PYTHON_CMD -m venv "$INSTALL_DIR/venv"
    source "$INSTALL_DIR/venv/bin/activate"

    # Upgrade pip
    pip install --upgrade pip -q

    # Install requirements
    pip install -r "$INSTALL_DIR/requirements.txt" -q

    deactivate
    log_success "Python dependencies installed"
}

generate_ssl_certs() {
    local CERT_DIR="$DATA_DIR/certs"
    local CERT_FILE="$CERT_DIR/server.crt"
    local KEY_FILE="$CERT_DIR/server.key"

    if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
        log_info "SSL certificates already exist, skipping generation"
        return
    fi

    log_info "Generating self-signed SSL certificate..."

    local HOSTNAME=$(hostname -f 2>/dev/null || hostname)
    local IP_ADDR=$(hostname -I 2>/dev/null | awk '{print $1}')

    openssl req -x509 -nodes -days 3650 \
        -newkey rsa:2048 \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -subj "/C=US/ST=Server/L=ServerInventory/O=ServerInventory/CN=$HOSTNAME" \
        -addext "subjectAltName=DNS:$HOSTNAME,DNS:localhost,IP:$IP_ADDR,IP:127.0.0.1" \
        2>/dev/null

    chmod 600 "$KEY_FILE"
    chmod 644 "$CERT_FILE"

    log_success "SSL certificate generated (valid for 10 years)"
    log_info "  Certificate: $CERT_FILE"
    log_info "  Private Key: $KEY_FILE"
}

generate_config() {
    local CONFIG_FILE="$DATA_DIR/config.json"

    if [ -f "$CONFIG_FILE" ]; then
        log_info "Configuration file exists, preserving"
        return
    fi

    log_info "Generating configuration..."

    local SECRET_KEY=$(openssl rand -hex 32)

    cat > "$CONFIG_FILE" <<EOF
{
    "secret_key": "${SECRET_KEY}",
    "port": ${PORT},
    "session_timeout_minutes": 30,
    "max_upload_size_mb": 500,
    "allowed_file_roots": ["/"],
    "blocked_paths": ["/proc", "/sys", "/dev", "/run/lock", "/var/lib/serverinventory"],
    "enable_terminal": true,
    "enable_file_manager": true,
    "enable_service_control": true,
    "log_level": "INFO"
}
EOF

    chmod 600 "$CONFIG_FILE"
    log_success "Configuration generated at $CONFIG_FILE"
}

install_systemd_service() {
    log_info "Installing systemd service..."

    cat > /etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=ServerInventory — Linux Server Management
Documentation=https://github.com/iammohdrazi/Server-Inventory
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=${INSTALL_DIR}/server
Environment=SERVERINVENTORY_DATA=${DATA_DIR}
Environment=SERVERINVENTORY_PORT=${PORT}
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/server/app.py
Restart=always
RestartSec=5
StartLimitInterval=60
StartLimitBurst=3

# Security hardening
NoNewPrivileges=false
ProtectSystem=false
ProtectHome=false
ReadWritePaths=${DATA_DIR}

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=serverinventory

[Install]
WantedBy=multi-user.target
EOF

    if pidof systemd &>/dev/null || [ -d /run/systemd/system ]; then
        systemctl daemon-reload 2>/dev/null || true
        systemctl enable ${SERVICE_NAME} --now 2>/dev/null || true
    fi

    log_success "Systemd service installed"
}

configure_firewall() {
    log_info "Configuring firewall..."

    # UFW
    if command -v ufw &>/dev/null; then
        ufw allow ${PORT}/tcp comment "ServerInventory" 2>/dev/null && \
            log_success "UFW: Port ${PORT} opened" || true
    fi

    # firewalld
    if command -v firewall-cmd &>/dev/null && systemctl is-active firewalld &>/dev/null; then
        firewall-cmd --permanent --add-port=${PORT}/tcp 2>/dev/null && \
            firewall-cmd --reload 2>/dev/null && \
            log_success "firewalld: Port ${PORT} opened" || true
    fi

    # iptables direct (if no other firewall)
    if ! command -v ufw &>/dev/null && ! command -v firewall-cmd &>/dev/null; then
        if command -v iptables &>/dev/null; then
            iptables -I INPUT -p tcp --dport ${PORT} -j ACCEPT 2>/dev/null && \
                log_success "iptables: Port ${PORT} opened" || true
        fi
    fi
}

print_summary() {
    local IP_ADDR=$(hostname -I 2>/dev/null | awk '{print $1}')
    local HOSTNAME=$(hostname -f 2>/dev/null || hostname)

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                  ║${NC}"
    echo -e "${GREEN}║    ✅ ServerInventory installed successfully!     ║${NC}"
    echo -e "${GREEN}║                                                  ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BOLD}Access your server at:${NC}"
    echo -e "    🌐 ${CYAN}https://${IP_ADDR}:${PORT}${NC}"
    echo -e "    🌐 ${CYAN}https://${HOSTNAME}:${PORT}${NC}"
    echo -e "    🌐 ${CYAN}https://localhost:${PORT}${NC}"
    echo ""
    echo -e "  ${BOLD}Login:${NC} Use your Linux system credentials"
    echo ""
    echo -e "  ${BOLD}Service management:${NC}"
    echo -e "    Start:   ${YELLOW}sudo systemctl start ${SERVICE_NAME}${NC}"
    echo -e "    Stop:    ${YELLOW}sudo systemctl stop ${SERVICE_NAME}${NC}"
    echo -e "    Status:  ${YELLOW}sudo systemctl status ${SERVICE_NAME}${NC}"
    echo -e "    Logs:    ${YELLOW}sudo journalctl -u ${SERVICE_NAME} -f${NC}"
    echo ""
    echo -e "  ${BOLD}Uninstall:${NC}"
    echo -e "    ${YELLOW}sudo ${INSTALL_DIR}/uninstall.sh${NC}"
    echo ""
    echo -e "  ${RED}Note:${NC} Your browser will show a certificate warning"
    echo -e "  because we use a self-signed SSL certificate."
    echo -e "  This is safe — just click 'Advanced' → 'Proceed'."
    echo ""
}

# ─── Main ───────────────────────────────────────────────────────────────

main() {
    banner
    check_root
    detect_os
    install_system_deps
    check_python
    create_directories
    install_application
    setup_virtualenv
    generate_ssl_certs
    generate_config
    install_systemd_service
    configure_firewall
    print_summary
}

# Handle --local flag (skip download, use local files)
if [[ "${1:-}" == "--local" ]]; then
    log_info "Local install mode"
fi

main "$@"
