"""
Error Handling Framework for AI Trading Arena

Custom exceptions for different error scenarios:
- Configuration errors
- Market data errors
- LLM API errors
- Trading execution errors
- Validation errors

All exceptions inherit from ArenaError base class for easy catching.

Usage:
    from utils.errors import LLMAPIError, MarketDataError

    try:
        response = llm.generate()
    except LLMAPIError as e:
        logger.error("LLM failed", error=e)
        # Handle gracefully
"""

from typing import Any, Dict, Optional


# ============================================================================
# Base Exception
# ============================================================================


class ArenaError(Exception):
    """
    Base exception for all Arena errors

    All custom exceptions inherit from this for easy catching.
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize arena error

        Args:
            message: Human-readable error message
            code: Error code for programmatic handling
            context: Additional error context
        """
        self.message = message
        self.code = code or self.__class__.__name__
        self.context = context or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/API responses"""
        return {
            "error_type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "context": self.context,
        }

    def __str__(self) -> str:
        """String representation"""
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message


# ============================================================================
# Configuration Errors
# ============================================================================


class ConfigurationError(ArenaError):
    """Configuration-related errors"""

    pass


class MissingAPIKeyError(ConfigurationError):
    """API key not found in configuration"""

    def __init__(self, service: str):
        super().__init__(
            message=f"API key for '{service}' not found",
            code="MISSING_API_KEY",
            context={"service": service},
        )


class InvalidConfigError(ConfigurationError):
    """Invalid configuration value"""

    def __init__(self, field: str, value: Any, reason: str):
        super().__init__(
            message=f"Invalid configuration for '{field}': {reason}",
            code="INVALID_CONFIG",
            context={"field": field, "value": str(value), "reason": reason},
        )


# ============================================================================
# Market Data Errors
# ============================================================================


class MarketDataError(ArenaError):
    """Market data-related errors"""

    pass


class DataFetchError(MarketDataError):
    """Failed to fetch market data"""

    def __init__(self, symbol: str, timeframe: str, reason: str):
        super().__init__(
            message=f"Failed to fetch data for {symbol} {timeframe}: {reason}",
            code="DATA_FETCH_FAILED",
            context={
                "symbol": symbol,
                "timeframe": timeframe,
                "reason": reason,
            },
        )


class InvalidDataError(MarketDataError):
    """Market data validation failed"""

    def __init__(self, symbol: str, reason: str):
        super().__init__(
            message=f"Invalid data for {symbol}: {reason}",
            code="INVALID_DATA",
            context={"symbol": symbol, "reason": reason},
        )


class StaleDataError(MarketDataError):
    """Market data is too old"""

    def __init__(self, symbol: str, age_seconds: float, max_age_seconds: float):
        super().__init__(
            message=f"Data for {symbol} is stale ({age_seconds:.0f}s old, max {max_age_seconds:.0f}s)",
            code="STALE_DATA",
            context={
                "symbol": symbol,
                "age_seconds": age_seconds,
                "max_age_seconds": max_age_seconds,
            },
        )


# ============================================================================
# LLM API Errors
# ============================================================================


class LLMError(ArenaError):
    """LLM-related errors"""

    pass


class LLMAPIError(LLMError):
    """LLM API request failed"""

    def __init__(self, model: str, reason: str, status_code: Optional[int] = None):
        super().__init__(
            message=f"LLM API error for {model}: {reason}",
            code="LLM_API_ERROR",
            context={
                "model": model,
                "reason": reason,
                "status_code": status_code,
            },
        )


class LLMTimeoutError(LLMError):
    """LLM request timed out"""

    def __init__(self, model: str, timeout_seconds: float):
        super().__init__(
            message=f"LLM request timed out for {model} after {timeout_seconds}s",
            code="LLM_TIMEOUT",
            context={"model": model, "timeout": timeout_seconds},
        )


class LLMRateLimitError(LLMError):
    """LLM rate limit exceeded"""

    def __init__(self, model: str, retry_after: Optional[float] = None):
        super().__init__(
            message=f"Rate limit exceeded for {model}",
            code="LLM_RATE_LIMIT",
            context={"model": model, "retry_after": retry_after},
        )


class LLMResponseError(LLMError):
    """LLM response invalid or unparseable"""

    def __init__(self, model: str, reason: str, raw_response: Optional[str] = None):
        super().__init__(
            message=f"Invalid response from {model}: {reason}",
            code="LLM_RESPONSE_ERROR",
            context={
                "model": model,
                "reason": reason,
                "response_preview": (
                    raw_response[:200] if raw_response else None
                ),
            },
        )


# ============================================================================
# Trading Execution Errors
# ============================================================================


class TradingError(ArenaError):
    """Trading execution errors"""

    pass


class OrderExecutionError(TradingError):
    """Failed to execute order"""

    def __init__(self, symbol: str, action: str, reason: str):
        super().__init__(
            message=f"Failed to execute {action} order for {symbol}: {reason}",
            code="ORDER_EXECUTION_FAILED",
            context={"symbol": symbol, "action": action, "reason": reason},
        )


class InsufficientFundsError(TradingError):
    """Insufficient funds for trade"""

    def __init__(self, required: float, available: float, symbol: str):
        super().__init__(
            message=f"Insufficient funds for {symbol}: need ${required:.2f}, have ${available:.2f}",
            code="INSUFFICIENT_FUNDS",
            context={
                "required": required,
                "available": available,
                "symbol": symbol,
            },
        )


class InvalidOrderError(TradingError):
    """Order parameters invalid"""

    def __init__(self, reason: str, **kwargs):
        super().__init__(
            message=f"Invalid order: {reason}",
            code="INVALID_ORDER",
            context=kwargs,
        )


class CircuitBreakerTriggeredError(TradingError):
    """Circuit breaker triggered due to losses"""

    def __init__(self, loss_percent: float, threshold_percent: float):
        super().__init__(
            message=f"Circuit breaker triggered: loss {loss_percent:.2f}% exceeds threshold {threshold_percent:.2f}%",
            code="CIRCUIT_BREAKER",
            context={
                "loss_percent": loss_percent,
                "threshold": threshold_percent,
            },
        )


# ============================================================================
# Validation Errors
# ============================================================================


class ValidationError(ArenaError):
    """Validation errors"""

    pass


class SchemaValidationError(ValidationError):
    """Data schema validation failed"""

    def __init__(self, schema: str, errors: list):
        super().__init__(
            message=f"Schema validation failed for {schema}",
            code="SCHEMA_VALIDATION_FAILED",
            context={"schema": schema, "errors": errors},
        )


# ============================================================================
# Arena Errors
# ============================================================================


class ArenaStateError(ArenaError):
    """Arena state errors"""

    pass


class InvalidStateError(ArenaStateError):
    """Operation not allowed in current state"""

    def __init__(self, current_state: str, required_state: str, operation: str):
        super().__init__(
            message=f"Cannot {operation} in state {current_state} (requires {required_state})",
            code="INVALID_STATE",
            context={
                "current_state": current_state,
                "required_state": required_state,
                "operation": operation,
            },
        )


# ============================================================================
# Helper Functions
# ============================================================================


def handle_error(
    error: Exception,
    component: str,
    context: Optional[Dict[str, Any]] = None,
    raise_after_log: bool = True,
) -> None:
    """
    Centralized error handling with logging

    Args:
        error: Exception that occurred
        component: Component where error occurred
        context: Additional context
        raise_after_log: Whether to re-raise after logging

    Example:
        try:
            # Some operation
            pass
        except Exception as e:
            handle_error(e, "data_fetcher", {"symbol": "BTC/USDT"})
    """
    from utils.logger import log_error

    # Determine if this is a fatal error
    fatal_errors = (
        MissingAPIKeyError,
        InvalidConfigError,
        CircuitBreakerTriggeredError,
    )
    is_fatal = isinstance(error, fatal_errors)

    # Log the error
    log_error(
        component=component,
        error=error,
        context=context,
        fatal=is_fatal,
    )

    # Re-raise if requested
    if raise_after_log:
        raise error


def is_retriable_error(error: Exception) -> bool:
    """
    Check if an error is retriable

    Args:
        error: Exception to check

    Returns:
        True if error can be retried

    Example:
        try:
            # API call
            pass
        except Exception as e:
            if is_retriable_error(e):
                # Retry
                pass
    """
    retriable_errors = (
        LLMTimeoutError,
        LLMRateLimitError,
        DataFetchError,
    )
    return isinstance(error, retriable_errors)


def get_retry_delay(error: Exception) -> float:
    """
    Get recommended retry delay for an error

    Args:
        error: Exception that occurred

    Returns:
        Delay in seconds before retry

    Example:
        try:
            # API call
            pass
        except Exception as e:
            if is_retriable_error(e):
                delay = get_retry_delay(e)
                time.sleep(delay)
                # Retry
    """
    if isinstance(error, LLMRateLimitError):
        # Use retry_after from error context if available
        if hasattr(error, "context") and "retry_after" in error.context:
            return error.context["retry_after"] or 60
        return 60  # Default 1 minute

    if isinstance(error, LLMTimeoutError):
        return 5  # Short delay for timeout

    if isinstance(error, DataFetchError):
        return 2  # Very short delay for data fetch

    return 10  # Default delay


# ============================================================================
# Context Manager for Error Handling
# ============================================================================


class error_context:
    """
    Context manager for consistent error handling

    Usage:
        with error_context("data_fetching", symbol="BTC/USDT"):
            # Your code here
            fetch_data()

        # Or with custom error handling
        with error_context("llm_call", model="gpt4", suppress=True):
            # Won't raise, just logs
            llm.generate()
    """

    def __init__(
        self,
        component: str,
        suppress: bool = False,
        **context_kwargs,
    ):
        """
        Initialize error context

        Args:
            component: Component name
            suppress: If True, suppress exceptions after logging
            **context_kwargs: Additional context
        """
        self.component = component
        self.suppress = suppress
        self.context = context_kwargs

    def __enter__(self):
        """Enter context"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context, handling any exceptions"""
        if exc_val:
            handle_error(
                exc_val,
                self.component,
                self.context,
                raise_after_log=not self.suppress,
            )
            return self.suppress  # Suppress if requested
        return False
