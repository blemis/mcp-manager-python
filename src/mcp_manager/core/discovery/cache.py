"""
Cache management for discovery results.
"""

from datetime import datetime, timedelta
from typing import List

from pydantic import BaseModel

from mcp_manager.core.models import DiscoveryResult


class CacheEntry(BaseModel):
    """Cache entry for discovery results."""
    
    data: List[DiscoveryResult]
    timestamp: datetime
    ttl: int  # Time to live in seconds
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl)