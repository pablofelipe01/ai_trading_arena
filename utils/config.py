"""
Configuration Manager for AI Trading Arena

This module provides robust configuration management using Pydantic models
for validation and type safety. It loads configuration from:
1. config/config.yaml - Base configuration
2. .env file - Environment variables (API keys, secrets)
3. Environment overrides - Runtime configuration

Usage:
    from utils.config import config

    # Access configuration
    capital = config.trading.capital_per_model
    api_key = config.get_api_key('deepseek')
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================================
# Risk Management Configuration
# ============================================================================


class RiskConfig(BaseModel):
    """Risk management parameters"""

    max_risk_per_trade: float = Field(
        default=0.02,
        ge=0.0,
        le=1.0,
        description="Maximum risk per trade (fraction of capital)",
    )
    max_position_size: float = Field(
        default=0.20, ge=0.0, le=1.0, description="Maximum position size"
    )
    max_daily_loss: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Maximum daily loss before circuit breaker",
    )
    enable_circuit_breaker: bool = Field(
        default=True, description="Enable circuit breaker on losses"
    )
    enable_emergency_stop: bool = Field(
        default=True, description="Enable manual emergency stop"
    )


class ExecutionConfig(BaseModel):
    """Order execution configuration"""

    slippage_simulation: float = Field(
        default=0.001, ge=0.0, description="Simulated slippage in paper mode"
    )
    commission_rate: float = Field(
        default=0.001, ge=0.0, description="Trading commission rate"
    )
    min_order_size_usd: float = Field(default=10.0, gt=0.0, description="Minimum order size in USD")


class TradingConfig(BaseModel):
    """Trading configuration"""

    mode: Literal["paper", "live"] = Field(
        default="paper", description="Trading mode (always start with paper!)"
    )
    capital_per_model: float = Field(
        default=100.0, gt=0.0, description="Starting capital per model in USD"
    )
    risk: RiskConfig = Field(default_factory=RiskConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Ensure trading mode is valid"""
        if v == "live":
            import warnings

            warnings.warn(
                "⚠️  LIVE TRADING ENABLED - USE WITH EXTREME CAUTION!",
                UserWarning,
                stacklevel=2,
            )
        return v


# ============================================================================
# Exchange Configuration
# ============================================================================


class RateLimitsConfig(BaseModel):
    """API rate limits"""

    requests_per_minute: int = Field(default=1200, gt=0)
    order_per_second: int = Field(default=10, gt=0)
    weight_per_minute: int = Field(default=6000, gt=0)


class ExchangeConfig(BaseModel):
    """Exchange API configuration"""

    name: str = Field(default="binance")
    testnet: bool = Field(default=True, description="Use testnet for paper trading")
    symbols: List[str] = Field(default=["BTC/USDT"])
    rate_limits: RateLimitsConfig = Field(default_factory=RateLimitsConfig)


# ============================================================================
# Data Configuration
# ============================================================================


class IndicatorsConfig(BaseModel):
    """Technical indicators configuration"""

    ema: Dict[str, List[int]] = Field(default={"periods": [20, 50]})
    macd: Dict[str, int] = Field(default={"fast": 12, "slow": 26, "signal": 9})
    rsi: Dict[str, List[int]] = Field(default={"periods": [7, 14]})
    atr: Dict[str, List[int]] = Field(default={"periods": [3, 14]})
    include_volume: bool = True
    include_funding_rate: bool = True
    include_open_interest: bool = True


class CacheConfig(BaseModel):
    """Data caching configuration"""

    enabled: bool = True
    ttl_seconds: int = Field(default=60, gt=0)


class DataConfig(BaseModel):
    """Market data configuration"""

    timeframes: Dict[str, Any] = Field(
        default={
            "primary": "3m",
            "context": ["1m", "15m", "1h", "4h"],
        }
    )
    candle_limits: Dict[str, int] = Field(
        default={
            "1m": 60,
            "3m": 100,
            "15m": 96,
            "1h": 168,
            "4h": 180,
        }
    )
    indicators: IndicatorsConfig = Field(default_factory=IndicatorsConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    ordering: Literal["oldest_to_newest"] = Field(
        default="oldest_to_newest",
        description="CRITICAL: Always oldest → newest for nof1 compatibility",
    )


# ============================================================================
# Prompt Configuration
# ============================================================================


class PromptSectionsConfig(BaseModel):
    """Control which sections to include in prompts"""

    include_market_state: bool = True
    include_price_series: bool = True
    include_indicators: bool = True
    include_funding_rate: bool = True
    include_open_interest: bool = True
    include_recent_performance: bool = True
    include_portfolio_state: bool = True


class PromptsConfig(BaseModel):
    """Prompt engineering configuration"""

    template_version: Literal["nof1_exact", "simplified", "advanced", "minimal"] = Field(
        default="nof1_exact", description="Template version selection"
    )
    templates_dir: str = "strategies/templates"
    enable_ab_testing: bool = False
    max_tokens: int = Field(default=8000, gt=0)
    sections: PromptSectionsConfig = Field(default_factory=PromptSectionsConfig)


# ============================================================================
# LLM Model Configuration
# ============================================================================


class APIConfig(BaseModel):
    """LLM API configuration"""

    base_url: str
    model: str
    timeout: int = Field(default=30, gt=0)
    provider: Optional[str] = None  # For Llama (groq | together)


class LLMParametersConfig(BaseModel):
    """LLM generation parameters"""

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, gt=0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)
    max_retries: int = Field(default=3, gt=0)
    retry_delay: float = Field(default=2.0, gt=0.0)
    max_requests_per_minute: int = Field(default=100, gt=0)
    timeout: int = Field(default=30, gt=0)


class RateLimitConfig(BaseModel):
    """LLM rate limiting"""

    calls_per_minute: int = Field(default=100, gt=0)


class CostConfig(BaseModel):
    """LLM cost tracking"""

    input_per_1m_tokens: float = Field(default=0.0, ge=0.0)
    output_per_1m_tokens: float = Field(default=0.0, ge=0.0)


class MetadataConfig(BaseModel):
    """LLM metadata for display"""

    narrative: str
    color: str = "#FFFFFF"


class LLMModelConfig(BaseModel):
    """Individual LLM model configuration"""

    enabled: bool = True
    priority: int = Field(gt=0, description="Lower number = higher priority")
    api: Optional[APIConfig] = None
    parameters: Optional[LLMParametersConfig] = Field(default_factory=LLMParametersConfig)
    rate_limit: Optional[RateLimitConfig] = Field(default_factory=RateLimitConfig)
    cost: Optional[CostConfig] = Field(default_factory=CostConfig)
    metadata: MetadataConfig

    @model_validator(mode="after")
    def validate_enabled_has_api(self):
        """Ensure enabled models have complete API configuration"""
        if self.enabled and not self.api:
            raise ValueError("Enabled models must have API configuration")
        return self


class ModelsConfig(BaseModel):
    """All LLM models configuration"""

    deepseek: Optional[LLMModelConfig] = None
    openai: Optional[LLMModelConfig] = None
    anthropic: Optional[LLMModelConfig] = None
    groq: Optional[LLMModelConfig] = None
    gemini: Optional[LLMModelConfig] = None
    qwen: Optional[LLMModelConfig] = None

    def get_enabled_models(self) -> Dict[str, LLMModelConfig]:
        """Get all enabled models"""
        enabled = {}
        for name, model in self.__dict__.items():
            if model and model.enabled:
                enabled[name] = model
        return enabled

    def get_model_by_priority(self) -> List[tuple[str, LLMModelConfig]]:
        """Get enabled models sorted by priority"""
        enabled = self.get_enabled_models()
        return sorted(enabled.items(), key=lambda x: x[1].priority)


# ============================================================================
# Arena Configuration
# ============================================================================


class LeaderboardConfig(BaseModel):
    """Leaderboard configuration"""

    update_frequency: int = Field(default=300, gt=0, description="Update interval in seconds")
    metrics: List[str] = Field(
        default=[
            "total_return_pct",
            "sharpe_ratio",
            "win_rate",
            "max_drawdown",
            "total_trades",
            "avg_trade_duration",
        ]
    )


class PersistenceConfig(BaseModel):
    """Results persistence configuration"""

    save_decisions: bool = True
    save_prompts: bool = True
    save_responses: bool = True
    export_format: List[str] = Field(default=["json", "csv"])


class SessionDurationConfig(BaseModel):
    """Competition duration limits"""

    default: int = Field(default=86400, gt=0, description="24 hours")
    max: int = Field(default=2592000, gt=0, description="30 days")


class ArenaConfig(BaseModel):
    """Arena manager configuration"""

    decision_interval: int = Field(
        default=180, gt=0, description="Decision interval in seconds (3 min like nof1)"
    )
    parallel_execution: bool = True
    max_concurrent_llm_calls: int = Field(default=4, gt=0)
    session_duration: SessionDurationConfig = Field(default_factory=SessionDurationConfig)
    leaderboard: LeaderboardConfig = Field(default_factory=LeaderboardConfig)
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)


# ============================================================================
# Logging Configuration
# ============================================================================


class ConsoleLoggingConfig(BaseModel):
    """Console logging configuration"""

    enabled: bool = True
    colorize: bool = True
    format: str = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"


class FileLoggingConfig(BaseModel):
    """File logging configuration"""

    enabled: bool = True
    path: str = "data/logs/arena.log"
    rotation: str = "100 MB"
    retention: str = "30 days"
    compression: str = "zip"


class StructuredLoggingConfig(BaseModel):
    """Structured logging configuration"""

    enabled: bool = True
    path: str = "data/logs/structured.jsonl"


class LoggingConfig(BaseModel):
    """Logging system configuration"""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    console: ConsoleLoggingConfig = Field(default_factory=ConsoleLoggingConfig)
    file: FileLoggingConfig = Field(default_factory=FileLoggingConfig)
    structured: StructuredLoggingConfig = Field(default_factory=StructuredLoggingConfig)


# ============================================================================
# Main Configuration
# ============================================================================


class MetaConfig(BaseModel):
    """Metadata about the configuration"""

    version: str = "0.1.0"
    phase: str = "PHASE_1_IN_PROGRESS"
    last_updated: str
    nof1_compatible: bool = True


class AppConfig(BaseModel):
    """Complete application configuration"""

    trading: TradingConfig = Field(default_factory=TradingConfig)
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    prompts: PromptsConfig = Field(default_factory=PromptsConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    arena: ArenaConfig = Field(default_factory=ArenaConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    meta: MetaConfig

    @model_validator(mode="after")
    def validate_config(self):
        """Cross-field validation"""
        # Ensure at least one model is enabled
        enabled_models = self.models.get_enabled_models()
        if not enabled_models:
            raise ValueError("At least one LLM model must be enabled")

        # Warn if using live mode
        if self.trading.mode == "live":
            print("⚠️  WARNING: LIVE TRADING MODE ENABLED")

        return self


# ============================================================================
# Environment Settings (for API keys and secrets)
# ============================================================================


class Settings(BaseSettings):
    """Environment variables and secrets"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Trading
    trading_mode: str = "paper"
    capital_per_model: float = 100.0

    # Exchange
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True

    # LLM APIs
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""

    # Optional tier 2
    gemini_api_key: str = ""
    qwen_api_key: str = ""


# ============================================================================
# Config Manager
# ============================================================================


class ConfigManager:
    """
    Centralized configuration manager

    Usage:
        from utils.config import config

        # Access configuration
        capital = config.trading.capital_per_model

        # Get API key
        api_key = config.get_api_key('deepseek')

        # Get enabled models
        models = config.models.get_enabled_models()
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager

        Args:
            config_path: Path to config.yaml file
        """
        if config_path is None:
            # Default to config/config.yaml relative to project root
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "config.yaml"

        self.config_path = config_path
        self.settings = Settings()
        self.config = self._load_config()

    def _load_config(self) -> AppConfig:
        """Load and validate configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            config_dict = yaml.safe_load(f)

        # Create AppConfig from dictionary
        return AppConfig(**config_dict)

    def get_api_key(self, service: str) -> str:
        """
        Get API key for a service

        Args:
            service: Service name (deepseek, openai, anthropic, groq, etc.)

        Returns:
            API key from environment variables

        Raises:
            ValueError: If API key is not set
        """
        key_attr = f"{service}_api_key"
        api_key = getattr(self.settings, key_attr, "")

        if not api_key:
            raise ValueError(
                f"API key for '{service}' not found. "
                f"Please set {key_attr.upper()} in your .env file"
            )

        return api_key

    def reload(self):
        """Reload configuration from file"""
        self.settings = Settings()
        self.config = self._load_config()

    def __getattr__(self, name):
        """Allow direct access to config attributes"""
        return getattr(self.config, name)


# ============================================================================
# Global Config Instance
# ============================================================================

# Singleton instance - import this in other modules
config: Optional[ConfigManager] = None


def init_config(config_path: Optional[Path] = None) -> ConfigManager:
    """
    Initialize global configuration

    Args:
        config_path: Optional path to config.yaml

    Returns:
        ConfigManager instance
    """
    global config
    config = ConfigManager(config_path)
    return config


def get_config() -> ConfigManager:
    """
    Get global configuration instance

    Returns:
        ConfigManager instance

    Raises:
        RuntimeError: If config not initialized
    """
    if config is None:
        return init_config()
    return config
