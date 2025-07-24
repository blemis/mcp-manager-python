#!/usr/bin/env python3
"""
Show Test Output Files for Bug Fixing and Sharing

Intelligent utility that shows EXACTLY which files you need to share for debugging,
based on what tests actually ran and which ones failed.
"""

from pathlib import Path
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

def analyze_test_results() -> Dict:
    """Analyze test results to determine exactly what files are needed for debugging."""
    root_dir = Path(__file__).parent.parent.parent
    results_dir = root_dir / "tests" / "results"
    summary_file = results_dir / "test-results-summary.json"
    
    if not summary_file.exists():
        return {
            'status': 'no_tests',
            'message': 'No test results found. Run tests first with: ./test'
        }
    
    try:
        with open(summary_file, 'r') as f:
            data = json.load(f)
        
        # Get file modification time for recency
        mod_time = datetime.fromtimestamp(summary_file.stat().st_mtime)
        
        # Analyze what actually ran and failed
        results = data.get('results', [])
        failed_categories = [r for r in results if not r.get('success', False)]
        passed_categories = [r for r in results if r.get('success', False)]
        
        # Find corresponding XML files that actually exist
        existing_xml_files = []
        for result in results:
            category_safe = result['category'].lower().replace(' ', '-')
            xml_file = results_dir / f"test-results-{category_safe}.xml"
            if xml_file.exists():
                existing_xml_files.append({
                    'path': xml_file,
                    'category': result['category'],
                    'failed': not result.get('success', False),
                    'size_kb': xml_file.stat().st_size / 1024
                })
        
        return {
            'status': 'has_results',
            'summary_file': summary_file,
            'mod_time': mod_time,
            'total_categories': len(results),
            'failed_categories': failed_categories,
            'passed_categories': passed_categories,
            'existing_xml_files': existing_xml_files,
            'test_data': data
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error reading test results: {e}'
        }

def main():
    """Show exactly what files are needed for debugging."""
    os.chdir(Path(__file__).parent.parent.parent)
    
    print("🔍 MCP Manager Test Debugging Files")
    print("=" * 60)
    
    analysis = analyze_test_results()
    
    if analysis['status'] == 'no_tests':
        print("❌ No test results found")
        print("   Run tests first: ./test smoke  (or any other test category)")
        print("   Then run: ./test files")
        return
    
    if analysis['status'] == 'error':
        print(f"❌ {analysis['message']}")
        return
    
    # Show test run summary
    failed_count = len(analysis['failed_categories'])
    passed_count = len(analysis['passed_categories']) 
    total_time = analysis['test_data'].get('total_time', 0)
    
    print(f"📊 Last Test Run: {analysis['mod_time'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Categories tested: {analysis['total_categories']}")
    print(f"   Failed: {failed_count} | Passed: {passed_count} | Duration: {total_time:.1f}s")
    print()
    
    if failed_count == 0:
        print("🎉 ALL TESTS PASSED - No debugging files needed!")
        print("   Everything is working correctly.")
        return
    
    # Show EXACTLY what files to share for debugging
    print("🚨 DEBUGGING REQUIRED - Share these files:")
    print("-" * 50)
    
    # 1. Always include the summary for failed tests
    print("📋 REQUIRED - Test Summary:")
    print(f"   {analysis['summary_file']}")
    print("   └─ Contains overall results and failure details")
    print()
    
    # 2. Only show XML files for categories that actually failed
    failed_xml_files = [f for f in analysis['existing_xml_files'] if f['failed']]
    if failed_xml_files:
        print("📄 REQUIRED - Failed Test Details:")
        for xml_file in failed_xml_files:
            print(f"   {xml_file['path']}")
            print(f"   └─ {xml_file['category']} failed ({xml_file['size_kb']:.1f} KB)")
        print()
    
    # 3. Show what passed (optional context)
    passed_xml_files = [f for f in analysis['existing_xml_files'] if not f['failed']]
    if passed_xml_files:
        print("📝 OPTIONAL - Passed Test Context:")
        for xml_file in passed_xml_files:
            print(f"   {xml_file['path']}")
            print(f"   └─ {xml_file['category']} passed ({xml_file['size_kb']:.1f} KB)")
        print()
    
    # 4. Log files (if they exist and are recent)
    fixtures_dir = Path("tests/fixtures")
    log_files = []
    if fixtures_dir.exists():
        for log_file in fixtures_dir.glob("*.log"):
            # Only include recent log files (within last hour of test run)
            log_time = datetime.fromtimestamp(log_file.stat().st_mtime)
            if abs((log_time - analysis['mod_time']).total_seconds()) < 3600:
                log_files.append(log_file)
    
    if log_files:
        print("📋 HELPFUL - Recent Log Files:")
        for log_file in log_files:
            size_kb = log_file.stat().st_size / 1024
            print(f"   {log_file} ({size_kb:.1f} KB)")
        print()
    
    # 5. Exact copy commands for failed tests only
    print("🔗 COPY COMMANDS FOR DEBUGGING:")
    print("# Essential files (failures only):")
    
    essential_files = [str(analysis['summary_file'])]
    essential_files.extend([str(f['path']) for f in failed_xml_files])
    
    for file in essential_files:
        print(f"cp '{file}' /destination/")
    
    print()
    print("# One command for all essential files:")
    files_str = " ".join([f"'{f}'" for f in essential_files])
    print(f"cp {files_str} /destination/")
    
    print()
    print("💡 DEBUGGING TIPS:")
    print("   1. Start with test-results-summary.json - shows which categories failed")
    print("   2. Check failed test XML files for specific error details")
    print("   3. Look for patterns in error messages")
    print("   4. Log files contain runtime errors if tests crashed")
    
    # Show specific failure summary
    print()
    print("🎯 FAILURE SUMMARY:")
    for failed in analysis['failed_categories']:
        category = failed['category']
        duration = failed.get('duration', 0)
        error = failed.get('error', 'See XML file for details')
        returncode = failed.get('returncode', 'unknown')
        
        print(f"   ❌ {category} (exit code: {returncode}, {duration:.1f}s)")
        if error and error != 'See XML file for details':
            print(f"      Error: {error}")
    
    print("=" * 60)

if __name__ == "__main__":
    main()