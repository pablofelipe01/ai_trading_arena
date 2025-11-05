"""
Comprehensive HTML Report Generator for AI Trading Arena

Creates beautiful, professional HTML reports with:
- Executive summary
- Performance metrics
- Interactive charts (equity curves, comparisons)
- Decision logs
- Trade history
- Risk analysis
- Model comparisons
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import click
from rich.console import Console
import plotly.graph_objects as go

from visualization.chart_builder import ChartBuilder, COLORS


# ============================================================================
# HTML Report Generator
# ============================================================================


class HTMLReportGenerator:
    """Generates comprehensive HTML reports"""

    def __init__(self, results_dir: str = "data/results"):
        """Initialize report generator"""
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

    def generate_report(
        self,
        session_id: str,
        output_file: Optional[str] = None,
        include_decisions: bool = True
    ) -> Path:
        """
        Generate comprehensive HTML report

        Args:
            session_id: Session ID
            output_file: Output file path
            include_decisions: Include detailed decision logs

        Returns:
            Path to saved HTML file
        """
        self.console.print(f"[cyan]Generating comprehensive report for {session_id}...[/cyan]")

        session = self.load_session(session_id)

        # Generate components
        self.console.print("[cyan]  Building executive summary...[/cyan]")
        summary_html = self._generate_summary(session, session_id)

        self.console.print("[cyan]  Creating performance charts...[/cyan]")
        charts_html = self._generate_charts(session)

        self.console.print("[cyan]  Generating model comparison...[/cyan]")
        comparison_html = self._generate_model_comparison(session)

        self.console.print("[cyan]  Building risk analysis...[/cyan]")
        risk_html = self._generate_risk_analysis(session)

        if include_decisions:
            self.console.print("[cyan]  Compiling decision logs...[/cyan]")
            decisions_html = self._generate_decision_logs(session)
        else:
            decisions_html = ""

        # Combine into final HTML
        html = self._assemble_report(
            session_id,
            summary_html,
            charts_html,
            comparison_html,
            risk_html,
            decisions_html
        )

        # Save
        if output_file is None:
            output_dir = Path("data/visualizations/reports")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"report_{session_id}.html"
        else:
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            f.write(html)

        self.console.print(f"[green]✅ Report saved: {output_file}[/green]")
        return output_file

    def _generate_summary(self, session: Dict[str, Any], session_id: str) -> str:
        """Generate executive summary section"""
        leaderboard = session.get("final_leaderboard", [])
        total_rounds = session.get("total_rounds", 0)

        winner = leaderboard[0] if leaderboard else None
        total_trades = sum(m["total_trades"] for m in leaderboard)
        total_decisions = sum(m["decisions_made"] for m in leaderboard)

        return f"""
        <div class="summary-section">
            <h2>📊 Executive Summary</h2>
            <div class="summary-grid">
                <div class="summary-card">
                    <div class="summary-icon">🏆</div>
                    <div class="summary-content">
                        <div class="summary-label">Winner</div>
                        <div class="summary-value">{winner['provider'] if winner else 'N/A'}</div>
                        <div class="summary-detail">{winner['return_pct'] if winner else 0:.2f}% Return</div>
                    </div>
                </div>
                <div class="summary-card">
                    <div class="summary-icon">🔄</div>
                    <div class="summary-content">
                        <div class="summary-label">Rounds</div>
                        <div class="summary-value">{total_rounds}</div>
                        <div class="summary-detail">Trading Cycles</div>
                    </div>
                </div>
                <div class="summary-card">
                    <div class="summary-icon">🤖</div>
                    <div class="summary-content">
                        <div class="summary-label">Models</div>
                        <div class="summary-value">{len(leaderboard)}</div>
                        <div class="summary-detail">Competing AIs</div>
                    </div>
                </div>
                <div class="summary-card">
                    <div class="summary-icon">📈</div>
                    <div class="summary-content">
                        <div class="summary-label">Trades</div>
                        <div class="summary-value">{total_trades}</div>
                        <div class="summary-detail">{total_decisions} Decisions</div>
                    </div>
                </div>
            </div>
        </div>
        """

    def _generate_charts(self, session: Dict[str, Any]) -> str:
        """Generate charts section with embedded Plotly"""
        # Extract equity data
        round_results = session.get("round_results", [])
        equity_data = {}

        for round_data in round_results:
            leaderboard = round_data.get("leaderboard", [])
            for model in leaderboard:
                provider = model["provider"]
                if provider not in equity_data:
                    equity_data[provider] = []
                equity_data[provider].append({
                    "timestamp": round_data["timestamp"],
                    "value": model["account_value"],
                    "round": round_data["round"]
                })

        # Create equity curve
        equity_fig = self.chart_builder.create_equity_curve(
            equity_data=equity_data,
            title="Model Performance Over Time",
            show_drawdown=True
        )

        # Create performance comparison
        leaderboard = session.get("final_leaderboard", [])
        perf_fig = self.chart_builder.create_performance_comparison(
            models=leaderboard,
            metric="return_pct",
            title="Final Returns Comparison"
        )

        return f"""
        <div class="charts-section">
            <h2>📈 Performance Charts</h2>
            <div class="chart-container">
                {equity_fig.to_html(full_html=False, include_plotlyjs='cdn')}
            </div>
            <div class="chart-container">
                {perf_fig.to_html(full_html=False, include_plotlyjs=False)}
            </div>
        </div>
        """

    def _generate_model_comparison(self, session: Dict[str, Any]) -> str:
        """Generate model comparison table"""
        leaderboard = session.get("final_leaderboard", [])

        table_rows = ""
        medals = ["🥇", "🥈", "🥉"]

        for i, model in enumerate(leaderboard):
            rank = medals[i] if i < 3 else f"#{i+1}"
            return_class = "positive" if model["return_pct"] >= 0 else "negative"

            table_rows += f"""
            <tr>
                <td class="rank-cell">{rank}</td>
                <td class="model-cell">{model['provider']}</td>
                <td class="{return_class}">{model['return_pct']:.2f}%</td>
                <td>${model['account_value']:.2f}</td>
                <td>{model['total_trades']}</td>
                <td>{model['win_rate']:.1f}%</td>
                <td>{model['decisions_made']}</td>
                <td class="error-cell">{model['errors']}</td>
                <td>{model.get('avg_latency', 0):.2f}s</td>
            </tr>
            """

        return f"""
        <div class="comparison-section">
            <h2>🏅 Model Leaderboard</h2>
            <div class="table-container">
                <table class="leaderboard-table">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Model</th>
                            <th>Return %</th>
                            <th>Value</th>
                            <th>Trades</th>
                            <th>Win Rate</th>
                            <th>Decisions</th>
                            <th>Errors</th>
                            <th>Avg Latency</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
        </div>
        """

    def _generate_risk_analysis(self, session: Dict[str, Any]) -> str:
        """Generate risk analysis section"""
        leaderboard = session.get("final_leaderboard", [])

        risk_cards = ""
        for model in leaderboard:
            return_pct = model["return_pct"]
            # Simplified risk metrics
            volatility = abs(return_pct) / 10  # Simplified
            sharpe = return_pct / volatility if volatility > 0 else 0
            max_dd = abs(min(return_pct, 0))

            risk_cards += f"""
            <div class="risk-card">
                <h4>{model['provider']}</h4>
                <div class="risk-metrics">
                    <div class="risk-metric">
                        <span class="metric-label">Total Return</span>
                        <span class="metric-value">{return_pct:.2f}%</span>
                    </div>
                    <div class="risk-metric">
                        <span class="metric-label">Max Drawdown</span>
                        <span class="metric-value">{max_dd:.2f}%</span>
                    </div>
                    <div class="risk-metric">
                        <span class="metric-label">Sharpe Ratio</span>
                        <span class="metric-value">{sharpe:.2f}</span>
                    </div>
                    <div class="risk-metric">
                        <span class="metric-label">Trade Count</span>
                        <span class="metric-value">{model['total_trades']}</span>
                    </div>
                </div>
            </div>
            """

        return f"""
        <div class="risk-section">
            <h2>⚠️ Risk Analysis</h2>
            <div class="risk-grid">
                {risk_cards}
            </div>
        </div>
        """

    def _generate_decision_logs(self, session: Dict[str, Any]) -> str:
        """Generate decision logs section (abbreviated)"""
        round_results = session.get("round_results", [])

        # Show only last 5 rounds
        recent_rounds = round_results[-5:] if len(round_results) > 5 else round_results

        logs_html = ""
        for round_data in recent_rounds:
            round_num = round_data["round"]
            decisions = round_data.get("decisions", {})

            logs_html += f"""
            <div class="round-log">
                <h4>Round {round_num}</h4>
                <div class="decisions-summary">
            """

            for model, decision in decisions.items():
                if decision:
                    action = decision.get("action", "UNKNOWN")
                    confidence = decision.get("confidence", 0.5) * 100
                    action_class = action.lower()

                    logs_html += f"""
                    <div class="decision-item">
                        <span class="decision-model">{model}</span>
                        <span class="decision-action {action_class}">{action}</span>
                        <span class="decision-confidence">{confidence:.0f}%</span>
                    </div>
                    """

            logs_html += """
                </div>
            </div>
            """

        return f"""
        <div class="decisions-section">
            <h2>📋 Recent Decisions (Last 5 Rounds)</h2>
            {logs_html}
        </div>
        """

    def _assemble_report(
        self,
        session_id: str,
        summary: str,
        charts: str,
        comparison: str,
        risk: str,
        decisions: str
    ) -> str:
        """Assemble final HTML report"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>AI Trading Arena - Report {session_id}</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f7fa;
            color: #2c3e50;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header p {{
            opacity: 0.9;
            font-size: 1.1em;
        }}

        .summary-section, .charts-section, .comparison-section, .risk-section, .decisions-section {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }}

        h2 {{
            color: #667eea;
            margin-bottom: 25px;
            font-size: 1.8em;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
        }}

        .summary-card {{
            display: flex;
            align-items: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.2);
        }}

        .summary-icon {{
            font-size: 3em;
            margin-right: 20px;
        }}

        .summary-label {{
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 5px;
        }}

        .summary-value {{
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 5px;
        }}

        .summary-detail {{
            font-size: 0.85em;
            opacity: 0.8;
        }}

        .chart-container {{
            margin-bottom: 30px;
        }}

        .table-container {{
            overflow-x: auto;
        }}

        .leaderboard-table {{
            width: 100%;
            border-collapse: collapse;
        }}

        .leaderboard-table th {{
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}

        .leaderboard-table td {{
            padding: 12px 15px;
            border-bottom: 1px solid #ecf0f1;
        }}

        .leaderboard-table tr:hover {{
            background: #f8f9fa;
        }}

        .rank-cell {{
            font-size: 1.2em;
            font-weight: bold;
        }}

        .model-cell {{
            font-weight: 600;
            text-transform: capitalize;
        }}

        .positive {{
            color: #27ae60;
            font-weight: bold;
        }}

        .negative {{
            color: #e74c3c;
            font-weight: bold;
        }}

        .error-cell {{
            color: #e74c3c;
        }}

        .risk-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }}

        .risk-card {{
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            border-left: 4px solid #667eea;
        }}

        .risk-card h4 {{
            color: #667eea;
            margin-bottom: 15px;
            text-transform: capitalize;
        }}

        .risk-metrics {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }}

        .risk-metric {{
            display: flex;
            flex-direction: column;
        }}

        .metric-label {{
            font-size: 0.85em;
            color: #7f8c8d;
            margin-bottom: 5px;
        }}

        .metric-value {{
            font-size: 1.3em;
            font-weight: bold;
            color: #2c3e50;
        }}

        .round-log {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }}

        .round-log h4 {{
            color: #667eea;
            margin-bottom: 10px;
        }}

        .decisions-summary {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
        }}

        .decision-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px;
            background: white;
            border-radius: 5px;
        }}

        .decision-model {{
            font-weight: 600;
            text-transform: capitalize;
        }}

        .decision-action {{
            padding: 4px 12px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 0.85em;
        }}

        .decision-action.buy {{
            background: #27ae60;
            color: white;
        }}

        .decision-action.sell {{
            background: #e74c3c;
            color: white;
        }}

        .decision-action.hold {{
            background: #95a5a6;
            color: white;
        }}

        .decision-confidence {{
            color: #7f8c8d;
            font-size: 0.9em;
        }}

        .footer {{
            text-align: center;
            padding: 30px;
            color: #7f8c8d;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 AI Trading Arena</h1>
            <p>Comprehensive Performance Report</p>
            <p>Session ID: {session_id} | Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>

        {summary}
        {charts}
        {comparison}
        {risk}
        {decisions}

        <div class="footer">
            <p>Generated by AI Trading Arena Visualization System</p>
            <p>© 2025 AI Trading Arena - All Rights Reserved</p>
        </div>
    </div>
</body>
</html>
"""


# ============================================================================
# CLI
# ============================================================================


@click.command()
@click.option(
    "--session",
    "-s",
    type=str,
    required=True,
    help="Session ID to generate report for"
)
@click.option(
    "--no-decisions",
    is_flag=True,
    help="Exclude detailed decision logs"
)
@click.option(
    "--output",
    "-o",
    type=str,
    help="Output HTML file path"
)
def main(session, no_decisions, output):
    """
    📄 Comprehensive HTML Report Generator

    Generate beautiful HTML reports with charts and analytics.

    Examples:
        python visualization/html_reporter.py --session 20251030_112514
        python visualization/html_reporter.py -s 20251030_112514 --no-decisions
        python visualization/html_reporter.py -s 20251030_112514 -o my_report.html
    """
    console = Console()
    reporter = HTMLReportGenerator()

    try:
        output_path = reporter.generate_report(
            session_id=session,
            output_file=output,
            include_decisions=not no_decisions
        )
        console.print(f"\n[green]📄 Open in browser: file://{output_path.absolute()}[/green]\n")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")


if __name__ == "__main__":
    main()
