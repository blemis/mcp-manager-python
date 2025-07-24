"""
AI configuration commands for MCP Manager CLI.
"""

import asyncio
from typing import Optional

import click
from rich.console import Console

from mcp_manager.cli.helpers import handle_errors

console = Console()


def ai_commands(cli_context):
    """Add AI commands to the CLI."""
    
    @click.group("ai")
    def ai():
        """Manage AI configuration for intelligent MCP curation."""
        pass
    
    
    @ai.command("setup")
    @click.option("--provider", type=click.Choice(["claude", "openai", "gemini", "local", "ollama"]), 
                  help="AI provider to configure")
    @click.option("--interactive", "-i", is_flag=True, help="Interactive configuration")
    @handle_errors
    def ai_setup(provider: Optional[str], interactive: bool):
        """Set up AI configuration with secure credential storage."""
        from mcp_manager.core.ai_config import ai_config_manager, AIProvider
        from rich.prompt import Prompt, Confirm
        from rich.panel import Panel
        
        console.print("[bold blue]🤖 AI Configuration Setup[/bold blue]")
        console.print("Configure AI providers for intelligent MCP server curation and recommendations.\n")
        
        # Show available providers if none specified
        if not provider and not interactive:
            console.print("[cyan]Available AI Providers:[/cyan]")
            for p in AIProvider:
                status = "✅ Configured" if ai_config_manager.is_provider_configured(p) else "❌ Not configured"
                console.print(f"  • {p.value}: {status}")
            console.print(f"\n[dim]💡 Use --provider <name> or --interactive to configure[/dim]")
            return
        
        # Interactive mode - let user choose provider
        if interactive or not provider:
            console.print("[cyan]Select AI provider to configure:[/cyan]")
            providers = list(AIProvider)
            for i, p in enumerate(providers):
                status = "✅" if ai_config_manager.is_provider_configured(p) else "❌"
                console.print(f"  {i + 1}. {status} {p.value}")
            
            try:
                from rich.prompt import IntPrompt
                choice = IntPrompt.ask("Choose provider", choices=[str(i + 1) for i in range(len(providers))])
                provider_enum = providers[choice - 1]
            except (EOFError, KeyboardInterrupt):
                console.print("[dim]Configuration cancelled[/dim]")
                return
        else:
            try:
                provider_enum = AIProvider(provider)
            except ValueError:
                console.print(f"[red]❌ Invalid provider: {provider}[/red]")
                return
        
        console.print(f"\n[blue]Configuring {provider_enum.value}...[/blue]")
        
        # Provider-specific configuration
        config = {}
        
        if provider_enum == AIProvider.CLAUDE:
            console.print("[dim]Claude API configuration:[/dim]")
            api_key = Prompt.ask("Enter your Claude API key", password=True)
            if not api_key:
                console.print("[red]❌ API key is required[/red]")
                return
            config = {
                "api_key": api_key,
                "model": "claude-3-sonnet-20240229",  # Default model
                "base_url": "https://api.anthropic.com"
            }
            
        elif provider_enum == AIProvider.OPENAI:
            console.print("[dim]OpenAI API configuration:[/dim]")
            api_key = Prompt.ask("Enter your OpenAI API key", password=True)
            if not api_key:
                console.print("[red]❌ API key is required[/red]")
                return
            model = Prompt.ask("Model", default="gpt-4")
            config = {
                "api_key": api_key,
                "model": model,
                "base_url": "https://api.openai.com/v1"
            }
            
        elif provider_enum == AIProvider.GEMINI:
            console.print("[dim]Google Gemini API configuration:[/dim]")
            api_key = Prompt.ask("Enter your Google AI API key", password=True)
            if not api_key:
                console.print("[red]❌ API key is required[/red]")
                return
            model = Prompt.ask("Model", default="gemini-pro")
            config = {
                "api_key": api_key,
                "model": model
            }
            
        elif provider_enum == AIProvider.LOCAL:
            console.print("[dim]Local AI server configuration:[/dim]")
            base_url = Prompt.ask("Server URL", default="http://localhost:1234/v1")
            model = Prompt.ask("Model name", default="local-model")
            api_key = Prompt.ask("API key (optional)", default="", show_default=False)
            config = {
                "base_url": base_url,
                "model": model,
                "api_key": api_key or None
            }
            
        elif provider_enum == AIProvider.OLLAMA:
            console.print("[dim]Ollama configuration:[/dim]")
            base_url = Prompt.ask("Ollama server URL", default="http://localhost:11434")
            model = Prompt.ask("Model name", default="llama2")
            config = {
                "base_url": base_url,
                "model": model
            }
        
        # Save configuration
        try:
            success = ai_config_manager.configure_provider(provider_enum, config)
            if success:
                console.print(f"[green]✅ {provider_enum.value} configured successfully![/green]")
                
                # Test connection
                if Confirm.ask("Test the connection now?", default=True):
                    console.print(f"[blue]Testing {provider_enum.value} connection...[/blue]")
                    
                    test_result = ai_config_manager.test_provider(provider_enum)
                    if test_result.get("success"):
                        console.print("[green]✅ Connection test successful![/green]")
                        if test_result.get("model_info"):
                            console.print(f"[dim]Model: {test_result['model_info']}[/dim]")
                    else:
                        console.print(f"[red]❌ Connection test failed: {test_result.get('error', 'Unknown error')}[/red]")
            else:
                console.print(f"[red]❌ Failed to configure {provider_enum.value}[/red]")
                
        except Exception as e:
            console.print(f"[red]❌ Configuration failed: {e}[/red]")
    
    
    @ai.command("status")
    @handle_errors  
    def ai_status():
        """Show AI configuration status."""
        from mcp_manager.core.ai_config import ai_config_manager, AIProvider
        from rich.table import Table
        
        console.print("[bold blue]🤖 AI Configuration Status[/bold blue]\n")
        
        table = Table(
            title="AI Providers",
            show_header=True,
            header_style="bold cyan",
            title_style="bold cyan"
        )
        
        table.add_column("Provider", style="white")
        table.add_column("Status", style="green")
        table.add_column("Model", style="dim")
        table.add_column("Last Tested", style="dim")
        
        for provider in AIProvider:
            is_configured = ai_config_manager.is_provider_configured(provider)
            status = "✅ Configured" if is_configured else "❌ Not configured"
            
            if is_configured:
                try:
                    config = ai_config_manager.get_provider_config(provider)
                    model = config.get("model", "Unknown")
                    last_tested = "Never"  # TODO: Add last tested tracking
                except:
                    model = "Error"
                    last_tested = "Error"
            else:
                model = "-"
                last_tested = "-"
            
            table.add_row(provider.value, status, model, last_tested)
        
        console.print(table)
        
        # Show configuration instructions
        unconfigured = [p for p in AIProvider if not ai_config_manager.is_provider_configured(p)]
        if unconfigured:
            console.print(f"\n[dim]💡 Configure providers with:[/dim]")
            console.print(f"[dim]   [cyan]mcp-manager ai setup --provider <name>[/cyan][/dim]")
            console.print(f"[dim]   [cyan]mcp-manager ai setup --interactive[/cyan][/dim]")
    
    
    @ai.command("test")  
    @click.option("--provider", type=click.Choice(["claude", "openai", "gemini", "local", "ollama"]),
                  help="Test specific provider (tests all if not specified)")
    @handle_errors
    def ai_test(provider: Optional[str]):
        """Test AI provider connectivity and functionality."""
        from mcp_manager.core.ai_config import ai_config_manager, AIProvider
        
        console.print("[bold blue]🧪 Testing AI Providers[/bold blue]\n")
        
        providers_to_test = []
        if provider:
            try:
                providers_to_test = [AIProvider(provider)]
            except ValueError:
                console.print(f"[red]❌ Invalid provider: {provider}[/red]")
                return
        else:
            providers_to_test = [p for p in AIProvider if ai_config_manager.is_provider_configured(p)]
            
            if not providers_to_test:
                console.print("[yellow]⚠️ No providers configured[/yellow]")
                console.print("[dim]Configure a provider first with: [cyan]mcp-manager ai setup[/cyan][/dim]")
                return
        
        for provider_enum in providers_to_test:
            console.print(f"[blue]Testing {provider_enum.value}...[/blue]")
            
            try:
                result = ai_config_manager.test_provider(provider_enum)
                
                if result.get("success"):
                    console.print(f"[green]✅ {provider_enum.value} - Connection successful[/green]")
                    if result.get("response_time"):
                        console.print(f"[dim]   Response time: {result['response_time']:.2f}s[/dim]")
                    if result.get("model_info"):
                        console.print(f"[dim]   Model: {result['model_info']}[/dim]")
                else:
                    console.print(f"[red]❌ {provider_enum.value} - {result.get('error', 'Unknown error')}[/red]")
                    
            except Exception as e:
                console.print(f"[red]❌ {provider_enum.value} - Test failed: {e}[/red]")
            
            console.print()  # Add spacing between providers
    
    
    @ai.command("remove")
    @click.argument("provider", type=click.Choice(["claude", "openai", "gemini", "local", "ollama"]))
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
    @handle_errors
    def ai_remove(provider: str, force: bool):
        """Remove AI provider configuration."""
        from mcp_manager.core.ai_config import ai_config_manager, AIProvider
        from rich.prompt import Confirm
        
        try:
            provider_enum = AIProvider(provider)
        except ValueError:
            console.print(f"[red]❌ Invalid provider: {provider}[/red]")
            return
        
        if not ai_config_manager.is_provider_configured(provider_enum):
            console.print(f"[yellow]⚠️ {provider} is not configured[/yellow]")
            return
        
        if not force:
            if not Confirm.ask(f"Remove {provider} configuration?"):
                console.print("[dim]Removal cancelled[/dim]")
                return
        
        try:
            success = ai_config_manager.remove_provider(provider_enum)
            if success:
                console.print(f"[green]✅ {provider} configuration removed[/green]")
            else:
                console.print(f"[red]❌ Failed to remove {provider} configuration[/red]")
                
        except Exception as e:
            console.print(f"[red]❌ Failed to remove configuration: {e}[/red]")
    
    
    @ai.command("curate")
    @click.option("--task", help="Specific task description for curation")
    @click.option("--category", help="Category to focus curation on")
    @click.option("--update-database", is_flag=True, help="Update database with AI recommendations")
    @handle_errors
    def ai_curate(task: Optional[str], category: Optional[str], update_database: bool):
        """Generate AI-powered MCP suite recommendations."""
        
        async def run_curation():
            from mcp_manager.core.ai_config import ai_config_manager, AIProvider
            
            # Check if any AI provider is configured
            configured_providers = [p for p in AIProvider if ai_config_manager.is_provider_configured(p)]
            if not configured_providers:
                console.print("[red]❌ No AI providers configured[/red]")
                console.print("[dim]Configure an AI provider first with: [cyan]mcp-manager ai setup[/cyan][/dim]")
                return
            
            console.print("[bold blue]🤖 AI MCP Suite Curation[/bold blue]\n")
            
            if task and category:
                # Generate recommendation for specific task and category
                console.print(f"[blue]Generating recommendations for:[/blue]")
                console.print(f"  Task: [cyan]{task}[/cyan]")
                console.print(f"  Category: [cyan]{category}[/cyan]")
                
                try:
                    from mcp_manager.core.ai_curation import ai_curator
                    
                    recommendations = await ai_curator.generate_task_recommendations(
                        task_description=task,
                        category=category,
                        update_database=update_database
                    )
                    
                    if recommendations:
                        console.print(f"\n[green]✅ Generated {len(recommendations)} recommendations[/green]")
                        
                        from rich.table import Table
                        table = Table(title="AI Recommendations", show_header=True, header_style="bold cyan")
                        table.add_column("Server", style="green")
                        table.add_column("Relevance", style="yellow")
                        table.add_column("Reason", style="dim")
                        
                        for rec in recommendations:
                            table.add_row(
                                rec.get("server_name", "Unknown"),
                                f"{rec.get('relevance_score', 0):.1f}",
                                rec.get("reason", "No reason provided")[:50] + "..."
                            )
                        
                        console.print(table)
                        
                        if update_database:
                            console.print(f"\n[green]✅ Database updated with recommendations[/green]")
                    else:
                        console.print("[yellow]⚠️ No recommendations generated[/yellow]")
                        
                except Exception as e:
                    console.print(f"[red]❌ Curation failed: {e}[/red]")
            
            else:
                # General curation - update all suites
                console.print("[blue]Running general suite curation...[/blue]")
                
                try:
                    from mcp_manager.core.ai_curation import ai_curator
                    
                    results = await ai_curator.curate_all_suites(update_database=update_database)
                    
                    console.print(f"\n[green]✅ Curation complete![/green]")
                    console.print(f"Suites updated: [cyan]{results.get('suites_updated', 0)}[/cyan]")
                    console.print(f"New recommendations: [cyan]{results.get('new_recommendations', 0)}[/cyan]")
                    
                    if update_database:
                        console.print(f"Database changes: [cyan]{results.get('database_changes', 0)}[/cyan]")
                    
                except Exception as e:
                    console.print(f"[red]❌ Curation failed: {e}[/red]")
        
        asyncio.run(run_curation())
    
    return [ai]