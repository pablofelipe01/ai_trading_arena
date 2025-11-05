"""
Comprehensive Test Report Generator for AI Trading Arena

Runs all test suites and generates detailed reports:
- Test coverage summary
- Performance benchmarks
- Chaos testing results
- Stress testing results
- System health assessment
- Recommendations

Usage:
    python tests/generate_test_report.py
    python tests/generate_test_report.py --html
    python tests/generate_test_report.py --quick
"""

import subprocess
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn


# ============================================================================
# Test Runner
# ============================================================================


class TestReportGenerator:
    """Generates comprehensive test reports"""

    def __init__(self, output_dir: str = "data/test_reports"):
        """Initialize report generator"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.console = Console()
        self.report_data = {
            "report_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "timestamp": datetime.now().isoformat(),
            "test_suites": {},
            "summary": {},
            "recommendations": []
        }

    def run_test_suite(self, suite_name: str, test_file: str, description: str) -> Dict[str, Any]:
        """Run a test suite and collect results"""
        self.console.print(f"\n[cyan]Running {suite_name}...[/cyan]")

        start_time = time.time()

        # Run pytest
        result = subprocess.run(
            ["pytest", test_file, "-v", "--tb=short", "-q"],
            capture_output=True,
            text=True
        )

        elapsed = time.time() - start_time

        # Parse results
        output = result.stdout + result.stderr

        # Extract test counts (simple parsing)
        passed = output.count(" PASSED")
        failed = output.count(" FAILED")
        errors = output.count(" ERROR")
        skipped = output.count(" SKIPPED")

        suite_result = {
            "name": suite_name,
            "description": description,
            "test_file": test_file,
            "duration_seconds": elapsed,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "total": passed + failed + errors + skipped,
            "success_rate": (passed / (passed + failed + errors) * 100) if (passed + failed + errors) > 0 else 0,
            "output": output
        }

        # Display results
        status = "✅" if failed == 0 and errors == 0 else "❌"
        self.console.print(
            f"{status} {suite_name}: {passed} passed, {failed} failed, "
            f"{errors} errors in {elapsed:.1f}s"
        )

        return suite_result

    def run_all_tests(self, quick: bool = False):
        """Run all test suites"""
        self.console.print("\n" + "="*80)
        self.console.print("[bold cyan]🧪 RUNNING COMPREHENSIVE TEST SUITE[/bold cyan]")
        self.console.print("="*80)

        test_suites = [
            {
                "name": "Chaos Testing",
                "file": "tests/test_chaos.py",
                "description": "Tests system resilience under adverse conditions",
                "skip_quick": False
            },
            {
                "name": "Performance Benchmarks",
                "file": "tests/test_performance.py",
                "description": "Benchmarks system performance metrics",
                "skip_quick": False
            },
            {
                "name": "Stress Testing",
                "file": "tests/test_stress.py",
                "description": "Tests system under extreme load",
                "skip_quick": True  # Skip in quick mode (resource intensive)
            }
        ]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("Running tests...", total=len(test_suites))

            for suite in test_suites:
                if quick and suite.get("skip_quick", False):
                    self.console.print(f"[yellow]⏭️  Skipping {suite['name']} (quick mode)[/yellow]")
                    progress.advance(task)
                    continue

                result = self.run_test_suite(
                    suite["name"],
                    suite["file"],
                    suite["description"]
                )
                self.report_data["test_suites"][suite["name"]] = result
                progress.advance(task)

        self.console.print("\n" + "="*80)
        self.console.print("[bold green]✅ ALL TEST SUITES COMPLETE[/bold green]")
        self.console.print("="*80)

    def generate_summary(self):
        """Generate test summary"""
        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_errors = 0
        total_duration = 0

        for suite in self.report_data["test_suites"].values():
            total_tests += suite["total"]
            total_passed += suite["passed"]
            total_failed += suite["failed"]
            total_errors += suite["errors"]
            total_duration += suite["duration_seconds"]

        overall_success = (total_passed / total_tests * 100) if total_tests > 0 else 0

        self.report_data["summary"] = {
            "total_test_suites": len(self.report_data["test_suites"]),
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_errors": total_errors,
            "overall_success_rate": overall_success,
            "total_duration_seconds": total_duration,
            "total_duration_minutes": total_duration / 60
        }

    def generate_recommendations(self):
        """Generate recommendations based on test results"""
        recommendations = []

        summary = self.report_data["summary"]

        # Overall health
        if summary["overall_success_rate"] >= 95:
            recommendations.append({
                "type": "success",
                "message": "System is highly robust with excellent test coverage"
            })
        elif summary["overall_success_rate"] >= 80:
            recommendations.append({
                "type": "warning",
                "message": "System is generally stable but has some issues to address"
            })
        else:
            recommendations.append({
                "type": "critical",
                "message": "System has significant issues that need immediate attention"
            })

        # Check individual suites
        for suite_name, suite in self.report_data["test_suites"].items():
            if suite["failed"] > 0 or suite["errors"] > 0:
                recommendations.append({
                    "type": "warning",
                    "message": f"{suite_name} has {suite['failed']} failures and {suite['errors']} errors"
                })

            if suite["success_rate"] < 80:
                recommendations.append({
                    "type": "critical",
                    "message": f"{suite_name} has low success rate ({suite['success_rate']:.1f}%)"
                })

        # Performance recommendations
        if "Performance Benchmarks" in self.report_data["test_suites"]:
            perf = self.report_data["test_suites"]["Performance Benchmarks"]
            if perf["duration_seconds"] > 60:
                recommendations.append({
                    "type": "info",
                    "message": "Performance tests took >60s, consider optimizing critical paths"
                })

        # Stress test recommendations
        if "Stress Testing" in self.report_data["test_suites"]:
            stress = self.report_data["test_suites"]["Stress Testing"]
            if stress["failed"] > 0:
                recommendations.append({
                    "type": "warning",
                    "message": "System shows weaknesses under extreme load, review stress test failures"
                })

        self.report_data["recommendations"] = recommendations

    def display_report(self):
        """Display report in terminal"""
        self.console.print("\n" + "="*80)
        self.console.print("[bold cyan]📊 COMPREHENSIVE TEST REPORT[/bold cyan]")
        self.console.print("="*80)

        # Summary Panel
        summary = self.report_data["summary"]
        self.console.print(Panel(
            f"Test Suites: {summary['total_test_suites']}\n"
            f"Total Tests: {summary['total_tests']}\n"
            f"Passed: [green]{summary['total_passed']}[/green]\n"
            f"Failed: [red]{summary['total_failed']}[/red]\n"
            f"Errors: [red]{summary['total_errors']}[/red]\n"
            f"Success Rate: [bold]{summary['overall_success_rate']:.1f}%[/bold]\n"
            f"Duration: {summary['total_duration_minutes']:.2f} minutes",
            title="Summary",
            border_style="cyan"
        ))

        # Test Suites Table
        table = Table(title="Test Suite Results")
        table.add_column("Suite", style="cyan")
        table.add_column("Tests", style="yellow")
        table.add_column("Passed", style="green")
        table.add_column("Failed", style="red")
        table.add_column("Success %", style="blue")
        table.add_column("Duration", style="magenta")

        for suite in self.report_data["test_suites"].values():
            status = "✅" if suite["failed"] == 0 and suite["errors"] == 0 else "❌"
            table.add_row(
                f"{status} {suite['name']}",
                str(suite["total"]),
                str(suite["passed"]),
                str(suite["failed"] + suite["errors"]),
                f"{suite['success_rate']:.1f}%",
                f"{suite['duration_seconds']:.1f}s"
            )

        self.console.print(table)

        # Recommendations
        if self.report_data["recommendations"]:
            self.console.print("\n[bold yellow]📋 Recommendations:[/bold yellow]")
            for rec in self.report_data["recommendations"]:
                icon = {
                    "success": "✅",
                    "info": "ℹ️",
                    "warning": "⚠️",
                    "critical": "🔴"
                }.get(rec["type"], "•")

                color = {
                    "success": "green",
                    "info": "cyan",
                    "warning": "yellow",
                    "critical": "red"
                }.get(rec["type"], "white")

                self.console.print(f"  {icon} [{color}]{rec['message']}[/{color}]")

        self.console.print("\n" + "="*80)

    def export_json(self) -> Path:
        """Export report as JSON"""
        report_file = self.output_dir / f"test_report_{self.report_data['report_id']}.json"

        with open(report_file, "w") as f:
            json.dump(self.report_data, f, indent=2)

        self.console.print(f"\n[green]✅ JSON report exported: {report_file}[/green]")
        return report_file

    def export_html(self) -> Path:
        """Export report as HTML"""
        report_file = self.output_dir / f"test_report_{self.report_data['report_id']}.html"

        html = self._generate_html()

        with open(report_file, "w") as f:
            f.write(html)

        self.console.print(f"[green]✅ HTML report exported: {report_file}[/green]")
        return report_file

    def _generate_html(self) -> str:
        """Generate HTML report"""
        summary = self.report_data["summary"]

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>AI Trading Arena - Test Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        .summary {{
            background-color: #ecf0f1;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .summary-item {{
            display: inline-block;
            margin: 10px 20px 10px 0;
        }}
        .summary-label {{
            font-weight: bold;
            color: #7f8c8d;
        }}
        .summary-value {{
            font-size: 1.2em;
            color: #2c3e50;
        }}
        .success {{ color: #27ae60; }}
        .failure {{ color: #e74c3c; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th {{
            background-color: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ecf0f1;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .recommendations {{
            margin: 20px 0;
        }}
        .recommendation {{
            padding: 10px;
            margin: 5px 0;
            border-radius: 4px;
        }}
        .rec-success {{ background-color: #d4edda; border-left: 4px solid #28a745; }}
        .rec-info {{ background-color: #d1ecf1; border-left: 4px solid #17a2b8; }}
        .rec-warning {{ background-color: #fff3cd; border-left: 4px solid #ffc107; }}
        .rec-critical {{ background-color: #f8d7da; border-left: 4px solid #dc3545; }}
        .timestamp {{
            color: #7f8c8d;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 AI Trading Arena - Comprehensive Test Report</h1>
        <p class="timestamp">Generated: {self.report_data['timestamp']}</p>

        <div class="summary">
            <h2>Summary</h2>
            <div class="summary-item">
                <span class="summary-label">Test Suites:</span>
                <span class="summary-value">{summary['total_test_suites']}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Total Tests:</span>
                <span class="summary-value">{summary['total_tests']}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Passed:</span>
                <span class="summary-value success">{summary['total_passed']}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Failed:</span>
                <span class="summary-value failure">{summary['total_failed']}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Errors:</span>
                <span class="summary-value failure">{summary['total_errors']}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Success Rate:</span>
                <span class="summary-value {'success' if summary['overall_success_rate'] >= 95 else 'failure'}">
                    {summary['overall_success_rate']:.1f}%
                </span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Duration:</span>
                <span class="summary-value">{summary['total_duration_minutes']:.2f} min</span>
            </div>
        </div>

        <h2>Test Suite Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Suite</th>
                    <th>Description</th>
                    <th>Tests</th>
                    <th>Passed</th>
                    <th>Failed</th>
                    <th>Success Rate</th>
                    <th>Duration</th>
                </tr>
            </thead>
            <tbody>
"""

        for suite in self.report_data["test_suites"].values():
            status = "✅" if suite["failed"] == 0 and suite["errors"] == 0 else "❌"
            html += f"""
                <tr>
                    <td>{status} {suite['name']}</td>
                    <td>{suite['description']}</td>
                    <td>{suite['total']}</td>
                    <td class="success">{suite['passed']}</td>
                    <td class="failure">{suite['failed'] + suite['errors']}</td>
                    <td>{suite['success_rate']:.1f}%</td>
                    <td>{suite['duration_seconds']:.1f}s</td>
                </tr>
"""

        html += """
            </tbody>
        </table>

        <div class="recommendations">
            <h2>Recommendations</h2>
"""

        for rec in self.report_data["recommendations"]:
            rec_class = f"rec-{rec['type']}"
            html += f'            <div class="recommendation {rec_class}">{rec["message"]}</div>\n'

        html += """
        </div>

        <footer>
            <p class="timestamp">AI Trading Arena - Automated Test Report</p>
        </footer>
    </div>
</body>
</html>
"""

        return html


# ============================================================================
# CLI
# ============================================================================


@click.command()
@click.option(
    "--html",
    is_flag=True,
    help="Generate HTML report"
)
@click.option(
    "--quick",
    is_flag=True,
    help="Quick mode (skip resource-intensive tests)"
)
@click.option(
    "--output-dir",
    "-o",
    type=str,
    default="data/test_reports",
    help="Output directory for reports"
)
def main(html, quick, output_dir):
    """
    🧪 Comprehensive Test Report Generator

    Runs all test suites and generates detailed reports.

    Examples:
        python tests/generate_test_report.py
        python tests/generate_test_report.py --html
        python tests/generate_test_report.py --quick
    """
    console = Console()

    console.print("\n[bold cyan]🚀 Starting Comprehensive Test Suite[/bold cyan]\n")

    # Create generator
    generator = TestReportGenerator(output_dir)

    # Run all tests
    generator.run_all_tests(quick=quick)

    # Generate analysis
    console.print("\n[cyan]Generating analysis...[/cyan]")
    generator.generate_summary()
    generator.generate_recommendations()

    # Display report
    generator.display_report()

    # Export reports
    console.print("\n[cyan]Exporting reports...[/cyan]")
    json_file = generator.export_json()

    if html:
        html_file = generator.export_html()
        console.print(f"\n[green]📄 Open in browser: file://{html_file.absolute()}[/green]")

    console.print("\n[bold green]✅ Test report generation complete![/bold green]\n")


if __name__ == "__main__":
    main()
