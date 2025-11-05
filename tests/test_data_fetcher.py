"""
Test Data Fetcher

Tests for BinanceDataFetcher to verify:
- Single timeframe fetching
- Multi-timeframe fetching
- Rate limiting
- Caching
- Data validation
- Oldest → newest ordering
"""

import asyncio
import pytest
from datetime import datetime

from core.data_fetcher import (
    BinanceDataFetcher,
    RateLimiter,
    DataCache,
    fetch_data_sync
)
from utils.errors import DataFetchError, InvalidDataError


class TestRateLimiter:
    """Test rate limiter"""

    @pytest.mark.asyncio
    async def test_rate_limiter(self):
        """Test rate limiter delays requests"""
        limiter = RateLimiter(max_calls=3, time_window=1.0)

        # First 3 calls should be instant
        for i in range(3):
            await limiter.acquire()

        # 4th call should wait
        import time
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start

        assert elapsed > 0.5  # Should have waited


class TestDataCache:
    """Test data cache"""

    def test_cache_miss(self):
        """Test cache miss returns None"""
        cache = DataCache(ttl=60)

        result = cache.get("BTC/USDT", "1m", 100)
        assert result is None

    def test_cache_hit(self):
        """Test cache hit returns data"""
        cache = DataCache(ttl=60)

        test_data = [{"close": 50000.0}]
        cache.set("BTC/USDT", "1m", 100, test_data)

        result = cache.get("BTC/USDT", "1m", 100)
        assert result == test_data

    def test_cache_expiration(self):
        """Test cache expires after TTL"""
        import time

        cache = DataCache(ttl=1)  # 1 second TTL

        test_data = [{"close": 50000.0}]
        cache.set("BTC/USDT", "1m", 100, test_data)

        # Should hit immediately
        assert cache.get("BTC/USDT", "1m", 100) is not None

        # Wait for expiration
        time.sleep(1.5)

        # Should miss after expiration
        assert cache.get("BTC/USDT", "1m", 100) is None


class TestBinanceDataFetcher:
    """Test Binance data fetcher"""

    @pytest.mark.asyncio
    async def test_fetch_single_timeframe(self):
        """Test fetching single timeframe"""
        fetcher = BinanceDataFetcher()

        try:
            # Fetch 1-minute data
            candles = await fetcher.fetch_ohlcv(
                symbol="BTC/USDT",
                timeframe="1m",
                lookback=10,
                use_cache=False
            )

            # Verify we got data
            assert len(candles) == 10
            assert all(isinstance(c, dict) for c in candles)

            # Verify required fields
            for candle in candles:
                assert "timestamp" in candle
                assert "open" in candle
                assert "high" in candle
                assert "low" in candle
                assert "close" in candle
                assert "volume" in candle

            # Verify oldest → newest ordering
            for i in range(1, len(candles)):
                assert candles[i]["timestamp"] > candles[i-1]["timestamp"]

            print(f"✓ Fetched {len(candles)} candles")
            print(f"  First: {candles[0]['timestamp']} @ ${candles[0]['close']:.2f}")
            print(f"  Last:  {candles[-1]['timestamp']} @ ${candles[-1]['close']:.2f}")

        finally:
            await fetcher.close()

    @pytest.mark.asyncio
    async def test_fetch_multi_timeframe(self):
        """Test fetching multiple timeframes"""
        fetcher = BinanceDataFetcher()

        try:
            # Fetch multiple timeframes
            data = await fetcher.fetch_multi_timeframe(
                symbol="BTC/USDT",
                timeframes=["1m", "5m", "15m"],
                lookback=20,
                use_cache=False
            )

            # Verify all timeframes
            assert "1m" in data
            assert "5m" in data
            assert "15m" in data

            # Verify each has correct length
            assert len(data["1m"]) == 20
            assert len(data["5m"]) == 20
            assert len(data["15m"]) == 20

            # Verify oldest → newest for all
            for tf, candles in data.items():
                for i in range(1, len(candles)):
                    assert candles[i]["timestamp"] > candles[i-1]["timestamp"]

            print(f"✓ Fetched data for {len(data)} timeframes")

        finally:
            await fetcher.close()

    @pytest.mark.asyncio
    async def test_caching(self):
        """Test data caching works"""
        import time

        fetcher = BinanceDataFetcher()

        try:
            # First fetch (should hit API)
            start = time.time()
            data1 = await fetcher.fetch_ohlcv(
                symbol="BTC/USDT",
                timeframe="1m",
                lookback=10,
                use_cache=True
            )
            time1 = time.time() - start

            # Second fetch (should hit cache)
            start = time.time()
            data2 = await fetcher.fetch_ohlcv(
                symbol="BTC/USDT",
                timeframe="1m",
                lookback=10,
                use_cache=True
            )
            time2 = time.time() - start

            # Cache should be faster
            assert time2 < time1 / 2  # At least 2x faster

            # Data should be identical
            assert len(data1) == len(data2)

            print(f"✓ Cache hit {(time1/time2):.1f}x faster")

        finally:
            await fetcher.close()

    @pytest.mark.asyncio
    async def test_current_price(self):
        """Test getting current price"""
        fetcher = BinanceDataFetcher()

        try:
            price = await fetcher.get_current_price("BTC/USDT")

            assert isinstance(price, float)
            assert price > 0
            assert price > 10000  # BTC should be above $10k

            print(f"✓ Current BTC price: ${price:,.2f}")

        finally:
            await fetcher.close()

    @pytest.mark.asyncio
    async def test_invalid_timeframe(self):
        """Test invalid timeframe raises error"""
        fetcher = BinanceDataFetcher()

        try:
            with pytest.raises(DataFetchError):
                await fetcher.fetch_ohlcv(
                    symbol="BTC/USDT",
                    timeframe="99m",  # Invalid
                    lookback=10
                )
        finally:
            await fetcher.close()


def test_sync_wrapper():
    """Test synchronous wrapper"""
    # This should work without async/await
    data = fetch_data_sync(
        symbol="BTC/USDT",
        timeframes=["1m", "5m"],
        lookback=5
    )

    assert "1m" in data
    assert "5m" in data
    assert len(data["1m"]) == 5
    assert len(data["5m"]) == 5

    print("✓ Synchronous wrapper works")


if __name__ == "__main__":
    """Run smoke tests"""
    print("Running BinanceDataFetcher smoke tests...\n")

    # Test 1: Fetch single timeframe
    print("Test 1: Fetching single timeframe")
    async def test1():
        fetcher = BinanceDataFetcher()
        try:
            candles = await fetcher.fetch_ohlcv(
                symbol="BTC/USDT",
                timeframe="1m",
                lookback=5
            )
            print(f"✓ Fetched {len(candles)} candles")
            print(f"  Latest price: ${candles[-1]['close']:,.2f}")
            print()
        finally:
            await fetcher.close()

    asyncio.run(test1())

    # Test 2: Multi-timeframe
    print("Test 2: Fetching multi-timeframe")
    async def test2():
        fetcher = BinanceDataFetcher()
        try:
            data = await fetcher.fetch_multi_timeframe(
                symbol="BTC/USDT",
                timeframes=["1m", "5m", "15m"],
                lookback=10
            )
            print(f"✓ Fetched {len(data)} timeframes:")
            for tf, candles in data.items():
                print(f"  {tf}: {len(candles)} candles")
            print()
        finally:
            await fetcher.close()

    asyncio.run(test2())

    # Test 3: Current price
    print("Test 3: Getting current price")
    async def test3():
        fetcher = BinanceDataFetcher()
        try:
            price = await fetcher.get_current_price("BTC/USDT")
            print(f"✓ Current BTC/USDT: ${price:,.2f}")
            print()
        finally:
            await fetcher.close()

    asyncio.run(test3())

    # Test 4: Sync wrapper
    print("Test 4: Synchronous wrapper")
    data = fetch_data_sync(
        symbol="ETH/USDT",
        timeframes=["1m"],
        lookback=3
    )
    print(f"✓ Fetched {len(data['1m'])} ETH candles via sync wrapper")
    print(f"  Latest ETH: ${data['1m'][-1]['close']:,.2f}")

    print("\n✅ All smoke tests passed!")
