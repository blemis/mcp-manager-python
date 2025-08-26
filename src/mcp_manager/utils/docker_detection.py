"""
Docker Desktop detection utilities for MCP Manager.

Provides robust detection of Docker Desktop availability to gracefully handle
DD-specific MCP servers when Docker Desktop is not installed.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from functools import lru_cache

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DockerDesktopDetector:
    """Detects Docker Desktop availability and provides graceful fallbacks."""
    
    # Cache detection results for performance
    _detection_cache: Optional[Dict[str, Any]] = None
    
    @classmethod
    @lru_cache(maxsize=1)
    def is_docker_desktop_available(cls) -> bool:
        """
        Check if Docker Desktop is installed and available.
        
        Returns:
            True if Docker Desktop is available, False otherwise
        """
        try:
            # Check 1: Docker Desktop MCP plugin exists
            mcp_plugin_path = Path("/Applications/Docker.app/Contents/Resources/cli-plugins/docker-mcp")
            if not mcp_plugin_path.exists():
                logger.debug("Docker Desktop MCP plugin not found")
                return False
            
            # Check 2: Docker MCP command works
            result = subprocess.run(
                ["docker", "mcp", "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                logger.debug(f"Docker Desktop MCP available: {result.stdout.strip()}")
                return True
            else:
                logger.debug(f"Docker MCP command failed: {result.stderr}")
                return False
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.debug(f"Docker Desktop detection failed: {e}")
            return False
    
    @classmethod
    def get_detection_info(cls) -> Dict[str, Any]:
        """
        Get detailed Docker Desktop detection information.
        
        Returns:
            Dictionary with detection details
        """
        if cls._detection_cache is not None:
            return cls._detection_cache
        
        info = {
            "available": False,
            "version": None,
            "mcp_plugin_path": None,
            "docker_app_path": None,
            "fallback_message": None
        }
        
        try:
            # Check Docker Desktop app
            docker_app = Path("/Applications/Docker.app")
            info["docker_app_path"] = str(docker_app) if docker_app.exists() else None
            
            # Check MCP plugin
            mcp_plugin = Path("/Applications/Docker.app/Contents/Resources/cli-plugins/docker-mcp")
            info["mcp_plugin_path"] = str(mcp_plugin) if mcp_plugin.exists() else None
            
            # Check if commands work
            if mcp_plugin.exists():
                try:
                    result = subprocess.run(
                        ["docker", "mcp", "version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        info["available"] = True
                        info["version"] = result.stdout.strip()
                    else:
                        info["fallback_message"] = "Docker Desktop installed but MCP commands not working"
                        
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    info["fallback_message"] = "Docker Desktop installed but not running"
            else:
                info["fallback_message"] = "Docker Desktop not installed"
        
        except Exception as e:
            logger.error(f"Error during Docker Desktop detection: {e}")
            info["fallback_message"] = f"Detection error: {e}"
        
        cls._detection_cache = info
        return info
    
    @classmethod
    def clear_cache(cls):
        """Clear detection cache to force re-detection."""
        cls._detection_cache = None
        cls.is_docker_desktop_available.cache_clear()
    
    @classmethod
    def get_dd_server_message(cls, server_name: str) -> str:
        """
        Get appropriate message for Docker Desktop server operations.
        
        Args:
            server_name: Name of the DD server
            
        Returns:
            User-friendly message explaining the situation
        """
        if cls.is_docker_desktop_available():
            return ""  # No message needed, DD is available
        
        info = cls.get_detection_info()
        base_msg = f"Server '{server_name}' requires Docker Desktop."
        
        if info["docker_app_path"]:
            return f"{base_msg} Docker Desktop is installed but may not be running. Try starting Docker Desktop."
        else:
            return f"{base_msg} Install Docker Desktop or try 'mcp-{server_name}' for Docker CLI alternative."
    
    @classmethod
    def should_show_dd_servers(cls) -> bool:
        """
        Determine if DD servers should be shown in discovery/listing.
        
        Returns:
            True if DD servers should be shown (even if marked as unavailable)
        """
        # Always show them but mark appropriately
        return True
    
    @classmethod
    def can_install_dd_server(cls, server_name: str) -> tuple[bool, str]:
        """
        Check if a DD server can be installed.
        
        Args:
            server_name: Name of the server to install
            
        Returns:
            Tuple of (can_install, error_message)
        """
        if cls.is_docker_desktop_available():
            return True, ""
        
        error_msg = cls.get_dd_server_message(server_name)
        return False, error_msg
    
    @classmethod
    def can_enable_dd_server(cls, server_name: str) -> tuple[bool, str]:
        """
        Check if a DD server can be enabled.
        
        Args:
            server_name: Name of the server to enable
            
        Returns:
            Tuple of (can_enable, error_message)
        """
        return cls.can_install_dd_server(server_name)


# Convenience functions for easy importing
def is_docker_desktop_available() -> bool:
    """Check if Docker Desktop is available."""
    return DockerDesktopDetector.is_docker_desktop_available()


def get_dd_server_message(server_name: str) -> str:
    """Get message for DD server operations."""
    return DockerDesktopDetector.get_dd_server_message(server_name)


def can_install_dd_server(server_name: str) -> tuple[bool, str]:
    """Check if DD server can be installed."""
    return DockerDesktopDetector.can_install_dd_server(server_name)