"""
OpenAI LLM provider implementation.

Integrates with OpenAI's GPT models for AI-powered tool recommendations
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


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider implementation."""
    
    def _validate_config(self) -> None:
        """Validate OpenAI-specific configuration."""
        if not self.config.api_key:
            raise LLMProviderError(
                "OpenAI API key is required. Set MCP_LLM_API_KEY or OPENAI_API_KEY environment variable."
            )
        
        # Set default model if not specified
        if not self.config.model:
            self.config.model = "gpt-4"
        
        self.logger.debug("OpenAI provider configuration validated", extra={
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "has_api_key": bool(self.config.api_key)
        })
    
    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None,
                              **kwargs) -> LLMResponse:
        """
        Generate a response using OpenAI GPT.
        
        Args:
            prompt: User prompt/query
            system_prompt: Optional system prompt for context
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            LLMResponse with OpenAI's generated content
        """
        try:
            # Import openai here to avoid requiring it unless OpenAI is used
            try:
                import openai
            except ImportError:
                raise LLMProviderError(
                    "openai package is required for OpenAI provider. Install with: pip install openai"
                )
            
            # Initialize OpenAI client
            client = openai.AsyncOpenAI(
                api_key=self.config.api_key,
                timeout=self.config.timeout_seconds,
                base_url=self.config.base_url  # For custom endpoints
            )
            
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Prepare request parameters
            request_params = {
                "model": self.config.get_default_model(),
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "temperature": kwargs.get("temperature", self.config.temperature)
            }
            
            self.logger.debug("Sending request to OpenAI", extra={
                "model": request_params["model"],
                "max_tokens": request_params["max_tokens"],
                "temperature": request_params["temperature"],
                "has_system_prompt": bool(system_prompt),
                "prompt_length": len(prompt)
            })
            
            # Make the API call with retry logic
            response = await self._make_request_with_retry(client, request_params)
            
            # Extract response content
            content = response.choices[0].message.content if response.choices else ""
            usage_tokens = response.usage.total_tokens if response.usage else None
            
            self.logger.info("OpenAI response generated successfully", extra={
                "model": response.model,
                "usage_tokens": usage_tokens,
                "response_length": len(content),
                "finish_reason": response.choices[0].finish_reason if response.choices else None
            })
            
            return self._create_response(
                content=content,
                usage_tokens=usage_tokens,
                model_used=response.model,
                finish_reason=response.choices[0].finish_reason if response.choices else None,
                usage=response.usage.model_dump() if response.usage else None
            )
            
        except openai.AuthenticationError as e:
            self.logger.error("OpenAI authentication failed", extra={"error": str(e)})
            raise LLMAuthenticationError(f"OpenAI authentication failed: {e}")
        
        except openai.RateLimitError as e:
            self.logger.error("OpenAI rate limit exceeded", extra={"error": str(e)})
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {e}")
        
        except openai.APITimeoutError as e:
            self.logger.error("OpenAI request timed out", extra={"error": str(e)})
            raise LLMTimeoutError(f"OpenAI request timed out: {e}")
        
        except Exception as e:
            self.logger.error("OpenAI request failed", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise LLMProviderError(f"OpenAI request failed: {e}")
    
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
        # Try to use OpenAI's function calling/tools feature if available
        try:
            import openai
            client = openai.AsyncOpenAI(
                api_key=self.config.api_key,
                timeout=self.config.timeout_seconds,
                base_url=self.config.base_url
            )
            
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Create a function definition from the schema
            function_def = {
                "name": "structured_response",
                "description": "Generate a structured response matching the required schema",
                "parameters": schema
            }
            
            request_params = {
                "model": self.config.get_default_model(),
                "messages": messages,
                "tools": [{"type": "function", "function": function_def}],
                "tool_choice": {"type": "function", "function": {"name": "structured_response"}},
                "temperature": kwargs.get("temperature", self.config.temperature)
            }
            
            response = await self._make_request_with_retry(client, request_params)
            
            # Extract structured response from function call
            if response.choices and response.choices[0].message.tool_calls:
                tool_call = response.choices[0].message.tool_calls[0]
                content = tool_call.function.arguments
                
                # Validate JSON
                try:
                    json.loads(content)
                    self.logger.debug("Structured response validated successfully")
                except json.JSONDecodeError:
                    self.logger.warning("Function call returned invalid JSON")
            else:
                # Fallback to regular response
                content = response.choices[0].message.content if response.choices else "{}"
            
            usage_tokens = response.usage.total_tokens if response.usage else None
            
            return self._create_response(
                content=content,
                usage_tokens=usage_tokens,
                model_used=response.model,
                finish_reason=response.choices[0].finish_reason if response.choices else None,
                structured_response=True
            )
            
        except Exception as e:
            self.logger.warning(f"Function calling failed, falling back to prompt-based approach: {e}")
            
            # Fallback to prompt-based structured response
            structured_prompt = f"""
{prompt}

Please respond with a JSON object that matches this exact schema:
{json.dumps(schema, indent=2)}

Important: Return ONLY the JSON object, no additional text or formatting.
"""
            
            enhanced_system = """You are a helpful assistant that always responds with valid JSON matching the requested schema."""
            if system_prompt:
                enhanced_system = f"{system_prompt}\n\n{enhanced_system}"
            
            return await self.generate_response(
                prompt=structured_prompt,
                system_prompt=enhanced_system,
                **kwargs
            )
    
    async def _make_request_with_retry(self, client, request_params: Dict[str, Any]):
        """Make request to OpenAI with retry logic."""
        import openai
        
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                response = await client.chat.completions.create(**request_params)
                return response
                
            except (openai.RateLimitError, openai.APITimeoutError) as e:
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


class AzureOpenAIProvider(OpenAIProvider):
    """Azure OpenAI provider implementation."""
    
    def _validate_config(self) -> None:
        """Validate Azure OpenAI-specific configuration."""
        if not self.config.api_key:
            raise LLMProviderError(
                "Azure OpenAI API key is required. Set MCP_LLM_API_KEY or AZURE_OPENAI_API_KEY environment variable."
            )
        
        if not self.config.azure_endpoint:
            raise LLMProviderError(
                "Azure OpenAI endpoint is required. Set AZURE_OPENAI_ENDPOINT environment variable."
            )
        
        # Set default model if not specified
        if not self.config.model:
            self.config.model = "gpt-4"
        
        self.logger.debug("Azure OpenAI provider configuration validated", extra={
            "model": self.config.model,
            "endpoint": self.config.azure_endpoint[:50] + "..." if len(self.config.azure_endpoint) > 50 else self.config.azure_endpoint,
            "api_version": self.config.azure_api_version,
            "has_api_key": bool(self.config.api_key)
        })
    
    async def _make_request_with_retry(self, client, request_params: Dict[str, Any]):
        """Override to use Azure OpenAI client."""
        try:
            import openai
        except ImportError:
            raise LLMProviderError(
                "openai package is required for Azure OpenAI provider. Install with: pip install openai"
            )
        
        # Initialize Azure OpenAI client
        azure_client = openai.AsyncAzureOpenAI(
            api_key=self.config.api_key,
            azure_endpoint=self.config.azure_endpoint,
            api_version=self.config.azure_api_version,
            timeout=self.config.timeout_seconds
        )
        
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                response = await azure_client.chat.completions.create(**request_params)
                return response
                
            except (openai.RateLimitError, openai.APITimeoutError) as e:
                last_exception = e
                if attempt < self.config.max_retries - 1:
                    wait_time = (2 ** attempt) * 1
                    self.logger.warning(f"Azure OpenAI request failed (attempt {attempt + 1}), retrying in {wait_time}s", extra={
                        "error": str(e),
                        "attempt": attempt + 1,
                        "max_retries": self.config.max_retries
                    })
                    await asyncio.sleep(wait_time)
                else:
                    raise
            
            except Exception as e:
                raise e
        
        if last_exception:
            raise last_exception