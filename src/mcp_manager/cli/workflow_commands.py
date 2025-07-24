"""
CLI commands for workflow management.

Provides command-line interface for managing task-specific MCP configurations,
workflow automation, and template installation.
"""

import asyncio
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm

from mcp_manager.core.models import TaskCategory
from mcp_manager.core.workflow_manager import workflow_manager
from mcp_manager.core.config_templates import ConfigTemplates, TemplateInstaller
from mcp_manager.core.suite_manager import suite_manager
from mcp_manager.utils.logging import get_logger

console = Console()
logger = get_logger(__name__)


def handle_errors(func):
    """Decorator to handle common CLI errors."""
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
            logger.error(f"CLI command failed: {e}")
    
    return wrapper


@click.group("workflow")
def workflow():
    """Manage task-specific MCP workflows and automation."""
    pass


@workflow.command("list")
@click.option("--category", "-c", help="Filter by task category")
@click.option("--active-only", is_flag=True, help="Show only active workflow")
@handle_errors
def workflow_list(category: Optional[str], active_only: bool):
    """List available workflows with their status and configuration."""
    async def list_workflows():
        try:
            # Parse category filter
            category_filter = None
            if category:
                try:
                    category_filter = TaskCategory(category.upper().replace('-', '_'))
                except ValueError:
                    console.print(f"[red]❌ Invalid category: {category}[/red]")
                    return
            
            # Get workflows
            if active_only:
                active_workflow = workflow_manager.get_active_workflow()
                workflows = [active_workflow] if active_workflow else []
            else:
                workflows = workflow_manager.list_workflows(category_filter)
            
            if not workflows:
                if active_only:
                    console.print("[yellow]⚠️ No active workflow[/yellow]")
                else:
                    console.print("[yellow]⚠️ No workflows found[/yellow]")
                return
            
            # Create table
            table = Table(show_header=True, header_style="bold blue")
            table.add_column("Name", style="cyan", width=25)
            table.add_column("Category", style="green", width=15)
            table.add_column("Suites", style="yellow", width=10, justify="center")
            table.add_column("Priority", style="magenta", width=8, justify="center")
            table.add_column("Status", style="white", width=10, justify="center")
            table.add_column("Last Used", style="dim", width=15)
            
            for workflow in sorted(workflows, key=lambda w: w.priority, reverse=True):
                # Status indicator
                if workflow_manager.active_workflow == workflow.name:
                    status = "🟢 Active"
                    status_style = "green"
                else:
                    status = "⚪ Inactive"
                    status_style = "dim"
                
                # Last used formatting
                last_used = "Never" if not workflow.last_used else workflow.last_used.strftime("%Y-%m-%d")
                
                table.add_row(
                    workflow.name,
                    workflow.category.value if workflow.category else "general",
                    str(len(workflow.suite_ids)),
                    str(workflow.priority),
                    f"[{status_style}]{status}[/{status_style}]",
                    last_used
                )
            
            console.print(f"\n[bold blue]📋 MCP Workflows[/bold blue]")
            console.print(table)
            
            # Show active workflow details
            if not active_only:
                active = workflow_manager.get_active_workflow()
                if active:
                    console.print(f"\n[bold]Active Workflow:[/bold] [green]{active.name}[/green]")
                    console.print(f"[dim]{active.description}[/dim]")
            
            console.print(f"\n[green]✅ Listed {len(workflows)} workflows[/green]")
            
        except Exception as e:
            console.print(f"[red]❌ Failed to list workflows: {e}[/red]")
    
    asyncio.run(list_workflows())


@workflow.command("create")
@click.argument("name")
@click.option("--description", "-d", help="Workflow description")
@click.option("--category", "-c", help="Task category")
@click.option("--suites", "-s", help="Comma-separated list of suite IDs")
@click.option("--priority", "-p", default=50, help="Workflow priority (1-100)")
@click.option("--no-auto-activate", is_flag=True, help="Disable auto-activation")
@handle_errors
def workflow_create(name: str, description: Optional[str], category: Optional[str],
                   suites: Optional[str], priority: int, no_auto_activate: bool):
    """Create a new workflow with specified suites."""
    async def create_workflow():
        try:
            # Parse category
            category_enum = None
            if category:
                try:
                    category_enum = TaskCategory(category.upper().replace('-', '_'))
                except ValueError:
                    console.print(f"[red]❌ Invalid category: {category}[/red]")
                    return
            
            # Parse suite IDs
            if not suites:
                console.print("[red]❌ At least one suite ID is required[/red]")
                return
            
            suite_ids = [s.strip() for s in suites.split(',')]
            
            # Validate suites exist
            missing_suites = []
            for suite_id in suite_ids:
                suite = await suite_manager.get_suite(suite_id)
                if not suite:
                    missing_suites.append(suite_id)
            
            if missing_suites:
                console.print(f"[red]❌ Suites not found: {missing_suites}[/red]")
                return
            
            # Create workflow
            success = await workflow_manager.create_workflow(
                name=name,
                description=description or f"Custom workflow: {name}",
                suite_ids=suite_ids,
                category=category_enum,
                auto_activate=not no_auto_activate,
                priority=priority
            )
            
            if success:
                console.print(f"[green]✅ Created workflow '{name}' with {len(suite_ids)} suites[/green]")
            else:
                console.print(f"[red]❌ Failed to create workflow '{name}'[/red]")
                
        except Exception as e:
            console.print(f"[red]❌ Failed to create workflow: {e}[/red]")
    
    asyncio.run(create_workflow())


@workflow.command("activate")
@click.argument("name")
@handle_errors
def workflow_activate(name: str):
    """Activate a workflow, switching MCP server configuration."""
    async def activate_workflow():
        try:
            console.print(f"[blue]🔄 Activating workflow '{name}'...[/blue]")
            
            success = await workflow_manager.activate_workflow(name)
            
            if success:
                console.print(f"[green]✅ Activated workflow '{name}'[/green]")
                
                # Show activated suites
                workflow = workflow_manager.get_workflow(name)
                if workflow:
                    console.print(f"\n[bold]Activated Suites:[/bold]")
                    for suite_id in workflow.suite_ids:
                        suite = await suite_manager.get_suite(suite_id)
                        if suite:
                            console.print(f"  • [cyan]{suite.name}[/cyan] ({len(suite.memberships)} servers)")
            else:
                console.print(f"[red]❌ Failed to activate workflow '{name}'[/red]")
                
        except Exception as e:
            console.print(f"[red]❌ Failed to activate workflow: {e}[/red]")
    
    asyncio.run(activate_workflow())


@workflow.command("switch")
@click.argument("category", type=click.Choice([cat.value.lower().replace('_', '-') for cat in TaskCategory]))
@handle_errors 
def workflow_switch(category: str):
    """Switch to the best workflow for a specific task category."""
    async def switch_workflow():
        try:
            # Parse category
            category_enum = TaskCategory(category.upper().replace('-', '_'))
            
            console.print(f"[blue]🔄 Switching to workflow for {category_enum.value} tasks...[/blue]")
            
            activated_workflow = await workflow_manager.switch_workflow(category_enum)
            
            if activated_workflow:
                console.print(f"[green]✅ Switched to workflow '{activated_workflow}'[/green]")
            else:
                console.print(f"[yellow]⚠️ No suitable workflow found for {category_enum.value}[/yellow]")
                
                # Suggest templates
                templates = ConfigTemplates.get_templates_by_category(category_enum)
                if templates:
                    console.print(f"\n[bold]Available templates for {category_enum.value}:[/bold]")
                    for template in templates[:3]:  # Show top 3
                        console.print(f"  • [cyan]{template.name}[/cyan]: {template.description}")
                    console.print(f"\nUse [green]mcp-manager workflow install-template[/green] to install templates")
                
        except Exception as e:
            console.print(f"[red]❌ Failed to switch workflow: {e}[/red]")
    
    asyncio.run(switch_workflow())


@workflow.command("deactivate")
@handle_errors
def workflow_deactivate():
    """Deactivate the currently active workflow."""
    async def deactivate_workflow():
        try:
            active = workflow_manager.get_active_workflow()
            if not active:
                console.print("[yellow]⚠️ No active workflow to deactivate[/yellow]")
                return
            
            console.print(f"[blue]🔄 Deactivating workflow '{active.name}'...[/blue]")
            
            # Deactivate all suites in the workflow
            for suite_id in active.suite_ids:
                await workflow_manager.deactivate_suite(suite_id)
            
            # Clear active workflow
            workflow_manager.active_workflow = None
            workflow_manager._save_workflows()
            
            console.print(f"[green]✅ Deactivated workflow '{active.name}'[/green]")
            
        except Exception as e:
            console.print(f"[red]❌ Failed to deactivate workflow: {e}[/red]")
    
    asyncio.run(deactivate_workflow())


@workflow.command("delete")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@handle_errors
def workflow_delete(name: str, force: bool):
    """Delete a workflow."""
    async def delete_workflow():
        try:
            workflow = workflow_manager.get_workflow(name)
            if not workflow:
                console.print(f"[red]❌ Workflow '{name}' not found[/red]")
                return
            
            # Confirmation
            if not force:
                if not Confirm.ask(f"Delete workflow '[red]{name}[/red]'?"):
                    console.print("[yellow]⚠️ Deletion cancelled[/yellow]")
                    return
            
            success = await workflow_manager.delete_workflow(name)
            
            if success:
                console.print(f"[green]✅ Deleted workflow '{name}'[/green]")
            else:
                console.print(f"[red]❌ Failed to delete workflow '{name}'[/red]")
                
        except Exception as e:
            console.print(f"[red]❌ Failed to delete workflow: {e}[/red]")
    
    asyncio.run(delete_workflow())


@workflow.command("templates")
@click.option("--category", "-c", help="Filter by task category")
@handle_errors
def workflow_templates(category: Optional[str]):
    """List available workflow templates."""
    try:
        # Parse category filter
        category_filter = None
        if category:
            try:
                category_filter = TaskCategory(category.upper().replace('-', '_'))
            except ValueError:
                console.print(f"[red]❌ Invalid category: {category}[/red]")
                return
        
        # Get templates
        if category_filter:
            templates = ConfigTemplates.get_templates_by_category(category_filter)
        else:
            templates = ConfigTemplates.get_all_templates()
        
        if not templates:
            console.print("[yellow]⚠️ No templates found[/yellow]")
            return
        
        # Create table
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Template", style="cyan", width=25)
        table.add_column("Category", style="green", width=15)
        table.add_column("Priority", style="magenta", width=8, justify="center")
        table.add_column("Required", style="yellow", width=15)
        table.add_column("Optional", style="dim", width=15)
        table.add_column("Description", style="white", width=40)
        
        for template in templates:
            required_servers = ", ".join(template.required_servers[:2])
            if len(template.required_servers) > 2:
                required_servers += f" (+{len(template.required_servers) - 2})"
            
            optional_servers = ", ".join(template.optional_servers[:2])
            if len(template.optional_servers) > 2:
                optional_servers += f" (+{len(template.optional_servers) - 2})"
            
            description = template.description[:37] + "..." if len(template.description) > 40 else template.description
            
            table.add_row(
                template.name,
                template.category.value,
                str(template.priority),
                required_servers or "None",
                optional_servers or "None", 
                description
            )
        
        console.print(f"\n[bold blue]📋 Workflow Templates[/bold blue]")
        console.print(table)
        console.print(f"\n[green]✅ Found {len(templates)} templates[/green]")
        console.print(f"[dim]Use 'mcp-manager workflow install-template <name>' to install[/dim]")
        
    except Exception as e:
        console.print(f"[red]❌ Failed to list templates: {e}[/red]")


@workflow.command("install-template")
@click.argument("template_name")
@click.option("--force", "-f", is_flag=True, help="Override existing workflow")
@handle_errors
def workflow_install_template(template_name: str, force: bool):
    """Install a workflow template."""
    async def install_template():
        try:
            # Find template
            template = ConfigTemplates.get_template_by_name(template_name)
            if not template:
                console.print(f"[red]❌ Template '{template_name}' not found[/red]")
                
                # Show available templates
                all_templates = ConfigTemplates.get_all_templates()
                if all_templates:
                    console.print(f"\n[bold]Available templates:[/bold]")
                    for t in all_templates[:5]:  # Show first 5
                        console.print(f"  • [cyan]{t.name}[/cyan]")
                return
            
            console.print(f"[blue]📦 Installing template '{template_name}'...[/blue]")
            
            # Install template
            success = await TemplateInstaller.install_template(
                template, workflow_manager, suite_manager, force
            )
            
            if success:
                console.print(f"[green]✅ Installed workflow template '{template_name}'[/green]")
                
                # Show details
                console.print(f"\n[bold]Installed Workflow Details:[/bold]")
                console.print(f"  Name: [cyan]{template.name}[/cyan]")
                console.print(f"  Category: [green]{template.category.value}[/green]")
                console.print(f"  Description: {template.description}")
                console.print(f"  Required Servers: {', '.join(template.required_servers)}")
                if template.optional_servers:
                    console.print(f"  Optional Servers: {', '.join(template.optional_servers)}")
                
            else:
                console.print(f"[red]❌ Failed to install template '{template_name}'[/red]")
                
        except Exception as e:
            console.print(f"[red]❌ Failed to install template: {e}[/red]")
    
    asyncio.run(install_template())


@workflow.command("install-all-templates")
@click.option("--force", "-f", is_flag=True, help="Override existing workflows")
@handle_errors
def workflow_install_all_templates(force: bool):
    """Install all viable workflow templates based on available servers."""
    async def install_all_templates():
        try:
            console.print("[blue]📦 Installing all viable workflow templates...[/blue]")
            
            # Get available servers
            from mcp_manager.core.simple_manager import SimpleMCPManager
            manager = SimpleMCPManager()
            servers = manager.list_servers_fast()
            available_servers = [s.name for s in servers]
            
            console.print(f"Found {len(available_servers)} available servers")
            
            # Install templates
            results = await TemplateInstaller.install_all_templates(
                workflow_manager, suite_manager, available_servers, force
            )
            
            # Show results
            successful = [name for name, success in results.items() if success]
            failed = [name for name, success in results.items() if not success]
            
            if successful:
                console.print(f"\n[green]✅ Successfully installed {len(successful)} templates:[/green]")
                for name in successful:
                    console.print(f"  • [cyan]{name}[/cyan]")
            
            if failed:
                console.print(f"\n[yellow]⚠️ Skipped/failed {len(failed)} templates:[/yellow]")
                for name in failed:
                    console.print(f"  • [dim]{name}[/dim]")
            
            console.print(f"\n[bold]Installation Summary:[/bold] {len(successful)}/{len(results)} successful")
            
        except Exception as e:
            console.print(f"[red]❌ Failed to install templates: {e}[/red]")
    
    asyncio.run(install_all_templates())


@workflow.command("status")
@handle_errors
def workflow_status():
    """Show current workflow status and active configuration."""
    async def show_status():
        try:
            console.print("[bold blue]📊 Workflow Status[/bold blue]")
            
            # Active workflow
            active = workflow_manager.get_active_workflow()
            if active:
                console.print(Panel.fit(
                    f"[green]Active Workflow:[/green] [cyan]{active.name}[/cyan]\n"
                    f"[green]Category:[/green] {active.category.value if active.category else 'general'}\n"
                    f"[green]Description:[/green] {active.description}\n"
                    f"[green]Suites:[/green] {len(active.suite_ids)}\n"
                    f"[green]Priority:[/green] {active.priority}",
                    title="[green]🟢 Active[/green]",
                    border_style="green"
                ))
                
                # Show active suites
                console.print(f"\n[bold]Active Suites:[/bold]")
                for suite_id in active.suite_ids:
                    suite = await suite_manager.get_suite(suite_id)
                    if suite:
                        console.print(f"  • [cyan]{suite.name}[/cyan] - {len(suite.memberships)} servers")
                        
            else:
                console.print(Panel.fit(
                    "[dim]No workflow currently active[/dim]",
                    title="[yellow]⚪ Inactive[/yellow]",
                    border_style="yellow"
                ))
            
            # Summary statistics
            all_workflows = workflow_manager.list_workflows()
            categories = {}
            for workflow in all_workflows:
                cat = workflow.category.value if workflow.category else 'general'
                categories[cat] = categories.get(cat, 0) + 1
            
            console.print(f"\n[bold]Summary:[/bold]")
            console.print(f"  Total Workflows: [cyan]{len(all_workflows)}[/cyan]")
            console.print(f"  Categories: [green]{len(categories)}[/green]")
            
            if categories:
                console.print(f"  Breakdown:")
                for cat, count in sorted(categories.items()):
                    console.print(f"    • {cat}: {count}")
            
        except Exception as e:
            console.print(f"[red]❌ Failed to show workflow status: {e}[/red]")
    
    asyncio.run(show_status())