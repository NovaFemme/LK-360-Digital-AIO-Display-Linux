# LK Digital Display for Linux 🐧

**Why this project exists: The Xigmatek LK 360 Digital AIO cooler has a beautiful LCD display for system monitoring, but the official software only supports Windows. Linux users – especially those with newer AMD GPUs like the RX 9070 XT – were left without any way to use this hardware feature. This project provides a fully native Linux solution using Python and kernel interfaces, with no Wine or Windows dependencies required.**

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Linux-green?logo=linux" alt="Linux">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
  <img src="https://img.shields.io/badge/Status-Working-brightgreen" alt="Status">
</p>

<p align="center">
  <b>Native Linux support for Xigmatek LK 360 Digital AIO cooler LCD displays</b><br>
  Real-time CPU and GPU monitoring without Wine or Windows dependencies
</p>

---

## 📸 Preview

Your AIO cooler display will show real-time system stats:

| Metric | Display |
|--------|---------|
| CPU Temperature | ✅ Live updates |
| CPU Frequency | ✅ Current clock speed |
| GPU Temperature | ✅ Live updates |
| GPU Frequency/Usage | ✅ Live updates |

---

## ✨ Features

- **🚀 Native Linux** - No Wine, no Windows, no emulation
- **🔧 Zero Dependencies** - Uses built-in Linux kernel interfaces
- **💻 Multi-GPU Support**
  - NVIDIA (via nvidia-smi)
  - AMD Radeon (via amdgpu sysfs)
  - Intel (via i915 sysfs)
- **🌡️ Accurate Sensors** - Uses lm-sensors/hwmon for reliable readings
- **⚡ Lightweight** - Minimal resource usage (~1% CPU)
- **🔄 Auto-reconnect** - Handles USB disconnects gracefully
- **📦 Easy Install** - One-command installation script

---

## 🖥️ Supported Hardware

### Displays

| Device | Vendor ID | Product ID | Status |
|--------|-----------|------------|--------|
| Xigmatek LK 360 Digital AIO | `0x1B80` | `0xB538` | ✅ Fully Supported |
| HWCX Controller | `0x0145` | `0x1005` | ✅ Fully Supported |

### Tested Distributions

| Distribution | Version | Status |
|--------------|---------|--------|
| Linux Mint | 22.x | ✅ Tested |
| Ubuntu | 22.04+ | ✅ Should work |
| Fedora | 38+ | ✅ Should work |
| Arch Linux | Rolling | ✅ Should work |
| Debian | 12+ | ✅ Should work |

---

## 📋 Requirements

- **Linux** with kernel 5.x or newer
- **Python 3.10** or newer
- **lm-sensors** (for CPU temperature)
- **Root access** (or udev rules configured)

### For GPU Monitoring

| GPU Brand | Requirement |
|-----------|-------------|
| NVIDIA | `nvidia-driver` package installed |
| AMD | Built-in (amdgpu kernel driver) |
| Intel | Built-in (i915 kernel driver) |

---

## 🚀 Quick Start

### Option 1: Automated Install (Recommended)

```bash
# Clone the repository
git clone https://github.com/NovaFemme/lk-display-linux.git
cd lk-display-linux

# Run the installer
sudo ./install.sh
```

The installer will:
- ✅ Install required packages (python3, lm-sensors)
- ✅ Configure hardware sensors
- ✅ Install udev rules for USB access
- ✅ Set up systemd service
- ✅ Enable auto-start on boot

### Option 2: Manual Install

```bash
# Install dependencies
sudo apt install python3 lm-sensors  # Debian/Ubuntu/Mint
# OR
sudo dnf install python3 lm_sensors  # Fedora
# OR
sudo pacman -S python lm_sensors     # Arch

# Configure sensors
sudo sensors-detect --auto

# Copy files
sudo mkdir -p /opt/lk-display
sudo cp *.py /opt/lk-display/
sudo cp config.ini /opt/lk-display/

# Install udev rules (allows non-root access)
sudo cp 99-lk-display.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

# Install and enable service
sudo cp lk-display.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lk-display
```

---

## 🎮 Usage

### Service Commands

```bash
# Start the service
sudo systemctl start lk-display

# Stop the service
sudo systemctl stop lk-display

# Check status
sudo systemctl status lk-display

# View live logs
sudo journalctl -u lk-display -f

# Enable auto-start on boot
sudo systemctl enable lk-display

# Disable auto-start
sudo systemctl disable lk-display
```

### Manual Execution (for testing)

```bash
# Run with debug output
sudo python3 /opt/lk-display/lk_display.py -d

# Scan for devices only
python3 /opt/lk-display/lk_display.py --scan

# Use custom config file
sudo python3 /opt/lk-display/lk_display.py -c /path/to/config.ini
```

### Diagnostic Tools

```bash
# Run hardware diagnostics
sudo python3 /opt/lk-display/diagnose.py

# Test display communication
sudo python3 /opt/lk-display/test_packet.py

# Test display modes
sudo python3 /opt/lk-display/test_display_mode.py
```

---

## ⚙️ Configuration

Edit `/opt/lk-display/config.ini`:

```ini
[config]
# Update interval in milliseconds (default: 500)
refresh_delay=500

# Enable logging (True/False)
IsLog=True

# Log file path (empty = application directory)
LogPath=

# Enable debug output (True/False)
Debug=False
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `refresh_delay` | `500` | How often to update the display (ms) |
| `IsLog` | `True` | Enable/disable logging |
| `LogPath` | *(empty)* | Custom log file path |
| `Debug` | `False` | Enable verbose debug output |

---

## 🔧 Troubleshooting

### Display Not Detected

1. **Check USB connection**
   ```bash
   lsusb | grep -E "1B80|0145"
   ```
   You should see your device listed.

2. **Check hidraw devices**
   ```bash
   ls -la /dev/hidraw*
   ```

3. **Run with sudo**
   ```bash
   sudo python3 /opt/lk-display/lk_display.py -d
   ```

4. **Verify udev rules**
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

### CPU Temperature Shows 0°C

1. **Check if sensors work**
   ```bash
   sensors
   ```

2. **Run sensors-detect**
   ```bash
   sudo sensors-detect
   ```

3. **Load kernel modules**
   ```bash
   # Intel CPU
   sudo modprobe coretemp
   
   # AMD CPU
   sudo modprobe k10temp
   ```

### GPU Not Detected

**NVIDIA:**
```bash
# Check if nvidia-smi works
nvidia-smi

# If not found, install drivers
sudo apt install nvidia-driver-535  # or current version
```

**AMD:**
```bash
# Check if amdgpu is loaded
lsmod | grep amdgpu

# Check sysfs path
ls /sys/class/drm/card*/device/gpu_busy_percent
```

### Permission Denied Errors

```bash
# Add user to plugdev group
sudo usermod -a -G plugdev $USER

# Log out and back in, or run:
newgrp plugdev
```

### Service Won't Start

```bash
# Check for errors
sudo journalctl -u lk-display -n 50

# Try running manually to see errors
sudo python3 /opt/lk-display/lk_display.py -d
```

---

## 🗑️ Uninstallation

```bash
# Run uninstaller
sudo ./uninstall.sh

# Or manually:
sudo systemctl stop lk-display
sudo systemctl disable lk-display
sudo rm /etc/systemd/system/lk-display.service
sudo rm /etc/udev/rules.d/99-lk-display.rules
sudo rm -rf /opt/lk-display
sudo systemctl daemon-reload
sudo udevadm control --reload-rules
```

---

## 📁 Project Structure

```
lk-display-linux/
├── lk_display.py          # Main application
├── hardware_monitor.py    # CPU/GPU sensor reading
├── hid_device.py          # USB HID communication
├── config.py              # Configuration handling
├── config.ini             # Configuration file
├── diagnose.py            # Hardware diagnostics tool
├── test_packet.py         # Packet format tester
├── test_display_mode.py   # Display mode tester
├── 99-lk-display.rules    # udev rules
├── lk-display.service     # systemd service
├── install.sh             # Installation script
├── uninstall.sh           # Uninstallation script
└── README.md              # This file
```

---

## 🔬 Technical Details

### How It Works

| Component | Linux Source |
|-----------|--------------|
| CPU Temperature | `/sys/class/hwmon/*/temp*_input` |
| CPU Usage | `/proc/stat` |
| CPU Frequency | `/sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq` |
| GPU (NVIDIA) | `nvidia-smi` command |
| GPU (AMD) | `/sys/class/drm/card*/device/gpu_busy_percent` |
| GPU (Intel) | `/sys/class/drm/card*/device/gt_cur_freq_mhz` |
| Memory | `/proc/meminfo` |
| USB HID | `/dev/hidraw*` via ioctl |

### USB Protocol

- **Interface:** USB HID (Human Interface Device)
- **Report Size:** 65 bytes
- **Update Rate:** Configurable (default 500ms)

---

### Development Setup

```bash
git clone https://github.com/NovaFemme/lk-display-linux.git
cd lk-display-linux

# Run in debug mode for development
sudo python3 lk_display.py -d
```

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Original Windows version developers
- [lm-sensors](https://github.com/lm-sensors/lm-sensors) project
- Linux kernel hwmon subsystem developers
- The Linux community

---

<p align="center">
  Made with ❤️ for the Linux community
</p>
