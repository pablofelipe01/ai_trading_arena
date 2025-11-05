"""
FASE 3 Integration Test

End-to-end test that verifies:
1. Binance data fetcher retrieves real market data
2. Prompt builder generates NOF1-style prompts
3. PaperExchange executes trades
4. Account tracking works correctly
5. Complete trading flow works

This test demonstrates all FASE 3 components working together.
"""

import asyncio
from datetime import datetime

from core.data_fetcher import BinanceDataFetcher
from core.exchange_executor import PaperExchange
from strategies.prompts import PromptBuilder


async def test_complete_trading_flow():
    """
    Test the complete trading flow from data → prompt → execution
    """
    print("=" * 80)
    print("FASE 3 INTEGRATION TEST")
    print("=" * 80)
    print()

    # =========================================================================
    # STEP 1: Initialize Components
    # =========================================================================
    print("Step 1: Initializing components...")

    data_fetcher = BinanceDataFetcher()
    prompt_builder = PromptBuilder()
    exchange = PaperExchange(initial_capital=100.0)

    print(f"✓ Data fetcher initialized")
    print(f"✓ Prompt builder initialized")
    print(f"✓ Paper exchange initialized with ${exchange.initial_capital:.2f}")
    print()

    try:
        # =====================================================================
        # STEP 2: Fetch Real Market Data
        # =====================================================================
        print("Step 2: Fetching real market data from Binance...")

        symbol = "BTC/USDT"
        timeframes = ["1m", "3m", "15m"]
        lookback = 20

        market_data = await data_fetcher.fetch_multi_timeframe(
            symbol=symbol,
            timeframes=timeframes,
            lookback=lookback
        )

        print(f"✓ Fetched data for {len(market_data)} timeframes:")
        for tf, candles in market_data.items():
            latest_price = candles[-1]["close"]
            print(f"  - {tf}: {len(candles)} candles, latest ${latest_price:,.2f}")
        print()

        # =====================================================================
        # STEP 3: Get Current Price
        # =====================================================================
        print("Step 3: Getting current price...")

        current_price = await data_fetcher.get_current_price(symbol)
        print(f"✓ Current {symbol}: ${current_price:,.2f}")
        print()

        # =====================================================================
        # STEP 4: Build Trading Prompt
        # =====================================================================
        print("Step 4: Building NOF1-style prompt...")

        account_info = exchange.get_account_state()

        prompt = prompt_builder.build_prompt(
            symbol=symbol,
            market_data=market_data,
            account_info=account_info,
            template_version="nof1_exact"
        )

        print(f"✓ Prompt generated ({len(prompt):,} characters)")
        print(f"  Preview (first 500 chars):")
        print("  " + "-" * 76)
        for line in prompt[:500].split("\n"):
            print(f"  {line}")
        print("  " + "-" * 76)
        print()

        # =====================================================================
        # STEP 5: Simulate Buy Order
        # =====================================================================
        print("Step 5: Simulating BUY order...")

        # Calculate position size (use 40% of capital)
        position_value = exchange.cash_balance * 0.4
        size = position_value / current_price

        buy_order = exchange.execute_order(
            symbol=symbol,
            action="BUY",
            size=size,
            price=current_price,
            model_name="integration_test",
            reasoning="Testing complete trading flow",
            confidence=0.8
        )

        print(f"✓ Buy order executed:")
        print(f"  - Order ID: {buy_order.order_id}")
        print(f"  - Size: {buy_order.size:.6f} BTC")
        print(f"  - Price: ${buy_order.executed_price:,.2f}")
        print(f"  - Status: {buy_order.status}")
        print()

        # =====================================================================
        # STEP 6: Check Account State After Buy
        # =====================================================================
        print("Step 6: Checking account state after buy...")

        # Simulate price movement (up 1%)
        new_price = current_price * 1.01

        account_state = exchange.get_account_state(
            current_prices={symbol: new_price}
        )

        print(f"✓ Account state (price up 1%):")
        print(f"  - Cash Balance: ${account_state['cash_balance']:.2f}")
        print(f"  - Position Value: ${account_state['position_value']:.2f}")
        print(f"  - Total Value: ${account_state['total_value']:.2f}")
        print(f"  - Total Return: {account_state['total_return_pct']:.2f}%")
        print(f"  - Open Positions: {len(account_state['positions'])}")
        print()

        # =====================================================================
        # STEP 7: Simulate Sell Order
        # =====================================================================
        print("Step 7: Simulating SELL order...")

        # Sell the position at profit
        sell_order = exchange.execute_order(
            symbol=symbol,
            action="SELL",
            size=buy_order.size,
            price=new_price,
            model_name="integration_test",
            reasoning="Taking profit after 1% gain",
            confidence=0.7
        )

        print(f"✓ Sell order executed:")
        print(f"  - Order ID: {sell_order.order_id}")
        print(f"  - Size: {sell_order.size:.6f} BTC")
        print(f"  - Price: ${sell_order.executed_price:,.2f}")
        print(f"  - Status: {sell_order.status}")
        print()

        # =====================================================================
        # STEP 8: Final Account State
        # =====================================================================
        print("Step 8: Final account state...")

        final_state = exchange.get_account_state()

        print(f"✓ Final account state:")
        print(f"  - Cash Balance: ${final_state['cash_balance']:.2f}")
        print(f"  - Total Value: ${final_state['total_value']:.2f}")
        print(f"  - Total Return: {final_state['total_return_pct']:.2f}%")
        print(f"  - Total Trades: {final_state['total_trades']}")
        print(f"  - Open Positions: {len(final_state['positions'])}")
        print()

        # =====================================================================
        # STEP 9: Verify Results
        # =====================================================================
        print("Step 9: Verifying results...")

        # Check that we made a profit
        assert final_state['total_value'] > exchange.initial_capital, \
            "Should have profit after 1% price increase"

        # Check that both orders executed
        assert len(exchange.orders) == 2, "Should have 2 orders"
        assert exchange.orders[0].status == "filled", "First order should be filled"
        assert exchange.orders[1].status == "filled", "Second order should be filled"

        # Check no open positions
        assert len(final_state['positions']) == 0, "Should have no open positions"

        print("✓ All verifications passed!")
        print()

        # =====================================================================
        # SUCCESS
        # =====================================================================
        print("=" * 80)
        print("✅ FASE 3 INTEGRATION TEST PASSED")
        print("=" * 80)
        print()
        print("Summary:")
        print(f"  • Data fetched from Binance: {len(market_data)} timeframes")
        print(f"  • Prompt generated: {len(prompt):,} characters")
        print(f"  • Orders executed: {len(exchange.orders)}")
        print(f"  • Starting capital: ${exchange.initial_capital:.2f}")
        print(f"  • Final value: ${final_state['total_value']:.2f}")
        print(f"  • Net profit: ${final_state['total_value'] - exchange.initial_capital:.2f}")
        print(f"  • Return: {final_state['total_return_pct']:.2f}%")
        print()
        print("All FASE 3 components are working correctly! 🎉")
        print()

    finally:
        await data_fetcher.close()


if __name__ == "__main__":
    """Run the integration test"""
    asyncio.run(test_complete_trading_flow())
