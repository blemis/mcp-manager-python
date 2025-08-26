"""
Admin CLI commands for managing test categories and suite mappings.
"""

import click
import asyncio
from typing import Optional

from mcp_manager.core.test_management.category_manager import TestCategoryManager
from mcp_manager.core.test_management.models import TestScope
from mcp_manager.core.suites.suite_manager import SuiteManager
from mcp_manager.core.discovery import ServerDiscovery
from mcp_manager.utils.logging import get_logger
from pathlib import Path

logger = get_logger(__name__)


async def _get_server_description(server_name: str, server_type: str) -> str:
    """Get server description from registry database."""
    try:
        from ..database.registry import MCPServerRegistry
        
        registry = MCPServerRegistry()
        server_info = await registry.get_server(server_name)
        
        if server_info and server_info.description:
            return server_info.description
        
        # Fallback for servers not in registry yet
        return f"{server_type} MCP server: {server_name}"
        
    except Exception as e:
        logger.error(f"Failed to get server description for {server_name}: {e}")
        return f"{server_type} MCP server: {server_name}"


@click.group(name='test-admin')
def test_admin():
    """Admin commands for managing test categories and suites."""
    pass


@test_admin.command()
@click.option('--scope', type=click.Choice([s.value for s in TestScope]), help='Filter by test scope')
def list_categories(scope: Optional[str]):
    """List all test categories."""
    try:
        manager = TestCategoryManager()
        test_scope = TestScope(scope) if scope else None
        categories = manager.list_categories(test_scope)
        
        if not categories:
            click.echo("No test categories found.")
            return
        
        click.echo(f"\nFound {len(categories)} test categories:")
        click.echo("-" * 60)
        
        for category in categories:
            suite_id = manager.db.get_suite_for_category(category.id)
            click.echo(f"📁 {category.name} ({category.id})")
            click.echo(f"   Scope: {category.scope.value}")
            click.echo(f"   Pattern: {category.test_file_pattern}")
            click.echo(f"   Suite: {suite_id or 'None'}")
            click.echo(f"   Required Servers: {', '.join(category.required_servers)}")
            click.echo()
            
    except Exception as e:
        click.echo(f"❌ Error listing categories: {e}")


@test_admin.command()
@click.argument('name')
@click.argument('description')
@click.argument('test_file_pattern')
@click.option('--scope', type=click.Choice([s.value for s in TestScope]), 
              default=TestScope.INTEGRATION.value, help='Test scope')
@click.option('--required-servers', help='Comma-separated list of required servers')
@click.option('--optional-servers', help='Comma-separated list of optional servers')
def create_category(name: str, description: str, test_file_pattern: str, 
                   scope: str, required_servers: Optional[str], 
                   optional_servers: Optional[str]):
    """Create a new test category."""
    try:
        manager = TestCategoryManager()
        test_scope = TestScope(scope)
        
        required = required_servers.split(',') if required_servers else []
        optional = optional_servers.split(',') if optional_servers else []
        
        category = manager.create_category(
            name=name,
            description=description,
            scope=test_scope,
            test_file_pattern=test_file_pattern,
            required_servers=required,
            optional_servers=optional
        )
        
        if category:
            click.echo(f"✅ Created test category: {name}")
            click.echo(f"   ID: {category.id}")
            click.echo(f"   Pattern: {test_file_pattern}")
            click.echo(f"   Required servers: {', '.join(required)}")
        else:
            click.echo(f"❌ Failed to create test category: {name}")
            
    except Exception as e:
        click.echo(f"❌ Error creating category: {e}")


@test_admin.command()
@click.argument('category_id')
@click.argument('suite_id')
@click.option('--priority', type=int, default=50, help='Mapping priority (higher = preferred)')
def map_suite(category_id: str, suite_id: str, priority: int):
    """Map a test category to a suite."""
    try:
        manager = TestCategoryManager()
        
        # Check if category exists
        category = manager.db.get_test_category(category_id)
        if not category:
            click.echo(f"❌ Test category '{category_id}' not found")
            return
        
        success = manager.map_category_to_suite(
            category_id=category_id,
            suite_id=suite_id,
            priority=priority,
            created_by="admin"
        )
        
        if success:
            click.echo(f"✅ Mapped category '{category_id}' to suite '{suite_id}'")
            click.echo(f"   Priority: {priority}")
        else:
            click.echo(f"❌ Failed to create mapping")
            
    except Exception as e:
        click.echo(f"❌ Error creating mapping: {e}")


@test_admin.command()
@click.argument('test_file')
def check_mapping(test_file: str):
    """Check which category and suite a test file would use."""
    try:
        manager = TestCategoryManager()
        
        category = manager.get_category_for_test_file(test_file)
        if not category:
            click.echo(f"❌ No category found for test file: {test_file}")
            return
        
        suite_id = manager.get_suite_for_test_file(test_file)
        
        click.echo(f"🔍 Test file: {test_file}")
        click.echo(f"📁 Category: {category.name} ({category.id})")
        click.echo(f"📦 Suite: {suite_id or 'None'}")
        click.echo(f"🎯 Scope: {category.scope.value}")
        click.echo(f"🖥️  Required servers: {', '.join(category.required_servers)}")
        
    except Exception as e:
        click.echo(f"❌ Error checking mapping: {e}")


@test_admin.command()
def init_defaults():
    """Initialize default test categories and mappings."""
    try:
        click.echo("🔧 Initializing default test categories...")
        manager = TestCategoryManager()  # This triggers default creation
        categories = manager.list_categories()
        
        click.echo(f"✅ Initialized {len(categories)} default categories:")
        for category in categories:
            suite_id = manager.db.get_suite_for_category(category.id)
            click.echo(f"   • {category.name} → {suite_id}")
            
    except Exception as e:
        click.echo(f"❌ Error initializing defaults: {e}")


@test_admin.command()
def list_suites():
    """List all test suites and their MCP servers."""
    try:
        # Use test database path
        test_db_path = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "test_suites.db"
        suite_manager = SuiteManager(test_db_path)
        
        async def list_all_suites():
            suites = await suite_manager.list_suites()
            
            if not suites:
                click.echo("No test suites found.")
                return
            
            click.echo(f"\n📋 Found {len(suites)} test suites:")
            click.echo("=" * 80)
            
            for suite in suites:
                click.echo(f"\n🎯 {suite.name} ({suite.id})")
                click.echo(f"   Description: {suite.description}")
                click.echo(f"   Category: {suite.category}")
                click.echo(f"   Created: {suite.created_at.strftime('%Y-%m-%d %H:%M')}")
                
                if suite.memberships:
                    click.echo(f"   📦 MCP Servers ({len(suite.memberships)}):")
                    
                    # Sort by priority (highest first)
                    sorted_memberships = sorted(suite.memberships, key=lambda m: m.priority, reverse=True)
                    
                    for membership in sorted_memberships:
                        role_emoji = {
                            "primary": "🎯",
                            "secondary": "⚡", 
                            "optional": "🔧",
                            "member": "📦"
                        }.get(membership.role, "📦")
                        
                        type_emoji = {
                            "docker-desktop": "🐳",
                            "npm": "📦",
                            "custom": "⚙️"
                        }.get(membership.server_type, "❓")
                        
                        click.echo(f"      {role_emoji}{type_emoji} {membership.server_name}")
                        click.echo(f"         Role: {membership.role} (priority: {membership.priority})")
                        click.echo(f"         Type: {membership.server_type}")
                        if membership.server_command:
                            click.echo(f"         Command: {membership.server_command}")
                        
                        # Add server description from registry
                        description = await _get_server_description(membership.server_name, membership.server_type)
                        if description:
                            click.echo(f"         Description: {description}")
                else:
                    click.echo("   📦 No MCP servers configured")
        
        asyncio.run(list_all_suites())
        
    except Exception as e:
        click.echo(f"❌ Error listing suites: {e}")


@test_admin.command()
@click.argument('suite_id')
def show_suite(suite_id: str):
    """Show detailed information about a specific test suite."""
    try:
        # Use test database path
        test_db_path = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "test_suites.db"
        suite_manager = SuiteManager(test_db_path)
        
        async def show_suite_details():
            suite = await suite_manager.get_suite(suite_id)
            
            if not suite:
                click.echo(f"❌ Suite '{suite_id}' not found")
                return
            
            click.echo(f"\n🎯 Suite Details: {suite.name}")
            click.echo("=" * 60)
            click.echo(f"ID: {suite.id}")
            click.echo(f"Description: {suite.description}")
            click.echo(f"Category: {suite.category}")
            click.echo(f"Created: {suite.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            click.echo(f"Updated: {suite.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if suite.config:
                click.echo(f"Config: {suite.config}")
            
            if suite.memberships:
                click.echo(f"\n📦 MCP Servers ({len(suite.memberships)}):")
                click.echo("-" * 40)
                
                # Sort by priority (highest first) 
                sorted_memberships = sorted(suite.memberships, key=lambda m: m.priority, reverse=True)
                
                for i, membership in enumerate(sorted_memberships, 1):
                    role_emoji = {
                        "primary": "🎯",
                        "secondary": "⚡",
                        "optional": "🔧", 
                        "member": "📦"
                    }.get(membership.role, "📦")
                    
                    type_emoji = {
                        "docker-desktop": "🐳",
                        "npm": "📦",
                        "custom": "⚙️"
                    }.get(membership.server_type, "❓")
                    
                    click.echo(f"\n{i}. {role_emoji}{type_emoji} {membership.server_name}")
                    
                    # Add description from registry
                    description = await _get_server_description(membership.server_name, membership.server_type)
                    if description:
                        click.echo(f"   Description: {description}")
                    
                    click.echo(f"   Role: {membership.role}")
                    click.echo(f"   Priority: {membership.priority}")
                    click.echo(f"   Type: {membership.server_type}")
                    click.echo(f"   Command: {membership.server_command}")
                    click.echo(f"   Added: {membership.added_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    if membership.config_overrides:
                        click.echo(f"   Config: {membership.config_overrides}")
            else:
                click.echo("\n📦 No MCP servers configured in this suite")
        
        asyncio.run(show_suite_details())
        
    except Exception as e:
        click.echo(f"❌ Error showing suite: {e}")


if __name__ == '__main__':
    test_admin()