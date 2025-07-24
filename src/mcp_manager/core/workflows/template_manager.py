"""
Workflow template management.

Handles creation and management of reusable workflow templates from server lists,
including suite creation and server validation.
"""

from typing import List, Optional, Set

from mcp_manager.core.models import TaskCategory
from mcp_manager.core.suite_manager import suite_manager
from mcp_manager.core.workflows.models import WorkflowConfig
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class TemplateManager:
    """Manages workflow template creation and operations."""
    
    def __init__(self):
        """Initialize template manager."""
        logger.debug("TemplateManager initialized")
    
    async def create_workflow_template(self, name: str, servers: List[str], 
                                     category: Optional[TaskCategory] = None,
                                     description: Optional[str] = None,
                                     priority: int = 70) -> Optional[WorkflowConfig]:
        """
        Create reusable workflow template from server list.
        
        Args:
            name: Template name
            servers: List of server names
            category: Task category
            description: Custom description (auto-generated if None)
            priority: Workflow priority (templates default to 70)
            
        Returns:
            WorkflowConfig if created successfully, None otherwise
        """
        try:
            logger.info(f"Creating workflow template '{name}' with {len(servers)} servers")
            
            # Validate inputs
            if not name or not name.strip():
                logger.error("Template name cannot be empty")
                return None
            
            if not servers:
                logger.error("Template must include at least one server")
                return None
            
            # Check if servers exist
            missing_servers = await self._validate_servers(servers)
            if missing_servers:
                logger.error(f"Servers not found: {missing_servers}")
                return None
            
            # Create a suite for this template
            suite_id = self._generate_suite_id(name)
            suite_description = f"Workflow template: {name}"
            
            # Create suite
            success = await suite_manager.create_or_update_suite(
                suite_id, 
                name, 
                suite_description, 
                category.value if category else "general"
            )
            
            if not success:
                logger.error(f"Failed to create suite for template '{name}'")
                return None
            
            # Add servers to suite with default priorities
            servers_added = await self._add_servers_to_suite(suite_id, servers)
            if not servers_added:
                logger.error(f"Failed to add servers to suite for template '{name}'")
                return None
            
            # Generate description if not provided
            if not description:
                category_desc = f" for {category.value}" if category else ""
                description = f"Workflow template{category_desc} tasks with {len(servers)} servers"
            
            # Create workflow configuration
            workflow = WorkflowConfig(
                name=name,
                description=description,
                suite_ids=[suite_id],
                category=category,
                auto_activate=True,
                priority=priority
            )
            
            logger.info(f"Created workflow template '{name}' with suite '{suite_id}'")
            return workflow
            
        except Exception as e:
            logger.error(f"Failed to create workflow template '{name}': {e}")
            return None
    
    async def _validate_servers(self, servers: List[str]) -> Set[str]:
        """
        Validate that servers exist in the registry.
        
        Args:
            servers: List of server names to validate
            
        Returns:
            Set of missing server names
        """
        try:
            from mcp_manager.core.simple_manager import SimpleMCPManager
            manager = SimpleMCPManager()
            existing_servers = {s.name for s in manager.list_servers_fast()}
            
            missing_servers = set(servers) - existing_servers
            
            if missing_servers:
                logger.warning(f"Missing servers: {missing_servers}")
            else:
                logger.debug(f"All {len(servers)} servers validated successfully")
            
            return missing_servers
            
        except Exception as e:
            logger.error(f"Failed to validate servers: {e}")
            # Return all servers as missing if validation fails
            return set(servers)
    
    def _generate_suite_id(self, template_name: str) -> str:
        """
        Generate a suite ID for a workflow template.
        
        Args:
            template_name: Name of the template
            
        Returns:
            Generated suite ID
        """
        # Convert to lowercase and replace spaces/special chars with hyphens
        import re
        safe_name = re.sub(r'[^a-zA-Z0-9\s]', '', template_name)
        safe_name = re.sub(r'\s+', '-', safe_name.strip()).lower()
        
        suite_id = f"template-{safe_name}"
        logger.debug(f"Generated suite ID '{suite_id}' for template '{template_name}'")
        return suite_id
    
    async def _add_servers_to_suite(self, suite_id: str, servers: List[str], 
                                  default_priority: int = 50) -> bool:
        """
        Add servers to a suite with default priorities.
        
        Args:
            suite_id: Suite ID to add servers to
            servers: List of server names
            default_priority: Default priority for servers
            
        Returns:
            True if all servers added successfully
        """
        try:
            added_count = 0
            
            for server_name in servers:
                try:
                    success = await suite_manager.add_server_to_suite(
                        suite_id, 
                        server_name, 
                        role="member", 
                        priority=default_priority
                    )
                    
                    if success:
                        added_count += 1
                        logger.debug(f"Added server '{server_name}' to suite '{suite_id}'")
                    else:
                        logger.warning(f"Failed to add server '{server_name}' to suite '{suite_id}'")
                        
                except Exception as e:
                    logger.error(f"Failed to add server '{server_name}' to suite '{suite_id}': {e}")
                    continue
            
            success = added_count == len(servers)
            logger.info(f"Added {added_count}/{len(servers)} servers to suite '{suite_id}'")
            return success
            
        except Exception as e:
            logger.error(f"Failed to add servers to suite '{suite_id}': {e}")
            return False
    
    async def update_template_servers(self, suite_id: str, new_servers: List[str]) -> bool:
        """
        Update the servers in a workflow template suite.
        
        Args:
            suite_id: Suite ID to update
            new_servers: New list of server names
            
        Returns:
            True if updated successfully
        """
        try:
            logger.info(f"Updating template suite '{suite_id}' with {len(new_servers)} servers")
            
            # Validate new servers exist
            missing_servers = await self._validate_servers(new_servers)
            if missing_servers:
                logger.error(f"Cannot update template - missing servers: {missing_servers}")
                return False
            
            # Get current suite
            suite = await suite_manager.get_suite(suite_id)
            if not suite:
                logger.error(f"Suite '{suite_id}' not found")
                return False
            
            # Get current server names
            current_servers = {membership.server_name for membership in suite.memberships}
            new_servers_set = set(new_servers)
            
            # Remove servers no longer needed
            servers_to_remove = current_servers - new_servers_set
            for server_name in servers_to_remove:
                await suite_manager.remove_server_from_suite(suite_id, server_name)
                logger.debug(f"Removed server '{server_name}' from suite '{suite_id}'")
            
            # Add new servers  
            servers_to_add = new_servers_set - current_servers
            for server_name in servers_to_add:
                await suite_manager.add_server_to_suite(suite_id, server_name, role="member", priority=50)
                logger.debug(f"Added server '{server_name}' to suite '{suite_id}'")
            
            logger.info(f"Updated suite '{suite_id}': removed {len(servers_to_remove)}, added {len(servers_to_add)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update template suite '{suite_id}': {e}")
            return False
    
    async def delete_template(self, workflow: WorkflowConfig) -> bool:
        """
        Delete a workflow template and its associated suite.
        
        Args:
            workflow: Workflow configuration to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            logger.info(f"Deleting workflow template '{workflow.name}'")
            
            # Delete associated suites (templates typically have one suite)
            deleted_suites = 0
            for suite_id in workflow.suite_ids:
                if suite_id.startswith("template-"):
                    success = await suite_manager.delete_suite(suite_id)
                    if success:
                        deleted_suites += 1
                        logger.debug(f"Deleted template suite '{suite_id}'")
                    else:
                        logger.warning(f"Failed to delete template suite '{suite_id}'")
            
            logger.info(f"Deleted template '{workflow.name}' with {deleted_suites} suites")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete template '{workflow.name}': {e}")
            return False
    
    def is_template_workflow(self, workflow: WorkflowConfig) -> bool:
        """
        Check if a workflow is a template (has template-prefixed suites).
        
        Args:
            workflow: Workflow to check
            
        Returns:
            True if workflow is a template
        """
        return any(suite_id.startswith("template-") for suite_id in workflow.suite_ids)
    
    async def get_template_servers(self, workflow: WorkflowConfig) -> List[str]:
        """
        Get the list of servers in a template workflow.
        
        Args:
            workflow: Template workflow
            
        Returns:
            List of server names in the template
        """
        try:
            all_servers = []
            
            for suite_id in workflow.suite_ids:
                suite = await suite_manager.get_suite(suite_id)
                if suite:
                    suite_servers = [membership.server_name for membership in suite.memberships]
                    all_servers.extend(suite_servers)
            
            # Remove duplicates while preserving order
            unique_servers = list(dict.fromkeys(all_servers))
            logger.debug(f"Template '{workflow.name}' has {len(unique_servers)} servers")
            return unique_servers
            
        except Exception as e:
            logger.error(f"Failed to get servers for template '{workflow.name}': {e}")
            return []