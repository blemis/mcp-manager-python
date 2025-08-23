"""
Intelligent context detection for MCP Manager.

This module provides automatic detection of:
- Project vs User scope
- Current working context
- Configuration file locations
- Smart scope resolution with user prompts when ambiguous
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from rich.console import Console
from rich.prompt import Confirm, Prompt

from mcp_manager.core.models import ServerScope

console = Console()


@dataclass
class MCPContext:
    """Represents the current MCP context."""
    scope: ServerScope
    project_path: Optional[Path] = None
    config_file: Optional[Path] = None
    is_explicit: bool = False  # True if user explicitly specified scope
    confidence: float = 1.0  # 0.0 to 1.0, how confident we are in this detection
    
    @property
    def scope_name(self) -> str:
        return self.scope.value if self.scope else "unknown"
    
    @property
    def description(self) -> str:
        if self.scope == ServerScope.PROJECT:
            return f"Project scope ({self.project_path})"
        elif self.scope == ServerScope.USER:
            return "User scope (global)"
        else:
            return "Local scope (mcp-manager only)"


class ContextDetector:
    """Intelligent context detection for MCP operations."""
    
    def __init__(self):
        self.current_dir = Path.cwd()
        self.home_dir = Path.home()
        
    def detect_context(self, explicit_scope: Optional[str] = None, interactive: bool = True) -> MCPContext:
        """
        Detect the appropriate MCP context.
        
        Args:
            explicit_scope: User-specified scope override
            interactive: Whether to prompt user for clarification
            
        Returns:
            MCPContext with detected scope and configuration
        """
        # Handle explicit scope override
        if explicit_scope:
            try:
                scope = ServerScope(explicit_scope.lower())
                return MCPContext(
                    scope=scope,
                    project_path=self.current_dir if scope == ServerScope.PROJECT else None,
                    is_explicit=True,
                    confidence=1.0
                )
            except ValueError:
                console.print(f"[red]Invalid scope '{explicit_scope}'. Using auto-detection.[/red]")
        
        # Detect possible contexts
        contexts = self._detect_all_contexts()
        
        if not contexts:
            # No project context found, default to user
            return MCPContext(
                scope=ServerScope.USER,
                confidence=0.8
            )
        
        if len(contexts) == 1:
            # Single context found, use it
            return contexts[0]
        
        # Multiple contexts found - need user input
        if interactive:
            return self._resolve_ambiguous_context(contexts)
        else:
            # Non-interactive - use highest confidence
            return max(contexts, key=lambda c: c.confidence)
    
    def _detect_all_contexts(self) -> List[MCPContext]:
        """Detect all possible MCP contexts."""
        contexts = []
        
        # 1. Check for .mcp.json in current directory
        current_mcp = self.current_dir / ".mcp.json"
        if current_mcp.exists():
            contexts.append(MCPContext(
                scope=ServerScope.PROJECT,
                project_path=self.current_dir,
                config_file=current_mcp,
                confidence=1.0
            ))
        
        # 2. Check for .mcp.json in parent directories (git repo root, etc.)
        parent_context = self._find_parent_project()
        if parent_context:
            contexts.append(parent_context)
        
        # 3. Check Claude's internal state for project configs
        claude_context = self._check_claude_project_context()
        if claude_context:
            contexts.append(claude_context)
        
        # 4. Check for git repository with MCP configuration
        git_context = self._check_git_project_context()
        if git_context:
            contexts.append(git_context)
        
        return contexts
    
    def _find_parent_project(self) -> Optional[MCPContext]:
        """Find .mcp.json in parent directories."""
        current = self.current_dir.parent
        
        while current != current.parent:  # Stop at filesystem root
            mcp_file = current / ".mcp.json"
            if mcp_file.exists():
                return MCPContext(
                    scope=ServerScope.PROJECT,
                    project_path=current,
                    config_file=mcp_file,
                    confidence=0.8
                )
            current = current.parent
        
        return None
    
    def _check_claude_project_context(self) -> Optional[MCPContext]:
        """Check if Claude has project-specific servers for current path."""
        claude_config = self.home_dir / ".claude.json"
        if not claude_config.exists():
            return None
        
        try:
            with open(claude_config, 'r') as f:
                config = json.load(f)
            
            project_configs = config.get("projectConfigs", {})
            current_path_str = str(self.current_dir)
            
            # Check exact path match
            if current_path_str in project_configs:
                project_data = project_configs[current_path_str]
                if project_data.get("mcpServers"):
                    return MCPContext(
                        scope=ServerScope.PROJECT,
                        project_path=self.current_dir,
                        confidence=0.9
                    )
            
            # Check if current path is under any configured project
            for project_path, project_data in project_configs.items():
                if current_path_str.startswith(project_path + "/"):
                    if project_data.get("mcpServers"):
                        return MCPContext(
                            scope=ServerScope.PROJECT,
                            project_path=Path(project_path),
                            confidence=0.7
                        )
        
        except (json.JSONDecodeError, Exception):
            pass
        
        return None
    
    def _check_git_project_context(self) -> Optional[MCPContext]:
        """Check for git repository with MCP configuration."""
        git_root = self._find_git_root()
        if not git_root:
            return None
        
        mcp_file = git_root / ".mcp.json"
        if mcp_file.exists():
            return MCPContext(
                scope=ServerScope.PROJECT,
                project_path=git_root,
                config_file=mcp_file,
                confidence=0.6
            )
        
        return None
    
    def _find_git_root(self) -> Optional[Path]:
        """Find the root of the current git repository."""
        current = self.current_dir
        
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        
        return None
    
    def _resolve_ambiguous_context(self, contexts: List[MCPContext]) -> MCPContext:
        """Prompt user to resolve ambiguous context."""
        console.print("\n[yellow]⚠️ Multiple MCP contexts detected![/yellow]")
        console.print("Please choose which context to use:\n")
        
        for i, context in enumerate(contexts, 1):
            confidence_bar = "█" * int(context.confidence * 10) + "░" * (10 - int(context.confidence * 10))
            console.print(f"  {i}. {context.description}")
            console.print(f"     Confidence: {confidence_bar} {context.confidence:.1%}")
            if context.config_file:
                console.print(f"     Config: {context.config_file}")
            console.print()
        
        # Add user scope option
        contexts.append(MCPContext(scope=ServerScope.USER, confidence=1.0))
        console.print(f"  {len(contexts)}. User scope (global)")
        console.print(f"     Confidence: ██████████ 100%")
        console.print(f"     Config: ~/.config/claude-code/mcp-servers.json\n")
        
        while True:
            try:
                choice = Prompt.ask(
                    "Select context",
                    choices=[str(i) for i in range(1, len(contexts) + 1)],
                    default="1"
                )
                return contexts[int(choice) - 1]
            except (ValueError, IndexError):
                console.print("[red]Invalid choice. Please try again.[/red]")
    
    def get_config_paths(self, context: MCPContext) -> Dict[str, Optional[Path]]:
        """Get all relevant configuration file paths for a context."""
        paths = {
            "claude_internal": self.home_dir / ".claude.json",
            "user_config": self.home_dir / ".config" / "claude-code" / "mcp-servers.json",
            "project_config": None,
            "manager_db": self.home_dir / ".config" / "mcp-manager" / "mcp_manager.db"
        }
        
        if context.scope == ServerScope.PROJECT and context.project_path:
            paths["project_config"] = context.project_path / ".mcp.json"
        
        return paths
    
    def should_sync_databases(self, context: MCPContext) -> bool:
        """Determine if databases need synchronization for this context."""
        # Always sync if we detected context issues
        return context.confidence < 1.0 or not context.is_explicit