"""
AI Configuration Management with Encrypted Storage.

Provides secure, user-friendly management of AI service credentials
with interactive setup and automatic encryption.
"""

import json
import os
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import keyring
from pydantic import BaseModel, Field

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)

class AIProvider(str, Enum):
    """Supported AI providers."""
    CLAUDE = "claude"
    OPENAI = "openai"  
    GEMINI = "gemini"
    LOCAL = "local"
    OLLAMA = "ollama"

class AIServiceConfig(BaseModel):
    """Configuration for a specific AI service."""
    provider: AIProvider
    api_key_encrypted: Optional[str] = None
    api_key_set: bool = False
    base_url: Optional[str] = None  # For custom endpoints
    model: Optional[str] = None
    enabled: bool = True
    priority: int = 50  # 1-100, higher = preferred
    rate_limit_rpm: int = 60  # Requests per minute
    max_tokens: int = 8192
    temperature: float = 0.1  # Low for analytical tasks
    
class AICurationConfig(BaseModel):
    """AI curation engine configuration."""
    enabled: bool = False
    primary_provider: AIProvider = AIProvider.CLAUDE
    fallback_providers: List[AIProvider] = Field(default_factory=lambda: [AIProvider.OPENAI, AIProvider.LOCAL])
    services: Dict[AIProvider, AIServiceConfig] = Field(default_factory=dict)
    curation_frequency: str = "daily"  # daily, weekly, on-demand
    auto_update_suites: bool = True
    performance_threshold: float = 0.85
    compatibility_threshold: float = 0.90
    max_api_cost_per_month: float = 50.0  # USD
    enable_local_fallback: bool = True
    
    class Config:
        use_enum_values = True

class SecureAIConfigManager:
    """Manages AI configuration with encrypted credential storage."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".config" / "mcp-manager"
        self.config_file = self.config_dir / "ai_config.json"
        self.keyring_service = "mcp-manager-ai"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._config: Optional[AICurationConfig] = None
        
    def _get_encryption_key(self) -> bytes:
        """Get or create encryption key using system keyring."""
        try:
            # Try to get existing key from keyring
            key_b64 = keyring.get_password(self.keyring_service, "encryption_key")
            if key_b64:
                return base64.b64decode(key_b64.encode())
        except Exception as e:
            logger.debug(f"Could not retrieve encryption key from keyring: {e}")
        
        # Generate new key
        key = Fernet.generate_key()
        try:
            # Store in keyring for future use
            keyring.set_password(self.keyring_service, "encryption_key", base64.b64encode(key).decode())
        except Exception as e:
            logger.warning(f"Could not store encryption key in keyring: {e}")
            
        return key
    
    def _encrypt_value(self, value: str) -> str:
        """Encrypt a sensitive value."""
        try:
            key = self._get_encryption_key()
            f = Fernet(key)
            encrypted = f.encrypt(value.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt value: {e}")
            raise
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a sensitive value."""
        try:
            key = self._get_encryption_key()
            f = Fernet(key)
            encrypted_bytes = base64.b64decode(encrypted_value.encode())
            decrypted = f.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt value: {e}")
            raise
    
    def load_config(self) -> AICurationConfig:
        """Load AI configuration from disk."""
        if self._config is not None:
            return self._config
            
        if not self.config_file.exists():
            # Create default config
            self._config = AICurationConfig()
            self.save_config()
            return self._config
            
        try:
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
            
            self._config = AICurationConfig(**config_data)
            logger.debug("AI configuration loaded successfully")
            return self._config
            
        except Exception as e:
            logger.error(f"Failed to load AI config: {e}")
            # Return default config on error
            self._config = AICurationConfig()
            return self._config
    
    def save_config(self) -> None:
        """Save AI configuration to disk."""
        if self._config is None:
            return
            
        try:
            # Don't save encrypted API keys to JSON - they're in keyring
            config_dict = self._config.dict()
            for provider, service_config in config_dict.get("services", {}).items():
                if "api_key_encrypted" in service_config:
                    service_config["api_key_encrypted"] = None  # Don't persist
                    
            with open(self.config_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
                
            logger.debug("AI configuration saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save AI config: {e}")
            raise
    
    def set_api_key(self, provider: AIProvider, api_key: str) -> bool:
        """Securely store an API key for a provider."""
        try:
            # Store encrypted in keyring
            keyring.set_password(self.keyring_service, f"{provider.value}_api_key", api_key)
            
            # Update config
            config = self.load_config()
            if provider not in config.services:
                config.services[provider] = AIServiceConfig(provider=provider)
                
            config.services[provider].api_key_set = True
            self._config = config
            self.save_config()
            
            logger.info(f"API key set for {provider.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set API key for {provider.value}: {e}")
            return False
    
    def get_api_key(self, provider: AIProvider) -> Optional[str]:
        """Retrieve decrypted API key for a provider."""
        try:
            api_key = keyring.get_password(self.keyring_service, f"{provider.value}_api_key")
            return api_key
        except Exception as e:
            logger.debug(f"Could not retrieve API key for {provider.value}: {e}")
            return None
    
    def remove_api_key(self, provider: AIProvider) -> bool:
        """Remove stored API key for a provider."""
        try:
            keyring.delete_password(self.keyring_service, f"{provider.value}_api_key")
            
            # Update config
            config = self.load_config()
            if provider in config.services:
                config.services[provider].api_key_set = False
                
            self._config = config
            self.save_config()
            
            logger.info(f"API key removed for {provider.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove API key for {provider.value}: {e}")
            return False
    
    def update_service_config(self, provider: AIProvider, **kwargs) -> bool:
        """Update configuration for a specific AI service."""
        try:
            config = self.load_config()
            
            if provider not in config.services:
                config.services[provider] = AIServiceConfig(provider=provider)
            
            # Update service config with provided values
            service_config = config.services[provider]
            for key, value in kwargs.items():
                if hasattr(service_config, key):
                    setattr(service_config, key, value)
            
            self._config = config
            self.save_config()
            
            logger.info(f"Updated configuration for {provider.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update config for {provider.value}: {e}")
            return False
    
    def get_available_providers(self) -> List[AIProvider]:
        """Get list of providers with valid API keys."""
        config = self.load_config()
        available = []
        
        for provider in AIProvider:
            if provider == AIProvider.LOCAL or provider == AIProvider.OLLAMA:
                # Local providers don't need API keys
                available.append(provider)
            elif provider in config.services and config.services[provider].api_key_set:
                # Check if API key is actually available
                if self.get_api_key(provider):
                    available.append(provider)
        
        return available
    
    def get_primary_provider(self) -> Optional[AIProvider]:
        """Get the primary AI provider if available."""
        config = self.load_config()
        available = self.get_available_providers()
        
        if config.primary_provider in available:
            return config.primary_provider
            
        # Return first available fallback
        for provider in config.fallback_providers:
            if provider in available:
                return provider
                
        return None
    
    def validate_provider_access(self, provider: AIProvider) -> bool:
        """Test if a provider is accessible with current configuration."""
        if provider in [AIProvider.LOCAL, AIProvider.OLLAMA]:
            # TODO: Check if local AI services are running
            return True
            
        api_key = self.get_api_key(provider)
        if not api_key:
            return False
            
        # TODO: Make a test API call to validate the key
        # This would be implemented when we add the actual AI client
        return True
    
    def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all configured AI services."""
        config = self.load_config()
        status = {}
        
        for provider in AIProvider:
            provider_status = {
                "configured": provider in config.services,
                "api_key_set": False,
                "accessible": False,
                "enabled": False,
                "priority": 0
            }
            
            if provider in config.services:
                service_config = config.services[provider]
                provider_status.update({
                    "api_key_set": service_config.api_key_set,
                    "enabled": service_config.enabled,
                    "priority": service_config.priority,
                    "accessible": self.validate_provider_access(provider)
                })
            elif provider in [AIProvider.LOCAL, AIProvider.OLLAMA]:
                provider_status.update({
                    "api_key_set": True,  # No key needed
                    "accessible": self.validate_provider_access(provider)
                })
                
            status[provider.value] = provider_status
            
        return status

# Global instance
ai_config_manager = SecureAIConfigManager()