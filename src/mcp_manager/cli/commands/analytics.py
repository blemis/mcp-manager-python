"""
Analytics commands for MCP Manager CLI.
"""

import asyncio
from typing import Optional

import click
from rich.console import Console

from mcp_manager.cli.helpers import handle_errors

console = Console()


def analytics_commands(cli_context):
    """Add analytics commands to the CLI."""
    
    @click.group("analytics")
    def analytics():
        """Analyze MCP usage patterns and performance."""
        pass
    
    
    @analytics.command("summary")
    @click.option("--days", "-d", default=7, help="Number of days to analyze (default: 7)")
    @handle_errors
    def analytics_summary(days: int):
        """Show usage analytics summary."""
        
        async def show_summary():
            try:
                from mcp_manager.analytics.usage_analytics import UsageAnalyticsService
                
                analytics = UsageAnalyticsService()
                summary = await analytics.get_usage_summary(days=days)
                
                console.print(f"[bold blue]📊 Usage Analytics Summary ({days} days)[/bold blue]\n")
                
                # Basic stats
                console.print(f"Total Queries: [cyan]{summary.get('total_queries', 0)}[/cyan]")
                console.print(f"Unique Users: [cyan]{summary.get('unique_users', 0)}[/cyan]")
                console.print(f"Active Tools: [cyan]{summary.get('active_tools', 0)}[/cyan]")
                console.print(f"Success Rate: [cyan]{summary.get('success_rate', 0):.1f}%[/cyan]")
                
                # Top tools
                top_tools = summary.get('top_tools', [])
                if top_tools:
                    console.print(f"\n[bold cyan]🏆 Most Used Tools:[/bold cyan]")
                    for i, tool in enumerate(top_tools[:5]):
                        console.print(f"  {i+1}. [green]{tool['name']}[/green]: {tool['usage_count']} uses")
                
                # Performance metrics
                avg_response_time = summary.get('avg_response_time', 0)
                console.print(f"\n[bold cyan]⚡ Performance:[/bold cyan]")
                console.print(f"Average Response Time: [cyan]{avg_response_time:.2f}ms[/cyan]")
                
                # Error analysis
                error_rate = summary.get('error_rate', 0)
                if error_rate > 0:
                    console.print(f"Error Rate: [red]{error_rate:.1f}%[/red]")
                
            except Exception as e:
                console.print(f"[red]Failed to get analytics summary: {e}[/red]")
        
        asyncio.run(show_summary())
    
    
    @analytics.command("query")
    @click.option("--pattern", "-p", help="Search pattern for queries")
    @click.option("--limit", "-l", default=20, help="Maximum results to show")
    @handle_errors
    def analytics_query(pattern: Optional[str], limit: int):
        """Query usage patterns and trending searches."""
        
        async def show_query_patterns():
            try:
                from mcp_manager.analytics.usage_analytics import UsageAnalyticsService
                
                analytics = UsageAnalyticsService()
                
                if pattern:
                    console.print(f"[blue]🔍 Searching queries matching: {pattern}[/blue]\n")
                    results = await analytics.search_queries(pattern=pattern, limit=limit)
                else:
                    console.print("[blue]📈 Trending Query Patterns[/blue]\n")
                    results = await analytics.get_trending_queries(limit=limit)
                
                if not results:
                    console.print("[yellow]No query patterns found[/yellow]")
                    return
                
                from rich.table import Table
                
                table = Table(
                    title=f"Query Patterns ({len(results)} results)",
                    show_header=True,
                    header_style="bold cyan",
                    title_style="bold cyan"
                )
                
                table.add_column("Query", style="white", width=40)
                table.add_column("Count", style="cyan", width=8)
                table.add_column("Success Rate", style="green", width=12)
                table.add_column("Avg Response", style="yellow", width=12)
                table.add_column("Last Used", style="dim", width=15)
                
                for result in results:
                    table.add_row(
                        result.get('query', 'Unknown')[:37] + "..." if len(result.get('query', '')) > 40 else result.get('query', 'Unknown'),
                        str(result.get('count', 0)),
                        f"{result.get('success_rate', 0):.1f}%",
                        f"{result.get('avg_response_time', 0):.0f}ms",
                        result.get('last_used', 'Unknown')
                    )
                
                console.print(table)
                
            except Exception as e:
                console.print(f"[red]Failed to query patterns: {e}[/red]")
        
        asyncio.run(show_query_patterns())
    
    return [analytics]