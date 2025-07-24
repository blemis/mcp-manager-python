"""
Proxy server commands for MCP Manager CLI.

Manages the MCP proxy server for protocol translation and unified endpoint access.
"""

import asyncio
import json
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from mcp_manager.cli.helpers import handle_errors

console = Console()


def proxy_commands(cli_context):
    """Add proxy commands to the CLI."""
    
    @click.group("proxy")
    def proxy():
        """Manage MCP proxy server for unified endpoint access."""
        pass
    
    
    @proxy.command("start")
    @click.option("--host", "-h", default="127.0.0.1", help="Proxy server host")
    @click.option("--port", "-p", default=3001, help="Proxy server port")
    @click.option("--mode", "-m", 
                  type=click.Choice(["transparent", "aggregating", "load_balancing", "failover"]),
                  default="transparent", help="Proxy operation mode")
    @click.option("--config", "-c", type=click.Path(exists=True), help="Proxy configuration file")
    @click.option("--daemon", "-d", is_flag=True, help="Run as daemon process")
    @handle_errors
    def proxy_start(host: str, port: int, mode: str, config: Optional[str], daemon: bool):
        """Start the MCP proxy server."""
        
        async def start_proxy():
            try:
                from mcp_manager.core.proxy.models import ProxyConfig, ProxyMode
                from mcp_manager.core.proxy.server import ProxyServer
                
                # Load configuration
                if config:
                    console.print(f"[blue]📄 Loading configuration from {config}[/blue]")
                    with open(config, 'r') as f:
                        config_data = json.load(f)
                    
                    proxy_config = ProxyConfig(**config_data)
                else:
                    proxy_config = ProxyConfig(
                        host=host,
                        port=port,
                        mode=ProxyMode(mode)
                    )
                
                console.print(f"[blue]🚀 Starting MCP proxy server...[/blue]")
                console.print(f"   Host: [cyan]{proxy_config.host}[/cyan]")
                console.print(f"   Port: [cyan]{proxy_config.port}[/cyan]")
                console.print(f"   Mode: [cyan]{proxy_config.mode.value}[/cyan]")
                console.print(f"   Web Interface: [cyan]http://{proxy_config.host}:{proxy_config.port}[/cyan]")
                
                if daemon:
                    console.print("[yellow]⚠️  Daemon mode not yet implemented[/yellow]")
                    console.print("[dim]Starting in foreground mode...[/dim]")
                
                # Create and start server
                server = ProxyServer(proxy_config)
                
                console.print("[green]✅ Proxy server started successfully[/green]")
                console.print("[dim]Press Ctrl+C to stop[/dim]")
                
                # Run server
                await server.run_forever()
                
            except KeyboardInterrupt:
                console.print("\n[yellow]🛑 Proxy server stopped by user[/yellow]")
            except Exception as e:
                console.print(f"[red]❌ Failed to start proxy server: {e}[/red]")
        
        asyncio.run(start_proxy())
    
    
    @proxy.command("status")
    @click.option("--host", "-h", default="127.0.0.1", help="Proxy server host")
    @click.option("--port", "-p", default=3001, help="Proxy server port")
    @handle_errors
    def proxy_status(host: str, port: int):
        """Check proxy server status."""
        
        async def check_status():
            try:
                import aiohttp
                
                base_url = f"http://{host}:{port}"
                console.print(f"[blue]🔍 Checking proxy server at {base_url}[/blue]")
                
                async with aiohttp.ClientSession() as session:
                    # Check health endpoint
                    console.print("Checking health... ", end="")
                    try:
                        async with session.get(f"{base_url}/health", timeout=10) as response:
                            if response.status == 200:
                                health_data = await response.json()
                                console.print("[green]✅ Healthy[/green]")
                                
                                console.print(f"[bold blue]📊 Proxy Server Status[/bold blue]")
                                console.print(f"Status: [green]{health_data.get('status', 'unknown')}[/green]")
                                console.print(f"Active Servers: [cyan]{health_data.get('active_servers', 0)}[/cyan]")
                                console.print(f"Total Servers: [cyan]{health_data.get('total_servers', 0)}[/cyan]")
                                console.print(f"Active Connections: [cyan]{health_data.get('active_connections', 0)}[/cyan]")
                            else:
                                console.print(f"[red]❌ {response.status}[/red]")
                    except asyncio.TimeoutError:
                        console.print("[red]❌ Timeout[/red]")
                        return
                    except Exception as e:
                        console.print(f"[red]❌ {e}[/red]")
                        return
                    
                    # Get detailed status
                    try:
                        async with session.get(f"{base_url}/status", timeout=10) as response:
                            if response.status == 200:
                                status_data = await response.json()
                                
                                # Show server list
                                servers = status_data.get('servers', {})
                                if servers:
                                    console.print(f"\n[bold cyan]🖥️  Configured Servers ({len(servers)}):[/bold cyan]")
                                    
                                    table = Table(show_header=True, header_style="bold cyan")
                                    table.add_column("Name", style="green")
                                    table.add_column("URL", style="blue")
                                    table.add_column("Protocol", style="yellow")
                                    table.add_column("Status", style="white")
                                    table.add_column("Response Time", style="dim")
                                    
                                    for name, server_info in servers.items():
                                        status_icon = {
                                            "online": "🟢",
                                            "offline": "🔴",
                                            "error": "❌",
                                            "initializing": "🟡"
                                        }.get(server_info.get('status', 'unknown'), "❓")
                                        
                                        response_time = server_info.get('response_time_ms')
                                        response_time_str = f"{response_time:.1f}ms" if response_time else "N/A"
                                        
                                        table.add_row(
                                            name,
                                            server_info.get('url', 'N/A'),
                                            server_info.get('protocol_version', 'N/A'),
                                            f"{status_icon} {server_info.get('status', 'unknown')}",
                                            response_time_str
                                        )
                                    
                                    console.print(table)
                                
                                # Show configuration
                                config = status_data.get('proxy_config', {})
                                console.print(f"\n[bold cyan]⚙️  Configuration:[/bold cyan]")
                                console.print(f"Mode: [yellow]{config.get('mode', 'unknown')}[/yellow]")
                                console.print(f"Protocol Translation: [yellow]{config.get('protocol_translation', False)}[/yellow]")
                                console.print(f"Load Balancing: [yellow]{config.get('load_balancing', False)}[/yellow]")
                                console.print(f"Failover: [yellow]{config.get('failover', False)}[/yellow]")
                                
                    except Exception as e:
                        console.print(f"[dim]Could not get detailed status: {e}[/dim]")
                
            except Exception as e:
                console.print(f"[red]Failed to check proxy status: {e}[/red]")
        
        asyncio.run(check_status())
    
    
    @proxy.command("stats")
    @click.option("--host", "-h", default="127.0.0.1", help="Proxy server host")
    @click.option("--port", "-p", default=3001, help="Proxy server port")
    @handle_errors
    def proxy_stats(host: str, port: int):
        """Show proxy server statistics."""
        
        async def show_stats():
            try:
                import aiohttp
                
                base_url = f"http://{host}:{port}"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{base_url}/stats", timeout=10) as response:
                        if response.status == 200:
                            stats = await response.json()
                            
                            console.print("[bold blue]📈 Proxy Server Statistics[/bold blue]\n")
                            
                            # Request statistics
                            total_requests = stats.get('total_requests', 0)
                            successful_requests = stats.get('successful_requests', 0)
                            failed_requests = stats.get('failed_requests', 0)
                            success_rate = stats.get('success_rate_percent', 0)
                            
                            console.print(f"[bold cyan]📊 Request Statistics:[/bold cyan]")
                            console.print(f"Total Requests: [cyan]{total_requests}[/cyan]")
                            console.print(f"Successful: [green]{successful_requests}[/green]")
                            console.print(f"Failed: [red]{failed_requests}[/red]")
                            console.print(f"Success Rate: [green]{success_rate:.1f}%[/green]")
                            
                            # Performance statistics
                            console.print(f"\n[bold cyan]⚡ Performance:[/bold cyan]")
                            console.print(f"Average Response Time: [cyan]{stats.get('average_response_time_ms', 0):.2f}ms[/cyan]")
                            console.print(f"Min Response Time: [cyan]{stats.get('min_response_time_ms', 0):.2f}ms[/cyan]")
                            console.print(f"Max Response Time: [cyan]{stats.get('max_response_time_ms', 0):.2f}ms[/cyan]")
                            
                            # Server statistics
                            console.print(f"\n[bold cyan]🖥️  Servers:[/bold cyan]")
                            console.print(f"Active Servers: [green]{stats.get('active_servers', 0)}[/green]")
                            console.print(f"Total Servers: [cyan]{stats.get('total_servers', 0)}[/cyan]")
                            console.print(f"Uptime: [cyan]{stats.get('uptime_seconds', 0):.0f}s[/cyan]")
                            
                            # Requests per server
                            requests_per_server = stats.get('requests_per_server', {})
                            if requests_per_server:
                                console.print(f"\n[bold cyan]📈 Requests per Server:[/bold cyan]")
                                for server, count in requests_per_server.items():
                                    console.print(f"  • {server}: [cyan]{count}[/cyan] requests")
                            
                            # Errors per server
                            errors_per_server = stats.get('errors_per_server', {})
                            if any(count > 0 for count in errors_per_server.values()):
                                console.print(f"\n[bold red]❌ Errors per Server:[/bold red]")
                                for server, count in errors_per_server.items():
                                    if count > 0:
                                        console.print(f"  • {server}: [red]{count}[/red] errors")
                            
                            # Translation statistics
                            translation_stats = stats.get('translation_stats', {})
                            if translation_stats:
                                console.print(f"\n[bold cyan]🔄 Protocol Translation:[/bold cyan]")
                                console.print(f"Translations Performed: [cyan]{translation_stats.get('translations_performed', 0)}[/cyan]")
                                console.print(f"Cache Hits: [green]{translation_stats.get('cache_hits', 0)}[/green]")
                                console.print(f"Cache Hit Rate: [green]{translation_stats.get('cache_hit_rate_percent', 0):.1f}%[/green]")
                                
                        else:
                            console.print(f"[red]❌ Failed to get stats: HTTP {response.status}[/red]")
                
            except Exception as e:
                console.print(f"[red]Failed to get proxy statistics: {e}[/red]")
        
        asyncio.run(show_stats())
    
    
    @proxy.command("add-server")
    @click.argument("name")
    @click.argument("url")
    @click.option("--protocol", "-p", default="mcp-v1", 
                  type=click.Choice(["mcp-v1", "mcp-v2", "legacy"]),
                  help="MCP protocol version")
    @click.option("--weight", "-w", default=100, help="Load balancing weight")
    @click.option("--timeout", "-t", default=30, help="Request timeout in seconds")
    @click.option("--proxy-host", default="127.0.0.1", help="Proxy server host")
    @click.option("--proxy-port", default=3001, help="Proxy server port")
    @handle_errors
    def proxy_add_server(name: str, url: str, protocol: str, weight: int, 
                        timeout: int, proxy_host: str, proxy_port: int):
        """Add server to running proxy."""
        
        async def add_server():
            try:
                import aiohttp
                
                base_url = f"http://{proxy_host}:{proxy_port}"
                
                server_data = {
                    "name": name,
                    "url": url,
                    "protocol_version": protocol,
                    "weight": weight,
                    "timeout_seconds": timeout
                }
                
                console.print(f"[blue]➕ Adding server '{name}' to proxy...[/blue]")
                console.print(f"   URL: [cyan]{url}[/cyan]")
                console.print(f"   Protocol: [cyan]{protocol}[/cyan]")
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{base_url}/servers",
                        json=server_data,
                        timeout=10
                    ) as response:
                        result = await response.json()
                        
                        if response.status == 200:
                            console.print(f"[green]✅ {result.get('message', 'Server added successfully')}[/green]")
                        else:
                            console.print(f"[red]❌ {result.get('message', 'Failed to add server')}[/red]")
                
            except Exception as e:
                console.print(f"[red]Failed to add server: {e}[/red]")
        
        asyncio.run(add_server())
    
    
    @proxy.command("remove-server")
    @click.argument("name")
    @click.option("--proxy-host", default="127.0.0.1", help="Proxy server host")
    @click.option("--proxy-port", default=3001, help="Proxy server port")
    @handle_errors
    def proxy_remove_server(name: str, proxy_host: str, proxy_port: int):
        """Remove server from running proxy."""
        
        async def remove_server():
            try:
                import aiohttp
                
                base_url = f"http://{proxy_host}:{proxy_port}"
                
                console.print(f"[blue]➖ Removing server '{name}' from proxy...[/blue]")
                
                async with aiohttp.ClientSession() as session:
                    async with session.delete(
                        f"{base_url}/servers/{name}",
                        timeout=10
                    ) as response:
                        result = await response.json()
                        
                        if response.status == 200:
                            console.print(f"[green]✅ {result.get('message', 'Server removed successfully')}[/green]")
                        else:
                            console.print(f"[red]❌ {result.get('message', 'Failed to remove server')}[/red]")
                
            except Exception as e:
                console.print(f"[red]Failed to remove server: {e}[/red]")
        
        asyncio.run(remove_server())
    
    
    @proxy.command("test")
    @click.option("--host", "-h", default="127.0.0.1", help="Proxy server host")
    @click.option("--port", "-p", default=3001, help="Proxy server port")
    @click.option("--method", "-m", default="tools/list", help="MCP method to test")
    @handle_errors
    def proxy_test(host: str, port: int, method: str):
        """Test proxy server with sample request."""
        
        async def test_proxy():
            try:
                import aiohttp
                
                base_url = f"http://{host}:{port}"
                
                # Create test request
                test_request = {
                    "jsonrpc": "2.0",
                    "method": method,
                    "id": "test_request",
                    "params": {}
                }
                
                console.print(f"[blue]🧪 Testing proxy server at {base_url}[/blue]")
                console.print(f"Method: [cyan]{method}[/cyan]")
                
                async with aiohttp.ClientSession() as session:
                    start_time = asyncio.get_event_loop().time()
                    
                    async with session.post(
                        f"{base_url}/mcp",
                        json=test_request,
                        timeout=30
                    ) as response:
                        response_time = (asyncio.get_event_loop().time() - start_time) * 1000
                        
                        console.print(f"Response Time: [cyan]{response_time:.2f}ms[/cyan]")
                        console.print(f"Status Code: [cyan]{response.status}[/cyan]")
                        
                        # Show proxy headers
                        proxy_server = response.headers.get('X-Proxy-Server')
                        if proxy_server:
                            console.print(f"Proxy Server: [green]{proxy_server}[/green]")
                        
                        protocol_version = response.headers.get('X-Protocol-Version')
                        if protocol_version:
                            console.print(f"Protocol Version: [yellow]{protocol_version}[/yellow]")
                        
                        # Show response
                        if response.status == 200:
                            result = await response.json()
                            console.print(f"\n[green]✅ Test successful![/green]")
                            
                            if "result" in result:
                                console.print("[dim]Response preview:[/dim]")
                                result_preview = str(result["result"])[:200]
                                if len(str(result["result"])) > 200:
                                    result_preview += "..."
                                console.print(f"[dim]{result_preview}[/dim]")
                            
                            if "error" in result:
                                console.print(f"[yellow]⚠️  Server returned error: {result['error'].get('message', 'Unknown error')}[/yellow]")
                                
                        else:
                            console.print(f"[red]❌ Test failed with status {response.status}[/red]")
                            error_text = await response.text()
                            console.print(f"[dim]{error_text[:200]}[/dim]")
                
            except Exception as e:
                console.print(f"[red]Proxy test failed: {e}[/red]")
        
        asyncio.run(test_proxy())
    
    
    @proxy.command("config")
    @click.option("--template", "-t", is_flag=True, help="Generate configuration template")
    @click.option("--output", "-o", help="Output file path")
    @handle_errors
    def proxy_config(template: bool, output: Optional[str]):
        """Generate or manage proxy configuration."""
        
        def generate_config():
            if template:
                config_template = {
                    "host": "127.0.0.1",
                    "port": 3001,
                    "workers": 4,
                    "mode": "transparent",
                    "timeout_seconds": 30,
                    "max_concurrent_requests": 100,
                    "enable_load_balancing": True,
                    "enable_failover": True,
                    "health_check_enabled": True,
                    "enable_protocol_translation": True,
                    "default_protocol_version": "mcp-v1",
                    "enable_request_logging": True,
                    "enable_metrics": True,
                    "log_level": "INFO",
                    "servers": [
                        {
                            "name": "example-server-1",
                            "url": "http://localhost:3000/mcp",
                            "protocol_version": "mcp-v1",
                            "weight": 100,
                            "timeout_seconds": 30,
                            "max_retries": 3,
                            "health_check_interval": 60,
                            "headers": {},
                            "supported_tools": [],
                            "supported_resources": [],
                            "supported_prompts": []
                        }
                    ]
                }
                
                if output:
                    output_path = Path(output)
                    with open(output_path, 'w') as f:
                        json.dump(config_template, f, indent=2)
                    console.print(f"[green]✅ Configuration template saved to {output_path}[/green]")
                else:
                    console.print("[bold blue]📄 Proxy Configuration Template[/bold blue]\n")
                    console.print(json.dumps(config_template, indent=2))
                    console.print(f"\n[dim]💡 Save this template: [cyan]mcp-manager proxy config --template --output config.json[/cyan][/dim]")
            else:
                console.print("[yellow]Use --template flag to generate configuration template[/yellow]")
        
        generate_config()
    
    
    return [proxy]