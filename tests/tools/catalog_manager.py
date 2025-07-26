#!/usr/bin/env python3
"""
Test Catalog Manager CLI

Command-line interface for managing the JSON test catalog database.
Provides easy access to test discovery, search, and reusability features.
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.tools.test_catalog_db import TestCatalogDB


def main():
    """Main CLI interface for test catalog management."""
    parser = argparse.ArgumentParser(
        description="MCP Manager Test Catalog Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s rebuild                      # Rebuild entire catalog
  %(prog)s search --category core       # Search by category
  %(prog)s search --priority critical   # Search by priority
  %(prog)s list --collection-type any   # List collection-agnostic tests
  %(prog)s stats                        # Show catalog statistics
  %(prog)s scenarios 5                  # Show scenarios for suite ID 5
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Rebuild command
    rebuild_parser = subparsers.add_parser('rebuild', help='Rebuild test catalog from JSON files')
    rebuild_parser.add_argument('--force', action='store_true', help='Force rebuild even if files unchanged')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search test catalog')
    search_parser.add_argument('--category', help='Filter by category')
    search_parser.add_argument('--priority', help='Filter by priority')
    search_parser.add_argument('--collection-type', help='Filter by collection type')
    search_parser.add_argument('--command', help='Filter by command pattern')
    search_parser.add_argument('--npm', action='store_true', help='NPM server compatible')
    search_parser.add_argument('--docker-desktop', action='store_true', help='Docker Desktop compatible')
    search_parser.add_argument('--empty-state', action='store_true', help='Empty state compatible')
    search_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all test suites')
    list_parser.add_argument('--collection-type', help='Filter by collection type')
    list_parser.add_argument('--brief', action='store_true', help='Brief output')
    
    # Scenarios command
    scenarios_parser = subparsers.add_parser('scenarios', help='Show scenarios for a test suite')
    scenarios_parser.add_argument('suite_id', type=int, help='Test suite ID')
    scenarios_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show catalog statistics')
    stats_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Remove orphaned catalog entries')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        catalog = TestCatalogDB()
        
        if args.command == 'rebuild':
            print("🔄 Rebuilding test catalog...")
            
            # Clear existing if force rebuild
            if args.force:
                import sqlite3
                with sqlite3.connect(catalog.db_path) as conn:
                    conn.execute("DELETE FROM test_suites")
                    conn.commit()
                print("🗑️  Cleared existing catalog entries")
            
            success, total = catalog.index_all_test_files()
            print(f"✅ Catalog rebuilt: {success}/{total} files indexed")
            
            if success > 0:
                stats = catalog.get_statistics()
                print(f"📊 Total: {stats['total_test_suites']} suites, {stats['total_test_scenarios']} scenarios")
        
        elif args.command == 'search':
            compatibility = {}
            if args.npm:
                compatibility['npm_servers'] = True
            if args.docker_desktop:
                compatibility['docker_desktop_servers'] = True
            if args.empty_state:
                compatibility['empty_state'] = True
            
            results = catalog.search_tests(
                category=args.category,
                priority=args.priority,
                collection_type=getattr(args, 'collection_type'),
                command_pattern=args.command,
                compatibility=compatibility if compatibility else None
            )
            
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                print(f"🔍 Found {len(results)} matching test suites:")
                for result in results:
                    priority_emoji = {
                        'critical': '🔴',
                        'high': '🟡', 
                        'medium': '🟢',
                        'low': '🔵'
                    }.get(result['priority'], '⚪')
                    
                    print(f"\n{priority_emoji} {result['test_suite_name']} (ID: {result['id']})")
                    print(f"   📂 Category: {result['category']}")
                    print(f"   📊 Priority: {result['priority']}")
                    print(f"   🧪 Scenarios: {result['scenario_count']}")
                    print(f"   📄 Description: {result['test_suite_description']}")
                    print(f"   📁 File: {result['file_path']}")
                    
                    if result['tags']:
                        tags = json.loads(result['tags']) if isinstance(result['tags'], str) else result['tags']
                        print(f"   🏷️  Tags: {', '.join(tags)}")
        
        elif args.command == 'list':
            results = catalog.search_tests(collection_type=getattr(args, 'collection_type'))
            
            print(f"📋 Test Suites ({len(results)} total):")
            for result in results:
                if args.brief:
                    print(f"  {result['id']:2d}. {result['test_suite_name']} ({result['category']})")
                else:
                    print(f"\n  {result['id']:2d}. {result['test_suite_name']}")
                    print(f"      Category: {result['category']}, Priority: {result['priority']}")
                    print(f"      Scenarios: {result['scenario_count']}, File: {result['file_path']}")
        
        elif args.command == 'scenarios':
            scenarios = catalog.get_test_scenarios(args.suite_id)
            
            if args.json:
                print(json.dumps(scenarios, indent=2))
            else:
                print(f"🧪 Test Scenarios for Suite ID {args.suite_id} ({len(scenarios)} scenarios):")
                for i, scenario in enumerate(scenarios, 1):
                    print(f"\n  {i:2d}. {scenario['test_name']}")
                    print(f"      Description: {scenario['description']}")
                    print(f"      Command: {scenario['command']}")
                    print(f"      Exit Code: {scenario['expected_exit_code']}, Timeout: {scenario['timeout']}s")
                    
                    if scenario['expected_output_contains']:
                        print(f"      Expected Output: {', '.join(scenario['expected_output_contains'])}")
                    
                    if scenario['collection_state'] != 'any':
                        print(f"      Collection State: {scenario['collection_state']}")
        
        elif args.command == 'stats':
            stats = catalog.get_statistics()
            
            if args.json:
                print(json.dumps(stats, indent=2))
            else:
                print("📊 Test Catalog Statistics:")
                print(f"   📁 Total Test Suites: {stats['total_test_suites']}")
                print(f"   🧪 Total Test Scenarios: {stats['total_test_scenarios']}")
                
                print(f"\n📂 Categories:")
                for category, count in stats['categories'].items():
                    print(f"   {category}: {count} suites")
                
                print(f"\n📊 Priorities:")
                for priority, count in stats['priorities'].items():
                    print(f"   {priority}: {count} suites")
                
                print(f"\n🔗 Collection Compatibility:")
                comp = stats['compatibility']
                print(f"   NPM servers: {comp['npm_servers']}/{stats['total_test_suites']} suites")
                print(f"   Docker Desktop: {comp['docker_desktop_servers']}/{stats['total_test_suites']} suites")
                print(f"   Docker Hub: {comp['docker_hub_servers']}/{stats['total_test_suites']} suites")
                print(f"   Empty state: {comp['empty_state']}/{stats['total_test_suites']} suites")
        
        elif args.command == 'cleanup':
            print("🧹 Cleaning up orphaned catalog entries...")
            removed = catalog.cleanup_orphaned_entries()
            print(f"✅ Removed {removed} orphaned entries")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())