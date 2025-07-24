"""
MCP Proxy Server implementation.

Provides HTTP server interface for the MCP proxy functionality,
handling incoming requests and routing them through the proxy manager.
"""

import asyncio
import json
import time
from typing import Any, Dict, Optional

from aiohttp import web, WSMsgType
from aiohttp.web import Application, Request, Response, WebSocketResponse

from mcp_manager.core.proxy.models import ProxyConfig, ProxyRequest, ProxyResponse
from mcp_manager.core.proxy.proxy_manager import ProxyManager
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ProxyServer:
    """
    HTTP server for MCP proxy functionality.
    
    Provides REST API and WebSocket endpoints for MCP protocol communication,
    with request routing, load balancing, and protocol translation.
    """
    
    def __init__(self, config: Optional[ProxyConfig] = None):
        """
        Initialize proxy server.
        
        Args:
            config: Proxy configuration. If None, uses default configuration.
        """
        self.config = config or ProxyConfig()
        self.proxy_manager = ProxyManager(self.config)
        self.app: Optional[Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        
        # Connection tracking
        self.active_connections: Dict[str, WebSocketResponse] = {}
        self.connection_counter = 0
        
        logger.info("Proxy server initialized", extra={
            "host": self.config.host,
            "port": self.config.port,
            "mode": self.config.mode.value
        })
    
    async def start(self) -> None:
        """Start the proxy server."""
        try:
            # Start proxy manager
            await self.proxy_manager.start()
            
            # Create web application
            self.app = self._create_app()
            
            # Create runner and site
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(
                self.runner, 
                self.config.host, 
                self.config.port
            )
            
            await self.site.start()
            
            logger.info(f"Proxy server started on {self.config.host}:{self.config.port}")
            
        except Exception as e:
            logger.error(f"Failed to start proxy server: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop the proxy server."""
        try:
            # Close all WebSocket connections
            for conn_id, ws in self.active_connections.items():
                if not ws.closed:
                    await ws.close()
            
            self.active_connections.clear()
            
            # Stop HTTP server
            if self.site:
                await self.site.stop()
            
            if self.runner:
                await self.runner.cleanup()
            
            # Stop proxy manager
            await self.proxy_manager.stop()
            
            logger.info("Proxy server stopped")
            
        except Exception as e:
            logger.error(f"Error stopping proxy server: {e}")
    
    def _create_app(self) -> Application:
        """Create aiohttp web application with routes."""
        app = Application()
        
        # Add middleware
        app.middlewares.append(self._request_logging_middleware)
        app.middlewares.append(self._cors_middleware) 
        app.middlewares.append(self._error_handling_middleware)
        
        # Add routes  
        self._add_routes(app)
        
        return app
    
    def _add_routes(self, app: Application) -> None:
        """Add HTTP routes to application."""
        
        # Main MCP endpoint (POST)
        app.router.add_post('/mcp', self._handle_mcp_request)
        
        # WebSocket endpoint
        app.router.add_get('/ws', self._handle_websocket)
        
        # Health and status endpoints
        app.router.add_get('/health', self._handle_health)
        app.router.add_get('/status', self._handle_status)
        app.router.add_get('/stats', self._handle_stats)
        
        # Server management endpoints
        app.router.add_get('/servers', self._handle_list_servers)
        app.router.add_post('/servers', self._handle_add_server)
        app.router.add_delete('/servers/{server_name}', self._handle_remove_server)
        
        # Static files for web interface (optional)
        app.router.add_get('/', self._handle_index)
        
        logger.debug(f"Added {len(app.router._resources)} routes to proxy server")
    
    async def _handle_mcp_request(self, request: Request) -> Response:
        """Handle HTTP MCP request."""
        try:
            # Parse request body
            body = await request.json()
            
            # Convert to proxy request format
            proxy_request = ProxyRequest(
                method=body.get("method", ""),
                params=body.get("params"),
                id=body.get("id"),
                user_id=request.headers.get("X-User-ID"),
                session_id=request.headers.get("X-Session-ID"),
                metadata={
                    "client_ip": request.remote,
                    "user_agent": request.headers.get("User-Agent", ""),
                    "timestamp": time.time()
                }
            )
            
            # Process through proxy manager
            proxy_response = await self.proxy_manager.process_request(proxy_request)
            
            # Convert to HTTP response
            response_data = {
                "jsonrpc": "2.0",
                "id": proxy_response.id,
            }
            
            if proxy_response.error:
                response_data["error"] = proxy_response.error
            else:
                response_data["result"] = proxy_response.result
            
            # Add proxy metadata in headers
            headers = {}
            if proxy_response.server_name:
                headers["X-Proxy-Server"] = proxy_response.server_name
            if proxy_response.processing_time_ms:
                headers["X-Processing-Time"] = str(proxy_response.processing_time_ms)
            if proxy_response.protocol_version:
                headers["X-Protocol-Version"] = proxy_response.protocol_version
            
            return web.json_response(response_data, headers=headers)
            
        except json.JSONDecodeError:
            return web.json_response({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": "Parse error: Invalid JSON"
                },
                "id": None
            }, status=400)
        
        except Exception as e:
            logger.error(f"Error handling MCP request: {e}")
            return web.json_response({
                "jsonrpc": "2.0", 
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                },
                "id": None
            }, status=500)
    
    async def _handle_websocket(self, request: Request) -> WebSocketResponse:
        """Handle WebSocket connection for real-time MCP communication."""
        ws = WebSocketResponse()
        await ws.prepare(request)
        
        # Generate connection ID
        self.connection_counter += 1
        conn_id = f"ws_{self.connection_counter}"
        self.active_connections[conn_id] = ws
        
        logger.info(f"WebSocket connection established: {conn_id}")
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        # Parse JSON message
                        data = json.loads(msg.data)
                        
                        # Convert to proxy request
                        proxy_request = ProxyRequest(
                            method=data.get("method", ""),
                            params=data.get("params"),
                            id=data.get("id"),
                            metadata={
                                "connection_id": conn_id,
                                "timestamp": time.time()
                            }
                        )
                        
                        # Process request
                        proxy_response = await self.proxy_manager.process_request(proxy_request)
                        
                        # Send response
                        response_data = {
                            "jsonrpc": "2.0",
                            "id": proxy_response.id
                        }
                        
                        if proxy_response.error:
                            response_data["error"] = proxy_response.error
                        else:
                            response_data["result"] = proxy_response.result
                        
                        await ws.send_str(json.dumps(response_data))
                        
                    except json.JSONDecodeError:
                        await ws.send_str(json.dumps({
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32700,
                                "message": "Parse error: Invalid JSON"
                            }
                        }))
                    
                    except Exception as e:
                        logger.error(f"WebSocket message error: {e}")
                        await ws.send_str(json.dumps({
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32603,
                                "message": f"Internal error: {str(e)}"
                            }
                        }))
                
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break
        
        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
        
        finally:
            # Clean up connection
            self.active_connections.pop(conn_id, None)
            logger.info(f"WebSocket connection closed: {conn_id}")
        
        return ws
    
    async def _handle_health(self, request: Request) -> Response:
        """Handle health check request."""
        health_data = {
            "status": "healthy",
            "timestamp": time.time(),
            "proxy_manager": "running",
            "active_servers": len(self.proxy_manager.active_servers),
            "total_servers": len(self.proxy_manager.servers),
            "active_connections": len(self.active_connections)
        }
        
        return web.json_response(health_data)
    
    async def _handle_status(self, request: Request) -> Response:
        """Handle status request with detailed information."""
        status_data = {
            "proxy_config": {
                "host": self.config.host,
                "port": self.config.port,
                "mode": self.config.mode.value,
                "protocol_translation": self.config.enable_protocol_translation,
                "load_balancing": self.config.enable_load_balancing,
                "failover": self.config.enable_failover
            },
            "servers": self.proxy_manager.get_server_status(),
            "connections": {
                "active_websockets": len(self.active_connections),
                "connection_list": list(self.active_connections.keys())
            },
            "routing_rules": len(self.proxy_manager.route_rules)
        }
        
        return web.json_response(status_data)
    
    async def _handle_stats(self, request: Request) -> Response:
        """Handle statistics request."""
        stats = self.proxy_manager.get_proxy_stats()
        return web.json_response(stats)
    
    async def _handle_list_servers(self, request: Request) -> Response:
        """Handle server list request."""
        servers = {}
        
        for name, config in self.proxy_manager.servers.items():
            servers[name] = {
                "url": config.url,
                "protocol_version": config.protocol_version.value,
                "weight": config.weight,
                "timeout_seconds": config.timeout_seconds,
                "health": self.proxy_manager.server_health.get(name, {})
            }
        
        return web.json_response({"servers": servers})
    
    async def _handle_add_server(self, request: Request) -> Response:
        """Handle add server request."""
        try:
            server_data = await request.json()
            
            # Create server configuration
            from mcp_manager.core.proxy.models import ProxyServerConfig, ProtocolVersion
            
            server_config = ProxyServerConfig(
                name=server_data["name"],
                url=server_data["url"],
                protocol_version=ProtocolVersion(server_data.get("protocol_version", "mcp-v1")),
                weight=server_data.get("weight", 100),
                timeout_seconds=server_data.get("timeout_seconds", 30)
            )
            
            # Add to proxy manager
            self.proxy_manager.add_server(server_config)
            
            # Trigger health check
            await self.proxy_manager._check_server_health(server_config.name)
            
            return web.json_response({
                "status": "success",
                "message": f"Server '{server_config.name}' added successfully"
            })
            
        except Exception as e:
            logger.error(f"Error adding server: {e}")
            return web.json_response({
                "status": "error",
                "message": str(e)
            }, status=400)
    
    async def _handle_remove_server(self, request: Request) -> Response:
        """Handle remove server request."""
        server_name = request.match_info["server_name"]
        
        if self.proxy_manager.remove_server(server_name):
            return web.json_response({
                "status": "success",
                "message": f"Server '{server_name}' removed successfully"
            })
        else:
            return web.json_response({
                "status": "error",
                "message": f"Server '{server_name}' not found"
            }, status=404)
    
    async def _handle_index(self, request: Request) -> Response:
        """Handle index page request."""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>MCP Proxy Server</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #007acc; padding-bottom: 10px; }
        .status { background: #e8f5e8; padding: 15px; border-left: 4px solid #4caf50; margin: 20px 0; }
        .endpoint { background: #f0f8ff; padding: 10px; margin: 10px 0; border-radius: 4px; font-family: monospace; }
        ul { list-style-type: none; padding: 0; }
        li { padding: 8px 0; border-bottom: 1px solid #eee; }
        .method { color: #007acc; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔄 MCP Proxy Server</h1>
        
        <div class="status">
            <strong>Status:</strong> Running<br>
            <strong>Mode:</strong> """ + self.config.mode.value + """<br>
            <strong>Host:</strong> """ + self.config.host + """<br>
            <strong>Port:</strong> """ + str(self.config.port) + """
        </div>
        
        <h2>📡 API Endpoints</h2>
        <ul>
            <li><span class="method">POST</span> <div class="endpoint">/mcp</div> Main MCP protocol endpoint</li>
            <li><span class="method">GET</span> <div class="endpoint">/ws</div> WebSocket connection for real-time communication</li>
            <li><span class="method">GET</span> <div class="endpoint">/health</div> Health check endpoint</li>
            <li><span class="method">GET</span> <div class="endpoint">/status</div> Detailed status information</li>
            <li><span class="method">GET</span> <div class="endpoint">/stats</div> Proxy statistics</li>
            <li><span class="method">GET</span> <div class="endpoint">/servers</div> List configured servers</li>
        </ul>
        
        <h2>🔧 Quick Actions</h2>
        <p>
            <a href="/health" target="_blank">Check Health</a> | 
            <a href="/status" target="_blank">View Status</a> | 
            <a href="/stats" target="_blank">View Statistics</a> |
            <a href="/servers" target="_blank">List Servers</a>
        </p>
        
        <h2>📖 Usage</h2>
        <p>Send JSON-RPC requests to <code>/mcp</code> endpoint:</p>
        <div class="endpoint">
POST /mcp<br>
Content-Type: application/json<br><br>
{<br>
&nbsp;&nbsp;"jsonrpc": "2.0",<br>
&nbsp;&nbsp;"method": "tools/list",<br>
&nbsp;&nbsp;"id": 1<br>
}
        </div>
    </div>
</body>
</html>
        """
        
        return web.Response(text=html_content, content_type='text/html')
    
    @web.middleware
    async def _request_logging_middleware(self, request: Request, handler) -> Response:
        """Log all requests."""
        start_time = time.time()
        
        try:
            response = await handler(request)
            processing_time = (time.time() - start_time) * 1000
            
            logger.info(f"{request.method} {request.path}", extra={
                "status": response.status,
                "processing_time_ms": round(processing_time, 2),
                "client_ip": request.remote,
                "user_agent": request.headers.get("User-Agent", "")
            })
            
            return response
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            logger.error(f"{request.method} {request.path} - Error: {e}", extra={
                "processing_time_ms": round(processing_time, 2),
                "client_ip": request.remote
            })
            raise
    
    @web.middleware
    async def _cors_middleware(self, request: Request, handler) -> Response:
        """Handle CORS headers."""
        response = await handler(request)
        
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        
        return response
    
    @web.middleware  
    async def _error_handling_middleware(self, request: Request, handler) -> Response:
        """Handle errors gracefully."""
        try:
            return await handler(request)
        except web.HTTPException:
            # Re-raise HTTP exceptions (they're handled properly by aiohttp)
            raise
        except Exception as e:
            logger.error(f"Unhandled error in {request.method} {request.path}: {e}")
            
            return web.json_response({
                "error": {
                    "code": -32603,
                    "message": "Internal server error"
                }
            }, status=500)
    
    async def run_forever(self) -> None:
        """Start server and run forever."""
        await self.start()
        
        try:
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.stop()


async def create_proxy_server(config: Optional[ProxyConfig] = None) -> ProxyServer:
    """Factory function to create and start proxy server.""" 
    server = ProxyServer(config)
    await server.start()
    return server