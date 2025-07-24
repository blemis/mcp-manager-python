#!/usr/bin/env python3
"""
Show Test Output Files for Sharing

Quick utility to display all test output files with full paths for easy sharing.
"""

from pathlib import Path
import json
import os

def main():
    """Show all test output files."""
    # Get project root (3 levels up from this file)
    root_dir = Path(__file__).parent.parent.parent
    os.chdir(root_dir)
    
    results_dir = root_dir / "tests" / "results"
    
    print("🧪 MCP Manager Test Output Files")
    print("=" * 50)
    
    # Summary file
    summary_file = results_dir / "test-results-summary.json"
    if summary_file.exists():
        print(f"📊 Summary Report:")
        print(f"   {summary_file}")
        
        # Show quick stats from summary
        try:
            with open(summary_file, 'r') as f:
                data = json.load(f)
            
            total_categories = data.get('total_categories', 0)
            passed_categories = data.get('passed_categories', 0)
            failed_categories = data.get('failed_categories', 0)
            success_rate = data.get('success_rate', 0)
            total_time = data.get('total_time', 0)
            
            print(f"   └─ {passed_categories}/{total_categories} passed ({success_rate:.1f}%) in {total_time:.1f}s")
            
        except Exception:
            print("   └─ (Unable to read summary)")
        
        print()
    
    # XML files
    xml_files = list(results_dir.glob("test-results-*.xml"))
    if xml_files:
        print(f"📄 Individual Test Reports ({len(xml_files)} files):")
        for xml_file in sorted(xml_files):
            category = xml_file.stem.replace('test-results-', '').replace('-', ' ').title()
            size_kb = xml_file.stat().st_size / 1024
            print(f"   {xml_file}")
            print(f"   └─ {category} ({size_kb:.1f} KB)")
        print()
    
    # Recent log files (if any)
    fixtures_dir = root_dir / "tests" / "fixtures"
    log_files = list(fixtures_dir.glob("test_failures.log")) + list(fixtures_dir.glob("*.log"))
    if log_files:
        print(f"📋 Log Files:")
        for log_file in sorted(log_files):
            size_kb = log_file.stat().st_size / 1024
            print(f"   {log_file} ({size_kb:.1f} KB)")
        print()
    
    # Easy copy commands
    all_files = []
    if summary_file.exists():
        all_files.append(str(summary_file))
    all_files.extend([str(f) for f in xml_files])
    
    if all_files:
        print("🔗 Copy Commands for Sharing:")
        print("# Copy individual files:")
        for file in all_files:
            print(f"cp '{file}' /destination/")
        
        print()
        print("# Copy all test results:")
        files_str = " ".join([f"'{f}'" for f in all_files])
        print(f"cp {files_str} /destination/")
        print()
        
        print("💡 Tip: These files contain all test execution details")
        print("   Summary JSON: Machine-readable results and statistics")
        print("   XML files: JUnit format for CI/CD integration")
    else:
        print("❌ No test output files found.")
        print("   Run './test' to generate test results first.")
    
    print("=" * 50)

if __name__ == "__main__":
    main()