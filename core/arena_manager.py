"""
Arena Manager for AI Trading Arena

Orchestrates LLM trading competitions:
- Manages competition sessions
- Coordinates trading rounds
- Displays real-time leaderboard
- Exports results
- Handles graceful shutdown

Usage:
    from core.arena_manager import ArenaManager

    arena = ArenaManager()
    await arena.run_competition(duration_minutes=60)
"""

import asyncio
import json
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich import box

from core.data_fetcher import BinanceDataFetcher
from models.llm_manager import LLMManager
from strategies.prompts import PromptBuilder
from utils.config import get_config
from utils.logger import get_logger
from utils.indicators import calculate_indicators_from_ohlcv


logger = get_logger(__name__)
console = Console()


# ============================================================================
# Arena Manager
# ============================================================================


class ArenaManager:
    """
    Manages LLM trading competitions

    Responsibilities:
    - Session lifecycle (start/stop/pause)
    - Trading round coordination
    - Real-time leaderboard updates
    - Results export
    - Signal handling for graceful shutdown
    """

    def __init__(self):
        """Initialize arena manager"""
        self.config = get_config()
        self.logger = get_logger("arena.manager")

        # Components
        self.llm_manager: Optional[LLMManager] = None
        self.data_fetcher: Optional[BinanceDataFetcher] = None
        self.prompt_builder: Optional[PromptBuilder] = None

        # Session state
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_start: Optional[datetime] = None
        self.session_end: Optional[datetime] = None
        self.running = False
        self.paused = False

        # Trading state
        self.current_round = 0
        self.total_rounds = 0
        self.symbols = self.config.exchange.symbols  # All trading symbols (multi-asset)

        # Results tracking
        self.round_results: List[Dict[str, Any]] = []

        # Shutdown handling
        self.shutdown_requested = False

        self.logger.info("Arena manager initialized", session_id=self.session_id)

    async def initialize(self):
        """Initialize all components"""
        self.logger.info("Initializing arena components...")

        try:
            # Initialize LLM manager
            self.llm_manager = LLMManager()
            await self.llm_manager.initialize()

            # Initialize data fetcher
            self.data_fetcher = BinanceDataFetcher()

            # Initialize prompt builder
            self.prompt_builder = PromptBuilder()

            self.logger.info("Arena components initialized successfully")

        except Exception as e:
            self.logger.error("Failed to initialize arena", error=str(e), exc_info=True)
            raise

    def setup_signal_handlers(self):
        """Setup graceful shutdown on Ctrl+C"""
        def signal_handler(signum, frame):
            self.logger.info("Shutdown signal received")
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def run_competition(
        self,
        duration_minutes: Optional[int] = None,
        max_rounds: Optional[int] = None
    ):
        """
        Run a trading competition

        Args:
            duration_minutes: Competition duration (None = unlimited)
            max_rounds: Maximum rounds (None = unlimited)
        """
        self.setup_signal_handlers()

        # Calculate end time if duration specified
        if duration_minutes:
            self.session_end = datetime.now() + timedelta(minutes=duration_minutes)

        if max_rounds:
            self.total_rounds = max_rounds

        self.session_start = datetime.now()
        self.running = True

        self.logger.info(
            "Starting competition",
            duration_minutes=duration_minutes,
            max_rounds=max_rounds,
            symbols=len(self.symbols),
            assets=self.symbols
        )

        # Display welcome
        self._display_welcome()

        try:
            # Main competition loop
            while self.running and not self.shutdown_requested:
                # Check if we should stop
                if self.session_end and datetime.now() >= self.session_end:
                    self.logger.info("Session time limit reached")
                    break

                if max_rounds and self.current_round >= max_rounds:
                    self.logger.info("Max rounds reached")
                    break

                # Run trading round
                await self._run_trading_round()

                # Display current leaderboard
                self._display_round_summary()

                # Wait for next round
                if not self.shutdown_requested and self.current_round < (max_rounds or float('inf')):
                    console.print(f"\n[dim]⏳ Waiting {self.config.arena.decision_interval}s before next round...[/dim]\n")
                    await asyncio.sleep(self.config.arena.decision_interval)

            # Competition ended
            self._display_final_results()

        except Exception as e:
            self.logger.error("Competition error", error=str(e), exc_info=True)
            raise

        finally:
            self.running = False
            await self._cleanup()

    async def _run_trading_round(self):
        """Run a single trading round"""
        self.current_round += 1

        # Ensure session_start is set (for testing/web dashboard)
        if not self.session_start:
            self.session_start = datetime.now()

        self.logger.info(
            "Starting trading round",
            round=self.current_round,
            num_symbols=len(self.symbols)
        )

        try:
            # Fetch market data for ALL symbols (Level 1: Multi-asset)
            timeframes = ["1m", "3m", "15m", "1h", "4h"]

            market_data_all = {}
            current_prices = {}

            for symbol in self.symbols:
                try:
                    # Fetch OHLCV data for all timeframes
                    ohlcv_data = await self.data_fetcher.fetch_multi_timeframe(
                        symbol=symbol,
                        timeframes=timeframes,
                        lookback=100
                    )

                    # Get current price from most recent 3m candle
                    current_price = ohlcv_data["3m"][-1]["close"]
                    current_prices[symbol] = current_price

                    # Calculate indicators from 3m timeframe (primary for Level 1)
                    indicators_data = calculate_indicators_from_ohlcv(
                        candles=ohlcv_data["3m"],
                        timeframe="3m"
                    )

                    # Build price_series dict (timeframe → close prices)
                    price_series = {}
                    for tf, candles in ohlcv_data.items():
                        price_series[tf] = [c["close"] for c in candles]

                    # Store market data
                    market_data_all[symbol] = {
                        "current_price": current_price,
                        "indicators": indicators_data["indicators"],
                        "price_series": price_series,
                        "indicator_series": indicators_data["indicator_series"]
                    }

                except Exception as e:
                    self.logger.error(f"Failed to fetch data for {symbol}", error=str(e))
                    continue

            if not market_data_all:
                raise RuntimeError("Failed to fetch data for any symbols")

            # Get decisions from all models (multi-asset decisions)
            decisions = await self.llm_manager.get_all_multi_asset_decisions(
                symbols=self.symbols,
                market_data_all=market_data_all,
                current_prices=current_prices,
                session_info={
                    "minutes_elapsed": (datetime.now() - self.session_start).total_seconds() / 60,
                    "current_time": datetime.now(),
                    "invocations": self.current_round
                }
            )

            # Execute decisions for each model across all assets
            execution_results = await self.llm_manager.execute_multi_asset_decisions(
                decisions=decisions,
                current_prices=current_prices
            )

            # Record round results
            round_result = {
                "round": self.current_round,
                "timestamp": datetime.now().isoformat(),
                "prices": current_prices,
                "decisions": {
                    provider: {
                        "num_decisions": len(decision_list) if decision_list else 0,
                        "actions": [d.action for d in decision_list] if decision_list else []
                    }
                    for provider, decision_list in decisions.items()
                },
                "executions": execution_results,
                "leaderboard": self.llm_manager.get_leaderboard()
            }

            self.round_results.append(round_result)

            self.logger.info(
                "Trading round completed",
                round=self.current_round,
                symbols_fetched=len(market_data_all),
                models_decided=len([d for d in decisions.values() if d is not None])
            )

        except Exception as e:
            self.logger.error(
                "Trading round failed",
                round=self.current_round,
                error=str(e),
                exc_info=True
            )
            # Show error to user
            console.print(f"[red]✗ Round {self.current_round} failed: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")

    def _generate_dashboard(self) -> Layout:
        """Generate real-time dashboard"""
        layout = Layout()

        # Header
        header_text = f"🤖 AI Trading Arena - Session {self.session_id}"
        if self.session_end:
            time_left = (self.session_end - datetime.now()).total_seconds() / 60
            header_text += f" | Time Left: {time_left:.1f}m"

        header = Panel(
            f"[bold cyan]{header_text}[/bold cyan]",
            box=box.DOUBLE
        )

        # Leaderboard
        leaderboard_table = self._create_leaderboard_table()

        # Session stats
        stats = self._create_stats_panel()

        # Layout
        layout.split_column(
            Layout(header, size=3),
            Layout(leaderboard_table),
            Layout(stats, size=8)
        )

        return layout

    def _create_leaderboard_table(self) -> Table:
        """Create leaderboard table"""
        table = Table(
            title="🏆 Live Leaderboard",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )

        table.add_column("Rank", justify="center", style="cyan")
        table.add_column("Model", justify="left", style="bold")
        table.add_column("Return", justify="right", style="green")
        table.add_column("Value", justify="right")
        table.add_column("Trades", justify="center")
        table.add_column("Win Rate", justify="center")
        table.add_column("Errors", justify="center", style="red")

        if self.llm_manager:
            leaderboard = self.llm_manager.get_leaderboard()

            medals = ["🥇", "🥈", "🥉"]

            for i, performance in enumerate(leaderboard):
                rank = medals[i] if i < 3 else f"#{i+1}"

                return_pct = performance["return_pct"]
                return_color = "green" if return_pct >= 0 else "red"

                table.add_row(
                    rank,
                    performance["provider"],
                    f"[{return_color}]{return_pct:+.2f}%[/{return_color}]",
                    f"${performance['account_value']:.2f}",
                    str(performance["total_trades"]),
                    f"{performance['win_rate']:.1f}%",
                    str(performance["errors"])
                )

        return table

    def _display_round_summary(self):
        """Display summary after each round"""
        console.print(f"\n[bold cyan]{'='*80}[/bold cyan]")
        console.print(f"[bold yellow]📊 Round {self.current_round} Complete[/bold yellow]")
        console.print(f"[bold cyan]{'='*80}[/bold cyan]\n")

        # Show leaderboard
        table = self._create_leaderboard_table()
        console.print(table)

        # Show round stats
        duration = (datetime.now() - self.session_start).total_seconds() / 60
        console.print(f"\n[dim]Session Duration: {duration:.1f}m | Total Decisions: {self.llm_manager.total_decisions}[/dim]")

    def _create_stats_panel(self) -> Panel:
        """Create session statistics panel"""
        if not self.session_start:
            return Panel("Waiting to start...")

        duration = (datetime.now() - self.session_start).total_seconds() / 60

        stats_text = f"""
[bold]Session Statistics[/bold]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[bold cyan]LEVEL 1: Multi-Asset Portfolio[/bold cyan]
Assets: [cyan]{len(self.symbols)}[/cyan] ({', '.join([s.split('/')[0] for s in self.symbols[:4]])}...)
Round: [yellow]{self.current_round}[/yellow]
Duration: [yellow]{duration:.1f}m[/yellow]
Decision Interval: [cyan]{self.config.arena.decision_interval}s[/cyan]

Models Active: [green]{len(self.llm_manager.models) if self.llm_manager else 0}[/green]
Total Decisions: [yellow]{self.llm_manager.total_decisions if self.llm_manager else 0}[/yellow]
        """

        return Panel(stats_text.strip(), box=box.ROUNDED)

    def _display_welcome(self):
        """Display welcome message"""
        assets_str = ', '.join([s.split('/')[0] for s in self.symbols])
        welcome = f"""
[bold cyan]════════════════════════════════════════════════════════════════[/bold cyan]
[bold yellow]🤖  AI TRADING ARENA - LEVEL 1: MULTI-ASSET[/bold yellow]
[bold cyan]════════════════════════════════════════════════════════════════[/bold cyan]

Session ID: [cyan]{self.session_id}[/cyan]
Assets: [yellow]{len(self.symbols)}[/yellow] [{assets_str}]
Models: [green]{len(self.llm_manager.models) if self.llm_manager else 0}[/green]
Capital per Model: [green]$100[/green]

[dim]Press Ctrl+C to stop gracefully[/dim]
        """
        console.print(welcome)

    def _display_final_results(self):
        """Display final competition results"""
        if not self.llm_manager:
            return

        leaderboard = self.llm_manager.get_leaderboard()
        winner = leaderboard[0] if leaderboard else None

        console.print("\n" + "="*80)
        console.print("[bold green]🏁 COMPETITION COMPLETE![/bold green]")
        console.print("="*80 + "\n")

        # Final leaderboard
        final_table = self._create_leaderboard_table()
        console.print(final_table)

        # Winner announcement
        if winner:
            console.print(f"\n[bold yellow]🎉 WINNER: {winner['provider'].upper()}![/bold yellow]")
            console.print(f"[green]Return: {winner['return_pct']:+.2f}%[/green]")
            console.print(f"Total Trades: {winner['total_trades']}")

        # Session summary
        duration = (datetime.now() - self.session_start).total_seconds() / 60
        console.print(f"\nSession Duration: {duration:.1f} minutes")
        console.print(f"Total Rounds: {self.current_round}")
        console.print(f"Results saved to: data/results/session_{self.session_id}.json")

    async def _cleanup(self):
        """Cleanup resources and export results"""
        self.logger.info("Cleaning up arena...")

        try:
            # Export results
            await self.export_results()

            # Close LLM manager
            if self.llm_manager:
                await self.llm_manager.close()

            self.logger.info("Arena cleanup complete")

        except Exception as e:
            self.logger.error("Cleanup error", error=str(e), exc_info=True)

    async def export_results(self):
        """Export competition results to files"""
        self.logger.info("Exporting results...")

        try:
            # Create results directory
            results_dir = Path("data/results")
            results_dir.mkdir(parents=True, exist_ok=True)

            # Prepare results data
            results = {
                "session_id": self.session_id,
                "session_start": self.session_start.isoformat() if self.session_start else None,
                "session_end": datetime.now().isoformat(),
                "level": "level1_multi_asset",
                "symbols": self.symbols,
                "num_assets": len(self.symbols),
                "total_rounds": self.current_round,
                "config": {
                    "decision_interval": self.config.arena.decision_interval,
                    "capital_per_model": self.config.trading.capital_per_model
                },
                "final_leaderboard": self.llm_manager.get_leaderboard() if self.llm_manager else [],
                "round_results": self.round_results,
                "summary": self.llm_manager.get_summary() if self.llm_manager else {}
            }

            # Export JSON
            json_path = results_dir / f"session_{self.session_id}.json"
            with open(json_path, "w") as f:
                json.dump(results, f, indent=2)

            self.logger.info("Results exported", path=str(json_path))

            # Export CSV leaderboard
            await self._export_leaderboard_csv(results_dir)

        except Exception as e:
            self.logger.error("Failed to export results", error=str(e), exc_info=True)

    async def _export_leaderboard_csv(self, results_dir: Path):
        """Export leaderboard to CSV"""
        try:
            import csv

            if not self.llm_manager:
                return

            leaderboard = self.llm_manager.get_leaderboard()

            csv_path = results_dir / f"leaderboard_{self.session_id}.csv"

            with open(csv_path, "w", newline="") as f:
                if leaderboard:
                    writer = csv.DictWriter(f, fieldnames=leaderboard[0].keys())
                    writer.writeheader()
                    writer.writerows(leaderboard)

            self.logger.info("Leaderboard CSV exported", path=str(csv_path))

        except Exception as e:
            self.logger.error("Failed to export CSV", error=str(e), exc_info=True)


# ============================================================================
# Convenience Functions
# ============================================================================


async def run_arena(duration_minutes: Optional[int] = None, max_rounds: Optional[int] = None):
    """
    Convenience function to run arena competition

    Args:
        duration_minutes: Competition duration
        max_rounds: Maximum rounds
    """
    arena = ArenaManager()
    await arena.initialize()
    await arena.run_competition(
        duration_minutes=duration_minutes,
        max_rounds=max_rounds
    )
