"""
LLM Client System for AI Trading Arena

Provides unified interface for multiple LLM providers:
- DeepSeek (winner of nof1.ai with +11.06%)
- OpenAI GPT-4
- Anthropic Claude
- Groq (Llama)

Each client handles:
- API communication
- Response parsing
- Error handling
- Rate limiting
- Retries

Usage:
    from models.llm_client import DeepSeekClient

    client = DeepSeekClient()
    decision = await client.get_trading_decision(prompt)
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx
from anthropic import AsyncAnthropic
from groq import AsyncGroq
from openai import AsyncOpenAI

from utils.config import get_config
from utils.errors import (
    LLMAPIError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from utils.logger import get_logger, log_decision
from utils.validator import validate_and_sanitize_llm_response, TradingDecision


logger = get_logger(__name__)


# ============================================================================
# Base LLM Client
# ============================================================================


class BaseLLMClient(ABC):
    """
    Base class for all LLM clients

    All provider-specific clients inherit from this class.
    """

    def __init__(self, model_name: str, provider: str):
        """
        Initialize LLM client

        Args:
            model_name: Name of the model (e.g., "deepseek-chat")
            provider: Provider name (e.g., "deepseek")
        """
        self.model_name = model_name
        self.provider = provider
        self.config = get_config()
        self.logger = get_logger(f"llm.{provider}")

        # Get model config
        self.model_config = getattr(self.config.models, provider, None)
        if not self.model_config:
            raise ValueError(f"Model config not found for {provider}")

        # Rate limiting
        self.rate_limit_calls: list[float] = []
        self.max_rpm = self.model_config.parameters.max_requests_per_minute

        # Retry settings
        self.max_retries = self.model_config.parameters.max_retries
        self.retry_delay = self.model_config.parameters.retry_delay

        # Timeout (prefer API timeout if set, otherwise use parameters)
        self.timeout = self.model_config.api.timeout if self.model_config.api else self.model_config.parameters.timeout

        self.logger.info(
            "LLM client initialized",
            model=model_name,
            provider=provider,
            max_rpm=self.max_rpm
        )

    @abstractmethod
    async def _call_api(self, prompt: str) -> str:
        """
        Call the LLM API

        Must be implemented by each provider.

        Args:
            prompt: The trading prompt

        Returns:
            Raw response string
        """
        pass

    async def get_trading_decision(
        self,
        prompt: str,
        symbol: str = "BTC/USDT",
        current_price: float = 0.0
    ) -> TradingDecision:
        """
        Get trading decision from LLM

        Handles:
        - Rate limiting
        - Retries
        - Response validation
        - Error handling

        Args:
            prompt: Trading prompt
            symbol: Trading symbol
            current_price: Current market price

        Returns:
            Validated TradingDecision object

        Raises:
            LLMAPIError: API call failed
            LLMResponseError: Invalid response
        """
        self.logger.info(
            "Requesting trading decision",
            model=self.model_name,
            prompt_length=len(prompt)
        )

        start_time = time.time()

        # Rate limiting
        await self._rate_limit()

        # Retry loop
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Call API
                response = await self._call_api(prompt)

                # Validate and parse response (with sanitization for markdown/text wrapping)
                decision = validate_and_sanitize_llm_response(response, self.model_name)

                # Calculate latency
                latency = time.time() - start_time

                # Log decision
                log_decision(
                    model=self.model_name,
                    symbol=symbol,
                    action=decision.action,
                    confidence=decision.confidence,
                    reasoning=decision.reasoning,
                    indicators={},  # Indicators not available at decision time
                    position_size=decision.position_size,
                    price=current_price,
                    latency=latency
                )

                self.logger.info(
                    "Trading decision received",
                    model=self.model_name,
                    action=decision.action,
                    confidence=decision.confidence,
                    latency=latency,
                    attempt=attempt + 1
                )

                return decision

            except (LLMRateLimitError, LLMTimeoutError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(
                        "Retrying after error",
                        model=self.model_name,
                        error=str(e),
                        attempt=attempt + 1,
                        wait_seconds=wait_time
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(
                        "Max retries reached",
                        model=self.model_name,
                        error=str(e)
                    )

            except Exception as e:
                self.logger.error(
                    "Unexpected error getting decision",
                    model=self.model_name,
                    error=str(e),
                    exc_info=True
                )
                last_error = e
                break

        # All retries failed
        raise LLMAPIError(
            model=self.model_name,
            reason=f"Failed after {self.max_retries} attempts: {str(last_error)}"
        )

    async def _rate_limit(self):
        """Apply rate limiting"""
        now = time.time()

        # Remove old calls outside the window
        self.rate_limit_calls = [
            call_time for call_time in self.rate_limit_calls
            if now - call_time < 60.0
        ]

        # Check if at limit
        if len(self.rate_limit_calls) >= self.max_rpm:
            oldest_call = self.rate_limit_calls[0]
            wait_time = 60.0 - (now - oldest_call)

            if wait_time > 0:
                self.logger.warning(
                    "Rate limit reached, waiting",
                    model=self.model_name,
                    wait_seconds=wait_time
                )
                await asyncio.sleep(wait_time)

        # Record this call
        self.rate_limit_calls.append(time.time())


# ============================================================================
# DeepSeek Client (The Winner!)
# ============================================================================


class DeepSeekClient(BaseLLMClient):
    """
    DeepSeek client

    This model won nof1.ai competition with +11.06% returns.
    Priority: 1 (highest)
    """

    def __init__(self):
        super().__init__(
            model_name="deepseek-chat",
            provider="deepseek"
        )

        # Initialize OpenAI-compatible client
        self.client = AsyncOpenAI(
            api_key=self.config.get_api_key("deepseek"),
            base_url=self.model_config.api.base_url
        )

    async def _call_api(self, prompt: str) -> str:
        """Call DeepSeek API"""
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert cryptocurrency trader. Analyze the market data and respond with ONLY a valid JSON object. Do not include any explanatory text before or after the JSON. The JSON must follow this exact format: {\"action\": \"BUY|SELL|HOLD\", \"confidence\": 0.0-1.0, \"reasoning\": \"explanation\", \"position_size\": 0.0-1.0}"
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=self.model_config.parameters.temperature,
                    max_tokens=self.model_config.parameters.max_tokens,
                    response_format={"type": "json_object"}  # DeepSeek supports JSON mode
                ),
                timeout=self.timeout
            )

            return response.choices[0].message.content

        except asyncio.TimeoutError:
            raise LLMTimeoutError(
                f"DeepSeek API timeout after {self.timeout}s",
                model=self.model_name
            )
        except Exception as e:
            if "rate_limit" in str(e).lower():
                raise LLMRateLimitError(
                    f"DeepSeek rate limit exceeded",
                    model=self.model_name
                )
            raise LLMAPIError(
                model=self.model_name,
                reason=f"DeepSeek API error: {str(e)}"
            )


# ============================================================================
# OpenAI Client (GPT-4)
# ============================================================================


class OpenAIClient(BaseLLMClient):
    """
    OpenAI GPT-4 client

    Priority: 3
    """

    def __init__(self):
        super().__init__(
            model_name="gpt-4o",
            provider="openai"
        )

        self.client = AsyncOpenAI(
            api_key=self.config.get_api_key("openai")
        )

    async def _call_api(self, prompt: str) -> str:
        """Call OpenAI API"""
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert cryptocurrency trader. Analyze the market data and respond with ONLY a valid JSON object. Do not include any explanatory text before or after the JSON. The JSON must follow this exact format: {\"action\": \"BUY|SELL|HOLD\", \"confidence\": 0.0-1.0, \"reasoning\": \"explanation\", \"position_size\": 0.0-1.0}"
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=self.model_config.parameters.temperature,
                    max_tokens=self.model_config.parameters.max_tokens,
                    response_format={"type": "json_object"}  # GPT-4 JSON mode
                ),
                timeout=self.timeout
            )

            return response.choices[0].message.content

        except asyncio.TimeoutError:
            raise LLMTimeoutError(
                f"OpenAI API timeout after {self.timeout}s",
                model=self.model_name
            )
        except Exception as e:
            if "rate_limit" in str(e).lower():
                raise LLMRateLimitError(
                    f"OpenAI rate limit exceeded",
                    model=self.model_name
                )
            raise LLMAPIError(
                model=self.model_name,
                reason=f"OpenAI API error: {str(e)}"
            )


# ============================================================================
# Anthropic Client (Claude)
# ============================================================================


class AnthropicClient(BaseLLMClient):
    """
    Anthropic Claude client

    Priority: 4
    """

    def __init__(self):
        super().__init__(
            model_name="claude-sonnet-4-5-20250929",
            provider="anthropic"
        )

        self.client = AsyncAnthropic(
            api_key=self.config.get_api_key("anthropic")
        )

    async def _call_api(self, prompt: str) -> str:
        """Call Anthropic API"""
        try:
            response = await asyncio.wait_for(
                self.client.messages.create(
                    model=self.model_name,
                    max_tokens=self.model_config.parameters.max_tokens,
                    temperature=self.model_config.parameters.temperature,
                    system="You are an expert cryptocurrency trader. You MUST respond with ONLY a valid JSON object, nothing else. Do not include any explanatory text, markdown formatting, or code blocks. Just the raw JSON object. The JSON must follow this exact format: {\"action\": \"BUY\" or \"SELL\" or \"HOLD\", \"confidence\": number between 0.0 and 1.0, \"reasoning\": \"your explanation as a string\", \"position_size\": number between 0.0 and 1.0}",
                    messages=[
                        {
                            "role": "user",
                            "content": prompt + "\n\nRemember: Respond with ONLY valid JSON, no other text or formatting."
                        }
                    ]
                ),
                timeout=self.timeout
            )

            return response.content[0].text

        except asyncio.TimeoutError:
            raise LLMTimeoutError(
                f"Anthropic API timeout after {self.timeout}s",
                model=self.model_name
            )
        except Exception as e:
            if "rate_limit" in str(e).lower():
                raise LLMRateLimitError(
                    f"Anthropic rate limit exceeded",
                    model=self.model_name
                )
            raise LLMAPIError(
                model=self.model_name,
                reason=f"Anthropic API error: {str(e)}"
            )


# ============================================================================
# Groq Client (Llama)
# ============================================================================


class GroqClient(BaseLLMClient):
    """
    Groq Llama client

    Priority: 2
    """

    def __init__(self):
        super().__init__(
            model_name="llama-3.3-70b-versatile",
            provider="groq"
        )

        self.client = AsyncGroq(
            api_key=self.config.get_api_key("groq")
        )

    async def _call_api(self, prompt: str) -> str:
        """Call Groq API"""
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert cryptocurrency trader. Analyze the market data and respond with ONLY a valid JSON object. Do not include any explanatory text before or after the JSON. The JSON must follow this exact format: {\"action\": \"BUY|SELL|HOLD\", \"confidence\": 0.0-1.0, \"reasoning\": \"explanation\", \"position_size\": 0.0-1.0}"
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=self.model_config.parameters.temperature,
                    max_tokens=self.model_config.parameters.max_tokens,
                    response_format={"type": "json_object"}  # Groq JSON mode
                ),
                timeout=self.timeout
            )

            return response.choices[0].message.content

        except asyncio.TimeoutError:
            raise LLMTimeoutError(
                f"Groq API timeout after {self.timeout}s",
                model=self.model_name
            )
        except Exception as e:
            if "rate_limit" in str(e).lower():
                raise LLMRateLimitError(
                    f"Groq rate limit exceeded",
                    model=self.model_name
                )
            raise LLMAPIError(
                model=self.model_name,
                reason=f"Groq API error: {str(e)}"
            )


# ============================================================================
# Client Factory
# ============================================================================


def create_llm_client(provider: str) -> BaseLLMClient:
    """
    Create LLM client for a provider

    Args:
        provider: Provider name (deepseek, openai, anthropic, groq)

    Returns:
        LLM client instance
    """
    clients = {
        "deepseek": DeepSeekClient,
        "openai": OpenAIClient,
        "anthropic": AnthropicClient,
        "groq": GroqClient,
    }

    if provider not in clients:
        raise ValueError(f"Unknown provider: {provider}")

    return clients[provider]()
