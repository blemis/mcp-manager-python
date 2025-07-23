"""
Database migration for comprehensive analytics tables.

Creates tables for recommendation analytics, server analytics, 
query patterns, and API usage tracking.
"""

import os
import sqlite3
from pathlib import Path
from typing import Dict, Any

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


def get_database_path() -> Path:
    """Get database path from environment or default."""
    db_path = os.getenv("MCP_MANAGER_DB_PATH")
    if db_path:
        return Path(db_path)
    
    # Default to user config directory
    config_dir = Path.home() / ".config" / "mcp-manager"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "mcp_manager.db"


def up(db_path: Path) -> bool:
    """
    Apply migration: Create analytics tables.
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        True if migration succeeded, False otherwise
    """
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            
            # Create recommendation_analytics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recommendation_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_query TEXT NOT NULL,
                    query_category TEXT,
                    recommendations_count INTEGER NOT NULL,
                    llm_provider TEXT NOT NULL,
                    model_used TEXT NOT NULL,
                    processing_time_ms INTEGER NOT NULL,
                    tools_analyzed INTEGER NOT NULL,
                    user_selected_tool TEXT,
                    user_satisfaction_score REAL,
                    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    context_data TEXT DEFAULT '{}',
                    
                    -- Constraints
                    CHECK (recommendations_count >= 0),
                    CHECK (processing_time_ms >= 0),
                    CHECK (tools_analyzed >= 0),
                    CHECK (user_satisfaction_score IS NULL OR 
                           (user_satisfaction_score >= 0.0 AND user_satisfaction_score <= 1.0))
                )
            """)
            
            # Create indexes for recommendation_analytics
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_recommendation_analytics_session 
                ON recommendation_analytics(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_recommendation_analytics_timestamp 
                ON recommendation_analytics(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_recommendation_analytics_provider 
                ON recommendation_analytics(llm_provider)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_recommendation_analytics_query_category 
                ON recommendation_analytics(query_category)
            """)
            
            # Create server_analytics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS server_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_name TEXT NOT NULL,
                    server_type TEXT NOT NULL,
                    date DATETIME NOT NULL,
                    total_tools INTEGER DEFAULT 0,
                    active_tools INTEGER DEFAULT 0,
                    total_requests INTEGER DEFAULT 0,
                    successful_requests INTEGER DEFAULT 0,
                    average_response_time_ms REAL DEFAULT 0.0,
                    peak_concurrent_usage INTEGER DEFAULT 0,
                    uptime_percentage REAL DEFAULT 1.0,
                    error_rate REAL DEFAULT 0.0,
                    discovery_success_rate REAL DEFAULT 1.0,
                    last_updated DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Constraints  
                    CHECK (total_tools >= 0),
                    CHECK (active_tools >= 0),
                    CHECK (total_requests >= 0),
                    CHECK (successful_requests >= 0),
                    CHECK (average_response_time_ms >= 0.0),
                    CHECK (peak_concurrent_usage >= 0),
                    CHECK (uptime_percentage >= 0.0 AND uptime_percentage <= 1.0),
                    CHECK (error_rate >= 0.0 AND error_rate <= 1.0),
                    CHECK (discovery_success_rate >= 0.0 AND discovery_success_rate <= 1.0),
                    
                    -- Unique constraint for daily server analytics
                    UNIQUE(server_name, date)
                )
            """)
            
            # Create indexes for server_analytics
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_server_analytics_server 
                ON server_analytics(server_name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_server_analytics_date 
                ON server_analytics(date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_server_analytics_type 
                ON server_analytics(server_type)
            """)
            
            # Create query_patterns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS query_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT NOT NULL UNIQUE,
                    query_category TEXT NOT NULL,
                    query_keywords TEXT DEFAULT '[]',
                    frequency INTEGER DEFAULT 1,
                    success_rate REAL DEFAULT 0.0,
                    average_recommendation_count REAL DEFAULT 0.0,
                    most_selected_tools TEXT DEFAULT '[]',
                    first_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    trending_score REAL DEFAULT 0.0,
                    
                    -- Constraints
                    CHECK (frequency > 0),
                    CHECK (success_rate >= 0.0 AND success_rate <= 1.0),
                    CHECK (average_recommendation_count >= 0.0),
                    CHECK (trending_score >= 0.0)
                )
            """)
            
            # Create indexes for query_patterns
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_patterns_category 
                ON query_patterns(query_category)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_patterns_frequency 
                ON query_patterns(frequency DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_patterns_trending 
                ON query_patterns(trending_score DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_patterns_last_seen 
                ON query_patterns(last_seen)
            """)
            
            # Create api_usage_analytics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_usage_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    date DATETIME NOT NULL,
                    request_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    average_response_time_ms REAL DEFAULT 0.0,
                    max_response_time_ms INTEGER DEFAULT 0,
                    data_transferred_bytes INTEGER DEFAULT 0,
                    unique_clients INTEGER DEFAULT 0,
                    rate_limited_requests INTEGER DEFAULT 0,
                    last_updated DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Constraints
                    CHECK (request_count >= 0),
                    CHECK (success_count >= 0),
                    CHECK (error_count >= 0),
                    CHECK (average_response_time_ms >= 0.0),
                    CHECK (max_response_time_ms >= 0),
                    CHECK (data_transferred_bytes >= 0),
                    CHECK (unique_clients >= 0),
                    CHECK (rate_limited_requests >= 0),
                    
                    -- Unique constraint for hourly endpoint analytics
                    UNIQUE(endpoint, method, date)
                )
            """)
            
            # Create indexes for api_usage_analytics
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_usage_endpoint 
                ON api_usage_analytics(endpoint)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_usage_date 
                ON api_usage_analytics(date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_usage_method 
                ON api_usage_analytics(method)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_usage_requests 
                ON api_usage_analytics(request_count DESC)
            """)
            
            conn.commit()
            
            logger.info("Analytics tables migration completed successfully")
            return True
            
    except Exception as e:
        logger.error(f"Failed to apply analytics tables migration: {e}")
        return False


def down(db_path: Path) -> bool:
    """
    Rollback migration: Drop analytics tables.
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        True if rollback succeeded, False otherwise
    """
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            
            # Drop tables in reverse dependency order
            tables_to_drop = [
                "api_usage_analytics",
                "query_patterns", 
                "server_analytics",
                "recommendation_analytics"
            ]
            
            for table in tables_to_drop:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
            
            conn.commit()
            
            logger.info("Analytics tables migration rollback completed successfully")
            return True
            
    except Exception as e:
        logger.error(f"Failed to rollback analytics tables migration: {e}")
        return False


def run_migration(db_path: Path) -> bool:
    """
    Run the analytics tables migration (compatibility function).
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        True if migration succeeded, False otherwise
    """
    return up(db_path)


def rollback_migration(db_path: Path) -> bool:
    """
    Rollback the analytics tables migration (compatibility function).
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        True if rollback succeeded, False otherwise
    """
    return down(db_path)


def get_migration_info() -> Dict[str, Any]:
    """Get migration metadata."""
    return {
        "version": "002",
        "name": "analytics_tables",
        "description": "Create comprehensive analytics tables for usage tracking",
        "dependencies": ["001_tool_registry"],
        "tables_created": [
            "recommendation_analytics",
            "server_analytics", 
            "query_patterns",
            "api_usage_analytics"
        ],
        "indexes_created": [
            "idx_recommendation_analytics_session",
            "idx_recommendation_analytics_timestamp", 
            "idx_recommendation_analytics_provider",
            "idx_recommendation_analytics_query_category",
            "idx_server_analytics_server",
            "idx_server_analytics_date",
            "idx_server_analytics_type",
            "idx_query_patterns_category",
            "idx_query_patterns_frequency", 
            "idx_query_patterns_trending",
            "idx_query_patterns_last_seen",
            "idx_api_usage_endpoint",
            "idx_api_usage_date",
            "idx_api_usage_method",
            "idx_api_usage_requests"
        ]
    }


if __name__ == "__main__":
    # Allow running migration directly for testing
    db_path = get_database_path()
    print(f"Running analytics tables migration on: {db_path}")
    
    success = up(db_path)
    if success:
        print("✅ Migration completed successfully")
    else:
        print("❌ Migration failed")
        exit(1)