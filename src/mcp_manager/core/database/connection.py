"""
Database Connection Manager - Async SQLite + WAL

Handles connection pooling and WAL configuration.
Single responsibility: Database connection management.
"""

import aiosqlite
import asyncio
from pathlib import Path
from typing import Optional, AsyncContextManager
from contextlib import asynccontextmanager

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DatabaseConnection:
    """Manages async SQLite connections with WAL mode."""
    
    def __init__(self, db_path: Path):
        """Initialize connection manager."""
        self.db_path = db_path
        self._connection_lock = asyncio.Lock()
        self._is_configured = False
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncContextManager[aiosqlite.Connection]:
        """Get an async database connection with automatic cleanup."""
        async with self._connection_lock:
            try:
                conn = await aiosqlite.connect(self.db_path)
                
                # Configure WAL mode on first use
                if not self._is_configured:
                    await self._configure_connection(conn)
                    self._is_configured = True
                
                # Enable foreign keys for this connection
                await conn.execute("PRAGMA foreign_keys = ON")
                
                yield conn
                await conn.commit()
                
            except Exception as e:
                if 'conn' in locals():
                    await conn.rollback()
                logger.error(f"Database connection error: {e}")
                raise
            finally:
                if 'conn' in locals():
                    await conn.close()
    
    async def _configure_connection(self, conn: aiosqlite.Connection):
        """Configure SQLite connection for optimal WAL performance."""
        logger.info("🔧 Configuring SQLite connection with WAL mode...")
        
        # Enable WAL mode for concurrent access
        await conn.execute("PRAGMA journal_mode = WAL")
        
        # Performance optimizations
        await conn.execute("PRAGMA synchronous = NORMAL")      # Balance safety/speed
        await conn.execute("PRAGMA cache_size = -64000")       # 64MB cache 
        await conn.execute("PRAGMA temp_store = memory")       # Temp tables in memory
        await conn.execute("PRAGMA mmap_size = 134217728")     # 128MB memory-mapped
        await conn.execute("PRAGMA wal_autocheckpoint = 1000") # Auto-checkpoint
        
        # Verify WAL mode
        result = await conn.execute("PRAGMA journal_mode")
        mode = await result.fetchone()
        if mode and mode[0].upper() == 'WAL':
            logger.info("✅ WAL mode configured successfully")
        else:
            logger.warning(f"⚠️ Unexpected journal mode: {mode}")
    
    async def health_check(self) -> bool:
        """Check database connection health."""
        try:
            async with self.get_connection() as conn:
                await conn.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    async def get_wal_info(self) -> dict:
        """Get WAL file information."""
        try:
            async with self.get_connection() as conn:
                info = {}
                
                # Get WAL mode status
                result = await conn.execute("PRAGMA journal_mode")
                mode = await result.fetchone()
                info['journal_mode'] = mode[0] if mode else 'unknown'
                
                # WAL file size
                wal_file = Path(str(self.db_path) + '-wal')
                info['wal_file_exists'] = wal_file.exists()
                if wal_file.exists():
                    info['wal_file_size_bytes'] = wal_file.stat().st_size
                    info['wal_file_size_mb'] = round(info['wal_file_size_bytes'] / 1024 / 1024, 2)
                
                return info
        except Exception as e:
            logger.error(f"Failed to get WAL info: {e}")
            return {'error': str(e)}


# Global connection instance
_db_connection: Optional[DatabaseConnection] = None


def get_database_connection(db_path: Optional[Path] = None) -> DatabaseConnection:
    """Get singleton database connection manager."""
    global _db_connection
    
    if _db_connection is None:
        if db_path is None:
            from mcp_manager.utils.config import get_config
            config = get_config()
            data_dir = Path(getattr(config, 'data_dir', '~/.local/share/mcp-manager')).expanduser()
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = data_dir / 'mcp_manager.db'
        
        _db_connection = DatabaseConnection(db_path)
        logger.info(f"📊 Database connection initialized: {db_path}")
    
    return _db_connection