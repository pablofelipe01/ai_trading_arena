"""
Extended Competition Runner for AI Trading Arena

Runs long-duration competitions (24+ hours) with:
- Checkpoint saving/loading
- Detailed analytics collection
- System health monitoring
- Periodic progress reports
- Graceful shutdown/resume
- Anomaly detection

Usage:
    python tests/extended_runner.py --duration 24 --checkpoint-interval 60
    python tests/extended_runner.py --resume session_20251030_112514
"""

import asyncio
import json
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.arena_manager import ArenaManager
from utils.config_loader import load_config
from tests.test_utils import PerformanceMonitor


# ============================================================================
# Extended Session Manager
# ============================================================================


class ExtendedSessionManager:
    """Manages extended competition sessions with checkpointing"""

    def __init__(self, session_id: str, checkpoint_dir: str = "data/checkpoints"):
        """Initialize session manager"""
        self.session_id = session_id
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self.start_time = datetime.now()
        self.rounds_completed = 0
        self.checkpoints_saved = 0
        self.last_checkpoint_time = None

        self.analytics = {
            "hourly_stats": [],
            "model_performance": {},
            "system_health": [],
            "anomalies": [],
            "round_history": []
        }

        self.console = Console()
        self.monitor = PerformanceMonitor()
        self.monitor.start()

        self.shutdown_requested = False

    def save_checkpoint(self, arena_manager: ArenaManager) -> Path:
        """Save a checkpoint of current state"""
        checkpoint = {
            "session_id": self.session_id,
            "checkpoint_time": datetime.now().isoformat(),
            "rounds_completed": self.rounds_completed,
            "start_time": self.start_time.isoformat(),
            "analytics": self.analytics,
            "leaderboard": arena_manager.get_leaderboard()
        }

        checkpoint_file = self.checkpoint_dir / f"checkpoint_{self.session_id}_{self.rounds_completed}.json"
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint, f, indent=2)

        self.checkpoints_saved += 1
        self.last_checkpoint_time = datetime.now()

        self.console.print(f"[green]💾 Checkpoint saved: {checkpoint_file.name}[/green]")
        return checkpoint_file

    def load_checkpoint(self, checkpoint_file: Path) -> Dict[str, Any]:
        """Load a checkpoint"""
        with open(checkpoint_file, "r") as f:
            checkpoint = json.load(f)

        self.session_id = checkpoint["session_id"]
        self.rounds_completed = checkpoint["rounds_completed"]
        self.start_time = datetime.fromisoformat(checkpoint["start_time"])
        self.analytics = checkpoint["analytics"]

        self.console.print(f"[green]📂 Checkpoint loaded: {checkpoint_file.name}[/green]")
        return checkpoint

    def record_round(self, round_num: int, round_data: Dict[str, Any]):
        """Record round data"""
        self.rounds_completed = round_num
        self.analytics["round_history"].append({
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "data": round_data
        })

    def record_hourly_stats(self, arena_manager: ArenaManager):
        """Record hourly statistics"""
        leaderboard = arena_manager.get_leaderboard()

        hourly_stat = {
            "timestamp": datetime.now().isoformat(),
            "hour": len(self.analytics["hourly_stats"]) + 1,
            "rounds_completed": self.rounds_completed,
            "leaderboard_snapshot": leaderboard,
            "leader": leaderboard[0]["provider"] if leaderboard else None,
            "avg_return": sum(m["return_pct"] for m in leaderboard) / len(leaderboard) if leaderboard else 0
        }

        self.analytics["hourly_stats"].append(hourly_stat)

    def detect_anomalies(self, arena_manager: ArenaManager):
        """Detect performance anomalies"""
        leaderboard = arena_manager.get_leaderboard()

        for model in leaderboard:
            # Check for excessive errors
            if model["errors"] > 10:
                anomaly = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "excessive_errors",
                    "model": model["provider"],
                    "error_count": model["errors"]
                }
                self.analytics["anomalies"].append(anomaly)

            # Check for extreme losses
            if model["return_pct"] < -90:
                anomaly = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "extreme_loss",
                    "model": model["provider"],
                    "return_pct": model["return_pct"]
                }
                self.analytics["anomalies"].append(anomaly)

            # Check for very high latency
            if model.get("avg_latency", 0) > 30:
                anomaly = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "high_latency",
                    "model": model["provider"],
                    "latency": model["avg_latency"]
                }
                self.analytics["anomalies"].append(anomaly)

    def display_progress_report(self, arena_manager: ArenaManager):
        """Display detailed progress report"""
        elapsed = datetime.now() - self.start_time
        leaderboard = arena_manager.get_leaderboard()

        self.console.print("\n" + "="*80)
        self.console.print(f"[bold cyan]📊 EXTENDED SESSION PROGRESS REPORT[/bold cyan]")
        self.console.print("="*80)
        self.console.print(f"Session ID: {self.session_id}")
        self.console.print(f"Elapsed Time: {elapsed}")
        self.console.print(f"Rounds Completed: {self.rounds_completed}")
        self.console.print(f"Checkpoints Saved: {self.checkpoints_saved}")

        # Leaderboard table
        table = Table(title="Current Leaderboard")
        table.add_column("Rank", style="cyan")
        table.add_column("Model", style="magenta")
        table.add_column("Return %", style="green")
        table.add_column("Trades", style="yellow")
        table.add_column("Win Rate", style="blue")
        table.add_column("Errors", style="red")

        medals = ["🥇", "🥈", "🥉"]
        for i, model in enumerate(leaderboard[:10]):  # Top 10
            rank = medals[i] if i < 3 else f"#{i+1}"
            table.add_row(
                rank,
                model["provider"],
                f"{model['return_pct']:.2f}%",
                str(model["total_trades"]),
                f"{model['win_rate']:.1f}%",
                str(model["errors"])
            )

        self.console.print(table)

        # Anomalies
        if self.analytics["anomalies"]:
            self.console.print(f"\n[bold red]⚠️  Anomalies Detected: {len(self.analytics['anomalies'])}[/bold red]")
            for anomaly in self.analytics["anomalies"][-5:]:  # Last 5
                self.console.print(f"  - {anomaly['type']}: {anomaly.get('model', 'N/A')}")

        self.console.print("="*80 + "\n")

    def export_final_report(self, arena_manager: ArenaManager) -> Path:
        """Export comprehensive final report"""
        self.monitor.stop()
        monitor_report = self.monitor.get_report()

        final_report = {
            "session_id": self.session_id,
            "session_start": self.start_time.isoformat(),
            "session_end": datetime.now().isoformat(),
            "total_duration_hours": (datetime.now() - self.start_time).total_seconds() / 3600,
            "rounds_completed": self.rounds_completed,
            "checkpoints_saved": self.checkpoints_saved,
            "final_leaderboard": arena_manager.get_leaderboard(),
            "analytics": self.analytics,
            "performance_metrics": monitor_report
        }

        report_file = Path("data/results") / f"extended_session_{self.session_id}.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)

        with open(report_file, "w") as f:
            json.dump(final_report, f, indent=2)

        self.console.print(f"[bold green]✅ Final report exported: {report_file}[/bold green]")
        return report_file


# ============================================================================
# Extended Runner
# ============================================================================


class ExtendedRunner:
    """Runs extended competitions with monitoring"""

    def __init__(
        self,
        duration_hours: int,
        symbol: str = "BTC/USDT",
        checkpoint_interval_minutes: int = 60,
        report_interval_minutes: int = 60
    ):
        """Initialize extended runner"""
        self.duration_hours = duration_hours
        self.symbol = symbol
        self.checkpoint_interval = checkpoint_interval_minutes * 60  # Convert to seconds
        self.report_interval = report_interval_minutes * 60

        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_manager = ExtendedSessionManager(self.session_id)

        self.config = load_config()
        self.arena_manager = None

        self.console = Console()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.console.print("\n[yellow]⚠️  Shutdown signal received. Saving checkpoint...[/yellow]")
        self.session_manager.shutdown_requested = True

    async def run(self):
        """Run extended competition"""
        self.console.print("\n" + "="*80)
        self.console.print(f"[bold green]🚀 STARTING EXTENDED COMPETITION[/bold green]")
        self.console.print("="*80)
        self.console.print(f"Duration: {self.duration_hours} hours")
        self.console.print(f"Symbol: {self.symbol}")
        self.console.print(f"Checkpoint Interval: {self.checkpoint_interval/60:.0f} minutes")
        self.console.print(f"Report Interval: {self.report_interval/60:.0f} minutes")
        self.console.print(f"Session ID: {self.session_id}")
        self.console.print("="*80 + "\n")

        # Initialize arena
        self.arena_manager = ArenaManager(symbol=self.symbol)

        end_time = datetime.now() + timedelta(hours=self.duration_hours)
        last_checkpoint = datetime.now()
        last_report = datetime.now()
        round_num = 0

        try:
            while datetime.now() < end_time and not self.session_manager.shutdown_requested:
                round_num += 1

                # Run trading round
                self.console.print(f"[cyan]Round {round_num} starting...[/cyan]")
                round_start = time.time()

                try:
                    await self.arena_manager._run_trading_round()
                    round_duration = time.time() - round_start

                    # Record round
                    round_data = {
                        "duration": round_duration,
                        "timestamp": datetime.now().isoformat()
                    }
                    self.session_manager.record_round(round_num, round_data)
                    self.session_manager.monitor.record_api_call(round_duration)

                    # Detect anomalies
                    self.session_manager.detect_anomalies(self.arena_manager)

                except Exception as e:
                    self.console.print(f"[red]❌ Round {round_num} failed: {e}[/red]")
                    self.session_manager.monitor.record_error()

                # Checkpoint if needed
                if (datetime.now() - last_checkpoint).total_seconds() >= self.checkpoint_interval:
                    self.session_manager.save_checkpoint(self.arena_manager)
                    last_checkpoint = datetime.now()

                # Progress report if needed
                if (datetime.now() - last_report).total_seconds() >= self.report_interval:
                    self.session_manager.record_hourly_stats(self.arena_manager)
                    self.session_manager.display_progress_report(self.arena_manager)
                    last_report = datetime.now()

                # Wait for next round
                await asyncio.sleep(self.config.arena.decision_interval)

        except Exception as e:
            self.console.print(f"[bold red]❌ Fatal error: {e}[/bold red]")

        finally:
            # Final checkpoint and report
            self.console.print("\n[yellow]💾 Saving final checkpoint...[/yellow]")
            self.session_manager.save_checkpoint(self.arena_manager)

            self.console.print("[yellow]📊 Generating final report...[/yellow]")
            report_file = self.session_manager.export_final_report(self.arena_manager)

            # Display final summary
            self.session_manager.display_progress_report(self.arena_manager)

            self.console.print("\n" + "="*80)
            self.console.print("[bold green]✅ EXTENDED COMPETITION COMPLETE[/bold green]")
            self.console.print("="*80)
            self.console.print(f"Total Rounds: {round_num}")
            self.console.print(f"Duration: {(datetime.now() - self.session_manager.start_time)}")
            self.console.print(f"Report: {report_file}")
            self.console.print("="*80 + "\n")

            # Cleanup
            await self.arena_manager.cleanup()


# ============================================================================
# CLI
# ============================================================================


@click.command()
@click.option(
    "--duration",
    "-d",
    type=int,
    default=24,
    help="Competition duration in hours (default: 24)"
)
@click.option(
    "--symbol",
    "-s",
    type=str,
    default="BTC/USDT",
    help="Trading symbol (default: BTC/USDT)"
)
@click.option(
    "--checkpoint-interval",
    "-c",
    type=int,
    default=60,
    help="Checkpoint interval in minutes (default: 60)"
)
@click.option(
    "--report-interval",
    "-r",
    type=int,
    default=60,
    help="Progress report interval in minutes (default: 60)"
)
@click.option(
    "--resume",
    type=str,
    help="Resume from checkpoint (provide checkpoint file path)"
)
def main(duration, symbol, checkpoint_interval, report_interval, resume):
    """
    🏃 Extended Competition Runner for AI Trading Arena

    Run long-duration competitions (24+ hours) with automatic checkpointing,
    progress monitoring, and comprehensive analytics.

    Examples:
        python tests/extended_runner.py --duration 24
        python tests/extended_runner.py --duration 48 --checkpoint-interval 30
        python tests/extended_runner.py --resume data/checkpoints/checkpoint_20251030_112514_100.json
    """

    if resume:
        console = Console()
        console.print(f"[yellow]📂 Resume functionality coming soon...[/yellow]")
        console.print(f"[yellow]Would load checkpoint: {resume}[/yellow]")
        return

    runner = ExtendedRunner(
        duration_hours=duration,
        symbol=symbol,
        checkpoint_interval_minutes=checkpoint_interval,
        report_interval_minutes=report_interval
    )

    asyncio.run(runner.run())


if __name__ == "__main__":
    main()
