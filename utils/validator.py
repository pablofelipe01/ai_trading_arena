"""
Validators for AI Trading Arena

Robust validation system for:
- LLM responses (trading decisions)
- Market data integrity
- Configuration values
- API responses

All validators use Pydantic for type safety and detailed error messages.

Usage:
    from utils.validator import validate_llm_response, validate_market_data

    # Validate LLM trading decision
    decision = validate_llm_response(llm_output)

    # Validate market data
    data = validate_market_data(binance_response)
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# Trading Decision Validation
# ============================================================================


class TradingDecision(BaseModel):
    """
    Validated trading decision from LLM

    This is the expected format from all LLM models.
    """

    action: Literal["BUY", "SELL", "HOLD"] = Field(
        description="Trading action to take"
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Model confidence in decision (0-1)",
    )

    reasoning: str = Field(
        min_length=10,
        max_length=2000,
        description="Explanation of the decision",
    )

    position_size: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of capital to use (0-1)",
    )

    stop_loss: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Stop loss price (optional)",
    )

    take_profit: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Take profit price (optional)",
    )

    indicators_used: Optional[List[str]] = Field(
        default=None,
        description="List of indicators considered",
    )

    timeframe: Optional[str] = Field(
        default=None,
        description="Primary timeframe used for decision",
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Ensure action is uppercase"""
        return v.upper()

    @field_validator("position_size")
    @classmethod
    def validate_position_size(cls, v: float, info) -> float:
        """Validate position size based on action"""
        action = info.data.get("action")
        if action == "HOLD" and v > 0:
            logger.warning(
                "HOLD action with non-zero position size, setting to 0",
                original_size=v,
            )
            return 0.0
        return v

    @model_validator(mode="after")
    def validate_stop_loss_take_profit(self):
        """Ensure stop loss and take profit make sense"""
        if self.action == "BUY":
            if self.stop_loss and self.take_profit:
                if self.stop_loss >= self.take_profit:
                    raise ValueError(
                        "For BUY: stop_loss must be < take_profit "
                        f"(got stop={self.stop_loss}, take={self.take_profit})"
                    )

        elif self.action == "SELL":
            if self.stop_loss and self.take_profit:
                if self.stop_loss <= self.take_profit:
                    raise ValueError(
                        "For SELL: stop_loss must be > take_profit "
                        f"(got stop={self.stop_loss}, take={self.take_profit})"
                    )

        return self


# ============================================================================
# Market Data Validation
# ============================================================================


class OHLCV(BaseModel):
    """Single OHLCV candle"""

    timestamp: int = Field(description="Unix timestamp in milliseconds")
    open: float = Field(gt=0, description="Open price")
    high: float = Field(gt=0, description="High price")
    low: float = Field(gt=0, description="Low price")
    close: float = Field(gt=0, description="Close price")
    volume: float = Field(ge=0, description="Trading volume")

    @model_validator(mode="after")
    def validate_ohlc(self):
        """Ensure OHLC values make sense"""
        if not (self.low <= self.open <= self.high):
            raise ValueError(
                f"Invalid OHLC: low={self.low}, open={self.open}, high={self.high}"
            )
        if not (self.low <= self.close <= self.high):
            raise ValueError(
                f"Invalid OHLC: low={self.low}, close={self.close}, high={self.high}"
            )
        return self


class MarketData(BaseModel):
    """Validated market data"""

    symbol: str = Field(description="Trading symbol (e.g., BTC/USDT)")
    timeframe: str = Field(description="Timeframe (e.g., 1m, 3m, 1h)")
    candles: List[OHLCV] = Field(min_length=1, description="OHLCV candles")

    @field_validator("candles")
    @classmethod
    def validate_candles_ordering(cls, v: List[OHLCV]) -> List[OHLCV]:
        """Ensure candles are ordered oldest → newest (CRITICAL for nof1 compatibility)"""
        if len(v) < 2:
            return v

        for i in range(1, len(v)):
            if v[i].timestamp <= v[i - 1].timestamp:
                raise ValueError(
                    f"Candles must be ordered oldest → newest. "
                    f"Found timestamp {v[i].timestamp} after {v[i-1].timestamp}"
                )

        return v


# ============================================================================
# Technical Indicators Validation
# ============================================================================


class TechnicalIndicators(BaseModel):
    """Validated technical indicators"""

    # Price-based
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None

    # Momentum
    rsi_7: Optional[float] = Field(default=None, ge=0, le=100)
    rsi_14: Optional[float] = Field(default=None, ge=0, le=100)

    # Trend
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None

    # Volatility
    atr_3: Optional[float] = Field(default=None, ge=0)
    atr_14: Optional[float] = Field(default=None, ge=0)

    # Volume
    volume: Optional[float] = Field(default=None, ge=0)

    # Futures-specific
    funding_rate: Optional[float] = None
    open_interest: Optional[float] = Field(default=None, ge=0)

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary, excluding None values"""
        return {k: v for k, v in self.model_dump().items() if v is not None}


# ============================================================================
# Validation Functions
# ============================================================================


def validate_llm_response(
    response: str | Dict[str, Any],
    model_name: str = "unknown",
) -> TradingDecision:
    """
    Validate and parse LLM response

    Args:
        response: Raw LLM response (JSON string or dict)
        model_name: Name of the model (for logging)

    Returns:
        Validated TradingDecision object

    Raises:
        ValueError: If response is invalid
        json.JSONDecodeError: If response is not valid JSON

    Example:
        >>> response = '{"action": "BUY", "confidence": 0.85, ...}'
        >>> decision = validate_llm_response(response, "deepseek")
        >>> print(decision.action)  # "BUY"
    """
    logger.debug("Validating LLM response", model=model_name)

    try:
        # Parse JSON if string
        if isinstance(response, str):
            data = json.loads(response)
        else:
            data = response

        # Validate with Pydantic
        decision = TradingDecision(**data)

        logger.info(
            "LLM response validated successfully",
            model=model_name,
            action=decision.action,
            confidence=decision.confidence,
        )

        return decision

    except json.JSONDecodeError as e:
        logger.error(
            "Invalid JSON in LLM response",
            model=model_name,
            error=str(e),
            response_preview=response[:200] if isinstance(response, str) else "N/A",
        )
        raise ValueError(f"Invalid JSON from {model_name}: {e}")

    except Exception as e:
        logger.error(
            "Invalid LLM response format",
            model=model_name,
            error=str(e),
            response_type=type(response).__name__,
        )
        raise ValueError(f"Invalid response from {model_name}: {e}")


def validate_market_data(
    candles: List[List[Any]],
    symbol: str,
    timeframe: str,
) -> MarketData:
    """
    Validate market data from exchange

    Args:
        candles: List of OHLCV candles [[timestamp, o, h, l, c, v], ...]
        symbol: Trading symbol
        timeframe: Timeframe

    Returns:
        Validated MarketData object

    Raises:
        ValueError: If data is invalid

    Example:
        >>> candles = [[1609459200000, 29000, 29500, 28800, 29200, 1000], ...]
        >>> data = validate_market_data(candles, "BTC/USDT", "1h")
    """
    logger.debug(
        "Validating market data",
        symbol=symbol,
        timeframe=timeframe,
        candle_count=len(candles),
    )

    try:
        # Convert to OHLCV objects
        ohlcv_list = []
        for candle in candles:
            if len(candle) < 6:
                raise ValueError(
                    f"Candle must have at least 6 values (got {len(candle)})"
                )

            ohlcv = OHLCV(
                timestamp=int(candle[0]),
                open=float(candle[1]),
                high=float(candle[2]),
                low=float(candle[3]),
                close=float(candle[4]),
                volume=float(candle[5]),
            )
            ohlcv_list.append(ohlcv)

        # Create and validate MarketData
        market_data = MarketData(
            symbol=symbol,
            timeframe=timeframe,
            candles=ohlcv_list,
        )

        logger.debug(
            "Market data validated successfully",
            symbol=symbol,
            timeframe=timeframe,
            candles=len(market_data.candles),
            first_timestamp=datetime.fromtimestamp(
                market_data.candles[0].timestamp / 1000
            ).isoformat(),
            last_timestamp=datetime.fromtimestamp(
                market_data.candles[-1].timestamp / 1000
            ).isoformat(),
        )

        return market_data

    except Exception as e:
        logger.error(
            "Invalid market data",
            symbol=symbol,
            timeframe=timeframe,
            error=str(e),
        )
        raise ValueError(f"Invalid market data for {symbol} {timeframe}: {e}")


def validate_indicators(
    indicators: Dict[str, float],
) -> TechnicalIndicators:
    """
    Validate technical indicators

    Args:
        indicators: Dictionary of indicator values

    Returns:
        Validated TechnicalIndicators object

    Raises:
        ValueError: If indicators are invalid

    Example:
        >>> indicators = {"rsi_14": 65.5, "macd": 120.3, "ema_20": 115000}
        >>> validated = validate_indicators(indicators)
    """
    logger.debug("Validating technical indicators", count=len(indicators))

    try:
        ti = TechnicalIndicators(**indicators)

        logger.debug(
            "Technical indicators validated",
            indicators=list(ti.to_dict().keys()),
        )

        return ti

    except Exception as e:
        logger.error(
            "Invalid technical indicators",
            error=str(e),
            indicators_keys=list(indicators.keys()),
        )
        raise ValueError(f"Invalid technical indicators: {e}")


# ============================================================================
# Response Sanitization
# ============================================================================


def sanitize_llm_response(response: str) -> str:
    """
    Sanitize LLM response, extracting JSON if embedded in text

    Sometimes LLMs return JSON wrapped in markdown code blocks or with
    additional text. This function extracts the JSON portion.

    Args:
        response: Raw LLM response

    Returns:
        Cleaned JSON string

    Example:
        >>> response = '''Here's my analysis:\n```json\n{"action": "BUY"}\n```'''
        >>> clean = sanitize_llm_response(response)
        >>> print(clean)  # '{"action": "BUY"}'
    """
    # Remove markdown code blocks
    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        response = response[start:end].strip()

    elif "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        response = response[start:end].strip()

    # Try to find JSON object
    if "{" in response and "}" in response:
        start = response.find("{")
        end = response.rfind("}") + 1
        response = response[start:end]

    return response.strip()


def validate_and_sanitize_llm_response(
    response: str,
    model_name: str = "unknown",
) -> TradingDecision:
    """
    Sanitize and validate LLM response in one step

    Args:
        response: Raw LLM response
        model_name: Name of the model

    Returns:
        Validated TradingDecision

    Example:
        >>> response = "I think you should ```json\n{...}\n``` because..."
        >>> decision = validate_and_sanitize_llm_response(response, "gpt4")
    """
    sanitized = sanitize_llm_response(response)
    return validate_llm_response(sanitized, model_name)
