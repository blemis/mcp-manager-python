"""Enhanced CLI commands with validation and better error handling."""

import asyncio
from typing import List, Optional

import click
from rich.console import Console
from rich.prompt import Confirm

from mcp_manager.core.exceptions import MCPManagerError, ValidationError
from mcp_manager.core.models import ServerScope, ServerType
from mcp_manager.utils import validators
from mcp_manager.utils.logging import get_logger

console = Console()
logger = get_logger(__name__)


def validate_and_add_server(
    manager,
    name: str,
    command: str,
    scope: str,
    server_type: str,
    description: Optional[str],
    env: List[str],
    args: List[str],
):
    """Add a server with validation."""
    # Validate server name
    try:
        validators.validate_server_name(name)
    except ValidationError as e:
        console.print(f"[red]✗[/red] {e}")
        
        # Suggest correction
        suggested = validators.suggest_server_name_correction(name)
        if suggested and suggested != name:
            console.print(f"[yellow]💡[/yellow] Did you mean: [cyan]{suggested}[/cyan]?")
            if Confirm.ask("Use suggested name?"):
                name = suggested
            else:
                raise click.Abort()
        else:
            raise click.Abort()
    
    # Validate command
    try:
        validators.validate_command(command, server_type)
    except ValidationError as e:
        console.print(f"[red]✗[/red] {e}")
        raise click.Abort()
    
    # Check server availability
    available, error_msg = validators.validate_server_availability(server_type, name)
    if not available:
        console.print(f"[red]✗[/red] {error_msg}")
        raise click.Abort()
    
    # Check if server already exists
    existing_servers = asyncio.run(manager.list_servers())
    if any(s.name == name for s in existing_servers):
        console.print(f"[yellow]⚠[/yellow] Server '{name}' already exists")
        if not Confirm.ask("Replace existing server?"):
            raise click.Abort()
    
    # Parse and validate environment variables
    env_dict = {}
    for env_var in env:
        if "=" not in env_var:
            console.print(f"[red]✗[/red] Invalid environment variable format: {env_var}")
            console.print("[yellow]💡[/yellow] Expected format: KEY=VALUE")
            raise click.Abort()
            
        key, value = env_var.split("=", 1)
        env_dict[key] = value
    
    # Create server
    try:
        server = asyncio.run(
            manager.add_server(
                name=name,
                server_type=ServerType(server_type),
                command=command,
                description=description,
                env=env_dict if env_dict else None,
                args=list(args) if args else None,
                scope=ServerScope(scope),
            )
        )
        console.print(f"[green]✓[/green] Added server: {server.name} ({server.scope.value})")
        
        # Provide helpful next steps
        console.print("\n[dim]Next steps:[/dim]")
        console.print(f"  • Enable the server: [cyan]mcp-manager enable {name}[/cyan]")
        console.print(f"  • Sync with Claude: [cyan]mcp-manager sync[/cyan]")
        
    except MCPManagerError as e:
        console.print(f"[red]✗[/red] Failed to add server: {e}")
        raise click.Abort()


def validate_and_remove_server(
    manager,
    name: str,
    scope: Optional[str],
    force: bool = False,
):
    """Remove a server with validation and confirmation."""
    # Check if server exists
    servers = asyncio.run(manager.list_servers())
    server = next((s for s in servers if s.name == name), None)
    
    if not server:
        console.print(f"[red]✗[/red] Server '{name}' not found")
        
        # Suggest similar servers
        similar = [s.name for s in servers if name.lower() in s.name.lower()]
        if similar:
            console.print("\n[yellow]💡[/yellow] Did you mean one of these?")
            for s in similar[:5]:
                console.print(f"  • {s}")
        raise click.Abort()
    
    # Confirm removal unless forced
    if not force:
        console.print(f"\n[yellow]⚠[/yellow] About to remove server: [bold]{server.name}[/bold]")
        console.print(f"  Type: {server.server_type.value}")
        console.print(f"  Command: {server.command}")
        if server.enabled:
            console.print("  [yellow]Status: ENABLED[/yellow]")
        
        if not Confirm.ask("\nRemove this server?"):
            console.print("[dim]Cancelled[/dim]")
            raise click.Abort()
    
    # Remove server
    try:
        scope_filter = ServerScope(scope) if scope else None
        removed = asyncio.run(manager.remove_server(name, scope_filter))
        
        if removed:
            console.print(f"[green]✓[/green] Removed server: {name}")
            
            if server.enabled:
                console.print("\n[yellow]💡[/yellow] The server was enabled. Don't forget to:")
                console.print(f"  • Sync with Claude: [cyan]mcp-manager sync[/cyan]")
        else:
            console.print(f"[red]✗[/red] Failed to remove server")
            
    except MCPManagerError as e:
        console.print(f"[red]✗[/red] Failed to remove server: {e}")
        raise click.Abort()


def validate_and_enable_server(manager, name: str):
    """Enable a server with validation."""
    # Check if server exists
    servers = asyncio.run(manager.list_servers())
    server = next((s for s in servers if s.name == name), None)
    
    if not server:
        console.print(f"[red]✗[/red] Server '{name}' not found")
        
        # Suggest similar servers
        similar = [s.name for s in servers if name.lower() in s.name.lower()]
        if similar:
            console.print("\n[yellow]💡[/yellow] Did you mean one of these?")
            for s in similar[:5]:
                console.print(f"  • {s}")
        raise click.Abort()
    
    if server.enabled:
        console.print(f"[yellow]ℹ[/yellow] Server '{name}' is already enabled")
        return
    
    # Check dependencies
    available, error_msg = validators.validate_server_availability(
        server.server_type.value,
        server.name
    )
    if not available:
        console.print(f"[red]✗[/red] Cannot enable server: {error_msg}")
        raise click.Abort()
    
    # Enable server
    try:
        asyncio.run(manager.enable_server(name))
        console.print(f"[green]✓[/green] Enabled server: {name}")
        
        console.print("\n[yellow]💡[/yellow] Don't forget to sync with Claude:")
        console.print(f"  [cyan]mcp-manager sync[/cyan]")
        
    except MCPManagerError as e:
        console.print(f"[red]✗[/red] Failed to enable server: {e}")
        raise click.Abort()


def validate_and_disable_server(manager, name: str):
    """Disable a server with validation."""
    # Check if server exists
    servers = asyncio.run(manager.list_servers())
    server = next((s for s in servers if s.name == name), None)
    
    if not server:
        console.print(f"[red]✗[/red] Server '{name}' not found")
        
        # Suggest similar servers
        similar = [s.name for s in servers if name.lower() in s.name.lower()]
        if similar:
            console.print("\n[yellow]💡[/yellow] Did you mean one of these?")
            for s in similar[:5]:
                console.print(f"  • {s}")
        raise click.Abort()
    
    if not server.enabled:
        console.print(f"[yellow]ℹ[/yellow] Server '{name}' is already disabled")
        return
    
    # Disable server
    try:
        asyncio.run(manager.disable_server(name))
        console.print(f"[green]✓[/green] Disabled server: {name}")
        
        console.print("\n[yellow]💡[/yellow] Don't forget to sync with Claude:")
        console.print(f"  [cyan]mcp-manager sync[/cyan]")
        
    except MCPManagerError as e:
        console.print(f"[red]✗[/red] Failed to disable server: {e}")
        raise click.Abort()