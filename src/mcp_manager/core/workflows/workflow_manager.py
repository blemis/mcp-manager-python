"""
Main workflow manager orchestration.

Provides the primary interface for workflow management, coordinating between
configuration persistence, activation management, and template operations.
"""

from pathlib import Path
from typing import Dict, List, Optional

from mcp_manager.core.models import TaskCategory
from mcp_manager.core.workflows.activation_manager import ActivationManager
from mcp_manager.core.workflows.config_persistence import ConfigPersistence
from mcp_manager.core.workflows.models import WorkflowConfig
from mcp_manager.core.workflows.template_manager import TemplateManager
from mcp_manager.utils.config import get_config
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class WorkflowManager:
    """
    Main workflow manager for task-specific MCP configurations.
    
    Orchestrates workflow operations using AI-curated suites and provides
    automation for switching between different development contexts.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize workflow manager.
        
        Args:
            config_path: Path to workflow configuration file
        """
        self.config = get_config()
        
        # Initialize components
        self.persistence = ConfigPersistence(config_path)
        self.activation = ActivationManager()
        self.templates = TemplateManager()
        
        # State management
        self.workflows: Dict[str, WorkflowConfig] = {}
        self.active_workflow: Optional[str] = None
        
        # Load existing workflows
        self._load_workflows()
        
        logger.info("WorkflowManager initialized", extra={
            "config_path": str(self.persistence.config_path),
            "workflows_loaded": len(self.workflows)
        })
    
    def _load_workflows(self) -> None:
        """Load workflows from persistent storage."""
        try:
            workflows, active_workflow = self.persistence.load_workflows()
            self.workflows = workflows
            self.active_workflow = active_workflow
            
            logger.debug(f"Loaded {len(self.workflows)} workflows, active: {self.active_workflow}")
            
        except Exception as e:
            logger.error(f"Failed to load workflows: {e}")
            self.workflows = {}
            self.active_workflow = None
    
    def _save_workflows(self) -> bool:
        """Save workflows to persistent storage."""
        return self.persistence.save_workflows(self.workflows, self.active_workflow)
    
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
            from mcp_manager.core.suite_manager import suite_manager
            for suite_id in suite_ids:
                suite = await suite_manager.get_suite(suite_id)
                if not suite:
                    logger.error(f"Suite '{suite_id}' not found")
                    return False
            
            # Create workflow configuration
            workflow = WorkflowConfig(
                name=name,
                description=description,
                suite_ids=suite_ids,
                category=category,
                auto_activate=auto_activate,
                priority=priority
            )
            
            # Add to workflows
            self.workflows[name] = workflow
            
            # Save to disk
            if self._save_workflows():
                logger.info(f"Created workflow '{name}' with {len(suite_ids)} suites")
                return True
            else:
                # Rollback on save failure
                del self.workflows[name]
                logger.error(f"Failed to save workflow '{name}', rolled back")
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
            current_workflow = self.workflows.get(self.active_workflow) if self.active_workflow else None
            
            # Use activation manager to handle the activation
            success = await self.activation.activate_workflow(workflow, current_workflow)
            
            if success:
                # Update active workflow state
                self.active_workflow = workflow_name
                
                # Save state
                self._save_workflows()
                
                logger.info(f"Successfully activated workflow '{workflow_name}'")
                return True
            else:
                logger.error(f"Failed to activate workflow '{workflow_name}'")
                return False
                
        except Exception as e:
            logger.error(f"Failed to activate workflow '{workflow_name}': {e}")
            return False
    
    async def switch_workflow(self, task_category: TaskCategory) -> Optional[str]:
        """
        Switch to AI-recommended workflow for specific task category.
        
        Args:
            task_category: Task category to switch to
            
        Returns:
            Name of activated workflow, or None if failed
        """
        try:
            activated_workflow = await self.activation.switch_to_category_workflow(
                self.workflows, task_category, self.active_workflow
            )
            
            if activated_workflow:
                self.active_workflow = activated_workflow
                self._save_workflows()
                return activated_workflow
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to switch workflow for {task_category.value}: {e}")
            return None
    
    async def create_workflow_template(self, name: str, servers: List[str], 
                                     category: Optional[TaskCategory] = None,
                                     description: Optional[str] = None,
                                     priority: int = 70) -> bool:
        """
        Create reusable workflow template from server list.
        
        Args:
            name: Template name
            servers: List of server names
            category: Task category
            description: Custom description
            priority: Template priority
            
        Returns:
            True if created successfully
        """
        try:
            if name in self.workflows:
                logger.warning(f"Template '{name}' already exists")
                return False
            
            # Create template using template manager
            workflow = await self.templates.create_workflow_template(
                name, servers, category, description, priority
            )
            
            if workflow:
                # Add to workflows
                self.workflows[name] = workflow
                
                # Save to disk
                if self._save_workflows():
                    logger.info(f"Created workflow template '{name}'")
                    return True
                else:
                    # Rollback
                    del self.workflows[name]
                    return False
            else:
                return False
                
        except Exception as e:
            logger.error(f"Failed to create workflow template '{name}': {e}")
            return False
    
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
            
            workflow = self.workflows[name]
            
            # Deactivate if it's the active workflow
            if self.active_workflow == name:
                await self.activation.deactivate_workflow(workflow)
                self.active_workflow = None
            
            # If it's a template, clean up associated suite
            if self.templates.is_template_workflow(workflow):
                await self.templates.delete_template(workflow)
            
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
        """
        Get workflow by name.
        
        Args:
            name: Workflow name
            
        Returns:
            WorkflowConfig if found, None otherwise
        """
        return self.workflows.get(name)
    
    def get_active_workflow(self) -> Optional[WorkflowConfig]:
        """
        Get currently active workflow.
        
        Returns:
            Active WorkflowConfig if any, None otherwise
        """
        if self.active_workflow:
            return self.workflows.get(self.active_workflow)
        return None
    
    async def deactivate_current_workflow(self) -> bool:
        """
        Deactivate the currently active workflow.
        
        Returns:
            True if deactivated successfully
        """
        try:
            if not self.active_workflow:
                logger.debug("No active workflow to deactivate")
                return True
            
            workflow = self.workflows.get(self.active_workflow)
            if not workflow:
                logger.warning(f"Active workflow '{self.active_workflow}' not found in registry")
                self.active_workflow = None
                self._save_workflows()
                return True
            
            success = await self.activation.deactivate_workflow(workflow)
            
            if success:
                self.active_workflow = None
                self._save_workflows()
                logger.info(f"Deactivated workflow '{workflow.name}'")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to deactivate current workflow: {e}")
            return False
    
    def backup_configuration(self) -> bool:
        """
        Create a backup of the current workflow configuration.
        
        Returns:
            True if backup created successfully
        """
        return self.persistence.backup_config()
    
    def restore_from_backup(self, backup_path: Path) -> bool:
        """
        Restore workflow configuration from backup.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if restored successfully
        """
        success = self.persistence.restore_from_backup(backup_path)
        if success:
            # Reload workflows after restore
            self._load_workflows()
        return success
    
    def get_workflow_stats(self) -> Dict:
        """
        Get workflow statistics and status information.
        
        Returns:
            Dictionary with workflow statistics
        """
        try:
            # Count by category
            by_category = {}
            for workflow in self.workflows.values():
                category = workflow.category.value if workflow.category else "uncategorized"
                by_category[category] = by_category.get(category, 0) + 1
            
            # Find most recently used
            recent_workflows = sorted(
                [w for w in self.workflows.values() if w.last_used],
                key=lambda w: w.last_used,
                reverse=True
            )
            
            most_recent = recent_workflows[0].name if recent_workflows else None
            
            return {
                "total_workflows": len(self.workflows),
                "active_workflow": self.active_workflow,
                "by_category": by_category,
                "most_recent": most_recent,
                "template_count": sum(1 for w in self.workflows.values() 
                                    if self.templates.is_template_workflow(w)),
                "active_suites": list(self.activation.get_active_suites())
            }
            
        except Exception as e:
            logger.error(f"Failed to get workflow stats: {e}")
            return {"error": str(e)}


# Global workflow manager instance
workflow_manager = WorkflowManager()