"""
Test Utilities for AI Trading Arena

Provides helper functions and fixtures for testing.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, AsyncMock

from models.llm_client import BaseLLMClient
from utils.validator import TradingDecision


# ============================================================================
# Mock LLM Client
# ============================================================================


class MockLLMClient(BaseLLMClient):
    """
    Mock LLM client for testing

    Allows controlling responses and simulating errors.
    """

    def __init__(
        self,
        provider: str = "mock",
        responses: Optional[List[TradingDecision]] = None,
        fail_count: int = 0,
        delay_seconds: float = 0.0
    ):
        """
        Initialize mock client

        Args:
            provider: Provider name
            responses: List of pre-defined responses (cycles through)
            fail_count: Number of times to fail before succeeding
            delay_seconds: Artificial delay to simulate API latency
        """
        self.provider = provider
        self.model_name = f"mock-{provider}"
        self.responses = responses or [
            TradingDecision(
                action="HOLD",
                confidence=0.5,
                reasoning="Mock decision",
                position_size=0.0
            )
        ]
        self.call_count = 0
        self.fail_count = fail_count
        self.delay_seconds = delay_seconds
        self.config = Mock()

    async def _call_api(self, prompt: str) -> str:
        """Mock API call"""
        await asyncio.sleep(self.delay_seconds)

        # Simulate failures
        if self.call_count < self.fail_count:
            self.call_count += 1
            raise Exception(f"Mock API failure {self.call_count}/{self.fail_count}")

        # Return pre-defined response
        response_idx = self.call_count % len(self.responses)
        decision = self.responses[response_idx]

        self.call_count += 1

        return json.dumps({
            "action": decision.action,
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
            "position_size": decision.position_size
        })


# ============================================================================
# Mock Data Fetcher
# ============================================================================


class MockDataFetcher:
    """Mock data fetcher for testing"""

    def __init__(self, price: float = 100000.0):
        """Initialize with a base price"""
        self.price = price
        self.call_count = 0

    async def fetch_multi_timeframe(
        self,
        symbol: str,
        timeframes: List[str],
        lookback: int,
        use_cache: bool = True
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Generate mock market data"""
        self.call_count += 1

        data = {}
        for tf in timeframes:
            candles = []
            for i in range(lookback):
                # Generate simple trending data
                price = self.price + (i * 10)
                candles.append({
                    "timestamp": datetime.now(),
                    "open": price,
                    "high": price + 5,
                    "low": price - 5,
                    "close": price,
                    "volume": 1000.0
                })
            data[tf] = candles

        return data

    async def close(self):
        """Mock close"""
        pass


# ============================================================================
# Test Fixtures
# ============================================================================


def create_mock_market_data(
    timeframes: List[str] = ["1m", "3m", "15m"],
    lookback: int = 100,
    base_price: float = 100000.0
) -> Dict[str, List[Dict[str, Any]]]:
    """Create mock market data for testing"""
    data = {}

    for tf in timeframes:
        candles = []
        for i in range(lookback):
            price = base_price + (i * 10)
            candles.append({
                "timestamp": datetime.now(),
                "open": price,
                "high": price + 50,
                "low": price - 50,
                "close": price,
                "volume": 1000.0
            })
        data[tf] = candles

    return data


def create_mock_trading_decision(
    action: str = "HOLD",
    confidence: float = 0.5,
    reasoning: str = "Test decision",
    position_size: float = 0.0
) -> TradingDecision:
    """Create a mock trading decision"""
    return TradingDecision(
        action=action,
        confidence=confidence,
        reasoning=reasoning,
        position_size=position_size
    )


def load_test_results(session_id: str) -> Optional[Dict[str, Any]]:
    """Load test results from file"""
    results_path = Path("data/results") / f"session_{session_id}.json"

    if not results_path.exists():
        return None

    with open(results_path, "r") as f:
        return json.load(f)


# ============================================================================
# Performance Monitoring
# ============================================================================


class PerformanceMonitor:
    """Monitor performance metrics during tests"""

    def __init__(self):
        """Initialize performance monitor"""
        self.start_time = None
        self.end_time = None
        self.metrics = {
            "api_calls": 0,
            "trades_executed": 0,
            "errors": 0,
            "latencies": []
        }

    def start(self):
        """Start monitoring"""
        self.start_time = time.time()

    def stop(self):
        """Stop monitoring"""
        self.end_time = time.time()

    def record_api_call(self, latency: float):
        """Record an API call"""
        self.metrics["api_calls"] += 1
        self.metrics["latencies"].append(latency)

    def record_trade(self):
        """Record a trade execution"""
        self.metrics["trades_executed"] += 1

    def record_error(self):
        """Record an error"""
        self.metrics["errors"] += 1

    def get_report(self) -> Dict[str, Any]:
        """Get performance report"""
        duration = (self.end_time or time.time()) - (self.start_time or time.time())
        latencies = self.metrics["latencies"]

        return {
            "duration_seconds": duration,
            "api_calls": self.metrics["api_calls"],
            "trades_executed": self.metrics["trades_executed"],
            "errors": self.metrics["errors"],
            "calls_per_second": self.metrics["api_calls"] / duration if duration > 0 else 0,
            "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
            "min_latency": min(latencies) if latencies else 0,
            "max_latency": max(latencies) if latencies else 0,
            "error_rate": self.metrics["errors"] / self.metrics["api_calls"]
                if self.metrics["api_calls"] > 0 else 0
        }


# ============================================================================
# Test Validators
# ============================================================================


def assert_valid_leaderboard(leaderboard: List[Dict[str, Any]]):
    """Assert leaderboard is valid"""
    assert len(leaderboard) > 0, "Leaderboard is empty"

    # Check sorted by return
    returns = [model["return_pct"] for model in leaderboard]
    assert returns == sorted(returns, reverse=True), "Leaderboard not sorted correctly"

    # Check required fields
    required_fields = ["provider", "return_pct", "account_value", "total_trades", "win_rate"]
    for model in leaderboard:
        for field in required_fields:
            assert field in model, f"Missing field: {field}"


def assert_valid_session_results(results: Dict[str, Any]):
    """Assert session results are valid"""
    required_fields = [
        "session_id",
        "session_start",
        "session_end",
        "symbol",
        "total_rounds",
        "final_leaderboard",
        "round_results"
    ]

    for field in required_fields:
        assert field in results, f"Missing field: {field}"

    assert results["total_rounds"] > 0, "No rounds completed"
    assert len(results["final_leaderboard"]) > 0, "Empty leaderboard"
    assert len(results["round_results"]) > 0, "No round results"


def assert_trading_decision_valid(decision: TradingDecision):
    """Assert trading decision is valid"""
    assert decision.action in ["BUY", "SELL", "HOLD"], f"Invalid action: {decision.action}"
    assert 0.0 <= decision.confidence <= 1.0, f"Invalid confidence: {decision.confidence}"
    assert len(decision.reasoning) >= 10, "Reasoning too short"
    assert 0.0 <= decision.position_size <= 1.0, f"Invalid position size: {decision.position_size}"


# ============================================================================
# Async Test Helpers
# ============================================================================


def run_async_test(coro):
    """Run an async test"""
    return asyncio.run(coro)


async def wait_for_condition(
    condition_func,
    timeout: float = 10.0,
    check_interval: float = 0.1
) -> bool:
    """Wait for a condition to become true"""
    start_time = time.time()

    while time.time() - start_time < timeout:
        if condition_func():
            return True
        await asyncio.sleep(check_interval)

    return False
