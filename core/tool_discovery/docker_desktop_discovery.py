"""
Docker Desktop MCP server tool discovery service.

Discovers tools from Docker Desktop enabled MCP servers using the
docker-gateway unified proxy interface.
"""

import asyncio
import json
from typing import Any, Dict, List

from mcp_manager.core.models import Server, ServerType
from mcp_manager.core.tool_discovery.base import BaseToolDiscovery, ToolDiscoveryResult
from mcp_manager.core.tool_discovery_logger import performance_timer


class DockerDesktopToolDiscovery(BaseToolDiscovery):
    """Tool discovery service for Docker Desktop MCP servers."""
    
    def can_handle_server(self, server: Server) -> bool:
        """Check if this service can handle Docker Desktop servers."""
        return (server.server_type == ServerType.DOCKER_DESKTOP or
                server.name == "docker-gateway" or
                (server.args and any("docker-gateway" in str(arg).lower() for arg in server.args)))
    
    async def validate_server_connection(self, server: Server) -> bool:
        """Validate that Docker Desktop and docker-gateway are available."""
        try:
            # Check if docker mcp is available
            result = await asyncio.create_subprocess_exec(
                "docker", "mcp", "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.wait()
            
            success = result.returncode == 0
            self.logger.log_server_connection(server.name, "docker_desktop", success)
            return success
            
        except Exception as e:
            self.logger.discovery_logger.log_discovery_error(
                server.name, e, context={"validation_step": "docker_desktop_check"}
            )
            return False
    
    async def discover_tools(self, server: Server) -> ToolDiscoveryResult:
        """
        Discover tools from Docker Desktop servers via docker-gateway.
        
        Args:
            server: Docker Desktop server configuration
            
        Returns:
            ToolDiscoveryResult with discovered tools
        """
        operation_id = self.logger.log_discovery_start(server.name, server.server_type)
        
        result = ToolDiscoveryResult(
            server_name=server.name,
            server_type=server.server_type,
            discovery_duration_seconds=0.0,
            success=False
        )
        
        try:
            with performance_timer("docker_desktop_tool_discovery", self.logger) as timing:
                # Validate server is accessible
                if not await self.validate_server_connection(server):
                    result.errors.append("Docker Desktop MCP is not available")
                    return result
                
                # Get enabled Docker Desktop servers
                enabled_servers = await self._get_enabled_dd_servers()
                
                if not enabled_servers:
                    result.warnings.append("No Docker Desktop MCP servers are enabled")
                    result.success = True  # Not an error, just no servers
                    return result
                
                # Discover tools from all enabled servers via docker-gateway
                all_tools = await self._discover_tools_via_docker_gateway(server, enabled_servers)
                
                # Convert to ToolRegistry entries
                for tool_info in all_tools:
                    try:
                        # Use the source server name for tool identification
                        source_server = tool_info.get("source_server", server.name)
                        
                        tool_registry = self.create_tool_registry_entry(
                            server=server,
                            tool_name=tool_info["name"],
                            tool_description=tool_info.get("description", ""),
                            tool_schema=tool_info.get("inputSchema", {}),
                            categories=None,  # Will be inferred
                            tags=None        # Will be inferred
                        )
                        
                        # Override canonical name to include source server
                        tool_registry.canonical_name = f"{source_server}/{tool_info['name']}"
                        tool_registry.server_name = source_server
                        
                        result.tools_discovered.append(tool_registry)
                        
                        self.logger.log_tool_found(
                            tool_info["name"], source_server, 
                            tool_info.get("inputSchema", {}), operation_id
                        )
                        
                    except Exception as e:
                        result.warnings.append(f"Failed to process tool {tool_info.get('name', 'unknown')}: {e}")
                
                result.success = True
                result.discovery_duration_seconds = timing.get("duration_seconds", 0.0)
                
                # Add metadata
                result.metadata = {
                    "discovery_method": "docker_gateway",
                    "enabled_dd_servers": enabled_servers,
                    "tools_per_second": len(result.tools_discovered) / max(result.discovery_duration_seconds, 0.001)
                }
        
        except Exception as e:
            self.logger.log_discovery_error(server.name, e, operation_id)
            result.errors.append(f"Discovery failed: {e}")
            result.success = False
        
        finally:
            self.logger.log_discovery_performance(
                server.name, len(result.tools_discovered), operation_id
            )
        
        return result
    
    async def _get_enabled_dd_servers(self) -> List[str]:
        """
        Get list of enabled Docker Desktop MCP servers.
        
        Returns:
            List of enabled server names
        """
        try:
            # Get enabled servers using docker mcp server list
            process = await asyncio.create_subprocess_exec(
                "docker", "mcp", "server", "list", "--format", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config.timeout_seconds
            )
            
            if process.returncode != 0:
                self.logger.logger.warning(f"Failed to list Docker Desktop servers: {stderr.decode()}")
                return []
            
            # Parse the JSON output
            servers_data = json.loads(stdout.decode())
            enabled_servers = []
            
            for server in servers_data:
                if server.get("enabled", False):
                    enabled_servers.append(server.get("name", "unknown"))
            
            return enabled_servers
            
        except asyncio.TimeoutError:
            self.logger.logger.warning("Timeout getting Docker Desktop server list")
            return []
        except json.JSONDecodeError as e:
            self.logger.logger.warning(f"Failed to parse Docker Desktop server list: {e}")
            return []
        except Exception as e:
            self.logger.logger.error(f"Error getting Docker Desktop servers: {e}")
            return []
    
    async def _discover_tools_via_docker_gateway(self, server: Server, enabled_servers: List[str]) -> List[Dict[str, Any]]:
        """
        Discover tools from enabled Docker Desktop servers via docker-gateway.
        
        Args:
            server: Docker gateway server configuration
            enabled_servers: List of enabled DD server names
            
        Returns:
            List of tool information dictionaries with source server info
        """
        try:
            # Build the docker-gateway command
            cmd = [server.command] + (server.args or [])
            if not cmd or cmd == [""]:
                # Default docker-gateway command
                cmd = ["docker", "mcp", "serve"]
            
            # MCP protocol initialization and tools request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "mcp-manager", "version": "1.0.0"}
                }
            }
            
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            # Prepare input for the subprocess
            requests = json.dumps(init_request) + "\n" + json.dumps(tools_request) + "\n"
            
            # Execute the docker-gateway
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=server.working_dir
            )
            
            # Send requests and get response
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=requests.encode('utf-8')),
                timeout=self.config.timeout_seconds
            )
            
            if process.returncode != 0:
                raise Exception(f"Docker gateway exited with code {process.returncode}: {stderr.decode()}")
            
            # Parse response lines
            response_lines = stdout.decode('utf-8').strip().split('\n')
            tools = []
            
            for line in response_lines:
                if not line.strip():
                    continue
                    
                try:
                    response = json.loads(line)
                    
                    # Look for tools/list response
                    if (response.get("id") == 2 and 
                        "result" in response and 
                        "tools" in response["result"]):
                        
                        tools_data = response["result"]["tools"]
                        for tool in tools_data:
                            # Try to infer source server from tool name or description
                            source_server = self._infer_source_server(tool, enabled_servers)
                            
                            parsed_tool = {
                                "name": tool.get("name", "unknown"),
                                "description": tool.get("description", ""),
                                "inputSchema": self._parse_mcp_tool_parameters(tool.get("inputSchema", {})),
                                "source_server": source_server
                            }
                            tools.append(parsed_tool)
                        break
                        
                except json.JSONDecodeError:
                    # Skip non-JSON lines (might be debug output)
                    continue
            
            return tools
            
        except asyncio.TimeoutError:
            raise Exception(f"Docker gateway discovery timed out after {self.config.timeout_seconds} seconds")
        except Exception as e:
            raise Exception(f"Docker gateway communication failed: {e}")
    
    def _infer_source_server(self, tool: Dict[str, Any], enabled_servers: List[str]) -> str:
        """
        Infer which Docker Desktop server provides this tool.
        
        Args:
            tool: Tool information from docker-gateway
            enabled_servers: List of enabled DD server names
            
        Returns:
            Inferred source server name
        """
        tool_name = tool.get("name", "").lower()
        tool_description = tool.get("description", "").lower()
        
        # Map tool patterns to known Docker Desktop servers
        server_patterns = {
            "sqlite": ["sql", "database", "query", "table"],
            "filesystem": ["file", "directory", "read", "write", "path"],  
            "search": ["search", "find", "query", "index"],
            "http": ["http", "request", "web", "api", "url"],
            "k8s": ["kubernetes", "k8s", "pod", "deployment", "cluster"],
            "terraform": ["terraform", "tf", "infrastructure", "resource"],
            "aws": ["aws", "amazon", "s3", "ec2", "lambda"]
        }
        
        # Check if tool name directly matches a server
        for server in enabled_servers:
            if server.lower() in tool_name or tool_name.startswith(server.lower()):
                return server
        
        # Check patterns in tool name and description
        text_to_check = f"{tool_name} {tool_description}"
        
        for server, patterns in server_patterns.items():
            if server in enabled_servers:
                if any(pattern in text_to_check for pattern in patterns):
                    return server
        
        # Default to first enabled server or generic name
        return enabled_servers[0] if enabled_servers else "docker-desktop"
    
    def _parse_mcp_tool_parameters(self, input_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse MCP tool input schema into standardized format.
        
        Args:
            input_schema: Raw input schema from MCP server
            
        Returns:
            Standardized parameter schema
        """
        if not input_schema:
            return {}
        
        # Handle different schema formats
        if "properties" in input_schema:
            # JSON Schema format
            parameters = []
            properties = input_schema["properties"]
            required = input_schema.get("required", [])
            
            for param_name, param_info in properties.items():
                parameter = {
                    "name": param_name,
                    "type": param_info.get("type", "string"),
                    "description": param_info.get("description", ""),
                    "required": param_name in required
                }
                
                # Add additional constraints
                if "enum" in param_info:
                    parameter["enum"] = param_info["enum"]
                if "default" in param_info:
                    parameter["default"] = param_info["default"]
                
                parameters.append(parameter)
            
            return {
                "type": "object",
                "properties": properties,
                "required": required,
                "parameters": parameters  # Flattened format for easier processing
            }
        
        # Return as-is if already in expected format
        return input_schema