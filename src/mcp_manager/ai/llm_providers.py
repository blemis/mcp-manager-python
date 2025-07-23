"""
LLM provider interfaces for AI-powered tool recommendations.

Supports multiple LLM providers including Claude (Anthropic), OpenAI GPT models,
and other compatible APIs with configurable authentication and settings.
"""

import json
import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    CLAUDE = "claude"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"
    CUSTOM = "custom"


class LLMConfig(BaseModel):
    """Configuration for LLM providers."""
    
    provider: LLMProvider = Field(
        default_factory=lambda: LLMProvider(os.getenv("MCP_LLM_PROVIDER", "claude")),
        description="LLM provider to use"
    )
    
    # Authentication
    api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("MCP_LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY"),
        description="API key for the LLM service"
    )
    
    # Model configuration
    model: Optional[str] = Field(
        default_factory=lambda: os.getenv("MCP_LLM_MODEL"),
        description="Specific model to use (e.g., claude-3.5-sonnet, gpt-4)"
    )
    
    # Request parameters
    max_tokens: int = Field(
        default_factory=lambda: int(os.getenv("MCP_LLM_MAX_TOKENS", "2000")),
        description="Maximum tokens in response"
    )
    temperature: float = Field(
        default_factory=lambda: float(os.getenv("MCP_LLM_TEMPERATURE", "0.3")),
        description="Temperature for response randomness"
    )
    
    # Provider-specific settings
    base_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("MCP_LLM_BASE_URL"),
        description="Base URL for custom or local LLM services"
    )
    azure_endpoint: Optional[str] = Field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT"),
        description="Azure OpenAI endpoint"
    )
    azure_api_version: str = Field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        description="Azure OpenAI API version"
    )
    
    # Timeout and retry settings
    timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("MCP_LLM_TIMEOUT", "30")),
        description="Request timeout in seconds"
    )
    max_retries: int = Field(
        default_factory=lambda: int(os.getenv("MCP_LLM_MAX_RETRIES", "3")),
        description="Maximum retry attempts"
    )
    
    def get_default_model(self) -> str:
        """Get default model for the configured provider."""
        if self.model:
            return self.model
            
        defaults = {
            LLMProvider.CLAUDE: "claude-3-5-sonnet-20241022",
            LLMProvider.OPENAI: "gpt-4",
            LLMProvider.AZURE_OPENAI: "gpt-4",
            LLMProvider.OLLAMA: "llama2",
            LLMProvider.CUSTOM: "default"
        }
        return defaults.get(self.provider, "default")


class LLMResponse(BaseModel):
    """Response from an LLM provider."""
    
    content: str = Field(description="Response content")
    usage_tokens: Optional[int] = Field(default=None, description="Tokens used in request")
    model_used: Optional[str] = Field(default=None, description="Model that generated the response")
    provider: Optional[str] = Field(default=None, description="Provider that handled the request")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional response metadata")


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: LLMConfig):
        """
        Initialize LLM provider.
        
        Args:
            config: LLM configuration
        """
        self.config = config
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        
        # Validate configuration
        self._validate_config()
        
        self.logger.info(f"Initialized {self.__class__.__name__}", extra={
            "provider": self.config.provider.value,
            "model": self.config.get_default_model(),
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature
        })
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider-specific configuration."""
        pass
    
    @abstractmethod
    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None,
                              **kwargs) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: User prompt/query
            system_prompt: Optional system prompt for context
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse with generated content
        """
        pass
    
    @abstractmethod
    async def generate_structured_response(self, prompt: str, schema: Dict[str, Any],
                                         system_prompt: Optional[str] = None,
                                         **kwargs) -> LLMResponse:
        """
        Generate a structured response matching a specific schema.
        
        Args:
            prompt: User prompt/query
            schema: JSON schema for the expected response structure
            system_prompt: Optional system prompt for context
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse with structured content
        """
        pass
    
    def _create_response(self, content: str, usage_tokens: Optional[int] = None,
                        model_used: Optional[str] = None, **metadata) -> LLMResponse:
        """Create a standardized LLMResponse object."""
        return LLMResponse(
            content=content,
            usage_tokens=usage_tokens,
            model_used=model_used or self.config.get_default_model(),
            provider=self.config.provider.value,
            metadata=metadata
        )


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMAuthenticationError(LLMProviderError):
    """Raised when authentication fails."""
    pass


class LLMRateLimitError(LLMProviderError):
    """Raised when rate limits are exceeded."""
    pass


class LLMTimeoutError(LLMProviderError):
    """Raised when requests timeout."""
    pass


class LLMProviderFactory:
    """Factory for creating LLM provider instances."""
    
    _providers = {}
    
    @classmethod
    def register_provider(cls, provider_type: LLMProvider, provider_class: type):
        """Register a new LLM provider class."""
        cls._providers[provider_type] = provider_class
        logger.info(f"Registered LLM provider: {provider_type.value}")
    
    @classmethod
    def create_provider(cls, config: Optional[LLMConfig] = None) -> BaseLLMProvider:
        """
        Create an LLM provider instance.
        
        Args:
            config: LLM configuration. If None, uses defaults from environment.
            
        Returns:
            LLM provider instance
            
        Raises:
            LLMProviderError: If provider is not supported or configuration is invalid
        """
        if config is None:
            config = LLMConfig()
        
        provider_class = cls._providers.get(config.provider)
        if not provider_class:
            raise LLMProviderError(f"Unsupported LLM provider: {config.provider}")
        
        return provider_class(config)
    
    @classmethod
    def get_supported_providers(cls) -> List[str]:
        """Get list of supported provider names."""
        return [provider.value for provider in cls._providers.keys()]


def create_llm_provider(provider: Optional[str] = None, **kwargs) -> BaseLLMProvider:
    """
    Convenience function to create an LLM provider.
    
    Args:
        provider: Provider name (claude, openai, etc.)
        **kwargs: Additional configuration parameters override environment variables
        
    Returns:
        LLM provider instance
    """
    # Create config with overrides
    config_dict = {}
    if provider:
        config_dict["provider"] = LLMProvider(provider)
    
    # Add any provided kwargs
    config_dict.update(kwargs)
    
    config = LLMConfig(**config_dict)
    return LLMProviderFactory.create_provider(config)