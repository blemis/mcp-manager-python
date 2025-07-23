"""
Ollama LLM provider implementation.

Integrates with Ollama for local LLM execution supporting various models
like Llama 2, Code Llama, Mistral, and other open-source models.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

import aiohttp

from mcp_manager.ai.llm_providers import (
    BaseLLMProvider,
    LLMProviderError,
    LLMResponse,
    LLMTimeoutError,
)


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider implementation."""
    
    def _validate_config(self) -> None:
        """Validate Ollama-specific configuration."""
        # Set default base URL if not specified
        if not self.config.base_url:
            self.config.base_url = "http://localhost:11434"
        
        # Set default model if not specified
        if not self.config.model:
            self.config.model = "llama2"
        
        self.logger.debug("Ollama provider configuration validated", extra={
            "model": self.config.model,
            "base_url": self.config.base_url,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature
        })
    
    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None,
                              **kwargs) -> LLMResponse:
        """
        Generate a response using Ollama.
        
        Args:
            prompt: User prompt/query
            system_prompt: Optional system prompt for context
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            LLMResponse with Ollama's generated content
        """
        try:
            # Prepare the request payload
            payload = {
                "model": self.config.get_default_model(),
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", self.config.temperature),
                    "num_predict": kwargs.get("max_tokens", self.config.max_tokens)
                }
            }
            
            # Add system prompt if provided
            if system_prompt:
                payload["system"] = system_prompt
            
            self.logger.debug("Sending request to Ollama", extra={
                "model": payload["model"],
                "base_url": self.config.base_url,
                "temperature": payload["options"]["temperature"],
                "max_tokens": payload["options"]["num_predict"],
                "has_system_prompt": bool(system_prompt),
                "prompt_length": len(prompt)
            })
            
            # Make the API call with retry logic
            response_data = await self._make_request_with_retry(payload)
            
            # Extract response content
            content = response_data.get("response", "")
            model_used = response_data.get("model", self.config.get_default_model())
            
            # Calculate approximate token usage (Ollama doesn't provide this directly)
            usage_tokens = self._estimate_token_usage(prompt, content, system_prompt)
            
            self.logger.info("Ollama response generated successfully", extra={
                "model": model_used,
                "estimated_tokens": usage_tokens,
                "response_length": len(content),
                "done": response_data.get("done", False)
            })
            
            return self._create_response(
                content=content,
                usage_tokens=usage_tokens,
                model_used=model_used,
                done=response_data.get("done", False),
                eval_duration=response_data.get("eval_duration"),
                prompt_eval_duration=response_data.get("prompt_eval_duration")
            )
            
        except asyncio.TimeoutError as e:
            self.logger.error("Ollama request timed out", extra={"error": str(e)})
            raise LLMTimeoutError(f"Ollama request timed out: {e}")
        
        except Exception as e:
            self.logger.error("Ollama request failed", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise LLMProviderError(f"Ollama request failed: {e}")
    
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
        enhanced_system = """You are a helpful assistant that always responds with valid JSON matching the requested schema. Do not include any additional text, explanations, or formatting - only the JSON object."""
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
            # Try to extract JSON from the response if it's wrapped in text
            response.content = self._extract_json_from_response(response.content)
        
        return response
    
    async def _make_request_with_retry(self, payload: Dict[str, Any]):
        """Make request to Ollama with retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        f"{self.config.base_url}/api/generate",
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            raise LLMProviderError(f"Ollama API error {response.status}: {error_text}")
                            
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
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
    
    def _estimate_token_usage(self, prompt: str, response: str, system_prompt: Optional[str] = None) -> int:
        """
        Estimate token usage since Ollama doesn't provide exact counts.
        
        Uses a rough approximation of 4 characters per token.
        """
        total_chars = len(prompt) + len(response)
        if system_prompt:
            total_chars += len(system_prompt)
        
        # Rough approximation: 4 characters per token
        return int(total_chars / 4)
    
    def _extract_json_from_response(self, content: str) -> str:
        """
        Attempt to extract JSON from a response that may contain additional text.
        """
        # Look for JSON object boundaries
        start_idx = content.find('{')
        if start_idx == -1:
            return content  # No JSON found, return as-is
        
        # Find the matching closing brace
        brace_count = 0
        end_idx = start_idx
        
        for i, char in enumerate(content[start_idx:], start_idx):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        extracted = content[start_idx:end_idx]
        
        # Validate the extracted JSON
        try:
            json.loads(extracted)
            self.logger.debug("Successfully extracted JSON from response")
            return extracted
        except json.JSONDecodeError:
            self.logger.warning("Failed to extract valid JSON from response")
            return content  # Return original if extraction failed
    
    async def check_health(self) -> bool:
        """
        Check if Ollama is running and accessible.
        
        Returns:
            True if Ollama is healthy, False otherwise
        """
        try:
            timeout = aiohttp.ClientTimeout(total=5)  # Short timeout for health check
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.config.base_url}/api/tags") as response:
                    return response.status == 200
        except Exception as e:
            self.logger.warning(f"Ollama health check failed: {e}")
            return False
    
    async def list_models(self) -> List[str]:
        """
        List available models in Ollama.
        
        Returns:
            List of model names
        """
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.config.base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        return [model["name"] for model in data.get("models", [])]
                    else:
                        return []
        except Exception as e:
            self.logger.error(f"Failed to list Ollama models: {e}")
            return []