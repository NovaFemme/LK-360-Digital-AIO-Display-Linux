#!/usr/bin/env python3
"""
HID Device Communication for Linux
Communicates with USB HID devices (GAMDIAS ATLAS, HWCX) using native Linux hidraw.
No Wine or Windows dependencies.

Supports:
- GAMDIAS ATLAS (VID: 0x1B80, PID: 0xB538)
- HWCX Controller (VID: 0x0145, PID: 0x1005)
"""

import os
import struct
import fcntl
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Callable
from datetime import datetime

logger = logging.getLogger(__name__)

# ioctl constants for hidraw
HIDIOCGRAWINFO = 0x80084803
HIDIOCGRAWNAME_LEN = 256
HIDIOCGRAWNAME = 0x80FF4804


@dataclass
class DeviceInfo:
    path: str
    vendor_id: int
    product_id: int
    name: str
    is_gamdias: bool = False


@dataclass
class SensorData:
    cpu_temp: int = 0
    cpu_usage: int = 0
    cpu_freq: int = 0  # MHz
    cpu_fan_rpm: int = 0
    cpu_power: int = 0  # Watts
    
    gpu_temp: int = 0
    gpu_usage: int = 0
    gpu_freq: int = 0  # MHz
    gpu_fan_rpm: int = 0
    gpu_power: int = 0  # Watts
    
    mem_usage: int = 0
    mem_temp: int = 0
    
    disk_usage: int = 0
    disk_temp: int = 0
    
    net_upload: int = 0
    net_download: int = 0
    
    display_mode: int = 0


class HidDevice:
    """HID Device communication using Linux hidraw"""
    
    # Supported devices
    SUPPORTED_DEVICES = [
        (0x1B80, 0xB538, "GAMDIAS ATLAS"),  # GAMDIAS
        (0x0145, 0x1005, "HWCX Controller"),  # HWCX
    ]
    
    REPORT_SIZE = 65  # 64 bytes + report ID
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self.log_callback = log_callback or (lambda x: None)
        self._devices: Dict[str, int] = {}  # path -> file descriptor
        self._device_info: Dict[str, DeviceInfo] = {}
        self._sensor_data = SensorData()
        self._initialized_devices: set = set()
    
    def _log(self, msg: str):
        logger.info(msg)
        self.log_callback(msg)
    
    def _get_device_info(self, path: str) -> Optional[DeviceInfo]:
        """Get HID device information using ioctl"""
        try:
            fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
            try:
                # Get raw device info (bus, vendor, product)
                buf = bytearray(8)
                fcntl.ioctl(fd, HIDIOCGRAWINFO, buf)
                bus_type, vendor_id, product_id = struct.unpack('Ihh', buf)
                
                # Convert signed to unsigned
                vendor_id = vendor_id & 0xFFFF
                product_id = product_id & 0xFFFF
                
                # Get device name
                name_buf = bytearray(HIDIOCGRAWNAME_LEN)
                try:
                    fcntl.ioctl(fd, HIDIOCGRAWNAME, name_buf)
                    name = name_buf.split(b'\x00')[0].decode('utf-8', errors='ignore')
                except:
                    name = "Unknown Device"
                
                is_gamdias = (vendor_id == 0x1B80 and product_id == 0xB538)
                
                return DeviceInfo(
                    path=path,
                    vendor_id=vendor_id,
                    product_id=product_id,
                    name=name,
                    is_gamdias=is_gamdias
                )
            finally:
                os.close(fd)
        except Exception as e:
            logger.debug(f"Failed to get device info for {path}: {e}")
            return None
    
    def scan_devices(self) -> List[DeviceInfo]:
        """Scan for supported HID devices"""
        found = []
        hidraw_dir = Path("/dev")
        
        for path in sorted(hidraw_dir.glob("hidraw*")):
            info = self._get_device_info(str(path))
            if info:
                # Check if this is a supported device
                for vid, pid, desc in self.SUPPORTED_DEVICES:
                    if info.vendor_id == vid and info.product_id == pid:
                        self._log(f"Found {desc}: {path} (VID={vid:04X}, PID={pid:04X})")
                        found.append(info)
                        break
        
        return found
    
    def open_devices(self) -> int:
        """Open all supported devices"""
        devices = self.scan_devices()
        opened = 0
        
        for info in devices:
            try:
                fd = os.open(info.path, os.O_RDWR)
                self._devices[info.path] = fd
                self._device_info[info.path] = info
                opened += 1
                self._log(f"Opened device: {info.path}")
            except PermissionError:
                self._log(f"Permission denied: {info.path} (run with sudo or add udev rule)")
            except Exception as e:
                self._log(f"Failed to open {info.path}: {e}")
        
        return opened
    
    def close_devices(self):
        """Close all open devices"""
        for path, fd in self._devices.items():
            try:
                os.close(fd)
                self._log(f"Closed device: {path}")
            except:
                pass
        self._devices.clear()
        self._device_info.clear()
        self._initialized_devices.clear()
    
    def get_online_device_count(self) -> int:
        """Return number of open devices"""
        return len(self._devices)
    
    def set_cpu_data(self, temp: int, usage: int, freq: int = 0, 
                     fan_rpm: int = 0, power: int = 0):
        """Set CPU sensor data"""
        self._sensor_data.cpu_temp = min(255, max(0, temp))
        self._sensor_data.cpu_usage = min(100, max(0, usage))
        self._sensor_data.cpu_freq = min(65535, max(0, freq))
        self._sensor_data.cpu_fan_rpm = min(65535, max(0, fan_rpm))
        self._sensor_data.cpu_power = min(65535, max(0, power))
    
    def set_gpu_data(self, temp: int, usage: int, freq: int = 0,
                     fan_rpm: int = 0, power: int = 0):
        """Set GPU sensor data"""
        self._sensor_data.gpu_temp = min(255, max(0, temp))
        self._sensor_data.gpu_usage = min(100, max(0, usage))
        self._sensor_data.gpu_freq = min(65535, max(0, freq))
        self._sensor_data.gpu_fan_rpm = min(65535, max(0, fan_rpm))
        self._sensor_data.gpu_power = min(65535, max(0, power))
    
    def set_memory_data(self, usage: int, temp: int = 0):
        """Set memory data"""
        self._sensor_data.mem_usage = min(100, max(0, usage))
        self._sensor_data.mem_temp = min(255, max(0, temp))
    
    def set_disk_data(self, usage: int, temp: int = 0):
        """Set disk data"""
        self._sensor_data.disk_usage = min(100, max(0, usage))
        self._sensor_data.disk_temp = min(255, max(0, temp))
    
    def set_network_speed(self, upload: int, download: int):
        """Set network speed in bytes/sec"""
        self._sensor_data.net_upload = upload
        self._sensor_data.net_download = download
    
    def set_display_mode(self, mode: int):
        """Set display mode"""
        self._sensor_data.display_mode = mode
    
    def _build_gamdias_packet(self) -> bytes:
        """
        Build data packet for GAMDIAS ATLAS display
        
        Protocol from documentation:
        | Byte  | Description                    |
        |-------|--------------------------------|
        | 0     | Report ID (0xB0)               |
        | 1     | Command (0x01 = Dynamic Data)  |
        | 2     | Sub-command                    |
        | 3     | GPU Temperature                |
        | 4-5   | CPU Temperature (16-bit)       |
        | 6     | CPU Usage %                    |
        | 14-15 | CPU Frequency (MHz, big-endian)|
        | 16    | GPU Usage %                    |
        | 17-18 | GPU Frequency (MHz, big-endian)|
        """
        now = datetime.now()
        data = self._sensor_data
        
        packet = bytearray(self.REPORT_SIZE)
        
        # Header - following documented protocol
        packet[0] = 0xB0   # Report ID
        packet[1] = 0x01   # Command: Dynamic Data
        packet[2] = 0x00   # Sub-command
        
        # GPU Temperature (byte 3)
        packet[3] = data.gpu_temp
        
        # CPU Temperature (bytes 4-5, 16-bit little-endian)
        packet[4] = data.cpu_temp & 0xFF
        packet[5] = (data.cpu_temp >> 8) & 0xFF
        
        # CPU Usage % (byte 6)
        packet[6] = data.cpu_usage
        
        # Fan RPM (bytes 7-8 for CPU fan)
        packet[7] = data.cpu_fan_rpm & 0xFF
        packet[8] = (data.cpu_fan_rpm >> 8) & 0xFF
        
        # GPU Fan RPM (bytes 9-10)
        packet[9] = data.gpu_fan_rpm & 0xFF
        packet[10] = (data.gpu_fan_rpm >> 8) & 0xFF
        
        # GPU Power (bytes 11-12)
        packet[11] = data.gpu_power & 0xFF
        packet[12] = (data.gpu_power >> 8) & 0xFF
        
        # Reserved (byte 13)
        packet[13] = 0x00
        
        # CPU Frequency (bytes 14-15, big-endian per docs)
        packet[14] = (data.cpu_freq >> 8) & 0xFF
        packet[15] = data.cpu_freq & 0xFF
        
        # GPU Usage % (byte 16)
        packet[16] = data.gpu_usage
        
        # GPU Frequency (bytes 17-18, big-endian per docs)
        packet[17] = (data.gpu_freq >> 8) & 0xFF
        packet[18] = data.gpu_freq & 0xFF
        
        # Additional data
        packet[19] = now.hour
        packet[20] = now.minute
        packet[21] = now.second
        packet[22] = data.mem_usage
        packet[23] = data.disk_usage
        packet[24] = data.cpu_power & 0xFF
        packet[25] = (data.cpu_power >> 8) & 0xFF
        
        logger.debug(
            f"GAMDIAS: CPU {data.cpu_temp}°C {data.cpu_usage}% {data.cpu_freq}MHz | "
            f"GPU {data.gpu_temp}°C {data.gpu_usage}% {data.gpu_freq}MHz"
        )
        
        return bytes(packet)
    
    def _build_hwcx_packet(self) -> bytes:
        """Build data packet for HWCX controller"""
        now = datetime.now()
        data = self._sensor_data
        
        packet = bytearray(self.REPORT_SIZE)
        
        packet[0] = 0x00  # Report ID
        packet[1] = 0x02  # Command: update data
        packet[2] = data.cpu_temp
        packet[3] = data.gpu_temp
        packet[4] = now.hour
        packet[5] = now.minute
        packet[6] = now.second
        packet[7] = 0x00  # Extra
        
        # Date
        year = now.year
        packet[8] = (year >> 8) & 0xFF
        packet[9] = year & 0xFF
        packet[10] = now.month
        packet[11] = now.day
        packet[12] = now.weekday()
        
        # CPU
        packet[13] = data.cpu_usage
        packet[14] = (data.cpu_freq >> 8) & 0xFF
        packet[15] = data.cpu_freq & 0xFF
        
        # GPU
        packet[16] = data.gpu_usage
        packet[17] = (data.gpu_freq >> 8) & 0xFF
        packet[18] = data.gpu_freq & 0xFF
        
        # Memory
        packet[19] = data.mem_usage
        packet[20] = data.mem_temp
        packet[21] = 0x00  # mem_freq high
        packet[22] = 0x00  # mem_freq low
        
        # Disk
        packet[23] = data.disk_usage
        packet[24] = data.disk_temp
        
        # Fan RPM
        packet[25] = (data.cpu_fan_rpm >> 8) & 0xFF
        packet[26] = data.cpu_fan_rpm & 0xFF
        packet[27] = 0x00  # cpu_voltage high
        packet[28] = 0x00  # cpu_voltage low
        packet[29] = (data.cpu_power >> 8) & 0xFF
        packet[30] = data.cpu_power & 0xFF
        packet[31] = (data.gpu_fan_rpm >> 8) & 0xFF
        packet[32] = data.gpu_fan_rpm & 0xFF
        packet[33] = 0x00  # gpu_voltage high
        packet[34] = 0x00  # gpu_voltage low
        packet[35] = (data.gpu_power >> 8) & 0xFF
        packet[36] = data.gpu_power & 0xFF
        
        # Network
        packet[41] = (data.net_upload >> 24) & 0xFF
        packet[42] = (data.net_upload >> 16) & 0xFF
        packet[43] = (data.net_upload >> 8) & 0xFF
        packet[44] = data.net_upload & 0xFF
        packet[45] = (data.net_download >> 24) & 0xFF
        packet[46] = (data.net_download >> 16) & 0xFF
        packet[47] = (data.net_download >> 8) & 0xFF
        packet[48] = data.net_download & 0xFF
        
        packet[49] = data.display_mode
        
        return bytes(packet)
    
    def _send_gamdias_init(self, fd: int):
        """Send initialization sequence to GAMDIAS display"""
        # Try multiple init sequences for compatibility
        init_commands = [
            # Standard init
            bytes([0xB0, 0x01, 0x00]),
            # Wake/enable commands  
            bytes([0x00, 0x38, 0xB5, 0x01, 0x00]),
            bytes([0x00, 0x38, 0xB5, 0x01, 0x01]),
        ]
        
        for cmd in init_commands:
            packet = bytearray(self.REPORT_SIZE)
            packet[:len(cmd)] = cmd
            try:
                os.write(fd, bytes(packet))
                import time
                time.sleep(0.05)
            except Exception as e:
                logger.debug(f"Init command failed: {e}")
        
        self._log("GAMDIAS initialization complete")
    
    def send_data(self) -> bool:
        """Send sensor data to all connected devices"""
        if not self._devices:
            return False
        
        success = False
        to_remove = []
        
        for path, fd in self._devices.items():
            info = self._device_info.get(path)
            if not info:
                continue
            
            try:
                # Send init if not done yet
                if path not in self._initialized_devices:
                    if info.is_gamdias:
                        self._send_gamdias_init(fd)
                    self._initialized_devices.add(path)
                
                # Build appropriate packet
                if info.is_gamdias:
                    packet = self._build_gamdias_packet()
                else:
                    packet = self._build_hwcx_packet()
                
                # Send packet
                written = os.write(fd, packet)
                if written == len(packet):
                    success = True
                    logger.debug(f"Sent {written} bytes to {path}")
                else:
                    logger.warning(f"Partial write to {path}: {written}/{len(packet)}")
                    
            except OSError as e:
                if e.errno == 19:  # No such device
                    self._log(f"Device disconnected: {path}")
                    to_remove.append(path)
                else:
                    logger.error(f"Write error on {path}: {e}")
            except Exception as e:
                logger.error(f"Error sending to {path}: {e}")
        
        # Clean up disconnected devices
        for path in to_remove:
            try:
                os.close(self._devices[path])
            except:
                pass
            del self._devices[path]
            if path in self._device_info:
                del self._device_info[path]
            if path in self._initialized_devices:
                self._initialized_devices.remove(path)
        
        return success
    
    def __enter__(self):
        self.open_devices()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_devices()


# Test
if __name__ == "__main__":
    import time
    
    logging.basicConfig(level=logging.DEBUG)
    
    def log_cb(msg):
        print(f"[HID] {msg}")
    
    print("Scanning for HID devices...")
    print("Note: Run with sudo if devices are not found")
    print()
    
    hid = HidDevice(log_callback=log_cb)
    
    # Just scan without opening
    devices = hid.scan_devices()
    if not devices:
        print("\nNo supported devices found.")
        print("\nTroubleshooting:")
        print("1. Run with sudo: sudo python3 hid_device.py")
        print("2. Check if device is connected: lsusb | grep -i gamdias")
        print("3. Add udev rule for non-root access (see README)")
    else:
        print(f"\nFound {len(devices)} device(s)")
        
        # Try to open and send test data
        count = hid.open_devices()
        if count > 0:
            print(f"Opened {count} device(s)")
            
            # Set test data
            hid.set_cpu_data(temp=45, usage=25, freq=3500)
            hid.set_gpu_data(temp=55, usage=30, freq=1800, fan_rpm=1500, power=120)
            hid.set_memory_data(usage=60)
            
            print("Sending test data...")
            if hid.send_data():
                print("Data sent successfully!")
            else:
                print("Failed to send data")
            
            hid.close_devices()
