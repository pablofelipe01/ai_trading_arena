"""
Logger System for AI Trading Arena

Professional logging system using Loguru with:
- Beautiful colored console output
- File rotation and compression
- Structured JSON logging
- Context-aware logging (per component)
- Performance tracking
- Trading decision logging

Usage:
    from utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Trading decision made", symbol="BTC/USDT", action="BUY")
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from utils.config import get_config


# ============================================================================
# Custom Log Levels
# ============================================================================

# Add custom log levels for trading-specific events
logger.level("TRADE", no=38, color="<green>", icon="💰")
logger.level("DECISION", no=35, color="<yellow>", icon="🤔")
logger.level("SIGNAL", no=33, color="<cyan>", icon="📊")


# ============================================================================
# Logger Configuration
# ============================================================================


class LoggerManager:
    """
    Centralized logger management

    Features:
    - Console logging with colors
    - File logging with rotation
    - Structured JSON logging
    - Context injection (component, model, etc.)
    - Performance tracking
    """

    def __init__(self):
        """Initialize logger manager"""
        self._initialized = False
        self._config = None
        self._loggers: Dict[str, Any] = {}

    def init(self, config=None):
        """
        Initialize logging system

        Args:
            config: Configuration object (optional)
        """
        if self._initialized:
            return

        # Get configuration
        if config is None:
            config = get_config()
        self._config = config.logging

        # Remove default logger
        logger.remove()

        # Setup console logging
        if self._config.console.enabled:
            logger.add(
                sys.stderr,
                format=self._config.console.format,
                level=self._config.level,
                colorize=self._config.console.colorize,
                backtrace=True,
                diagnose=True,
            )

        # Setup file logging
        if self._config.file.enabled:
            log_path = Path(self._config.file.path)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            logger.add(
                log_path,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                level=self._config.level,
                rotation=self._config.file.rotation,
                retention=self._config.file.retention,
                compression=self._config.file.compression,
                backtrace=True,
                diagnose=True,
            )

        # Setup structured logging
        if self._config.structured.enabled:
            struct_path = Path(self._config.structured.path)
            struct_path.parent.mkdir(parents=True, exist_ok=True)

            logger.add(
                struct_path,
                format="{message}",
                level=self._config.level,
                serialize=True,  # JSON format
                backtrace=True,
                diagnose=True,
            )

        self._initialized = True
        logger.info("🚀 Logger system initialized", level=self._config.level)

    def get_logger(self, name: str, context: Optional[Dict[str, Any]] = None):
        """
        Get a context-aware logger

        Args:
            name: Logger name (usually __name__)
            context: Additional context (model, symbol, etc.)

        Returns:
            Configured logger with context
        """
        if not self._initialized:
            self.init()

        # Create unique key for this logger
        context_key = name
        if context:
            context_key += "_" + "_".join(f"{k}={v}" for k, v in sorted(context.items()))

        # Return cached logger if exists
        if context_key in self._loggers:
            return self._loggers[context_key]

        # Bind context to logger
        if context:
            ctx_logger = logger.bind(name=name, **context)
        else:
            ctx_logger = logger.bind(name=name)

        self._loggers[context_key] = ctx_logger
        return ctx_logger


# ============================================================================
# Global Logger Manager Instance
# ============================================================================

_manager = LoggerManager()


def init_logger(config=None):
    """
    Initialize global logger

    Args:
        config: Optional configuration object
    """
    _manager.init(config)


def get_logger(name: str, **context) -> logger:
    """
    Get a logger with context

    Args:
        name: Logger name (usually __name__)
        **context: Additional context kwargs

    Returns:
        Configured logger

    Example:
        logger = get_logger(__name__, model="deepseek", symbol="BTC/USDT")
        logger.info("Making trading decision")
    """
    return _manager.get_logger(name, context if context else None)


# ============================================================================
# Specialized Logging Functions
# ============================================================================


def log_trade(
    model: str,
    symbol: str,
    action: str,
    size: float,
    price: float,
    confidence: float,
    reasoning: str,
    **extra,
):
    """
    Log a trading decision

    Args:
        model: Model name (deepseek, gpt4, etc.)
        symbol: Trading symbol (BTC/USDT)
        action: BUY | SELL | HOLD
        size: Position size
        price: Entry price
        confidence: Model confidence (0-1)
        reasoning: Model's reasoning
        **extra: Additional context
    """
    trade_logger = get_logger("trading.decisions", model=model, symbol=symbol)

    trade_logger.log(
        "TRADE",
        "Trade executed",
        action=action,
        size=size,
        price=price,
        confidence=confidence,
        reasoning=reasoning,
        **extra,
    )


def log_decision(
    model: str,
    symbol: str,
    action: str,
    confidence: float,
    reasoning: str,
    indicators: Dict[str, Any],
    **extra,
):
    """
    Log a trading decision (before execution)

    Args:
        model: Model name
        symbol: Trading symbol
        action: Proposed action
        confidence: Model confidence
        reasoning: Model's reasoning
        indicators: Technical indicators at decision time
        **extra: Additional context
    """
    decision_logger = get_logger("trading.analysis", model=model, symbol=symbol)

    decision_logger.log(
        "DECISION",
        "Trading decision made",
        action=action,
        confidence=confidence,
        reasoning=reasoning,
        indicators=indicators,
        **extra,
    )


def log_signal(
    symbol: str,
    timeframe: str,
    signal_type: str,
    value: float,
    threshold: Optional[float] = None,
    **extra,
):
    """
    Log a technical signal

    Args:
        symbol: Trading symbol
        timeframe: Timeframe (1m, 3m, etc.)
        signal_type: Signal type (RSI_OVERSOLD, MACD_CROSS, etc.)
        value: Signal value
        threshold: Threshold crossed (if applicable)
        **extra: Additional context
    """
    signal_logger = get_logger("market.signals", symbol=symbol, timeframe=timeframe)

    signal_logger.log(
        "SIGNAL",
        f"Signal detected: {signal_type}",
        signal_type=signal_type,
        value=value,
        threshold=threshold,
        **extra,
    )


def log_performance(
    model: str,
    total_return: float,
    sharpe_ratio: float,
    win_rate: float,
    max_drawdown: float,
    total_trades: int,
    **extra,
):
    """
    Log model performance metrics

    Args:
        model: Model name
        total_return: Total return percentage
        sharpe_ratio: Sharpe ratio
        win_rate: Win rate (0-1)
        max_drawdown: Maximum drawdown
        total_trades: Total number of trades
        **extra: Additional metrics
    """
    perf_logger = get_logger("arena.performance", model=model)

    perf_logger.info(
        "Performance update",
        total_return=f"{total_return:.2f}%",
        sharpe_ratio=f"{sharpe_ratio:.2f}",
        win_rate=f"{win_rate*100:.1f}%",
        max_drawdown=f"{max_drawdown:.2f}%",
        total_trades=total_trades,
        **extra,
    )


def log_market_data(
    symbol: str,
    timeframe: str,
    price: float,
    volume: float,
    indicators: Dict[str, float],
    **extra,
):
    """
    Log market data update

    Args:
        symbol: Trading symbol
        timeframe: Timeframe
        price: Current price
        volume: Current volume
        indicators: Calculated indicators
        **extra: Additional data
    """
    data_logger = get_logger("market.data", symbol=symbol, timeframe=timeframe)

    data_logger.debug(
        "Market data update",
        price=price,
        volume=volume,
        indicators=indicators,
        **extra,
    )


def log_llm_request(
    model: str,
    prompt_length: int,
    response_length: int,
    latency_ms: float,
    cost_usd: float,
    **extra,
):
    """
    Log LLM API request

    Args:
        model: Model name
        prompt_length: Prompt length in tokens
        response_length: Response length in tokens
        latency_ms: Request latency in milliseconds
        cost_usd: API cost in USD
        **extra: Additional data
    """
    llm_logger = get_logger("llm.requests", model=model)

    llm_logger.debug(
        "LLM request completed",
        prompt_tokens=prompt_length,
        response_tokens=response_length,
        latency_ms=f"{latency_ms:.2f}",
        cost_usd=f"${cost_usd:.4f}",
        **extra,
    )


def log_error(
    component: str,
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    fatal: bool = False,
):
    """
    Log an error with context

    Args:
        component: Component where error occurred
        error: Exception object
        context: Additional context
        fatal: Whether this is a fatal error
    """
    error_logger = get_logger(f"errors.{component}")

    level = "CRITICAL" if fatal else "ERROR"

    error_logger.log(
        level,
        f"{'FATAL ' if fatal else ''}Error in {component}: {error}",
        error_type=type(error).__name__,
        error_message=str(error),
        context=context or {},
        exc_info=True,
    )


# ============================================================================
# Context Managers
# ============================================================================


class log_execution_time:
    """
    Context manager to log execution time

    Usage:
        with log_execution_time("data_fetching", symbol="BTC/USDT"):
            # Your code here
            fetch_market_data()
    """

    def __init__(self, operation: str, **context):
        """
        Initialize timer

        Args:
            operation: Operation name
            **context: Additional context
        """
        self.operation = operation
        self.context = context
        self.logger = get_logger(f"performance.{operation}", **context)

    def __enter__(self):
        """Start timing"""
        import time

        self.start_time = time.time()
        self.logger.debug(f"Starting: {self.operation}", **self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End timing and log"""
        import time

        elapsed_ms = (time.time() - self.start_time) * 1000

        if exc_type:
            self.logger.error(
                f"Failed: {self.operation}",
                elapsed_ms=f"{elapsed_ms:.2f}",
                error=str(exc_val),
                **self.context,
            )
        else:
            self.logger.debug(
                f"Completed: {self.operation}",
                elapsed_ms=f"{elapsed_ms:.2f}",
                **self.context,
            )


# ============================================================================
# Initialization
# ============================================================================

# Auto-initialize on import (but can be re-initialized with config)
try:
    init_logger()
except Exception as e:
    # Fallback to basic logging if config not available
    logger.add(sys.stderr, level="INFO")
    logger.warning(f"Logger initialized with defaults (config not available): {e}")
