"""
Data models for workflow management.

Defines the WorkflowConfig class and related data structures for managing
task-specific MCP configurations and workflow states.
"""

from datetime import datetime
from typing import Dict, List, Optional

from mcp_manager.core.models import TaskCategory
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class WorkflowConfig:
    """Configuration for a specific workflow."""
    
    def __init__(self, name: str, description: str, suite_ids: List[str], 
                 category: Optional[TaskCategory] = None,
                 auto_activate: bool = True, priority: int = 50):
        """
        Initialize workflow configuration.
        
        Args:
            name: Workflow name
            description: Workflow description
            suite_ids: List of suite IDs to include
            category: Task category
            auto_activate: Whether to auto-activate suites
            priority: Workflow priority (1-100)
        """
        self.name = name
        self.description = description
        self.suite_ids = suite_ids
        self.category = category
        self.auto_activate = auto_activate
        self.priority = priority
        self.created_at = datetime.utcnow()
        self.last_used = None
        
        # Validate inputs
        self._validate()
    
    def _validate(self) -> None:
        """Validate workflow configuration."""
        if not self.name or not self.name.strip():
            raise ValueError("Workflow name cannot be empty")
        
        if not self.description or not self.description.strip():
            raise ValueError("Workflow description cannot be empty")
        
        if not self.suite_ids:
            raise ValueError("Workflow must include at least one suite")
        
        if not (1 <= self.priority <= 100):
            raise ValueError("Priority must be between 1 and 100")
    
    def mark_used(self) -> None:
        """Mark workflow as recently used."""
        self.last_used = datetime.utcnow()
        logger.debug(f"Marked workflow '{self.name}' as used")
    
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
        """
        Create workflow configuration from dictionary.
        
        Args:
            data: Dictionary containing workflow data
            
        Returns:
            WorkflowConfig instance
            
        Raises:
            ValueError: If required fields are missing or invalid
            KeyError: If required keys are missing from data
        """
        try:
            # Validate required fields
            required_fields = ["name", "description", "suite_ids"]
            for field in required_fields:
                if field not in data:
                    raise KeyError(f"Missing required field: {field}")
            
            # Create workflow config
            config = cls(
                name=data["name"],
                description=data["description"],
                suite_ids=data["suite_ids"],
                category=TaskCategory(data["category"]) if data.get("category") else None,
                auto_activate=data.get("auto_activate", True),
                priority=data.get("priority", 50)
            )
            
            # Set timestamps if provided
            if data.get("created_at"):
                try:
                    config.created_at = datetime.fromisoformat(data["created_at"])
                except ValueError as e:
                    logger.warning(f"Invalid created_at timestamp: {e}")
                    # Keep default created_at
            
            if data.get("last_used"):
                try:
                    config.last_used = datetime.fromisoformat(data["last_used"])
                except ValueError as e:
                    logger.warning(f"Invalid last_used timestamp: {e}")
                    # Keep None for last_used
                    
            return config
            
        except Exception as e:
            logger.error(f"Failed to create WorkflowConfig from dict: {e}")
            raise
    
    def __str__(self) -> str:
        """String representation of workflow config."""
        category_str = f" ({self.category.value})" if self.category else ""
        return f"WorkflowConfig('{self.name}'{category_str}, {len(self.suite_ids)} suites, priority={self.priority})"
    
    def __repr__(self) -> str:
        """Detailed representation of workflow config."""
        return (f"WorkflowConfig(name='{self.name}', description='{self.description}', "
                f"suite_ids={self.suite_ids}, category={self.category}, "
                f"auto_activate={self.auto_activate}, priority={self.priority})")