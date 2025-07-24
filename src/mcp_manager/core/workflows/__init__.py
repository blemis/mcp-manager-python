"""
Workflow management module for MCP Manager.

This module provides focused, modular components for managing task-specific
MCP server configurations and workflow automation.
"""

from mcp_manager.core.workflows.models import WorkflowConfig
from mcp_manager.core.workflows.workflow_manager import WorkflowManager, workflow_manager

__all__ = [
    "WorkflowConfig",
    "WorkflowManager", 
    "workflow_manager"
]