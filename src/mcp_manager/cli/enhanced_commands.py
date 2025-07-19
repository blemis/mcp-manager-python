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


async def _get_docker_desktop_servers():
    """Get list of enabled Docker Desktop servers."""
    try:
        import yaml
        from pathlib import Path
        
        registry_path = Path.home() / ".docker" / "mcp" / "registry.yaml"
        if not registry_path.exists():
            return []
        
        with open(registry_path) as f:
            registry_data = yaml.safe_load(f)
        
        return list(registry_data.get("registry", {}).keys())
    except Exception:
        return []


async def _get_available_docker_desktop_servers(name: str):
    """Check if a server name is available in Docker Desktop catalog."""
    try:
        import subprocess
        import shutil
        
        # Discover docker path
        docker_path = shutil.which("docker") or "/opt/homebrew/bin/docker"
        
        result = subprocess.run(
            [docker_path, "mcp", "catalog", "show", "docker-mcp"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode == 0:
            # Check if the server name appears in the catalog
            return name.lower() in result.stdout.lower()
        
        return False
    except Exception:
        return False


def validate_and_add_server(
    manager,
    name: str,
    command: Optional[str],
    scope: str,
    server_type: str,
    description: Optional[str],
    env: List[str],
    args: List[str],
):
    """Add a server with validation."""
    # Auto-detect Docker Desktop servers if no command provided
    if command is None:
        if server_type == "docker-desktop":
            # For Docker Desktop servers, the command is auto-managed
            command = "docker-desktop-auto"
        else:
            # Check if this might be a Docker Desktop server by checking available servers
            docker_servers = asyncio.run(_get_available_docker_desktop_servers(name))
            if docker_servers:
                console.print(f"[yellow]💡[/yellow] '{name}' appears to be a Docker Desktop MCP server")
                if Confirm.ask("Add as Docker Desktop server?"):
                    server_type = "docker-desktop"
                    command = "docker-desktop-auto"
                else:
                    console.print(f"[red]✗[/red] Missing command for {server_type} server")
                    raise click.Abort()
            else:
                console.print(f"[red]✗[/red] Missing command for {server_type} server")
                console.print(f"[yellow]💡[/yellow] Use: mcp-manager add {name} <command>")
                raise click.Abort()
    
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
    
    # Validate command (skip for auto-detected Docker Desktop servers)
    if command != "docker-desktop-auto":
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
        console.print(f"  • Server is now active in Claude Code!")
        console.print(f"  • Check: [cyan]claude mcp list[/cyan]")
        
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
    # Check if this might be a Docker Desktop server
    docker_desktop_servers = asyncio.run(_get_docker_desktop_servers())
    if name in docker_desktop_servers:
        # Handle Docker Desktop server removal
        if not force and not Confirm.ask(f"Remove Docker Desktop server '{name}'?"):
            raise click.Abort()
        
        try:
            # This will disable in Docker Desktop and re-sync gateway
            success = asyncio.run(manager.remove_server(f"docker-desktop-{name}"))
            if success:
                console.print(f"[green]✓[/green] Removed Docker Desktop server: {name}")
                console.print("[dim]Docker gateway updated in Claude Code[/dim]")
                return
            else:
                console.print(f"[red]✗[/red] Failed to remove Docker Desktop server: {name}")
                raise click.Abort()
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to remove server: {e}")
            raise click.Abort()
    
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
            
            console.print("\n[green]✓[/green] Server removed from Claude Code!")
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
        
        console.print("\n[green]✓[/green] Server is now active in Claude Code!")
        
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
        
        console.print("\n[green]✓[/green] Server removed from Claude Code!")
        
    except MCPManagerError as e:
        console.print(f"[red]✗[/red] Failed to disable server: {e}")
        raise click.Abort()