#!/usr/bin/env python3
"""
Hardware Monitor for Linux
Reads CPU and GPU sensor data using native Linux interfaces.
No Wine, LibreHardwareMonitor, or HWiNFO dependencies.

Supported:
- CPU: lm-sensors via /sys/class/hwmon/, /proc/stat
- GPU: NVIDIA (nvidia-smi), AMD (amdgpu sysfs), Intel (i915 sysfs)
"""

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Callable
import logging

logger = logging.getLogger(__name__)


@dataclass
class CpuData:
    name: str = ""
    temperature: float = 0.0
    usage: float = 0.0
    frequency: float = 0.0  # MHz
    power: float = 0.0  # Watts
    fan_rpm: int = 0
    is_valid: bool = False


@dataclass
class GpuData:
    name: str = ""
    temperature: float = 0.0
    usage: float = 0.0
    frequency: float = 0.0  # MHz
    memory_usage: float = 0.0
    fan_rpm: int = 0
    power: float = 0.0  # Watts
    vendor: str = ""  # nvidia, amd, intel
    is_valid: bool = False


class CpuUsageTracker:
    """Track CPU usage using /proc/stat"""
    
    def __init__(self):
        self._last_idle = 0
        self._last_total = 0
        self._initialized = False
        # Initialize with current values
        self._init_values()
    
    def _init_values(self):
        """Initialize with current CPU values"""
        try:
            with open('/proc/stat', 'r') as f:
                line = f.readline()
            parts = line.split()
            self._last_idle = int(parts[4]) + int(parts[5])
            self._last_total = sum(int(p) for p in parts[1:11])  # Only first 10 values
            self._initialized = True
        except Exception:
            pass
    
    def get_usage(self) -> float:
        try:
            with open('/proc/stat', 'r') as f:
                line = f.readline()
            
            parts = line.split()
            # cpu user nice system idle iowait irq softirq steal guest guest_nice
            # Only use first 10 fields for consistency
            idle = int(parts[4]) + int(parts[5])  # idle + iowait
            total = sum(int(p) for p in parts[1:11])
            
            if not self._initialized:
                self._last_idle = idle
                self._last_total = total
                self._initialized = True
                return 0.0
            
            idle_delta = idle - self._last_idle
            total_delta = total - self._last_total
            
            self._last_idle = idle
            self._last_total = total
            
            if total_delta <= 0:
                return 0.0
            
            usage = 100.0 * (1.0 - idle_delta / total_delta)
            return max(0.0, min(100.0, usage))
        except Exception as e:
            logger.debug(f"Failed to read CPU usage: {e}")
            return 0.0


class HardwareMonitor:
    """Main hardware monitoring class for Linux"""
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self.log_callback = log_callback or (lambda x: None)
        self._cpu_usage_tracker = CpuUsageTracker()
        self._hwmon_cache: Dict[str, Path] = {}
        self._gpu_vendor: Optional[str] = None
        self._nvidia_available = self._check_nvidia()
        self._amd_gpu_path: Optional[Path] = None
        self._intel_gpu_path: Optional[Path] = None
        
        self._detect_gpu()
        self._scan_hwmon()
    
    def _log(self, msg: str):
        logger.info(msg)
        self.log_callback(msg)
    
    def _check_nvidia(self) -> bool:
        """Check if nvidia-smi is available"""
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def _detect_gpu(self):
        """Detect which GPU is present"""
        # Check for NVIDIA first
        if self._nvidia_available:
            self._gpu_vendor = "nvidia"
            self._log("Detected NVIDIA GPU (nvidia-smi available)")
            return
        
        # Check for AMD GPU via DRM
        drm_path = Path("/sys/class/drm")
        if drm_path.exists():
            for card in drm_path.iterdir():
                if not card.name.startswith("card") or "-" in card.name:
                    continue
                device_path = card / "device"
                if not device_path.exists():
                    continue
                
                # Check vendor
                vendor_file = device_path / "vendor"
                if vendor_file.exists():
                    vendor = vendor_file.read_text().strip()
                    if vendor == "0x1002":  # AMD
                        # Find hwmon for this device
                        hwmon_path = device_path / "hwmon"
                        if hwmon_path.exists():
                            for hwmon in hwmon_path.iterdir():
                                self._amd_gpu_path = hwmon
                                self._gpu_vendor = "amd"
                                self._log(f"Detected AMD GPU at {hwmon}")
                                return
                    elif vendor == "0x8086":  # Intel
                        self._intel_gpu_path = device_path
                        self._gpu_vendor = "intel"
                        self._log(f"Detected Intel GPU at {device_path}")
                        return
        
        self._log("No discrete GPU detected")
    
    def _scan_hwmon(self):
        """Scan /sys/class/hwmon for sensor devices"""
        hwmon_base = Path("/sys/class/hwmon")
        if not hwmon_base.exists():
            self._log("Warning: /sys/class/hwmon not found")
            return
        
        for hwmon in hwmon_base.iterdir():
            name_file = hwmon / "name"
            if name_file.exists():
                name = name_file.read_text().strip()
                self._hwmon_cache[name] = hwmon
                self._log(f"Found hwmon device: {name} at {hwmon}")
    
    def _read_sysfs_value(self, path: Path) -> Optional[float]:
        """Read a numeric value from a sysfs file"""
        try:
            if path.exists():
                value = path.read_text().strip()
                return float(value)
        except (ValueError, PermissionError, OSError) as e:
            logger.debug(f"Failed to read {path}: {e}")
        return None
    
    def _find_cpu_temp_hwmon(self) -> Optional[Path]:
        """Find the hwmon device for CPU temperature"""
        # Priority order for CPU temp sensors
        cpu_sensors = ['coretemp', 'k10temp', 'zenpower', 'it87', 'nct6775', 'acpitz']
        
        for sensor in cpu_sensors:
            if sensor in self._hwmon_cache:
                return self._hwmon_cache[sensor]
        
        # Fallback: look for any temp1_input
        for name, path in self._hwmon_cache.items():
            if (path / "temp1_input").exists():
                return path
        
        return None
    
    def get_cpu_data(self) -> CpuData:
        """Get CPU sensor data"""
        data = CpuData()
        
        # Get CPU name
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('model name'):
                        data.name = line.split(':')[1].strip()
                        break
        except Exception:
            data.name = "Unknown CPU"
        
        # Get CPU usage
        data.usage = self._cpu_usage_tracker.get_usage()
        if data.usage > 0:
            data.is_valid = True
        
        # Get CPU frequency (average of all cores)
        try:
            freq_path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
            if freq_path.exists():
                # Value is in kHz, convert to MHz
                freq_khz = float(freq_path.read_text().strip())
                data.frequency = freq_khz / 1000.0
        except Exception as e:
            logger.debug(f"Failed to read CPU frequency: {e}")
        
        # Get CPU temperature
        hwmon = self._find_cpu_temp_hwmon()
        if hwmon:
            # Try different temp inputs (temp1 is usually package temp)
            for i in range(1, 10):
                temp_file = hwmon / f"temp{i}_input"
                label_file = hwmon / f"temp{i}_label"
                
                if temp_file.exists():
                    temp = self._read_sysfs_value(temp_file)
                    if temp is not None:
                        # Convert from millidegrees to degrees
                        temp_c = temp / 1000.0
                        
                        # Check label to prefer package/Tctl temp
                        label = ""
                        if label_file.exists():
                            try:
                                label = label_file.read_text().strip().lower()
                            except:
                                pass
                        
                        if 'package' in label or 'tctl' in label or 'tdie' in label:
                            data.temperature = temp_c
                            data.is_valid = True
                            break
                        elif data.temperature == 0:
                            data.temperature = temp_c
                            data.is_valid = True
        
        # Try to get CPU power from RAPL
        rapl_path = Path("/sys/class/powercap/intel-rapl:0/energy_uj")
        if rapl_path.exists():
            # Would need to track over time for power calculation
            # For now, skip this
            pass
        
        return data
    
    def get_gpu_data(self) -> GpuData:
        """Get GPU sensor data"""
        if self._gpu_vendor == "nvidia":
            return self._get_nvidia_gpu_data()
        elif self._gpu_vendor == "amd":
            return self._get_amd_gpu_data()
        elif self._gpu_vendor == "intel":
            return self._get_intel_gpu_data()
        else:
            return GpuData()
    
    def _get_nvidia_gpu_data(self) -> GpuData:
        """Get NVIDIA GPU data using nvidia-smi"""
        data = GpuData(vendor="nvidia")
        
        try:
            # Query all needed values in one call
            result = subprocess.run(
                [
                    'nvidia-smi',
                    '--query-gpu=name,temperature.gpu,utilization.gpu,clocks.gr,memory.used,memory.total,fan.speed,power.draw',
                    '--format=csv,noheader,nounits'
                ],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                parts = [p.strip() for p in result.stdout.strip().split(',')]
                if len(parts) >= 8:
                    data.name = parts[0]
                    data.temperature = float(parts[1]) if parts[1] != '[N/A]' else 0
                    data.usage = float(parts[2]) if parts[2] != '[N/A]' else 0
                    data.frequency = float(parts[3]) if parts[3] != '[N/A]' else 0
                    
                    mem_used = float(parts[4]) if parts[4] != '[N/A]' else 0
                    mem_total = float(parts[5]) if parts[5] != '[N/A]' else 1
                    data.memory_usage = (mem_used / mem_total) * 100 if mem_total > 0 else 0
                    
                    fan_str = parts[6]
                    if fan_str != '[N/A]':
                        # Fan speed is in %, estimate RPM (typical max ~3000)
                        data.fan_rpm = int(float(fan_str) * 30)
                    
                    data.power = float(parts[7]) if parts[7] != '[N/A]' else 0
                    data.is_valid = True
                    
        except Exception as e:
            logger.debug(f"nvidia-smi failed: {e}")
        
        return data
    
    def _get_amd_gpu_data(self) -> GpuData:
        """Get AMD GPU data from sysfs"""
        data = GpuData(vendor="amd")
        
        if not self._amd_gpu_path:
            return data
        
        hwmon = self._amd_gpu_path
        device_path = hwmon.parent.parent
        
        # GPU Name - try to get from device
        try:
            name_file = device_path / "product_name"
            if name_file.exists():
                data.name = name_file.read_text().strip()
            else:
                # Try to get from marketing name via uevent
                uevent_file = device_path / "uevent"
                if uevent_file.exists():
                    content = uevent_file.read_text()
                    for line in content.split('\n'):
                        if 'DRIVER=' in line:
                            data.name = "AMD Radeon GPU"
                            break
                else:
                    data.name = "AMD Radeon GPU"
        except:
            data.name = "AMD Radeon GPU"
        
        # Temperature - AMD GPUs often have edge, junction, and memory temps
        for i in range(1, 10):
            temp_file = hwmon / f"temp{i}_input"
            label_file = hwmon / f"temp{i}_label"
            
            if temp_file.exists():
                temp = self._read_sysfs_value(temp_file)
                if temp is not None:
                    temp_c = temp / 1000.0
                    
                    label = ""
                    if label_file.exists():
                        try:
                            label = label_file.read_text().strip().lower()
                        except:
                            pass
                    
                    # Prefer edge temperature
                    if 'edge' in label:
                        data.temperature = temp_c
                        data.is_valid = True
                        break
                    elif data.temperature == 0:
                        data.temperature = temp_c
                        data.is_valid = True
        
        # GPU Usage - Try multiple methods
        usage_found = False
        
        # Method 1: gpu_busy_percent in device path
        busy_file = device_path / "gpu_busy_percent"
        if busy_file.exists():
            usage = self._read_sysfs_value(busy_file)
            if usage is not None:
                data.usage = usage
                data.is_valid = True
                usage_found = True
                logger.debug(f"AMD GPU usage from gpu_busy_percent: {usage}%")
        
        # Method 2: Check in /sys/class/drm/card*/device/
        if not usage_found:
            for card_path in Path("/sys/class/drm").glob("card[0-9]"):
                busy_file = card_path / "device" / "gpu_busy_percent"
                if busy_file.exists():
                    usage = self._read_sysfs_value(busy_file)
                    if usage is not None:
                        data.usage = usage
                        data.is_valid = True
                        usage_found = True
                        logger.debug(f"AMD GPU usage from {busy_file}: {usage}%")
                        break
        
        # Method 3: Try reading from hwmon power usage as activity indicator
        if not usage_found:
            # Some AMD GPUs expose activity through different means
            # Check for any gpu activity sensor
            for f in hwmon.glob("*"):
                fname = f.name.lower()
                if 'activity' in fname or 'busy' in fname:
                    val = self._read_sysfs_value(f)
                    if val is not None:
                        data.usage = val
                        usage_found = True
                        logger.debug(f"AMD GPU usage from {f}: {val}%")
                        break
        
        # GPU Frequency
        freq_file = device_path / "pp_dpm_sclk"
        if freq_file.exists():
            try:
                content = freq_file.read_text()
                # Format: "0: 500Mhz\n1: 800Mhz *\n..."
                # The active one has *
                for line in content.split('\n'):
                    if '*' in line:
                        match = re.search(r'(\d+)\s*[Mm][Hh]z', line)
                        if match:
                            data.frequency = float(match.group(1))
                        break
            except Exception as e:
                self._log(f"Failed to read GPU frequency: {e}")
        
        # Alternative frequency source
        if data.frequency == 0:
            freq_file = hwmon / "freq1_input"
            if freq_file.exists():
                freq = self._read_sysfs_value(freq_file)
                if freq is not None:
                    # freq1_input is in Hz, convert to MHz
                    data.frequency = freq / 1000000.0
        
        # Fan RPM
        for i in range(1, 5):
            fan_file = hwmon / f"fan{i}_input"
            if fan_file.exists():
                rpm = self._read_sysfs_value(fan_file)
                if rpm is not None:
                    data.fan_rpm = int(rpm)
                    break
        
        # Power
        power_file = hwmon / "power1_average"
        if power_file.exists():
            power = self._read_sysfs_value(power_file)
            if power is not None:
                # Value is in microwatts
                data.power = power / 1000000.0
        
        # Alternative power source
        if data.power == 0:
            power_file = hwmon / "power1_input"
            if power_file.exists():
                power = self._read_sysfs_value(power_file)
                if power is not None:
                    data.power = power / 1000000.0
        
        return data
    
    def _get_intel_gpu_data(self) -> GpuData:
        """Get Intel GPU data from sysfs"""
        data = GpuData(vendor="intel", name="Intel Graphics")
        
        if not self._intel_gpu_path:
            return data
        
        # Intel GPU frequency
        freq_file = self._intel_gpu_path / "gt_cur_freq_mhz"
        if freq_file.exists():
            freq = self._read_sysfs_value(freq_file)
            if freq is not None:
                data.frequency = freq
                data.is_valid = True
        
        # Intel GPU temperature (if available via hwmon)
        hwmon_path = self._intel_gpu_path / "hwmon"
        if hwmon_path.exists():
            for hwmon in hwmon_path.iterdir():
                temp_file = hwmon / "temp1_input"
                if temp_file.exists():
                    temp = self._read_sysfs_value(temp_file)
                    if temp is not None:
                        data.temperature = temp / 1000.0
                        data.is_valid = True
                        break
        
        # GPU usage via perf events would require more complex handling
        # For now, we'll leave usage at 0 for Intel integrated GPUs
        
        return data


# Simple test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    def log_cb(msg):
        print(f"[Monitor] {msg}")
    
    monitor = HardwareMonitor(log_callback=log_cb)
    
    print("\n--- CPU Data ---")
    # Need a delay for accurate CPU usage
    time.sleep(0.5)
    cpu = monitor.get_cpu_data()
    print(f"Name: {cpu.name}")
    print(f"Temperature: {cpu.temperature:.1f}°C")
    print(f"Usage: {cpu.usage:.1f}%")
    print(f"Frequency: {cpu.frequency:.0f} MHz")
    print(f"Valid: {cpu.is_valid}")
    
    print("\n--- GPU Data ---")
    gpu = monitor.get_gpu_data()
    print(f"Name: {gpu.name}")
    print(f"Vendor: {gpu.vendor}")
    print(f"Temperature: {gpu.temperature:.1f}°C")
    print(f"Usage: {gpu.usage:.1f}%")
    print(f"Frequency: {gpu.frequency:.0f} MHz")
    print(f"Fan RPM: {gpu.fan_rpm}")
    print(f"Power: {gpu.power:.1f}W")
    print(f"Valid: {gpu.is_valid}")
