"""
Results Analyzer and Statistics Generator for AI Trading Arena

Analyzes competition results to provide:
- Performance statistics
- Model comparisons
- Trend analysis
- Win/loss patterns
- Risk metrics
- Trading behavior analysis

Usage:
    python tests/results_analyzer.py --session session_20251030_112514
    python tests/results_analyzer.py --compare session1 session2 session3
    python tests/results_analyzer.py --all --export
"""

import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


# ============================================================================
# Results Analyzer
# ============================================================================


class ResultsAnalyzer:
    """Analyzes trading competition results"""

    def __init__(self, results_dir: str = "data/results"):
        """Initialize analyzer"""
        self.results_dir = Path(results_dir)
        self.console = Console()

    def load_session(self, session_id: str) -> Dict[str, Any]:
        """Load session results"""
        session_file = self.results_dir / f"session_{session_id}.json"

        if not session_file.exists():
            # Try extended session format
            session_file = self.results_dir / f"extended_session_{session_id}.json"

        if not session_file.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        with open(session_file, "r") as f:
            return json.load(f)

    def list_sessions(self) -> List[str]:
        """List all available sessions"""
        sessions = []

        for file in self.results_dir.glob("session_*.json"):
            session_id = file.stem.replace("session_", "")
            sessions.append(session_id)

        for file in self.results_dir.glob("extended_session_*.json"):
            session_id = file.stem.replace("extended_session_", "")
            sessions.append(session_id)

        return sorted(sessions)

    def calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio"""
        if not returns or len(returns) < 2:
            return 0.0

        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)

        if std_return == 0:
            return 0.0

        return (avg_return - risk_free_rate) / std_return

    def calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate maximum drawdown"""
        if not equity_curve:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0.0

        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        return max_dd * 100  # Return as percentage

    def analyze_session(self, session_id: str) -> Dict[str, Any]:
        """Perform comprehensive session analysis"""
        session = self.load_session(session_id)

        analysis = {
            "session_id": session_id,
            "session_info": self._analyze_session_info(session),
            "model_performance": self._analyze_model_performance(session),
            "trading_behavior": self._analyze_trading_behavior(session),
            "risk_metrics": self._analyze_risk_metrics(session),
            "decision_analysis": self._analyze_decisions(session),
            "round_progression": self._analyze_round_progression(session)
        }

        return analysis

    def _analyze_session_info(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze basic session information"""
        start = datetime.fromisoformat(session["session_start"])
        end = datetime.fromisoformat(session["session_end"])
        duration = (end - start).total_seconds() / 60  # Minutes

        return {
            "start_time": session["session_start"],
            "end_time": session["session_end"],
            "duration_minutes": duration,
            "duration_hours": duration / 60,
            "symbol": session["symbol"],
            "total_rounds": session["total_rounds"],
            "avg_round_duration": duration / session["total_rounds"] if session["total_rounds"] > 0 else 0
        }

    def _analyze_model_performance(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze individual model performance"""
        leaderboard = session.get("final_leaderboard", [])

        model_stats = {}
        for model in leaderboard:
            provider = model["provider"]

            # Calculate additional metrics
            trades = model["total_trades"]
            wins = int(trades * model["win_rate"] / 100) if trades > 0 else 0
            losses = trades - wins

            profit_factor = abs(model["return_pct"]) / 100 if model["return_pct"] < 0 else model["return_pct"] / 10

            model_stats[provider] = {
                "return_pct": model["return_pct"],
                "account_value": model["account_value"],
                "total_trades": trades,
                "wins": wins,
                "losses": losses,
                "win_rate": model["win_rate"],
                "errors": model["errors"],
                "avg_latency": model.get("avg_latency", 0),
                "decisions_made": model["decisions_made"],
                "trade_frequency": trades / session["total_rounds"] if session["total_rounds"] > 0 else 0,
                "error_rate": model["errors"] / model["decisions_made"] if model["decisions_made"] > 0 else 0,
                "profit_factor": profit_factor
            }

        return model_stats

    def _analyze_trading_behavior(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze trading behavior patterns"""
        round_results = session.get("round_results", [])

        behavior = {
            "action_distribution": defaultdict(lambda: defaultdict(int)),
            "confidence_stats": defaultdict(list),
            "execution_rate": defaultdict(lambda: {"executed": 0, "total": 0})
        }

        for round_data in round_results:
            decisions = round_data.get("decisions", {})
            executions = round_data.get("executions", {})

            for model, decision in decisions.items():
                if decision:
                    # Action distribution
                    action = decision.get("action", "UNKNOWN")
                    behavior["action_distribution"][model][action] += 1

                    # Confidence
                    confidence = decision.get("confidence", 0)
                    behavior["confidence_stats"][model].append(confidence)

                    # Execution rate
                    behavior["execution_rate"][model]["total"] += 1
                    if executions.get(model, False):
                        behavior["execution_rate"][model]["executed"] += 1

        # Calculate execution percentages
        execution_summary = {}
        for model, counts in behavior["execution_rate"].items():
            execution_summary[model] = {
                "execution_rate": counts["executed"] / counts["total"] * 100 if counts["total"] > 0 else 0,
                "total_decisions": counts["total"],
                "executed_decisions": counts["executed"]
            }

        return {
            "action_distribution": dict(behavior["action_distribution"]),
            "confidence_stats": {
                model: {
                    "avg": statistics.mean(conf) if conf else 0,
                    "min": min(conf) if conf else 0,
                    "max": max(conf) if conf else 0,
                    "stdev": statistics.stdev(conf) if len(conf) > 1 else 0
                }
                for model, conf in behavior["confidence_stats"].items()
            },
            "execution_summary": execution_summary
        }

    def _analyze_risk_metrics(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze risk metrics"""
        round_results = session.get("round_results", [])
        leaderboard = session.get("final_leaderboard", [])

        risk_metrics = {}

        for model_data in leaderboard:
            provider = model_data["provider"]

            # Build equity curve from round history
            equity_curve = [100.0]  # Start with $100
            returns = []

            for round_data in round_results:
                # This is simplified - in a real implementation, track actual portfolio value
                pass

            # Calculate risk metrics
            final_return = model_data["return_pct"]
            trades = model_data["total_trades"]

            risk_metrics[provider] = {
                "total_return": final_return,
                "max_drawdown": abs(final_return) if final_return < 0 else 0,
                "sharpe_ratio": 0.0,  # Would need return series
                "risk_per_trade": abs(final_return) / trades if trades > 0 else 0,
                "return_to_risk": final_return / abs(final_return) if final_return < 0 else float('inf')
            }

        return risk_metrics

    def _analyze_decisions(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze decision quality"""
        round_results = session.get("round_results", [])

        decision_analysis = {
            "total_decisions": 0,
            "buy_decisions": 0,
            "sell_decisions": 0,
            "hold_decisions": 0,
            "avg_confidence": 0,
            "high_confidence_decisions": 0,  # >0.8
            "low_confidence_decisions": 0,   # <0.5
        }

        confidences = []

        for round_data in round_results:
            decisions = round_data.get("decisions", {})

            for model, decision in decisions.items():
                if decision:
                    decision_analysis["total_decisions"] += 1

                    action = decision.get("action", "HOLD")
                    if action == "BUY":
                        decision_analysis["buy_decisions"] += 1
                    elif action == "SELL":
                        decision_analysis["sell_decisions"] += 1
                    else:
                        decision_analysis["hold_decisions"] += 1

                    confidence = decision.get("confidence", 0.5)
                    confidences.append(confidence)

                    if confidence > 0.8:
                        decision_analysis["high_confidence_decisions"] += 1
                    elif confidence < 0.5:
                        decision_analysis["low_confidence_decisions"] += 1

        decision_analysis["avg_confidence"] = statistics.mean(confidences) if confidences else 0

        return decision_analysis

    def _analyze_round_progression(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze how models performed over rounds"""
        round_results = session.get("round_results", [])

        progression = defaultdict(list)

        for round_data in round_results:
            leaderboard = round_data.get("leaderboard", [])

            for model_data in leaderboard:
                provider = model_data["provider"]
                progression[provider].append({
                    "round": round_data["round"],
                    "return_pct": model_data["return_pct"],
                    "account_value": model_data["account_value"],
                    "trades": model_data["total_trades"]
                })

        return dict(progression)

    def compare_sessions(self, session_ids: List[str]) -> Dict[str, Any]:
        """Compare multiple sessions"""
        sessions_data = []

        for session_id in session_ids:
            try:
                session = self.load_session(session_id)
                analysis = self.analyze_session(session_id)
                sessions_data.append({
                    "session_id": session_id,
                    "session": session,
                    "analysis": analysis
                })
            except FileNotFoundError:
                self.console.print(f"[yellow]⚠️  Session not found: {session_id}[/yellow]")

        if not sessions_data:
            return {}

        comparison = {
            "sessions_compared": len(sessions_data),
            "model_comparison": self._compare_models(sessions_data),
            "session_comparison": self._compare_sessions_stats(sessions_data)
        }

        return comparison

    def _compare_models(self, sessions_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare model performance across sessions"""
        model_stats = defaultdict(lambda: {
            "sessions": 0,
            "avg_return": 0,
            "best_return": float('-inf'),
            "worst_return": float('inf'),
            "returns": []
        })

        for session_data in sessions_data:
            leaderboard = session_data["session"].get("final_leaderboard", [])

            for model in leaderboard:
                provider = model["provider"]
                return_pct = model["return_pct"]

                model_stats[provider]["sessions"] += 1
                model_stats[provider]["returns"].append(return_pct)
                model_stats[provider]["best_return"] = max(
                    model_stats[provider]["best_return"],
                    return_pct
                )
                model_stats[provider]["worst_return"] = min(
                    model_stats[provider]["worst_return"],
                    return_pct
                )

        # Calculate averages
        for provider in model_stats:
            returns = model_stats[provider]["returns"]
            model_stats[provider]["avg_return"] = statistics.mean(returns) if returns else 0
            model_stats[provider]["stdev_return"] = statistics.stdev(returns) if len(returns) > 1 else 0
            model_stats[provider]["consistency"] = 1.0 / (1.0 + model_stats[provider]["stdev_return"])

        return dict(model_stats)

    def _compare_sessions_stats(self, sessions_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Compare session-level statistics"""
        stats = []

        for session_data in sessions_data:
            session = session_data["session"]
            analysis = session_data["analysis"]

            stats.append({
                "session_id": session_data["session_id"],
                "duration_hours": analysis["session_info"]["duration_hours"],
                "total_rounds": session["total_rounds"],
                "winner": session["final_leaderboard"][0]["provider"] if session["final_leaderboard"] else None,
                "winner_return": session["final_leaderboard"][0]["return_pct"] if session["final_leaderboard"] else 0,
                "total_decisions": analysis["decision_analysis"]["total_decisions"]
            })

        return stats

    def export_analysis(self, analysis: Dict[str, Any], output_file: Path):
        """Export analysis to JSON file"""
        with open(output_file, "w") as f:
            json.dump(analysis, f, indent=2)

        self.console.print(f"[green]✅ Analysis exported: {output_file}[/green]")


# ============================================================================
# Display Functions
# ============================================================================


def display_session_analysis(console: Console, analysis: Dict[str, Any]):
    """Display session analysis in terminal"""
    console.print("\n" + "="*80)
    console.print(f"[bold cyan]📊 SESSION ANALYSIS: {analysis['session_id']}[/bold cyan]")
    console.print("="*80)

    # Session Info
    info = analysis["session_info"]
    console.print(Panel(
        f"Duration: {info['duration_hours']:.2f} hours\n"
        f"Rounds: {info['total_rounds']}\n"
        f"Symbol: {info['symbol']}\n"
        f"Avg Round: {info['avg_round_duration']:.2f} min",
        title="Session Info",
        border_style="cyan"
    ))

    # Model Performance Table
    table = Table(title="Model Performance")
    table.add_column("Model", style="cyan")
    table.add_column("Return %", style="green")
    table.add_column("Trades", style="yellow")
    table.add_column("Win Rate", style="blue")
    table.add_column("Errors", style="red")
    table.add_column("Latency", style="magenta")

    for model, stats in analysis["model_performance"].items():
        table.add_row(
            model,
            f"{stats['return_pct']:.2f}%",
            str(stats['total_trades']),
            f"{stats['win_rate']:.1f}%",
            str(stats['errors']),
            f"{stats['avg_latency']:.2f}s"
        )

    console.print(table)

    # Decision Analysis
    decisions = analysis["decision_analysis"]
    console.print(Panel(
        f"Total Decisions: {decisions['total_decisions']}\n"
        f"BUY: {decisions['buy_decisions']} | "
        f"SELL: {decisions['sell_decisions']} | "
        f"HOLD: {decisions['hold_decisions']}\n"
        f"Avg Confidence: {decisions['avg_confidence']:.2f}\n"
        f"High Confidence (>0.8): {decisions['high_confidence_decisions']}\n"
        f"Low Confidence (<0.5): {decisions['low_confidence_decisions']}",
        title="Decision Analysis",
        border_style="green"
    ))

    console.print("="*80 + "\n")


def display_comparison(console: Console, comparison: Dict[str, Any]):
    """Display session comparison"""
    console.print("\n" + "="*80)
    console.print(f"[bold cyan]📊 SESSION COMPARISON ({comparison['sessions_compared']} sessions)[/bold cyan]")
    console.print("="*80)

    # Model comparison table
    table = Table(title="Model Performance Across Sessions")
    table.add_column("Model", style="cyan")
    table.add_column("Sessions", style="yellow")
    table.add_column("Avg Return", style="green")
    table.add_column("Best Return", style="blue")
    table.add_column("Worst Return", style="red")
    table.add_column("Consistency", style="magenta")

    for model, stats in comparison["model_comparison"].items():
        table.add_row(
            model,
            str(stats["sessions"]),
            f"{stats['avg_return']:.2f}%",
            f"{stats['best_return']:.2f}%",
            f"{stats['worst_return']:.2f}%",
            f"{stats['consistency']:.2f}"
        )

    console.print(table)
    console.print("="*80 + "\n")


# ============================================================================
# CLI
# ============================================================================


@click.command()
@click.option(
    "--session",
    "-s",
    type=str,
    help="Analyze specific session"
)
@click.option(
    "--compare",
    "-c",
    multiple=True,
    help="Compare multiple sessions (use multiple -c flags)"
)
@click.option(
    "--all",
    "analyze_all",
    is_flag=True,
    help="Analyze all available sessions"
)
@click.option(
    "--list",
    "list_sessions",
    is_flag=True,
    help="List all available sessions"
)
@click.option(
    "--export",
    "-e",
    type=str,
    help="Export analysis to file"
)
def main(session, compare, analyze_all, list_sessions, export):
    """
    📊 Results Analyzer for AI Trading Arena

    Analyze competition results and generate statistics.

    Examples:
        python tests/results_analyzer.py --session 20251030_112514
        python tests/results_analyzer.py -c session1 -c session2 -c session3
        python tests/results_analyzer.py --all
        python tests/results_analyzer.py --list
    """
    console = Console()
    analyzer = ResultsAnalyzer()

    if list_sessions:
        sessions = analyzer.list_sessions()
        console.print(f"\n[bold cyan]Available Sessions ({len(sessions)}):[/bold cyan]")
        for s in sessions:
            console.print(f"  - {s}")
        console.print()
        return

    if session:
        try:
            analysis = analyzer.analyze_session(session)
            display_session_analysis(console, analysis)

            if export:
                output_file = Path(export)
                analyzer.export_analysis(analysis, output_file)
        except FileNotFoundError as e:
            console.print(f"[red]❌ {e}[/red]")

    elif compare:
        comparison = analyzer.compare_sessions(list(compare))
        display_comparison(console, comparison)

        if export:
            output_file = Path(export)
            analyzer.export_analysis(comparison, output_file)

    elif analyze_all:
        sessions = analyzer.list_sessions()
        console.print(f"[cyan]Analyzing {len(sessions)} sessions...[/cyan]")

        for session_id in sessions:
            try:
                analysis = analyzer.analyze_session(session_id)
                display_session_analysis(console, analysis)
            except Exception as e:
                console.print(f"[red]❌ Error analyzing {session_id}: {e}[/red]")

    else:
        console.print("[yellow]⚠️  Please specify --session, --compare, --all, or --list[/yellow]")
        console.print("[yellow]Use --help for more information[/yellow]")


if __name__ == "__main__":
    main()
