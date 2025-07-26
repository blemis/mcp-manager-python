"""
Test Catalog Database System

Catalogs all JSON test files in a database for reusability, search, and management.
Enables easy discovery and reuse of existing test scenarios.
"""

import sqlite3
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import os

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class TestCatalogDB:
    """Database catalog for JSON test files and scenarios."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize test catalog database."""
        self.db_path = db_path or Path(__file__).parent.parent / "data" / "test_catalog.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.tests_dir = Path(__file__).parent.parent / "scenarios" / "cli_tests"
        self._initialize_db()
    
    def _initialize_db(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS test_suites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_hash TEXT NOT NULL,
                    test_suite_name TEXT NOT NULL,
                    test_suite_description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    collection_type TEXT DEFAULT 'any',
                    min_servers INTEGER DEFAULT 0,
                    created_by TEXT DEFAULT 'unknown',
                    created_date TEXT,
                    last_updated TEXT,
                    test_count INTEGER DEFAULT 0,
                    estimated_duration INTEGER DEFAULT 0,
                    tags TEXT,
                    compatibility_npm BOOLEAN DEFAULT 1,
                    compatibility_dd BOOLEAN DEFAULT 1,
                    compatibility_docker BOOLEAN DEFAULT 1,
                    compatibility_empty BOOLEAN DEFAULT 1,
                    indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS test_scenarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    suite_id INTEGER NOT NULL,
                    test_name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    command TEXT NOT NULL,
                    expected_exit_code INTEGER DEFAULT 0,
                    timeout INTEGER DEFAULT 30,
                    collection_state TEXT DEFAULT 'any',
                    skip_if_no_servers BOOLEAN DEFAULT 0,
                    requires_specific_collection TEXT,
                    tags TEXT,
                    indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (suite_id) REFERENCES test_suites (id)
                );
                
                CREATE TABLE IF NOT EXISTS test_outputs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scenario_id INTEGER NOT NULL,
                    output_type TEXT NOT NULL, -- 'contains' or 'not_contains'
                    output_text TEXT NOT NULL,
                    FOREIGN KEY (scenario_id) REFERENCES test_scenarios (id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_suites_category ON test_suites(category);
                CREATE INDEX IF NOT EXISTS idx_suites_priority ON test_suites(priority);
                CREATE INDEX IF NOT EXISTS idx_suites_collection_type ON test_suites(collection_type);
                CREATE INDEX IF NOT EXISTS idx_scenarios_command ON test_scenarios(command);
                CREATE INDEX IF NOT EXISTS idx_scenarios_collection_state ON test_scenarios(collection_state);
                CREATE INDEX IF NOT EXISTS idx_outputs_type ON test_outputs(output_type);
            """)
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file content."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate hash for {file_path}: {e}")
            return ""
    
    def index_test_file(self, file_path: Path) -> bool:
        """Index a single JSON test file into the catalog."""
        try:
            # Load and validate JSON
            with open(file_path, 'r') as f:
                test_data = json.load(f)
            
            # Calculate file hash
            file_hash = self._calculate_file_hash(file_path)
            relative_path = file_path.relative_to(self.tests_dir.parent)
            
            # Check if file is already indexed with same hash
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, file_hash FROM test_suites WHERE file_path = ?",
                    (str(relative_path),)
                )
                existing = cursor.fetchone()
                
                if existing and existing[1] == file_hash:
                    logger.debug(f"File {file_path.name} already indexed with current hash")
                    return True
                
                # Delete existing entry if hash changed
                if existing:
                    cursor.execute("DELETE FROM test_suites WHERE id = ?", (existing[0],))
                    logger.info(f"Updated test file: {file_path.name}")
                
                # Extract metadata
                metadata = test_data.get('metadata', {})
                collection_req = test_data.get('collection_requirements', {})
                compatibility = metadata.get('compatibility', {})
                tags = json.dumps(metadata.get('tags', []))
                
                # Insert test suite
                cursor.execute("""
                    INSERT INTO test_suites (
                        file_path, file_hash, test_suite_name, test_suite_description,
                        category, priority, collection_type, min_servers, created_by,
                        created_date, last_updated, test_count, estimated_duration,
                        tags, compatibility_npm, compatibility_dd, compatibility_docker,
                        compatibility_empty
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(relative_path), file_hash, 
                    test_data.get('test_suite_name', ''),
                    test_data.get('test_suite_description', ''),
                    test_data.get('category', 'unknown'),
                    test_data.get('priority', 'medium'),
                    collection_req.get('collection_type', 'any'),
                    collection_req.get('min_servers', 0),
                    metadata.get('created_by', 'unknown'),
                    metadata.get('created_date', datetime.now().strftime('%Y-%m-%d')),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    len(test_data.get('test_scenarios', [])),
                    metadata.get('estimated_duration_seconds', 0),
                    tags,
                    compatibility.get('npm_servers', True),
                    compatibility.get('docker_desktop_servers', True),
                    compatibility.get('docker_hub_servers', True),
                    compatibility.get('empty_state', True)
                ))
                
                suite_id = cursor.lastrowid
                
                # Insert test scenarios
                scenarios = test_data.get('test_scenarios', [])
                for scenario in scenarios:
                    cursor.execute("""
                        INSERT INTO test_scenarios (
                            suite_id, test_name, description, command, expected_exit_code,
                            timeout, collection_state, skip_if_no_servers,
                            requires_specific_collection, tags
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        suite_id,
                        scenario.get('test_name', ''),
                        scenario.get('description', ''),
                        scenario.get('command', ''),
                        scenario.get('expected_exit_code', 0),
                        scenario.get('timeout', 30),
                        scenario.get('collection_state', 'any'),
                        scenario.get('skip_if_no_servers', False),
                        scenario.get('requires_specific_collection'),
                        json.dumps(scenario.get('tags', []))
                    ))
                    
                    scenario_id = cursor.lastrowid
                    
                    # Insert expected outputs
                    for output_text in scenario.get('expected_output_contains', []):
                        cursor.execute("""
                            INSERT INTO test_outputs (scenario_id, output_type, output_text)
                            VALUES (?, 'contains', ?)
                        """, (scenario_id, output_text))
                    
                    for output_text in scenario.get('expected_output_not_contains', []):
                        cursor.execute("""
                            INSERT INTO test_outputs (scenario_id, output_type, output_text)
                            VALUES (?, 'not_contains', ?)
                        """, (scenario_id, output_text))
                
                conn.commit()
                logger.info(f"Indexed test file: {file_path.name} ({len(scenarios)} scenarios)")
                return True
                
        except Exception as e:
            logger.error(f"Failed to index test file {file_path}: {e}")
            return False
    
    def index_all_test_files(self) -> Tuple[int, int]:
        """Index all JSON test files in the tests directory."""
        success_count = 0
        total_count = 0
        
        for json_file in self.tests_dir.glob("*.json"):
            if json_file.name == "master_test_config.json":
                continue  # Skip master config
            
            total_count += 1
            if self.index_test_file(json_file):
                success_count += 1
        
        logger.info(f"Indexed {success_count}/{total_count} test files")
        return success_count, total_count
    
    def search_tests(self, 
                    category: Optional[str] = None,
                    priority: Optional[str] = None,
                    collection_type: Optional[str] = None,
                    command_pattern: Optional[str] = None,
                    tags: Optional[List[str]] = None,
                    compatibility: Optional[Dict[str, bool]] = None) -> List[Dict[str, Any]]:
        """Search for test suites matching criteria."""
        
        query = """
            SELECT s.*, 
                   COUNT(sc.id) as scenario_count
            FROM test_suites s
            LEFT JOIN test_scenarios sc ON s.id = sc.suite_id
            WHERE 1=1
        """
        params = []
        
        if category:
            query += " AND s.category = ?"
            params.append(category)
        
        if priority:
            query += " AND s.priority = ?"
            params.append(priority)
        
        if collection_type:
            query += " AND s.collection_type = ?"
            params.append(collection_type)
        
        if command_pattern:
            query += " AND EXISTS (SELECT 1 FROM test_scenarios WHERE suite_id = s.id AND command LIKE ?)"
            params.append(f"%{command_pattern}%")
        
        if compatibility:
            if compatibility.get('npm_servers') is not None:
                query += " AND s.compatibility_npm = ?"
                params.append(compatibility['npm_servers'])
            if compatibility.get('docker_desktop_servers') is not None:
                query += " AND s.compatibility_dd = ?"
                params.append(compatibility['docker_desktop_servers'])
            if compatibility.get('empty_state') is not None:
                query += " AND s.compatibility_empty = ?"
                params.append(compatibility['empty_state'])
        
        query += " GROUP BY s.id ORDER BY s.priority DESC, s.category, s.test_suite_name"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                result['tags'] = json.loads(result['tags']) if result['tags'] else []
                results.append(result)
            
            return results
    
    def get_test_scenarios(self, suite_id: int) -> List[Dict[str, Any]]:
        """Get all test scenarios for a test suite."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT s.*, 
                       GROUP_CONCAT(CASE WHEN o.output_type = 'contains' THEN o.output_text END) as expected_contains,
                       GROUP_CONCAT(CASE WHEN o.output_type = 'not_contains' THEN o.output_text END) as expected_not_contains
                FROM test_scenarios s
                LEFT JOIN test_outputs o ON s.id = o.scenario_id
                WHERE s.suite_id = ?
                GROUP BY s.id
                ORDER BY s.test_name
            """, (suite_id,))
            
            scenarios = []
            for row in cursor.fetchall():
                scenario = dict(row)
                scenario['expected_output_contains'] = [
                    item.strip() for item in (scenario.pop('expected_contains') or '').split(',') if item.strip()
                ]
                scenario['expected_output_not_contains'] = [
                    item.strip() for item in (scenario.pop('expected_not_contains') or '').split(',') if item.strip()
                ]
                scenario['tags'] = json.loads(scenario['tags']) if scenario['tags'] else []
                scenarios.append(scenario)
            
            return scenarios
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get catalog statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Basic counts
            cursor.execute("SELECT COUNT(*) FROM test_suites")
            total_suites = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM test_scenarios")
            total_scenarios = cursor.fetchone()[0]
            
            # Category breakdown
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM test_suites
                GROUP BY category
                ORDER BY count DESC
            """)
            categories = dict(cursor.fetchall())
            
            # Priority breakdown
            cursor.execute("""
                SELECT priority, COUNT(*) as count
                FROM test_suites
                GROUP BY priority
                ORDER BY 
                    CASE priority 
                        WHEN 'critical' THEN 1 
                        WHEN 'high' THEN 2 
                        WHEN 'medium' THEN 3 
                        WHEN 'low' THEN 4 
                        ELSE 5 
                    END
            """)
            priorities = dict(cursor.fetchall())
            
            # Collection compatibility
            cursor.execute("""
                SELECT 
                    SUM(compatibility_npm) as npm_compatible,
                    SUM(compatibility_dd) as dd_compatible,
                    SUM(compatibility_docker) as docker_compatible,
                    SUM(compatibility_empty) as empty_compatible
                FROM test_suites
            """)
            compatibility = cursor.fetchone()
            
            return {
                'total_test_suites': total_suites,
                'total_test_scenarios': total_scenarios,
                'categories': categories,
                'priorities': priorities,
                'compatibility': {
                    'npm_servers': compatibility[0],
                    'docker_desktop_servers': compatibility[1], 
                    'docker_hub_servers': compatibility[2],
                    'empty_state': compatibility[3]
                }
            }
    
    def cleanup_orphaned_entries(self) -> int:
        """Remove catalog entries for files that no longer exist."""
        removed_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, file_path FROM test_suites")
            
            for suite_id, file_path in cursor.fetchall():
                full_path = self.tests_dir.parent / file_path
                if not full_path.exists():
                    cursor.execute("DELETE FROM test_suites WHERE id = ?", (suite_id,))
                    removed_count += 1
                    logger.info(f"Removed orphaned entry: {file_path}")
            
            conn.commit()
        
        return removed_count


# CLI interface functions
def rebuild_catalog():
    """Rebuild the entire test catalog."""
    print("🔄 Rebuilding test catalog...")
    catalog = TestCatalogDB()
    
    # Clear existing data
    with sqlite3.connect(catalog.db_path) as conn:
        conn.execute("DELETE FROM test_suites")
        conn.commit()
    
    # Reindex all files
    success, total = catalog.index_all_test_files()
    print(f"✅ Catalog rebuilt: {success}/{total} files indexed")
    
    # Show statistics
    stats = catalog.get_statistics()
    print(f"📊 Statistics:")
    print(f"   Total test suites: {stats['total_test_suites']}")
    print(f"   Total scenarios: {stats['total_test_scenarios']}")
    print(f"   Categories: {list(stats['categories'].keys())}")


def search_catalog(**kwargs):
    """Search the test catalog."""
    catalog = TestCatalogDB()
    results = catalog.search_tests(**kwargs)
    
    print(f"🔍 Found {len(results)} matching test suites:")
    for result in results:
        print(f"   📁 {result['test_suite_name']} ({result['category']}, {result['priority']})")
        print(f"      {result['test_suite_description']}")
        print(f"      Scenarios: {result['scenario_count']}, File: {result['file_path']}")
        print()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "rebuild":
            rebuild_catalog()
        elif sys.argv[1] == "search":
            if len(sys.argv) > 2:
                search_catalog(category=sys.argv[2])
            else:
                search_catalog()
        elif sys.argv[1] == "stats":
            catalog = TestCatalogDB()
            stats = catalog.get_statistics()
            print(json.dumps(stats, indent=2))
    else:
        rebuild_catalog()