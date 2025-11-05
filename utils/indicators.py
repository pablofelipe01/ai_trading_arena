"""
Technical Indicators Calculator for AI Trading Arena

Calculates basic technical indicators from OHLCV data:
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- EMA (Exponential Moving Average)
- Volume

Uses pandas for efficient calculations.
"""

from typing import Dict, List, Any
import pandas as pd


def calculate_ema(prices: List[float], period: int = 20) -> List[float]:
    """
    Calculate Exponential Moving Average

    Args:
        prices: List of prices (oldest → newest)
        period: EMA period

    Returns:
        List of EMA values (same length as prices, padded with None for first values)
    """
    if not prices or len(prices) < period:
        return [None] * len(prices)

    df = pd.DataFrame({"price": prices})
    ema = df["price"].ewm(span=period, adjust=False).mean()

    return ema.tolist()


def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """
    Calculate Relative Strength Index

    Args:
        prices: List of prices (oldest → newest)
        period: RSI period

    Returns:
        List of RSI values (0-100, same length as prices)
    """
    if not prices or len(prices) < period + 1:
        return [50.0] * len(prices)  # Neutral RSI for insufficient data

    df = pd.DataFrame({"price": prices})

    # Calculate price changes
    delta = df["price"].diff()

    # Separate gains and losses
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)

    # Calculate average gains and losses
    avg_gains = gains.ewm(span=period, adjust=False).mean()
    avg_losses = losses.ewm(span=period, adjust=False).mean()

    # Calculate RS and RSI
    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))

    # Fill NaN with neutral RSI
    rsi = rsi.fillna(50.0)

    return rsi.tolist()


def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> List[float]:
    """
    Calculate MACD (Moving Average Convergence Divergence)

    Args:
        prices: List of prices (oldest → newest)
        fast: Fast EMA period
        slow: Slow EMA period
        signal: Signal line period

    Returns:
        List of MACD values (MACD line - signal line)
    """
    if not prices or len(prices) < slow:
        return [0.0] * len(prices)

    df = pd.DataFrame({"price": prices})

    # Calculate fast and slow EMAs
    ema_fast = df["price"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["price"].ewm(span=slow, adjust=False).mean()

    # MACD line
    macd_line = ema_fast - ema_slow

    # Signal line
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()

    # MACD histogram (MACD - signal)
    macd_histogram = macd_line - signal_line

    # Fill NaN with 0
    macd_histogram = macd_histogram.fillna(0.0)

    return macd_histogram.tolist()


def calculate_indicators_from_ohlcv(
    candles: List[Dict[str, Any]],
    timeframe: str = "3m"
) -> Dict[str, Any]:
    """
    Calculate all Level 1 indicators from OHLCV candles

    Args:
        candles: List of OHLCV candles (oldest → newest)
                Each candle: {"timestamp", "open", "high", "low", "close", "volume"}
        timeframe: Timeframe string (for logging)

    Returns:
        Dict with:
        - indicators: Current indicator values (last candle)
        - price_series: Close prices (for chart display)
        - indicator_series: Full indicator arrays
    """
    if not candles:
        return {
            "indicators": {},
            "price_series": [],
            "indicator_series": {}
        }

    # Extract price and volume data
    close_prices = [c["close"] for c in candles]
    volumes = [c["volume"] for c in candles]

    # Calculate indicators
    ema_20 = calculate_ema(close_prices, period=20)
    rsi_14 = calculate_rsi(close_prices, period=14)
    macd = calculate_macd(close_prices)

    # Current values (last candle)
    current_indicators = {
        "ema_20": ema_20[-1] if ema_20 and ema_20[-1] is not None else close_prices[-1],
        "rsi_14": rsi_14[-1] if rsi_14 else 50.0,
        "macd": macd[-1] if macd else 0.0,
        "volume": volumes[-1] if volumes else 0.0
    }

    # Return structured data
    return {
        "indicators": current_indicators,
        "price_series": close_prices,
        "indicator_series": {
            "ema_20_series": [v if v is not None else close_prices[i] for i, v in enumerate(ema_20)],
            "rsi_14_series": rsi_14,
            "macd_series": macd,
            "volume_series": volumes
        }
    }


def calculate_multi_timeframe_indicators(
    ohlcv_data: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate indicators for multiple timeframes

    Args:
        ohlcv_data: Dict of timeframe → candles

    Returns:
        Dict of timeframe → {indicators, price_series, indicator_series}
    """
    result = {}

    for timeframe, candles in ohlcv_data.items():
        result[timeframe] = calculate_indicators_from_ohlcv(candles, timeframe)

    return result
