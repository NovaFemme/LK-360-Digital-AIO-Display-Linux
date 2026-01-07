#!/usr/bin/env python3
"""
LK Digital Display - Linux Edition
Main application for GAMDIAS ATLAS AIO cooler LCD displays.

Native Linux implementation using:
- /sys/class/hwmon for CPU temperature (lm-sensors)
- /proc/stat for CPU usage
- nvidia-smi for NVIDIA GPUs
- amdgpu sysfs for AMD GPUs
- hidraw for USB HID communication

No Wine, LibreHardwareMonitor, or HWiNFO required.
"""

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from hardware_monitor import HardwareMonitor, CpuData, GpuData
from hid_device import HidDevice
from config import Config

__version__ = "2.2.0-linux"

# Setup logging
logger = logging.getLogger("lk-display")


class LKDisplay:
    """Main application class"""
    
    def __init__(self, config: Config):
        self.config = config
        self.running = False
        self.hid: Optional[HidDevice] = None
        self.monitor: Optional[HardwareMonitor] = None
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure logging based on config"""
        level = logging.DEBUG if self.config.debug else logging.INFO
        
        handlers = [logging.StreamHandler()]
        
        if self.config.log_enabled and self.config.log_path:
            try:
                file_handler = logging.FileHandler(self.config.log_path)
                file_handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                ))
                handlers.append(file_handler)
            except Exception as e:
                print(f"Warning: Could not create log file: {e}")
        
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=handlers
        )
    
    def _log(self, msg: str):
        """Log callback for modules"""
        logger.info(msg)
    
    def _get_memory_usage(self) -> int:
        """Get system memory usage percentage"""
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
            
            mem_total = 0
            mem_available = 0
            
            for line in lines:
                if line.startswith('MemTotal:'):
                    mem_total = int(line.split()[1])
                elif line.startswith('MemAvailable:'):
                    mem_available = int(line.split()[1])
            
            if mem_total > 0:
                return int(100 * (mem_total - mem_available) / mem_total)
        except Exception as e:
            logger.debug(f"Failed to get memory usage: {e}")
        
        return 0
    
    def _get_disk_usage(self) -> int:
        """Get root filesystem usage percentage"""
        try:
            stat = os.statvfs('/')
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bfree * stat.f_frsize
            used = total - free
            return int(100 * used / total) if total > 0 else 0
        except Exception as e:
            logger.debug(f"Failed to get disk usage: {e}")
            return 0
    
    def start(self) -> bool:
        """Start the display service"""
        logger.info(f"LK Digital Display v{__version__} starting...")
        
        # Initialize hardware monitor
        self.monitor = HardwareMonitor(log_callback=self._log)
        
        # Initialize HID device
        self.hid = HidDevice(log_callback=self._log)
        count = self.hid.open_devices()
        
        if count == 0:
            logger.error("No supported displays found!")
            logger.info("Troubleshooting:")
            logger.info("  1. Run with sudo: sudo python3 lk_display.py")
            logger.info("  2. Check USB connection: lsusb | grep -E '1B80|0145'")
            logger.info("  3. Install udev rules: sudo cp 99-lk-display.rules /etc/udev/rules.d/")
            return False
        
        logger.info(f"Connected to {count} display(s)")
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.running = True
        return True
    
    def stop(self):
        """Stop the display service"""
        logger.info("Stopping LK Digital Display...")
        self.running = False
        
        if self.hid:
            self.hid.close_devices()
            self.hid = None
        
        self.monitor = None
        logger.info("Stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle termination signals"""
        logger.info(f"Received signal {signum}")
        self.running = False
    
    def run(self):
        """Main run loop"""
        if not self.start():
            return 1
        
        logger.info(f"Update interval: {self.config.refresh_delay}ms")
        
        # Prime the CPU usage tracker - need multiple readings for accurate delta
        logger.info("Initializing CPU usage tracking...")
        for _ in range(3):
            self.monitor.get_cpu_data()
            time.sleep(0.2)
        
        logger.info("Starting main loop")
        
        try:
            while self.running:
                self._update_cycle()
                time.sleep(self.config.refresh_delay / 1000.0)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
        
        return 0
    
    def _update_cycle(self):
        """Single update cycle"""
        # Check if devices are still connected
        if self.hid.get_online_device_count() == 0:
            logger.warning("No devices connected, scanning...")
            count = self.hid.open_devices()
            if count == 0:
                time.sleep(5)  # Wait before retry
                return
        
        # Get CPU data
        cpu = self.monitor.get_cpu_data()
        self.hid.set_cpu_data(
            temp=int(cpu.temperature),
            usage=int(cpu.usage),
            freq=int(cpu.frequency),
            fan_rpm=cpu.fan_rpm,
            power=int(cpu.power)
        )
        
        # Get GPU data
        gpu = self.monitor.get_gpu_data()
        if gpu.is_valid:
            self.hid.set_gpu_data(
                temp=int(gpu.temperature),
                usage=int(gpu.usage),
                freq=int(gpu.frequency),
                fan_rpm=int(gpu.fan_rpm),
                power=int(gpu.power)
            )
        else:
            # Send zeros if GPU not valid
            self.hid.set_gpu_data(temp=0, usage=0, freq=0, fan_rpm=0, power=0)
        
        # Get memory usage
        mem_usage = self._get_memory_usage()
        self.hid.set_memory_data(usage=mem_usage)
        
        # Get disk usage
        disk_usage = self._get_disk_usage()
        self.hid.set_disk_data(usage=disk_usage)
        
        # Send to display
        if not self.hid.send_data():
            logger.debug("Failed to send data")
        
        # Debug output - always show key values
        if self.config.debug:
            logger.debug(
                f"CPU: {cpu.temperature:.0f}°C {cpu.usage:.0f}% {cpu.frequency:.0f}MHz | "
                f"GPU: {gpu.temperature:.0f}°C {gpu.usage:.0f}% {gpu.frequency:.0f}MHz | "
                f"MEM: {mem_usage}%"
            )


def main():
    parser = argparse.ArgumentParser(
        description="LK Digital Display for Linux",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 lk_display.py              Run with default settings
  sudo python3 lk_display.py -d           Run with debug output
  sudo python3 lk_display.py -c my.ini    Use custom config file
  python3 lk_display.py --scan            Scan for devices (no root needed)

For udev setup (run once):
  sudo cp 99-lk-display.rules /etc/udev/rules.d/
  sudo udevadm control --reload-rules
  sudo udevadm trigger
        """
    )
    
    parser.add_argument(
        '-c', '--config',
        default='config.ini',
        help='Configuration file path (default: config.ini)'
    )
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--scan',
        action='store_true',
        help='Scan for devices and exit'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'LK Digital Display v{__version__}'
    )
    
    args = parser.parse_args()
    
    # Just scan for devices
    if args.scan:
        print("Scanning for supported devices...")
        hid = HidDevice()
        devices = hid.scan_devices()
        if devices:
            print(f"\nFound {len(devices)} device(s):")
            for dev in devices:
                print(f"  - {dev.name}")
                print(f"    Path: {dev.path}")
                print(f"    VID: 0x{dev.vendor_id:04X}, PID: 0x{dev.product_id:04X}")
        else:
            print("\nNo supported devices found.")
            print("\nLooking for any HID devices...")
            for path in sorted(Path("/dev").glob("hidraw*")):
                print(f"  Found: {path}")
        return 0
    
    # Load config
    config = Config()
    config_path = Path(args.config)
    
    if config_path.exists():
        config.load(str(config_path))
        print(f"Loaded config from {config_path}")
    else:
        print(f"Config file not found: {config_path}, using defaults")
    
    if args.debug:
        config.debug = True
    
    # Run application
    app = LKDisplay(config)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
