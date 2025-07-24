"""
Authentication and authorization for MCP Manager API.

Provides JWT-based authentication, API key management, and role-based access control.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

import jwt
from cryptography.fernet import Fernet
from pydantic import BaseModel

from mcp_manager.utils.config import get_config
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class APIKey(BaseModel):
    """API key model."""
    
    key_id: str
    key_hash: str
    name: str
    scopes: List[str]
    created_at: datetime
    last_used: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True


class AuthToken(BaseModel):
    """Authentication token model."""
    
    user_id: str
    scopes: List[str]
    issued_at: datetime
    expires_at: datetime
    token_type: str = "Bearer"


class AuthenticationManager:
    """Manages API authentication and authorization."""
    
    def __init__(self):
        """Initialize authentication manager."""
        self.config = get_config()
        self.logger = logger
        
        # JWT settings
        self.jwt_secret = self._get_jwt_secret()
        self.jwt_algorithm = "HS256"
        self.token_expiry_hours = 24
        
        # API key storage (in production, use database)
        self._api_keys: Dict[str, APIKey] = {}
        self._load_api_keys()
        
        # Valid scopes
        self.valid_scopes = {
            "analytics:read", "analytics:write", "analytics:export",
            "tools:read", "tools:write", "tools:execute",
            "servers:read", "servers:write", "servers:manage",
            "config:read", "config:write",
            "admin:full"
        }
        
        logger.info("Authentication manager initialized", extra={
            "valid_scopes_count": len(self.valid_scopes),
            "api_keys_loaded": len(self._api_keys)
        })
    
    def _get_jwt_secret(self) -> str:
        """Get or generate JWT secret."""
        # In production, use environment variable or secure key management
        secret = getattr(self.config, 'jwt_secret', None)
        if not secret:
            secret = secrets.token_urlsafe(32)
            logger.warning("JWT secret generated, not from configuration")
        return secret
    
    def _load_api_keys(self):
        """Load API keys from configuration or storage."""
        # In production, load from database
        # For now, create a default admin key if none exists
        if not self._api_keys:
            admin_key = self.create_api_key(
                name="default-admin",
                scopes=["admin:full"],
                expires_days=365
            )
            logger.info("Default admin API key created", extra={
                "key_id": admin_key.key_id,
                "scopes": admin_key.scopes
            })
    
    def create_api_key(
        self, 
        name: str, 
        scopes: List[str], 
        expires_days: Optional[int] = None
    ) -> APIKey:
        """Create a new API key."""
        # Validate scopes
        invalid_scopes = set(scopes) - self.valid_scopes
        if invalid_scopes:
            raise ValueError(f"Invalid scopes: {invalid_scopes}")
        
        # Generate key
        key_id = secrets.token_urlsafe(16)
        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Create expiration
        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            scopes=scopes,
            created_at=datetime.utcnow(),
            expires_at=expires_at
        )
        
        self._api_keys[key_id] = api_key
        
        logger.info("API key created", extra={
            "key_id": key_id,
            "name": name,
            "scopes": scopes,
            "expires_at": expires_at.isoformat() if expires_at else None
        })
        
        # Return the raw key for user (only shown once)
        api_key.raw_key = raw_key  # Temporary attribute
        return api_key
    
    def validate_api_key(self, raw_key: str) -> Optional[APIKey]:
        """Validate an API key and return associated permissions."""
        if not raw_key:
            return None
        
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        for api_key in self._api_keys.values():
            if api_key.key_hash == key_hash:
                # Check if key is active
                if not api_key.is_active:
                    logger.warning("Inactive API key used", extra={
                        "key_id": api_key.key_id
                    })
                    return None
                
                # Check expiration
                if api_key.expires_at and datetime.utcnow() > api_key.expires_at:
                    logger.warning("Expired API key used", extra={
                        "key_id": api_key.key_id,
                        "expires_at": api_key.expires_at.isoformat()
                    })
                    return None
                
                # Update last used
                api_key.last_used = datetime.utcnow()
                
                logger.debug("API key validated", extra={
                    "key_id": api_key.key_id,
                    "scopes": api_key.scopes
                })
                
                return api_key
        
        logger.warning("Invalid API key attempted")
        return None
    
    def create_jwt_token(self, user_id: str, scopes: List[str]) -> str:
        """Create a JWT token."""
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=self.token_expiry_hours)
        
        payload = {
            "user_id": user_id,
            "scopes": scopes,
            "iat": now,
            "exp": expires_at,
            "iss": "mcp-manager-api"
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        
        logger.debug("JWT token created", extra={
            "user_id": user_id,
            "scopes": scopes,
            "expires_at": expires_at.isoformat()
        })
        
        return token
    
    def validate_jwt_token(self, token: str) -> Optional[AuthToken]:
        """Validate a JWT token."""
        try:
            payload = jwt.decode(
                token, 
                self.jwt_secret, 
                algorithms=[self.jwt_algorithm]
            )
            
            auth_token = AuthToken(
                user_id=payload["user_id"],
                scopes=payload["scopes"],
                issued_at=datetime.fromtimestamp(payload["iat"]),
                expires_at=datetime.fromtimestamp(payload["exp"])
            )
            
            logger.debug("JWT token validated", extra={
                "user_id": auth_token.user_id,
                "scopes": auth_token.scopes
            })
            
            return auth_token
            
        except jwt.ExpiredSignatureError:
            logger.warning("Expired JWT token")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid JWT token", extra={"error": str(e)})
            return None
    
    def check_permission(self, scopes: List[str], required_scope: str) -> bool:
        """Check if scopes include required permission."""
        # Admin scope grants all permissions
        if "admin:full" in scopes:
            return True
        
        # Check for exact scope match
        if required_scope in scopes:
            return True
        
        # Check for wildcard permissions (e.g., "analytics:*" covers "analytics:read")
        scope_parts = required_scope.split(":")
        if len(scope_parts) == 2:
            wildcard_scope = f"{scope_parts[0]}:*"
            if wildcard_scope in scopes:
                return True
        
        return False
    
    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        if key_id in self._api_keys:
            self._api_keys[key_id].is_active = False
            logger.info("API key revoked", extra={"key_id": key_id})
            return True
        return False
    
    def list_api_keys(self) -> List[APIKey]:
        """List all API keys (without sensitive data)."""
        return [
            APIKey(
                key_id=key.key_id,
                key_hash="***",  # Hide hash
                name=key.name,
                scopes=key.scopes,
                created_at=key.created_at,
                last_used=key.last_used,
                expires_at=key.expires_at,
                is_active=key.is_active
            )
            for key in self._api_keys.values()
        ]
    
    def get_api_key_stats(self) -> Dict[str, int]:
        """Get API key statistics."""
        active_keys = sum(1 for key in self._api_keys.values() if key.is_active)
        expired_keys = sum(
            1 for key in self._api_keys.values() 
            if key.expires_at and datetime.utcnow() > key.expires_at
        )
        
        return {
            "total_keys": len(self._api_keys),
            "active_keys": active_keys,
            "expired_keys": expired_keys,
            "revoked_keys": len(self._api_keys) - active_keys
        }