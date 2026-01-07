#!/usr/bin/env python3
"""
Configuration handling for LK Digital Display
"""

import configparser
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Application configuration"""
    
    # Timing
    refresh_delay: int = 500  # ms
    send_delay: int = 500  # ms (not used in Linux version, kept for compatibility)
    
    # Logging
    log_enabled: bool = True
    log_path: str = ""  # Empty = use default (app directory)
    debug: bool = False
    
    # Network (UDP server, optional)
    udp_enabled: bool = False
    udp_port: int = 8890
    
    def load(self, path: str) -> bool:
        """Load configuration from INI file"""
        config = configparser.ConfigParser()
        
        try:
            config.read(path)
            
            if 'config' in config:
                section = config['config']
                
                # Timing - note: original has typo "fefresh_delay"
                if 'refresh_delay' in section:
                    self.refresh_delay = int(section['refresh_delay'])
                elif 'fefresh_delay' in section:  # Handle original typo
                    self.refresh_delay = int(section['fefresh_delay'])
                
                if 'send_delay' in section:
                    self.send_delay = int(section['send_delay'])
                
                # Logging
                if 'IsLog' in section:
                    self.log_enabled = section['IsLog'].lower() == 'true'
                
                if 'LogPath' in section:
                    self.log_path = section['LogPath']
                
                if 'Debug' in section:
                    self.debug = section['Debug'].lower() == 'true'
                
                # Network
                if 'IsUdp' in section:
                    self.udp_enabled = section['IsUdp'].lower() == 'true'
                
                if 'localPort' in section:
                    self.udp_port = int(section['localPort'])
            
            return True
            
        except Exception as e:
            print(f"Error loading config: {e}")
            return False
    
    def save(self, path: str) -> bool:
        """Save configuration to INI file"""
        config = configparser.ConfigParser()
        config['config'] = {
            'refresh_delay': str(self.refresh_delay),
            'send_delay': str(self.send_delay),
            'IsLog': str(self.log_enabled),
            'LogPath': self.log_path,
            'Debug': str(self.debug),
            'IsUdp': str(self.udp_enabled),
            'localPort': str(self.udp_port),
        }
        
        try:
            with open(path, 'w') as f:
                config.write(f)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False


def create_default_config(path: str = "config.ini"):
    """Create a default configuration file"""
    config = Config()
    config.save(path)
    print(f"Created default config at {path}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "create":
        create_default_config()
    else:
        print("Usage: python3 config.py create")
        print("  Creates a default config.ini file")
