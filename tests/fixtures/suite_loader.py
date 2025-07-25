"""
Suite loader/unloader for test environments.

Loads and unloads entire suites into/from the MCP manager for testing.
"""

import asyncio
from typing import Dict, List, Optional, Set
from pathlib import Path

from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.core.suites.suite_manager import SuiteManager
from mcp_manager.core.models import Server, ServerType, ServerScope
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class SuiteLoader:
    """Loads and unloads test suites into MCP manager."""
    
    def __init__(self, mcp_manager: SimpleMCPManager):
        """Initialize with MCP manager instance."""
        self.mcp_manager = mcp_manager
        test_db_path = Path(__file__).parent / "test_suites.db"
        self.suite_manager = SuiteManager(test_db_path)
        self.loaded_suites: Set[str] = set()
        self.deployed_servers: Dict[str, Server] = {}
    
    async def load_suite(self, suite_id: str) -> Dict[str, any]:
        """
        Load a suite and deploy all its servers to MCP manager.
        
        Args:
            suite_id: ID of the suite to load
            
        Returns:
            Dict with suite info and deployed servers
        """
        try:
            # Get suite from database
            suite = await self.suite_manager.get_suite(suite_id)
            if not suite:
                raise ValueError(f"Suite '{suite_id}' not found")
            
            print(f"📦 Loading test suite: {suite_id}")
            print(f"   Description: {suite.description}")
            print(f"   Total servers in suite: {len(suite.memberships)}")
            
            deployed_servers = {}
            
            # Deploy each server in the suite
            for membership in suite.memberships:
                server_name = membership.server_name
                config = membership.config_overrides
                
                try:
                    # Skip servers marked as non-existent (for negative testing)
                    if config.get("should_exist", True) is False:
                        print(f"   ⏭️  Skipping non-existent server: {server_name} (negative test)")
                        continue
                    
                    print(f"   ➕ Adding MCP server: {server_name}")
                    print(f"      Scope: {config.get('scope', 'user')}")
                    print(f"      Type: {config.get('type', 'custom')}")
                    print(f"      Command: {config.get('command', 'N/A')}")
                    
                    server = await self._create_and_deploy_server(server_name, config)
                    if server:
                        deployed_servers[server_name] = server
                        self.deployed_servers[server_name] = server
                        print(f"      ✅ Successfully deployed server: {server_name}")
                    else:
                        print(f"      ❌ Failed to deploy server: {server_name}")
                        
                except Exception as e:
                    # Log but continue - some servers may be expected to fail
                    if not config.get("expected_error"):
                        print(f"      ❌ Failed to deploy server {server_name}: {e}")
                        logger.warning(f"Failed to deploy server {server_name}: {e}")
                    else:
                        print(f"      ⚠️  Expected failure for server {server_name}: {e}")
                        logger.debug(f"Expected failure for server {server_name}: {e}")
            
            self.loaded_suites.add(suite_id)
            
            print(f"✅ Suite '{suite_id}' loaded successfully!")
            print(f"   Deployed: {len(deployed_servers)}/{len(suite.memberships)} servers")
            print()
            
            logger.info(f"Loaded suite '{suite_id}' with {len(deployed_servers)} servers")
            
            return {
                "suite_id": suite_id,
                "suite": suite,
                "deployed_servers": deployed_servers,
                "total_servers": len(suite.memberships),
                "successful_deployments": len(deployed_servers)
            }
            
        except Exception as e:
            print(f"❌ Failed to load suite '{suite_id}': {e}")
            logger.error(f"Failed to load suite '{suite_id}': {e}")
            raise
    
    async def unload_suite(self, suite_id: str) -> bool:
        """
        Unload a suite by removing all its servers from MCP manager.
        
        Args:
            suite_id: ID of the suite to unload
            
        Returns:
            True if successful
        """
        try:
            if suite_id not in self.loaded_suites:
                print(f"⚠️  Suite '{suite_id}' not currently loaded")
                logger.warning(f"Suite '{suite_id}' not currently loaded")
                return True
            
            # Get suite to know which servers to remove
            suite = await self.suite_manager.get_suite(suite_id)
            if not suite:
                print(f"⚠️  Suite '{suite_id}' not found in database")
                logger.warning(f"Suite '{suite_id}' not found in database")
                return True
            
            print(f"🗑️  Unloading test suite: {suite_id}")
            removed_count = 0
            
            # Remove each server that was deployed from this suite
            for membership in suite.memberships:
                server_name = membership.server_name
                
                if server_name in self.deployed_servers:
                    try:
                        print(f"   ➖ Removing MCP server: {server_name}")
                        server = self.deployed_servers[server_name]
                        success = self.mcp_manager.remove_server(server_name, server.scope)
                        if success:
                            del self.deployed_servers[server_name]
                            removed_count += 1
                            print(f"      ✅ Successfully removed server: {server_name}")
                        else:
                            print(f"      ⚠️  Server {server_name} may not have existed")
                    except Exception as e:
                        print(f"      ❌ Failed to remove server {server_name}: {e}")
                        logger.warning(f"Failed to remove server {server_name}: {e}")
            
            self.loaded_suites.discard(suite_id)
            
            print(f"✅ Suite '{suite_id}' unloaded successfully!")
            print(f"   Removed: {removed_count} servers")
            print()
            
            logger.info(f"Unloaded suite '{suite_id}', removed {removed_count} servers")
            return True
            
        except Exception as e:
            print(f"❌ Failed to unload suite '{suite_id}': {e}")
            logger.error(f"Failed to unload suite '{suite_id}': {e}")
            return False
    
    async def unload_all_suites(self) -> bool:
        """Unload all currently loaded suites."""
        try:
            suite_ids = list(self.loaded_suites)
            
            if not suite_ids:
                print("🧹 No test suites to unload")
                return True
            
            print(f"🧹 Unloading all test suites ({len(suite_ids)} total)")
            
            for suite_id in suite_ids:
                await self.unload_suite(suite_id)
            
            # Clean up any remaining deployed servers
            remaining_servers = list(self.deployed_servers.keys())
            if remaining_servers:
                print(f"🧹 Cleaning up {len(remaining_servers)} remaining servers")
                for server_name in remaining_servers:
                    try:
                        print(f"   ➖ Cleaning up server: {server_name}")
                        server = self.deployed_servers[server_name]
                        self.mcp_manager.remove_server(server_name, server.scope)
                        del self.deployed_servers[server_name]
                        print(f"      ✅ Cleaned up server: {server_name}")
                    except Exception as e:
                        print(f"      ⚠️  Failed to cleanup server {server_name}: {e}")
                        logger.warning(f"Failed to cleanup server {server_name}: {e}")
            
            self.loaded_suites.clear()
            self.deployed_servers.clear()
            
            print("✅ All test suites unloaded and cleaned up")
            print()
            
            logger.info("Unloaded all suites and cleaned up servers")
            return True
            
        except Exception as e:
            print(f"❌ Failed to unload all suites: {e}")
            logger.error(f"Failed to unload all suites: {e}")
            return False
    
    def get_suite_servers(self, suite_id: str) -> List[str]:
        """Get list of server names from a loaded suite."""
        if suite_id not in self.loaded_suites:
            return []
        
        return [
            name for name, server in self.deployed_servers.items()
            # We'd need to track which suite each server came from
            # For now, return all deployed servers
        ]
    
    def get_loaded_suites(self) -> List[str]:
        """Get list of currently loaded suite IDs."""
        return list(self.loaded_suites)
    
    async def _create_and_deploy_server(self, server_name: str, config: Dict) -> Optional[Server]:
        """Create and deploy a server from suite configuration."""
        try:
            # Handle name override for testing invalid names
            actual_name = config.get("test_name_override", server_name)
            
            # Convert scope string to enum
            scope_str = config.get("scope", "user")
            scope = ServerScope.USER if scope_str == "user" else ServerScope.PROJECT
            
            # Convert type string to enum
            type_str = config.get("type", "custom")
            server_type = getattr(ServerType, type_str.upper(), ServerType.CUSTOM)
            
            # Create server object
            server = Server(
                name=actual_name,
                command=config.get("command", ""),
                args=config.get("args", []),
                env=config.get("env", {}),
                server_type=server_type,
                scope=scope,
                enabled=config.get("enabled", True),
                working_dir=config.get("working_dir"),
                description=config.get("description", f"Test server from suite")
            )
            
            # Deploy to MCP manager
            success = await self.mcp_manager.add_server(
                name=server.name,
                server_type=server.server_type,  
                command=server.command,
                args=server.args,
                env=server.env,
                scope=server.scope,
                working_dir=server.working_dir,
                description=server.description
            )
            
            if success:
                logger.debug(f"Successfully deployed server: {server.name}")
                return server
            else:
                logger.warning(f"Failed to deploy server: {server.name}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating/deploying server {server_name}: {e}")
            # Re-raise if this wasn't an expected error
            if not config.get("expected_error"):
                raise
            return None