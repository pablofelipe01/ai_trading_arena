"""
Data Fetcher for AI Trading Arena

Fetches real-time and historical market data from Binance.
Supports multi-timeframe analysis with proper caching and rate limiting.

CRITICAL: All data is returned in oldest → newest order for nof1 compatibility.

Usage:
    from core.data_fetcher import BinanceDataFetcher

    fetcher = BinanceDataFetcher()
    data = await fetcher.fetch_multi_timeframe(
        symbol="BTC/USDT",
        timeframes=["1m", "3m", "15m"],
        lookback=100
    )
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import ccxt.async_support as ccxt
from ccxt.base.errors import (
    RateLimitExceeded,
    NetworkError,
    ExchangeNotAvailable,
)

from utils.config import get_config
from utils.errors import (
    DataFetchError,
    InvalidDataError,
)
from utils.logger import get_logger


logger = get_logger(__name__)


# ============================================================================
# Rate Limiter
# ============================================================================


class RateLimiter:
    """
    Simple rate limiter for API calls

    Ensures we don't exceed exchange rate limits.
    """

    def __init__(self, max_calls: int, time_window: float):
        """
        Initialize rate limiter

        Args:
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: List[float] = []
        self.logger = get_logger("data.ratelimiter")

    async def acquire(self):
        """Acquire permission to make an API call"""
        now = time.time()

        # Remove old calls outside the time window
        self.calls = [call_time for call_time in self.calls
                     if now - call_time < self.time_window]

        # Check if we're at the limit
        if len(self.calls) >= self.max_calls:
            # Calculate wait time
            oldest_call = self.calls[0]
            wait_time = self.time_window - (now - oldest_call)

            if wait_time > 0:
                self.logger.warning(
                    "Rate limit reached, waiting",
                    wait_seconds=wait_time,
                    calls_made=len(self.calls)
                )
                await asyncio.sleep(wait_time)

        # Record this call
        self.calls.append(time.time())


# ============================================================================
# Data Cache
# ============================================================================


class DataCache:
    """
    Simple in-memory cache for market data

    Prevents redundant API calls for recently fetched data.
    """

    def __init__(self, ttl: int = 60):
        """
        Initialize cache

        Args:
            ttl: Time to live in seconds
        """
        self.ttl = ttl
        self.cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
        self.logger = get_logger("data.cache")

    def get(
        self,
        symbol: str,
        timeframe: str,
        lookback: int
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached data if available and fresh

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., "1m", "5m")
            lookback: Number of candles

        Returns:
            Cached data or None
        """
        key = f"{symbol}:{timeframe}:{lookback}"

        if key in self.cache:
            timestamp, data = self.cache[key]
            age = time.time() - timestamp

            if age < self.ttl:
                self.logger.debug(
                    "Cache hit",
                    symbol=symbol,
                    timeframe=timeframe,
                    age_seconds=age
                )
                return data
            else:
                # Expired
                del self.cache[key]

        return None

    def set(
        self,
        symbol: str,
        timeframe: str,
        lookback: int,
        data: List[Dict[str, Any]]
    ):
        """
        Store data in cache

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            lookback: Number of candles
            data: Market data to cache
        """
        key = f"{symbol}:{timeframe}:{lookback}"
        self.cache[key] = (time.time(), data)

        self.logger.debug(
            "Data cached",
            symbol=symbol,
            timeframe=timeframe,
            candles=len(data)
        )

    def clear(self):
        """Clear all cached data"""
        self.cache.clear()
        self.logger.info("Cache cleared")


# ============================================================================
# Binance Data Fetcher
# ============================================================================


class BinanceDataFetcher:
    """
    Fetches market data from Binance

    Features:
    - Multi-timeframe support
    - Rate limiting
    - Caching
    - Retry logic
    - Data validation
    - Oldest → newest ordering (CRITICAL)
    """

    def __init__(self):
        """Initialize Binance data fetcher"""
        self.config = get_config()
        self.logger = get_logger("data.binance")

        # Initialize exchange
        # Note: API keys are optional for public endpoints (OHLCV data)
        import os
        exchange_config = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',  # Use spot market
            }
        }

        # Add API keys if available (optional for public data)
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        if api_key and api_secret:
            exchange_config['apiKey'] = api_key
            exchange_config['secret'] = api_secret

        self.exchange = ccxt.binance(exchange_config)

        # Rate limiter (Binance allows ~1200 requests/min, we use 600 to be safe)
        max_requests = getattr(
            getattr(self.config.data, 'rate_limit', None),
            'max_requests_per_minute',
            600
        ) if hasattr(self.config.data, 'rate_limit') else 600

        self.rate_limiter = RateLimiter(
            max_calls=max_requests,
            time_window=60.0
        )

        # Cache with TTL from config (default 60 seconds)
        cache_ttl = getattr(
            getattr(self.config.data, 'cache', None),
            'ttl_seconds',
            60
        ) if hasattr(self.config.data, 'cache') else 60

        self.cache = DataCache(ttl=cache_ttl)

        # Timeframe mapping (ccxt format)
        self.timeframe_map = {
            "1m": "1m",
            "3m": "3m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "2h": "2h",
            "4h": "4h",
            "1d": "1d",
        }

        self.logger.info("Binance data fetcher initialized")

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        lookback: int,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV candles for a symbol

        Args:
            symbol: Trading symbol (e.g., "BTC/USDT")
            timeframe: Timeframe (e.g., "1m", "5m", "1h")
            lookback: Number of candles to fetch
            use_cache: Whether to use cached data

        Returns:
            List of candle dicts (oldest → newest)

        Raises:
            DataFetchError: If fetch fails
            DataValidationError: If data is invalid
        """
        # Check cache first
        if use_cache:
            cached_data = self.cache.get(symbol, timeframe, lookback)
            if cached_data is not None:
                return cached_data

        # Validate timeframe
        if timeframe not in self.timeframe_map:
            raise DataFetchError(
                f"Invalid timeframe: {timeframe}",
                symbol=symbol,
                details={"valid_timeframes": list(self.timeframe_map.keys())}
            )

        self.logger.info(
            "Fetching OHLCV data",
            symbol=symbol,
            timeframe=timeframe,
            lookback=lookback
        )

        try:
            # Rate limiting
            await self.rate_limiter.acquire()

            # Calculate since timestamp
            # We fetch extra candles to account for gaps
            timeframe_ms = self._timeframe_to_ms(timeframe)
            since = int((time.time() * 1000) - (lookback * 1.2 * timeframe_ms))

            # Fetch from exchange
            ohlcv = await self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=self.timeframe_map[timeframe],
                since=since,
                limit=min(lookback * 2, 1000)  # Binance limit is 1000
            )

            if not ohlcv:
                raise DataFetchError(
                    "No data returned from exchange",
                    symbol=symbol,
                    timeframe=timeframe
                )

            # Convert to our format (oldest → newest)
            candles = []
            for candle in ohlcv[-lookback:]:  # Get most recent N candles
                candle_dict = {
                    "timestamp": datetime.fromtimestamp(candle[0] / 1000),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5]),
                }
                candles.append(candle_dict)

            # Verify oldest → newest ordering
            for i in range(1, len(candles)):
                if candles[i]["timestamp"] < candles[i-1]["timestamp"]:
                    raise InvalidDataError(
                        "Candles not in oldest → newest order",
                        symbol=symbol,
                        details={
                            "index": i,
                            "current": candles[i]["timestamp"],
                            "previous": candles[i-1]["timestamp"]
                        }
                    )

            self.logger.info(
                "OHLCV data fetched successfully",
                symbol=symbol,
                timeframe=timeframe,
                candles=len(candles),
                first_timestamp=candles[0]["timestamp"],
                last_timestamp=candles[-1]["timestamp"]
            )

            # Cache the data
            if use_cache:
                self.cache.set(symbol, timeframe, lookback, candles)

            return candles

        except (RateLimitExceeded, NetworkError, ExchangeNotAvailable) as e:
            self.logger.error(
                "Exchange error fetching data",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            raise DataFetchError(
                f"Failed to fetch data from Binance: {str(e)}",
                symbol=symbol,
                details={"timeframe": timeframe, "lookback": lookback}
            ) from e

        except Exception as e:
            self.logger.error(
                "Unexpected error fetching data",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e),
                exc_info=True
            )
            raise DataFetchError(
                f"Unexpected error: {str(e)}",
                symbol=symbol
            ) from e

    async def fetch_multi_timeframe(
        self,
        symbol: str,
        timeframes: List[str],
        lookback: int,
        use_cache: bool = True
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch data for multiple timeframes

        Args:
            symbol: Trading symbol
            timeframes: List of timeframes
            lookback: Number of candles per timeframe
            use_cache: Whether to use cache

        Returns:
            Dict of timeframe → candles (all oldest → newest)
        """
        self.logger.info(
            "Fetching multi-timeframe data",
            symbol=symbol,
            timeframes=timeframes,
            lookback=lookback
        )

        # Fetch all timeframes concurrently
        tasks = [
            self.fetch_ohlcv(symbol, tf, lookback, use_cache)
            for tf in timeframes
        ]

        try:
            results = await asyncio.gather(*tasks)

            # Build result dict
            data = {tf: candles for tf, candles in zip(timeframes, results)}

            self.logger.info(
                "Multi-timeframe data fetched successfully",
                symbol=symbol,
                timeframes=len(data)
            )

            return data

        except Exception as e:
            self.logger.error(
                "Failed to fetch multi-timeframe data",
                symbol=symbol,
                error=str(e)
            )
            raise

    async def get_current_price(self, symbol: str) -> float:
        """
        Get current market price

        Args:
            symbol: Trading symbol

        Returns:
            Current price
        """
        try:
            await self.rate_limiter.acquire()
            ticker = await self.exchange.fetch_ticker(symbol)
            price = float(ticker['last'])

            self.logger.debug("Current price fetched", symbol=symbol, price=price)
            return price

        except Exception as e:
            self.logger.error(
                "Failed to fetch current price",
                symbol=symbol,
                error=str(e)
            )
            raise DataFetchError(
                f"Failed to get current price: {str(e)}",
                symbol=symbol
            ) from e

    def _timeframe_to_ms(self, timeframe: str) -> int:
        """
        Convert timeframe string to milliseconds

        Args:
            timeframe: Timeframe (e.g., "1m", "5m", "1h")

        Returns:
            Milliseconds
        """
        units = {
            "m": 60 * 1000,
            "h": 60 * 60 * 1000,
            "d": 24 * 60 * 60 * 1000,
        }

        value = int(timeframe[:-1])
        unit = timeframe[-1]

        return value * units[unit]

    async def close(self):
        """Close exchange connection"""
        await self.exchange.close()
        self.logger.info("Exchange connection closed")


# ============================================================================
# Synchronous Wrapper (for testing)
# ============================================================================


def fetch_data_sync(
    symbol: str,
    timeframes: List[str],
    lookback: int = 100
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Synchronous wrapper for fetching multi-timeframe data

    Useful for testing and simple scripts.

    Args:
        symbol: Trading symbol
        timeframes: List of timeframes
        lookback: Number of candles

    Returns:
        Dict of timeframe → candles
    """
    async def _fetch():
        fetcher = BinanceDataFetcher()
        try:
            data = await fetcher.fetch_multi_timeframe(
                symbol=symbol,
                timeframes=timeframes,
                lookback=lookback
            )
            return data
        finally:
            await fetcher.close()

    return asyncio.run(_fetch())
