"""
Workflow activation and deactivation management.

Handles the orchestration of MCP server suites for workflow transitions,
including proper priority-based activation and graceful deactivation.
"""

from typing import Dict, List, Optional, Set

from mcp_manager.core.models import TaskCategory
from mcp_manager.core.suite_manager import suite_manager
from mcp_manager.core.workflows.models import WorkflowConfig
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ActivationManager:
    """Manages workflow activation and deactivation operations."""
    
    def __init__(self):
        """Initialize activation manager."""
        self._active_suites: Set[str] = set()
        logger.debug("ActivationManager initialized")
    
    async def activate_workflow(self, workflow: WorkflowConfig, 
                              current_active_workflow: Optional[WorkflowConfig] = None) -> bool:
        """
        Activate a workflow by enabling its suites and servers.
        
        Args:
            workflow: Workflow configuration to activate
            current_active_workflow: Currently active workflow to deactivate first
            
        Returns:
            True if activated successfully
        """
        try:
            logger.info(f"Activating workflow '{workflow.name}'")
            
            # Deactivate current workflow if different
            if (current_active_workflow and 
                current_active_workflow.name != workflow.name):
                await self.deactivate_workflow(current_active_workflow)
            
            # Validate suite IDs exist
            for suite_id in workflow.suite_ids:
                suite = await suite_manager.get_suite(suite_id)
                if not suite:
                    logger.error(f"Suite '{suite_id}' not found for workflow '{workflow.name}'")
                    return False
            
            # Activate suites in the workflow
            activated_suites = []
            for suite_id in workflow.suite_ids:
                if await self._activate_suite(suite_id):
                    activated_suites.append(suite_id)
                    self._active_suites.add(suite_id)
                else:
                    logger.warning(f"Failed to activate suite '{suite_id}' in workflow '{workflow.name}'")
            
            if activated_suites:
                # Mark workflow as used
                workflow.mark_used()
                
                logger.info(f"Activated workflow '{workflow.name}' with {len(activated_suites)} suites")
                return True
            else:
                logger.error(f"Failed to activate any suites for workflow '{workflow.name}'")
                return False
                
        except Exception as e:
            logger.error(f"Failed to activate workflow '{workflow.name}': {e}")
            return False
    
    async def deactivate_workflow(self, workflow: WorkflowConfig) -> bool:
        """
        Deactivate a workflow by disabling its suites and servers.
        
        Args:
            workflow: Workflow configuration to deactivate
            
        Returns:
            True if deactivated successfully
        """
        try:
            if not workflow:
                return True
            
            logger.info(f"Deactivating workflow '{workflow.name}'")
            
            # Deactivate all suites in the workflow
            deactivated_suites = []
            for suite_id in workflow.suite_ids:
                if await self._deactivate_suite(suite_id):
                    deactivated_suites.append(suite_id)
                    self._active_suites.discard(suite_id)
                else:
                    logger.warning(f"Failed to deactivate suite '{suite_id}' in workflow '{workflow.name}'")
            
            logger.info(f"Deactivated workflow '{workflow.name}' with {len(deactivated_suites)} suites")
            return True
            
        except Exception as e:
            logger.error(f"Failed to deactivate workflow '{workflow.name}': {e}")
            return False
    
    async def _activate_suite(self, suite_id: str) -> bool:
        """
        Activate all servers in a suite with proper priorities.
        
        Args:
            suite_id: Suite ID to activate
            
        Returns:
            True if activated successfully
        """
        try:
            # Get suite and its servers
            suite = await suite_manager.get_suite(suite_id)
            if not suite:
                logger.error(f"Suite '{suite_id}' not found")
                return False
            
            logger.debug(f"Activating suite '{suite_id}' with {len(suite.memberships)} servers")
            
            # Import SimpleMCPManager for server operations
            from mcp_manager.core.simple_manager import SimpleMCPManager
            manager = SimpleMCPManager()
            
            activated_count = 0
            
            # Activate servers based on priority (highest first)
            servers_by_priority = sorted(suite.memberships, key=lambda s: s.priority, reverse=True)
            
            for suite_server in servers_by_priority:
                try:
                    # Get the actual server
                    servers = manager.list_servers_fast() 
                    actual_server = next((s for s in servers if s.name == suite_server.server_name), None)
                    
                    if actual_server:
                        # Enable the server
                        if manager.enable_server(suite_server.server_name):
                            activated_count += 1
                            logger.debug(f"Activated server '{suite_server.server_name}' (priority: {suite_server.priority})")
                        else:
                            logger.warning(f"Failed to activate server '{suite_server.server_name}'")
                    else:
                        logger.warning(f"Server '{suite_server.server_name}' not found in registry")
                        
                except Exception as e:
                    logger.error(f"Failed to activate server '{suite_server.server_name}': {e}")
                    continue
            
            success = activated_count > 0
            if success:
                logger.info(f"Activated suite '{suite_id}': {activated_count}/{len(suite.memberships)} servers")
            else:
                logger.error(f"Failed to activate any servers in suite '{suite_id}'")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to activate suite '{suite_id}': {e}")
            return False
    
    async def _deactivate_suite(self, suite_id: str) -> bool:
        """
        Deactivate all servers in a suite.
        
        Args:
            suite_id: Suite ID to deactivate
            
        Returns:
            True if deactivated successfully
        """
        try:
            # Get suite and its servers
            suite = await suite_manager.get_suite(suite_id)
            if not suite:
                logger.error(f"Suite '{suite_id}' not found")
                return False
            
            logger.debug(f"Deactivating suite '{suite_id}' with {len(suite.memberships)} servers")
            
            # Import SimpleMCPManager for server operations
            from mcp_manager.core.simple_manager import SimpleMCPManager
            manager = SimpleMCPManager()
            
            deactivated_count = 0
            
            for suite_server in suite.memberships:
                try:
                    if manager.disable_server(suite_server.server_name):
                        deactivated_count += 1
                        logger.debug(f"Deactivated server '{suite_server.server_name}'")
                    else:
                        logger.warning(f"Failed to deactivate server '{suite_server.server_name}'")
                        
                except Exception as e:
                    logger.error(f"Failed to deactivate server '{suite_server.server_name}': {e}")
                    continue
            
            success = deactivated_count > 0 or len(suite.memberships) == 0
            if success:
                logger.info(f"Deactivated suite '{suite_id}': {deactivated_count}/{len(suite.memberships)} servers")
            else:
                logger.error(f"Failed to deactivate any servers in suite '{suite_id}'")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to deactivate suite '{suite_id}': {e}")
            return False
    
    async def switch_to_category_workflow(self, workflows: Dict[str, WorkflowConfig], 
                                        task_category: TaskCategory,
                                        current_active: Optional[str] = None) -> Optional[str]:
        """
        Switch to the best workflow for a specific task category.
        
        Args:
            workflows: Available workflows
            task_category: Task category to switch to
            current_active: Currently active workflow name
            
        Returns:
            Name of activated workflow, or None if failed
        """
        try:
            logger.info(f"Switching to workflow for task category: {task_category.value}")
            
            # Find workflows matching the task category
            matching_workflows = [
                name for name, workflow in workflows.items()
                if workflow.category == task_category
            ]
            
            if not matching_workflows:
                logger.warning(f"No workflows found for task category: {task_category.value}")
                return None
            
            # Sort by priority (highest first), then by last used (most recent first)
            matching_workflows.sort(
                key=lambda name: (
                    workflows[name].priority,
                    workflows[name].last_used or workflows[name].created_at
                ),
                reverse=True
            )
            
            best_workflow_name = matching_workflows[0]
            best_workflow = workflows[best_workflow_name]
            
            # Get current active workflow for deactivation
            current_workflow = workflows.get(current_active) if current_active else None
            
            # Activate the best matching workflow
            if await self.activate_workflow(best_workflow, current_workflow):
                logger.info(f"Switched to workflow '{best_workflow_name}' for {task_category.value}")
                return best_workflow_name
            else:
                logger.error(f"Failed to activate workflow '{best_workflow_name}'")
                return None
                
        except Exception as e:
            logger.error(f"Failed to switch workflow for {task_category.value}: {e}")
            return None
    
    def get_active_suites(self) -> Set[str]:
        """Get set of currently active suite IDs."""
        return self._active_suites.copy()
    
    async def deactivate_all(self) -> bool:
        """
        Deactivate all currently active suites.
        
        Returns:
            True if all suites deactivated successfully
        """
        try:
            if not self._active_suites:
                logger.debug("No active suites to deactivate")
                return True
            
            logger.info(f"Deactivating all {len(self._active_suites)} active suites")
            
            success_count = 0
            active_suites_copy = self._active_suites.copy()
            
            for suite_id in active_suites_copy:
                if await self._deactivate_suite(suite_id):
                    success_count += 1
                    self._active_suites.discard(suite_id)
            
            logger.info(f"Deactivated {success_count}/{len(active_suites_copy)} suites")
            return success_count == len(active_suites_copy)
            
        except Exception as e:
            logger.error(f"Failed to deactivate all suites: {e}")
            return False