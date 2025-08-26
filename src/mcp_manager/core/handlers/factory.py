"""
Server handler factory and routing system.

Provides a centralized way to get the appropriate handler for different
server types, implementing the polymorphic handler architecture.
"""

from typing import Dict, Type, Optional
from mcp_manager.core.models import Server, ServerType
from mcp_manager.core.handlers import ServerHandler
from mcp_manager.core.handlers.docker_desktop import DockerDesktopServerHandler
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DefaultServerHandler(ServerHandler):
    """
    Default handler for server types that don't have specialized handlers.
    
    This handles NPM, Docker, and Custom servers using basic subprocess
    operations and status tracking through the manager's internal state.
    """
    
    def __init__(self, manager=None):
        """
        Initialize default server handler.
        
        Args:
            manager: Reference to the main MCP manager for state operations
        """
        self.manager = manager
        logger.debug("DefaultServerHandler initialized")
    
    async def enable_server(self, server: Server) -> bool:
        """
        Enable server using manager's internal mechanisms.
        
        For NPM/Docker/Custom servers, this typically means updating
        the server's enabled state and syncing with Claude Code.
        """
        try:
            if self.manager:
                # Use manager's existing enable logic
                success = await self.manager._enable_server_internal(server)
                if success:
                    logger.info(f"Successfully enabled server: {server.name}")
                return success
            else:
                # Fallback - just mark as enabled
                logger.warning(f"No manager reference, marking server as enabled: {server.name}")
                return True
                
        except Exception as e:
            logger.error(f"Error enabling server {server.name}: {e}")
            return False
    
    async def disable_server(self, server: Server) -> bool:
        """
        Disable server using manager's internal mechanisms.
        """
        try:
            if self.manager:
                success = await self.manager._disable_server_internal(server)
                if success:
                    logger.info(f"Successfully disabled server: {server.name}")
                return success
            else:
                logger.warning(f"No manager reference, marking server as disabled: {server.name}")
                return True
                
        except Exception as e:
            logger.error(f"Error disabling server {server.name}: {e}")
            return False
    
    async def get_server_status(self, server: Server) -> str:
        """
        Get server status from manager's internal state.
        """
        try:
            if self.manager:
                # Use manager's existing status logic
                is_enabled = getattr(server, 'enabled', False)
                return 'enabled' if is_enabled else 'disabled'
            else:
                return 'unknown'
                
        except Exception as e:
            logger.error(f"Error getting status for server {server.name}: {e}")
            return 'error'
    
    async def is_server_available(self, server: Server) -> bool:
        """
        Check if server is available based on server type.
        """
        try:
            if server.server_type == ServerType.NPM:
                # Check if npm package is available
                return await self._check_npm_availability(server)
            elif server.server_type == ServerType.DOCKER:
                # Check if docker image is available
                return await self._check_docker_availability(server)
            else:
                # Custom servers are assumed available if they have a command
                return bool(server.command)
                
        except Exception as e:
            logger.error(f"Error checking availability of server {server.name}: {e}")
            return False
    
    async def _check_npm_availability(self, server: Server) -> bool:
        """Check if NPM package is available."""
        import subprocess
        try:
            # Try to get package info
            package_name = getattr(server, 'package', server.name)
            result = subprocess.run(
                ['npm', 'list', package_name, '--depth=0'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    
    async def _check_docker_availability(self, server: Server) -> bool:
        """Check if Docker image is available."""
        import subprocess
        try:
            # Extract image name from args
            image_name = None
            if server.args:
                for arg in server.args:
                    if '/' in arg or ':' in arg:  # Looks like an image reference
                        image_name = arg
                        break
            
            if not image_name:
                return False
            
            # Check if image exists locally
            result = subprocess.run(
                ['docker', 'image', 'inspect', image_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False


class ServerHandlerFactory:
    """
    Factory for creating and managing server handlers.
    
    Routes server operations to the appropriate specialized handler
    based on server type and characteristics.
    """
    
    def __init__(self, manager=None):
        """
        Initialize server handler factory.
        
        Args:
            manager: Reference to the main MCP manager
        """
        self.manager = manager
        self._handlers: Dict[Type[ServerHandler], ServerHandler] = {}
        self._docker_desktop_handler: Optional[DockerDesktopServerHandler] = None
        self._default_handler: Optional[DefaultServerHandler] = None
        
        logger.debug("ServerHandlerFactory initialized")
    
    async def get_handler(self, server: Server) -> ServerHandler:
        """
        Get the appropriate handler for a server.
        
        Args:
            server: Server to get handler for
            
        Returns:
            Appropriate server handler
        """
        # Check if it's a Docker Desktop server
        if self._is_docker_desktop_server(server):
            return await self._get_docker_desktop_handler()
        
        # Use default handler for other types
        return await self._get_default_handler()
    
    async def _get_docker_desktop_handler(self) -> DockerDesktopServerHandler:
        """Get or create Docker Desktop handler."""
        if self._docker_desktop_handler is None:
            self._docker_desktop_handler = DockerDesktopServerHandler()
            logger.debug("Created Docker Desktop handler")
        
        return self._docker_desktop_handler
    
    async def _get_default_handler(self) -> DefaultServerHandler:
        """Get or create default handler."""
        if self._default_handler is None:
            self._default_handler = DefaultServerHandler(manager=self.manager)
            logger.debug("Created default handler")
        
        return self._default_handler
    
    def _is_docker_desktop_server(self, server: Server) -> bool:
        """
        Check if server is a Docker Desktop MCP server.
        
        Args:
            server: Server to check
            
        Returns:
            True if this is a Docker Desktop server
        """
        # Check server type
        if server.server_type == ServerType.DOCKER_DESKTOP:
            return True
        
        # Check server name patterns
        if server.name.startswith('dd-'):
            return True
        
        # Check for docker-gateway in command/args
        if server.command == 'docker' and server.args:
            if 'mcp' in server.args and 'gateway' in server.args:
                return True
        
        # Check known Docker Desktop server names
        docker_desktop_servers = {
            'dd-SQLite', 'dd-Ref', 'dd-Search', 'dd-HTTP', 
            'dd-K8s', 'dd-Terraform', 'dd-AWS'
        }
        
        return server.name in docker_desktop_servers
    
    async def enable_server(self, server: Server) -> bool:
        """
        Enable a server using the appropriate handler.
        
        Args:
            server: Server to enable
            
        Returns:
            True if successfully enabled
        """
        handler = await self.get_handler(server)
        return await handler.enable_server(server)
    
    async def disable_server(self, server: Server) -> bool:
        """
        Disable a server using the appropriate handler.
        
        Args:
            server: Server to disable
            
        Returns:
            True if successfully disabled
        """
        handler = await self.get_handler(server)
        return await handler.disable_server(server)
    
    async def get_server_status(self, server: Server) -> str:
        """
        Get server status using the appropriate handler.
        
        Args:
            server: Server to check
            
        Returns:
            Status string
        """
        handler = await self.get_handler(server)
        return await handler.get_server_status(server)
    
    async def is_server_available(self, server: Server) -> bool:
        """
        Check if server is available using the appropriate handler.
        
        Args:
            server: Server to check
            
        Returns:
            True if server is available
        """
        handler = await self.get_handler(server)
        return await handler.is_server_available(server)
    
    async def close(self):
        """Close all handlers and cleanup resources."""
        if self._docker_desktop_handler:
            await self._docker_desktop_handler.close()
            self._docker_desktop_handler = None
        
        self._default_handler = None
        self._handlers.clear()
        
        logger.debug("ServerHandlerFactory closed")


# Global factory instance
_factory_instance: Optional[ServerHandlerFactory] = None


def get_server_handler_factory(manager=None) -> ServerHandlerFactory:
    """
    Get the global server handler factory instance.
    
    Args:
        manager: MCP manager reference (only used on first call)
        
    Returns:
        Server handler factory instance
    """
    global _factory_instance
    
    if _factory_instance is None:
        _factory_instance = ServerHandlerFactory(manager=manager)
        logger.debug("Created global ServerHandlerFactory instance")
    
    return _factory_instance


async def close_server_handler_factory():
    """Close the global server handler factory."""
    global _factory_instance
    
    if _factory_instance:
        await _factory_instance.close()
        _factory_instance = None
        logger.debug("Closed global ServerHandlerFactory")