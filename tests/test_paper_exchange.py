"""
Test Paper Exchange Implementation

Tests for the PaperExchange class to verify:
- Order execution
- Position tracking
- Circuit breaker
- PnL calculation
- Commission and slippage
"""

import pytest
from datetime import datetime

from core.exchange_executor import PaperExchange, Order, Position
from utils.errors import (
    InsufficientFundsError,
    InvalidOrderError,
    CircuitBreakerTriggeredError,
)


class TestPaperExchange:
    """Test suite for PaperExchange"""

    def test_initialization(self):
        """Test exchange initialization"""
        exchange = PaperExchange(initial_capital=100.0)

        assert exchange.initial_capital == 100.0
        assert exchange.cash_balance == 100.0
        assert len(exchange.positions) == 0
        assert len(exchange.orders) == 0
        assert exchange.circuit_breaker_active == False

    def test_buy_order_execution(self):
        """Test successful buy order"""
        exchange = PaperExchange(initial_capital=100.0)

        # Execute buy order
        order = exchange.execute_order(
            symbol="BTC/USDT",
            action="BUY",
            size=0.001,
            price=50000.0,
            model_name="test_model",
            reasoning="Test buy",
            confidence=0.8,
        )

        # Verify order
        assert order.status == "filled"
        assert order.action == "BUY"
        assert order.symbol == "BTC/USDT"
        assert order.executed_price is not None

        # Verify position created
        assert "BTC/USDT" in exchange.positions
        position = exchange.positions["BTC/USDT"]
        assert position.size == 0.001

        # Verify cash deducted (price + slippage + commission)
        expected_cost = 50000.0 * 0.001 * (1 + 0.001) * (1 + 0.001)  # slippage + commission
        assert exchange.cash_balance < 100.0
        assert exchange.cash_balance > 100.0 - expected_cost - 1.0  # Allow small rounding

    def test_sell_order_execution(self):
        """Test successful sell order"""
        exchange = PaperExchange(initial_capital=100.0)

        # First buy
        exchange.execute_order(
            symbol="BTC/USDT",
            action="BUY",
            size=0.001,
            price=50000.0,
            model_name="test_model",
        )

        initial_balance = exchange.cash_balance

        # Then sell
        order = exchange.execute_order(
            symbol="BTC/USDT",
            action="SELL",
            size=0.001,
            price=51000.0,  # Profit
            model_name="test_model",
            reasoning="Test sell",
            confidence=0.7,
        )

        # Verify order
        assert order.status == "filled"
        assert order.action == "SELL"

        # Verify position closed
        assert "BTC/USDT" not in exchange.positions

        # Verify cash increased (profitable trade)
        assert exchange.cash_balance > initial_balance

    def test_insufficient_funds(self):
        """Test insufficient funds error"""
        exchange = PaperExchange(initial_capital=100.0)

        with pytest.raises(InsufficientFundsError):
            exchange.execute_order(
                symbol="BTC/USDT",
                action="BUY",
                size=0.01,  # Too large
                price=50000.0,
                model_name="test_model",
            )

    def test_invalid_order_params(self):
        """Test invalid order parameters"""
        exchange = PaperExchange(initial_capital=100.0)

        # Invalid action
        with pytest.raises(InvalidOrderError):
            exchange.execute_order(
                symbol="BTC/USDT",
                action="INVALID",
                size=0.001,
                price=50000.0,
            )

        # Invalid size
        with pytest.raises(InvalidOrderError):
            exchange.execute_order(
                symbol="BTC/USDT",
                action="BUY",
                size=-0.001,
                price=50000.0,
            )

        # Invalid price
        with pytest.raises(InvalidOrderError):
            exchange.execute_order(
                symbol="BTC/USDT",
                action="BUY",
                size=0.001,
                price=-50000.0,
            )

    def test_sell_without_position(self):
        """Test selling without position"""
        exchange = PaperExchange(initial_capital=100.0)

        with pytest.raises(InvalidOrderError):
            exchange.execute_order(
                symbol="BTC/USDT",
                action="SELL",
                size=0.001,
                price=50000.0,
            )

    def test_circuit_breaker(self):
        """Test circuit breaker triggers on losses"""
        exchange = PaperExchange(initial_capital=100.0)

        # Buy high
        exchange.execute_order(
            symbol="BTC/USDT",
            action="BUY",
            size=0.001,
            price=50000.0,
        )

        # Sell low (trigger loss)
        exchange.execute_order(
            symbol="BTC/USDT",
            action="SELL",
            size=0.001,
            price=40000.0,  # -20% loss
        )

        # Circuit breaker should be active
        assert exchange.circuit_breaker_active == True

        # Next order should fail
        with pytest.raises(CircuitBreakerTriggeredError):
            exchange.execute_order(
                symbol="BTC/USDT",
                action="BUY",
                size=0.001,
                price=50000.0,
            )

    def test_position_averaging(self):
        """Test position averaging on multiple buys"""
        exchange = PaperExchange(initial_capital=200.0)

        # First buy
        exchange.execute_order(
            symbol="BTC/USDT",
            action="BUY",
            size=0.001,
            price=50000.0,
        )

        # Second buy at different price
        exchange.execute_order(
            symbol="BTC/USDT",
            action="BUY",
            size=0.001,
            price=52000.0,
        )

        # Verify position averaged
        position = exchange.positions["BTC/USDT"]
        assert position.size == 0.002
        assert position.entry_price > 50000.0
        assert position.entry_price < 52000.0

    def test_partial_sell(self):
        """Test partial position sell"""
        exchange = PaperExchange(initial_capital=200.0)

        # Buy
        exchange.execute_order(
            symbol="BTC/USDT",
            action="BUY",
            size=0.002,
            price=50000.0,
        )

        # Sell half
        exchange.execute_order(
            symbol="BTC/USDT",
            action="SELL",
            size=0.001,
            price=51000.0,
        )

        # Verify position remains
        assert "BTC/USDT" in exchange.positions
        position = exchange.positions["BTC/USDT"]
        assert position.size == 0.001

    def test_account_state(self):
        """Test get_account_state method"""
        exchange = PaperExchange(initial_capital=100.0)

        # Initial state
        state = exchange.get_account_state()
        assert state["cash_balance"] == 100.0
        assert state["total_value"] == 100.0
        assert state["total_return_pct"] == 0.0
        assert len(state["positions"]) == 0

        # After buying
        exchange.execute_order(
            symbol="BTC/USDT",
            action="BUY",
            size=0.001,
            price=50000.0,
        )

        state = exchange.get_account_state(current_prices={"BTC/USDT": 51000.0})
        assert state["cash_balance"] < 100.0
        assert len(state["positions"]) == 1
        assert state["position_value"] > 0

    def test_pnl_calculation(self):
        """Test PnL calculation for positions"""
        position = Position(
            symbol="BTC/USDT",
            size=0.001,
            entry_price=50000.0,
            entry_time=datetime.now(),
        )

        # Test profit
        pnl = position.calculate_pnl(current_price=51000.0)
        assert pnl["pnl_amount"] == 1.0  # (51000 - 50000) * 0.001
        assert pnl["pnl_percent"] == 2.0

        # Test loss
        pnl = position.calculate_pnl(current_price=49000.0)
        assert pnl["pnl_amount"] == -1.0
        assert pnl["pnl_percent"] == -2.0

    def test_min_order_size(self):
        """Test minimum order size validation"""
        exchange = PaperExchange(initial_capital=100.0)

        # Order too small (min is $5 by default)
        with pytest.raises(InvalidOrderError):
            exchange.execute_order(
                symbol="BTC/USDT",
                action="BUY",
                size=0.00001,
                price=50000.0,
            )

    def test_reset_daily_tracking(self):
        """Test daily tracking reset"""
        exchange = PaperExchange(initial_capital=100.0)

        # Simulate loss
        exchange.daily_pnl = -10.0
        exchange.circuit_breaker_active = True

        # Reset
        exchange.reset_daily_tracking()

        assert exchange.daily_pnl == 0.0
        assert exchange.circuit_breaker_active == False


if __name__ == "__main__":
    # Run basic smoke test
    print("Running PaperExchange smoke test...")

    exchange = PaperExchange(initial_capital=100.0)
    print(f"✓ Exchange initialized with ${exchange.cash_balance:.2f}")

    # Buy order
    order = exchange.execute_order(
        symbol="BTC/USDT",
        action="BUY",
        size=0.001,
        price=50000.0,
        model_name="smoke_test",
        reasoning="Testing buy order",
        confidence=0.8,
    )
    print(f"✓ Buy order executed: {order.order_id}")

    # Check account state
    state = exchange.get_account_state(current_prices={"BTC/USDT": 50500.0})
    print(f"✓ Account state: ${state['total_value']:.2f} ({state['total_return_pct']:.2f}%)")

    # Sell order
    order = exchange.execute_order(
        symbol="BTC/USDT",
        action="SELL",
        size=0.001,
        price=50500.0,
        model_name="smoke_test",
        reasoning="Testing sell order",
        confidence=0.7,
    )
    print(f"✓ Sell order executed: {order.order_id}")

    # Final state
    state = exchange.get_account_state()
    print(f"✓ Final balance: ${state['cash_balance']:.2f}")
    print(f"✓ Total trades: {state['total_trades']}")

    print("\n✅ All smoke tests passed!")
