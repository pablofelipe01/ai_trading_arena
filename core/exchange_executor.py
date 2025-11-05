"""
Exchange Executor for AI Trading Arena

Handles order execution in both paper trading and live modes.

Paper Trading:
- Simulates order execution with realistic slippage
- Tracks portfolio state
- No real money at risk

Live Trading:
- Real order execution via Binance API
- Proper risk management
- Circuit breakers

Usage:
    from core.exchange_executor import PaperExchange

    exchange = PaperExchange(initial_capital=100)
    order = exchange.execute_order(
        symbol="BTC/USDT",
        action="BUY",
        size=0.01,
        price=115000
    )
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from utils.config import get_config
from utils.errors import (
    InsufficientFundsError,
    InvalidOrderError,
    OrderExecutionError,
    CircuitBreakerTriggeredError,
)
from utils.logger import get_logger, log_trade
from utils.validator import validate_market_data

logger = get_logger(__name__)


# ============================================================================
# Order and Position Models
# ============================================================================


class Order:
    """Represents a trading order"""

    def __init__(
        self,
        order_id: str,
        symbol: str,
        action: str,
        size: float,
        price: float,
        timestamp: datetime,
        status: str = "pending",
    ):
        self.order_id = order_id
        self.symbol = symbol
        self.action = action
        self.size = size
        self.price = price
        self.timestamp = timestamp
        self.status = status
        self.executed_price: Optional[float] = None
        self.executed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "action": self.action,
            "size": self.size,
            "price": self.price,
            "status": self.status,
            "executed_price": self.executed_price,
            "timestamp": self.timestamp.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }


class Position:
    """Represents an open position"""

    def __init__(
        self,
        symbol: str,
        size: float,
        entry_price: float,
        entry_time: datetime,
    ):
        self.symbol = symbol
        self.size = size
        self.entry_price = entry_price
        self.entry_time = entry_time

    def calculate_pnl(self, current_price: float) -> Dict[str, float]:
        """Calculate current PnL"""
        pnl_amount = (current_price - self.entry_price) * self.size
        pnl_percent = (current_price / self.entry_price - 1) * 100

        return {
            "pnl_amount": pnl_amount,
            "pnl_percent": pnl_percent,
            "current_value": current_price * self.size,
            "entry_value": self.entry_price * self.size,
        }

    def to_dict(self, current_price: Optional[float] = None) -> Dict[str, Any]:
        """Convert to dictionary"""
        base = {
            "symbol": self.symbol,
            "size": self.size,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
        }

        if current_price:
            pnl = self.calculate_pnl(current_price)
            base.update(pnl)

        return base


# ============================================================================
# Paper Trading Exchange
# ============================================================================


class PaperExchange:
    """
    Paper trading exchange simulator

    Simulates order execution without real money.
    Includes realistic slippage and commission.
    """

    def __init__(self, initial_capital: float = 100.0):
        """
        Initialize paper exchange

        Args:
            initial_capital: Starting capital in USD
        """
        self.config = get_config()
        self.logger = get_logger("exchange.paper")

        # Account state
        self.initial_capital = initial_capital
        self.cash_balance = initial_capital
        self.positions: Dict[str, Position] = {}

        # Trading history
        self.orders: List[Order] = []
        self.trades: List[Dict[str, Any]] = []

        # Risk management
        self.max_daily_loss = initial_capital * self.config.trading.risk.max_daily_loss
        self.daily_pnl = 0.0
        self.circuit_breaker_active = False

        # Commission and slippage
        self.commission_rate = self.config.trading.execution.commission_rate
        self.slippage = self.config.trading.execution.slippage_simulation

        self.logger.info(
            "Paper exchange initialized",
            initial_capital=initial_capital,
            commission_rate=self.commission_rate,
            slippage=self.slippage,
        )

    def execute_order(
        self,
        symbol: str,
        action: str,
        size: float,
        price: float,
        model_name: str = "unknown",
        reasoning: str = "",
        confidence: float = 0.0,
    ) -> Order:
        """
        Execute a trading order

        Args:
            symbol: Trading symbol (e.g., "BTC/USDT")
            action: "BUY" or "SELL"
            size: Order size in base currency
            price: Expected execution price
            model_name: Name of the model placing order
            reasoning: Trading reasoning
            confidence: Model confidence

        Returns:
            Order object

        Raises:
            InsufficientFundsError: Not enough funds
            InvalidOrderError: Invalid order parameters
            CircuitBreakerTriggeredError: Circuit breaker active
        """
        # Check circuit breaker
        if self.circuit_breaker_active:
            raise CircuitBreakerTriggeredError(
                loss_percent=abs(self.daily_pnl / self.initial_capital * 100),
                threshold_percent=self.config.trading.risk.max_daily_loss * 100,
            )

        # Validate order
        self._validate_order(symbol, action, size, price)

        # Create order
        order = Order(
            order_id=str(uuid4()),
            symbol=symbol,
            action=action,
            size=size,
            price=price,
            timestamp=datetime.now(),
            status="pending",
        )

        self.logger.info(
            "Executing order",
            order_id=order.order_id,
            symbol=symbol,
            action=action,
            size=size,
            price=price,
            model=model_name,
        )

        try:
            # Simulate execution with slippage
            executed_price = self._apply_slippage(price, action)

            # Calculate costs
            order_value = executed_price * size
            commission = order_value * self.commission_rate
            total_cost = order_value + commission

            # Execute based on action
            if action == "BUY":
                self._execute_buy(symbol, size, executed_price, total_cost)
            elif action == "SELL":
                self._execute_sell(symbol, size, executed_price, commission)

            # Update order status
            order.status = "filled"
            order.executed_price = executed_price
            order.executed_at = datetime.now()

            # Record trade
            trade_record = {
                "order_id": order.order_id,
                "symbol": symbol,
                "action": action,
                "size": size,
                "price": executed_price,
                "commission": commission,
                "total_cost": total_cost,
                "timestamp": order.executed_at,
                "model": model_name,
                "reasoning": reasoning,
                "confidence": confidence,
            }
            self.trades.append(trade_record)

            # Log trade
            log_trade(
                model=model_name,
                symbol=symbol,
                action=action,
                size=size,
                price=executed_price,
                confidence=confidence,
                reasoning=reasoning,
                commission=commission,
            )

            self.logger.info(
                "Order executed successfully",
                order_id=order.order_id,
                executed_price=executed_price,
                commission=commission,
            )

        except Exception as e:
            order.status = "failed"
            self.logger.error(
                "Order execution failed",
                order_id=order.order_id,
                error=str(e),
            )
            raise OrderExecutionError(symbol, action, str(e))

        finally:
            self.orders.append(order)

        return order

    def _validate_order(
        self,
        symbol: str,
        action: str,
        size: float,
        price: float,
    ):
        """Validate order parameters"""
        if action not in ["BUY", "SELL"]:
            raise InvalidOrderError(f"Invalid action: {action}", action=action)

        if size <= 0:
            raise InvalidOrderError(f"Invalid size: {size}", size=size)

        if price <= 0:
            raise InvalidOrderError(f"Invalid price: {price}", price=price)

        # Check minimum order size
        order_value = size * price
        min_order = self.config.trading.execution.min_order_size_usd
        if order_value < min_order:
            raise InvalidOrderError(
                f"Order value ${order_value:.2f} below minimum ${min_order}",
                order_value=order_value,
                minimum=min_order,
            )

    def _apply_slippage(self, price: float, action: str) -> float:
        """Apply realistic slippage to price"""
        if action == "BUY":
            # Buy at slightly higher price
            return price * (1 + self.slippage)
        else:
            # Sell at slightly lower price
            return price * (1 - self.slippage)

    def _execute_buy(
        self,
        symbol: str,
        size: float,
        price: float,
        total_cost: float,
    ):
        """Execute buy order"""
        # Check if we have enough funds
        if total_cost > self.cash_balance:
            raise InsufficientFundsError(
                required=total_cost,
                available=self.cash_balance,
                symbol=symbol,
            )

        # Deduct from cash
        self.cash_balance -= total_cost

        # Add to or create position
        if symbol in self.positions:
            # Average up the position
            position = self.positions[symbol]
            total_value = (position.entry_price * position.size) + (price * size)
            total_size = position.size + size
            position.size = total_size
            position.entry_price = total_value / total_size
        else:
            # Create new position
            self.positions[symbol] = Position(
                symbol=symbol,
                size=size,
                entry_price=price,
                entry_time=datetime.now(),
            )

    def _execute_sell(
        self,
        symbol: str,
        size: float,
        price: float,
        commission: float,
    ):
        """Execute sell order"""
        # Check if we have the position
        if symbol not in self.positions:
            raise InvalidOrderError(
                f"No position to sell for {symbol}",
                symbol=symbol,
            )

        position = self.positions[symbol]
        if position.size < size:
            raise InvalidOrderError(
                f"Insufficient position size. Have {position.size}, trying to sell {size}",
                available=position.size,
                requested=size,
            )

        # Calculate PnL
        pnl = (price - position.entry_price) * size - commission
        self.daily_pnl += pnl

        # Check circuit breaker
        if self.daily_pnl < -self.max_daily_loss:
            self.circuit_breaker_active = True
            self.logger.warning(
                "Circuit breaker triggered!",
                daily_pnl=self.daily_pnl,
                max_loss=self.max_daily_loss,
            )

        # Add to cash
        sale_proceeds = price * size - commission
        self.cash_balance += sale_proceeds

        # Update or close position
        position.size -= size
        if position.size == 0:
            del self.positions[symbol]

    def get_account_state(
        self,
        current_prices: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Get current account state

        Args:
            current_prices: Dict of symbol → current price for open positions

        Returns:
            Account state dictionary
        """
        # Calculate position values
        position_value = 0.0
        positions_info = []

        if current_prices:
            for symbol, position in self.positions.items():
                if symbol in current_prices:
                    current_price = current_prices[symbol]
                    pnl = position.calculate_pnl(current_price)
                    position_value += pnl["current_value"]

                    pos_info = position.to_dict(current_price)
                    positions_info.append(pos_info)

        # Calculate total
        total_value = self.cash_balance + position_value
        total_return = (total_value / self.initial_capital - 1) * 100

        # Calculate win rate (track profitable vs unprofitable trades)
        # Build a map of BUY trades by symbol for profit calculation
        buy_history = {}  # symbol -> list of (price, size) tuples
        winning_trades = 0
        total_trades = 0

        for trade in self.trades:
            symbol = trade.get("symbol")
            action = trade.get("action")
            price = trade.get("price", 0)
            size = trade.get("size", 0)

            if action == "BUY":
                # Record buy for later profit calculation
                if symbol not in buy_history:
                    buy_history[symbol] = []
                buy_history[symbol].append((price, size))

            elif action == "SELL":
                # Count this as a trade
                total_trades += 1

                # Check if profitable (compare to average buy price)
                if symbol in buy_history and buy_history[symbol]:
                    # Calculate average entry price
                    total_value = sum(p * s for p, s in buy_history[symbol])
                    total_size = sum(s for _, s in buy_history[symbol])
                    avg_entry = total_value / total_size if total_size > 0 else 0

                    # Profitable if sold higher than bought (after costs)
                    # Break-even point: buy_price * (1 + commission) / (1 - commission)
                    # With 0.1% commission: 1.001 / 0.999 = 1.002002
                    if price > avg_entry * 1.002:
                        winning_trades += 1

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        return {
            "cash_balance": self.cash_balance,
            "position_value": position_value,
            "total_value": total_value,
            "available_balance": self.cash_balance,
            "initial_capital": self.initial_capital,
            "total_return": total_return,
            "total_return_pct": total_return,
            "daily_pnl": self.daily_pnl,
            "win_rate": win_rate,
            "total_trades": len(self.trades),
            "positions": positions_info,
            "circuit_breaker_active": self.circuit_breaker_active,
        }

    def reset_daily_tracking(self):
        """Reset daily tracking (call at start of each trading day)"""
        self.daily_pnl = 0.0
        self.circuit_breaker_active = False
        self.logger.info("Daily tracking reset")
