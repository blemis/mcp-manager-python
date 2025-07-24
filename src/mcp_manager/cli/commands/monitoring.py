"""
Monitoring and mode management commands for MCP Manager CLI.
"""

import click
from rich.console import Console

from mcp_manager.cli.helpers import handle_errors

console = Console()


def monitoring_commands(cli_context):
    """Add monitoring commands to the CLI."""
    
    @click.group("mode")
    def mode():
        """Manage MCP Manager operation modes (Direct/Proxy/Hybrid)."""
        pass
    
    
    @mode.command("status")
    @handle_errors
    def mode_status():
        """Show current operation mode and configuration."""
        try:
            manager = cli_context.get_manager()
            
            console.print("[bold blue]🔧 Operation Mode Status[/bold blue]\n")
            
            mode_info = manager.get_mode_status()
            current_mode = mode_info.get('current_mode', 'Unknown')
            
            console.print(f"Current Mode: [cyan]{current_mode}[/cyan]")
            console.print(f"Docker Gateway: [cyan]{'✅ Active' if mode_info.get('docker_gateway_active') else '❌ Inactive'}[/cyan]")
            
            if mode_info.get('mode_details'):
                details = mode_info['mode_details']
                console.print(f"\nMode Details:")
                for key, value in details.items():
                    console.print(f"  {key}: [dim]{value}[/dim]")
            
        except Exception as e:
            console.print(f"[red]Failed to get mode status: {e}[/red]")
    
    
    @mode.command("switch")
    @click.argument('target_mode', type=click.Choice(['direct', 'proxy', 'hybrid']))
    @click.option("--force", "-f", is_flag=True, help="Force mode switch without confirmation")
    @handle_errors
    def mode_switch(target_mode: str, force: bool):
        """Switch between operation modes."""
        try:
            manager = cli_context.get_manager()
            
            console.print(f"[blue]Switching to {target_mode} mode...[/blue]")
            
            if target_mode == 'proxy':
                success = manager.switch_to_proxy_mode()
            elif target_mode == 'direct':
                success = manager.switch_to_direct_mode()
            else:
                console.print(f"[yellow]Hybrid mode not yet implemented[/yellow]")
                return
            
            if success:
                console.print(f"[green]✅ Successfully switched to {target_mode} mode[/green]")
            else:
                console.print(f"[red]❌ Failed to switch to {target_mode} mode[/red]")
                
        except Exception as e:
            console.print(f"[red]Mode switch failed: {e}[/red]")
    
    
    @click.group("proxy")
    def proxy():
        """Manage MCP proxy server (unified endpoint mode)."""
        pass
    
    
    @proxy.command("status")
    @handle_errors
    def proxy_status():
        """Show proxy server status and statistics."""
        console.print("[blue]📊 MCP Proxy Status[/blue]")
        console.print("[dim]Proxy functionality not yet implemented[/dim]")
    
    
    @proxy.command("validate")
    @handle_errors  
    def proxy_validate():
        """Validate proxy configuration and requirements."""
        console.print("[blue]🔍 Validating Proxy Configuration[/blue]")
        console.print("[dim]Proxy validation not yet implemented[/dim]")
    
    
    @click.command("monitor-status")
    @handle_errors
    def monitor_status_quick():
        """Quick status check for background monitor service."""
        console.print("[blue]🔍 Quick Monitor Status[/blue]")
        console.print("[dim]Background monitoring not yet implemented[/dim]")
    
    return [mode, proxy, monitor_status_quick]