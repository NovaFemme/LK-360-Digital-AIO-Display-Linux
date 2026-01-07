#!/usr/bin/env python3
"""
Packet Format Tester for GAMDIAS Display
Tests different packet formats to find the correct byte positions for usage values.
Run with sudo.
"""

import os
import struct
import fcntl
import time
import sys
from pathlib import Path
from datetime import datetime

HIDIOCGRAWINFO = 0x80084803
REPORT_SIZE = 65

def find_device():
    """Find GAMDIAS device"""
    for path in sorted(Path("/dev").glob("hidraw*")):
        try:
            fd = os.open(str(path), os.O_RDWR | os.O_NONBLOCK)
            buf = bytearray(8)
            fcntl.ioctl(fd, HIDIOCGRAWINFO, buf)
            _, vid, pid = struct.unpack('Ihh', buf)
            vid = vid & 0xFFFF
            pid = pid & 0xFFFF
            os.close(fd)
            
            if vid == 0x1B80 and pid == 0xB538:
                return str(path)
        except:
            pass
    return None

def send_packet(fd, packet):
    """Send a packet to the device"""
    full_packet = bytearray(REPORT_SIZE)
    full_packet[:len(packet)] = packet
    os.write(fd, bytes(full_packet))

def test_format_1(fd):
    """Original C# format from the repository"""
    print("\n=== Format 1: Original C# format ===")
    print("packet[4]=usage, packet[5]=temp, packet[6-7]=freq")
    
    # Test values
    cpu_usage = 42
    cpu_temp = 55
    cpu_freq = 3500  # MHz
    gpu_usage = 37
    gpu_temp = 45
    gpu_freq = 1800  # MHz
    
    packet = bytearray(REPORT_SIZE)
    packet[0] = 0x00   # Report ID
    packet[1] = 0x38   # PID low
    packet[2] = 0xB5   # PID high
    packet[3] = 0x02   # Command
    
    packet[4] = cpu_usage
    packet[5] = cpu_temp
    packet[6] = cpu_freq & 0xFF
    packet[7] = (cpu_freq >> 8) & 0xFF
    
    packet[8] = gpu_usage
    packet[9] = gpu_temp
    packet[10] = gpu_freq & 0xFF
    packet[11] = (gpu_freq >> 8) & 0xFF
    
    print(f"  Sending: CPU {cpu_usage}% {cpu_temp}°C {cpu_freq}MHz | GPU {gpu_usage}% {gpu_temp}°C {gpu_freq}MHz")
    send_packet(fd, packet)
    return cpu_usage, gpu_usage

def test_format_2(fd):
    """README documented format"""
    print("\n=== Format 2: README documented format ===")
    print("packet[6]=cpu_usage, packet[14-15]=cpu_freq, packet[16]=gpu_usage")
    
    cpu_usage = 42
    cpu_temp = 55
    cpu_freq = 3500
    gpu_usage = 37
    gpu_temp = 45
    gpu_freq = 1800
    
    packet = bytearray(REPORT_SIZE)
    packet[0] = 0xB0   # Report ID
    packet[1] = 0x01   # Command
    packet[2] = 0x00   # Sub-command
    
    packet[3] = gpu_temp
    packet[4] = cpu_temp & 0xFF
    packet[5] = (cpu_temp >> 8) & 0xFF
    packet[6] = cpu_usage
    
    packet[14] = (cpu_freq >> 8) & 0xFF
    packet[15] = cpu_freq & 0xFF
    
    packet[16] = gpu_usage
    
    packet[17] = (gpu_freq >> 8) & 0xFF
    packet[18] = gpu_freq & 0xFF
    
    print(f"  Sending: CPU {cpu_usage}% {cpu_temp}°C {cpu_freq}MHz | GPU {gpu_usage}% {gpu_temp}°C {gpu_freq}MHz")
    send_packet(fd, packet)
    return cpu_usage, gpu_usage

def test_format_3(fd):
    """Swapped - usage in frequency position"""
    print("\n=== Format 3: Usage in frequency byte positions ===")
    print("packet[6-7]=cpu_usage, packet[4]=cpu_temp")
    
    cpu_usage = 42
    cpu_temp = 55
    cpu_freq = 3500
    gpu_usage = 37
    gpu_temp = 45
    gpu_freq = 1800
    
    packet = bytearray(REPORT_SIZE)
    packet[0] = 0x00
    packet[1] = 0x38
    packet[2] = 0xB5
    packet[3] = 0x02
    
    # Swap: put usage where freq was, freq where usage was
    packet[4] = cpu_temp
    packet[5] = cpu_freq & 0xFF        # Was usage position
    packet[6] = (cpu_freq >> 8) & 0xFF
    packet[7] = cpu_usage              # Was freq position
    
    packet[8] = gpu_temp
    packet[9] = gpu_freq & 0xFF
    packet[10] = (gpu_freq >> 8) & 0xFF
    packet[11] = gpu_usage
    
    print(f"  Sending: CPU {cpu_usage}% {cpu_temp}°C | GPU {gpu_usage}% {gpu_temp}°C")
    send_packet(fd, packet)
    return cpu_usage, gpu_usage

def test_format_4(fd):
    """Temperature and usage only (no frequency)"""
    print("\n=== Format 4: Simple temp+usage format ===")
    print("Minimal packet: temps and usage only")
    
    cpu_usage = 42
    cpu_temp = 55
    gpu_usage = 37
    gpu_temp = 45
    
    packet = bytearray(REPORT_SIZE)
    packet[0] = 0x00
    packet[1] = 0x02   # Simple data command
    
    packet[2] = cpu_temp
    packet[3] = gpu_temp
    
    now = datetime.now()
    packet[4] = now.hour
    packet[5] = now.minute
    packet[6] = now.second
    
    packet[13] = cpu_usage
    packet[16] = gpu_usage
    
    print(f"  Sending: CPU {cpu_usage}% {cpu_temp}°C | GPU {gpu_usage}% {gpu_temp}°C")
    send_packet(fd, packet)
    return cpu_usage, gpu_usage

def test_format_5(fd):
    """High usage values to be visible"""
    print("\n=== Format 5: High values for visibility ===")
    print("Using 88% usage, 77°C temp to make it obvious if values swap")
    
    cpu_usage = 88
    cpu_temp = 77
    cpu_freq = 4200
    gpu_usage = 66
    gpu_temp = 55
    gpu_freq = 2100
    
    packet = bytearray(REPORT_SIZE)
    packet[0] = 0x00
    packet[1] = 0x38
    packet[2] = 0xB5
    packet[3] = 0x02
    
    packet[4] = cpu_usage
    packet[5] = cpu_temp
    packet[6] = cpu_freq & 0xFF
    packet[7] = (cpu_freq >> 8) & 0xFF
    
    packet[8] = gpu_usage
    packet[9] = gpu_temp
    packet[10] = gpu_freq & 0xFF
    packet[11] = (gpu_freq >> 8) & 0xFF
    
    print(f"  Sending: CPU {cpu_usage}% {cpu_temp}°C {cpu_freq}MHz | GPU {gpu_usage}% {gpu_temp}°C {gpu_freq}MHz")
    print(f"  Look for: 88/77/4.20 on CPU line, 66/55/2.10 on GPU line")
    send_packet(fd, packet)
    return cpu_usage, gpu_usage


def main():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║     GAMDIAS Display Packet Format Tester                  ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    
    device = find_device()
    if not device:
        print("\nERROR: GAMDIAS device not found!")
        print("Make sure the display is connected and run with sudo.")
        return 1
    
    print(f"\nFound device: {device}")
    
    try:
        fd = os.open(device, os.O_RDWR)
    except PermissionError:
        print("ERROR: Permission denied. Run with sudo.")
        return 1
    
    formats = [
        ("1", test_format_1),
        ("2", test_format_2),
        ("3", test_format_3),
        ("4", test_format_4),
        ("5", test_format_5),
    ]
    
    print("\nThis will test different packet formats.")
    print("Watch your display and note which format shows usage correctly.")
    print("Press Enter after each test to continue, or 'q' to quit.\n")
    
    for name, func in formats:
        print("-" * 60)
        cpu_u, gpu_u = func(fd)
        print(f"\n  Expected on display: CPU usage={cpu_u}%, GPU usage={gpu_u}%")
        
        response = input("\n  Press Enter for next test (q=quit): ")
        if response.lower() == 'q':
            break
        time.sleep(0.5)
    
    os.close(fd)
    
    print("\n" + "=" * 60)
    print("Which format number showed the usage values correctly?")
    print("Please report back with the format number that worked.")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
