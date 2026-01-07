#!/usr/bin/env python3
"""
GAMDIAS Display Mode Tester
Tests different display mode commands to find one that shows usage % instead of GHz.
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

def send_data_packet(fd, cpu_temp=50, cpu_usage=75, gpu_temp=45, gpu_usage=60):
    """Send a data packet with fixed test values"""
    packet = bytearray(REPORT_SIZE)
    packet[0] = 0x00
    packet[1] = 0x38
    packet[2] = 0xB5
    packet[3] = 0x02
    
    # CPU - test with obvious values
    packet[4] = cpu_usage    # 75%
    packet[5] = cpu_temp     # 50°C
    packet[6] = 0xDC         # 3500 MHz low byte
    packet[7] = 0x0D         # 3500 MHz high byte
    
    # GPU
    packet[8] = gpu_usage    # 60%
    packet[9] = gpu_temp     # 45°C  
    packet[10] = 0x08        # 1800 MHz low byte
    packet[11] = 0x07        # 1800 MHz high byte
    
    send_packet(fd, packet)

def test_display_modes(fd):
    """Test different display mode commands"""
    print("\n=== Testing Display Mode Commands ===")
    print("Looking for a mode that shows usage % instead of GHz...")
    print("Watch your display for changes.\n")
    
    # Known command patterns from the original code
    mode_commands = [
        # (description, command bytes)
        ("Mode 0 - Default", [0x00, 0x38, 0xB5, 0x03, 0x00]),
        ("Mode 1 - Alt 1", [0x00, 0x38, 0xB5, 0x03, 0x01]),
        ("Mode 2 - Alt 2", [0x00, 0x38, 0xB5, 0x03, 0x02]),
        ("Mode 3 - Alt 3", [0x00, 0x38, 0xB5, 0x03, 0x03]),
        ("Mode 4 - Alt 4", [0x00, 0x38, 0xB5, 0x03, 0x04]),
        ("Display Mode 0", [0xB0, 0x03, 0x00]),
        ("Display Mode 1", [0xB0, 0x03, 0x01]),
        ("Display Mode 2", [0xB0, 0x03, 0x02]),
        ("Set View 0", [0x00, 0x38, 0xB5, 0x04, 0x00]),
        ("Set View 1", [0x00, 0x38, 0xB5, 0x04, 0x01]),
        ("Set View 2", [0x00, 0x38, 0xB5, 0x04, 0x02]),
        ("Config 0", [0x00, 0x38, 0xB5, 0x05, 0x00]),
        ("Config 1", [0x00, 0x38, 0xB5, 0x05, 0x01]),
    ]
    
    for desc, cmd in mode_commands:
        print(f"Testing: {desc}")
        print(f"  Command: {' '.join(f'{b:02X}' for b in cmd)}")
        
        # Send mode command
        send_packet(fd, bytes(cmd))
        time.sleep(0.2)
        
        # Send data to see effect
        send_data_packet(fd, cpu_temp=50, cpu_usage=75, gpu_temp=45, gpu_usage=60)
        
        response = input("  Did display change to show % instead of GHz? (y/n/q): ")
        if response.lower() == 'y':
            print(f"\n*** SUCCESS! Mode command: {cmd} ***\n")
            return cmd
        elif response.lower() == 'q':
            break
        
        time.sleep(0.3)
    
    return None

def test_packet_byte27_modes(fd):
    """Test different values in the display mode byte (27) of data packets"""
    print("\n=== Testing Data Packet Display Mode Byte ===")
    print("Testing byte 27 (display mode) with different values...\n")
    
    for mode in range(0, 16):
        print(f"Testing display_mode = {mode} (0x{mode:02X})")
        
        packet = bytearray(REPORT_SIZE)
        packet[0] = 0x00
        packet[1] = 0x38
        packet[2] = 0xB5
        packet[3] = 0x02
        
        # Test values - use distinctive numbers
        packet[4] = 75       # CPU usage 75%
        packet[5] = 50       # CPU temp 50°C
        packet[6] = 0xDC     # 3500 MHz
        packet[7] = 0x0D
        
        packet[8] = 60       # GPU usage 60%
        packet[9] = 45       # GPU temp 45°C
        packet[10] = 0x08    # 1800 MHz
        packet[11] = 0x07
        
        packet[27] = mode    # Display mode byte
        packet[28] = 0x01    # Enable flag
        
        send_packet(fd, bytes(packet))
        
        response = input(f"  Mode {mode}: Did it change to show 75% / 60%? (y/n/q): ")
        if response.lower() == 'y':
            print(f"\n*** SUCCESS! Display mode byte = {mode} ***\n")
            return mode
        elif response.lower() == 'q':
            break
        
        time.sleep(0.2)
    
    return None

def test_usage_in_freq_position(fd):
    """Test sending usage value in the frequency byte position"""
    print("\n=== Testing Usage Value in Frequency Position ===")
    print("This sends usage % scaled as a pseudo-frequency.\n")
    
    # The display shows X.XX GHz format
    # If we send usage*100, 75% becomes 7500 = 7.50 "GHz" displayed
    # If we send usage*10, 75% becomes 750 = 0.75 "GHz" displayed
    
    test_cases = [
        ("Usage as-is (75 = 0.07 GHz)", 75, 60),
        ("Usage * 10 (750 = 0.75 GHz)", 750, 600),
        ("Usage * 100 (7500 = 7.50 GHz)", 7500, 6000),
        ("Usage scaled (75% = 75 in upper display)", 75, 60),
    ]
    
    for desc, cpu_freq_val, gpu_freq_val in test_cases:
        print(f"Testing: {desc}")
        
        packet = bytearray(REPORT_SIZE)
        packet[0] = 0x00
        packet[1] = 0x38
        packet[2] = 0xB5
        packet[3] = 0x02
        
        packet[4] = 75       # CPU usage (ignored for freq display)
        packet[5] = 50       # CPU temp
        packet[6] = cpu_freq_val & 0xFF
        packet[7] = (cpu_freq_val >> 8) & 0xFF
        
        packet[8] = 60       # GPU usage (ignored for freq display)  
        packet[9] = 45       # GPU temp
        packet[10] = gpu_freq_val & 0xFF
        packet[11] = (gpu_freq_val >> 8) & 0xFF
        
        send_packet(fd, bytes(packet))
        print(f"  Sent CPU freq={cpu_freq_val}, GPU freq={gpu_freq_val}")
        
        response = input("  What does display show? (type value or 'n' for next, 'q' quit): ")
        if response.lower() == 'q':
            break
        
        time.sleep(0.3)

def main():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║     GAMDIAS Display Mode Finder                          ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    print("Your display is showing frequency (GHz) instead of usage (%).")
    print("This tool will try to find the command to switch display modes.")
    
    device = find_device()
    if not device:
        print("\nERROR: GAMDIAS device not found!")
        return 1
    
    print(f"\nFound device: {device}")
    
    try:
        fd = os.open(device, os.O_RDWR)
    except PermissionError:
        print("ERROR: Permission denied. Run with sudo.")
        return 1
    
    print("\nOptions:")
    print("  1. Test display mode commands")
    print("  2. Test data packet mode byte")
    print("  3. Test usage in frequency position (workaround)")
    print("  4. Run all tests")
    print("  q. Quit")
    
    choice = input("\nChoice: ").strip()
    
    if choice == '1':
        test_display_modes(fd)
    elif choice == '2':
        test_packet_byte27_modes(fd)
    elif choice == '3':
        test_usage_in_freq_position(fd)
    elif choice == '4':
        result = test_display_modes(fd)
        if not result:
            result = test_packet_byte27_modes(fd)
        if not result:
            test_usage_in_freq_position(fd)
    
    os.close(fd)
    
    print("\n" + "=" * 60)
    print("If no mode worked, your display may only support frequency view.")
    print("Workaround: We can send usage% as a scaled value in freq position.")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
