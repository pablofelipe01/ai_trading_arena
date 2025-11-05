"""
Mock LLM Client for Testing

Simulates LLM responses without requiring real API keys.
Useful for:
- Testing the trading flow
- Development without API costs
- CI/CD pipelines
- Demonstrations

Usage:
    from models.mock_llm import MockLLMClient

    client = MockLLMClient(strategy="conservative")
    decision = await client.get_trading_decision(prompt)
"""

import asyncio
import json
import random
from typing import Literal

from models.llm_client import BaseLLMClient
from utils.logger import get_logger
from utils.validator import TradingDecision


# ============================================================================
# Mock LLM Client
# ============================================================================


class MockLLMClient(BaseLLMClient):
    """
    Mock LLM client for testing

    Generates realistic trading decisions without calling real APIs.

    Strategies:
    - conservative: Mostly HOLD, occasional small trades
    - aggressive: Frequent trades, larger positions
    - random: Random decisions
    - trend_following: Buys on uptrends, sells on downtrends
    """

    def __init__(
        self,
        model_name: str = "mock-model",
        strategy: Literal["conservative", "aggressive", "random", "trend_following"] = "conservative",
        latency: float = 0.1  # Simulated latency
    ):
        """
        Initialize mock client

        Args:
            model_name: Name for this mock model
            strategy: Trading strategy to simulate
            latency: Simulated API latency in seconds
        """
        # We can't call super().__init__() because it requires config
        self.model_name = model_name
        self.provider = "mock"
        self.strategy = strategy
        self.latency = latency

        # Initialize logger
        self.logger = get_logger(f"llm.{model_name}")

        # Track calls for simulation
        self.call_count = 0
        self.last_action = "HOLD"

        # Rate limiting (fake)
        self.rate_limit_calls = []
        self.max_rpm = 60
        self.max_retries = 3
        self.retry_delay = 1.0
        self.timeout = 30.0

    async def _call_api(self, prompt: str) -> str:
        """
        Simulate API call

        Args:
            prompt: Trading prompt

        Returns:
            Mock JSON response
        """
        # Simulate latency
        await asyncio.sleep(self.latency)

        self.call_count += 1

        # Generate decision based on strategy
        if self.strategy == "conservative":
            decision = self._conservative_strategy()
        elif self.strategy == "aggressive":
            decision = self._aggressive_strategy()
        elif self.strategy == "trend_following":
            decision = self._trend_following_strategy(prompt)
        else:  # random
            decision = self._random_strategy()

        return json.dumps(decision)

    def _conservative_strategy(self) -> dict:
        """
        Conservative strategy: Mostly hold, occasional small trades
        """
        # 70% HOLD, 20% BUY, 10% SELL
        action = random.choices(
            ["HOLD", "BUY", "SELL"],
            weights=[0.7, 0.2, 0.1]
        )[0]

        self.last_action = action

        return {
            "action": action,
            "confidence": random.uniform(0.5, 0.7),
            "reasoning": f"Conservative strategy: {action} with low risk",
            "position_size": random.uniform(0.1, 0.3) if action != "HOLD" else 0.0,
            "stop_loss": None,
            "take_profit": None
        }

    def _aggressive_strategy(self) -> dict:
        """
        Aggressive strategy: Frequent trades, larger positions
        """
        # 30% HOLD, 40% BUY, 30% SELL
        action = random.choices(
            ["HOLD", "BUY", "SELL"],
            weights=[0.3, 0.4, 0.3]
        )[0]

        self.last_action = action

        return {
            "action": action,
            "confidence": random.uniform(0.7, 0.9),
            "reasoning": f"Aggressive strategy: {action} with high conviction",
            "position_size": random.uniform(0.4, 0.8) if action != "HOLD" else 0.0,
            "stop_loss": None,
            "take_profit": None
        }

    def _random_strategy(self) -> dict:
        """
        Random strategy: Equal probability for all actions
        """
        action = random.choice(["HOLD", "BUY", "SELL"])
        self.last_action = action

        return {
            "action": action,
            "confidence": random.uniform(0.3, 0.9),
            "reasoning": f"Random strategy: {action}",
            "position_size": random.uniform(0.2, 0.6) if action != "HOLD" else 0.0,
            "stop_loss": None,
            "take_profit": None
        }

    def _trend_following_strategy(self, prompt: str) -> dict:
        """
        Trend following: Try to detect trend from prompt
        """
        # Simple heuristic: look for price data in prompt
        # This is very basic - just for simulation

        # Alternate between buy and sell to simulate trend following
        if self.call_count % 3 == 0:
            action = "BUY"
        elif self.call_count % 3 == 1:
            action = "HOLD"
        else:
            action = "SELL"

        self.last_action = action

        return {
            "action": action,
            "confidence": random.uniform(0.6, 0.8),
            "reasoning": f"Trend following: {action} based on market analysis",
            "position_size": random.uniform(0.3, 0.5) if action != "HOLD" else 0.0,
            "stop_loss": None,
            "take_profit": None
        }


# ============================================================================
# Mock Client Factory
# ============================================================================


def create_mock_clients() -> dict:
    """
    Create a set of mock clients with different strategies

    Returns:
        Dict of provider → mock client
    """
    return {
        "deepseek": MockLLMClient(
            model_name="mock-deepseek",
            strategy="conservative",
            latency=0.15
        ),
        "groq": MockLLMClient(
            model_name="mock-groq",
            strategy="aggressive",
            latency=0.08
        ),
        "openai": MockLLMClient(
            model_name="mock-openai",
            strategy="trend_following",
            latency=0.12
        ),
        "anthropic": MockLLMClient(
            model_name="mock-anthropic",
            strategy="random",
            latency=0.10
        ),
    }
