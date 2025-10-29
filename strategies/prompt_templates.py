"""
Prompt Template System for AI Trading Arena

This module implements the prompt generation system, including:
- NOF1 exact template (replica of nof1.ai winning format)
- Simplified templates for testing
- Advanced templates with additional data
- Dynamic variable injection
- Multi-timeframe data formatting

The NOF1 format is CRITICAL - it's proven to work with DeepSeek's +11.06% win.

Usage:
    from strategies.prompt_templates import PromptTemplateManager

    manager = PromptTemplateManager()
    prompt = manager.generate_prompt(
        template_version="nof1_exact",
        market_data=data,
        account_info=account
    )
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# Base Template Class
# ============================================================================


class PromptTemplate(ABC):
    """
    Base class for all prompt templates

    All templates must implement the generate() method.
    """

    def __init__(self, name: str, description: str):
        """
        Initialize template

        Args:
            name: Template name
            description: Template description
        """
        self.name = name
        self.description = description
        self.logger = get_logger(f"prompt.{name}")

    @abstractmethod
    def generate(self, **kwargs) -> str:
        """
        Generate prompt from template

        Args:
            **kwargs: Template variables

        Returns:
            Generated prompt string
        """
        pass

    def _format_list(self, values: List[float], precision: int = 3) -> str:
        """
        Format a list of floats for display

        Args:
            values: List of float values
            precision: Decimal precision

        Returns:
            Formatted string like "[1.234, 5.678, ...]"
        """
        if not values:
            return "[]"

        formatted = [f"{v:.{precision}f}" for v in values]
        return f"[{', '.join(formatted)}]"

    def _format_timestamp(self, timestamp: datetime) -> str:
        """
        Format timestamp for display

        Args:
            timestamp: Datetime object

        Returns:
            Formatted timestamp string
        """
        return timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")


# ============================================================================
# NOF1 Exact Template (CRITICAL - The Winning Format)
# ============================================================================


class NOF1ExactTemplate(PromptTemplate):
    """
    Exact replica of the nof1.ai prompt format

    This is the format that DeepSeek used to achieve +11.06% returns.
    DO NOT modify this format unless you have strong evidence it will improve.

    Key characteristics:
    - Oldest → newest data ordering (CRITICAL)
    - 3-minute primary timeframe
    - Multiple indicator series
    - Narrative introduction with time context
    - Account performance summary
    """

    def __init__(self):
        super().__init__(
            name="nof1_exact",
            description="Exact replica of nof1.ai winning format (+11.06% with DeepSeek)"
        )

    def generate(
        self,
        symbol: str,
        current_price: float,
        indicators: Dict[str, float],
        price_series: Dict[str, List[float]],
        indicator_series: Dict[str, List[float]],
        account_info: Dict[str, Any],
        session_info: Dict[str, Any],
        **kwargs
    ) -> str:
        """
        Generate NOF1-style prompt

        Args:
            symbol: Trading symbol (e.g., "BTC/USDT")
            current_price: Current market price
            indicators: Current indicator values
            price_series: Price series by timeframe
            indicator_series: Indicator series (EMA, MACD, RSI, etc.)
            account_info: Account state (balance, positions, performance)
            session_info: Session metadata (time, invocations, etc.)

        Returns:
            NOF1-formatted prompt string
        """
        self.logger.debug("Generating NOF1 exact prompt", symbol=symbol)

        # Extract session info
        minutes_elapsed = session_info.get("minutes_elapsed", 0)
        current_time = session_info.get("current_time", datetime.now())
        invocations = session_info.get("invocations", 0)

        # Build the prompt using the exact NOF1 format
        prompt = f"""It has been {minutes_elapsed} minutes since you started trading. The current time is {self._format_timestamp(current_time)} and you've been invoked {invocations} times. Below, we are providing you with a variety of stats data, price data, and predictive signals so you can discover alpha. Below that is your current account information, value, performance, positions, etc.

ALL OF THE PRICE OR SIGNAL DATA BELOW IS ORDERED: OLDEST → NEWEST

Timeframes note: Unless stated otherwise in a section title, intraday series are provided at 3-minute intervals. If a coin uses a different interval, it is explicitly stated in that coin's section.

CURRENT MARKET STATE FOR ALL COINS

ALL {symbol.replace('/', '')} DATA
Current_price = {current_price:.1f}, current_ema20 = {indicators.get('ema_20', 0):.3f}, current_macd = {indicators.get('macd', 0):.3f}, current_rsi (7 period) = {indicators.get('rsi_7', 0):.3f}

"""

        # Add price series for each timeframe
        for timeframe, prices in price_series.items():
            if not prices:
                continue

            prompt += f"\nPrice Series ({timeframe}, oldest → latest):\n"
            prompt += f"Mid prices: {self._format_list(prices, precision=1)}\n"

        # Add indicator series
        if "ema_20_series" in indicator_series:
            prompt += f"\nEMA indicators (20-period): {self._format_list(indicator_series['ema_20_series'], precision=3)}\n"

        if "macd_series" in indicator_series:
            prompt += f"MACD indicators: {self._format_list(indicator_series['macd_series'], precision=3)}\n"

        if "rsi_14_series" in indicator_series:
            prompt += f"RSI indicators (14-Period): {self._format_list(indicator_series['rsi_14_series'], precision=3)}\n"

        # Add account information
        prompt += f"""

YOUR CURRENT ACCOUNT INFORMATION

Account Value: ${account_info.get('total_value', 0):.2f}
Available Balance: ${account_info.get('available_balance', 0):.2f}
Total Return: {account_info.get('total_return_pct', 0):.2f}%
Win Rate: {account_info.get('win_rate', 0):.1f}%
Total Trades: {account_info.get('total_trades', 0)}

"""

        # Add current positions if any
        positions = account_info.get('positions', [])
        if positions:
            prompt += "CURRENT POSITIONS:\n"
            for pos in positions:
                prompt += f"  {pos['symbol']}: {pos['size']:.4f} @ ${pos['entry_price']:.2f} (PnL: {pos['pnl_pct']:.2f}%)\n"
        else:
            prompt += "CURRENT POSITIONS: None\n"

        prompt += """

Based on the above data, what trading action should be taken? Respond with a JSON object containing:
- action: "BUY", "SELL", or "HOLD"
- confidence: float between 0 and 1
- reasoning: detailed explanation of your decision
- position_size: fraction of available capital to use (0 to 1)
- stop_loss: optional stop loss price
- take_profit: optional take profit price

Your response:"""

        return prompt


# ============================================================================
# Simplified Template (For Testing)
# ============================================================================


class SimplifiedTemplate(PromptTemplate):
    """
    Simplified template with less data

    Good for:
    - Testing the system
    - Debugging LLM responses
    - Educational purposes
    - When you want faster inference
    """

    def __init__(self):
        super().__init__(
            name="simplified",
            description="Simplified template for testing and debugging"
        )

    def generate(
        self,
        symbol: str,
        current_price: float,
        indicators: Dict[str, float],
        account_info: Dict[str, Any],
        **kwargs
    ) -> str:
        """Generate simplified prompt"""

        self.logger.debug("Generating simplified prompt", symbol=symbol)

        prompt = f"""Trading Decision Request for {symbol}

Current Market State:
- Price: ${current_price:.2f}
- RSI (14): {indicators.get('rsi_14', 0):.1f}
- MACD: {indicators.get('macd', 0):.2f}

Your Account:
- Balance: ${account_info.get('available_balance', 0):.2f}
- Return: {account_info.get('total_return_pct', 0):.2f}%

What action should be taken? Respond with JSON:
{{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0 to 1.0,
  "reasoning": "your explanation",
  "position_size": 0.0 to 1.0
}}"""

        return prompt


# ============================================================================
# Advanced Template (Experimental)
# ============================================================================


class AdvancedTemplate(PromptTemplate):
    """
    Advanced template with additional data

    Includes:
    - Order flow data
    - Liquidation levels
    - Funding rates
    - Open interest
    - Volume profile
    """

    def __init__(self):
        super().__init__(
            name="advanced",
            description="Advanced template with order flow and liquidations"
        )

    def generate(
        self,
        symbol: str,
        current_price: float,
        indicators: Dict[str, float],
        price_series: Dict[str, List[float]],
        indicator_series: Dict[str, List[float]],
        account_info: Dict[str, Any],
        session_info: Dict[str, Any],
        order_flow: Optional[Dict[str, Any]] = None,
        funding_rate: Optional[float] = None,
        open_interest: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate advanced prompt with extra data"""

        self.logger.debug("Generating advanced prompt", symbol=symbol)

        # Start with NOF1 base
        nof1 = NOF1ExactTemplate()
        prompt = nof1.generate(
            symbol=symbol,
            current_price=current_price,
            indicators=indicators,
            price_series=price_series,
            indicator_series=indicator_series,
            account_info=account_info,
            session_info=session_info
        )

        # Add advanced data
        advanced_section = "\nADVANCED MARKET DATA\n\n"

        if funding_rate is not None:
            advanced_section += f"Funding Rate: {funding_rate:.6f}%\n"

        if open_interest is not None:
            advanced_section += f"Open Interest: ${open_interest:,.0f}\n"

        if order_flow:
            advanced_section += f"\nOrder Flow:\n"
            advanced_section += f"  Buy Volume: {order_flow.get('buy_volume', 0):,.0f}\n"
            advanced_section += f"  Sell Volume: {order_flow.get('sell_volume', 0):,.0f}\n"
            advanced_section += f"  Buy/Sell Ratio: {order_flow.get('ratio', 0):.2f}\n"

        # Insert advanced section before the final question
        prompt = prompt.replace(
            "Based on the above data",
            advanced_section + "\nBased on the above data"
        )

        return prompt


# ============================================================================
# Prompt Template Manager
# ============================================================================


class PromptTemplateManager:
    """
    Manages all prompt templates

    Usage:
        manager = PromptTemplateManager()
        prompt = manager.generate_prompt(
            template_version="nof1_exact",
            symbol="BTC/USDT",
            ...
        )
    """

    def __init__(self):
        """Initialize template manager"""
        self.logger = get_logger("prompt.manager")

        # Register all templates
        self.templates: Dict[str, PromptTemplate] = {
            "nof1_exact": NOF1ExactTemplate(),
            "simplified": SimplifiedTemplate(),
            "advanced": AdvancedTemplate(),
        }

        self.logger.info(
            "Prompt template manager initialized",
            templates=list(self.templates.keys())
        )

    def generate_prompt(
        self,
        template_version: str,
        **kwargs
    ) -> str:
        """
        Generate prompt using specified template

        Args:
            template_version: Template to use
            **kwargs: Template variables

        Returns:
            Generated prompt string

        Raises:
            ValueError: If template not found
        """
        if template_version not in self.templates:
            raise ValueError(
                f"Template '{template_version}' not found. "
                f"Available: {list(self.templates.keys())}"
            )

        template = self.templates[template_version]

        self.logger.debug(
            "Generating prompt",
            template=template_version,
            symbol=kwargs.get("symbol", "unknown")
        )

        try:
            prompt = template.generate(**kwargs)

            self.logger.info(
                "Prompt generated successfully",
                template=template_version,
                prompt_length=len(prompt),
                symbol=kwargs.get("symbol", "unknown")
            )

            return prompt

        except Exception as e:
            self.logger.error(
                "Failed to generate prompt",
                template=template_version,
                error=str(e)
            )
            raise

    def get_available_templates(self) -> List[str]:
        """Get list of available template names"""
        return list(self.templates.keys())

    def get_template_info(self, template_version: str) -> Dict[str, str]:
        """
        Get information about a template

        Args:
            template_version: Template name

        Returns:
            Dict with name and description
        """
        if template_version not in self.templates:
            raise ValueError(f"Template '{template_version}' not found")

        template = self.templates[template_version]
        return {
            "name": template.name,
            "description": template.description
        }
