#!/usr/bin/env python3
"""
LK Display Diagnostic Tool
Scans system for all available hardware sensors and shows their current values.
Helps troubleshoot missing CPU/GPU usage readings.
"""

import os
import subprocess
from pathlib import Path


def print_header(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)


def read_file(path):
    """Safely read a file"""
    try:
        return Path(path).read_text().strip()
    except:
        return None


def scan_proc_stat():
    """Show CPU usage calculation"""
    print_header("CPU USAGE (/proc/stat)")
    try:
        with open('/proc/stat', 'r') as f:
            line = f.readline()
        parts = line.split()
        print(f"Raw: {line.strip()[:80]}...")
        
        user = int(parts[1])
        nice = int(parts[2])
        system = int(parts[3])
        idle = int(parts[4])
        iowait = int(parts[5])
        
        total = user + nice + system + idle + iowait
        usage = 100.0 * (total - idle - iowait) / total
        
        print(f"Calculated overall usage: {usage:.1f}%")
        print("(Note: This is cumulative since boot, real-time needs delta calculation)")
    except Exception as e:
        print(f"Error: {e}")


def scan_hwmon():
    """Scan all hwmon devices"""
    print_header("HWMON SENSORS (/sys/class/hwmon)")
    
    hwmon_base = Path("/sys/class/hwmon")
    if not hwmon_base.exists():
        print("ERROR: /sys/class/hwmon not found!")
        return
    
    for hwmon in sorted(hwmon_base.iterdir()):
        name_file = hwmon / "name"
        name = read_file(name_file) or "unknown"
        print(f"\n[{hwmon.name}] {name}")
        
        # Show temperatures
        for i in range(1, 10):
            temp_file = hwmon / f"temp{i}_input"
            label_file = hwmon / f"temp{i}_label"
            if temp_file.exists():
                temp = read_file(temp_file)
                label = read_file(label_file) or f"temp{i}"
                if temp:
                    print(f"  {label}: {int(temp)/1000:.1f}°C")
        
        # Show fans
        for i in range(1, 5):
            fan_file = hwmon / f"fan{i}_input"
            if fan_file.exists():
                rpm = read_file(fan_file)
                if rpm:
                    print(f"  fan{i}: {rpm} RPM")
        
        # Show power
        for suffix in ['average', 'input']:
            power_file = hwmon / f"power1_{suffix}"
            if power_file.exists():
                power = read_file(power_file)
                if power:
                    print(f"  power1_{suffix}: {int(power)/1000000:.1f}W")


def scan_drm():
    """Scan DRM devices for GPU info"""
    print_header("GPU DRM DEVICES (/sys/class/drm)")
    
    drm_base = Path("/sys/class/drm")
    if not drm_base.exists():
        print("ERROR: /sys/class/drm not found!")
        return
    
    for card in sorted(drm_base.glob("card[0-9]")):
        device = card / "device"
        if not device.exists():
            continue
        
        vendor = read_file(device / "vendor") or "unknown"
        device_id = read_file(device / "device") or "unknown"
        
        vendor_name = {
            "0x1002": "AMD",
            "0x10de": "NVIDIA", 
            "0x8086": "Intel"
        }.get(vendor, vendor)
        
        print(f"\n[{card.name}] Vendor: {vendor_name} ({vendor}), Device: {device_id}")
        
        # GPU busy percent (AMD)
        busy_file = device / "gpu_busy_percent"
        if busy_file.exists():
            busy = read_file(busy_file)
            print(f"  gpu_busy_percent: {busy}%")
        else:
            print(f"  gpu_busy_percent: NOT FOUND at {busy_file}")
        
        # Power profile
        pp_file = device / "pp_dpm_sclk"
        if pp_file.exists():
            content = read_file(pp_file)
            if content:
                for line in content.split('\n'):
                    if '*' in line:
                        print(f"  Active GPU clock: {line.strip()}")
                        break
        
        # Check hwmon under device
        hwmon_path = device / "hwmon"
        if hwmon_path.exists():
            print(f"  hwmon path: {hwmon_path}")
            for hwmon in hwmon_path.iterdir():
                print(f"    -> {hwmon}")


def check_nvidia():
    """Check NVIDIA GPU via nvidia-smi"""
    print_header("NVIDIA GPU (nvidia-smi)")
    
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,temperature.gpu,utilization.gpu,clocks.gr,power.draw',
             '--format=csv,noheader'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            print(f"nvidia-smi output: {result.stdout.strip()}")
        else:
            print(f"nvidia-smi error: {result.stderr}")
    except FileNotFoundError:
        print("nvidia-smi not found (NVIDIA driver not installed or not an NVIDIA GPU)")
    except Exception as e:
        print(f"Error: {e}")


def scan_cpu_freq():
    """Check CPU frequency"""
    print_header("CPU FREQUENCY")
    
    cpu_base = Path("/sys/devices/system/cpu")
    for cpu in sorted(cpu_base.glob("cpu[0-9]*")):
        freq_file = cpu / "cpufreq" / "scaling_cur_freq"
        if freq_file.exists():
            freq = read_file(freq_file)
            if freq:
                print(f"  {cpu.name}: {int(freq)/1000:.0f} MHz")
            break  # Just show first CPU


def scan_memory():
    """Check memory usage"""
    print_header("MEMORY (/proc/meminfo)")
    
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
            usage = 100 * (mem_total - mem_available) / mem_total
            print(f"  Total: {mem_total/1024/1024:.1f} GB")
            print(f"  Available: {mem_available/1024/1024:.1f} GB")
            print(f"  Usage: {usage:.1f}%")
    except Exception as e:
        print(f"Error: {e}")


def check_permissions():
    """Check if we can read sensor files"""
    print_header("PERMISSION CHECK")
    
    test_files = [
        "/sys/class/hwmon/hwmon0/temp1_input",
        "/sys/class/drm/card0/device/gpu_busy_percent",
        "/proc/stat",
        "/dev/hidraw0"
    ]
    
    for f in test_files:
        path = Path(f)
        if path.exists():
            try:
                if path.is_file():
                    path.read_text()
                print(f"  ✓ {f} - readable")
            except PermissionError:
                print(f"  ✗ {f} - PERMISSION DENIED")
            except Exception as e:
                print(f"  ? {f} - {e}")
        else:
            print(f"  - {f} - does not exist")


def main():
    print("╔════════════════════════════════════════════════════════════╗")
    print("║        LK Display - Hardware Sensor Diagnostic Tool       ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    scan_proc_stat()
    scan_cpu_freq()
    scan_memory()
    scan_hwmon()
    scan_drm()
    check_nvidia()
    check_permissions()
    
    print_header("SUMMARY")
    print("""
If CPU usage shows 0:
  - This is normal on first reading (needs time delta)
  - The service should show correct values after a few seconds

If GPU usage shows 0 or missing:
  - AMD: Check if gpu_busy_percent exists in DRM section above
  - NVIDIA: Check if nvidia-smi works
  - Intel: Integrated GPUs may not report usage

If permission errors:
  - Run with sudo, or
  - Install udev rules: sudo cp 99-lk-display.rules /etc/udev/rules.d/
  
To test the monitor directly:
  sudo python3 hardware_monitor.py
""")


if __name__ == "__main__":
    main()
