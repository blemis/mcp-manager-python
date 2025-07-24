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
                console.print(f"  Claude CLI: {'✅ Available' if info.get('claude_available') else '❌ Not available'}")
                console.print(f"  Docker: {'✅ Available' if info.get('docker_available') else '❌ Not available'}")
                console.print(f"  Mode: {info.get('current_mode', 'Unknown')}")
                
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
        
        try:
            manager = cli_context.get_manager()
            
            console.print("[blue]🔄 Checking sync status...[/blue]")
            
            sync_result = manager.check_sync_status()
            
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
    
    
    @click.command()
    @handle_errors
    def sync():
        """No longer needed - MCP Manager works directly with Claude's internal state."""
        console.print("[yellow]ℹ[/yellow] Sync is no longer needed!")
        console.print("[dim]MCP Manager now works directly with Claude's internal state.[/dim]")
        console.print("[dim]All server changes are immediately available in Claude Code.[/dim]")
        
        console.print(f"\n[dim]💡 To check sync status, use:[/dim]")
        console.print(f"[dim]   [cyan]mcp-manager check-sync[/cyan][/dim]")
    
    return [system_info, status, check_sync, sync]