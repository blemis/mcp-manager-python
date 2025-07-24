"""
API server commands for MCP Manager CLI.

Manages the REST API server for external integrations and dashboard access.
"""

import os
import signal
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from mcp_manager.cli.helpers import handle_errors

console = Console()


def api_commands(cli_context):
    """Add API server commands to the CLI."""
    
    @click.group("api")
    def api():
        """Manage MCP Manager REST API server."""
        pass
    
    
    @api.command("start")
    @click.option("--host", "-h", default="127.0.0.1", help="API server host")
    @click.option("--port", "-p", default=8000, help="API server port")
    @click.option("--daemon", "-d", is_flag=True, help="Run as daemon process")
    @click.option("--log-level", default="info", help="Logging level")
    @handle_errors
    def api_start(host: str, port: int, daemon: bool, log_level: str):
        """Start the MCP Manager API server."""
        try:
            console.print(f"[blue]🚀 Starting MCP Manager API server...[/blue]")
            console.print(f"   Host: [cyan]{host}[/cyan]")
            console.print(f"   Port: [cyan]{port}[/cyan]")
            console.print(f"   Docs: [cyan]http://{host}:{port}/docs[/cyan]")
            
            if daemon:
                console.print("[yellow]⚠️  Daemon mode not yet implemented[/yellow]")
                console.print("[dim]Starting in foreground mode...[/dim]")
            
            from mcp_manager.api.server import create_api_server
            
            server = create_api_server()
            
            # Store server info for stop command
            _store_server_info(host, port, os.getpid())
            
            console.print("[green]✅ API server started successfully[/green]")
            console.print("[dim]Press Ctrl+C to stop[/dim]")
            
            server.run(host=host, port=port)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]🛑 API server stopped by user[/yellow]")
        except Exception as e:
            console.print(f"[red]❌ Failed to start API server: {e}[/red]")
    
    
    @api.command("stop")
    @handle_errors
    def api_stop():
        """Stop the running API server."""
        try:
            server_info = _get_server_info()
            if not server_info:
                console.print("[yellow]No running API server found[/yellow]")
                return
            
            pid = server_info.get('pid')
            if not pid:
                console.print("[yellow]No server PID found[/yellow]")
                return
            
            console.print(f"[blue]🛑 Stopping API server (PID: {pid})[/blue]")
            
            try:
                os.kill(pid, signal.SIGTERM)
                
                # Wait for process to stop
                for _ in range(10):
                    try:
                        os.kill(pid, 0)  # Check if process exists
                        time.sleep(0.5)
                    except ProcessLookupError:
                        break
                else:
                    # Force kill if still running
                    console.print("[yellow]Process not responding, force killing...[/yellow]")
                    os.kill(pid, signal.SIGKILL)
                
                _clear_server_info()
                console.print("[green]✅ API server stopped successfully[/green]")
                
            except ProcessLookupError:
                console.print("[yellow]API server was not running[/yellow]")
                _clear_server_info()
            except PermissionError:
                console.print("[red]Permission denied - cannot stop server[/red]")
                
        except Exception as e:
            console.print(f"[red]Failed to stop API server: {e}[/red]")
    
    
    @api.command("status")
    @handle_errors
    def api_status():
        """Show API server status."""
        try:
            server_info = _get_server_info()
            
            if not server_info:
                console.print("[yellow]🔴 API server is not running[/yellow]")
                return
            
            pid = server_info.get('pid')
            host = server_info.get('host', 'unknown')
            port = server_info.get('port', 'unknown')
            
            # Check if process is actually running
            try:
                os.kill(pid, 0)
                status = "[green]🟢 Running[/green]"
            except ProcessLookupError:
                status = "[red]🔴 Not running (stale PID)[/red]"
                _clear_server_info()
            
            console.print(f"[bold blue]📊 API Server Status[/bold blue]")
            console.print(f"Status: {status}")
            console.print(f"PID: [cyan]{pid}[/cyan]")
            console.print(f"Host: [cyan]{host}[/cyan]")
            console.print(f"Port: [cyan]{port}[/cyan]")
            console.print(f"Docs: [cyan]http://{host}:{port}/docs[/cyan]")
            console.print(f"Health: [cyan]http://{host}:{port}/health[/cyan]")
            
        except Exception as e:
            console.print(f"[red]Failed to get API server status: {e}[/red]")
    
    
    @api.command("test")
    @click.option("--host", "-h", default="127.0.0.1", help="API server host")
    @click.option("--port", "-p", default=8000, help="API server port")
    @handle_errors
    def api_test(host: str, port: int):
        """Test API server connectivity."""
        try:
            import httpx
            
            base_url = f"http://{host}:{port}"
            console.print(f"[blue]🧪 Testing API server at {base_url}[/blue]")
            
            with httpx.Client(timeout=10.0) as client:
                # Test health endpoint
                console.print("Testing health endpoint... ", end="")
                try:
                    response = client.get(f"{base_url}/health")
                    if response.status_code == 200:
                        console.print("[green]✅ OK[/green]")
                        
                        health_data = response.json()
                        console.print(f"  Status: [cyan]{health_data.get('status', 'unknown')}[/cyan]")
                        console.print(f"  Version: [cyan]{health_data.get('version', 'unknown')}[/cyan]")
                        console.print(f"  Database: [cyan]{health_data.get('database_status', 'unknown')}[/cyan]")
                    else:
                        console.print(f"[red]❌ {response.status_code}[/red]")
                except httpx.RequestError as e:
                    console.print(f"[red]❌ Connection failed: {e}[/red]")
                    return
                
                # Test docs endpoint
                console.print("Testing docs endpoint... ", end="")
                try:
                    response = client.get(f"{base_url}/docs")
                    if response.status_code == 200:
                        console.print("[green]✅ OK[/green]")
                    else:
                        console.print(f"[yellow]⚠️  {response.status_code}[/yellow]")
                except httpx.RequestError:
                    console.print("[red]❌ Failed[/red]")
                
                console.print(f"\n[green]✅ API server is responsive[/green]")
                console.print(f"[dim]📖 API documentation: {base_url}/docs[/dim]")
                
        except ImportError:
            console.print("[red]httpx library not available for testing[/red]")
        except Exception as e:
            console.print(f"[red]API test failed: {e}[/red]")
    
    
    @api.command("create-key")
    @click.argument("name")
    @click.option("--scopes", "-s", multiple=True, help="API key scopes")
    @click.option("--expires-days", type=int, help="Expiration in days")
    @handle_errors
    def api_create_key(name: str, scopes: tuple, expires_days: Optional[int]):
        """Create a new API key."""
        try:
            from mcp_manager.api.auth import AuthenticationManager
            
            auth_manager = AuthenticationManager()
            
            # Default scopes if none provided
            if not scopes:
                scopes = ["analytics:read", "tools:read", "servers:read"]
            
            console.print(f"[blue]🔑 Creating API key: {name}[/blue]")
            console.print(f"Scopes: [cyan]{', '.join(scopes)}[/cyan]")
            if expires_days:
                console.print(f"Expires: [cyan]{expires_days} days[/cyan]")
            
            api_key = auth_manager.create_api_key(
                name=name,
                scopes=list(scopes),
                expires_days=expires_days
            )
            
            console.print(f"\n[green]✅ API key created successfully[/green]")
            console.print(f"Key ID: [cyan]{api_key.key_id}[/cyan]")
            console.print(f"API Key: [yellow]{getattr(api_key, 'raw_key', 'N/A')}[/yellow]")
            console.print(f"\n[red]⚠️  Save this key securely - it won't be shown again![/red]")
            
        except Exception as e:
            console.print(f"[red]Failed to create API key: {e}[/red]")
    
    
    return [api]


def _get_server_info_path() -> Path:
    """Get path to server info file."""
    return Path.home() / ".config" / "mcp-manager" / "api_server.json"


def _store_server_info(host: str, port: int, pid: int):
    """Store running server information."""
    import json
    
    info_path = _get_server_info_path()
    info_path.parent.mkdir(parents=True, exist_ok=True)
    
    info = {
        "host": host,
        "port": port,
        "pid": pid,
        "started_at": time.time()
    }
    
    with open(info_path, 'w') as f:
        json.dump(info, f, indent=2)


def _get_server_info() -> Optional[dict]:
    """Get stored server information."""
    import json
    
    info_path = _get_server_info_path()
    if not info_path.exists():
        return None
    
    try:
        with open(info_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _clear_server_info():
    """Clear stored server information."""
    info_path = _get_server_info_path()
    if info_path.exists():
        info_path.unlink()