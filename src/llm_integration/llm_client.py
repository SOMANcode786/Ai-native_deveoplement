"""
Base LLM client interface and implementations for VLA system
"""
import abc
import asyncio
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class LLMClient(abc.ABC):
    """Abstract base class for LLM clients"""

    @abc.abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a response from the LLM"""
        pass

    @abc.abstractmethod
    async def generate_json_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate a structured JSON response from the LLM"""
        pass


class OpenAILLMClient(LLMClient):
    """OpenAI API implementation of LLM client"""

    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.model = model
        # Import here to avoid dependency issues if not available
        try:
            import openai
            self.openai = openai
            self.openai.api_key = api_key
        except ImportError:
            logger.warning("OpenAI library not found. Install with: pip install openai")
            self.openai = None

    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a text response from OpenAI API"""
        if not self.openai:
            raise ImportError("OpenAI library not installed")

        try:
            response = await self.openai.ChatCompletion.acreate(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            raise

    async def generate_json_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate a structured JSON response from OpenAI API"""
        # Add instruction to return JSON
        json_prompt = f"{prompt}\n\nRespond in valid JSON format."
        response_text = await self.generate_response(json_prompt, **kwargs)

        import json
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response: {response_text}")
            raise


class AnthropicLLMClient(LLMClient):
    """Anthropic API implementation of LLM client"""

    def __init__(self, api_key: str, model: str = "claude-3-opus-20240229"):
        self.api_key = api_key
        self.model = model
        # Import here to avoid dependency issues if not available
        try:
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(api_key=api_key)
        except ImportError:
            logger.warning("Anthropic library not found. Install with: pip install anthropic")
            self.client = None

    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a text response from Anthropic API"""
        if not self.client:
            raise ImportError("Anthropic library not installed")

        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=kwargs.get('max_tokens', 1000),
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            raise

    async def generate_json_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate a structured JSON response from Anthropic API"""
        # Add instruction to return JSON
        json_prompt = f"{prompt}\n\nRespond in valid JSON format."
        response_text = await self.generate_response(json_prompt, **kwargs)

        import json
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response: {response_text}")
            raise


class LocalLLMClient(LLMClient):
    """Local LLM implementation (placeholder for models like Llama)"""

    def __init__(self, model_path: str):
        self.model_path = model_path
        logger.warning("Local LLM implementation is a placeholder. Integration with local models requires additional setup.")

    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Placeholder for local LLM response generation"""
        raise NotImplementedError("Local LLM integration requires additional setup and dependencies")

    async def generate_json_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Placeholder for local LLM JSON response generation"""
        raise NotImplementedError("Local LLM integration requires additional setup and dependencies")


def create_llm_client(provider: str, api_key: str, **kwargs) -> LLMClient:
    """Factory function to create LLM client based on provider"""
    if provider.lower() == "openai":
        return OpenAILLMClient(api_key, **kwargs)
    elif provider.lower() == "anthropic":
        return AnthropicLLMClient(api_key, **kwargs)
    elif provider.lower() == "local":
        model_path = kwargs.get("model_path", "")
        return LocalLLMClient(model_path)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")