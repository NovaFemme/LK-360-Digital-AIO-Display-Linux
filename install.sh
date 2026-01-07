#!/bin/bash
#
# LK Digital Display - Linux Installation Script
# For Linux Mint 22.2 and other Debian/Ubuntu-based distributions
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

INSTALL_DIR="/opt/lk-display"
SERVICE_NAME="lk-display"

echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   LK Digital Display - Linux Installer    ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root (sudo ./install.sh)${NC}"
    exit 1
fi

# Detect package manager
if command -v apt &> /dev/null; then
    PKG_MANAGER="apt"
elif command -v dnf &> /dev/null; then
    PKG_MANAGER="dnf"
elif command -v pacman &> /dev/null; then
    PKG_MANAGER="pacman"
else
    echo -e "${RED}Error: Unsupported package manager${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Installing dependencies...${NC}"

case $PKG_MANAGER in
    apt)
        apt update
        apt install -y python3 python3-pip lm-sensors
        ;;
    dnf)
        dnf install -y python3 python3-pip lm_sensors
        ;;
    pacman)
        pacman -Sy --noconfirm python python-pip lm_sensors
        ;;
esac

echo -e "${GREEN}✓ Dependencies installed${NC}"

echo
echo -e "${YELLOW}Step 2: Setting up sensors...${NC}"

# Detect and load sensor modules
if command -v sensors-detect &> /dev/null; then
    echo "Running sensors-detect (auto-accept)..."
    yes "" | sensors-detect --auto > /dev/null 2>&1 || true
fi

# Load sensor modules
modprobe coretemp 2>/dev/null || true
modprobe k10temp 2>/dev/null || true

echo -e "${GREEN}✓ Sensors configured${NC}"

echo
echo -e "${YELLOW}Step 3: Installing application...${NC}"

# Create install directory
mkdir -p "$INSTALL_DIR"

# Copy files
cp lk_display.py "$INSTALL_DIR/"
cp hardware_monitor.py "$INSTALL_DIR/"
cp hid_device.py "$INSTALL_DIR/"
cp config.py "$INSTALL_DIR/"

# Create default config if not exists
if [ ! -f "$INSTALL_DIR/config.ini" ]; then
    cat > "$INSTALL_DIR/config.ini" << EOF
[config]
refresh_delay=500
send_delay=500
IsLog=True
LogPath=
Debug=False
IsUdp=False
localPort=8890
EOF
fi

# Set permissions
chmod +x "$INSTALL_DIR/lk_display.py"
chmod 644 "$INSTALL_DIR"/*.py
chmod 644 "$INSTALL_DIR/config.ini"

echo -e "${GREEN}✓ Application installed to $INSTALL_DIR${NC}"

echo
echo -e "${YELLOW}Step 4: Installing udev rules...${NC}"

cp 99-lk-display.rules /etc/udev/rules.d/
udevadm control --reload-rules
udevadm trigger

echo -e "${GREEN}✓ udev rules installed${NC}"

echo
echo -e "${YELLOW}Step 5: Installing systemd service...${NC}"

cp lk-display.service /etc/systemd/system/
systemctl daemon-reload

echo -e "${GREEN}✓ Systemd service installed${NC}"

echo
echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Installation Complete!            ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo
echo "To start the service:"
echo -e "  ${YELLOW}sudo systemctl start lk-display${NC}"
echo
echo "To enable at boot:"
echo -e "  ${YELLOW}sudo systemctl enable lk-display${NC}"
echo
echo "To check status:"
echo -e "  ${YELLOW}sudo systemctl status lk-display${NC}"
echo
echo "To view logs:"
echo -e "  ${YELLOW}journalctl -u lk-display -f${NC}"
echo
echo "To run manually (for testing):"
echo -e "  ${YELLOW}sudo python3 $INSTALL_DIR/lk_display.py -d${NC}"
echo
echo "Configuration file: $INSTALL_DIR/config.ini"
echo

# Check for NVIDIA
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}✓ NVIDIA GPU detected - nvidia-smi available${NC}"
else
    echo -e "${YELLOW}ℹ NVIDIA GPU not detected or drivers not installed${NC}"
fi

# Check for AMD GPU
if [ -d "/sys/class/drm/card0/device/hwmon" ]; then
    if grep -q "0x1002" /sys/class/drm/card0/device/vendor 2>/dev/null; then
        echo -e "${GREEN}✓ AMD GPU detected${NC}"
    fi
fi

# Scan for devices
echo
echo "Scanning for display devices..."
python3 "$INSTALL_DIR/lk_display.py" --scan
