"""
Docker-based MCP server tool discovery service.

Discovers tools from Docker-based MCP servers by executing them
and using MCP protocol communication to enumerate available tools.
"""

import asyncio
import json
import os
from typing import Any, Dict, List

from mcp_manager.core.models import Server, ServerType
from mcp_manager.core.tool_discovery.base import BaseToolDiscovery, ToolDiscoveryResult
from mcp_manager.core.tool_discovery_logger import performance_timer


class DockerToolDiscovery(BaseToolDiscovery):
    """Tool discovery service for Docker-based MCP servers."""
    
    def can_handle_server(self, server: Server) -> bool:
        """Check if this service can handle Docker-based servers."""
        return (server.server_type == ServerType.DOCKER or 
                server.command == "docker" or
                (server.args and any("docker" in arg.lower() for arg in server.args)))
    
    async def validate_server_connection(self, server: Server) -> bool:
        """Validate that Docker is available and container exists."""
        try:
            # Check if docker is available
            result = await asyncio.create_subprocess_exec(
                "docker", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.wait()
            
            if result.returncode != 0:
                self.logger.log_server_connection(server.name, "docker", False)
                return False
            
            # Extract container/image name from args
            container_name = self._extract_container_name(server)
            if container_name:
                # Check if container/image exists
                check_result = await asyncio.create_subprocess_exec(
                    "docker", "inspect", container_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await check_result.wait()
                
                if check_result.returncode != 0:
                    # Try as image name if container check failed
                    image_result = await asyncio.create_subprocess_exec(
                        "docker", "image", "inspect", container_name,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await image_result.wait()
                    
                    success = image_result.returncode == 0
                else:
                    success = True
            else:
                success = True  # Generic docker command
            
            self.logger.log_server_connection(server.name, "docker", success)
            return success
            
        except Exception as e:
            self.logger.discovery_logger.log_discovery_error(
                server.name, e, context={"validation_step": "docker_check"}
            )
            return False
    
    async def discover_tools(self, server: Server) -> ToolDiscoveryResult:
        """
        Discover tools from Docker-based MCP server using MCP protocol.
        
        Args:
            server: Docker server configuration
            
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
            with performance_timer("docker_tool_discovery", self.logger) as timing:
                # Validate server is accessible
                if not await self.validate_server_connection(server):
                    result.errors.append("Docker is not available or container/image cannot be accessed")
                    return result
                
                # Discover tools using MCP protocol
                tools = await self._discover_tools_via_mcp_protocol(server)
                
                # Convert to ToolRegistry entries
                for tool_info in tools:
                    try:
                        tool_registry = self.create_tool_registry_entry(
                            server=server,
                            tool_name=tool_info["name"],
                            tool_description=tool_info.get("description", ""),
                            tool_schema=tool_info.get("inputSchema", {}),
                            categories=None,  # Will be inferred
                            tags=None        # Will be inferred
                        )
                        result.tools_discovered.append(tool_registry)
                        
                        self.logger.log_tool_found(
                            tool_info["name"], server.name, 
                            tool_info.get("inputSchema", {}), operation_id
                        )
                        
                    except Exception as e:
                        result.warnings.append(f"Failed to process tool {tool_info.get('name', 'unknown')}: {e}")
                
                result.success = True if result.tools_discovered else len(result.errors) == 0
                result.discovery_duration_seconds = timing.get("duration_seconds", 0.0)
                
                # Add metadata
                result.metadata = {
                    "discovery_method": "mcp_protocol",
                    "server_command": server.command,
                    "server_args": server.args or [],
                    "container_name": self._extract_container_name(server),
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
    
    async def _discover_tools_via_mcp_protocol(self, server: Server) -> List[Dict[str, Any]]:
        """
        Discover tools by communicating with Docker server via MCP protocol.
        
        Args:
            server: Server configuration
            
        Returns:
            List of tool information dictionaries
        """
        try:
            # Build the command
            cmd = [server.command] + (server.args or [])
            
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
            
            # Execute the Docker server
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=server.working_dir,
                env={**os.environ, **(server.env or {})}
            )
            
            # Send requests and get response
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=requests.encode('utf-8')),
                timeout=self.config.timeout_seconds
            )
            
            if process.returncode != 0:
                raise Exception(f"Docker server exited with code {process.returncode}: {stderr.decode()}")
            
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
                            parsed_tool = {
                                "name": tool.get("name", "unknown"),
                                "description": tool.get("description", ""),
                                "inputSchema": self._parse_mcp_tool_parameters(tool.get("inputSchema", {}))
                            }
                            tools.append(parsed_tool)
                        break
                        
                except json.JSONDecodeError:
                    # Skip non-JSON lines (might be debug output)
                    continue
            
            return tools
            
        except asyncio.TimeoutError:
            raise Exception(f"Docker server discovery timed out after {self.config.timeout_seconds} seconds")
        except Exception as e:
            raise Exception(f"Docker server communication failed: {e}")
    
    def _extract_container_name(self, server: Server) -> str:
        """
        Extract container or image name from server configuration.
        
        Args:
            server: Server configuration
            
        Returns:
            Container/image name or empty string if not found
        """
        if not server.args:
            return ""
        
        # Look for common docker run patterns
        args = server.args
        
        # Find image name after 'run' command
        if "run" in args:
            run_index = args.index("run")
            # Image name is typically the last argument or after flags
            for i in range(run_index + 1, len(args)):
                arg = args[i]
                # Skip flags (start with -)
                if not arg.startswith("-"):
                    # This might be the image name
                    # Check if it looks like an image (contains : or /)
                    if ":" in arg or "/" in arg or not arg.startswith("-"):
                        return arg
        
        # Look for exec patterns
        if "exec" in args:
            exec_index = args.index("exec")
            if exec_index + 1 < len(args):
                return args[exec_index + 1]
        
        # Look for container/image names in args
        for arg in args:
            if not arg.startswith("-") and ("/" in arg or ":" in arg):
                return arg
        
        return ""
    
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