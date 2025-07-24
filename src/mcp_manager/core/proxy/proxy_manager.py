"""
Main proxy manager orchestration module.

Coordinates proxy server operations, manages server health monitoring,
request routing, and provides the primary interface for proxy functionality.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

import aiohttp

from mcp_manager.core.proxy.models import (
    ProxyConfig, ProxyRequest, ProxyResponse, ProxyServerConfig,
    ProxyStats, RouteRule, ServerHealth, ServerStatus, ProxyMode
)
from mcp_manager.core.proxy.protocol_translator import ProtocolTranslator
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ProxyManager:
    """
    Main proxy manager for coordinating MCP server proxy operations.
    
    Manages server health monitoring, request routing, load balancing,
    and failover functionality across multiple MCP server endpoints.
    """
    
    def __init__(self, config: Optional[ProxyConfig] = None):
        """
        Initialize proxy manager.
        
        Args:
            config: Proxy configuration. If None, uses default configuration.
        """
        self.config = config or ProxyConfig()
        self.translator = ProtocolTranslator()
        
        # Server management
        self.servers: Dict[str, ProxyServerConfig] = {}
        self.server_health: Dict[str, ServerHealth] = {}
        self.active_servers: Set[str] = set()
        
        # Request routing
        self.route_rules: List[RouteRule] = []
        self.load_balancer_state: Dict[str, int] = {}  # server -> request count
        
        # Statistics and monitoring
        self.stats = ProxyStats()
        self.request_history: List[Dict[str, Any]] = []
        
        # Async components
        self.session: Optional[aiohttp.ClientSession] = None
        self.health_check_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Load servers from config
        for server_config in self.config.servers:
            self.add_server(server_config)
        
        logger.info("Proxy manager initialized", extra={
            "server_count": len(self.servers),
            "mode": self.config.mode.value,
            "port": self.config.port
        })
    
    async def start(self) -> None:
        """Start proxy manager and background tasks."""
        try:
            # Initialize HTTP session
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Start background tasks
            if self.config.health_check_enabled:
                self.health_check_task = asyncio.create_task(self._health_check_loop())
            
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            # Initialize server health
            for server_name in self.servers:
                await self._check_server_health(server_name)
            
            logger.info("Proxy manager started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start proxy manager: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop proxy manager and cleanup resources."""
        try:
            # Cancel background tasks
            if self.health_check_task:
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass
            
            if self.cleanup_task:
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Close HTTP session
            if self.session:
                await self.session.close()
            
            logger.info("Proxy manager stopped")
            
        except Exception as e:
            logger.error(f"Error stopping proxy manager: {e}")
    
    def add_server(self, server_config: ProxyServerConfig) -> None:
        """
        Add server to proxy configuration.
        
        Args:
            server_config: Server configuration to add
        """
        self.servers[server_config.name] = server_config
        self.load_balancer_state[server_config.name] = 0
        self.stats.requests_per_server[server_config.name] = 0
        self.stats.errors_per_server[server_config.name] = 0
        
        # Initialize health status
        self.server_health[server_config.name] = ServerHealth(
            name=server_config.name,
            status=ServerStatus.INITIALIZING,
            last_check=datetime.utcnow()
        )
        
        logger.info(f"Added server '{server_config.name}' to proxy")
    
    def remove_server(self, server_name: str) -> bool:
        """
        Remove server from proxy configuration.
        
        Args:
            server_name: Name of server to remove
            
        Returns:
            True if server was removed, False if not found
        """
        if server_name not in self.servers:
            logger.warning(f"Server '{server_name}' not found for removal")
            return False
        
        # Remove from all tracking structures
        del self.servers[server_name]
        del self.server_health[server_name]
        self.active_servers.discard(server_name)
        self.load_balancer_state.pop(server_name, None)
        
        logger.info(f"Removed server '{server_name}' from proxy")
        return True
    
    async def process_request(self, request: ProxyRequest) -> ProxyResponse:
        """
        Process incoming proxy request.
        
        Args:
            request: Standardized proxy request
            
        Returns:
            Proxy response with result or error
        """
        start_time = time.time()
        self.stats.total_requests += 1
        
        try:
            # Route request to appropriate server(s)
            target_servers = self._route_request(request)
            
            if not target_servers:
                self.stats.failed_requests += 1
                return ProxyResponse(
                    id=request.id,
                    error={
                        "code": -32601,
                        "message": "No available servers for request"
                    }
                )
            
            # Process based on proxy mode
            if self.config.mode == ProxyMode.AGGREGATING:
                response = await self._process_aggregating_request(request, target_servers)
            elif self.config.mode == ProxyMode.LOAD_BALANCING:
                response = await self._process_load_balanced_request(request, target_servers)
            elif self.config.mode == ProxyMode.FAILOVER:
                response = await self._process_failover_request(request, target_servers)
            else:  # TRANSPARENT
                response = await self._process_transparent_request(request, target_servers[0])
            
            # Update statistics
            processing_time = (time.time() - start_time) * 1000
            response.processing_time_ms = processing_time
            
            self._update_response_stats(processing_time, response.error is None)
            
            return response
            
        except Exception as e:
            self.stats.failed_requests += 1
            logger.error(f"Error processing request {request.method}: {e}")
            
            return ProxyResponse(
                id=request.id,
                error={
                    "code": -32603,
                    "message": f"Internal proxy error: {str(e)}"
                }
            )
    
    def _route_request(self, request: ProxyRequest) -> List[str]:
        """
        Route request to appropriate servers based on routing rules.
        
        Args:
            request: Request to route
            
        Returns:
            List of server names to handle the request
        """
        # Check for explicit target server
        if request.target_server:
            if request.target_server in self.active_servers:
                return [request.target_server]
            else:
                logger.warning(f"Requested server '{request.target_server}' not active")
        
        # Apply routing rules
        for rule in sorted(self.route_rules, key=lambda r: r.priority, reverse=True):
            if self._rule_matches_request(rule, request):
                # Filter to only active servers
                available_targets = [s for s in rule.target_servers if s in self.active_servers]
                if available_targets:
                    return available_targets
        
        # Default routing: all active servers
        return list(self.active_servers)
    
    def _rule_matches_request(self, rule: RouteRule, request: ProxyRequest) -> bool:
        """Check if routing rule matches request."""
        # Method pattern matching
        if rule.method_pattern:
            import re
            if not re.match(rule.method_pattern, request.method):
                return False
        
        # Tool name matching
        if rule.tool_name:
            tool_name = request.params.get("name") if request.params else None
            if tool_name != rule.tool_name:
                return False
        
        # User ID matching
        if rule.user_id and rule.user_id != request.user_id:
            return False
        
        return True
    
    async def _process_transparent_request(self, request: ProxyRequest, 
                                         server_name: str) -> ProxyResponse:
        """Process request in transparent mode (single server)."""
        try:
            server_config = self.servers[server_name]
            
            # Translate request to server protocol
            translated_request, translation_performed = self.translator.translate_request(
                request, server_config.protocol_version, server_config
            )
            
            # Send request to server
            response_data = await self._send_request_to_server(
                server_name, translated_request, request.timeout or server_config.timeout_seconds
            )
            
            # Translate response back
            response = self.translator.translate_response(
                response_data, server_config.protocol_version
            )
            
            response.server_name = server_name
            return response
            
        except Exception as e:
            logger.error(f"Transparent request failed for server {server_name}: {e}")
            return ProxyResponse(
                id=request.id,
                error={
                    "code": -32603,
                    "message": f"Server {server_name} error: {str(e)}"
                }
            )
    
    async def _process_load_balanced_request(self, request: ProxyRequest,
                                           target_servers: List[str]) -> ProxyResponse:
        """Process request with load balancing."""
        # Select server with lowest current load
        selected_server = min(target_servers, key=lambda s: self.load_balancer_state[s])
        
        # Update load balancer state
        self.load_balancer_state[selected_server] += 1
        self.stats.requests_per_server[selected_server] += 1
        
        try:
            response = await self._process_transparent_request(request, selected_server)
            
            if response.error is None:
                self.stats.successful_requests += 1
            else:
                self.stats.errors_per_server[selected_server] += 1
            
            return response
            
        finally:
            # Decrement load count
            self.load_balancer_state[selected_server] -= 1
    
    async def _process_failover_request(self, request: ProxyRequest,
                                      target_servers: List[str]) -> ProxyResponse:
        """Process request with failover support."""
        last_error = None
        
        for server_name in target_servers:
            try:
                response = await self._process_transparent_request(request, server_name)
                
                # Return immediately if successful
                if response.error is None:
                    self.stats.successful_requests += 1
                    if server_name != target_servers[0]:
                        response.failover_used = True
                    return response
                else:
                    last_error = response.error
                    
            except Exception as e:
                last_error = {"code": -32603, "message": str(e)}
                logger.warning(f"Failover attempt failed for server {server_name}: {e}")
                continue
        
        # All servers failed
        self.stats.failed_requests += 1
        return ProxyResponse(
            id=request.id,
            error=last_error or {"code": -32603, "message": "All servers failed"},
            failover_used=True
        )
    
    async def _process_aggregating_request(self, request: ProxyRequest,
                                         target_servers: List[str]) -> ProxyResponse:
        """Process request by aggregating responses from multiple servers."""
        tasks = []
        
        # Send request to all target servers concurrently
        for server_name in target_servers:
            task = asyncio.create_task(
                self._process_transparent_request(request, server_name)
            )
            tasks.append((server_name, task))
        
        # Collect responses
        aggregated_results = []
        successful_responses = 0
        
        for server_name, task in tasks:
            try:
                response = await task
                
                result_data = {
                    "server": server_name,
                    "result": response.result,
                    "error": response.error,
                    "processing_time_ms": response.processing_time_ms
                }
                aggregated_results.append(result_data)
                
                if response.error is None:
                    successful_responses += 1
                    
            except Exception as e:
                logger.error(f"Aggregation task failed for server {server_name}: {e}")
                aggregated_results.append({
                    "server": server_name,
                    "error": {"code": -32603, "message": str(e)}
                })
        
        # Create aggregated response
        if successful_responses > 0:
            self.stats.successful_requests += 1
            return ProxyResponse(
                id=request.id,
                result={"success": True, "servers_responded": successful_responses},
                aggregated_results=aggregated_results
            )
        else:
            self.stats.failed_requests += 1
            return ProxyResponse(
                id=request.id,
                error={"code": -32603, "message": "All servers failed"},
                aggregated_results=aggregated_results
            )
    
    async def _send_request_to_server(self, server_name: str, 
                                    request_data: Dict[str, Any],
                                    timeout: int) -> Any:
        """Send HTTP request to MCP server."""
        if not self.session:
            raise RuntimeError("HTTP session not initialized")
        
        server_config = self.servers[server_name]
        
        # Prepare request
        headers = {"Content-Type": "application/json"}
        headers.update(server_config.headers)
        
        # Add authentication if configured
        if server_config.auth_method and server_config.auth_credentials:
            headers.update(self._get_auth_headers(server_config))
        
        try:
            async with self.session.post(
                server_config.url,
                json=request_data,  
                headers=headers,
                timeout=timeout
            ) as response:
                response.raise_for_status()
                return await response.json()
                
        except asyncio.TimeoutError:
            raise Exception(f"Request timeout after {timeout}s")
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP client error: {e}")
        except Exception as e:
            raise Exception(f"Server communication error: {e}")
    
    def _get_auth_headers(self, server_config: ProxyServerConfig) -> Dict[str, str]:
        """Get authentication headers for server."""
        headers = {}
        
        if server_config.auth_method == "api_key":
            api_key = server_config.auth_credentials.get("api_key")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
        
        elif server_config.auth_method == "basic":
            import base64
            username = server_config.auth_credentials.get("username", "")
            password = server_config.auth_credentials.get("password", "")
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"
        
        return headers
    
    async def _check_server_health(self, server_name: str) -> None:
        """Check health of a specific server."""
        if server_name not in self.servers:
            return
        
        server_config = self.servers[server_name]
        start_time = time.time()
        
        try:
            # Send health check request
            health_request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": "health_check",
                "params": {}
            }
            
            response_data = await self._send_request_to_server(
                server_name, health_request, 10  # 10 second timeout for health checks
            )
            
            # Update health status
            response_time = (time.time() - start_time) * 1000
            
            self.server_health[server_name] = ServerHealth(
                name=server_name,
                status=ServerStatus.ONLINE,
                last_check=datetime.utcnow(),
                response_time_ms=response_time,
                consecutive_failures=0
            )
            
            self.active_servers.add(server_name)
            logger.debug(f"Health check passed for {server_name} ({response_time:.2f}ms)")
            
        except Exception as e:
            # Update failure status
            health = self.server_health.get(server_name)
            if health:
                health.status = ServerStatus.ERROR
                health.last_check = datetime.utcnow()
                health.error_message = str(e)
                health.consecutive_failures += 1
            
            self.active_servers.discard(server_name)
            logger.warning(f"Health check failed for {server_name}: {e}")
    
    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while True:
            try:
                # Check health of all servers
                tasks = [
                    self._check_server_health(server_name) 
                    for server_name in self.servers
                ]
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Update stats
                self.stats.active_servers = len(self.active_servers)
                self.stats.total_servers = len(self.servers)
                
                # Wait for next check
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(10)  # Short delay on error
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while True:
            try:
                # Clean up old request history
                cutoff_time = datetime.utcnow() - timedelta(hours=1)
                self.request_history = [
                    req for req in self.request_history 
                    if req.get("timestamp", datetime.min) > cutoff_time
                ]
                
                # Clear protocol translation cache periodically
                self.translator.clear_cache()
                
                # Wait for next cleanup
                await asyncio.sleep(300)  # Clean every 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
                await asyncio.sleep(60)
    
    def _update_response_stats(self, processing_time: float, success: bool) -> None:
        """Update response time statistics."""
        if success:
            self.stats.successful_requests += 1
        
        # Update timing stats
        if self.stats.average_response_time_ms == 0:
            self.stats.average_response_time_ms = processing_time
        else:
            # Running average
            total_requests = self.stats.successful_requests + self.stats.failed_requests
            self.stats.average_response_time_ms = (
                (self.stats.average_response_time_ms * (total_requests - 1) + processing_time) 
                / total_requests
            )
        
        # Update min/max
        if self.stats.min_response_time_ms == 0 or processing_time < self.stats.min_response_time_ms:
            self.stats.min_response_time_ms = processing_time
        
        if processing_time > self.stats.max_response_time_ms:
            self.stats.max_response_time_ms = processing_time
    
    def add_route_rule(self, rule: RouteRule) -> None:
        """Add routing rule."""
        self.route_rules.append(rule)
        self.route_rules.sort(key=lambda r: r.priority, reverse=True)
        logger.info(f"Added routing rule '{rule.name}'")
    
    def remove_route_rule(self, rule_name: str) -> bool:
        """Remove routing rule by name."""
        for i, rule in enumerate(self.route_rules):
            if rule.name == rule_name:
                del self.route_rules[i]
                logger.info(f"Removed routing rule '{rule_name}'")
                return True
        return False
    
    def get_server_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all servers."""
        status = {}
        
        for server_name, health in self.server_health.items():
            config = self.servers[server_name]
            status[server_name] = {
                "url": config.url,
                "protocol_version": config.protocol_version.value,
                "status": health.status.value,
                "last_check": health.last_check.isoformat(),
                "response_time_ms": health.response_time_ms,
                "consecutive_failures": health.consecutive_failures,
                "error_message": health.error_message
            }
        
        return status
    
    def get_proxy_stats(self) -> Dict[str, Any]:
        """Get comprehensive proxy statistics."""
        return {
            "total_requests": self.stats.total_requests,
            "successful_requests": self.stats.successful_requests,
            "failed_requests": self.stats.failed_requests,
            "success_rate_percent": (
                (self.stats.successful_requests / max(1, self.stats.total_requests)) * 100
            ),
            "average_response_time_ms": round(self.stats.average_response_time_ms, 2),
            "min_response_time_ms": self.stats.min_response_time_ms,
            "max_response_time_ms": self.stats.max_response_time_ms,
            "active_servers": self.stats.active_servers,
            "total_servers": self.stats.total_servers,
            "uptime_seconds": (datetime.utcnow() - self.stats.start_time).total_seconds(),
            "requests_per_server": dict(self.stats.requests_per_server),
            "errors_per_server": dict(self.stats.errors_per_server),
            "translation_stats": self.translator.get_stats(),
            "routing_rules": len(self.route_rules)
        }