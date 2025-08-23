"""
System information and status commands for MCP Manager CLI.
"""

import asyncio

import click
from rich.console import Console

from mcp_manager.cli.helpers import handle_errors

console = Console()


def system_commands(cli_context):
    """Add system commands to the CLI."""
    
    @click.command(name="system-info")
    @handle_errors
    def system_info():
        """Show system information and dependencies."""
        manager = cli_context.get_manager()
        
        try:
            info = manager.get_system_info()
            
            console.print("[bold blue]🖥️ System Information[/bold blue]\n")
            
            console.print(f"Version: [cyan]{info.get('version', 'Unknown')}[/cyan]")
            console.print(f"Server Count: [cyan]{info.get('server_count', 0)}[/cyan]")
            console.print(f"Enabled Servers: [cyan]{info.get('enabled_servers', 0)}[/cyan]")
            console.print(f"Claude CLI: [cyan]{'✅ Available' if info.get('claude_available') else '❌ Not available'}[/cyan]")
            console.print(f"Docker: [cyan]{'✅ Available' if info.get('docker_available') else '❌ Not available'}[/cyan]")
            console.print(f"Current Mode: [cyan]{info.get('current_mode', 'Unknown')}[/cyan]")
            
        except Exception as e:
            console.print(f"[red]Failed to get system info: {e}[/red]")
    
    
    @click.command()
    @handle_errors
    def status():
        """Show comprehensive MCP Manager system status."""
        
        async def show_status():
            try:
                manager = cli_context.get_manager()
                
                console.print("[bold blue]📊 MCP Manager Status[/bold blue]\n")
                
                # Get system info
                info = manager.get_system_info()
                
                # Server status
                servers = manager.list_servers_fast()
                enabled_servers = [s for s in servers if s.enabled]
                
                console.print("[bold cyan]🖥️ System Health[/bold cyan]")
                console.print(f"  Claude CLI: {'✅ Available' if info.claude_cli_available else '❌ Not available'}")
                console.print(f"  Docker: {'✅ Available' if info.docker_available else '❌ Not available'}")
                console.print(f"  NPM: {'✅ Available' if info.npm_available else '❌ Not available'}")
                console.print(f"  Git: {'✅ Available' if info.git_available else '❌ Not available'}")
                console.print(f"  Platform: {info.platform}")
                console.print(f"  Python: {info.python_version}")
                
                console.print(f"\n[bold cyan]📦 Server Status[/bold cyan]")
                console.print(f"  Total Servers: {len(servers)}")
                console.print(f"  Enabled: {len(enabled_servers)}")
                console.print(f"  Disabled: {len(servers) - len(enabled_servers)}")
                
                # Show recent activity if available
                try:
                    registry_stats = manager.get_tool_registry_stats()
                    console.print(f"\n[bold cyan]🛠️ Tools Registry[/bold cyan]")
                    console.print(f"  Total Tools: {registry_stats.get('total_tools', 0)}")
                    console.print(f"  Available Tools: {registry_stats.get('available_tools', 0)}")
                except:
                    pass
                
            except Exception as e:
                console.print(f"[red]Failed to get status: {e}[/red]")
        
        asyncio.run(show_status())
    
    
    @click.command("check-sync")
    @click.option("--verbose", "-v", is_flag=True, help="Show detailed sync information")
    @handle_errors
    def check_sync(verbose: bool):
        """Check synchronization status between mcp-manager and Claude."""
        
        async def check_sync_async():
            try:
                manager = cli_context.get_manager()
                
                console.print("[blue]🔄 Checking sync status...[/blue]")
                
                sync_result = await manager.check_sync_status()
                
                if sync_result.in_sync:
                    console.print("[green]✅ MCP Manager and Claude are in sync[/green]")
                else:
                    console.print("[yellow]⚠️ Synchronization issues detected[/yellow]")
                    
                    if sync_result.missing_in_claude:
                        console.print(f"[red]Missing in Claude ({len(sync_result.missing_in_claude)}):[/red]")
                        for server in sync_result.missing_in_claude:
                            console.print(f"  • {server}")
                    
                    if sync_result.missing_in_manager:
                        console.print(f"[red]Missing in Manager ({len(sync_result.missing_in_manager)}):[/red]")
                        for server in sync_result.missing_in_manager:
                            console.print(f"  • {server}")
                
                if verbose:
                    console.print(f"\n[dim]Last sync check: {sync_result.last_checked}[/dim]")
                    console.print(f"[dim]Claude servers: {len(sync_result.claude_servers)}[/dim]")
                    console.print(f"[dim]Manager servers: {len(sync_result.manager_servers)}[/dim]")
                    
            except Exception as e:
                console.print(f"[red]Sync check failed: {e}[/red]")
        
        import asyncio
        asyncio.run(check_sync_async())
    
    
    @click.command()
    @handle_errors
    def sync():
        """No longer needed - MCP Manager works directly with Claude's internal state."""
        console.print("[yellow]ℹ[/yellow] Sync is no longer needed!")
        console.print("[dim]MCP Manager now works directly with Claude's internal state.[/dim]")
        console.print("[dim]All server changes are immediately available in Claude Code.[/dim]")
        
        console.print(f"\n[dim]💡 To check sync status, use:[/dim]")
        console.print(f"[dim]   [cyan]mcp-manager check-sync[/cyan][/dim]")
    
    @click.command("requirements")
    @click.option("--server", "-s", help="Show requirements for specific server")
    @handle_errors
    def list_requirements(server: str):
        """List all server requirements stored in database."""
        try:
            from mcp_manager.core.database.server_state import MCPServerStateManager
            db = MCPServerStateManager()
            
            if server:
                # Show requirements for specific server
                requirements = db.get_server_requirements(server)
                if not requirements:
                    console.print(f"[yellow]No requirements found for server '{server}'[/yellow]")
                    return
                    
                console.print(f"[bold blue]Requirements for '{server}':[/bold blue]\n")
                for req in requirements:
                    required_text = "[red]REQUIRED[/red]" if req.get("required") else "[dim]optional[/dim]"
                    console.print(f"• {req['type']}: {required_text}")
                    console.print(f"  Prompt: [dim]{req['prompt']}[/dim]")
                    if req.get("default"):
                        console.print(f"  Default: [dim]{req['default']}[/dim]")
                    console.print("")
            else:
                # Show all requirements 
                all_requirements = db.list_all_server_requirements()
                if not all_requirements:
                    console.print("[yellow]No server requirements stored in database[/yellow]")
                    console.print("[dim]💡 Use 'mcp-manager add-requirement' to add requirements for new servers[/dim]")
                    return
                
                console.print(f"[bold blue]All Server Requirements ({len(all_requirements)} total):[/bold blue]\n")
                
                current_server = None
                for req in all_requirements:
                    if current_server != req['server_identifier']:
                        current_server = req['server_identifier']
                        console.print(f"[bold cyan]{current_server}[/bold cyan] ({req['server_type']}):")
                    
                    required_text = "[red]REQUIRED[/red]" if req['required'] else "[dim]optional[/dim]"
                    console.print(f"  • {req['requirement_type']}: {required_text}")
                    console.print(f"    Prompt: [dim]{req['prompt']}[/dim]")
                    if req['default_value']:
                        console.print(f"    Default: [dim]{req['default_value']}[/dim]")
                    console.print("")
                    
        except Exception as e:
            console.print(f"[red]Failed to list requirements: {e}[/red]")
    
    
    @click.command("add-requirement")
    @click.argument("server_identifier")
    @click.option("--type", "requirement_type", required=True, help="Requirement type (api_key, directory_access, url, etc.)")
    @click.option("--prompt", required=True, help="Prompt to show user during installation")
    @click.option("--server-type", type=click.Choice(['npm', 'docker', 'docker-desktop', 'custom']), default='docker', help="Server type")
    @click.option("--env-var", help="Environment variable name to set")
    @click.option("--required/--optional", default=True, help="Whether requirement is required")
    @click.option("--default", help="Default value")
    @click.option("--description", help="Description of requirement")
    @handle_errors
    def add_requirement(server_identifier: str, requirement_type: str, prompt: str, 
                       server_type: str, env_var: str, required: bool, default: str, description: str):
        """Add a requirement for a server."""
        try:
            from mcp_manager.core.database.server_state import MCPServerStateManager
            db = MCPServerStateManager()
            
            success = db.add_server_requirement(
                server_identifier=server_identifier,
                server_type=server_type,
                requirement_type=requirement_type,
                prompt=prompt,
                env_var_name=env_var,
                required=required,
                default_value=default,
                description=description
            )
            
            if success:
                console.print(f"[green]✅ Added {requirement_type} requirement for '{server_identifier}'[/green]")
                if env_var:
                    console.print(f"[dim]Will set environment variable: {env_var}[/dim]")
            else:
                console.print(f"[red]❌ Failed to add requirement[/red]")
                
        except Exception as e:
            console.print(f"[red]Failed to add requirement: {e}[/red]")
    
    
    return [system_info, status, check_sync, sync, list_requirements, add_requirement]