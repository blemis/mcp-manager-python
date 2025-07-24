"""
Display helper functions for CLI commands.
"""

from rich.console import Console
from rich.panel import Panel

console = Console()


async def show_server_details_after_install(manager, server_name: str):
    """Show server details after installation."""
    try:
        console.print(f"[blue]Fetching details for '{server_name}'...[/blue]")
        
        # Get server details with timeout handling
        server_details = await manager.get_server_details(server_name)
        
        if not server_details:
            console.print(f"[yellow]⚠[/yellow] Could not fetch detailed information for '{server_name}'")
            console.print(f"[dim]This may be due to connection timeouts or server unavailability[/dim]")
            console.print(f"[dim]The server is still installed and should work normally[/dim]")
            return
        
        # Create details display
        details_content = []
        
        # Basic server info
        details_content.append(f"[bold cyan]Server:[/bold cyan] {server_details['name']}")
        if server_details.get('description'):
            details_content.append(f"[bold cyan]Description:[/bold cyan] {server_details['description']}")
        details_content.append(f"[bold cyan]Type:[/bold cyan] {server_details.get('type', 'Unknown')}")
        details_content.append(f"[bold cyan]Status:[/bold cyan] {server_details.get('status', 'Unknown')}")
        
        # Tools information
        tools = server_details.get('tools', [])
        if tools:
            details_content.append(f"\n[bold cyan]Available Tools ({len(tools)}):[/bold cyan]")
            for tool in tools:
                tool_name = tool.get('name', 'Unknown')
                tool_desc = tool.get('description', 'No description available')
                details_content.append(f"  • [bold green]{tool_name}[/bold green]: {tool_desc}")
                
                # Show parameters if available
                params = tool.get('parameters', [])
                if params:
                    details_content.append("    [dim]Parameters:[/dim]")
                    for param in params:
                        param_name = param.get('name', 'unknown')
                        param_type = param.get('type', 'unknown')
                        param_required = " [red](required)[/red]" if param.get('required') else ""
                        param_desc = param.get('description', '')
                        details_content.append(f"      - [yellow]{param_name}[/yellow] ([cyan]{param_type}[/cyan]){param_required}: {param_desc}")
        else:
            # Enhanced display for cases where tool discovery failed
            source = server_details.get('source', 'unknown')
            if source == "docker_container_introspection_failed":
                details_content.append(f"\n[yellow]Tool discovery failed for Docker container[/yellow]")
                
                # Show fallback information
                fallback_info = server_details.get('fallback_info', {})
                docker_image = server_details.get('docker_image')
                
                if docker_image:
                    details_content.append(f"[dim]Docker Image: {docker_image}[/dim]")
                
                # Show likely tools
                likely_tools = fallback_info.get('likely_tools', [])
                if likely_tools:
                    details_content.append(f"\n[bold cyan]Likely Available Tools:[/bold cyan]")
                    for tool in likely_tools:
                        details_content.append(f"  • [bold green]{tool['name']}[/bold green]: {tool['description']}")
                
                # Show troubleshooting suggestions
                suggestions = fallback_info.get('suggestions', [])
                if suggestions:
                    details_content.append(f"\n[bold cyan]Troubleshooting:[/bold cyan]")
                    for suggestion in suggestions:
                        details_content.append(f"  • {suggestion}")
            else:
                details_content.append(f"\n[yellow]No tool information available yet[/yellow]")
        
        # Claude usage instructions
        details_content.append(f"\n[bold cyan]Usage in Claude:[/bold cyan]")
        details_content.append(f"This server is now active in Claude Code. You can use its tools directly in your conversations!")
        
        if tools:
            details_content.append(f"\n[bold cyan]Example Usage:[/bold cyan]")
            first_tool = tools[0]
            tool_name = first_tool.get('name', 'tool_name')
            details_content.append(f"Just ask Claude: \"Use the [green]{tool_name}[/green] tool to...\"")
        
        # Display in a panel
        content = "\n".join(details_content)
        panel = Panel(
            content,
            title=f"📋 Server Details: {server_name}",
            title_align="left",
            border_style="cyan",
            padding=(1, 2)
        )
        
        console.print("")  # Add spacing
        console.print(panel)
        
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to get server details: {e}")


async def show_discovery_for_next_install(discovery):
    """Show discovery results for the user to choose another server to install."""
    try:
        console.print(f"\n[blue]🔍 Discovering other available MCP servers...[/blue]")
        
        # Run discovery to show what else is available
        results = await discovery.discover_servers(limit=5)
        
        if not results:
            console.print("[yellow]No servers found[/yellow]")
            return
        
        from rich.table import Table
        
        # Create table for discovery results
        table = Table(
            title="Available MCP Servers",
            show_header=True,
            header_style="bold cyan",
            title_style="bold cyan",
            show_lines=True
        )
        
        table.add_column("Install ID", style="green", width=25)
        table.add_column("Type", style="blue", width=8)
        table.add_column("Description", style="white", width=40)
        table.add_column("Install Command", style="dim", width=35)
        
        # Add rows for each result
        for result in results:
            from mcp_manager.cli.helpers.discovery import generate_install_id
            
            # Generate install ID using same logic as discover command
            install_id = generate_install_id(result)
            
            # Create simple install command
            install_cmd = f"mcp-manager install-package {install_id}"
            
            table.add_row(
                install_id,
                result.server_type.value,
                result.description[:37] + "..." if result.description and len(result.description) > 40 else (result.description or ""),
                install_cmd[:32] + "..." if len(install_cmd) > 35 else install_cmd
            )
        
        console.print("")
        console.print(table)
        console.print("")
        console.print("[dim]💡 Copy and paste the install command for the server you want[/dim]")
        console.print("[dim]   Example: [cyan]mcp-manager install-package modelcontextprotocol-filesystem[/cyan][/dim]")
        
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to discover servers: {e}")