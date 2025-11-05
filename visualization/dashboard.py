"""
Performance Dashboard for AI Trading Arena

Creates comprehensive interactive dashboards with:
- Equity curves
- Performance metrics
- Model comparisons
- Decision analytics
- Risk metrics
- Real-time statistics
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import click
from rich.console import Console

from visualization.chart_builder import ChartBuilder, COLORS


# ============================================================================
# Dashboard Generator
# ============================================================================


class PerformanceDashboard:
    """Generates comprehensive performance dashboards"""

    def __init__(self, results_dir: str = "data/results"):
        """Initialize dashboard generator"""
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

    def generate_dashboard(
        self,
        session_id: str,
        output_file: Optional[str] = None
    ) -> Path:
        """
        Generate comprehensive dashboard

        Args:
            session_id: Session ID
            output_file: Output file path

        Returns:
            Path to saved HTML file
        """
        self.console.print(f"[cyan]Loading session {session_id}...[/cyan]")
        session = self.load_session(session_id)

        self.console.print("[cyan]Building dashboard components...[/cyan]")

        # Create figure with subplots
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=(
                "Equity Curves",
                "Performance Comparison",
                "Decision Distribution",
                "Win Rate & Trades",
                "Confidence Distribution",
                "Error Rates"
            ),
            specs=[
                [{"type": "scatter"}, {"type": "bar"}],
                [{"type": "pie"}, {"type": "bar"}],
                [{"type": "box"}, {"type": "bar"}]
            ],
            row_heights=[0.4, 0.3, 0.3],
            vertical_spacing=0.12,
            horizontal_spacing=0.15
        )

        # Get data
        leaderboard = session.get("final_leaderboard", [])
        round_results = session.get("round_results", [])

        # 1. Equity Curves (Row 1, Col 1)
        self._add_equity_curves(fig, round_results, row=1, col=1)

        # 2. Performance Comparison (Row 1, Col 2)
        self._add_performance_comparison(fig, leaderboard, row=1, col=2)

        # 3. Decision Distribution (Row 2, Col 1)
        self._add_decision_distribution(fig, round_results, row=2, col=1)

        # 4. Win Rate & Trades (Row 2, Col 2)
        self._add_win_rate_trades(fig, leaderboard, row=2, col=2)

        # 5. Confidence Distribution (Row 3, Col 1)
        self._add_confidence_distribution(fig, round_results, row=3, col=1)

        # 6. Error Rates (Row 3, Col 2)
        self._add_error_rates(fig, leaderboard, row=3, col=2)

        # Update layout
        fig.update_layout(
            title=dict(
                text=f"🤖 AI Trading Arena - Performance Dashboard<br><sub>Session: {session_id}</sub>",
                x=0.5,
                xanchor="center",
                font=dict(size=24)
            ),
            showlegend=True,
            height=1200,
            template="plotly_white"
        )

        # Save
        if output_file is None:
            output_dir = Path("data/visualizations/dashboards")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"dashboard_{session_id}.html"
        else:
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)

        fig.write_html(str(output_file))

        self.console.print(f"[green]✅ Dashboard saved: {output_file}[/green]")
        return output_file

    def _add_equity_curves(self, fig, round_results: List[Dict[str, Any]], row: int, col: int):
        """Add equity curves subplot"""
        # Extract equity data
        equity_data = {}

        for round_data in round_results:
            leaderboard = round_data.get("leaderboard", [])

            for model in leaderboard:
                provider = model["provider"]
                if provider not in equity_data:
                    equity_data[provider] = {"rounds": [], "values": []}

                equity_data[provider]["rounds"].append(round_data["round"])
                equity_data[provider]["values"].append(model["account_value"])

        # Plot curves
        for model, data in equity_data.items():
            color = COLORS.get(model.lower(), COLORS["neutral"])
            fig.add_trace(
                go.Scatter(
                    x=data["rounds"],
                    y=data["values"],
                    name=model,
                    mode="lines",
                    line=dict(color=color, width=2),
                    showlegend=True,
                    legendgroup=model
                ),
                row=row, col=col
            )

        fig.update_xaxes(title_text="Round", row=row, col=col)
        fig.update_yaxes(title_text="Account Value ($)", row=row, col=col)

    def _add_performance_comparison(self, fig, leaderboard: List[Dict[str, Any]], row: int, col: int):
        """Add performance comparison subplot"""
        models = [m["provider"] for m in leaderboard]
        returns = [m["return_pct"] for m in leaderboard]
        colors_list = [COLORS["profit"] if r >= 0 else COLORS["loss"] for r in returns]

        fig.add_trace(
            go.Bar(
                x=models,
                y=returns,
                marker_color=colors_list,
                text=[f"{r:.1f}%" for r in returns],
                textposition="outside",
                showlegend=False
            ),
            row=row, col=col
        )

        fig.update_xaxes(title_text="Model", row=row, col=col)
        fig.update_yaxes(title_text="Return (%)", row=row, col=col)

    def _add_decision_distribution(self, fig, round_results: List[Dict[str, Any]], row: int, col: int):
        """Add decision distribution pie chart"""
        action_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}

        for round_data in round_results:
            decisions = round_data.get("decisions", {})
            for decision in decisions.values():
                if decision:
                    action = decision.get("action", "HOLD")
                    action_counts[action] = action_counts.get(action, 0) + 1

        fig.add_trace(
            go.Pie(
                labels=list(action_counts.keys()),
                values=list(action_counts.values()),
                marker=dict(colors=["#27ae60", "#e74c3c", "#95a5a6"]),
                showlegend=False
            ),
            row=row, col=col
        )

    def _add_win_rate_trades(self, fig, leaderboard: List[Dict[str, Any]], row: int, col: int):
        """Add win rate and trades subplot"""
        models = [m["provider"] for m in leaderboard]
        win_rates = [m["win_rate"] for m in leaderboard]
        trades = [m["total_trades"] for m in leaderboard]

        # Win rate bars
        fig.add_trace(
            go.Bar(
                x=models,
                y=win_rates,
                name="Win Rate (%)",
                marker_color="#3498db",
                yaxis="y",
                showlegend=False
            ),
            row=row, col=col
        )

        # Trades line (secondary axis would be ideal, but simplified here)
        fig.update_xaxes(title_text="Model", row=row, col=col)
        fig.update_yaxes(title_text="Win Rate (%)", row=row, col=col)

    def _add_confidence_distribution(self, fig, round_results: List[Dict[str, Any]], row: int, col: int):
        """Add confidence distribution box plot"""
        confidence_by_model = {}

        for round_data in round_results:
            decisions = round_data.get("decisions", {})
            for model, decision in decisions.items():
                if decision:
                    if model not in confidence_by_model:
                        confidence_by_model[model] = []
                    confidence_by_model[model].append(decision.get("confidence", 0.5))

        for model, confidences in confidence_by_model.items():
            color = COLORS.get(model.lower(), COLORS["neutral"])
            fig.add_trace(
                go.Box(
                    y=confidences,
                    name=model,
                    marker_color=color,
                    showlegend=False
                ),
                row=row, col=col
            )

        fig.update_xaxes(title_text="Model", row=row, col=col)
        fig.update_yaxes(title_text="Confidence", row=row, col=col)

    def _add_error_rates(self, fig, leaderboard: List[Dict[str, Any]], row: int, col: int):
        """Add error rates subplot"""
        models = [m["provider"] for m in leaderboard]
        errors = [m["errors"] for m in leaderboard]

        fig.add_trace(
            go.Bar(
                x=models,
                y=errors,
                marker_color=COLORS["loss"],
                text=errors,
                textposition="outside",
                showlegend=False
            ),
            row=row, col=col
        )

        fig.update_xaxes(title_text="Model", row=row, col=col)
        fig.update_yaxes(title_text="Error Count", row=row, col=col)

    def generate_metrics_summary(self, session_id: str) -> Dict[str, Any]:
        """Generate metrics summary"""
        session = self.load_session(session_id)
        leaderboard = session.get("final_leaderboard", [])

        summary = {
            "session_id": session_id,
            "total_rounds": session.get("total_rounds", 0),
            "models": len(leaderboard),
            "winner": leaderboard[0]["provider"] if leaderboard else None,
            "winner_return": leaderboard[0]["return_pct"] if leaderboard else 0,
            "best_win_rate": max((m["win_rate"] for m in leaderboard), default=0),
            "total_trades": sum(m["total_trades"] for m in leaderboard),
            "total_errors": sum(m["errors"] for m in leaderboard),
            "avg_return": sum(m["return_pct"] for m in leaderboard) / len(leaderboard) if leaderboard else 0
        }

        return summary

    def print_summary(self, session_id: str):
        """Print dashboard summary"""
        summary = self.generate_metrics_summary(session_id)

        self.console.print(f"\n[bold cyan]📊 Dashboard Summary - {session_id}[/bold cyan]\n")
        self.console.print(f"Total Rounds: {summary['total_rounds']}")
        self.console.print(f"Models: {summary['models']}")
        self.console.print(f"Winner: {summary['winner']} ({summary['winner_return']:.2f}%)")
        self.console.print(f"Best Win Rate: {summary['best_win_rate']:.1f}%")
        self.console.print(f"Total Trades: {summary['total_trades']}")
        self.console.print(f"Total Errors: {summary['total_errors']}")
        self.console.print(f"Average Return: {summary['avg_return']:.2f}%\n")


# ============================================================================
# CLI
# ============================================================================


@click.command()
@click.option(
    "--session",
    "-s",
    type=str,
    required=True,
    help="Session ID to visualize"
)
@click.option(
    "--summary",
    is_flag=True,
    help="Print summary instead of generating dashboard"
)
@click.option(
    "--output",
    "-o",
    type=str,
    help="Output HTML file path"
)
def main(session, summary, output):
    """
    📊 Performance Dashboard Generator

    Generate comprehensive interactive dashboards.

    Examples:
        python visualization/dashboard.py --session 20251030_112514
        python visualization/dashboard.py -s 20251030_112514 --summary
        python visualization/dashboard.py -s 20251030_112514 -o my_dashboard.html
    """
    console = Console()
    dashboard = PerformanceDashboard()

    try:
        if summary:
            dashboard.print_summary(session)
        else:
            output_path = dashboard.generate_dashboard(session, output)
            console.print(f"\n[green]📄 Open in browser: file://{output_path.absolute()}[/green]\n")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")


if __name__ == "__main__":
    main()
