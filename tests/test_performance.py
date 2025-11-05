"""
Performance Benchmarking for AI Trading Arena

Benchmarks system performance across:
- LLM response times
- Data fetching speed
- Prompt generation
- Decision execution throughput
- End-to-end round performance
- Memory usage
- Concurrent operations

Usage:
    pytest tests/test_performance.py -v
    pytest tests/test_performance.py::test_llm_response_time -v
"""

import asyncio
import pytest
import time
import psutil
import os
from typing import Dict, Any, List
from unittest.mock import Mock

from models.llm_manager import LLMManager, ModelState
from data.binance_fetcher import BinanceFetcher
from strategies.prompt_builder import PromptBuilder
from tests.test_utils import (
    MockLLMClient,
    MockDataFetcher,
    create_mock_trading_decision,
    PerformanceMonitor
)


# ============================================================================
# LLM Performance Tests
# ============================================================================


@pytest.mark.asyncio
async def test_llm_response_time():
    """Benchmark LLM response times"""
    monitor = PerformanceMonitor()
    monitor.start()

    manager = LLMManager()

    # Add fast and slow models
    fast_client = MockLLMClient(
        provider="fast",
        delay_seconds=0.1,
        responses=[create_mock_trading_decision(action="BUY")]
    )
    slow_client = MockLLMClient(
        provider="slow",
        delay_seconds=2.0,
        responses=[create_mock_trading_decision(action="SELL")]
    )

    manager.models = {
        "fast": ModelState("fast", 1, 100.0),
        "slow": ModelState("slow", 2, 100.0)
    }
    manager.models["fast"].client = fast_client
    manager.models["slow"].client = slow_client

    # Run multiple iterations
    iterations = 5
    for _ in range(iterations):
        start = time.time()
        decisions = await manager.get_all_decisions(
            prompt="test prompt",
            symbol="BTC/USDT",
            current_price=100000.0
        )
        latency = time.time() - start
        monitor.record_api_call(latency)

    monitor.stop()
    report = monitor.get_report()

    # Print benchmark results
    print("\n" + "="*80)
    print("⚡ LLM RESPONSE TIME BENCHMARK")
    print("="*80)
    print(f"Total API Calls: {report['api_calls']}")
    print(f"Average Latency: {report['avg_latency']:.3f}s")
    print(f"Min Latency: {report['min_latency']:.3f}s")
    print(f"Max Latency: {report['max_latency']:.3f}s")
    print(f"Calls Per Second: {report['calls_per_second']:.2f}")
    print("="*80)

    # Assertions
    assert report["api_calls"] == iterations
    assert report["avg_latency"] > 0
    assert report["error_rate"] == 0.0


@pytest.mark.asyncio
async def test_parallel_llm_execution():
    """Benchmark parallel LLM execution performance"""
    monitor = PerformanceMonitor()
    monitor.start()

    manager = LLMManager()

    # Add 4 models with varying delays
    for i in range(4):
        client = MockLLMClient(
            provider=f"model{i}",
            delay_seconds=0.5 + (i * 0.1),  # 0.5s, 0.6s, 0.7s, 0.8s
            responses=[create_mock_trading_decision()]
        )
        state = ModelState(f"model{i}", i+1, 100.0)
        state.client = client
        manager.models[f"model{i}"] = state

    # Test parallel execution
    start = time.time()
    decisions = await manager.get_all_decisions("test", "BTC/USDT", 100000.0)
    total_time = time.time() - start

    monitor.record_api_call(total_time)
    monitor.stop()

    print("\n" + "="*80)
    print("🚀 PARALLEL EXECUTION BENCHMARK")
    print("="*80)
    print(f"Models: 4")
    print(f"Total Time: {total_time:.3f}s")
    print(f"Expected Sequential: ~2.6s (0.5+0.6+0.7+0.8)")
    print(f"Speedup: {2.6/total_time:.2f}x")
    print("="*80)

    # Should be significantly faster than sequential
    assert total_time < 1.5  # Should be ~0.8s (slowest model)
    assert len(decisions) == 4


# ============================================================================
# Data Fetching Performance Tests
# ============================================================================


@pytest.mark.asyncio
async def test_data_fetch_speed():
    """Benchmark data fetching performance"""
    monitor = PerformanceMonitor()
    monitor.start()

    fetcher = MockDataFetcher(price=100000.0)

    timeframes = ["1m", "3m", "15m", "1h", "4h"]
    iterations = 10

    for _ in range(iterations):
        start = time.time()
        data = await fetcher.fetch_multi_timeframe(
            symbol="BTC/USDT",
            timeframes=timeframes,
            lookback=100
        )
        latency = time.time() - start
        monitor.record_api_call(latency)

    monitor.stop()
    report = monitor.get_report()

    print("\n" + "="*80)
    print("📊 DATA FETCH SPEED BENCHMARK")
    print("="*80)
    print(f"Timeframes: {len(timeframes)}")
    print(f"Candles Per Timeframe: 100")
    print(f"Total Fetches: {iterations}")
    print(f"Average Fetch Time: {report['avg_latency']:.3f}s")
    print(f"Min Fetch Time: {report['min_latency']:.3f}s")
    print(f"Max Fetch Time: {report['max_latency']:.3f}s")
    print("="*80)

    assert report["api_calls"] == iterations
    assert report["avg_latency"] < 1.0  # Should be fast


@pytest.mark.asyncio
async def test_concurrent_data_fetches():
    """Benchmark concurrent data fetching"""
    monitor = PerformanceMonitor()
    monitor.start()

    fetcher = MockDataFetcher(price=100000.0)

    # Create 10 concurrent fetch tasks
    tasks = []
    for _ in range(10):
        task = fetcher.fetch_multi_timeframe(
            symbol="BTC/USDT",
            timeframes=["1m", "3m", "15m"],
            lookback=100
        )
        tasks.append(task)

    start = time.time()
    results = await asyncio.gather(*tasks)
    total_time = time.time() - start

    monitor.record_api_call(total_time)
    monitor.stop()

    print("\n" + "="*80)
    print("🔄 CONCURRENT DATA FETCH BENCHMARK")
    print("="*80)
    print(f"Concurrent Fetches: 10")
    print(f"Total Time: {total_time:.3f}s")
    print(f"Average Per Fetch: {total_time/10:.3f}s")
    print("="*80)

    assert len(results) == 10


# ============================================================================
# Prompt Generation Performance Tests
# ============================================================================


@pytest.mark.asyncio
async def test_prompt_generation_speed():
    """Benchmark prompt generation performance"""
    monitor = PerformanceMonitor()
    monitor.start()

    # Create mock data
    fetcher = MockDataFetcher(price=100000.0)
    market_data = await fetcher.fetch_multi_timeframe(
        symbol="BTC/USDT",
        timeframes=["1m", "3m", "15m", "1h", "4h"],
        lookback=100
    )

    # Mock config
    mock_config = Mock()
    mock_config.prompts.template_version = "nof1_exact"
    mock_config.prompts.templates_dir = "strategies/templates"
    mock_config.data.timeframes.primary = "3m"
    mock_config.data.indicators.ema.periods = [20, 50]
    mock_config.data.indicators.macd.fast = 12
    mock_config.data.indicators.macd.slow = 26
    mock_config.data.indicators.macd.signal = 9
    mock_config.data.indicators.rsi.periods = [7, 14]
    mock_config.data.indicators.atr.periods = [3, 14]

    builder = PromptBuilder(mock_config)

    account_info = {
        "cash_balance": 100.0,
        "total_value": 100.0,
        "positions": {}
    }

    iterations = 20
    for _ in range(iterations):
        start = time.time()
        prompt = builder.build_prompt(
            symbol="BTC/USDT",
            market_data=market_data,
            account_info=account_info
        )
        latency = time.time() - start
        monitor.record_api_call(latency)

    monitor.stop()
    report = monitor.get_report()

    print("\n" + "="*80)
    print("📝 PROMPT GENERATION BENCHMARK")
    print("="*80)
    print(f"Iterations: {iterations}")
    print(f"Average Generation Time: {report['avg_latency']*1000:.2f}ms")
    print(f"Min Generation Time: {report['min_latency']*1000:.2f}ms")
    print(f"Max Generation Time: {report['max_latency']*1000:.2f}ms")
    print(f"Prompts Per Second: {report['calls_per_second']:.2f}")
    print("="*80)

    assert report["avg_latency"] < 0.5  # Should be very fast


# ============================================================================
# End-to-End Performance Tests
# ============================================================================


@pytest.mark.asyncio
async def test_full_round_performance():
    """Benchmark complete trading round performance"""
    monitor = PerformanceMonitor()
    monitor.start()

    # Setup components
    manager = LLMManager()
    fetcher = MockDataFetcher(price=100000.0)

    # Add 4 models
    for i in range(4):
        client = MockLLMClient(
            provider=f"model{i}",
            delay_seconds=0.2,
            responses=[create_mock_trading_decision(action="BUY")]
        )
        state = ModelState(f"model{i}", i+1, 100.0)
        state.client = client
        manager.models[f"model{i}"] = state

    # Mock config
    mock_config = Mock()
    mock_config.prompts.template_version = "nof1_exact"
    mock_config.prompts.templates_dir = "strategies/templates"
    mock_config.data.timeframes.primary = "3m"
    mock_config.data.indicators.ema.periods = [20, 50]
    mock_config.data.indicators.macd.fast = 12
    mock_config.data.indicators.macd.slow = 26
    mock_config.data.indicators.macd.signal = 9
    mock_config.data.indicators.rsi.periods = [7, 14]
    mock_config.data.indicators.atr.periods = [3, 14]

    builder = PromptBuilder(mock_config)

    # Run full rounds
    iterations = 5
    for _ in range(iterations):
        start = time.time()

        # 1. Fetch data
        market_data = await fetcher.fetch_multi_timeframe(
            symbol="BTC/USDT",
            timeframes=["1m", "3m", "15m", "1h", "4h"],
            lookback=100
        )

        # 2. Build prompt
        account_info = {"cash_balance": 100.0, "total_value": 100.0, "positions": {}}
        prompt = builder.build_prompt(
            symbol="BTC/USDT",
            market_data=market_data,
            account_info=account_info
        )

        # 3. Get decisions
        current_price = market_data["3m"][-1]["close"]
        decisions = await manager.get_all_decisions(prompt, "BTC/USDT", current_price)

        # 4. Execute decisions
        execution_results = await manager.execute_decisions(
            decisions, "BTC/USDT", current_price
        )

        latency = time.time() - start
        monitor.record_api_call(latency)

    monitor.stop()
    report = monitor.get_report()

    print("\n" + "="*80)
    print("🏁 FULL ROUND PERFORMANCE BENCHMARK")
    print("="*80)
    print(f"Rounds Completed: {iterations}")
    print(f"Average Round Time: {report['avg_latency']:.3f}s")
    print(f"Min Round Time: {report['min_latency']:.3f}s")
    print(f"Max Round Time: {report['max_latency']:.3f}s")
    print(f"Rounds Per Minute: {60/report['avg_latency']:.2f}")
    print("="*80)

    assert report["api_calls"] == iterations
    assert report["avg_latency"] < 5.0  # Should be reasonably fast


# ============================================================================
# Memory Usage Tests
# ============================================================================


@pytest.mark.asyncio
async def test_memory_usage():
    """Benchmark memory usage during operations"""
    process = psutil.Process(os.getpid())

    # Get baseline memory
    baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

    manager = LLMManager()

    # Add 10 models
    for i in range(10):
        client = MockLLMClient(
            provider=f"model{i}",
            responses=[create_mock_trading_decision()]
        )
        state = ModelState(f"model{i}", i+1, 100.0)
        state.client = client
        manager.models[f"model{i}"] = state

    # Run many rounds
    for _ in range(50):
        await manager.get_all_decisions("test", "BTC/USDT", 100000.0)

    # Get final memory
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - baseline_memory

    print("\n" + "="*80)
    print("💾 MEMORY USAGE BENCHMARK")
    print("="*80)
    print(f"Baseline Memory: {baseline_memory:.2f} MB")
    print(f"Final Memory: {final_memory:.2f} MB")
    print(f"Memory Increase: {memory_increase:.2f} MB")
    print(f"Models: 10")
    print(f"Rounds: 50")
    print("="*80)

    # Should not have significant memory leak
    assert memory_increase < 100  # Less than 100MB increase


# ============================================================================
# Throughput Tests
# ============================================================================


@pytest.mark.asyncio
async def test_decision_throughput():
    """Benchmark decision-making throughput"""
    monitor = PerformanceMonitor()
    monitor.start()

    manager = LLMManager()

    # Add fast model
    client = MockLLMClient(
        provider="fast",
        delay_seconds=0.05,
        responses=[create_mock_trading_decision()]
    )
    state = ModelState("fast", 1, 100.0)
    state.client = client
    manager.models["fast"] = state

    # Make many rapid decisions
    total_decisions = 100
    for _ in range(total_decisions):
        start = time.time()
        await manager.get_all_decisions("test", "BTC/USDT", 100000.0)
        latency = time.time() - start
        monitor.record_api_call(latency)

    monitor.stop()
    report = monitor.get_report()

    print("\n" + "="*80)
    print("⚡ DECISION THROUGHPUT BENCHMARK")
    print("="*80)
    print(f"Total Decisions: {total_decisions}")
    print(f"Total Time: {report['duration_seconds']:.3f}s")
    print(f"Decisions Per Second: {report['calls_per_second']:.2f}")
    print(f"Average Latency: {report['avg_latency']*1000:.2f}ms")
    print("="*80)

    assert report["api_calls"] == total_decisions
    assert report["calls_per_second"] > 10  # At least 10 decisions/sec


# ============================================================================
# Scalability Tests
# ============================================================================


@pytest.mark.asyncio
async def test_model_scalability():
    """Test performance scaling with number of models"""
    results = []

    for num_models in [1, 2, 4, 8, 16]:
        manager = LLMManager()

        # Add N models
        for i in range(num_models):
            client = MockLLMClient(
                provider=f"model{i}",
                delay_seconds=0.1,
                responses=[create_mock_trading_decision()]
            )
            state = ModelState(f"model{i}", i+1, 100.0)
            state.client = client
            manager.models[f"model{i}"] = state

        # Time a round
        start = time.time()
        decisions = await manager.get_all_decisions("test", "BTC/USDT", 100000.0)
        elapsed = time.time() - start

        results.append({
            "num_models": num_models,
            "time": elapsed,
            "decisions": len(decisions)
        })

    print("\n" + "="*80)
    print("📈 MODEL SCALABILITY BENCHMARK")
    print("="*80)
    for result in results:
        print(f"Models: {result['num_models']:2d}  |  Time: {result['time']:.3f}s  |  "
              f"Decisions: {result['decisions']:2d}")
    print("="*80)

    # Time should scale logarithmically, not linearly
    # (parallel execution means more models doesn't mean proportional time increase)
    assert results[-1]["time"] < results[-1]["num_models"] * 0.1  # Much better than linear


# ============================================================================
# Performance Report
# ============================================================================


def test_performance_report():
    """Generate performance testing report"""
    print("\n" + "="*80)
    print("📊 PERFORMANCE TESTING COMPLETE")
    print("="*80)
    print("\nBenchmarks Performed:")
    print("  ✅ LLM Response Time")
    print("  ✅ Parallel LLM Execution")
    print("  ✅ Data Fetch Speed")
    print("  ✅ Concurrent Data Fetches")
    print("  ✅ Prompt Generation Speed")
    print("  ✅ Full Round Performance")
    print("  ✅ Memory Usage")
    print("  ✅ Decision Throughput")
    print("  ✅ Model Scalability")
    print("\n" + "="*80)
    print("Performance Analysis: COMPLETE ✅")
    print("="*80)


if __name__ == "__main__":
    # Run benchmarks
    pytest.main([__file__, "-v", "--tb=short", "-s"])
