"""
Prompt Builder for AI Trading Arena

This module builds complete prompts by:
1. Fetching market data (multi-timeframe)
2. Calculating technical indicators
3. Formatting data (CRITICAL: oldest → newest)
4. Injecting into templates
5. Generating final prompt

Usage:
    from strategies.prompts import PromptBuilder

    builder = PromptBuilder()
    prompt = builder.build_prompt(
        symbol="BTC/USDT",
        template_version="nof1_exact",
        account_info=account
    )
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from strategies.prompt_templates import PromptTemplateManager
from utils.config import get_config
from utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# Data Formatter
# ============================================================================


class DataFormatter:
    """
    Formats market data for prompt injection

    CRITICAL: All data must be ordered oldest → newest for nof1 compatibility
    """

    def __init__(self):
        """Initialize data formatter"""
        self.logger = get_logger("prompt.formatter")

    def format_price_series(
        self,
        candles: List[Dict[str, Any]],
        field: str = "close"
    ) -> List[float]:
        """
        Extract price series from candles

        Args:
            candles: List of candle dicts (MUST be oldest → newest)
            field: Which price field to extract (open/high/low/close)

        Returns:
            List of prices (oldest → newest)
        """
        if not candles:
            return []

        # Verify ordering (timestamps should be increasing)
        for i in range(1, len(candles)):
            if candles[i]["timestamp"] < candles[i-1]["timestamp"]:
                self.logger.error(
                    "Candles not in oldest → newest order!",
                    index=i,
                    current_ts=candles[i]["timestamp"],
                    previous_ts=candles[i-1]["timestamp"]
                )
                raise ValueError("Candles must be ordered oldest → newest")

        prices = [candle[field] for candle in candles]
        self.logger.debug(
            "Price series formatted",
            field=field,
            count=len(prices),
            first=prices[0] if prices else None,
            last=prices[-1] if prices else None
        )

        return prices

    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """
        Calculate EMA (Exponential Moving Average)

        Args:
            prices: Price series (oldest → newest)
            period: EMA period

        Returns:
            EMA series (oldest → newest)
        """
        if len(prices) < period:
            return []

        ema_values = []
        multiplier = 2 / (period + 1)

        # First EMA is SMA
        sma = sum(prices[:period]) / period
        ema_values.append(sma)

        # Calculate EMA for remaining prices
        for price in prices[period:]:
            ema = (price * multiplier) + (ema_values[-1] * (1 - multiplier))
            ema_values.append(ema)

        return ema_values

    def calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        """
        Calculate RSI (Relative Strength Index)

        Args:
            prices: Price series (oldest → newest)
            period: RSI period

        Returns:
            RSI series (oldest → newest)
        """
        if len(prices) < period + 1:
            return []

        rsi_values = []
        gains = []
        losses = []

        # Calculate price changes
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))

        # Calculate RSI for each window
        for i in range(period - 1, len(gains)):
            avg_gain = sum(gains[i-period+1:i+1]) / period
            avg_loss = sum(losses[i-period+1:i+1]) / period

            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))

            rsi_values.append(rsi)

        return rsi_values

    def calculate_macd(
        self,
        prices: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Dict[str, List[float]]:
        """
        Calculate MACD (Moving Average Convergence Divergence)

        Args:
            prices: Price series (oldest → newest)
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period

        Returns:
            Dict with 'macd', 'signal', 'histogram' series
        """
        if len(prices) < slow:
            return {"macd": [], "signal": [], "histogram": []}

        # Calculate EMAs
        ema_fast = self.calculate_ema(prices, fast)
        ema_slow = self.calculate_ema(prices, slow)

        # MACD = fast EMA - slow EMA
        # Need to align the series (ema_slow is shorter)
        offset = len(ema_fast) - len(ema_slow)
        macd_line = [
            ema_fast[i + offset] - ema_slow[i]
            for i in range(len(ema_slow))
        ]

        # Signal line = EMA of MACD
        if len(macd_line) >= signal:
            signal_line = self.calculate_ema(macd_line, signal)

            # Histogram = MACD - Signal
            offset2 = len(macd_line) - len(signal_line)
            histogram = [
                macd_line[i + offset2] - signal_line[i]
                for i in range(len(signal_line))
            ]
        else:
            signal_line = []
            histogram = []

        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }


# ============================================================================
# Prompt Builder
# ============================================================================


class PromptBuilder:
    """
    Builds complete prompts from market data

    This is the main interface for generating prompts.
    It coordinates data fetching, formatting, and template injection.
    """

    def __init__(self):
        """Initialize prompt builder"""
        self.config = get_config()
        self.template_manager = PromptTemplateManager()
        self.formatter = DataFormatter()
        self.logger = get_logger("prompt.builder")

        # Session tracking
        self.session_start = datetime.now()
        self.invocation_count = 0

        self.logger.info("Prompt builder initialized")

    def build_prompt(
        self,
        symbol: str,
        market_data: Dict[str, List[Dict[str, Any]]],  # Multi-timeframe candles
        account_info: Dict[str, Any],
        template_version: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Build complete prompt from market data

        Args:
            symbol: Trading symbol (e.g., "BTC/USDT")
            market_data: Dict of timeframe → candles (oldest → newest)
            account_info: Account state
            template_version: Template to use (default from config)
            **kwargs: Additional template variables

        Returns:
            Generated prompt string

        Example:
            market_data = {
                "1m": [candle1, candle2, ...],  # oldest → newest
                "3m": [candle1, candle2, ...],
                "15m": [candle1, candle2, ...]
            }
        """
        self.invocation_count += 1

        if template_version is None:
            template_version = self.config.prompts.template_version

        self.logger.info(
            "Building prompt",
            symbol=symbol,
            template=template_version,
            invocation=self.invocation_count
        )

        try:
            # Extract current state from most recent data
            primary_timeframe = self.config.data.timeframes["primary"]
            latest_candle = market_data[primary_timeframe][-1]
            current_price = latest_candle["close"]

            # Format price series for each timeframe
            price_series = {}
            for timeframe, candles in market_data.items():
                prices = self.formatter.format_price_series(candles, "close")
                price_series[timeframe] = prices

            # Calculate indicators from primary timeframe
            primary_prices = price_series[primary_timeframe]

            # Current indicators (most recent value)
            ema_20 = self.formatter.calculate_ema(primary_prices, 20)
            ema_50 = self.formatter.calculate_ema(primary_prices, 50)
            rsi_7 = self.formatter.calculate_rsi(primary_prices, 7)
            rsi_14 = self.formatter.calculate_rsi(primary_prices, 14)
            macd_data = self.formatter.calculate_macd(primary_prices)

            indicators = {
                "ema_20": ema_20[-1] if ema_20 else 0,
                "ema_50": ema_50[-1] if ema_50 else 0,
                "rsi_7": rsi_7[-1] if rsi_7 else 50,
                "rsi_14": rsi_14[-1] if rsi_14 else 50,
                "macd": macd_data["macd"][-1] if macd_data["macd"] else 0,
                "macd_signal": macd_data["signal"][-1] if macd_data["signal"] else 0,
                "macd_histogram": macd_data["histogram"][-1] if macd_data["histogram"] else 0,
            }

            # Indicator series (for charts in prompt)
            indicator_series = {
                "ema_20_series": ema_20[-20:] if len(ema_20) >= 20 else ema_20,
                "macd_series": macd_data["macd"][-20:] if len(macd_data["macd"]) >= 20 else macd_data["macd"],
                "rsi_14_series": rsi_14[-20:] if len(rsi_14) >= 20 else rsi_14,
            }

            # Session information
            session_info = {
                "minutes_elapsed": int((datetime.now() - self.session_start).total_seconds() / 60),
                "current_time": datetime.now(),
                "invocations": self.invocation_count
            }

            # Generate prompt using template
            prompt = self.template_manager.generate_prompt(
                template_version=template_version,
                symbol=symbol,
                current_price=current_price,
                indicators=indicators,
                price_series=price_series,
                indicator_series=indicator_series,
                account_info=account_info,
                session_info=session_info,
                **kwargs
            )

            self.logger.info(
                "Prompt built successfully",
                symbol=symbol,
                template=template_version,
                prompt_length=len(prompt),
                invocation=self.invocation_count
            )

            return prompt

        except Exception as e:
            self.logger.error(
                "Failed to build prompt",
                symbol=symbol,
                template=template_version,
                error=str(e),
                exc_info=True
            )
            raise

    def reset_session(self):
        """Reset session tracking"""
        self.session_start = datetime.now()
        self.invocation_count = 0
        self.logger.info("Session reset")
