"""
Data models for hybrid server state management.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from mcp_manager.core.models import Server


class ConnectionStatus(Enum):
    """Server connection status."""
    CONNECTED = "connected"
    FAILED = "failed" 
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class ServerStatus:
    """Real-time server connection status."""
    server_name: str
    status: ConnectionStatus
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    tool_count: Optional[int] = None
    checked_at: datetime = None
    
    def __post_init__(self):
        if self.checked_at is None:
            self.checked_at = datetime.now()


@dataclass
class ServerState:
    """Combined server definition and current status."""
    server: Server
    status: Optional[ServerStatus] = None
    last_seen: Optional[datetime] = None
    
    @property
    def is_healthy(self) -> bool:
        """Check if server is currently healthy."""
        return self.status and self.status.status == ConnectionStatus.CONNECTED
    
    @property
    def status_age_seconds(self) -> Optional[float]:
        """Age of status information in seconds."""
        if not self.status or not self.status.checked_at:
            return None
        return (datetime.now() - self.status.checked_at).total_seconds()


@dataclass 
class ServerAnalytics:
    """Historical analytics for a server."""
    server_name: str
    total_checks: int
    success_rate: float
    avg_response_time_ms: Optional[float]
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    install_count: int
    remove_count: int
    usage_events: List[Dict[str, Any]]
    
    @property
    def reliability_score(self) -> float:
        """Calculate reliability score (0-100)."""
        if self.total_checks == 0:
            return 0.0
        
        # Base score from success rate
        base_score = self.success_rate * 70
        
        # Bonus for consistent usage
        usage_bonus = min(self.total_checks / 100, 1.0) * 20
        
        # Penalty for recent failures
        recent_failure_penalty = 0
        if self.last_failure and self.last_success:
            if self.last_failure > self.last_success:
                recent_failure_penalty = 10
        
        return min(base_score + usage_bonus - recent_failure_penalty, 100.0)


@dataclass
class ConfigDrift:
    """Detected difference between config and live state."""
    server_name: str
    drift_type: str  # 'missing_in_live', 'extra_in_live', 'config_mismatch'
    config_value: Any
    live_value: Any
    description: str
    detected_at: datetime = None
    
    def __post_init__(self):
        if self.detected_at is None:
            self.detected_at = datetime.now()


@dataclass
class UsageEvent:
    """Server usage event for analytics."""
    server_name: str
    event_type: str  # 'install', 'remove', 'enable', 'disable', 'health_check'
    event_data: Dict[str, Any]
    user_context: Optional[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()