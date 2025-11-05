"""
LLM Manager for AI Trading Arena

Coordinates multiple LLM models trading simultaneously.
Each model has its own paper trading account and competes independently.

Key responsibilities:
- Initialize multiple LLM clients
- Coordinate trading decisions
- Track performance per model
- Handle failures gracefully
- Manage concurrent execution

Usage:
    from models.llm_manager import LLMManager

    manager = LLMManager()
    await manager.initialize()
    results = await manager.get_all_decisions(prompt, symbol, price)
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.exchange_executor import PaperExchange
from models.llm_client import create_llm_client, BaseLLMClient
from utils.config import get_config
from utils.errors import LLMAPIError, LLMResponseError
from utils.logger import get_logger
from utils.validator import TradingDecision


logger = get_logger(__name__)


# ============================================================================
# Model State Tracker
# ============================================================================


class ModelState:
    """
    Tracks state for a single model

    Includes:
    - LLM client
    - Paper exchange
    - Performance metrics
    - Error tracking
    """

    def __init__(
        self,
        provider: str,
        priority: int,
        initial_capital: float
    ):
        """
        Initialize model state

        Args:
            provider: Provider name
            priority: Model priority (1 = highest)
            initial_capital: Starting capital
        """
        self.provider = provider
        self.priority = priority
        self.initial_capital = initial_capital

        # Will be initialized later
        self.client: Optional[BaseLLMClient] = None
        self.exchange: Optional[PaperExchange] = None

        # Performance tracking
        self.decisions_made = 0
        self.trades_executed = 0
        self.errors = 0
        self.last_decision_time: Optional[datetime] = None
        self.total_latency = 0.0

        # Status
        self.enabled = True
        self.error_message: Optional[str] = None

    def record_decision(self, latency: float):
        """Record a successful decision"""
        self.decisions_made += 1
        self.last_decision_time = datetime.now()
        self.total_latency += latency

    def record_trade(self):
        """Record a trade execution"""
        self.trades_executed += 1

    def record_error(self, error: str):
        """Record an error"""
        self.errors += 1
        self.error_message = error

    def get_avg_latency(self) -> float:
        """Get average latency"""
        if self.decisions_made == 0:
            return 0.0
        return self.total_latency / self.decisions_made

    def get_performance(self) -> Dict[str, Any]:
        """Get performance metrics"""
        account_state = self.exchange.get_account_state() if self.exchange else {}

        return {
            "provider": self.provider,
            "priority": self.priority,
            "enabled": self.enabled,
            "decisions_made": self.decisions_made,
            "trades_executed": self.trades_executed,
            "errors": self.errors,
            "avg_latency": self.get_avg_latency(),
            "last_decision": self.last_decision_time.isoformat() if self.last_decision_time else None,
            "account_value": account_state.get("total_value", 0.0),
            "return_pct": account_state.get("total_return_pct", 0.0),
            "win_rate": account_state.get("win_rate", 0.0),
            "total_trades": account_state.get("total_trades", 0),
        }


# ============================================================================
# LLM Manager
# ============================================================================


class LLMManager:
    """
    Manages multiple LLM models trading concurrently

    Each model operates independently with its own paper trading account.
    The manager coordinates requests and tracks performance.
    """

    def __init__(self):
        """Initialize LLM manager"""
        self.config = get_config()
        self.logger = get_logger("llm.manager")

        # Model states
        self.models: Dict[str, ModelState] = {}

        # Session tracking
        self.session_start = datetime.now()
        self.total_decisions = 0

        self.logger.info("LLM manager initialized")

    async def initialize(self):
        """
        Initialize all enabled models

        Creates LLM clients and paper exchanges for each enabled model.
        """
        self.logger.info("Initializing LLM models...")

        # Get enabled models sorted by priority
        enabled_models = []
        for provider in ["deepseek", "openai", "anthropic", "groq"]:
            model_config = getattr(self.config.models, provider, None)
            if model_config and model_config.enabled:
                enabled_models.append((
                    provider,
                    model_config.priority
                ))

        enabled_models.sort(key=lambda x: x[1])  # Sort by priority

        # Initialize each model
        for provider, priority in enabled_models:
            try:
                self.logger.info(
                    "Initializing model",
                    provider=provider,
                    priority=priority
                )

                # Create model state
                state = ModelState(
                    provider=provider,
                    priority=priority,
                    initial_capital=self.config.trading.capital_per_model
                )

                # Create LLM client
                state.client = create_llm_client(provider)

                # Create paper exchange
                state.exchange = PaperExchange(
                    initial_capital=self.config.trading.capital_per_model
                )

                self.models[provider] = state

                self.logger.info(
                    "Model initialized",
                    provider=provider,
                    capital=state.initial_capital
                )

            except Exception as e:
                self.logger.error(
                    "Failed to initialize model",
                    provider=provider,
                    error=str(e),
                    exc_info=True
                )

        if not self.models:
            raise RuntimeError("No models could be initialized")

        self.logger.info(
            "LLM manager ready",
            models=len(self.models),
            providers=list(self.models.keys())
        )

    async def get_all_decisions(
        self,
        prompt: str,
        symbol: str,
        current_price: float
    ) -> Dict[str, Optional[TradingDecision]]:
        """
        Get trading decisions from all enabled models

        Requests are made concurrently for performance.

        Args:
            prompt: Trading prompt
            symbol: Trading symbol
            current_price: Current price

        Returns:
            Dict of provider → decision (None if failed)
        """
        self.logger.info(
            "Requesting decisions from all models",
            models=len(self.models)
        )

        # Create tasks for all models
        tasks = []
        providers = []

        for provider, state in self.models.items():
            if state.enabled and state.client:
                tasks.append(
                    self._get_decision_with_error_handling(
                        state, prompt, symbol, current_price
                    )
                )
                providers.append(provider)

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build results dict
        decisions = {}
        for provider, result in zip(providers, results):
            if isinstance(result, Exception):
                self.logger.error(
                    "Model decision failed",
                    provider=provider,
                    error=str(result)
                )
                decisions[provider] = None
            else:
                decisions[provider] = result

        self.total_decisions += len([d for d in decisions.values() if d is not None])

        return decisions

    async def _get_decision_with_error_handling(
        self,
        state: ModelState,
        prompt: str,
        symbol: str,
        current_price: float
    ) -> Optional[TradingDecision]:
        """
        Get decision with error handling

        Args:
            state: Model state
            prompt: Trading prompt
            symbol: Trading symbol
            current_price: Current price

        Returns:
            TradingDecision or None if failed
        """
        import time

        try:
            start_time = time.time()

            decision = await state.client.get_trading_decision(
                prompt=prompt,
                symbol=symbol,
                current_price=current_price
            )

            latency = time.time() - start_time
            state.record_decision(latency)

            return decision

        except (LLMAPIError, LLMResponseError) as e:
            state.record_error(str(e))
            self.logger.warning(
                "Model decision failed",
                provider=state.provider,
                error=str(e)
            )
            return None

        except Exception as e:
            state.record_error(str(e))
            self.logger.error(
                "Unexpected error getting decision",
                provider=state.provider,
                error=str(e),
                exc_info=True
            )
            return None

    async def execute_decisions(
        self,
        decisions: Dict[str, Optional[TradingDecision]],
        symbol: str,
        current_price: float
    ) -> Dict[str, bool]:
        """
        Execute trading decisions

        Args:
            decisions: Dict of provider → decision
            symbol: Trading symbol
            current_price: Current price

        Returns:
            Dict of provider → success
        """
        results = {}

        for provider, decision in decisions.items():
            if decision is None:
                results[provider] = False
                continue

            state = self.models[provider]

            try:
                # Execute based on action
                if decision.action == "BUY":
                    # Calculate position size (cap at 5% per trade)
                    available = state.exchange.cash_balance
                    capped_position_size = min(decision.position_size, 0.05)
                    position_value = available * capped_position_size
                    size = position_value / current_price

                    # Execute buy
                    state.exchange.execute_order(
                        symbol=symbol,
                        action="BUY",
                        size=size,
                        price=current_price,
                        model_name=provider,
                        reasoning=decision.reasoning,
                        confidence=decision.confidence
                    )

                    state.record_trade()
                    results[provider] = True

                elif decision.action == "SELL":
                    # Check if we have a position
                    if symbol in state.exchange.positions:
                        position = state.exchange.positions[symbol]

                        # Calculate size to sell
                        size = position.size * decision.position_size

                        # Execute sell
                        state.exchange.execute_order(
                            symbol=symbol,
                            action="SELL",
                            size=size,
                            price=current_price,
                            model_name=provider,
                            reasoning=decision.reasoning,
                            confidence=decision.confidence
                        )

                        state.record_trade()
                        results[provider] = True
                    else:
                        self.logger.warning(
                            "Cannot sell - no position",
                            provider=provider,
                            symbol=symbol
                        )
                        results[provider] = False

                else:  # HOLD
                    self.logger.debug(
                        "Model chose to hold",
                        provider=provider
                    )
                    results[provider] = True

            except Exception as e:
                self.logger.error(
                    "Failed to execute decision",
                    provider=provider,
                    action=decision.action,
                    error=str(e),
                    exc_info=True
                )
                state.record_error(str(e))
                results[provider] = False

        return results

    async def get_all_multi_asset_decisions(
        self,
        symbols: List[str],
        market_data_all: Dict[str, Dict[str, Any]],
        current_prices: Dict[str, float],
        session_info: Dict[str, Any]
    ) -> Dict[str, Optional[List[TradingDecision]]]:
        """
        Get multi-asset trading decisions from all models

        For Level 1: Each model gets data for all 8 assets and decides
        which assets to trade.

        Args:
            symbols: List of all trading symbols
            market_data_all: Dict of symbol → market data
            current_prices: Dict of symbol → current price
            session_info: Session metadata

        Returns:
            Dict of provider → list of decisions (one per asset they want to trade)
        """
        from strategies.prompt_templates import PromptTemplateManager

        self.logger.info(
            "Requesting multi-asset decisions from all models",
            models=len(self.models),
            symbols=len(symbols)
        )

        # Get prompt template manager
        template_manager = PromptTemplateManager()

        # Create tasks for all models
        tasks = []
        providers = []

        for provider, state in self.models.items():
            if state.enabled and state.client:
                tasks.append(
                    self._get_multi_asset_decision_with_error_handling(
                        state=state,
                        symbols=symbols,
                        market_data_all=market_data_all,
                        current_prices=current_prices,
                        session_info=session_info,
                        template_manager=template_manager
                    )
                )
                providers.append(provider)

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build results dict
        decisions = {}
        for provider, result in zip(providers, results):
            if isinstance(result, Exception):
                self.logger.error(
                    "Model multi-asset decision failed",
                    provider=provider,
                    error=str(result)
                )
                decisions[provider] = None
            else:
                decisions[provider] = result

        self.total_decisions += sum(len(d) for d in decisions.values() if d is not None)

        return decisions

    async def _get_multi_asset_decision_with_error_handling(
        self,
        state: ModelState,
        symbols: List[str],
        market_data_all: Dict[str, Dict[str, Any]],
        current_prices: Dict[str, float],
        session_info: Dict[str, Any],
        template_manager: Any
    ) -> Optional[List[TradingDecision]]:
        """Get multi-asset decision with error handling"""
        import time
        from utils.validator import validate_llm_response, MultiAssetDecisions

        try:
            start_time = time.time()

            # Get account info from exchange
            account_info = state.exchange.get_account_state(current_prices=current_prices)

            # Build Level 1 multi-asset prompt
            prompt = template_manager.generate_prompt(
                template_version="level1_multi_asset",
                symbols=symbols,
                market_data_all=market_data_all,
                account_info=account_info,
                session_info=session_info
            )

            # Get LLM response
            response = await state.client._call_api(prompt)

            # Validate response (expect array of decisions)
            validated = validate_llm_response(response, state.provider, multi_asset=True)

            latency = time.time() - start_time
            state.record_decision(latency)

            # Return list of decisions
            if isinstance(validated, MultiAssetDecisions):
                return validated.decisions
            else:
                # Single decision, wrap in list
                return [validated]

        except (LLMAPIError, LLMResponseError) as e:
            state.record_error(str(e))
            self.logger.warning(
                "Model multi-asset decision failed",
                provider=state.provider,
                error=str(e)
            )
            return None

        except Exception as e:
            state.record_error(str(e))
            self.logger.error(
                "Unexpected error getting multi-asset decision",
                provider=state.provider,
                error=str(e),
                exc_info=True
            )
            return None

    async def execute_multi_asset_decisions(
        self,
        decisions: Dict[str, Optional[List[TradingDecision]]],
        current_prices: Dict[str, float]
    ) -> Dict[str, int]:
        """
        Execute multi-asset trading decisions

        Args:
            decisions: Dict of provider → list of decisions
            current_prices: Dict of symbol → current price

        Returns:
            Dict of provider → number of successful executions
        """
        results = {}

        for provider, decision_list in decisions.items():
            if decision_list is None:
                results[provider] = 0
                continue

            state = self.models[provider]
            success_count = 0

            for decision in decision_list:
                try:
                    symbol = decision.symbol
                    if not symbol or symbol not in current_prices:
                        self.logger.warning(
                            "Invalid or missing symbol in decision",
                            provider=provider,
                            symbol=symbol
                        )
                        continue

                    current_price = current_prices[symbol]

                    # Execute based on action
                    if decision.action == "BUY":
                        # Calculate position size (cap at 5% per trade)
                        available = state.exchange.cash_balance
                        capped_position_size = min(decision.position_size, 0.05)
                        position_value = available * capped_position_size
                        size = position_value / current_price

                        # Execute buy
                        state.exchange.execute_order(
                            symbol=symbol,
                            action="BUY",
                            size=size,
                            price=current_price,
                            model_name=provider,
                            reasoning=decision.reasoning,
                            confidence=decision.confidence
                        )

                        state.record_trade()
                        success_count += 1

                    elif decision.action == "SELL":
                        # Check if we have a position
                        if symbol in state.exchange.positions:
                            position = state.exchange.positions[symbol]

                            # Calculate size to sell
                            size = position.size * decision.position_size

                            # Execute sell
                            state.exchange.execute_order(
                                symbol=symbol,
                                action="SELL",
                                size=size,
                                price=current_price,
                                model_name=provider,
                                reasoning=decision.reasoning,
                                confidence=decision.confidence
                            )

                            state.record_trade()
                            success_count += 1
                        else:
                            self.logger.warning(
                                "Cannot sell - no position",
                                provider=provider,
                                symbol=symbol
                            )

                    else:  # HOLD
                        self.logger.debug(
                            "Model chose to hold",
                            provider=provider,
                            symbol=symbol
                        )
                        success_count += 1

                except Exception as e:
                    self.logger.error(
                        "Failed to execute decision",
                        provider=provider,
                        symbol=decision.symbol if decision else "unknown",
                        action=decision.action if decision else "unknown",
                        error=str(e),
                        exc_info=True
                    )
                    state.record_error(str(e))

            results[provider] = success_count

        return results

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """
        Get performance leaderboard

        Returns list sorted by return percentage (best first).

        Returns:
            List of model performance dicts
        """
        performances = [
            state.get_performance()
            for state in self.models.values()
        ]

        # Sort by return percentage
        performances.sort(key=lambda x: x["return_pct"], reverse=True)

        return performances

    def get_summary(self) -> Dict[str, Any]:
        """
        Get overall summary

        Returns:
            Summary statistics
        """
        leaderboard = self.get_leaderboard()

        return {
            "session_start": self.session_start.isoformat(),
            "session_duration_minutes": (datetime.now() - self.session_start).total_seconds() / 60,
            "total_models": len(self.models),
            "total_decisions": self.total_decisions,
            "leaderboard": leaderboard,
            "leader": leaderboard[0] if leaderboard else None,
        }

    async def close(self):
        """Close all clients"""
        self.logger.info("Closing LLM manager")

        # Close any async resources if needed
        for state in self.models.values():
            if hasattr(state.client, 'close'):
                try:
                    await state.client.close()
                except:
                    pass

        self.logger.info("LLM manager closed")
