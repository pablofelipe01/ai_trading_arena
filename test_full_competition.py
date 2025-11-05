#!/usr/bin/env python3
"""
Test full Level 1 competition with 3 rounds
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.arena_manager import ArenaManager


async def main():
    """Run a full 3-round competition"""
    try:
        print("=" * 60)
        print("LEVEL 1: MULTI-ASSET TRADING COMPETITION")
        print("=" * 60)

        arena = ArenaManager()
        await arena.initialize()

        print(f"\n✅ Initialized with {len(arena.symbols)} assets:")
        print(f"   {', '.join([s.split('/')[0] for s in arena.symbols])}")
        print(f"\n💰 Each LLM starts with: $100 TOTAL")
        print(f"📊 Indicators: RSI, MACD, EMA-20, Volume")
        print(f"🎯 Actions: BUY/SELL/HOLD only (no shorting)")

        print("\n" + "=" * 60)
        print("RUNNING 3 TRADING ROUNDS")
        print("=" * 60)

        for round_num in range(1, 4):
            print(f"\n🔄 ROUND {round_num}/3...")
            await arena._run_trading_round()
            print(f"   ✓ Round {round_num} completed")

        print("\n" + "=" * 60)
        print("FINAL RESULTS")
        print("=" * 60)

        leaderboard = arena.llm_manager.get_leaderboard()

        print(f"\n{'Rank':<6} {'LLM':<12} {'Trades':<8} {'Errors':<8} {'Portfolio':<12} {'Return':<10}")
        print("-" * 70)

        for i, perf in enumerate(leaderboard, 1):
            print(f"{i:<6} {perf['provider']:<12} {perf['total_trades']:<8} "
                  f"{perf['errors']:<8} ${perf['account_value']:<11.2f} "
                  f"{perf['return_pct']:>+7.2f}%")

        print("\n" + "=" * 60)
        print("COMPETITION COMPLETE! 🎉")
        print("=" * 60)

        # Show winner
        winner = leaderboard[0]
        print(f"\n🏆 WINNER: {winner['provider'].upper()}")
        print(f"   Portfolio Value: ${winner['account_value']:.2f}")
        print(f"   Total Return: {winner['return_pct']:+.2f}%")
        print(f"   Trades Executed: {winner['total_trades']}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
