"""
Equity Curve Visualization for AI Trading Arena

Creates beautiful equity curve visualizations showing:
- Model performance over time
- Drawdown analysis
- Comparative performance
- Risk-adjusted returns
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import click
from rich.console import Console

from visualization.chart_builder import ChartBuilder, save_chart


# ============================================================================
# Equity Curve Generator
# ============================================================================


class EquityCurveGenerator:
    """Generates equity curve visualizations from session data"""

    def __init__(self, results_dir: str = "data/results"):
        """Initialize equity curve generator"""
        self.results_dir = Path(results_dir)
        self.chart_builder = ChartBuilder()
        self.console = Console()

    def load_session(self, session_id: str) -> Dict[str, Any]:
        """Load session results"""
        session_file = self.results_dir / f"session_{session_id}.json"

        if not session_file.exists():
            session_file = self.results_dir / f"extended_session_{session_id}.json"

        if not session_file.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        with open(session_file, "r") as f:
            return json.load(f)

    def extract_equity_data(self, session: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract equity curve data from session

        Returns:
            Dict mapping model names to equity history
        """
        round_results = session.get("round_results", [])

        equity_curves = {}

        for round_data in round_results:
            round_num = round_data["round"]
            timestamp = round_data["timestamp"]
            leaderboard = round_data.get("leaderboard", [])

            for model in leaderboard:
                provider = model["provider"]

                if provider not in equity_curves:
                    equity_curves[provider] = []

                equity_curves[provider].append({
                    "timestamp": timestamp,
                    "value": model["account_value"],
                    "round": round_num,
                    "return_pct": model["return_pct"]
                })

        return equity_curves

    def generate_equity_curve(
        self,
        session_id: str,
        show_drawdown: bool = True,
        output_file: Optional[str] = None
    ) -> Path:
        """
        Generate equity curve chart for session

        Args:
            session_id: Session ID
            show_drawdown: Show drawdown subplot
            output_file: Output file path (auto-generated if None)

        Returns:
            Path to saved chart
        """
        self.console.print(f"[cyan]Loading session {session_id}...[/cyan]")
        session = self.load_session(session_id)

        self.console.print("[cyan]Extracting equity data...[/cyan]")
        equity_data = self.extract_equity_data(session)

        if not equity_data:
            raise ValueError("No equity data found in session")

        self.console.print(f"[cyan]Generating chart for {len(equity_data)} models...[/cyan]")

        # Create chart
        fig = self.chart_builder.create_equity_curve(
            equity_data=equity_data,
            title=f"Equity Curves - Session {session_id}",
            show_drawdown=show_drawdown
        )

        # Determine output path
        if output_file is None:
            output_dir = Path("data/visualizations/equity_curves")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"equity_curve_{session_id}.html"
        else:
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)

        # Save chart
        save_chart(fig, str(output_file), format="html")

        self.console.print(f"[green]✅ Equity curve saved: {output_file}[/green]")
        return output_file

    def generate_comparative_chart(
        self,
        session_ids: List[str],
        model_name: str,
        output_file: Optional[str] = None
    ) -> Path:
        """
        Generate comparative equity curve for single model across sessions

        Args:
            session_ids: List of session IDs
            model_name: Model to compare
            output_file: Output file path

        Returns:
            Path to saved chart
        """
        self.console.print(f"[cyan]Generating comparative chart for {model_name}...[/cyan]")

        equity_data = {}

        for session_id in session_ids:
            try:
                session = self.load_session(session_id)
                session_equity = self.extract_equity_data(session)

                if model_name in session_equity:
                    equity_data[f"{model_name} - {session_id}"] = session_equity[model_name]
                else:
                    self.console.print(f"[yellow]⚠️  {model_name} not found in {session_id}[/yellow]")

            except FileNotFoundError:
                self.console.print(f"[yellow]⚠️  Session not found: {session_id}[/yellow]")

        if not equity_data:
            raise ValueError(f"No data found for {model_name}")

        # Create chart
        fig = self.chart_builder.create_equity_curve(
            equity_data=equity_data,
            title=f"{model_name} - Comparative Performance",
            show_drawdown=True
        )

        # Save
        if output_file is None:
            output_dir = Path("data/visualizations/comparative")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"comparative_{model_name}.html"
        else:
            output_file = Path(output_file)

        save_chart(fig, str(output_file), format="html")
        self.console.print(f"[green]✅ Comparative chart saved: {output_file}[/green]")
        return output_file

    def generate_all_sessions_overlay(
        self,
        output_file: Optional[str] = None
    ) -> Path:
        """
        Generate overlay of all sessions

        Args:
            output_file: Output file path

        Returns:
            Path to saved chart
        """
        self.console.print("[cyan]Finding all sessions...[/cyan]")

        # Find all sessions
        session_files = list(self.results_dir.glob("session_*.json"))
        session_files += list(self.results_dir.glob("extended_session_*.json"))

        if not session_files:
            raise ValueError("No sessions found")

        self.console.print(f"[cyan]Found {len(session_files)} sessions[/cyan]")

        equity_data = {}

        for session_file in session_files:
            session_id = session_file.stem.replace("session_", "").replace("extended_session_", "")

            try:
                session = self.load_session(session_id)
                session_equity = self.extract_equity_data(session)

                # Get winner
                final_leaderboard = session.get("final_leaderboard", [])
                if final_leaderboard:
                    winner = final_leaderboard[0]["provider"]
                    equity_data[f"{winner} ({session_id})"] = session_equity.get(winner, [])

            except Exception as e:
                self.console.print(f"[yellow]⚠️  Error loading {session_id}: {e}[/yellow]")

        if not equity_data:
            raise ValueError("No equity data found")

        # Create chart
        fig = self.chart_builder.create_equity_curve(
            equity_data=equity_data,
            title="All Sessions - Winners Overlay",
            show_drawdown=False
        )

        # Save
        if output_file is None:
            output_dir = Path("data/visualizations/overlays")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / "all_sessions_overlay.html"
        else:
            output_file = Path(output_file)

        save_chart(fig, str(output_file), format="html")
        self.console.print(f"[green]✅ Overlay chart saved: {output_file}[/green]")
        return output_file

    def calculate_statistics(self, equity_curve: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate statistics from equity curve"""
        if not equity_curve:
            return {}

        values = [e["value"] for e in equity_curve]
        returns = [e["return_pct"] for e in equity_curve]

        # Calculate metrics
        initial_value = values[0]
        final_value = values[-1]
        total_return = (final_value - initial_value) / initial_value * 100

        # Max drawdown
        peak = initial_value
        max_dd = 0
        for value in values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100
            max_dd = max(max_dd, dd)

        # Volatility (std dev of returns)
        if len(returns) > 1:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            volatility = variance ** 0.5
        else:
            volatility = 0

        # Sharpe ratio (simplified, assuming risk-free rate = 0)
        sharpe = (total_return / volatility) if volatility > 0 else 0

        return {
            "initial_value": initial_value,
            "final_value": final_value,
            "total_return_pct": total_return,
            "max_drawdown_pct": max_dd,
            "volatility": volatility,
            "sharpe_ratio": sharpe,
            "num_periods": len(equity_curve)
        }

    def print_statistics(self, session_id: str):
        """Print equity curve statistics"""
        session = self.load_session(session_id)
        equity_data = self.extract_equity_data(session)

        self.console.print(f"\n[bold cyan]📊 Equity Curve Statistics - {session_id}[/bold cyan]\n")

        for model_name, equity_curve in equity_data.items():
            stats = self.calculate_statistics(equity_curve)

            self.console.print(f"[bold]{model_name}:[/bold]")
            self.console.print(f"  Initial Value: ${stats['initial_value']:.2f}")
            self.console.print(f"  Final Value: ${stats['final_value']:.2f}")
            self.console.print(f"  Total Return: {stats['total_return_pct']:.2f}%")
            self.console.print(f"  Max Drawdown: {stats['max_drawdown_pct']:.2f}%")
            self.console.print(f"  Volatility: {stats['volatility']:.2f}")
            self.console.print(f"  Sharpe Ratio: {stats['sharpe_ratio']:.2f}")
            self.console.print(f"  Periods: {stats['num_periods']}\n")


# ============================================================================
# CLI
# ============================================================================


@click.command()
@click.option(
    "--session",
    "-s",
    type=str,
    help="Generate equity curve for specific session"
)
@click.option(
    "--compare",
    "-c",
    multiple=True,
    help="Compare model across sessions (use with --model)"
)
@click.option(
    "--model",
    "-m",
    type=str,
    help="Model name for comparison"
)
@click.option(
    "--overlay",
    is_flag=True,
    help="Generate overlay of all sessions"
)
@click.option(
    "--stats",
    is_flag=True,
    help="Print statistics instead of generating chart"
)
@click.option(
    "--no-drawdown",
    is_flag=True,
    help="Don't show drawdown subplot"
)
@click.option(
    "--output",
    "-o",
    type=str,
    help="Output file path"
)
def main(session, compare, model, overlay, stats, no_drawdown, output):
    """
    📈 Equity Curve Visualization Tool

    Generate beautiful equity curve charts from trading sessions.

    Examples:
        python visualization/equity_curves.py --session 20251030_112514
        python visualization/equity_curves.py -s 20251030_112514 --stats
        python visualization/equity_curves.py -c session1 -c session2 --model deepseek
        python visualization/equity_curves.py --overlay
    """
    console = Console()
    generator = EquityCurveGenerator()

    try:
        if session:
            if stats:
                generator.print_statistics(session)
            else:
                output_path = generator.generate_equity_curve(
                    session_id=session,
                    show_drawdown=not no_drawdown,
                    output_file=output
                )
                console.print(f"\n[green]📄 Open in browser: file://{output_path.absolute()}[/green]\n")

        elif compare and model:
            output_path = generator.generate_comparative_chart(
                session_ids=list(compare),
                model_name=model,
                output_file=output
            )
            console.print(f"\n[green]📄 Open in browser: file://{output_path.absolute()}[/green]\n")

        elif overlay:
            output_path = generator.generate_all_sessions_overlay(output_file=output)
            console.print(f"\n[green]📄 Open in browser: file://{output_path.absolute()}[/green]\n")

        else:
            console.print("[yellow]⚠️  Please specify --session, --compare + --model, or --overlay[/yellow]")
            console.print("[yellow]Use --help for more information[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")


if __name__ == "__main__":
    main()
