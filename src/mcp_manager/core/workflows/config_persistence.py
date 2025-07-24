"""
Configuration persistence for workflow management.

Handles loading and saving workflow configurations to/from disk with atomic
operations and proper error handling.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mcp_manager.core.workflows.models import WorkflowConfig
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigPersistence:
    """Handles workflow configuration persistence operations."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration persistence handler.
        
        Args:
            config_path: Path to workflow configuration file
        """
        self.config_path = config_path or self._get_default_config_path()
        
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"ConfigPersistence initialized with path: {self.config_path}")
    
    def _get_default_config_path(self) -> Path:
        """Get default workflow configuration path."""
        return Path.home() / ".config" / "mcp-manager" / "workflows.json"
    
    def load_workflows(self) -> Tuple[Dict[str, WorkflowConfig], Optional[str]]:
        """
        Load workflows from configuration file.
        
        Returns:
            Tuple of (workflow_dict, active_workflow_name)
        """
        workflows: Dict[str, WorkflowConfig] = {}
        active_workflow: Optional[str] = None
        
        try:
            if not self.config_path.exists():
                logger.debug("No existing workflow configuration found")
                return workflows, active_workflow
            
            # Read configuration file
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            
            # Validate file structure
            if not isinstance(data, dict):
                logger.error("Invalid workflow configuration format: not a dictionary")
                return workflows, active_workflow
            
            # Load workflows
            workflow_data_list = data.get("workflows", [])
            if not isinstance(workflow_data_list, list):
                logger.error("Invalid workflows format: not a list")
                return workflows, active_workflow
            
            loaded_count = 0
            for workflow_data in workflow_data_list:
                try:
                    workflow = WorkflowConfig.from_dict(workflow_data)
                    workflows[workflow.name] = workflow
                    loaded_count += 1
                except Exception as e:
                    logger.error(f"Failed to load workflow from data {workflow_data}: {e}")
                    continue
            
            # Load active workflow
            active_workflow = data.get("active_workflow")
            if active_workflow and active_workflow not in workflows:
                logger.warning(f"Active workflow '{active_workflow}' not found in loaded workflows")
                active_workflow = None
            
            logger.info(f"Loaded {loaded_count} workflows from configuration")
            
            return workflows, active_workflow
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in workflow configuration: {e}")
            return workflows, active_workflow
        except Exception as e:
            logger.error(f"Failed to load workflow configuration: {e}")
            return workflows, active_workflow
    
    def save_workflows(self, workflows: Dict[str, WorkflowConfig], 
                      active_workflow: Optional[str] = None) -> bool:
        """
        Save workflows to configuration file using atomic write.
        
        Args:
            workflows: Dictionary of workflows to save
            active_workflow: Name of currently active workflow
            
        Returns:
            True if saved successfully
        """
        try:
            # Prepare data for serialization
            data = {
                "workflows": [workflow.to_dict() for workflow in workflows.values()],
                "active_workflow": active_workflow,
                "last_updated": datetime.utcnow().isoformat(),
                "version": "1.0"
            }
            
            # Validate active workflow
            if active_workflow and active_workflow not in workflows:
                logger.warning(f"Active workflow '{active_workflow}' not in workflows list")
                data["active_workflow"] = None
            
            # Atomic write using temporary file
            temp_path = self.config_path.with_suffix('.tmp')
            try:
                with open(temp_path, 'w') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # Atomic rename
                temp_path.rename(self.config_path)
                
                logger.debug(f"Saved {len(workflows)} workflows to configuration")
                return True
                
            except Exception as e:
                # Clean up temp file if it exists
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass
                raise e
                
        except Exception as e:
            logger.error(f"Failed to save workflow configuration: {e}")
            return False
    
    def backup_config(self) -> bool:
        """
        Create a backup of the current configuration.
        
        Returns:
            True if backup created successfully
        """
        try:
            if not self.config_path.exists():
                logger.debug("No configuration file to backup")
                return True
            
            # Create backup with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.config_path.with_suffix(f'.backup_{timestamp}')
            
            # Copy current config to backup
            import shutil
            shutil.copy2(self.config_path, backup_path)
            
            logger.info(f"Created configuration backup: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create configuration backup: {e}")
            return False
    
    def restore_from_backup(self, backup_path: Path) -> bool:
        """
        Restore configuration from a backup file.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if restored successfully
        """
        try:
            if not backup_path.exists():
                logger.error(f"Backup file not found: {backup_path}")
                return False
            
            # Validate backup file by trying to load it
            try:
                with open(backup_path, 'r') as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid backup file format: {e}")
                return False
            
            # Create backup of current config before restore
            if self.config_path.exists():
                self.backup_config()
            
            # Copy backup to current config
            import shutil
            shutil.copy2(backup_path, self.config_path)
            
            logger.info(f"Restored configuration from backup: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            return False
    
    def cleanup_old_backups(self, keep_count: int = 5) -> None:
        """
        Clean up old backup files, keeping only the most recent ones.
        
        Args:
            keep_count: Number of recent backups to keep
        """
        try:
            backup_dir = self.config_path.parent
            backup_pattern = f"{self.config_path.name}.backup_*"
            
            # Find all backup files
            backup_files = list(backup_dir.glob(backup_pattern))
            
            if len(backup_files) <= keep_count:
                return
            
            # Sort by modification time (newest first)
            backup_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            
            # Remove old backups
            for backup_file in backup_files[keep_count:]:
                try:
                    backup_file.unlink()
                    logger.debug(f"Removed old backup: {backup_file}")
                except Exception as e:
                    logger.warning(f"Failed to remove backup {backup_file}: {e}")
            
            logger.info(f"Cleaned up {len(backup_files) - keep_count} old backups")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")