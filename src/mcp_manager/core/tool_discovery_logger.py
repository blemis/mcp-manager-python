"""
Specialized logging infrastructure for tool discovery operations.

Provides structured logging with performance tracking, debug points,
and comprehensive error context for the tool registry system.
"""

import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from mcp_manager.core.models import ServerType
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)

class ToolDiscoveryLogger:
    """Centralized logging for tool discovery operations with performance tracking."""
    
    def __init__(self, component_name: str = "tool_discovery"):
        """
        Initialize tool discovery logger.
        
        Args:
            component_name: Name of the component using this logger
        """
        self.component_name = component_name
        self.logger = get_logger(f"{__name__}.{component_name}")
        self._operation_start_times: Dict[str, float] = {}
    
    def log_discovery_start(self, server_name: str, server_type: ServerType, 
                          operation_id: Optional[str] = None) -> str:
        """
        Log the start of a tool discovery operation.
        
        Args:
            server_name: Name of the server being discovered
            server_type: Type of server (npm, docker, etc.)
            operation_id: Optional operation ID for tracking
            
        Returns:
            Operation ID for tracking this discovery
        """
        if operation_id is None:
            operation_id = f"{server_name}_{int(time.time() * 1000)}"
        
        self._operation_start_times[operation_id] = time.time()
        
        self.logger.info("Tool discovery started", extra={
            "operation": "tool_discovery_start",
            "operation_id": operation_id,
            "server_name": server_name,
            "server_type": server_type.value if hasattr(server_type, 'value') else str(server_type),
            "timestamp": datetime.utcnow().isoformat(),
            "component": self.component_name
        })
        
        return operation_id
    
    def log_tool_found(self, tool_name: str, server_name: str, schema: Dict[str, Any],
                      operation_id: Optional[str] = None) -> None:
        """
        Log discovery of an individual tool.
        
        Args:
            tool_name: Name of the discovered tool
            server_name: Server providing the tool
            schema: Tool schema information
            operation_id: Operation ID for tracking
        """
        parameter_count = 0
        if isinstance(schema, dict) and "properties" in schema:
            parameter_count = len(schema["properties"])
        elif isinstance(schema, dict) and "parameters" in schema:
            parameter_count = len(schema["parameters"])
        
        self.logger.debug("Tool discovered", extra={
            "operation": "tool_found",
            "operation_id": operation_id,
            "tool_name": tool_name,
            "server_name": server_name,
            "canonical_name": f"{server_name}/{tool_name}",
            "parameter_count": parameter_count,
            "has_description": bool(schema.get("description")),
            "schema_keys": list(schema.keys()) if isinstance(schema, dict) else [],
            "component": self.component_name
        })
    
    def log_discovery_performance(self, server_name: str, tool_count: int,
                                operation_id: Optional[str] = None) -> float:
        """
        Log completion of tool discovery with performance metrics.
        
        Args:
            server_name: Name of the server that was discovered
            tool_count: Number of tools discovered
            operation_id: Operation ID for tracking
            
        Returns:
            Duration in seconds
        """
        duration_seconds = 0.0
        if operation_id and operation_id in self._operation_start_times:
            duration_seconds = time.time() - self._operation_start_times[operation_id]
            # Clean up tracking
            del self._operation_start_times[operation_id]
        
        duration_ms = int(duration_seconds * 1000)
        tools_per_second = tool_count / duration_seconds if duration_seconds > 0 else 0
        
        self.logger.info("Tool discovery completed", extra={
            "operation": "tool_discovery_completed",
            "operation_id": operation_id,
            "server_name": server_name,
            "duration_ms": duration_ms,
            "duration_seconds": round(duration_seconds, 3),
            "tools_discovered": tool_count,
            "tools_per_second": round(tools_per_second, 2),
            "performance_category": self._categorize_performance(duration_seconds, tool_count),
            "component": self.component_name
        })
        
        return duration_seconds
    
    def log_discovery_error(self, server_name: str, error: Exception,
                          operation_id: Optional[str] = None,
                          context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log tool discovery errors with full context.
        
        Args:
            server_name: Name of the server that failed
            error: Exception that occurred
            operation_id: Operation ID for tracking
            context: Additional context information
        """
        # Calculate duration if we have start time
        duration_seconds = None
        if operation_id and operation_id in self._operation_start_times:
            duration_seconds = time.time() - self._operation_start_times[operation_id]
            # Clean up tracking
            del self._operation_start_times[operation_id]
        
        error_context = {
            "operation": "tool_discovery_error",
            "operation_id": operation_id,
            "server_name": server_name,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "component": self.component_name
        }
        
        if duration_seconds is not None:
            error_context["failure_after_seconds"] = round(duration_seconds, 3)
        
        if context:
            error_context["additional_context"] = context
        
        self.logger.error("Tool discovery failed", extra=error_context)
    
    def log_server_connection(self, server_name: str, connection_type: str,
                            success: bool, duration_ms: Optional[int] = None) -> None:
        """
        Log server connection attempts and results.
        
        Args:
            server_name: Name of the server
            connection_type: Type of connection (docker, npx, etc.)
            success: Whether connection was successful
            duration_ms: Connection time in milliseconds
        """
        log_data = {
            "operation": "server_connection",
            "server_name": server_name,
            "connection_type": connection_type,
            "success": success,
            "component": self.component_name
        }
        
        if duration_ms is not None:
            log_data["connection_duration_ms"] = duration_ms
        
        if success:
            self.logger.debug("Server connection successful", extra=log_data)
        else:
            self.logger.warning("Server connection failed", extra=log_data)
    
    def log_tool_validation(self, tool_name: str, server_name: str,
                          validation_result: Dict[str, Any]) -> None:
        """
        Log tool validation results.
        
        Args:
            tool_name: Name of the tool being validated
            server_name: Server providing the tool
            validation_result: Results of validation checks
        """
        self.logger.debug("Tool validation completed", extra={
            "operation": "tool_validation",
            "tool_name": tool_name,
            "server_name": server_name,
            "canonical_name": f"{server_name}/{tool_name}",
            "validation_result": validation_result,
            "is_valid": validation_result.get("valid", False),
            "validation_errors": validation_result.get("errors", []),
            "component": self.component_name
        })
    
    def _categorize_performance(self, duration_seconds: float, tool_count: int) -> str:
        """
        Categorize discovery performance for monitoring.
        
        Args:
            duration_seconds: Time taken for discovery
            tool_count: Number of tools discovered
            
        Returns:
            Performance category string
        """
        if tool_count == 0:
            return "no_tools_found"
        
        tools_per_second = tool_count / duration_seconds if duration_seconds > 0 else float('inf')
        
        if tools_per_second > 10:
            return "excellent"
        elif tools_per_second > 5:
            return "good"  
        elif tools_per_second > 1:
            return "acceptable"
        else:
            return "slow"

@contextmanager
def performance_timer(operation_name: str, logger_instance: Optional[ToolDiscoveryLogger] = None):
    """
    Context manager for timing operations with automatic logging.
    
    Args:
        operation_name: Name of the operation being timed
        logger_instance: Optional logger instance to use
        
    Yields:
        Dictionary that will contain timing information
    """
    start_time = time.time()
    timing_info = {"start_time": start_time}
    
    try:
        yield timing_info
    finally:
        end_time = time.time()
        duration_seconds = end_time - start_time
        duration_ms = int(duration_seconds * 1000)
        
        timing_info.update({
            "end_time": end_time,
            "duration_seconds": duration_seconds,
            "duration_ms": duration_ms
        })
        
        # Log performance if logger provided
        if logger_instance:
            logger_instance.logger.debug("Operation timing", extra={
                "operation": "performance_timing",
                "operation_name": operation_name,
                "duration_ms": duration_ms,
                "duration_seconds": round(duration_seconds, 3)
            })

class ToolAnalyticsLogger:
    """Specialized logger for tool usage analytics."""
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.analytics")
    
    def log_tool_usage(self, canonical_name: str, query: str, selected: bool,
                      success: bool, response_time_ms: int,
                      context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log tool usage for analytics.
        
        Args:
            canonical_name: Tool canonical name (server/tool)
            query: User query that led to this tool
            selected: Whether user selected this tool
            success: Whether tool usage was successful
            response_time_ms: Response time in milliseconds
            context: Additional context information
        """
        self.logger.info("Tool usage recorded", extra={
            "operation": "tool_usage",
            "canonical_name": canonical_name,
            "query_length": len(query),
            "selected": selected,
            "success": success,
            "response_time_ms": response_time_ms,
            "context_provided": bool(context),
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def log_recommendation_request(self, query: str, context: Optional[Dict[str, Any]] = None,
                                 recommendations_count: int = 0) -> None:
        """
        Log tool recommendation requests.
        
        Args:
            query: User query
            context: Context information provided  
            recommendations_count: Number of recommendations returned
        """
        self.logger.info("Tool recommendation requested", extra={
            "operation": "recommendation_request",
            "query_length": len(query),
            "has_context": bool(context),
            "context_keys": list(context.keys()) if context else [],
            "recommendations_count": recommendations_count,
            "timestamp": datetime.utcnow().isoformat()
        })