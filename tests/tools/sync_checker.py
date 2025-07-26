#!/usr/bin/env python3
"""
Test File-Database Sync Checker

Comprehensive sync verification and automatic repair system for ensuring
JSON test files and database catalog remain consistent.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import argparse

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.tools.test_catalog_db import TestCatalogDB
from tests.tools.hybrid_test_loader import get_hybrid_loader
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class SyncChecker:
    """Comprehensive sync checker for JSON files and database."""
    
    def __init__(self):
        """Initialize sync checker."""
        self.catalog = TestCatalogDB()
        self.hybrid_loader = get_hybrid_loader()
        self.tests_dir = Path(__file__).parent.parent / "scenarios" / "cli_tests"
        self.master_config_path = self.tests_dir / "master_test_config.json"
    
    def check_full_sync(self) -> Dict[str, Any]:
        """Perform comprehensive sync check."""
        print("🔍 Comprehensive File-Database Sync Check")
        print("=" * 50)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "synced",
            "files_vs_db": {},
            "master_config_vs_files": {},
            "master_config_vs_db": {},
            "recommendations": [],
            "auto_fixable": [],
            "manual_fixes_needed": []
        }
        
        # 1. Check JSON files vs Database
        print("1️⃣  Checking JSON files vs Database...")
        file_db_status = self._check_files_vs_db()
        results["files_vs_db"] = file_db_status
        
        if not file_db_status["in_sync"]:
            results["overall_status"] = "out_of_sync"
        
        # 2. Check Master config vs JSON files
        print("2️⃣  Checking Master config vs JSON files...")
        config_files_status = self._check_master_config_vs_files()
        results["master_config_vs_files"] = config_files_status
        
        if not config_files_status["in_sync"]:
            results["overall_status"] = "out_of_sync"
        
        # 3. Check Master config vs Database
        print("3️⃣  Checking Master config vs Database...")
        config_db_status = self._check_master_config_vs_db()
        results["master_config_vs_db"] = config_db_status
        
        if not config_db_status["in_sync"]:
            results["overall_status"] = "out_of_sync"
        
        # 4. Generate recommendations
        results["recommendations"] = self._generate_recommendations(results)
        
        # Print summary
        self._print_sync_summary(results)
        
        return results
    
    def _check_files_vs_db(self) -> Dict[str, Any]:
        """Check if JSON files match database entries."""
        status = {
            "in_sync": True,
            "total_files": 0,
            "synced_files": 0,
            "missing_from_db": [],
            "hash_mismatches": [],
            "orphaned_db_entries": [],
            "details": []
        }
        
        # Check JSON files
        json_files = list(self.tests_dir.glob("*.json"))
        json_files = [f for f in json_files if f.name != "master_test_config.json"]
        
        status["total_files"] = len(json_files)
        
        for json_file in json_files:
            relative_path = str(json_file.relative_to(self.tests_dir.parent))
            file_hash = self._calculate_file_hash(json_file)
            
            # Check if file exists in DB
            db_entry = self._get_db_entry_for_file(relative_path)
            
            if not db_entry:
                status["missing_from_db"].append(relative_path)
                status["in_sync"] = False
                status["details"].append({
                    "file": relative_path,
                    "issue": "missing_from_db",
                    "auto_fixable": True
                })
            elif db_entry["file_hash"] != file_hash:
                status["hash_mismatches"].append({
                    "file": relative_path,
                    "file_hash": file_hash,
                    "db_hash": db_entry["file_hash"]
                })
                status["in_sync"] = False
                status["details"].append({
                    "file": relative_path,
                    "issue": "hash_mismatch",
                    "auto_fixable": True
                })
            else:
                status["synced_files"] += 1
        
        # Check for orphaned DB entries
        db_entries = self._get_all_db_entries()
        for entry in db_entries:
            file_path = self.tests_dir.parent / entry["file_path"]
            if not file_path.exists():
                status["orphaned_db_entries"].append(entry["file_path"])
                status["in_sync"] = False
                status["details"].append({
                    "file": entry["file_path"],
                    "issue": "orphaned_db_entry",
                    "auto_fixable": True
                })
        
        return status
    
    def _check_master_config_vs_files(self) -> Dict[str, Any]:
        """Check if master config matches actual JSON files."""
        status = {
            "in_sync": True,
            "master_config_exists": False,
            "config_entries": 0,
            "actual_files": 0,
            "missing_from_config": [],
            "missing_files": [],
            "count_mismatches": [],
            "details": []
        }
        
        # Check master config exists
        if not self.master_config_path.exists():
            status["master_config_exists"] = False
            status["in_sync"] = False
            return status
        
        status["master_config_exists"] = True
        
        # Load master config
        try:
            with open(self.master_config_path, 'r') as f:
                config = json.load(f)
        except Exception as e:
            status["error"] = f"Failed to load master config: {e}"
            status["in_sync"] = False
            return status
        
        config_suites = config.get("test_suites", [])
        status["config_entries"] = len(config_suites)
        
        # Get actual JSON files
        json_files = [f for f in self.tests_dir.glob("*.json") 
                     if f.name != "master_test_config.json"]
        status["actual_files"] = len(json_files)
        
        # Check each config entry
        config_files = [suite.get("file", "") for suite in config_suites]
        actual_filenames = [f.name for f in json_files]
        
        for filename in actual_filenames:
            if filename not in config_files:
                status["missing_from_config"].append(filename)
                status["in_sync"] = False
        
        for filename in config_files:
            if filename not in actual_filenames:
                status["missing_files"].append(filename)
                status["in_sync"] = False
        
        # Check test counts
        for suite in config_suites:
            filename = suite.get("file", "")
            config_count = suite.get("test_count", 0)
            
            file_path = self.tests_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        file_data = json.load(f)
                    actual_count = len(file_data.get("test_scenarios", []))
                    
                    if config_count != actual_count:
                        status["count_mismatches"].append({
                            "file": filename,
                            "config_count": config_count,
                            "actual_count": actual_count
                        })
                        status["in_sync"] = False
                        
                except Exception as e:
                    status["details"].append({
                        "file": filename,
                        "issue": f"failed_to_read: {e}",
                        "auto_fixable": False
                    })
        
        return status
    
    def _check_master_config_vs_db(self) -> Dict[str, Any]:
        """Check if master config matches database entries."""
        status = {
            "in_sync": True,
            "config_suites": 0,
            "db_suites": 0,
            "matching_entries": 0,
            "missing_from_db": [],
            "missing_from_config": [],
            "metadata_mismatches": []
        }
        
        # Load master config
        try:
            with open(self.master_config_path, 'r') as f:
                config = json.load(f)
            config_suites = config.get("test_suites", [])
            status["config_suites"] = len(config_suites)
        except Exception as e:
            status["error"] = f"Failed to load master config: {e}"
            status["in_sync"] = False
            return status
        
        # Get DB entries
        db_entries = self._get_all_db_entries()
        status["db_suites"] = len(db_entries)
        
        # Compare entries
        config_files = [suite.get("file", "") for suite in config_suites]
        db_files = [entry["file_path"].split("/")[-1] for entry in db_entries]
        
        for filename in config_files:
            if filename not in db_files:
                status["missing_from_db"].append(filename)
                status["in_sync"] = False
        
        for filename in db_files:
            if filename not in config_files:
                status["missing_from_config"].append(filename)
                status["in_sync"] = False
        
        # Check metadata consistency for matching files
        for suite in config_suites:
            filename = suite.get("file", "")
            db_entry = self._get_db_entry_for_filename(filename)
            
            if db_entry:
                # Compare key fields
                if (suite.get("category") != db_entry.get("category") or 
                    suite.get("priority") != db_entry.get("priority") or
                    suite.get("test_count") != db_entry.get("test_count")):
                    
                    status["metadata_mismatches"].append({
                        "file": filename,
                        "config": {
                            "category": suite.get("category"),
                            "priority": suite.get("priority"),
                            "test_count": suite.get("test_count")
                        },
                        "db": {
                            "category": db_entry.get("category"),
                            "priority": db_entry.get("priority"),
                            "test_count": db_entry.get("test_count")
                        }
                    })
                    status["in_sync"] = False
                else:
                    status["matching_entries"] += 1
        
        return status
    
    def auto_fix_sync_issues(self, dry_run: bool = True) -> Dict[str, Any]:
        """Automatically fix sync issues where possible."""
        print(f"🔧 Auto-fix sync issues ({'DRY RUN' if dry_run else 'LIVE'})")
        print("=" * 50)
        
        sync_status = self.check_full_sync()
        
        fixes_applied = {
            "timestamp": datetime.now().isoformat(),
            "dry_run": dry_run,
            "fixes": [],
            "errors": [],
            "summary": {}
        }
        
        # Fix missing DB entries
        missing_from_db = sync_status["files_vs_db"].get("missing_from_db", [])
        for file_path in missing_from_db:
            try:
                full_path = self.tests_dir.parent / file_path
                if not dry_run:
                    success = self.catalog.index_test_file(full_path)
                    if success:
                        fixes_applied["fixes"].append(f"Indexed {file_path} in database")
                    else:
                        fixes_applied["errors"].append(f"Failed to index {file_path}")
                else:
                    fixes_applied["fixes"].append(f"Would index {file_path} in database")
            except Exception as e:
                fixes_applied["errors"].append(f"Error indexing {file_path}: {e}")
        
        # Fix hash mismatches by re-indexing
        hash_mismatches = sync_status["files_vs_db"].get("hash_mismatches", [])
        for mismatch in hash_mismatches:
            try:
                file_path = mismatch["file"]
                full_path = self.tests_dir.parent / file_path
                if not dry_run:
                    success = self.catalog.index_test_file(full_path)
                    if success:
                        fixes_applied["fixes"].append(f"Re-indexed {file_path} (hash updated)")
                    else:
                        fixes_applied["errors"].append(f"Failed to re-index {file_path}")
                else:
                    fixes_applied["fixes"].append(f"Would re-index {file_path} (hash mismatch)")
            except Exception as e:
                fixes_applied["errors"].append(f"Error re-indexing {file_path}: {e}")
        
        # Remove orphaned DB entries
        orphaned_entries = sync_status["files_vs_db"].get("orphaned_db_entries", [])
        if orphaned_entries and not dry_run:
            removed = self.catalog.cleanup_orphaned_entries()
            fixes_applied["fixes"].append(f"Removed {removed} orphaned DB entries")
        elif orphaned_entries:
            fixes_applied["fixes"].append(f"Would remove {len(orphaned_entries)} orphaned DB entries")
        
        # Summary
        fixes_applied["summary"] = {
            "total_fixes": len(fixes_applied["fixes"]),
            "total_errors": len(fixes_applied["errors"]),
            "status": "completed" if not fixes_applied["errors"] else "completed_with_errors"
        }
        
        print(f"✅ Auto-fix completed: {fixes_applied['summary']['total_fixes']} fixes applied")
        if fixes_applied["summary"]["total_errors"]:
            print(f"⚠️  {fixes_applied['summary']['total_errors']} errors occurred")
        
        return fixes_applied
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file content."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return ""
    
    def _get_db_entry_for_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get database entry for a file path."""
        try:
            import sqlite3
            with sqlite3.connect(self.catalog.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM test_suites WHERE file_path = ?", (file_path,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception:
            return None
    
    def _get_db_entry_for_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        """Get database entry for a filename."""
        try:
            import sqlite3
            with sqlite3.connect(self.catalog.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM test_suites WHERE file_path LIKE ?", (f"%{filename}",))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception:
            return None
    
    def _get_all_db_entries(self) -> List[Dict[str, Any]]:
        """Get all database entries."""
        try:
            import sqlite3
            with sqlite3.connect(self.catalog.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM test_suites ORDER BY file_path")
                return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []
    
    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on sync status."""
        recommendations = []
        
        if results["overall_status"] == "synced":
            recommendations.append("✅ All systems are in sync!")
            return recommendations
        
        # File-DB recommendations
        files_vs_db = results["files_vs_db"]
        if not files_vs_db["in_sync"]:
            if files_vs_db["missing_from_db"]:
                recommendations.append(f"🔄 Re-index {len(files_vs_db['missing_from_db'])} missing files in database")
            if files_vs_db["hash_mismatches"]:
                recommendations.append(f"🔄 Re-index {len(files_vs_db['hash_mismatches'])} files with hash mismatches")
            if files_vs_db["orphaned_db_entries"]:
                recommendations.append(f"🗑️  Remove {len(files_vs_db['orphaned_db_entries'])} orphaned database entries")
        
        # Master config recommendations
        config_vs_files = results["master_config_vs_files"]
        if not config_vs_files["in_sync"]:
            if config_vs_files["missing_from_config"]:
                recommendations.append(f"📝 Add {len(config_vs_files['missing_from_config'])} missing files to master config")
            if config_vs_files["count_mismatches"]:
                recommendations.append(f"📊 Update test counts for {len(config_vs_files['count_mismatches'])} files in master config")
        
        recommendations.append("🔧 Run 'python sync_checker.py --auto-fix' to automatically fix most issues")
        
        return recommendations
    
    def _print_sync_summary(self, results: Dict[str, Any]):
        """Print comprehensive sync summary."""
        print("\\n" + "=" * 60)
        print("📊 SYNC STATUS SUMMARY")
        print("=" * 60)
        
        status_emoji = "✅" if results["overall_status"] == "synced" else "❌"
        print(f"{status_emoji} Overall Status: {results['overall_status'].upper()}")
        
        print("\\n📁 Files vs Database:")
        fdb = results["files_vs_db"]
        print(f"   Synced: {fdb['synced_files']}/{fdb['total_files']} files")
        if fdb["missing_from_db"]:
            print(f"   ⚠️  Missing from DB: {len(fdb['missing_from_db'])}")
        if fdb["hash_mismatches"]:
            print(f"   ⚠️  Hash mismatches: {len(fdb['hash_mismatches'])}")
        if fdb["orphaned_db_entries"]:
            print(f"   ⚠️  Orphaned DB entries: {len(fdb['orphaned_db_entries'])}")
        
        print("\\n📋 Master Config vs Files:")
        mcf = results["master_config_vs_files"]
        if mcf["master_config_exists"]:
            print(f"   Config entries: {mcf['config_entries']}, Actual files: {mcf['actual_files']}")
            if mcf["missing_from_config"]:
                print(f"   ⚠️  Missing from config: {len(mcf['missing_from_config'])}")
            if mcf["missing_files"]:
                print(f"   ⚠️  Missing files: {len(mcf['missing_files'])}")
            if mcf["count_mismatches"]:
                print(f"   ⚠️  Count mismatches: {len(mcf['count_mismatches'])}")
        else:
            print("   ❌ Master config file not found!")
        
        print("\\n💡 Recommendations:")
        for rec in results["recommendations"]:
            print(f"   {rec}")
        
        print("=" * 60)


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Test File-Database Sync Checker",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--check', action='store_true', 
                       help='Perform comprehensive sync check')
    parser.add_argument('--auto-fix', action='store_true',
                       help='Automatically fix sync issues')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be fixed without making changes')
    parser.add_argument('--json', action='store_true',
                       help='Output results as JSON')
    
    args = parser.parse_args()
    
    if not any([args.check, args.auto_fix]):
        # Default to check
        args.check = True
    
    try:
        checker = SyncChecker()
        
        if args.auto_fix:
            dry_run = args.dry_run
            results = checker.auto_fix_sync_issues(dry_run=dry_run)
            
            if args.json:
                print(json.dumps(results, indent=2))
            
        elif args.check:
            results = checker.check_full_sync()
            
            if args.json:
                print(json.dumps(results, indent=2))
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())