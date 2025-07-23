"""
Operation mode management for MCP Manager.

Handles switching between different operation modes:
- Direct Mode: Traditional MCP server management
- Proxy Mode: Unified proxy endpoint
- Hybrid Mode: Both modes simultaneously
"""

import socket
from enum import Enum
from typing import Any, Dict, List, Optional

from mcp_manager.core.config.proxy_config import ProxyModeConfig, ValidationResult
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class OperationMode(str, Enum):
    """MCP Manager operation modes."""
    
    DIRECT = "direct"     # Traditional mode - manage individual servers
    PROXY = "proxy"       # Proxy mode - unified endpoint
    HYBRID = "hybrid"     # Both modes simultaneously


class ModeTransition(str, Enum):
    """Mode transition types."""
    
    STARTUP = "startup"           # Initial mode selection at startup
    USER_REQUESTED = "user_requested"  # User explicitly requested mode change
    AUTOMATIC = "automatic"       # System automatically switched modes
    FALLBACK = "fallback"        # Fallback due to errors


class ModeManager:
    """Manages operation mode transitions and validation."""
    
    def __init__(self, config: Any):
        """
        Initialize mode manager.
        
        Args:
            config: Main configuration object with proxy settings
        """
        self.config = config
        self.logger = get_logger(__name__)
        self._current_mode: Optional[OperationMode] = None
        self._proxy_validated = False
        
        # Initialize mode based on configuration
        self._determine_initial_mode()
    
    def _determine_initial_mode(self) -> None:
        """Determine initial operation mode based on configuration."""
        try:
            proxy_config = getattr(self.config, 'proxy', None)
            if not proxy_config:
                self._current_mode = OperationMode.DIRECT
                return
            
            enable_direct = getattr(self.config, 'enable_direct_mode', True)
            
            if proxy_config.enabled and enable_direct:
                self._current_mode = OperationMode.HYBRID
            elif proxy_config.enabled:
                self._current_mode = OperationMode.PROXY
            else:
                self._current_mode = OperationMode.DIRECT
            
            self.logger.info("Initial operation mode determined", extra={
                "mode": self._current_mode.value,
                "proxy_enabled": proxy_config.enabled if proxy_config else False,
                "direct_enabled": enable_direct
            })
            
        except Exception as e:
            self.logger.error(f"Failed to determine initial mode: {e}")
            self._current_mode = OperationMode.DIRECT
    
    def get_current_mode(self) -> OperationMode:
        """Get current operation mode."""
        if self._current_mode is None:
            self._determine_initial_mode()
        return self._current_mode
    
    def is_proxy_available(self) -> bool:
        """Check if proxy mode is available and properly configured."""
        try:
            proxy_config = getattr(self.config, 'proxy', None)
            if not proxy_config or not proxy_config.enabled:
                return False
            
            # Cache validation result to avoid repeated checks
            if not self._proxy_validated:
                validation_result = self.validate_proxy_requirements(proxy_config)
                self._proxy_validated = validation_result.valid
            
            return self._proxy_validated
            
        except Exception as e:
            self.logger.error(f"Error checking proxy availability: {e}")
            return False
    
    def is_direct_available(self) -> bool:
        """Check if direct mode is available."""
        # Direct mode is always available as it's the core functionality
        return True
    
    def validate_proxy_requirements(self, proxy_config: ProxyModeConfig) -> ValidationResult:
        """
        Validate all proxy mode requirements are met.
        
        Args:
            proxy_config: Proxy configuration to validate
            
        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(valid=True)
        
        try:
            # Port availability check
            if not self._is_port_available(proxy_config.host, proxy_config.port):
                result.add_issue(f"Port {proxy_config.port} is not available on {proxy_config.host}")
            
            # Authentication validation
            if proxy_config.enable_auth and not proxy_config.auth_token:
                result.add_issue("Authentication enabled but no auth token provided")
            
            # Performance validation
            if proxy_config.max_concurrent_requests < 1:
                result.add_issue("max_concurrent_requests must be positive")
            
            if proxy_config.request_timeout_seconds < 1:
                result.add_issue("request_timeout_seconds must be positive")
            
            # Cache validation
            if proxy_config.enable_caching and proxy_config.cache_ttl_seconds < 1:
                result.add_issue("cache_ttl_seconds must be positive when caching is enabled")
            
            # Rate limiting validation
            if proxy_config.enable_rate_limiting and proxy_config.rate_limit_requests_per_minute < 1:
                result.add_issue("rate_limit_requests_per_minute must be positive when rate limiting is enabled")
            
            # Performance warnings
            if proxy_config.max_concurrent_requests > 200:
                result.add_warning("High concurrent request limit may impact system performance")
            
            if proxy_config.request_timeout_seconds > 60:
                result.add_warning("Long request timeout may cause client timeouts")
            
            if not proxy_config.enable_caching:
                result.add_recommendation("Enable caching for better performance")
            
            if proxy_config.log_all_requests:
                result.add_warning("Logging all requests may impact performance in high-traffic scenarios")
            
            # Security recommendations
            if proxy_config.enabled and not proxy_config.enable_auth:
                result.add_recommendation("Consider enabling authentication for security")
            
            if proxy_config.host == "0.0.0.0":
                result.add_warning("Binding to 0.0.0.0 makes proxy accessible from all interfaces")
            
            self.logger.debug("Proxy configuration validated", extra={
                "valid": result.valid,
                "issues_count": len(result.issues),
                "warnings_count": len(result.warnings),
                "recommendations_count": len(result.recommendations)
            })
            
        except Exception as e:
            result.add_issue(f"Validation error: {str(e)}")
            self.logger.error(f"Proxy validation failed: {e}")
        
        return result
    
    def _is_port_available(self, host: str, port: int) -> bool:
        """Check if a port is available for binding."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                result = sock.connect_ex((host, port))
                return result != 0  # Port is available if connection fails
        except Exception as e:
            self.logger.debug(f"Port availability check failed: {e}")
            return False
    
    def switch_mode(self, target_mode: OperationMode, force: bool = False, 
                   transition_type: ModeTransition = ModeTransition.USER_REQUESTED) -> bool:
        """
        Safely switch between operation modes.
        
        Args:
            target_mode: Target operation mode
            force: Skip validation checks
            transition_type: Type of mode transition
            
        Returns:
            True if mode switch succeeded
        """
        try:
            current_mode = self.get_current_mode()
            
            if current_mode == target_mode:
                self.logger.info(f"Already in {target_mode.value} mode")
                return True
            
            self.logger.info("Mode switch requested", extra={
                "from_mode": current_mode.value,
                "to_mode": target_mode.value,
                "force": force,
                "transition_type": transition_type.value
            })
            
            # Validate target mode requirements
            if not force:
                validation_errors = self._validate_mode_switch(current_mode, target_mode)
                if validation_errors:
                    self.logger.error("Mode switch validation failed", extra={
                        "errors": validation_errors
                    })
                    return False
            
            # Perform the mode switch
            success = self._perform_mode_switch(current_mode, target_mode)
            
            if success:
                self._current_mode = target_mode
                self.logger.info("Mode switch completed successfully", extra={
                    "new_mode": target_mode.value,
                    "transition_type": transition_type.value
                })
            else:
                self.logger.error("Mode switch failed")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Mode switch error: {e}")
            return False
    
    def _validate_mode_switch(self, from_mode: OperationMode, to_mode: OperationMode) -> List[str]:
        """Validate mode switch requirements."""
        errors = []
        
        # Validate proxy mode requirements if switching to proxy or hybrid
        if to_mode in [OperationMode.PROXY, OperationMode.HYBRID]:
            proxy_config = getattr(self.config, 'proxy', None)
            if not proxy_config:
                errors.append("Proxy configuration not found")
            else:
                validation = self.validate_proxy_requirements(proxy_config)
                if not validation.valid:
                    errors.extend(validation.issues)
        
        # Validate direct mode requirements if switching to direct or hybrid
        if to_mode in [OperationMode.DIRECT, OperationMode.HYBRID]:
            if not self.is_direct_available():
                errors.append("Direct mode is not available")
        
        return errors
    
    def _perform_mode_switch(self, from_mode: OperationMode, to_mode: OperationMode) -> bool:
        """Perform the actual mode switch."""
        try:
            # Mode switch logic would be implemented here
            # This is a placeholder for the actual implementation
            
            self.logger.debug("Performing mode switch", extra={
                "from": from_mode.value,
                "to": to_mode.value
            })
            
            # For now, just update the internal state
            # In actual implementation, this would:
            # 1. Stop services that are no longer needed
            # 2. Start services that are newly required
            # 3. Update configurations
            # 4. Validate the new state
            
            return True
            
        except Exception as e:
            self.logger.error(f"Mode switch execution failed: {e}")
            return False
    
    def get_mode_info(self) -> Dict[str, Any]:
        """Get comprehensive information about current mode and capabilities."""
        current_mode = self.get_current_mode()
        proxy_config = getattr(self.config, 'proxy', None)
        
        info = {
            "current_mode": current_mode.value,
            "direct_available": self.is_direct_available(),
            "proxy_available": self.is_proxy_available(),
            "supported_modes": [mode.value for mode in OperationMode],
        }
        
        if proxy_config:
            info["proxy_config"] = {
                "enabled": proxy_config.enabled,
                "endpoint": proxy_config.get_proxy_endpoint() if proxy_config.enabled else None,
                "authentication_enabled": proxy_config.is_authentication_required(),
                "caching_enabled": proxy_config.enable_caching,
                "load_balancing_enabled": proxy_config.enable_load_balancing
            }
        
        return info
    
    def can_switch_to_mode(self, target_mode: OperationMode) -> bool:
        """Check if switching to target mode is possible."""
        if target_mode == self.get_current_mode():
            return True
        
        validation_errors = self._validate_mode_switch(self.get_current_mode(), target_mode)
        return len(validation_errors) == 0