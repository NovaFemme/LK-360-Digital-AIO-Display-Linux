#!/bin/bash
#
# LK Digital Display - Uninstall Script
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

INSTALL_DIR="/opt/lk-display"
SERVICE_NAME="lk-display"

echo -e "${YELLOW}LK Digital Display - Uninstaller${NC}"
echo

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root (sudo ./uninstall.sh)${NC}"
    exit 1
fi

echo "This will remove LK Digital Display from your system."
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo
echo -e "${YELLOW}Stopping service...${NC}"
systemctl stop $SERVICE_NAME 2>/dev/null || true
systemctl disable $SERVICE_NAME 2>/dev/null || true

echo -e "${YELLOW}Removing systemd service...${NC}"
rm -f /etc/systemd/system/lk-display.service
systemctl daemon-reload

echo -e "${YELLOW}Removing udev rules...${NC}"
rm -f /etc/udev/rules.d/99-lk-display.rules
udevadm control --reload-rules

echo -e "${YELLOW}Removing application files...${NC}"
rm -rf "$INSTALL_DIR"

echo
echo -e "${GREEN}✓ LK Digital Display has been uninstalled${NC}"
