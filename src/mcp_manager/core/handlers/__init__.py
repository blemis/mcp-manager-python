"""
Server handler interfaces and implementations for different server types.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from mcp_manager.core.models import Server


class ServerHandler(ABC):
    """
    Abstract base class for server handlers.
    
    Each server type (NPM, Docker, Docker Desktop, Custom) should implement
    this interface to provide consistent enable/disable/status operations.
    """
    
    @abstractmethod
    async def enable_server(self, server: Server) -> bool:
        """
        Enable a server.
        
        Args:
            server: Server to enable
            
        Returns:
            True if successfully enabled
        """
        pass
    
    @abstractmethod
    async def disable_server(self, server: Server) -> bool:
        """
        Disable a server.
        
        Args:
            server: Server to disable
            
        Returns:
            True if successfully disabled
        """
        pass
    
    @abstractmethod
    async def get_server_status(self, server: Server) -> str:
        """
        Get the current status of a server.
        
        Args:
            server: Server to check
            
        Returns:
            Status string ('enabled', 'disabled', 'error', etc.)
        """
        pass
    
    @abstractmethod
    async def is_server_available(self, server: Server) -> bool:
        """
        Check if server is available/installed.
        
        Args:
            server: Server to check
            
        Returns:
            True if server is available
        """
        pass