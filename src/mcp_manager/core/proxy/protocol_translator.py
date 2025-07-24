"""
Protocol translation module for MCP Proxy Server.

Handles translation between different MCP protocol versions and formats,
ensuring compatibility across diverse MCP server implementations.
"""

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from mcp_manager.core.proxy.models import (
    ProtocolVersion, ProxyRequest, ProxyResponse, ProxyServerConfig
)
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ProtocolTranslator:
    """
    Translates between different MCP protocol versions and formats.
    
    Provides bidirectional translation capabilities to ensure compatibility
    between clients and servers using different protocol versions.
    """
    
    def __init__(self):
        """Initialize protocol translator."""
        self.translation_cache: Dict[str, Any] = {}
        self.stats = {
            "translations_performed": 0,
            "cache_hits": 0,
            "translation_errors": 0
        }
        
        logger.info("Protocol translator initialized")
    
    def translate_request(self, request: ProxyRequest, 
                         target_protocol: ProtocolVersion,
                         server_config: ProxyServerConfig) -> Tuple[Dict[str, Any], bool]:
        """
        Translate request to target protocol version.
        
        Args:
            request: Standardized proxy request
            target_protocol: Target protocol version
            server_config: Target server configuration
            
        Returns:
            Tuple of (translated_request, translation_performed)
        """
        try:
            start_time = time.time()
            
            # Create cache key
            cache_key = f"{request.method}:{target_protocol.value}:{hash(str(request.dict()))}"
            
            # Check cache first
            if cache_key in self.translation_cache:
                self.stats["cache_hits"] += 1
                logger.debug(f"Using cached translation for {request.method}")
                return self.translation_cache[cache_key], True
            
            # Perform translation based on target protocol
            if target_protocol == ProtocolVersion.MCP_V1:
                translated = self._translate_to_mcp_v1(request, server_config)
            elif target_protocol == ProtocolVersion.MCP_V2:
                translated = self._translate_to_mcp_v2(request, server_config)
            elif target_protocol == ProtocolVersion.LEGACY:
                translated = self._translate_to_legacy(request, server_config)
            else:
                logger.warning(f"Unknown protocol version: {target_protocol}")
                translated = self._create_basic_request(request)
            
            # Cache the translation
            self.translation_cache[cache_key] = translated
            
            # Update stats
            self.stats["translations_performed"] += 1
            translation_time = (time.time() - start_time) * 1000
            
            logger.debug(f"Translated {request.method} to {target_protocol.value} in {translation_time:.2f}ms")
            
            return translated, True
            
        except Exception as e:
            self.stats["translation_errors"] += 1
            logger.error(f"Failed to translate request {request.method}: {e}")
            
            # Return basic request as fallback
            return self._create_basic_request(request), False
    
    def translate_response(self, response_data: Any, 
                          source_protocol: ProtocolVersion,
                          target_format: str = "standard") -> ProxyResponse:
        """
        Translate response from source protocol to standard format.
        
        Args:
            response_data: Raw response data from server
            source_protocol: Source protocol version
            target_format: Target response format
            
        Returns:
            Standardized proxy response
        """
        try:
            start_time = time.time()
            
            # Translate based on source protocol
            if source_protocol == ProtocolVersion.MCP_V1:
                translated = self._translate_from_mcp_v1(response_data)
            elif source_protocol == ProtocolVersion.MCP_V2:
                translated = self._translate_from_mcp_v2(response_data)
            elif source_protocol == ProtocolVersion.LEGACY:
                translated = self._translate_from_legacy(response_data)
            else:
                logger.warning(f"Unknown source protocol: {source_protocol}")
                translated = self._create_basic_response(response_data)
            
            # Add metadata
            translated.protocol_version = source_protocol.value
            translated.processing_time_ms = (time.time() - start_time) * 1000
            
            return translated
            
        except Exception as e:
            logger.error(f"Failed to translate response from {source_protocol}: {e}")
            return self._create_error_response(str(e))
    
    def _translate_to_mcp_v1(self, request: ProxyRequest, 
                           server_config: ProxyServerConfig) -> Dict[str, Any]:
        """Translate request to MCP v1 format."""
        translated = {
            "jsonrpc": "2.0",
            "method": request.method,
            "id": request.id or self._generate_request_id()
        }
        
        # Add parameters if present
        if request.params:
            translated["params"] = self._adapt_params_for_v1(request.params)
        
        # Add server-specific headers
        if server_config.headers:
            translated["headers"] = server_config.headers
        
        return translated
    
    def _translate_to_mcp_v2(self, request: ProxyRequest,
                           server_config: ProxyServerConfig) -> Dict[str, Any]:
        """Translate request to MCP v2 format."""
        translated = {
            "jsonrpc": "2.0",
            "method": request.method,
            "id": request.id or self._generate_request_id(),
            "meta": {
                "version": "2.0",
                "capabilities": self._get_client_capabilities()
            }
        }
        
        # Add parameters with v2 enhancements
        if request.params:
            translated["params"] = self._adapt_params_for_v2(request.params)
        
        # Add context information
        if request.user_id or request.session_id:
            translated["context"] = {
                "user_id": request.user_id,
                "session_id": request.session_id,
                "metadata": request.metadata
            }
        
        return translated
    
    def _translate_to_legacy(self, request: ProxyRequest,
                           server_config: ProxyServerConfig) -> Dict[str, Any]:
        """Translate request to legacy format."""
        # Legacy format is simpler, without JSON-RPC wrapper
        translated = {
            "method": request.method,
            "id": request.id or self._generate_request_id()
        }
        
        # Flatten parameters for legacy compatibility
        if request.params:
            translated.update(self._flatten_params_for_legacy(request.params))
        
        return translated
    
    def _translate_from_mcp_v1(self, response_data: Any) -> ProxyResponse:
        """Translate response from MCP v1 format."""
        if isinstance(response_data, dict):
            return ProxyResponse(
                id=response_data.get("id"),
                result=response_data.get("result"),
                error=response_data.get("error")
            )
        else:
            return ProxyResponse(result=response_data)
    
    def _translate_from_mcp_v2(self, response_data: Any) -> ProxyResponse:
        """Translate response from MCP v2 format."""
        if isinstance(response_data, dict):
            response = ProxyResponse(
                id=response_data.get("id"),
                result=response_data.get("result"),
                error=response_data.get("error")
            )
            
            # Extract v2-specific metadata
            if "meta" in response_data:
                meta = response_data["meta"]
                response.processing_time_ms = meta.get("processing_time")
                
            return response
        else:
            return ProxyResponse(result=response_data)
    
    def _translate_from_legacy(self, response_data: Any) -> ProxyResponse:
        """Translate response from legacy format."""
        if isinstance(response_data, dict):
            # Legacy responses might not have standard structure
            if "error" in response_data:
                return ProxyResponse(error=response_data["error"])
            else:
                return ProxyResponse(result=response_data)
        else:
            return ProxyResponse(result=response_data)
    
    def _adapt_params_for_v1(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt parameters for MCP v1 compatibility."""
        # Remove v2-specific parameter features
        adapted = params.copy()
        
        # Remove unsupported parameter types or structures
        for key, value in list(adapted.items()):
            if isinstance(value, dict) and "type" in value and "schema" in value:
                # Convert typed parameters to simple values
                adapted[key] = value.get("default") or value.get("value")
        
        return adapted
    
    def _adapt_params_for_v2(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt parameters for MCP v2 enhancements."""
        adapted = params.copy()
        
        # Add v2 parameter enhancements
        for key, value in adapted.items():
            if isinstance(value, (str, int, float, bool)):
                # Wrap simple values in v2 parameter objects
                adapted[key] = {
                    "value": value,
                    "type": type(value).__name__
                }
        
        return adapted
    
    def _flatten_params_for_legacy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten parameters for legacy compatibility."""
        flattened = {}
        
        def flatten_dict(d: Dict[str, Any], prefix: str = ""):
            for key, value in d.items():
                new_key = f"{prefix}_{key}" if prefix else key
                if isinstance(value, dict):
                    flatten_dict(value, new_key)
                else:
                    flattened[new_key] = value
        
        flatten_dict(params)
        return flattened
    
    def _create_basic_request(self, request: ProxyRequest) -> Dict[str, Any]:
        """Create basic request format as fallback."""
        return {
            "method": request.method,
            "params": request.params or {},
            "id": request.id or self._generate_request_id()
        }
    
    def _create_basic_response(self, response_data: Any) -> ProxyResponse:
        """Create basic response format as fallback."""
        return ProxyResponse(result=response_data)
    
    def _create_error_response(self, error_message: str) -> ProxyResponse:
        """Create error response."""
        return ProxyResponse(
            error={
                "code": -32603,  # Internal error
                "message": f"Protocol translation error: {error_message}"
            }
        )
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _get_client_capabilities(self) -> Dict[str, Any]:
        """Get client capabilities for protocol negotiation."""
        return {
            "tools": True,
            "resources": True,
            "prompts": True,
            "notifications": True,
            "protocol_translation": True
        }
    
    def get_supported_protocols(self) -> List[ProtocolVersion]:
        """Get list of supported protocol versions."""
        return list(ProtocolVersion)
    
    def detect_protocol_version(self, request_data: Dict[str, Any]) -> ProtocolVersion:
        """
        Detect protocol version from incoming request.
        
        Args:
            request_data: Raw request data
            
        Returns:
            Detected protocol version
        """
        # Check for v2-specific features
        if "meta" in request_data and isinstance(request_data["meta"], dict):
            version = request_data["meta"].get("version")
            if version and version.startswith("2"):
                return ProtocolVersion.MCP_V2
        
        # Check for JSON-RPC structure (v1)
        if "jsonrpc" in request_data and request_data["jsonrpc"] == "2.0":
            return ProtocolVersion.MCP_V1
        
        # Check for method without JSON-RPC wrapper (legacy)
        if "method" in request_data and "jsonrpc" not in request_data:
            return ProtocolVersion.LEGACY
        
        # Default to v1
        return ProtocolVersion.MCP_V1
    
    def clear_cache(self) -> None:
        """Clear translation cache."""
        self.translation_cache.clear()
        logger.debug("Translation cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get translation statistics."""
        cache_size = len(self.translation_cache)
        hit_rate = (self.stats["cache_hits"] / max(1, self.stats["translations_performed"])) * 100
        
        return {
            **self.stats,
            "cache_size": cache_size,
            "cache_hit_rate_percent": round(hit_rate, 2)
        }