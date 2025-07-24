"""
Task-specific workflow management for MCP Manager.

Manages automated multi-MCP workflows with suite-based server activation/deactivation,
configuration templates, and integration with AI curation recommendations.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from mcp_manager.core.models import Server, TaskCategory
from mcp_manager.core.suite_manager import suite_manager
from mcp_manager.utils.config import get_config
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class WorkflowConfig:
    """Configuration for a specific workflow."""
    
    def __init__(self, name: str, description: str, suite_ids: List[str], 
                 category: Optional[TaskCategory] = None,
                 auto_activate: bool = True, priority: int = 50):
        self.name = name
        self.description = description
        self.suite_ids = suite_ids
        self.category = category
        self.auto_activate = auto_activate
        self.priority = priority
        self.created_at = datetime.utcnow()
        self.last_used = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "suite_ids": self.suite_ids,
            "category": self.category.value if self.category else None,
            "auto_activate": self.auto_activate,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'WorkflowConfig':
        """Create from dictionary."""
        config = cls(
            name=data["name"],
            description=data["description"],
            suite_ids=data["suite_ids"],
            category=TaskCategory(data["category"]) if data.get("category") else None,
            auto_activate=data.get("auto_activate", True),
            priority=data.get("priority", 50)
        )
        
        if data.get("created_at"):
            config.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("last_used"):
            config.last_used = datetime.fromisoformat(data["last_used"])
            
        return config


class WorkflowManager:
    """
    Manages task-specific MCP configurations using AI-curated suites.
    
    Provides workflow automation for switching between different development contexts
    with appropriate MCP server configurations.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize workflow manager.
        
        Args:
            config_path: Path to workflow configuration file
        """
        self.config = get_config()
        self.config_path = config_path or self._get_default_config_path()
        self.workflows: Dict[str, WorkflowConfig] = {}
        self.active_workflow: Optional[str] = None
        
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing workflows
        self._load_workflows()
        
        logger.info("WorkflowManager initialized", extra={
            "config_path": str(self.config_path),
            "workflows_loaded": len(self.workflows)
        })
    
    def _get_default_config_path(self) -> Path:
        """Get default workflow configuration path."""
        return Path.home() / ".config" / "mcp-manager" / "workflows.json"
    
    def _load_workflows(self) -> None:
        """Load workflows from configuration file."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                
                # Load workflows
                for workflow_data in data.get("workflows", []):
                    workflow = WorkflowConfig.from_dict(workflow_data)
                    self.workflows[workflow.name] = workflow
                
                # Load active workflow
                self.active_workflow = data.get("active_workflow")
                
                logger.debug(f"Loaded {len(self.workflows)} workflows from config")
            
        except Exception as e:
            logger.warning(f"Failed to load workflows config: {e}")
            self.workflows = {}
            self.active_workflow = None
    
    def _save_workflows(self) -> bool:
        """Save workflows to configuration file."""
        try:
            data = {
                "workflows": [workflow.to_dict() for workflow in self.workflows.values()],
                "active_workflow": self.active_workflow,
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # Atomic write
            temp_path = self.config_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            temp_path.rename(self.config_path)
            logger.debug("Workflows configuration saved")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save workflows config: {e}")
            return False
    
    async def create_workflow(self, name: str, description: str, 
                            suite_ids: List[str], category: Optional[TaskCategory] = None,
                            auto_activate: bool = True, priority: int = 50) -> bool:
        """
        Create a new workflow configuration.
        
        Args:
            name: Workflow name
            description: Workflow description
            suite_ids: List of suite IDs to include
            category: Task category
            auto_activate: Whether to auto-activate suites
            priority: Workflow priority (1-100)
            
        Returns:
            True if created successfully
        """
        try:
            if name in self.workflows:
                logger.warning(f"Workflow '{name}' already exists")
                return False
            
            # Validate suite IDs exist
            for suite_id in suite_ids:
                suite = await suite_manager.get_suite(suite_id)
                if not suite:
                    logger.error(f"Suite '{suite_id}' not found")
                    return False
            
            # Create workflow
            workflow = WorkflowConfig(
                name=name,
                description=description,
                suite_ids=suite_ids,
                category=category,
                auto_activate=auto_activate,
                priority=priority
            )
            
            self.workflows[name] = workflow
            
            # Save to disk
            if self._save_workflows():
                logger.info(f"Created workflow '{name}' with {len(suite_ids)} suites")
                return True
            else:
                # Rollback
                del self.workflows[name]
                return False
                
        except Exception as e:
            logger.error(f"Failed to create workflow '{name}': {e}")
            return False
    
    async def activate_workflow(self, workflow_name: str) -> bool:
        """
        Activate a workflow, switching MCP server configuration.
        
        Args:
            workflow_name: Name of workflow to activate
            
        Returns:
            True if activated successfully
        """
        try:
            if workflow_name not in self.workflows:
                logger.error(f"Workflow '{workflow_name}' not found")
                return False
            
            workflow = self.workflows[workflow_name]
            
            logger.info(f"Activating workflow '{workflow_name}'")
            
            # Deactivate current workflow if any
            if self.active_workflow and self.active_workflow != workflow_name:
                await self._deactivate_current_workflow()
            
            # Activate suites in the workflow
            activated_suites = []
            for suite_id in workflow.suite_ids:
                if await self.activate_suite(suite_id):
                    activated_suites.append(suite_id)
                else:
                    logger.warning(f"Failed to activate suite '{suite_id}'")
            
            if activated_suites:
                # Update workflow state
                workflow.last_used = datetime.utcnow()
                self.active_workflow = workflow_name
                
                # Save state
                self._save_workflows()
                
                logger.info(f"Activated workflow '{workflow_name}' with {len(activated_suites)} suites")
                return True
            else:
                logger.error(f"Failed to activate any suites for workflow '{workflow_name}'")
                return False
                
        except Exception as e:
            logger.error(f"Failed to activate workflow '{workflow_name}': {e}")
            return False
    
    async def _deactivate_current_workflow(self) -> None:
        """Deactivate the currently active workflow."""
        if not self.active_workflow or self.active_workflow not in self.workflows:
            return
        
        try:
            current_workflow = self.workflows[self.active_workflow]
            logger.info(f"Deactivating current workflow '{self.active_workflow}'")
            
            # Deactivate all suites in the current workflow
            for suite_id in current_workflow.suite_ids:
                await self.deactivate_suite(suite_id)
            
        except Exception as e:
            logger.error(f"Failed to deactivate current workflow: {e}")
    
    async def activate_suite(self, suite_id: str) -> bool:
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
            
            logger.info(f"Activated suite '{suite_id}': {activated_count}/{len(suite.servers)} servers")
            return activated_count > 0
            
        except Exception as e:
            logger.error(f"Failed to activate suite '{suite_id}': {e}")
            return False
    
    async def deactivate_suite(self, suite_id: str) -> bool:
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
            
            logger.info(f"Deactivated suite '{suite_id}': {deactivated_count}/{len(suite.servers)} servers")
            return deactivated_count > 0
            
        except Exception as e:
            logger.error(f"Failed to deactivate suite '{suite_id}': {e}")
            return False
    
    async def switch_workflow(self, task_category: TaskCategory) -> Optional[str]:
        """
        Switch to AI-recommended suite for specific task.
        
        Args:
            task_category: Task category to switch to
            
        Returns:
            Name of activated workflow, or None if failed
        """
        try:
            logger.info(f"Switching to workflow for task category: {task_category.value}")
            
            # Find workflows matching the task category
            matching_workflows = [
                name for name, workflow in self.workflows.items()
                if workflow.category == task_category
            ]
            
            if not matching_workflows:
                logger.warning(f"No workflows found for task category: {task_category.value}")
                return None
            
            # Sort by priority (highest first)
            matching_workflows.sort(key=lambda name: self.workflows[name].priority, reverse=True)
            best_workflow = matching_workflows[0]
            
            # Activate the best matching workflow
            if await self.activate_workflow(best_workflow):
                logger.info(f"Switched to workflow '{best_workflow}' for {task_category.value}")
                return best_workflow
            else:
                logger.error(f"Failed to activate workflow '{best_workflow}'")
                return None
                
        except Exception as e:
            logger.error(f"Failed to switch workflow for {task_category.value}: {e}")
            return None
    
    async def create_workflow_template(self, name: str, servers: List[str], 
                                     category: Optional[TaskCategory] = None) -> bool:
        """
        Create reusable workflow template from server list.
        
        Args:
            name: Template name
            servers: List of server names
            category: Task category
            
        Returns:
            True if created successfully
        """
        try:
            logger.info(f"Creating workflow template '{name}' with {len(servers)} servers")
            
            # Check if servers exist
            from mcp_manager.core.simple_manager import SimpleMCPManager
            manager = SimpleMCPManager()
            existing_servers = {s.name for s in manager.list_servers_fast()}
            
            missing_servers = set(servers) - existing_servers
            if missing_servers:
                logger.error(f"Servers not found: {missing_servers}")
                return False
            
            # Create a suite for this template
            suite_id = f"template-{name.lower().replace(' ', '-')}"
            description = f"Workflow template: {name}"
            
            # Create suite
            success = await suite_manager.create_or_update_suite(
                suite_id, name, description, category.value if category else "general"
            )
            
            if not success:
                logger.error(f"Failed to create suite for template '{name}'")
                return False
            
            # Add servers to suite
            for server_name in servers:
                await suite_manager.add_server_to_suite(suite_id, server_name, role="member", priority=50)
            
            # Create workflow
            return await self.create_workflow(
                name=name,
                description=f"Workflow template for {category.value if category else 'general'} tasks",
                suite_ids=[suite_id],
                category=category,
                auto_activate=True,
                priority=70  # Templates get medium-high priority
            )
            
        except Exception as e:
            logger.error(f"Failed to create workflow template '{name}': {e}")
            return False
    
    def list_workflows(self, category: Optional[TaskCategory] = None) -> List[WorkflowConfig]:
        """
        List available workflows, optionally filtered by category.
        
        Args:
            category: Optional category filter
            
        Returns:
            List of workflow configurations
        """
        if category:
            return [w for w in self.workflows.values() if w.category == category]
        else:
            return list(self.workflows.values())
    
    def get_workflow(self, name: str) -> Optional[WorkflowConfig]:
        """Get workflow by name."""
        return self.workflows.get(name)
    
    def get_active_workflow(self) -> Optional[WorkflowConfig]:
        """Get currently active workflow."""
        if self.active_workflow:
            return self.workflows.get(self.active_workflow)
        return None
    
    async def delete_workflow(self, name: str) -> bool:
        """
        Delete a workflow.
        
        Args:
            name: Workflow name to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            if name not in self.workflows:
                logger.error(f"Workflow '{name}' not found")
                return False
            
            # Deactivate if it's the active workflow
            if self.active_workflow == name:
                await self._deactivate_current_workflow()
                self.active_workflow = None
            
            # Remove workflow
            del self.workflows[name]
            
            # Save state
            if self._save_workflows():
                logger.info(f"Deleted workflow '{name}'")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete workflow '{name}': {e}")
            return False


# Global workflow manager instance
workflow_manager = WorkflowManager()