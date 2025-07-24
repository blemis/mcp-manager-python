"""
API middleware for MCP Manager.

Provides rate limiting, security headers, request logging, and error handling.
"""

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional

from fastapi import HTTPException, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware

from mcp_manager.api.auth import AuthenticationManager
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""
    
    def __init__(self, app, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        """Initialize rate limiter."""
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        
        # Store request timestamps per client
        self._minute_windows: Dict[str, deque] = defaultdict(deque)
        self._hour_windows: Dict[str, deque] = defaultdict(deque)
        
        logger.info("Rate limiting middleware initialized", extra={
            "requests_per_minute": requests_per_minute,
            "requests_per_hour": requests_per_hour
        })
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Use API key if present, otherwise IP address
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return f"token:{auth_header[7:12]}..."  # First 5 chars of token
        
        # Use forwarded IP if behind proxy
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        return str(request.client.host)
    
    def _cleanup_old_requests(self, request_times: deque, window_seconds: int):
        """Remove requests older than window."""
        cutoff = time.time() - window_seconds
        while request_times and request_times[0] < cutoff:
            request_times.popleft()
    
    def _check_rate_limit(self, client_id: str) -> Optional[Dict[str, int]]:
        """Check if client exceeds rate limits."""
        now = time.time()
        
        # Clean up old requests
        minute_requests = self._minute_windows[client_id]
        hour_requests = self._hour_windows[client_id]
        
        self._cleanup_old_requests(minute_requests, 60)
        self._cleanup_old_requests(hour_requests, 3600)
        
        # Check limits
        if len(minute_requests) >= self.requests_per_minute:
            retry_after = 60 - (now - minute_requests[0])
            return {
                "limit_type": "minute",
                "limit": self.requests_per_minute,
                "current": len(minute_requests),
                "retry_after": int(retry_after)
            }
        
        if len(hour_requests) >= self.requests_per_hour:
            retry_after = 3600 - (now - hour_requests[0])
            return {
                "limit_type": "hour", 
                "limit": self.requests_per_hour,
                "current": len(hour_requests),
                "retry_after": int(retry_after)
            }
        
        return None
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        client_id = self._get_client_id(request)
        
        # Check rate limits
        limit_info = self._check_rate_limit(client_id)
        if limit_info:
            logger.warning("Rate limit exceeded", extra={
                "client_id": client_id,
                "limit_type": limit_info["limit_type"],
                "current_requests": limit_info["current"],
                "limit": limit_info["limit"]
            })
            
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit_info['current']}/{limit_info['limit']} requests per {limit_info['limit_type']}",
                headers={"Retry-After": str(limit_info["retry_after"])}
            )
        
        # Record request
        now = time.time()
        self._minute_windows[client_id].append(now)
        self._hour_windows[client_id].append(now)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        minute_requests = len(self._minute_windows[client_id])
        hour_requests = len(self._hour_windows[client_id])
        
        response.headers["X-RateLimit-Minute-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Minute-Remaining"] = str(max(0, self.requests_per_minute - minute_requests))
        response.headers["X-RateLimit-Hour-Limit"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Hour-Remaining"] = str(max(0, self.requests_per_hour - hour_requests))
        
        return response


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security headers and CORS middleware."""
    
    def __init__(self, app, allowed_origins: Optional[list] = None):
        """Initialize security middleware."""
        super().__init__(app)
        self.allowed_origins = allowed_origins or ["http://localhost:3000", "http://127.0.0.1:3000"]
        
        logger.info("Security middleware initialized", extra={
            "allowed_origins": self.allowed_origins
        })
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # CORS headers
        origin = request.headers.get("Origin")
        if origin in self.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Max-Age"] = "86400"
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Request/response logging middleware."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""
        start_time = time.time()
        
        # Log request
        logger.info("API request started", extra={
            "method": request.method,
            "url": str(request.url),
            "client_ip": getattr(request.client, 'host', 'unknown'),
            "user_agent": request.headers.get("User-Agent", "unknown"),
            "content_length": request.headers.get("Content-Length", 0)
        })
        
        # Process request
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            logger.info("API request completed", extra={
                "method": request.method,
                "url": str(request.url),
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "response_size": response.headers.get("Content-Length", 0)
            })
            
            # Add timing header
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            logger.error("API request failed", extra={
                "method": request.method,
                "url": str(request.url),
                "duration_ms": round(duration_ms, 2),
                "error": str(e),
                "error_type": type(e).__name__
            })
            
            raise


class AuthenticationMiddleware:
    """Authentication middleware using dependency injection."""
    
    def __init__(self):
        """Initialize authentication middleware."""
        self.auth_manager = AuthenticationManager()
        self.security = HTTPBearer(auto_error=False)
        
        logger.info("Authentication middleware initialized")
    
    async def get_current_user(
        self, 
        credentials: Optional[HTTPAuthorizationCredentials] = None
    ) -> Optional[Dict[str, any]]:
        """Get current authenticated user."""
        if not credentials:
            return None
        
        token = credentials.credentials
        
        # Try JWT token first
        auth_token = self.auth_manager.validate_jwt_token(token)
        if auth_token:
            return {
                "user_id": auth_token.user_id,
                "scopes": auth_token.scopes,
                "auth_type": "jwt"
            }
        
        # Try API key
        api_key = self.auth_manager.validate_api_key(token)
        if api_key:
            return {
                "user_id": api_key.key_id,
                "scopes": api_key.scopes,
                "auth_type": "api_key",
                "key_name": api_key.name
            }
        
        return None
    
    def require_scopes(self, required_scopes: list):
        """Decorator to require specific scopes."""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                # Get current user from kwargs (injected by FastAPI)
                current_user = kwargs.get('current_user')
                if not current_user:
                    raise HTTPException(
                        status_code=401,
                        detail="Authentication required"
                    )
                
                # Check scopes
                user_scopes = current_user.get('scopes', [])
                for required_scope in required_scopes:
                    if not self.auth_manager.check_permission(user_scopes, required_scope):
                        raise HTTPException(
                            status_code=403,
                            detail=f"Insufficient permissions. Required: {required_scope}"
                        )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Global error handling middleware."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle uncaught exceptions."""
        try:
            return await call_next(request)
        except HTTPException:
            # Re-raise HTTP exceptions (handled by FastAPI)
            raise
        except Exception as e:
            logger.error("Unhandled API error", extra={
                "method": request.method,
                "url": str(request.url),
                "error": str(e),
                "error_type": type(e).__name__
            }, exc_info=True)
            
            # Return generic error response
            raise HTTPException(
                status_code=500,
                detail="Internal server error"
            )