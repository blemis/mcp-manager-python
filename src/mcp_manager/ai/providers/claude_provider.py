"""
Claude (Anthropic) LLM provider implementation.

Integrates with Anthropic's Claude models for AI-powered tool recommendations
and contextual suggestions.
"""

import asyncio
import json
from typing import Any, Dict, Optional

from mcp_manager.ai.llm_providers import (
    BaseLLMProvider,
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
)


class ClaudeProvider(BaseLLMProvider):
    """Claude (Anthropic) LLM provider implementation."""
    
    def _validate_config(self) -> None:
        """Validate Claude-specific configuration."""
        if not self.config.api_key:
            raise LLMProviderError(
                "Claude API key is required. Set MCP_LLM_API_KEY or ANTHROPIC_API_KEY environment variable."
            )
        
        # Set default model if not specified
        if not self.config.model:
            self.config.model = "claude-3-5-sonnet-20241022"
        
        self.logger.debug("Claude provider configuration validated", extra={
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "has_api_key": bool(self.config.api_key)
        })
    
    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None,
                              **kwargs) -> LLMResponse:
        """
        Generate a response using Claude.
        
        Args:
            prompt: User prompt/query
            system_prompt: Optional system prompt for context
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            LLMResponse with Claude's generated content
        """
        try:
            # Import anthropic here to avoid requiring it unless Claude is used
            try:
                import anthropic
            except ImportError:
                raise LLMProviderError(
                    "anthropic package is required for Claude provider. Install with: pip install anthropic"
                )
            
            # Initialize Anthropic client
            client = anthropic.AsyncAnthropic(
                api_key=self.config.api_key,
                timeout=self.config.timeout_seconds
            )
            
            # Prepare messages
            messages = [{"role": "user", "content": prompt}]
            
            # Prepare request parameters
            request_params = {
                "model": self.config.get_default_model(),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "temperature": kwargs.get("temperature", self.config.temperature),
                "messages": messages
            }
            
            # Add system prompt if provided
            if system_prompt:
                request_params["system"] = system_prompt
            
            self.logger.debug("Sending request to Claude", extra={
                "model": request_params["model"],
                "max_tokens": request_params["max_tokens"],
                "temperature": request_params["temperature"],
                "has_system_prompt": bool(system_prompt),
                "prompt_length": len(prompt)
            })
            
            # Make the API call with retry logic
            response = await self._make_request_with_retry(client, request_params)
            
            # Extract response content
            content = response.content[0].text if response.content else ""
            usage_tokens = response.usage.input_tokens + response.usage.output_tokens if response.usage else None
            
            self.logger.info("Claude response generated successfully", extra={
                "model": response.model,
                "usage_tokens": usage_tokens,
                "response_length": len(content),
                "stop_reason": response.stop_reason
            })
            
            return self._create_response(
                content=content,
                usage_tokens=usage_tokens,
                model_used=response.model,
                stop_reason=response.stop_reason,
                usage=response.usage.model_dump() if response.usage else None
            )
            
        except anthropic.AuthenticationError as e:
            self.logger.error("Claude authentication failed", extra={"error": str(e)})
            raise LLMAuthenticationError(f"Claude authentication failed: {e}")
        
        except anthropic.RateLimitError as e:
            self.logger.error("Claude rate limit exceeded", extra={"error": str(e)})
            raise LLMRateLimitError(f"Claude rate limit exceeded: {e}")
        
        except anthropic.APITimeoutError as e:
            self.logger.error("Claude request timed out", extra={"error": str(e)})
            raise LLMTimeoutError(f"Claude request timed out: {e}")
        
        except Exception as e:
            self.logger.error("Claude request failed", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise LLMProviderError(f"Claude request failed: {e}")
    
    async def generate_structured_response(self, prompt: str, schema: Dict[str, Any],
                                         system_prompt: Optional[str] = None,
                                         **kwargs) -> LLMResponse:
        """
        Generate a structured response matching a specific schema.
        
        Args:
            prompt: User prompt/query
            schema: JSON schema for the expected response structure
            system_prompt: Optional system prompt for context
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse with structured content
        """
        # Enhance the prompt to request structured output
        structured_prompt = f"""
{prompt}

Please respond with a JSON object that matches this exact schema:
{json.dumps(schema, indent=2)}

Important: Return ONLY the JSON object, no additional text or formatting.
"""
        
        # Enhance system prompt to emphasize structured output
        enhanced_system = """You are a helpful assistant that always responds with valid JSON matching the requested schema."""
        if system_prompt:
            enhanced_system = f"{system_prompt}\n\n{enhanced_system}"
        
        response = await self.generate_response(
            prompt=structured_prompt,
            system_prompt=enhanced_system,
            **kwargs
        )
        
        # Attempt to validate the JSON response
        try:
            json.loads(response.content)
            self.logger.debug("Structured response validated successfully")
        except json.JSONDecodeError as e:
            self.logger.warning("Structured response is not valid JSON", extra={
                "error": str(e),
                "response_preview": response.content[:200]
            })
            # Don't raise an error - let the caller handle invalid JSON
        
        return response
    
    async def _make_request_with_retry(self, client, request_params: Dict[str, Any]):
        """Make request to Claude with retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                response = await client.messages.create(**request_params)
                return response
                
            except (anthropic.RateLimitError, anthropic.APITimeoutError) as e:
                last_exception = e
                if attempt < self.config.max_retries - 1:
                    wait_time = (2 ** attempt) * 1  # Exponential backoff starting at 1 second
                    self.logger.warning(f"Request failed (attempt {attempt + 1}), retrying in {wait_time}s", extra={
                        "error": str(e),
                        "attempt": attempt + 1,
                        "max_retries": self.config.max_retries
                    })
                    await asyncio.sleep(wait_time)
                else:
                    raise
            
            except Exception as e:
                # Don't retry on other types of errors
                raise e
        
        # This should never be reached, but just in case
        if last_exception:
            raise last_exception