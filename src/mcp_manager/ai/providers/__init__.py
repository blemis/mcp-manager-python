"""
LLM provider implementations for MCP Manager.

Registers all available LLM providers with the factory for automatic discovery.
"""

from mcp_manager.ai.llm_providers import LLMProvider, LLMProviderFactory
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)

# Import providers and register them
try:
    from .claude_provider import ClaudeProvider
    LLMProviderFactory.register_provider(LLMProvider.CLAUDE, ClaudeProvider)
except ImportError as e:
    logger.warning(f"Claude provider not available: {e}")

try:
    from .openai_provider import OpenAIProvider, AzureOpenAIProvider
    LLMProviderFactory.register_provider(LLMProvider.OPENAI, OpenAIProvider)
    LLMProviderFactory.register_provider(LLMProvider.AZURE_OPENAI, AzureOpenAIProvider)
except ImportError as e:
    logger.warning(f"OpenAI providers not available: {e}")

try:
    from .ollama_provider import OllamaProvider
    LLMProviderFactory.register_provider(LLMProvider.OLLAMA, OllamaProvider)
except ImportError as e:
    logger.warning(f"Ollama provider not available: {e}")

# Export commonly used items
__all__ = [
    "ClaudeProvider",
    "OpenAIProvider", 
    "AzureOpenAIProvider",
    "OllamaProvider"
]