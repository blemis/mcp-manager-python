"""
Tool management commands for MCP Manager CLI.
"""

import asyncio
from typing import Optional

import click
from rich.console import Console

from mcp_manager.cli.helpers import handle_errors

console = Console()


def tools_commands(cli_context):
    """Add tools commands to the CLI."""
    
    @click.group("tools")
    def tools():
        """Search and manage MCP tools registry."""
        pass
    
    
    @tools.command("search")
    @click.argument("query")
    @click.option("--server", "-s", help="Filter by server name")
    @click.option("--type", "-t", help="Filter by tool type")
    @click.option("--category", "-c", help="Filter by category")
    @click.option("--limit", "-l", default=20, help="Maximum results")
    @handle_errors
    def tools_search(query: str, server: Optional[str], type: Optional[str], category: Optional[str], limit: int):
        """Search for tools in the registry."""
        
        async def search_tools():
            try:
                from mcp_manager.core.tool_registry import ToolRegistryService
                
                registry = ToolRegistryService()
                results = await registry.search_tools(
                    query=query,
                    server_filter=server,
                    type_filter=type,
                    category_filter=category,
                    limit=limit
                )
                
                if not results:
                    console.print(f"[yellow]No tools found matching '{query}'[/yellow]")
                    return
                
                from rich.table import Table
                
                table = Table(
                    title=f"Tool Search Results ({len(results)} found)",
                    show_header=True,
                    header_style="bold cyan",
                    title_style="bold cyan",
                    show_lines=True
                )
                
                table.add_column("Tool", style="green", width=20)
                table.add_column("Server", style="blue", width=15)
                table.add_column("Type", style="yellow", width=10)
                table.add_column("Description", style="white", width=40)
                table.add_column("Status", style="dim", width=10)
                
                for tool in results:
                    table.add_row(
                        tool.get('name', 'Unknown'),
                        tool.get('server_name', 'Unknown'),
                        tool.get('type', 'Unknown'),
                        (tool.get('description', '')[:37] + "...") if len(tool.get('description', '')) > 40 else tool.get('description', ''),
                        "✅ Available" if tool.get('available', False) else "❌ Unavailable"
                    )
                
                console.print("")
                console.print(table)
                console.print("")
                console.print("[dim]💡 Use tools directly in Claude Code conversations[/dim]")
                
            except Exception as e:
                console.print(f"[red]Failed to search tools: {e}[/red]")
        
        asyncio.run(search_tools())
    
    
    @tools.command("list")
    @click.option("--server", "-s", help="Filter by server name")
    @click.option("--type", "-t", help="Filter by tool type")
    @click.option("--available-only", "-a", is_flag=True, help="Show only available tools")
    @click.option("--limit", "-l", default=50, help="Maximum results")
    @handle_errors
    def tools_list(server: Optional[str], type: Optional[str], available_only: bool, limit: int):
        """List all tools in the registry."""
        
        async def list_tools():
            try:
                from mcp_manager.core.tool_registry import ToolRegistryService
                
                registry = ToolRegistryService()
                tools = await registry.list_tools(
                    server_filter=server,
                    type_filter=type,
                    available_only=available_only,
                    limit=limit
                )
                
                if not tools:
                    console.print("[yellow]No tools found[/yellow]")
                    return
                
                # Group by server
                servers = {}
                for tool in tools:
                    server_name = tool.get('server_name', 'Unknown')
                    if server_name not in servers:
                        servers[server_name] = []
                    servers[server_name].append(tool)
                
                console.print(f"[bold blue]🛠️ MCP Tools Registry ({len(tools)} tools)[/bold blue]\n")
                
                for server_name, server_tools in servers.items():
                    console.print(f"[bold cyan]📦 {server_name}[/bold cyan] ([cyan]{len(server_tools)} tools[/cyan])")
                    
                    for tool in server_tools:
                        status = "✅" if tool.get('available', False) else "❌"
                        tool_name = tool.get('name', 'Unknown')
                        tool_desc = tool.get('description', 'No description')
                        
                        console.print(f"  {status} [green]{tool_name}[/green]: {tool_desc[:60]}{'...' if len(tool_desc) > 60 else ''}")
                        
                        # Show parameters if available
                        parameters = tool.get('parameters', [])
                        if parameters:
                            param_names = [p.get('name', 'unknown') for p in parameters[:3]]
                            param_text = ', '.join(param_names)
                            if len(parameters) > 3:
                                param_text += f", +{len(parameters) - 3} more"
                            console.print(f"    [dim]Parameters: {param_text}[/dim]")
                    
                    console.print()  # Add spacing between servers
                
                # Show summary
                available_count = sum(1 for tool in tools if tool.get('available', False))
                console.print(f"[dim]📊 Summary: {available_count}/{len(tools)} tools available[/dim]")
                
            except Exception as e:
                console.print(f"[red]Failed to list tools: {e}[/red]")
        
        asyncio.run(list_tools())
    
    return [tools]