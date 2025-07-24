"""
Workflow management commands for MCP Manager CLI.

Provides task-specific configuration automation using AI-curated suites
and workflow automation for seamless development context switching.
"""

import asyncio
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from mcp_manager.cli.helpers import handle_errors
from mcp_manager.core.models import TaskCategory

console = Console()


def workflow_commands(cli_context):
    """Add workflow commands to the CLI."""
    
    @click.group("workflow")
    def workflow():
        """Manage task-specific workflow configurations."""
        pass
    
    
    @workflow.command("create")
    @click.argument("name")
    @click.option("--description", "-d", help="Workflow description")
    @click.option("--suites", "-s", multiple=True, help="Suite IDs to include")
    @click.option("--category", "-c", type=click.Choice([cat.value for cat in TaskCategory]), 
                  help="Task category")
    @click.option("--priority", "-p", type=int, default=50, help="Workflow priority (1-100)")
    @click.option("--auto-activate", is_flag=True, default=True, help="Auto-activate suites")
    @handle_errors
    def workflow_create(name: str, description: Optional[str], suites: tuple, 
                       category: Optional[str], priority: int, auto_activate: bool):
        """Create a new task-specific workflow."""
        
        async def create_workflow():
            try:
                from mcp_manager.core.workflows.workflow_manager import workflow_manager
                
                # Convert string category to enum
                task_category = TaskCategory(category) if category else None
                
                console.print(f"[blue]🔄 Creating workflow '{name}'...[/blue]")
                
                if not suites:
                    console.print("[yellow]⚠️  No suites specified[/yellow]")
                    console.print("[dim]💡 Add suites with --suites option or edit workflow later[/dim]")
                
                success = await workflow_manager.create_workflow(
                    name=name,
                    description=description or f"Task-specific workflow: {name}",
                    suite_ids=list(suites),
                    category=task_category,
                    auto_activate=auto_activate,
                    priority=priority
                )
                
                if success:
                    console.print(f"[green]✅ Workflow '{name}' created successfully![/green]")
                    if suites:
                        console.print(f"[dim]Includes {len(suites)} suite(s): {', '.join(suites)}[/dim]")
                    
                    console.print(f"\n[dim]💡 Activate this workflow with:[/dim]")
                    console.print(f"[dim]   [cyan]mcp-manager workflow activate {name}[/cyan][/dim]")
                else:
                    console.print(f"[red]❌ Failed to create workflow[/red]")
                
            except ValueError as e:
                console.print(f"[red]❌ Invalid category: {e}[/red]")
            except Exception as e:
                console.print(f"[red]❌ Failed to create workflow: {e}[/red]")
        
        asyncio.run(create_workflow())
    
    
    @workflow.command("list")
    @click.option("--category", "-c", type=click.Choice([cat.value for cat in TaskCategory]),
                  help="Filter by task category")
    @handle_errors
    def workflow_list(category: Optional[str]):
        """List all workflow configurations."""
        
        async def list_workflows():
            try:
                from mcp_manager.core.workflows.workflow_manager import workflow_manager
                
                # Convert string category to enum
                task_category = TaskCategory(category) if category else None
                
                workflows = workflow_manager.list_workflows(task_category)
                
                if not workflows:
                    if category:
                        console.print(f"[yellow]No workflows found in category '{category}'[/yellow]")
                    else:
                        console.print("[yellow]No workflows configured[/yellow]")
                        console.print("[dim]💡 Create your first workflow with:[/dim]")
                        console.print("[dim]   [cyan]mcp-manager workflow create my-workflow --description 'My workflow'[/cyan][/dim]")
                    return
                
                table = Table(
                    title=f"Task-Specific Workflows ({len(workflows)} total)",
                    show_header=True,
                    header_style="bold cyan",
                    title_style="bold cyan",
                    show_lines=True
                )
                
                table.add_column("Name", style="green", width=20)
                table.add_column("Category", style="blue", width=15)
                table.add_column("Suites", style="yellow", width=8)
                table.add_column("Priority", style="magenta", width=8)
                table.add_column("Status", style="white", width=12)
                table.add_column("Description", style="dim", width=35)
                
                active_workflow = workflow_manager.get_active_workflow()
                active_name = active_workflow.name if active_workflow else None
                
                for wf in sorted(workflows, key=lambda w: w.priority, reverse=True):
                    status = "🟢 Active" if wf.name == active_name else "⚪ Inactive"
                    suite_count = len(wf.suite_ids)
                    category_display = wf.category.value if wf.category else "general"
                    
                    table.add_row(
                        wf.name,
                        category_display,
                        str(suite_count),
                        str(wf.priority),
                        status,
                        (wf.description[:32] + "...") if wf.description and len(wf.description) > 35 
                        else (wf.description or "")
                    )
                
                console.print("")
                console.print(table)
                console.print("")
                console.print("[dim]💡 To activate a workflow: [cyan]mcp-manager workflow activate <name>[/cyan][/dim]")
                console.print("[dim]💡 To view workflow details: [cyan]mcp-manager workflow show <name>[/cyan][/dim]")
                
            except Exception as e:
                console.print(f"[red]Failed to list workflows: {e}[/red]")
        
        asyncio.run(list_workflows())
    
    
    @workflow.command("activate")
    @click.argument("name")
    @handle_errors
    def workflow_activate(name: str):
        """Activate a workflow, switching MCP server configuration."""
        
        async def activate_workflow():
            try:
                from mcp_manager.core.workflows.workflow_manager import workflow_manager
                
                console.print(f"[blue]🔄 Activating workflow '{name}'...[/blue]")
                
                success = await workflow_manager.activate_workflow(name)
                
                if success:
                    console.print(f"[green]✅ Workflow '{name}' activated successfully![/green]")
                    
                    # Show activated workflow info
                    active_workflow = workflow_manager.get_active_workflow()
                    if active_workflow:
                        console.print(f"[dim]Category: {active_workflow.category.value if active_workflow.category else 'general'}[/dim]")
                        console.print(f"[dim]Suites: {len(active_workflow.suite_ids)}[/dim]")
                        
                        if active_workflow.suite_ids:
                            console.print(f"[dim]Suite IDs: {', '.join(active_workflow.suite_ids)}[/dim]")
                else:
                    console.print(f"[red]❌ Failed to activate workflow '{name}'[/red]")
                    console.print("[dim]💡 Check if workflow exists: [cyan]mcp-manager workflow list[/cyan][/dim]")
                
            except Exception as e:
                console.print(f"[red]Failed to activate workflow: {e}[/red]")
        
        asyncio.run(activate_workflow())
    
    
    @workflow.command("deactivate")
    @handle_errors
    def workflow_deactivate():
        """Deactivate the currently active workflow."""
        
        async def deactivate_workflow():
            try:
                from mcp_manager.core.workflows.workflow_manager import workflow_manager
                
                active_workflow = workflow_manager.get_active_workflow()
                if not active_workflow:
                    console.print("[yellow]No active workflow to deactivate[/yellow]")
                    return
                
                console.print(f"[blue]🔄 Deactivating workflow '{active_workflow.name}'...[/blue]")
                
                success = await workflow_manager.deactivate_current_workflow()
                
                if success:
                    console.print("[green]✅ Workflow deactivated successfully[/green]")
                    console.print("[dim]All MCP servers have been restored to default configuration[/dim]")
                else:
                    console.print("[red]❌ Failed to deactivate workflow[/red]")
                
            except Exception as e:
                console.print(f"[red]Failed to deactivate workflow: {e}[/red]")
        
        asyncio.run(deactivate_workflow())
    
    
    @workflow.command("switch")
    @click.argument("category", type=click.Choice([cat.value for cat in TaskCategory]))
    @handle_errors
    def workflow_switch(category: str):
        """Switch to AI-recommended workflow for task category."""
        
        async def switch_workflow():
            try:
                from mcp_manager.core.workflows.workflow_manager import workflow_manager
                
                task_category = TaskCategory(category)
                
                console.print(f"[blue]🤖 Switching to AI-recommended workflow for '{category}'...[/blue]")
                
                activated_workflow = await workflow_manager.switch_workflow(task_category)
                
                if activated_workflow:
                    console.print(f"[green]✅ Switched to workflow '{activated_workflow}'[/green]")
                    console.print(f"[dim]Category: {category}[/dim]")
                    console.print("[dim]MCP servers have been configured for optimal {category} tasks[/dim]")
                else:
                    console.print(f"[yellow]⚠️  No suitable workflow found for '{category}'[/yellow]")
                    console.print("[dim]💡 Create a workflow for this category with:[/dim]")
                    console.print(f"[dim]   [cyan]mcp-manager workflow create {category}-workflow --category {category}[/cyan][/dim]")
                
            except ValueError as e:
                console.print(f"[red]❌ Invalid category: {e}[/red]")
            except Exception as e:
                console.print(f"[red]Failed to switch workflow: {e}[/red]")
        
        asyncio.run(switch_workflow())
    
    
    @workflow.command("show")
    @click.argument("name")
    @handle_errors
    def workflow_show(name: str):
        """Show detailed information about a workflow."""
        
        def show_workflow():
            try:
                from mcp_manager.core.workflows.workflow_manager import workflow_manager
                
                workflow = workflow_manager.get_workflow(name)
                if not workflow:
                    console.print(f"[red]❌ Workflow '{name}' not found[/red]")
                    console.print("[dim]💡 List workflows: [cyan]mcp-manager workflow list[/cyan][/dim]")
                    return
                
                active_workflow = workflow_manager.get_active_workflow()
                is_active = active_workflow and active_workflow.name == name
                
                console.print(f"[bold blue]📋 Workflow Details: {name}[/bold blue]")
                console.print(f"Description: {workflow.description}")
                console.print(f"Category: [cyan]{workflow.category.value if workflow.category else 'general'}[/cyan]")
                console.print(f"Priority: [magenta]{workflow.priority}[/magenta]")
                console.print(f"Auto-activate: [yellow]{workflow.auto_activate}[/yellow]")
                console.print(f"Status: [green]🟢 Active[/green]" if is_active else "[dim]⚪ Inactive[/dim]")
                
                if workflow.last_used:
                    console.print(f"Last used: [dim]{workflow.last_used.strftime('%Y-%m-%d %H:%M:%S')}[/dim]")
                
                console.print(f"\n[bold cyan]Included Suites ({len(workflow.suite_ids)}):[/bold cyan]")
                if workflow.suite_ids:
                    for suite_id in workflow.suite_ids:
                        console.print(f"  • [green]{suite_id}[/green]")
                else:
                    console.print("  [dim]No suites configured[/dim]")
                
                # Show suite details if available
                async def show_suite_details():
                    try:
                        from mcp_manager.core.suite_manager import suite_manager
                        for suite_id in workflow.suite_ids:
                            suite = await suite_manager.get_suite(suite_id)
                            if suite:
                                server_count = len(suite.memberships) if hasattr(suite, 'memberships') else 0
                                console.print(f"    └─ [dim]{suite.name}: {server_count} servers[/dim]")
                    except Exception:
                        pass  # Suite details optional
                
                asyncio.run(show_suite_details())
                
                if not is_active:
                    console.print(f"\n[dim]💡 Activate this workflow: [cyan]mcp-manager workflow activate {name}[/cyan][/dim]")
                
            except Exception as e:
                console.print(f"[red]Failed to show workflow: {e}[/red]")
        
        show_workflow()
    
    
    @workflow.command("delete")
    @click.argument("name")
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
    @handle_errors
    def workflow_delete(name: str, force: bool):
        """Delete a workflow configuration."""
        
        async def delete_workflow():
            try:
                from mcp_manager.core.workflows.workflow_manager import workflow_manager
                
                workflow = workflow_manager.get_workflow(name)
                if not workflow:
                    console.print(f"[red]❌ Workflow '{name}' not found[/red]")
                    return
                
                if not force:
                    from rich.prompt import Confirm
                    if not Confirm.ask(f"Delete workflow '{name}'?"):
                        console.print("[dim]Deletion cancelled[/dim]")
                        return
                
                console.print(f"[blue]🗑️  Deleting workflow '{name}'...[/blue]")
                
                success = await workflow_manager.delete_workflow(name)
                
                if success:
                    console.print(f"[green]✅ Workflow '{name}' deleted successfully[/green]")
                else:
                    console.print(f"[red]❌ Failed to delete workflow[/red]")
                
            except Exception as e:
                console.print(f"[red]Failed to delete workflow: {e}[/red]")
        
        asyncio.run(delete_workflow())
    
    
    @workflow.command("status")
    @handle_errors
    def workflow_status():
        """Show current workflow status and statistics."""
        
        def show_status():
            try:
                from mcp_manager.core.workflows.workflow_manager import workflow_manager
                
                stats = workflow_manager.get_workflow_stats()
                
                if "error" in stats:
                    console.print(f"[red]❌ Error getting workflow stats: {stats['error']}[/red]")
                    return
                
                console.print("[bold blue]📊 Workflow Status[/bold blue]")
                console.print(f"Total Workflows: [cyan]{stats.get('total_workflows', 0)}[/cyan]")
                
                active_workflow = stats.get('active_workflow')
                if active_workflow:
                    console.print(f"Active Workflow: [green]{active_workflow}[/green]")
                else:
                    console.print("Active Workflow: [dim]None[/dim]")
                
                # Show category breakdown
                by_category = stats.get('by_category', {})
                if by_category:
                    console.print(f"\n[bold cyan]By Category:[/bold cyan]")
                    for category, count in sorted(by_category.items()):
                        console.print(f"  • {category}: [yellow]{count}[/yellow] workflows")
                
                # Show template count
                template_count = stats.get('template_count', 0)
                if template_count > 0:
                    console.print(f"\nTemplate Workflows: [magenta]{template_count}[/magenta]")
                
                # Show recent workflow
                most_recent = stats.get('most_recent')
                if most_recent:
                    console.print(f"Most Recently Used: [dim]{most_recent}[/dim]")
                
                # Active suites
                active_suites = stats.get('active_suites', [])
                if active_suites:
                    console.print(f"\n[bold cyan]Active Suites ({len(active_suites)}):[/bold cyan]")
                    for suite_id in active_suites:
                        console.print(f"  • [green]{suite_id}[/green]")
                
            except Exception as e:
                console.print(f"[red]Failed to get workflow status: {e}[/red]")
        
        show_status()
    
    
    @workflow.command("template")
    @click.argument("name")
    @click.option("--servers", "-s", multiple=True, help="Server names to include")
    @click.option("--category", "-c", type=click.Choice([cat.value for cat in TaskCategory]),
                  help="Task category")
    @click.option("--description", "-d", help="Template description")
    @click.option("--priority", "-p", type=int, default=70, help="Template priority")
    @handle_errors
    def workflow_template(name: str, servers: tuple, category: Optional[str], 
                         description: Optional[str], priority: int):
        """Create a workflow template from server list."""
        
        async def create_template():
            try:
                from mcp_manager.core.workflows.workflow_manager import workflow_manager
                
                if not servers:
                    console.print("[red]❌ No servers specified[/red]")
                    console.print("[dim]💡 Use --servers option to specify server names[/dim]")
                    return
                
                # Convert string category to enum
                task_category = TaskCategory(category) if category else None
                
                console.print(f"[blue]🔄 Creating workflow template '{name}'...[/blue]")
                console.print(f"[dim]Servers: {', '.join(servers)}[/dim]")
                
                success = await workflow_manager.create_workflow_template(
                    name=name,
                    servers=list(servers),
                    category=task_category,
                    description=description,
                    priority=priority
                )
                
                if success:
                    console.print(f"[green]✅ Workflow template '{name}' created successfully![/green]")
                    console.print(f"[dim]Template includes {len(servers)} server(s)[/dim]")
                    console.print(f"\n[dim]💡 Activate this template: [cyan]mcp-manager workflow activate {name}[/cyan][/dim]")
                else:
                    console.print(f"[red]❌ Failed to create workflow template[/red]")
                
            except ValueError as e:
                console.print(f"[red]❌ Invalid category: {e}[/red]")
            except Exception as e:
                console.print(f"[red]Failed to create workflow template: {e}[/red]")
        
        asyncio.run(create_template())
    
    
    return [workflow]