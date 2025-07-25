"""
IDE Connectivity Validation

Configurable system for validating MCP server connectivity across different IDEs.
Single responsibility: Test MCP server connectivity using IDE-specific commands.
"""

import asyncio
import subprocess
import json
from enum import Enum
from typing import Dict, List, Optional, Tuple, Protocol
from dataclasses import dataclass
from pathlib import Path

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class IDEType(Enum):
    """Supported IDE types for MCP connectivity testing."""
    CLAUDE_CODE = "claude-code"
    VS_CODE = "vscode"  # Future support
    JETBRAINS = "jetbrains"  # Future support
    CUSTOM = "custom"


@dataclass
class ConnectivityResult:
    """Result of MCP server connectivity test."""
    server_name: str
    connected: bool
    error_message: Optional[str] = None
    response_time_ms: Optional[float] = None
    ide_type: Optional[str] = None
    command_used: Optional[str] = None


class IDEConnectivityValidator(Protocol):
    """Protocol for IDE-specific connectivity validators."""
    
    async def validate_server(self, server_name: str, server_command: str) -> ConnectivityResult:
        """Validate connectivity for a single MCP server."""
        ...
    
    async def validate_all_servers(self) -> List[ConnectivityResult]:
        """Validate connectivity for all configured MCP servers."""
        ...


class ClaudeCodeValidator:
    """Validator for Claude Code MCP connectivity."""
    
    def __init__(self):
        self.ide_type = IDEType.CLAUDE_CODE
        
    async def validate_server(self, server_name: str, server_command: str) -> ConnectivityResult:
        """Validate connectivity for a single server using claude mcp list."""
        try:
            import time
            start_time = time.time()
            
            # Run claude mcp list to check connectivity
            result = await asyncio.create_subprocess_exec(
                "claude", "mcp", "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            if result.returncode != 0:
                return ConnectivityResult(
                    server_name=server_name,
                    connected=False,
                    error_message=f"claude mcp list failed: {stderr.decode()}",
                    response_time_ms=response_time,
                    ide_type=self.ide_type.value,
                    command_used="claude mcp list"
                )
            
            # Parse output to check if server is connected
            output = stdout.decode()
            
            # Look for server in output and check status
            if server_name in output:
                # Check if server shows as connected (✅) or failed (✗)
                lines = output.split('\n')
                for line in lines:
                    if server_name in line:
                        connected = "✅" in line or "✓" in line or "Connected" in line
                        failed = "✗" in line or "✘" in line or "Failed" in line
                        
                        if connected and not failed:
                            return ConnectivityResult(
                                server_name=server_name,
                                connected=True,
                                response_time_ms=response_time,
                                ide_type=self.ide_type.value,
                                command_used="claude mcp list"
                            )
                        else:
                            return ConnectivityResult(
                                server_name=server_name,
                                connected=False,
                                error_message="Server shows as failed in claude mcp list",
                                response_time_ms=response_time,
                                ide_type=self.ide_type.value,
                                command_used="claude mcp list"
                            )
            
            # Server not found in output
            return ConnectivityResult(
                server_name=server_name,
                connected=False,
                error_message="Server not found in claude mcp list output",
                response_time_ms=response_time,
                ide_type=self.ide_type.value,
                command_used="claude mcp list"
            )
            
        except Exception as e:
            return ConnectivityResult(
                server_name=server_name,
                connected=False,
                error_message=f"Exception during validation: {e}",
                ide_type=self.ide_type.value,
                command_used="claude mcp list"
            )
    
    async def validate_all_servers(self) -> List[ConnectivityResult]:
        """Validate connectivity for all servers configured in Claude Code."""
        try:
            # Get list of all servers from claude mcp list
            result = await asyncio.create_subprocess_exec(
                "claude", "mcp", "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                logger.error(f"Failed to get server list: {stderr.decode()}")
                return []
            
            # Parse server names from output
            output = stdout.decode()
            server_results = []
            
            lines = output.split('\n')
            for line in lines:
                # Look for server names in output (this is a simplified parser)
                if any(indicator in line for indicator in ["✅", "✗", "✓", "✘"]):
                    # Extract server name (this would need to be more robust)
                    parts = line.split()
                    if parts:
                        server_name = parts[0].rstrip(':')
                        connected = "✅" in line or "✓" in line
                        
                        server_results.append(ConnectivityResult(
                            server_name=server_name,
                            connected=connected,
                            error_message=None if connected else "Connection failed",
                            ide_type=self.ide_type.value,
                            command_used="claude mcp list"
                        ))
            
            return server_results
            
        except Exception as e:
            logger.error(f"Failed to validate all servers: {e}")
            return []


class VSCodeValidator:
    """Validator for VS Code MCP connectivity (future implementation)."""
    
    def __init__(self):
        self.ide_type = IDEType.VS_CODE
        
    async def validate_server(self, server_name: str, server_command: str) -> ConnectivityResult:
        """Validate connectivity for VS Code (not implemented yet)."""
        return ConnectivityResult(
            server_name=server_name,
            connected=False,
            error_message="VS Code validation not implemented yet",
            ide_type=self.ide_type.value,
            command_used="code --list-extensions"  # Placeholder
        )
    
    async def validate_all_servers(self) -> List[ConnectivityResult]:
        """Validate all servers for VS Code (not implemented yet)."""
        return []


class IDEConnectivityManager:
    """Manager for IDE-specific connectivity validation."""
    
    def __init__(self, ide_type: IDEType = IDEType.CLAUDE_CODE):
        self.ide_type = ide_type
        self.validator = self._create_validator()
    
    def _create_validator(self) -> IDEConnectivityValidator:
        """Create appropriate validator for the IDE type."""
        if self.ide_type == IDEType.CLAUDE_CODE:
            return ClaudeCodeValidator()
        elif self.ide_type == IDEType.VS_CODE:
            return VSCodeValidator()
        else:
            raise ValueError(f"Unsupported IDE type: {self.ide_type}")
    
    async def validate_server_connectivity(self, server_name: str, server_command: str) -> ConnectivityResult:
        """Validate connectivity for a specific server."""
        logger.debug(f"Validating {server_name} connectivity for {self.ide_type.value}")
        result = await self.validator.validate_server(server_name, server_command)
        
        # Log result
        if result.connected:
            logger.info(f"✅ {server_name} connected successfully ({result.response_time_ms:.1f}ms)")
        else:
            logger.warning(f"❌ {server_name} connection failed: {result.error_message}")
        
        return result
    
    async def validate_all_servers(self) -> List[ConnectivityResult]:
        """Validate connectivity for all servers."""
        logger.info(f"🔍 Validating all MCP servers for {self.ide_type.value}")
        results = await self.validator.validate_all_servers()
        
        connected_count = sum(1 for r in results if r.connected)
        total_count = len(results)
        
        logger.info(f"📊 Connectivity results: {connected_count}/{total_count} servers connected")
        return results
    
    async def get_quality_filtered_servers(self, min_quality_score: int = 50) -> List[ConnectivityResult]:
        """Get servers filtered by quality score and validate connectivity."""
        try:
            # Import quality system
            from ..quality.quality_manager import QualityManager
            
            quality_manager = QualityManager()
            quality_servers = await quality_manager.get_servers_by_quality(min_score=min_quality_score)
            
            # Validate connectivity for quality servers
            connectivity_results = []
            for server in quality_servers:
                result = await self.validate_server_connectivity(server.server_name, server.install_command)
                connectivity_results.append(result)
            
            return connectivity_results
            
        except Exception as e:
            logger.error(f"Failed to get quality filtered servers: {e}")
            return []


# Convenience functions for common IDE types
async def validate_claude_code_connectivity(server_name: str, server_command: str) -> ConnectivityResult:
    """Validate connectivity for Claude Code specifically."""
    manager = IDEConnectivityManager(IDEType.CLAUDE_CODE)
    return await manager.validate_server_connectivity(server_name, server_command)


async def validate_all_claude_code_servers() -> List[ConnectivityResult]:
    """Validate all Claude Code MCP servers."""
    manager = IDEConnectivityManager(IDEType.CLAUDE_CODE)
    return await manager.validate_all_servers()


# Configuration support
def get_ide_type_from_config() -> IDEType:
    """Get IDE type from configuration (defaults to Claude Code)."""
    try:
        from mcp_manager.utils.config import get_config
        config = get_config()
        ide_type_str = getattr(config, 'ide_type', 'claude-code')
        return IDEType(ide_type_str)
    except Exception:
        return IDEType.CLAUDE_CODE