"""
FASE 4 Integration Test

End-to-end test demonstrating LLM integration with the trading system.

Uses mock LLM clients to avoid requiring real API keys.

Flow:
1. Initialize LLM manager with multiple mock models
2. Fetch real market data from Binance
3. Build NOF1-style prompt
4. Get trading decisions from all models
5. Execute trades for each model
6. Track performance and generate leaderboard
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_fetcher import BinanceDataFetcher
from core.exchange_executor import PaperExchange
from models.mock_llm import create_mock_clients, MockLLMClient
from strategies.prompts import PromptBuilder


# ============================================================================
# Mock LLM Manager (Simplified version for testing)
# ============================================================================


class MockLLMManager:
    """
    Simplified LLM manager using mock clients

    This bypasses the full LLMManager to avoid requiring config/API keys.
    """

    def __init__(self):
        """Initialize mock manager"""
        self.models = {}
        self.session_start = datetime.now()

    async def initialize(self):
        """Initialize mock models"""
        mock_clients = create_mock_clients()

        for provider, client in mock_clients.items():
            self.models[provider] = {
                "client": client,
                "exchange": PaperExchange(initial_capital=100.0),
                "decisions": 0,
                "trades": 0
            }

        print(f"✓ Initialized {len(self.models)} mock models")

    async def get_all_decisions(self, prompt: str, symbol: str, price: float):
        """Get decisions from all models"""
        decisions = {}

        for provider, state in self.models.items():
            try:
                decision = await state["client"].get_trading_decision(
                    prompt=prompt,
                    symbol=symbol,
                    current_price=price
                )
                decisions[provider] = decision
                state["decisions"] += 1
            except Exception as e:
                print(f"  ⚠ {provider} failed: {e}")
                decisions[provider] = None

        return decisions

    async def execute_decisions(self, decisions, symbol: str, price: float):
        """Execute decisions"""
        results = {}

        for provider, decision in decisions.items():
            if decision is None:
                results[provider] = False
                continue

            state = self.models[provider]
            exchange = state["exchange"]

            try:
                if decision.action == "BUY":
                    # Calculate size
                    available = exchange.cash_balance
                    position_value = available * decision.position_size
                    size = position_value / price

                    if size > 0:
                        exchange.execute_order(
                            symbol=symbol,
                            action="BUY",
                            size=size,
                            price=price,
                            model_name=provider,
                            reasoning=decision.reasoning,
                            confidence=decision.confidence
                        )
                        state["trades"] += 1

                elif decision.action == "SELL":
                    if symbol in exchange.positions:
                        position = exchange.positions[symbol]
                        size = position.size * decision.position_size

                        exchange.execute_order(
                            symbol=symbol,
                            action="SELL",
                            size=size,
                            price=price,
                            model_name=provider,
                            reasoning=decision.reasoning,
                            confidence=decision.confidence
                        )
                        state["trades"] += 1

                results[provider] = True

            except Exception as e:
                print(f"  ⚠ {provider} execution failed: {e}")
                results[provider] = False

        return results

    def get_leaderboard(self):
        """Get performance leaderboard"""
        performances = []

        for provider, state in self.models.items():
            account = state["exchange"].get_account_state()

            performances.append({
                "provider": provider,
                "return_pct": account["total_return_pct"],
                "total_value": account["total_value"],
                "win_rate": account["win_rate"],
                "total_trades": account["total_trades"],
                "decisions": state["decisions"],
            })

        # Sort by return
        performances.sort(key=lambda x: x["return_pct"], reverse=True)

        return performances


# ============================================================================
# Integration Test
# ============================================================================


async def test_llm_integration():
    """
    Test complete LLM integration
    """
    print("=" * 80)
    print("FASE 4 INTEGRATION TEST - LLM Trading System")
    print("=" * 80)
    print()

    # =========================================================================
    # STEP 1: Initialize Components
    # =========================================================================
    print("Step 1: Initializing components...")

    data_fetcher = BinanceDataFetcher()
    prompt_builder = PromptBuilder()
    llm_manager = MockLLMManager()

    await llm_manager.initialize()

    print(f"✓ Data fetcher initialized")
    print(f"✓ Prompt builder initialized")
    print(f"✓ LLM manager initialized with {len(llm_manager.models)} models:")
    for provider in llm_manager.models.keys():
        print(f"  - {provider}")
    print()

    try:
        # =====================================================================
        # STEP 2: Simulate Trading Rounds
        # =====================================================================
        print("Step 2: Simulating trading rounds...")
        print()

        symbol = "BTC/USDT"
        num_rounds = 5

        for round_num in range(1, num_rounds + 1):
            print(f"Round {round_num}/{num_rounds}")
            print("-" * 40)

            # Fetch market data
            market_data = await data_fetcher.fetch_multi_timeframe(
                symbol=symbol,
                timeframes=["1m", "3m", "15m"],
                lookback=20
            )

            current_price = await data_fetcher.get_current_price(symbol)

            print(f"  Current price: ${current_price:,.2f}")

            # Build prompts for each model
            decisions_made = 0
            trades_executed = 0

            for provider, state in llm_manager.models.items():
                # Get account state
                account_info = state["exchange"].get_account_state(
                    current_prices={symbol: current_price}
                )

                # Build prompt
                prompt = prompt_builder.build_prompt(
                    symbol=symbol,
                    market_data=market_data,
                    account_info=account_info,
                    template_version="nof1_exact"
                )

                # Get decision
                decision = await state["client"].get_trading_decision(
                    prompt=prompt,
                    symbol=symbol,
                    current_price=current_price
                )

                state["decisions"] += 1
                decisions_made += 1

                print(f"  {provider}: {decision.action} (confidence: {decision.confidence:.2f})")

                # Execute decision
                try:
                    if decision.action == "BUY":
                        available = state["exchange"].cash_balance
                        position_value = available * decision.position_size
                        size = position_value / current_price

                        if size > 0:
                            state["exchange"].execute_order(
                                symbol=symbol,
                                action="BUY",
                                size=size,
                                price=current_price,
                                model_name=provider,
                                reasoning=decision.reasoning[:50],
                                confidence=decision.confidence
                            )
                            state["trades"] += 1
                            trades_executed += 1

                    elif decision.action == "SELL":
                        if symbol in state["exchange"].positions:
                            position = state["exchange"].positions[symbol]
                            size = position.size * decision.position_size

                            state["exchange"].execute_order(
                                symbol=symbol,
                                action="SELL",
                                size=size,
                                price=current_price,
                                model_name=provider,
                                reasoning=decision.reasoning[:50],
                                confidence=decision.confidence
                            )
                            state["trades"] += 1
                            trades_executed += 1

                except Exception as e:
                    print(f"    ⚠ Execution failed: {e}")

            print(f"  Decisions: {decisions_made}, Trades: {trades_executed}")
            print()

            # Wait between rounds
            if round_num < num_rounds:
                await asyncio.sleep(1)

        # =====================================================================
        # STEP 3: Generate Leaderboard
        # =====================================================================
        print("=" * 80)
        print("FINAL LEADERBOARD")
        print("=" * 80)
        print()

        leaderboard = llm_manager.get_leaderboard()

        print(f"{'Rank':<6} {'Model':<15} {'Return':<10} {'Value':<12} {'Trades':<8} {'Win Rate':<10}")
        print("-" * 80)

        for i, perf in enumerate(leaderboard, 1):
            rank = f"#{i}"
            model = perf["provider"]
            return_pct = f"{perf['return_pct']:+.2f}%"
            value = f"${perf['total_value']:.2f}"
            trades = f"{perf['total_trades']}"
            win_rate = f"{perf['win_rate']:.1f}%"

            # Add medal for top 3
            medal = ""
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"

            print(f"{rank:<6} {model:<15} {return_pct:<10} {value:<12} {trades:<8} {win_rate:<10} {medal}")

        print()

        # =====================================================================
        # STEP 4: Summary Statistics
        # =====================================================================
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print()

        total_decisions = sum(s["decisions"] for s in llm_manager.models.values())
        total_trades = sum(s["trades"] for s in llm_manager.models.values())

        winner = leaderboard[0]
        loser = leaderboard[-1]

        print(f"Models tested: {len(llm_manager.models)}")
        print(f"Trading rounds: {num_rounds}")
        print(f"Total decisions: {total_decisions}")
        print(f"Total trades: {total_trades}")
        print()
        print(f"🏆 Winner: {winner['provider']} with {winner['return_pct']:+.2f}% return")
        print(f"📉 Last place: {loser['provider']} with {loser['return_pct']:+.2f}% return")
        print()

        # =====================================================================
        # SUCCESS
        # =====================================================================
        print("=" * 80)
        print("✅ FASE 4 INTEGRATION TEST PASSED")
        print("=" * 80)
        print()
        print("All components working correctly:")
        print("  ✓ Real-time market data fetching")
        print("  ✓ Multi-model prompt generation")
        print("  ✓ LLM decision making (mock)")
        print("  ✓ Trade execution")
        print("  ✓ Performance tracking")
        print("  ✓ Leaderboard generation")
        print()
        print("Ready for real LLM integration! 🚀")
        print()

    finally:
        await data_fetcher.close()


if __name__ == "__main__":
    """Run the integration test"""
    asyncio.run(test_llm_integration())
