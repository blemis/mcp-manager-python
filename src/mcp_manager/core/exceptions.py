"""
Exception classes for MCP Manager.

Defines custom exception hierarchy for different types of errors
that can occur during MCP server management operations.
"""

from typing import Any, Dict, Optional


class MCPManagerError(Exception):
    """Base exception for all MCP Manager errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize MCPManagerError.
        
        Args:
            message: Error message
            error_code: Optional error code for categorization
            details: Optional additional error details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        
    def __str__(self) -> str:
        """String representation of the error."""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
        }


class ConfigError(MCPManagerError):
    """Configuration-related errors."""
    pass


class ServerError(MCPManagerError):
    """Server management errors."""
    pass


class ClaudeError(MCPManagerError):
    """Claude CLI interaction errors."""
    pass


class DiscoveryError(MCPManagerError):
    """Server discovery errors."""
    pass


class ValidationError(MCPManagerError):
    """Data validation errors."""
    pass


class DependencyError(MCPManagerError):
    """Missing dependency errors."""
    pass


class PermissionError(MCPManagerError):
    """Permission/access errors."""
    pass


class NetworkError(MCPManagerError):
    """Network-related errors."""
    pass


class TimeoutError(MCPManagerError):
    """Operation timeout errors."""
    pass


class DuplicateServerError(MCPManagerError):
    """Error raised when similar servers are detected during installation."""
    
    def __init__(
        self,
        message: str,
        similar_servers: Optional[list] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize DuplicateServerError.
        
        Args:
            message: Error message
            similar_servers: List of similar server information
            error_code: Optional error code
            details: Optional additional details
        """
        super().__init__(message, error_code, details)
        self.similar_servers = similar_servers or []