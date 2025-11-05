"""
Decision Logs Viewer for AI Trading Arena

Creates interactive HTML viewer for trading decisions showing:
- All decisions with reasoning
- Confidence levels
- Execution status
- Model comparisons
- Timeline view
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import click
from rich.console import Console


# ============================================================================
# Decision Viewer
# ============================================================================


class DecisionViewer:
    """Generates interactive decision log viewers"""

    def __init__(self, results_dir: str = "data/results"):
        """Initialize decision viewer"""
        self.results_dir = Path(results_dir)
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

    def extract_decisions(self, session: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all decisions from session"""
        round_results = session.get("round_results", [])
        all_decisions = []

        for round_data in round_results:
            round_num = round_data["round"]
            timestamp = round_data["timestamp"]
            price = round_data.get("price", 0)
            decisions = round_data.get("decisions", {})
            executions = round_data.get("executions", {})

            for model, decision in decisions.items():
                if decision:
                    all_decisions.append({
                        "round": round_num,
                        "timestamp": timestamp,
                        "price": price,
                        "model": model,
                        "action": decision.get("action", "UNKNOWN"),
                        "confidence": decision.get("confidence", 0.5),
                        "reasoning": decision.get("reasoning", "No reasoning provided"),
                        "position_size": decision.get("position_size", 0),
                        "executed": executions.get(model, False)
                    })

        return all_decisions

    def generate_html_viewer(
        self,
        session_id: str,
        output_file: Optional[str] = None
    ) -> Path:
        """
        Generate interactive HTML decision viewer

        Args:
            session_id: Session ID
            output_file: Output file path

        Returns:
            Path to saved HTML file
        """
        self.console.print(f"[cyan]Loading session {session_id}...[/cyan]")
        session = self.load_session(session_id)

        self.console.print("[cyan]Extracting decisions...[/cyan]")
        decisions = self.extract_decisions(session)

        if not decisions:
            raise ValueError("No decisions found in session")

        self.console.print(f"[cyan]Generating HTML viewer for {len(decisions)} decisions...[/cyan]")

        # Generate HTML
        html = self._generate_html(session_id, decisions, session)

        # Save
        if output_file is None:
            output_dir = Path("data/visualizations/decisions")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"decisions_{session_id}.html"
        else:
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            f.write(html)

        self.console.print(f"[green]✅ Decision viewer saved: {output_file}[/green]")
        return output_file

    def _generate_html(
        self,
        session_id: str,
        decisions: List[Dict[str, Any]],
        session: Dict[str, Any]
    ) -> str:
        """Generate HTML content"""

        # Group decisions by round
        decisions_by_round = {}
        for decision in decisions:
            round_num = decision["round"]
            if round_num not in decisions_by_round:
                decisions_by_round[round_num] = []
            decisions_by_round[round_num].append(decision)

        # Generate decision cards
        decision_cards_html = ""
        for round_num in sorted(decisions_by_round.keys()):
            round_decisions = decisions_by_round[round_num]

            # Round header
            first_decision = round_decisions[0]
            decision_cards_html += f"""
            <div class="round-section">
                <h3 class="round-header">
                    Round {round_num}
                    <span class="round-time">{first_decision['timestamp']}</span>
                    <span class="round-price">Price: ${first_decision['price']:.2f}</span>
                </h3>
                <div class="decisions-grid">
            """

            # Decision cards
            for decision in round_decisions:
                action_class = decision["action"].lower()
                executed_badge = "✓ Executed" if decision["executed"] else "✗ Not Executed"
                executed_class = "executed" if decision["executed"] else "not-executed"

                confidence_pct = decision["confidence"] * 100
                confidence_class = "high" if confidence_pct >= 80 else "medium" if confidence_pct >= 50 else "low"

                decision_cards_html += f"""
                <div class="decision-card {action_class}">
                    <div class="decision-header">
                        <span class="model-name">{decision['model']}</span>
                        <span class="execution-badge {executed_class}">{executed_badge}</span>
                    </div>
                    <div class="decision-action">
                        <span class="action-badge {action_class}">{decision['action']}</span>
                        <span class="confidence-badge {confidence_class}">
                            {confidence_pct:.0f}% Confidence
                        </span>
                    </div>
                    <div class="decision-reasoning">
                        <strong>Reasoning:</strong>
                        <p>{decision['reasoning']}</p>
                    </div>
                    <div class="decision-meta">
                        <span>Position Size: {decision['position_size']:.2%}</span>
                    </div>
                </div>
                """

            decision_cards_html += """
                </div>
            </div>
            """

        # Generate statistics
        total_decisions = len(decisions)
        buy_count = sum(1 for d in decisions if d["action"] == "BUY")
        sell_count = sum(1 for d in decisions if d["action"] == "SELL")
        hold_count = sum(1 for d in decisions if d["action"] == "HOLD")
        executed_count = sum(1 for d in decisions if d["executed"])
        avg_confidence = sum(d["confidence"] for d in decisions) / total_decisions if total_decisions > 0 else 0

        # Complete HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Decision Viewer - Session {session_id}</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header p {{
            opacity: 0.9;
            font-size: 1.1em;
        }}

        .stats-bar {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            padding: 20px 30px;
            background: #f8f9fa;
            border-bottom: 2px solid #e9ecef;
        }}

        .stat {{
            text-align: center;
            padding: 15px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .stat-value {{
            font-size: 1.8em;
            font-weight: bold;
            color: #667eea;
        }}

        .stat-label {{
            color: #6c757d;
            font-size: 0.9em;
            margin-top: 5px;
        }}

        .content {{
            padding: 30px;
        }}

        .round-section {{
            margin-bottom: 40px;
        }}

        .round-header {{
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 20px;
        }}

        .round-time {{
            font-size: 0.8em;
            opacity: 0.9;
        }}

        .round-price {{
            margin-left: auto;
            background: rgba(255,255,255,0.2);
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
        }}

        .decisions-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }}

        .decision-card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-left: 4px solid #ddd;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .decision-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 12px rgba(0,0,0,0.15);
        }}

        .decision-card.buy {{
            border-left-color: #27ae60;
        }}

        .decision-card.sell {{
            border-left-color: #e74c3c;
        }}

        .decision-card.hold {{
            border-left-color: #95a5a6;
        }}

        .decision-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}

        .model-name {{
            font-weight: bold;
            font-size: 1.2em;
            color: #2c3e50;
            text-transform: capitalize;
        }}

        .execution-badge {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: bold;
        }}

        .execution-badge.executed {{
            background: #d4edda;
            color: #155724;
        }}

        .execution-badge.not-executed {{
            background: #f8d7da;
            color: #721c24;
        }}

        .decision-action {{
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }}

        .action-badge {{
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 1.1em;
        }}

        .action-badge.buy {{
            background: #27ae60;
            color: white;
        }}

        .action-badge.sell {{
            background: #e74c3c;
            color: white;
        }}

        .action-badge.hold {{
            background: #95a5a6;
            color: white;
        }}

        .confidence-badge {{
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
        }}

        .confidence-badge.high {{
            background: #d4edda;
            color: #155724;
        }}

        .confidence-badge.medium {{
            background: #fff3cd;
            color: #856404;
        }}

        .confidence-badge.low {{
            background: #f8d7da;
            color: #721c24;
        }}

        .decision-reasoning {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            line-height: 1.6;
        }}

        .decision-reasoning strong {{
            display: block;
            margin-bottom: 8px;
            color: #495057;
        }}

        .decision-reasoning p {{
            color: #6c757d;
            font-size: 0.95em;
        }}

        .decision-meta {{
            color: #6c757d;
            font-size: 0.9em;
            padding-top: 10px;
            border-top: 1px solid #e9ecef;
        }}

        .filters {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}

        .filter-btn {{
            padding: 10px 20px;
            border: 2px solid #667eea;
            background: white;
            color: #667eea;
            border-radius: 20px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s;
        }}

        .filter-btn:hover {{
            background: #667eea;
            color: white;
        }}

        .filter-btn.active {{
            background: #667eea;
            color: white;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Decision Viewer</h1>
            <p>Session: {session_id}</p>
        </div>

        <div class="stats-bar">
            <div class="stat">
                <div class="stat-value">{total_decisions}</div>
                <div class="stat-label">Total Decisions</div>
            </div>
            <div class="stat">
                <div class="stat-value">{buy_count}</div>
                <div class="stat-label">BUY</div>
            </div>
            <div class="stat">
                <div class="stat-value">{sell_count}</div>
                <div class="stat-label">SELL</div>
            </div>
            <div class="stat">
                <div class="stat-value">{hold_count}</div>
                <div class="stat-label">HOLD</div>
            </div>
            <div class="stat">
                <div class="stat-value">{executed_count}</div>
                <div class="stat-label">Executed</div>
            </div>
            <div class="stat">
                <div class="stat-value">{avg_confidence*100:.0f}%</div>
                <div class="stat-label">Avg Confidence</div>
            </div>
        </div>

        <div class="content">
            {decision_cards_html}
        </div>
    </div>
</body>
</html>
"""

        return html

    def print_summary(self, session_id: str):
        """Print decision summary"""
        session = self.load_session(session_id)
        decisions = self.extract_decisions(session)

        self.console.print(f"\n[bold cyan]📊 Decision Summary - {session_id}[/bold cyan]\n")

        # Overall stats
        total = len(decisions)
        buy = sum(1 for d in decisions if d["action"] == "BUY")
        sell = sum(1 for d in decisions if d["action"] == "SELL")
        hold = sum(1 for d in decisions if d["action"] == "HOLD")
        executed = sum(1 for d in decisions if d["executed"])
        avg_conf = sum(d["confidence"] for d in decisions) / total if total > 0 else 0

        self.console.print(f"Total Decisions: {total}")
        self.console.print(f"  BUY: {buy} ({buy/total*100:.1f}%)")
        self.console.print(f"  SELL: {sell} ({sell/total*100:.1f}%)")
        self.console.print(f"  HOLD: {hold} ({hold/total*100:.1f}%)")
        self.console.print(f"Executed: {executed} ({executed/total*100:.1f}%)")
        self.console.print(f"Average Confidence: {avg_conf*100:.1f}%\n")

        # Per-model stats
        models = set(d["model"] for d in decisions)
        self.console.print("[bold]Per-Model Statistics:[/bold]")

        for model in sorted(models):
            model_decisions = [d for d in decisions if d["model"] == model]
            model_total = len(model_decisions)
            model_buy = sum(1 for d in model_decisions if d["action"] == "BUY")
            model_executed = sum(1 for d in model_decisions if d["executed"])
            model_avg_conf = sum(d["confidence"] for d in model_decisions) / model_total

            self.console.print(f"\n{model}:")
            self.console.print(f"  Decisions: {model_total}")
            self.console.print(f"  BUY: {model_buy} ({model_buy/model_total*100:.1f}%)")
            self.console.print(f"  Executed: {model_executed} ({model_executed/model_total*100:.1f}%)")
            self.console.print(f"  Avg Confidence: {model_avg_conf*100:.1f}%")


# ============================================================================
# CLI
# ============================================================================


@click.command()
@click.option(
    "--session",
    "-s",
    type=str,
    required=True,
    help="Session ID to view"
)
@click.option(
    "--summary",
    is_flag=True,
    help="Print summary instead of generating HTML"
)
@click.option(
    "--output",
    "-o",
    type=str,
    help="Output HTML file path"
)
def main(session, summary, output):
    """
    📋 Decision Logs Viewer

    Generate interactive HTML viewer for trading decisions.

    Examples:
        python visualization/decision_viewer.py --session 20251030_112514
        python visualization/decision_viewer.py -s 20251030_112514 --summary
        python visualization/decision_viewer.py -s 20251030_112514 -o my_decisions.html
    """
    console = Console()
    viewer = DecisionViewer()

    try:
        if summary:
            viewer.print_summary(session)
        else:
            output_path = viewer.generate_html_viewer(session, output)
            console.print(f"\n[green]📄 Open in browser: file://{output_path.absolute()}[/green]\n")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")


if __name__ == "__main__":
    main()
