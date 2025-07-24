"""
Quality management commands for MCP Manager CLI.

Provides commands for viewing quality metrics, managing feedback,
and analyzing server reliability data.
"""

import asyncio
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.progress import Progress, SpinnerColumn, TextColumn

from mcp_manager.cli.helpers import handle_errors
from mcp_manager.core.quality.tracker import QualityTracker
from mcp_manager.core.quality.models import IssueCategory
from mcp_manager.core.quality.discovery_integration import create_quality_aware_discovery

console = Console()


def quality_commands(cli_context):
    """Add quality management commands to the CLI."""
    
    @click.group("quality")
    def quality():
        """Manage MCP server quality tracking and analysis."""
        pass
    
    @quality.command("status")
    @click.option("--server-id", "-s", help="Show status for specific server")
    @click.option("--detailed", "-d", is_flag=True, help="Show detailed quality report")
    @handle_errors
    def quality_status(server_id: Optional[str], detailed: bool):
        """Show quality tracking status and metrics."""
        
        tracker = QualityTracker()
        
        if server_id:
            # Show detailed status for specific server
            _show_server_quality_status(tracker, server_id, detailed)
        else:
            # Show overall quality tracking status
            _show_overall_quality_status(tracker)
    
    @quality.command("rankings")
    @click.option("--limit", "-l", default=20, help="Number of servers to show")
    @click.option("--min-attempts", default=3, help="Minimum install attempts to include")
    @handle_errors
    def quality_rankings(limit: int, min_attempts: int):
        """Show server quality rankings."""
        
        tracker = QualityTracker()
        
        console.print(f"[bold blue]🏆 MCP Server Quality Rankings[/bold blue]")
        console.print(f"[dim]Minimum {min_attempts} install attempts required[/dim]\\n")
        
        rankings = tracker.get_server_rankings(limit=limit * 2)  # Get more to filter
        
        # Filter by minimum attempts
        filtered_rankings = [
            (server_id, metrics) for server_id, metrics in rankings
            if metrics.total_install_attempts >= min_attempts
        ][:limit]
        
        if not filtered_rankings:
            console.print("[yellow]No servers found with sufficient quality data[/yellow]")
            console.print(f"[dim]Try lowering --min-attempts (currently {min_attempts})[/dim]")
            return
        
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Rank", style="dim", width=6)
        table.add_column("Server", style="green", width=25)
        table.add_column("Quality", style="white", width=12)
        table.add_column("Success Rate", style="blue", width=12)
        table.add_column("Installs", style="cyan", width=10)
        table.add_column("Rating", style="yellow", width=10)
        table.add_column("Status", style="dim", width=12)
        
        for rank, (server_id, metrics) in enumerate(filtered_rankings, 1):
            # Truncate long server names
            display_name = server_id[:22] + "..." if len(server_id) > 25 else server_id
            
            # Quality score with tier indicator
            tier = metrics.get_quality_tier()
            tier_icons = {
                "excellent": "🏆", "good": "✅", "fair": "⚠️", 
                "poor": "❗", "critical": "❌"
            }
            quality_display = f"{tier_icons.get(tier, '')} {metrics.reliability_score:.0f}/100"
            
            # Success rate
            success_display = f"{metrics.success_rate:.1%}"
            if metrics.success_rate >= 0.8:
                success_display = f"[green]{success_display}[/green]"
            elif metrics.success_rate >= 0.6:
                success_display = f"[yellow]{success_display}[/yellow]"
            else:
                success_display = f"[red]{success_display}[/red]"
            
            # Install count
            install_display = f"{metrics.successful_installs}/{metrics.total_install_attempts}"
            
            # Rating
            rating_display = "N/A"
            if metrics.average_rating > 0:
                rating_display = f"{metrics.average_rating:.1f}/5"
                if metrics.average_rating >= 4:
                    rating_display = f"[green]{rating_display}[/green]"
                elif metrics.average_rating >= 3:
                    rating_display = f"[yellow]{rating_display}[/yellow]"
                else:
                    rating_display = f"[red]{rating_display}[/red]"
            
            # Maintenance status
            status_colors = {
                "active": "green", "recent": "yellow", 
                "stale": "red", "abandoned": "red"
            }
            status_color = status_colors.get(metrics.maintenance_status, "dim")
            status_display = f"[{status_color}]{metrics.maintenance_status}[/{status_color}]"
            
            table.add_row(
                f"#{rank}",
                display_name,
                quality_display,
                success_display,
                install_display,
                rating_display,
                status_display
            )
        
        console.print(table)
        console.print(f"\\n[dim]💡 Use 'mcp-manager quality status -s <server-id>' for detailed analysis[/dim]")
    
    @quality.command("feedback")
    @click.argument("server_id")
    @click.option("--rating", "-r", type=click.IntRange(1, 5), required=True, 
                  help="Rating from 1-5 stars")
    @click.option("--comment", "-c", help="Optional comment about the server")
    @click.option("--issues", multiple=True, 
                  type=click.Choice([e.value for e in IssueCategory]),
                  help="Report specific issues (can use multiple times)")
    @click.option("--recommend", help="Suggest an alternative server")
    @handle_errors
    def quality_feedback(server_id: str, rating: int, comment: Optional[str], 
                        issues: tuple, recommend: Optional[str]):
        """Submit feedback about an MCP server."""
        
        tracker = QualityTracker()
        
        # Convert issue strings back to enums
        issue_categories = [IssueCategory(issue) for issue in issues]
        
        console.print(f"[blue]📝 Submitting feedback for '{server_id}'[/blue]")
        console.print(f"Rating: {'⭐' * rating} ({rating}/5)")
        
        if comment:
            console.print(f"Comment: {comment}")
        
        if issue_categories:
            issues_text = ", ".join(issue.value.replace("_", " ").title() for issue in issue_categories)
            console.print(f"Issues: {issues_text}")
        
        if recommend:
            console.print(f"Recommended alternative: {recommend}")
        
        # Record the feedback
        tracker.record_user_feedback(
            server_id=server_id,
            rating=rating,
            comment=comment,
            reported_issues=issue_categories,
            recommended_alternative=recommend,
            user_identifier="anonymous"  # Could be enhanced with user identification
        )
        
        console.print(f"\\n[green]✅ Thank you for your feedback![/green]")
        console.print("[dim]Your feedback helps improve the MCP ecosystem for everyone[/dim]")
    
    @quality.command("report")
    @click.argument("server_id")
    @handle_errors
    def quality_report(server_id: str):
        """Generate detailed quality report for a server."""
        
        tracker = QualityTracker()
        
        console.print(f"[blue]📊 Generating quality report for '{server_id}'...[/blue]\\n")
        
        # Get detailed report
        report = tracker.get_quality_report(server_id, server_id)  # Using server_id as install_id
        
        if report.metrics.total_install_attempts == 0:
            console.print(f"[yellow]No quality data available for '{server_id}'[/yellow]")
            console.print("[dim]This server hasn't been tracked yet or has no installation attempts[/dim]")
            return
        
        # Display comprehensive report
        _display_quality_report(report)
    
    @quality.command("cleanup")
    @click.option("--days", "-d", default=90, help="Days of data to keep")
    @click.option("--dry-run", is_flag=True, help="Show what would be deleted without deleting")
    @handle_errors
    def quality_cleanup(days: int, dry_run: bool):
        """Clean up old quality tracking data."""
        
        tracker = QualityTracker()
        
        if dry_run:
            console.print(f"[yellow]🧹 Dry run: Would clean up data older than {days} days[/yellow]")
            console.print("[dim]Use without --dry-run to actually delete old data[/dim]")
        else:
            console.print(f"[blue]🧹 Cleaning up quality data older than {days} days...[/blue]")
            tracker.cleanup_old_data(days_to_keep=days)
            console.print("[green]✅ Cleanup completed[/green]")
    
    return [quality]


def _show_overall_quality_status(tracker: QualityTracker):
    """Show overall quality tracking status."""
    
    console.print("[bold blue]📊 Quality Tracking Status[/bold blue]\\n")
    
    # Get some basic statistics
    rankings = tracker.get_server_rankings(limit=100)
    
    if not rankings:
        console.print("[yellow]No quality data available yet[/yellow]")
        console.print("[dim]Quality data will be collected as servers are installed and used[/dim]")
        return
    
    total_servers = len(rankings)
    servers_with_data = len([r for r in rankings if r[1].total_install_attempts >= 3])
    
    # Quality tier distribution
    tier_counts = {"excellent": 0, "good": 0, "fair": 0, "poor": 0, "critical": 0}
    total_attempts = 0
    total_successful = 0
    
    for _, metrics in rankings:
        if metrics.total_install_attempts >= 3:  # Only count servers with meaningful data
            tier = metrics.get_quality_tier()
            tier_counts[tier] += 1
            total_attempts += metrics.total_install_attempts
            total_successful += metrics.successful_installs
    
    # Overall statistics panel
    overall_success_rate = total_successful / total_attempts if total_attempts > 0 else 0
    
    stats_text = f"""
[cyan]Tracked Servers:[/cyan] {total_servers}
[cyan]With Quality Data:[/cyan] {servers_with_data}
[cyan]Total Install Attempts:[/cyan] {total_attempts}
[cyan]Overall Success Rate:[/cyan] {overall_success_rate:.1%}
    """
    
    console.print(Panel(stats_text.strip(), title="📈 Overall Statistics", border_style="blue"))
    
    # Quality distribution
    if servers_with_data > 0:
        tier_panels = []
        tier_colors = {
            "excellent": "green", "good": "blue", "fair": "yellow", 
            "poor": "red", "critical": "red"
        }
        tier_icons = {
            "excellent": "🏆", "good": "✅", "fair": "⚠️", 
            "poor": "❗", "critical": "❌"
        }
        
        for tier, count in tier_counts.items():
            if count > 0:
                percentage = (count / servers_with_data) * 100
                color = tier_colors[tier]
                icon = tier_icons[tier]
                
                panel_text = f"{icon} {count} servers\\n({percentage:.1f}%)"
                tier_panels.append(Panel(
                    panel_text, 
                    title=tier.title(), 
                    border_style=color,
                    width=15
                ))
        
        if tier_panels:
            console.print("\\n[bold]Quality Distribution:[/bold]")
            console.print(Columns(tier_panels, equal=True))
    
    console.print("\\n[dim]💡 Use 'mcp-manager quality rankings' to see detailed server rankings[/dim]")


def _show_server_quality_status(tracker: QualityTracker, server_id: str, detailed: bool):
    """Show quality status for a specific server."""
    
    console.print(f"[bold blue]📊 Quality Status: {server_id}[/bold blue]\\n")
    
    metrics = tracker.get_quality_metrics(server_id, server_id)
    
    if metrics.total_install_attempts == 0:
        console.print(f"[yellow]No quality data available for '{server_id}'[/yellow]")
        console.print("[dim]This server hasn't been tracked yet[/dim]")
        return
    
    if detailed:
        report = tracker.get_quality_report(server_id, server_id)
        _display_quality_report(report)
    else:
        _display_quality_summary(metrics)


def _display_quality_summary(metrics):
    """Display a summary of quality metrics."""
    
    # Main metrics panel
    tier = metrics.get_quality_tier()
    status = metrics.get_recommendation_status()
    
    main_text = f"""
[cyan]Quality Score:[/cyan] {metrics.reliability_score:.1f}/100 ({tier})
[cyan]Status:[/cyan] {status}
[cyan]Success Rate:[/cyan] {metrics.success_rate:.1%} ({metrics.successful_installs}/{metrics.total_install_attempts})
[cyan]Maintenance:[/cyan] {metrics.maintenance_status}
    """
    
    if metrics.total_health_checks > 0:
        main_text += f"\\n[cyan]Health Rate:[/cyan] {metrics.health_rate:.1%}"
        if metrics.avg_response_time_ms:
            main_text += f"\\n[cyan]Avg Response:[/cyan] {metrics.avg_response_time_ms:.1f}ms"
    
    if metrics.average_rating > 0:
        stars = "⭐" * int(metrics.average_rating)
        main_text += f"\\n[cyan]User Rating:[/cyan] {metrics.average_rating:.1f}/5 {stars} ({metrics.total_ratings} reviews)"
    
    console.print(Panel(main_text.strip(), title="📊 Quality Metrics", border_style="blue"))
    
    # Issues panel
    if metrics.common_issues:
        issues_text = ""
        for issue, count in sorted(metrics.common_issues.items(), key=lambda x: x[1], reverse=True):
            issue_name = issue.value.replace("_", " ").title()
            issues_text += f"• {issue_name}: {count} reports\\n"
        
        console.print(Panel(issues_text.strip(), title="⚠️  Common Issues", border_style="yellow"))


def _display_quality_report(report):
    """Display a comprehensive quality report."""
    
    metrics = report.metrics
    
    # Header with summary
    summary = report.generate_summary()
    console.print(Panel(summary, title=f"📋 Quality Report: {report.server_id}", border_style="blue"))
    
    # Main metrics
    _display_quality_summary(metrics)
    
    # Recent activity
    if report.recent_attempts:
        console.print("\\n[bold]📈 Recent Install Attempts:[/bold]")
        
        attempts_table = Table(show_header=True, header_style="bold cyan")
        attempts_table.add_column("Outcome", width=12)
        attempts_table.add_column("Duration", width=10)
        attempts_table.add_column("Time", width=12)
        attempts_table.add_column("Error", width=40)
        
        for attempt in report.recent_attempts[:10]:  # Show last 10
            outcome_color = "green" if attempt.outcome.value == "success" else "red"
            outcome_display = f"[{outcome_color}]{attempt.outcome.value}[/{outcome_color}]"
            
            duration_display = f"{attempt.duration_seconds:.1f}s"
            time_display = _format_relative_time(attempt.timestamp)
            error_display = (attempt.error_message[:37] + "...") if attempt.error_message and len(attempt.error_message) > 40 else (attempt.error_message or "")
            
            attempts_table.add_row(outcome_display, duration_display, time_display, error_display)
        
        console.print(attempts_table)
    
    # Recommendations
    if report.alternative_suggestions:
        alt_text = "\\n".join(f"• {alt}" for alt in report.alternative_suggestions)
        console.print(Panel(alt_text, title="💡 Alternative Suggestions", border_style="green"))
    
    if report.troubleshooting_tips:
        tips_text = "\\n".join(f"• {tip}" for tip in report.troubleshooting_tips)
        console.print(Panel(tips_text, title="🔧 Troubleshooting Tips", border_style="yellow"))


def _format_relative_time(timestamp: float) -> str:
    """Format timestamp as relative time."""
    import time
    
    now = time.time()
    diff = now - timestamp
    
    if diff < 60:
        return f"{int(diff)}s ago"
    elif diff < 3600:
        return f"{int(diff/60)}m ago"
    elif diff < 86400:
        return f"{int(diff/3600)}h ago"
    else:
        return f"{int(diff/86400)}d ago"