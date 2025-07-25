"""
Database manager for test categories and suite mappings.
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from .models import TestCategory, TestSuiteMapping, TestExecution, TestScope
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class TestManagementDB:
    """Database manager for dynamic test category system."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection."""
        if db_path is None:
            # Use default path in data directory
            from mcp_manager.utils.config import get_config
            config = get_config()
            data_dir = Path(getattr(config, 'data_dir', '~/.local/share/mcp-manager')).expanduser()
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = data_dir / 'test_management.db'
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
            # Test categories table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS test_categories (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    scope TEXT NOT NULL,
                    test_file_pattern TEXT NOT NULL,
                    default_suite_id TEXT,
                    required_servers TEXT,  -- JSON array
                    optional_servers TEXT,  -- JSON array
                    test_markers TEXT,      -- JSON array
                    config TEXT,            -- JSON object
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Suite mappings table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS test_suite_mappings (
                    id TEXT PRIMARY KEY,
                    test_category_id TEXT NOT NULL,
                    suite_id TEXT NOT NULL,
                    priority INTEGER DEFAULT 50,
                    conditions TEXT,        -- JSON object
                    created_by TEXT DEFAULT 'system',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (test_category_id) REFERENCES test_categories (id)
                )
            ''')
            
            # Test executions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS test_executions (
                    id TEXT PRIMARY KEY,
                    test_category_id TEXT NOT NULL,
                    suite_id TEXT NOT NULL,
                    test_file TEXT NOT NULL,
                    test_class TEXT,
                    status TEXT DEFAULT 'pending',
                    suite_loaded BOOLEAN DEFAULT FALSE,
                    servers_deployed TEXT,   -- JSON array
                    execution_time REAL,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (test_category_id) REFERENCES test_categories (id)
                )
            ''')
            
            # Create test scenarios table
            self._create_test_scenarios_table(conn)
            
            # Create indexes
            conn.execute('CREATE INDEX IF NOT EXISTS idx_categories_scope ON test_categories (scope)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_mappings_category ON test_suite_mappings (test_category_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_mappings_priority ON test_suite_mappings (priority DESC)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_executions_status ON test_executions (status)')
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # Test Category CRUD operations
    def create_test_category(self, category: TestCategory) -> bool:
        """Create a new test category."""
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT INTO test_categories 
                    (id, name, description, scope, test_file_pattern, default_suite_id,
                     required_servers, optional_servers, test_markers, config)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    category.id,
                    category.name,
                    category.description,
                    category.scope.value,
                    category.test_file_pattern,
                    category.default_suite_id,
                    json.dumps(category.required_servers),
                    json.dumps(category.optional_servers),
                    json.dumps(category.test_markers),
                    json.dumps(category.config)
                ))
            logger.info(f"Created test category: {category.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create test category {category.id}: {e}")
            return False
    
    def get_test_category(self, category_id: str) -> Optional[TestCategory]:
        """Get test category by ID."""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    'SELECT * FROM test_categories WHERE id = ?', (category_id,)
                ).fetchone()
                
                if row:
                    return TestCategory(
                        id=row['id'],
                        name=row['name'],
                        description=row['description'],
                        scope=TestScope(row['scope']),
                        test_file_pattern=row['test_file_pattern'],
                        default_suite_id=row['default_suite_id'],
                        required_servers=json.loads(row['required_servers'] or '[]'),
                        optional_servers=json.loads(row['optional_servers'] or '[]'),
                        test_markers=json.loads(row['test_markers'] or '[]'),
                        config=json.loads(row['config'] or '{}')
                    )
        except Exception as e:
            logger.error(f"Failed to get test category {category_id}: {e}")
        
        return None
    
    def list_test_categories(self, scope: Optional[TestScope] = None) -> List[TestCategory]:
        """List all test categories, optionally filtered by scope."""
        categories = []
        try:
            with self._get_connection() as conn:
                query = 'SELECT * FROM test_categories'
                params = ()
                
                if scope:
                    query += ' WHERE scope = ?'
                    params = (scope.value,)
                
                query += ' ORDER BY name'
                
                for row in conn.execute(query, params):
                    categories.append(TestCategory(
                        id=row['id'],
                        name=row['name'],
                        description=row['description'],
                        scope=TestScope(row['scope']),
                        test_file_pattern=row['test_file_pattern'],
                        default_suite_id=row['default_suite_id'],
                        required_servers=json.loads(row['required_servers'] or '[]'),
                        optional_servers=json.loads(row['optional_servers'] or '[]'),
                        test_markers=json.loads(row['test_markers'] or '[]'),
                        config=json.loads(row['config'] or '{}')
                    ))
        except Exception as e:
            logger.error(f"Failed to list test categories: {e}")
        
        return categories
    
    # Suite Mapping operations
    def create_suite_mapping(self, mapping: TestSuiteMapping) -> bool:
        """Create a test category to suite mapping."""
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT INTO test_suite_mappings 
                    (id, test_category_id, suite_id, priority, conditions, created_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    mapping.id,
                    mapping.test_category_id,
                    mapping.suite_id,
                    mapping.priority,
                    json.dumps(mapping.conditions),
                    mapping.created_by
                ))
            logger.info(f"Created suite mapping: {mapping.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create suite mapping {mapping.id}: {e}")
            return False
    
    def get_suite_for_category(self, category_id: str) -> Optional[str]:
        """Get the best suite for a test category based on priority."""
        try:
            with self._get_connection() as conn:
                row = conn.execute('''
                    SELECT suite_id FROM test_suite_mappings 
                    WHERE test_category_id = ? 
                    ORDER BY priority DESC 
                    LIMIT 1
                ''', (category_id,)).fetchone()
                
                if row:
                    return row['suite_id']
        except Exception as e:
            logger.error(f"Failed to get suite for category {category_id}: {e}")
        
        return None
    
    def find_category_by_test_file(self, test_file: str) -> Optional[TestCategory]:
        """Find test category by matching test file pattern."""
        import fnmatch
        
        categories = self.list_test_categories()
        for category in categories:
            if fnmatch.fnmatch(test_file, category.test_file_pattern):
                return category
        
        return None
    
    def _create_test_scenarios_table(self, conn):
        """Create test scenarios table for JSON scenarios."""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS test_scenarios (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                created_by TEXT NOT NULL,
                scenario_json TEXT NOT NULL,
                tags TEXT,  -- JSON array of tags
                confidence_score REAL DEFAULT 0.0,
                ai_reasoning TEXT,
                suite_id TEXT,
                execution_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0,
                average_duration REAL DEFAULT 0.0,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_executed TIMESTAMP,
                enabled BOOLEAN DEFAULT 1,
                FOREIGN KEY (suite_id) REFERENCES test_suites(id)
            )
        ''')
        
        # Create indexes for efficient queries
        conn.execute('CREATE INDEX IF NOT EXISTS idx_scenarios_category ON test_scenarios(category)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_scenarios_priority ON test_scenarios(priority)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_scenarios_suite ON test_scenarios(suite_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_scenarios_enabled ON test_scenarios(enabled)')
    
    def create_test_scenario(self, scenario: 'TestScenario') -> bool:
        """Create a new test scenario in the database."""
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT INTO test_scenarios (
                        id, name, description, category, priority, created_by,
                        scenario_json, tags, confidence_score, ai_reasoning,
                        suite_id, execution_count, success_rate, average_duration,
                        created_date, last_modified, enabled
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    scenario.id, scenario.name, scenario.description,
                    scenario.category, scenario.priority, scenario.created_by,
                    scenario.scenario_json, json.dumps(scenario.tags),
                    scenario.confidence_score, scenario.ai_reasoning,
                    scenario.suite_id, scenario.execution_count,
                    scenario.success_rate, scenario.average_duration,
                    scenario.created_date, scenario.last_modified, scenario.enabled
                ))
            logger.info(f"Created test scenario: {scenario.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create test scenario {scenario.id}: {e}")
            return False
    
    def get_test_scenario(self, scenario_id: str) -> Optional['TestScenario']:
        """Retrieve a test scenario by ID."""
        try:
            with self._get_connection() as conn:
                row = conn.execute('''
                    SELECT * FROM test_scenarios WHERE id = ?
                ''', (scenario_id,)).fetchone()
                
                if row:
                    from .models import TestScenario
                    return TestScenario(
                        id=row['id'],
                        name=row['name'],
                        description=row['description'],
                        category=row['category'],
                        priority=row['priority'],
                        created_by=row['created_by'],
                        scenario_json=row['scenario_json'],
                        tags=json.loads(row['tags']) if row['tags'] else [],
                        confidence_score=row['confidence_score'],
                        ai_reasoning=row['ai_reasoning'],
                        suite_id=row['suite_id'],
                        execution_count=row['execution_count'],
                        success_rate=row['success_rate'],
                        average_duration=row['average_duration'],
                        created_date=row['created_date'],
                        last_modified=row['last_modified'],
                        last_executed=row['last_executed'],
                        enabled=bool(row['enabled'])
                    )
        except Exception as e:
            logger.error(f"Failed to get test scenario {scenario_id}: {e}")
        
        return None
    
    def list_test_scenarios(self, category: Optional[str] = None, 
                           suite_id: Optional[str] = None,
                           enabled_only: bool = True) -> List['TestScenario']:
        """List test scenarios with optional filtering."""
        try:
            with self._get_connection() as conn:
                query = 'SELECT * FROM test_scenarios WHERE 1=1'
                params = []
                
                if category:
                    query += ' AND category = ?'
                    params.append(category)
                
                if suite_id:
                    query += ' AND suite_id = ?'
                    params.append(suite_id)
                
                if enabled_only:
                    query += ' AND enabled = 1'
                
                query += ' ORDER BY priority DESC, created_date DESC'
                
                rows = conn.execute(query, params).fetchall()
                
                from .models import TestScenario
                scenarios = []
                for row in rows:
                    scenarios.append(TestScenario(
                        id=row['id'],
                        name=row['name'],
                        description=row['description'],
                        category=row['category'],
                        priority=row['priority'],
                        created_by=row['created_by'],
                        scenario_json=row['scenario_json'],
                        tags=json.loads(row['tags']) if row['tags'] else [],
                        confidence_score=row['confidence_score'],
                        ai_reasoning=row['ai_reasoning'],
                        suite_id=row['suite_id'],
                        execution_count=row['execution_count'],
                        success_rate=row['success_rate'],
                        average_duration=row['average_duration'],
                        created_date=row['created_date'],
                        last_modified=row['last_modified'],
                        last_executed=row['last_executed'],
                        enabled=bool(row['enabled'])
                    ))
                
                return scenarios
                
        except Exception as e:
            logger.error(f"Failed to list test scenarios: {e}")
            return []
    
    def update_test_scenario(self, scenario: 'TestScenario') -> bool:
        """Update an existing test scenario."""
        try:
            with self._get_connection() as conn:
                from datetime import datetime
                scenario.last_modified = datetime.now()
                conn.execute('''
                    UPDATE test_scenarios SET
                        name = ?, description = ?, category = ?, priority = ?,
                        scenario_json = ?, tags = ?, confidence_score = ?,
                        ai_reasoning = ?, suite_id = ?, execution_count = ?,
                        success_rate = ?, average_duration = ?, last_modified = ?,
                        last_executed = ?, enabled = ?
                    WHERE id = ?
                ''', (
                    scenario.name, scenario.description, scenario.category,
                    scenario.priority, scenario.scenario_json, json.dumps(scenario.tags),
                    scenario.confidence_score, scenario.ai_reasoning, scenario.suite_id,
                    scenario.execution_count, scenario.success_rate, scenario.average_duration,
                    scenario.last_modified, scenario.last_executed, scenario.enabled,
                    scenario.id
                ))
            logger.info(f"Updated test scenario: {scenario.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update test scenario {scenario.id}: {e}")
            return False
    
    def delete_test_scenario(self, scenario_id: str) -> bool:
        """Delete a test scenario."""
        try:
            with self._get_connection() as conn:
                conn.execute('DELETE FROM test_scenarios WHERE id = ?', (scenario_id,))
            logger.info(f"Deleted test scenario: {scenario_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete test scenario {scenario_id}: {e}")
            return False
    
    def update_scenario_stats(self, scenario_id: str, success: bool, duration: float) -> bool:
        """Update scenario execution statistics."""
        try:
            with self._get_connection() as conn:
                # Get current stats
                row = conn.execute('''
                    SELECT execution_count, success_rate, average_duration 
                    FROM test_scenarios WHERE id = ?
                ''', (scenario_id,)).fetchone()
                
                if row:
                    old_count = row['execution_count']
                    old_success_rate = row['success_rate']
                    old_avg_duration = row['average_duration']
                    
                    # Calculate new stats
                    new_count = old_count + 1
                    new_success_rate = ((old_success_rate * old_count) + (1 if success else 0)) / new_count
                    new_avg_duration = ((old_avg_duration * old_count) + duration) / new_count
                    
                    # Update with new stats
                    conn.execute('''
                        UPDATE test_scenarios SET 
                            execution_count = ?, success_rate = ?, average_duration = ?,
                            last_executed = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (new_count, new_success_rate, new_avg_duration, scenario_id))
                    
                    return True
        except Exception as e:
            logger.error(f"Failed to update scenario stats for {scenario_id}: {e}")
            return False