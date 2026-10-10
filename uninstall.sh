#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# ServerInventory — Uninstallation Script
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

INSTALL_DIR="/opt/serverinventory"
DATA_DIR="/var/lib/serverinventory"
SERVICE_NAME="serverinventory"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[  OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Check root
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[FAIL]${NC} This script must be run as root (use sudo)"
    exit 1
fi

echo -e "${RED}"
echo "╔══════════════════════════════════════════════════╗"
echo "║                                                  ║"
echo "║     🗑️  ServerInventory Uninstaller               ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${YELLOW}This will completely remove ServerInventory from this system.${NC}"
echo ""

# Ask for confirmation
read -p "Are you sure you want to uninstall? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

# Ask about data
REMOVE_DATA=false
read -p "Remove all data (config, certs, logs)? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    REMOVE_DATA=true
fi

echo ""

# Stop and disable service
log_info "Stopping service..."
systemctl stop ${SERVICE_NAME} 2>/dev/null || true
systemctl disable ${SERVICE_NAME} 2>/dev/null || true
log_success "Service stopped"

# Remove systemd service file
log_info "Removing systemd service..."
rm -f /etc/systemd/system/${SERVICE_NAME}.service
systemctl daemon-reload 2>/dev/null || true
log_success "Service file removed"

# Remove application files
log_info "Removing application files..."
rm -rf "$INSTALL_DIR"
log_success "Application removed from $INSTALL_DIR"

# Remove data if requested
if [ "$REMOVE_DATA" = true ]; then
    log_info "Removing data directory..."
    rm -rf "$DATA_DIR"
    log_success "Data removed from $DATA_DIR"
else
    log_warn "Data preserved at $DATA_DIR"
    log_warn "Remove manually with: sudo rm -rf $DATA_DIR"
fi

# Remove firewall rules
log_info "Cleaning up firewall rules..."
if command -v ufw &>/dev/null; then
    ufw delete allow 9443/tcp 2>/dev/null || true
fi
if command -v firewall-cmd &>/dev/null && systemctl is-active firewalld &>/dev/null; then
    firewall-cmd --permanent --remove-port=9443/tcp 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ ServerInventory has been uninstalled          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
