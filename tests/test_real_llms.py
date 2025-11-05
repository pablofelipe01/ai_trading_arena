"""
Real LLM Trading Test

This test uses REAL LLM APIs to make trading decisions!

Requirements:
- Add API keys to .env file
- Each model will analyze real BTC market data
- They'll make real trading decisions
- Compete in paper trading (no real money)

Cost estimate per run (10 rounds):
- DeepSeek: ~$0.02 (very cheap!)
- Groq: FREE (Llama via Groq)
- OpenAI: ~$0.20 (GPT-4o)
- Anthropic: ~$0.30 (Claude)
Total: ~$0.52 per test run
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_fetcher import BinanceDataFetcher
from models.llm_manager import LLMManager
from strategies.prompts import PromptBuilder


async def test_real_llm_trading():
    """
    Test real LLM trading decisions
    """
    print("=" * 80)
    print("🤖 REAL LLM TRADING TEST")
    print("=" * 80)
    print()
    print("⚠️  Using REAL API calls - Estimated cost: ~$0.52 for 10 rounds")
    print()
    print("=" * 80)
    print("Initializing...")
    print("=" * 80)
    print()

    # Initialize components
    data_fetcher = BinanceDataFetcher()
    prompt_builder = PromptBuilder()
    llm_manager = LLMManager()

    try:
        # Initialize LLM models (will use real API keys from .env)
        await llm_manager.initialize()

        print(f"✅ Initialized {len(llm_manager.models)} LLM models:")
        for provider, state in llm_manager.models.items():
            print(f"  • {provider} (priority {state.priority})")
        print()

        # Trading parameters
        symbol = "BTC/USDT"
        num_rounds = 10  # Increased from 5 to 10 rounds

        print("=" * 80)
        print(f"Starting {num_rounds} trading rounds...")
        print("=" * 80)
        print()

        for round_num in range(1, num_rounds + 1):
            print(f"📊 Round {round_num}/{num_rounds}")
            print("-" * 80)

            # Fetch real market data
            market_data = await data_fetcher.fetch_multi_timeframe(
                symbol=symbol,
                timeframes=["1m", "3m", "15m"],
                lookback=20
            )

            current_price = await data_fetcher.get_current_price(symbol)
            print(f"  Current {symbol}: ${current_price:,.2f}")
            print()

            # Get decisions from all models concurrently
            print("  🤔 Models are thinking...")

            decisions = {}
            for provider, state in llm_manager.models.items():
                # Build prompt for this model
                account_info = state.exchange.get_account_state(
                    current_prices={symbol: current_price}
                )

                prompt = prompt_builder.build_prompt(
                    symbol=symbol,
                    market_data=market_data,
                    account_info=account_info,
                    template_version="nof1_exact"
                )

                # Get decision from real LLM!
                print(f"  → Asking {provider}...", end=" ", flush=True)
                try:
                    decision = await state.client.get_trading_decision(
                        prompt=prompt,
                        symbol=symbol,
                        current_price=current_price
                    )
                    decisions[provider] = decision

                    # Show decision
                    action_emoji = {
                        "BUY": "🟢",
                        "SELL": "🔴",
                        "HOLD": "⚪"
                    }
                    print(f"{action_emoji.get(decision.action, '❓')} {decision.action} (conf: {decision.confidence:.2f})")

                    state.record_decision(0.5)  # Placeholder latency

                except Exception as e:
                    print(f"❌ ERROR: {str(e)[:50]}")
                    decisions[provider] = None
                    state.record_error(str(e))

            print()

            # Execute decisions
            print("  💰 Executing trades...")
            execution_results = await llm_manager.execute_decisions(
                decisions=decisions,
                symbol=symbol,
                current_price=current_price
            )

            trades_executed = sum(1 for success in execution_results.values() if success)
            print(f"  ✅ Executed {trades_executed} trades")
            print()

            # Show performance snapshot
            print("  📈 Current Performance:")
            for provider, state in llm_manager.models.items():
                account = state.exchange.get_account_state()
                value = account["total_value"]
                return_pct = account["total_return_pct"]

                return_color = "🟢" if return_pct > 0 else "🔴" if return_pct < 0 else "⚪"
                print(f"    {provider:12} ${value:7.2f} ({return_color} {return_pct:+.2f}%)")

            print()

            # Wait between rounds (except last)
            if round_num < num_rounds:
                print("  ⏳ Waiting 5 seconds before next round...")
                await asyncio.sleep(5)
                print()

        # Final leaderboard
        print("=" * 80)
        print("🏆 FINAL LEADERBOARD")
        print("=" * 80)
        print()

        leaderboard = llm_manager.get_leaderboard()

        print(f"{'Rank':<6} {'Model':<12} {'Return':<10} {'Value':<12} {'Trades':<8} {'Win Rate':<10}")
        print("-" * 80)

        medals = ["🥇", "🥈", "🥉"]
        for i, perf in enumerate(leaderboard, 1):
            rank = f"#{i}"
            model = perf["provider"]
            return_pct = f"{perf['return_pct']:+.2f}%"
            value = f"${perf['account_value']:.2f}"
            trades = f"{perf['total_trades']}"
            win_rate = f"{perf['win_rate']:.1f}%"

            medal = medals[i-1] if i <= 3 else ""

            print(f"{rank:<6} {model:<12} {return_pct:<10} {value:<12} {trades:<8} {win_rate:<10} {medal}")

        print()

        # Winner announcement
        winner = leaderboard[0]
        print("=" * 80)
        print(f"🎉 WINNER: {winner['provider'].upper()}!")
        print(f"   Return: {winner['return_pct']:+.2f}%")
        print(f"   Total Trades: {winner['total_trades']}")
        print("=" * 80)
        print()

        # Summary
        summary = llm_manager.get_summary()
        print("Summary:")
        print(f"  • Models tested: {summary['total_models']}")
        print(f"  • Trading rounds: {num_rounds}")
        print(f"  • Total decisions: {summary['total_decisions']}")
        print(f"  • Session duration: {summary['session_duration_minutes']:.1f} minutes")
        print()

        # Error statistics
        print("Error Statistics:")
        for provider, state in llm_manager.models.items():
            if state.errors > 0:
                error_rate = (state.errors / num_rounds) * 100
                print(f"  • {provider}: {state.errors} errors ({error_rate:.0f}% error rate)")
        print()

        print("✅ Real LLM trading test complete!")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await data_fetcher.close()
        await llm_manager.close()


if __name__ == "__main__":
    """Run the real LLM test"""
    asyncio.run(test_real_llm_trading())
