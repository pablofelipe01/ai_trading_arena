#!/usr/bin/env python3
"""
AI Trading Arena - Main Entry Point

Run LLM trading competitions from the command line.

Usage:
    # Run unlimited competition
    python main.py

    # Run for specific duration
    python main.py --duration 60

    # Run for specific number of rounds
    python main.py --rounds 10

    # Quick test (5 rounds)
    python main.py --test
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import click
from rich.console import Console

from core.arena_manager import ArenaManager
from utils.config import get_config
from utils.logger import get_logger


console = Console()
logger = get_logger("main")


@click.command()
@click.option(
    "--duration",
    "-d",
    type=int,
    help="Competition duration in minutes (default: unlimited)"
)
@click.option(
    "--rounds",
    "-r",
    type=int,
    help="Maximum number of trading rounds (default: unlimited)"
)
@click.option(
    "--test",
    is_flag=True,
    help="Quick test mode (5 rounds)"
)
def main(duration, rounds, test):
    """
    🤖 AI Trading Arena - Where LLMs Battle for Trading Supremacy

    Run competitions between DeepSeek, GPT-4, Claude, and Llama to see
    which AI has the best trading instincts.
    """

    # Test mode overrides
    if test:
        rounds = 5
        console.print("[yellow]🧪 Running in TEST mode (5 rounds)[/yellow]\n")

    # Display configuration
    config = get_config()

    console.print("\n[bold cyan]════════════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold yellow]   🤖  AI TRADING ARENA - LEVEL 1: MULTI-ASSET[/bold yellow]")
    console.print("[bold cyan]════════════════════════════════════════════════════════════════[/bold cyan]\n")

    assets_str = ', '.join([s.split('/')[0] for s in config.exchange.symbols])

    console.print("[bold]Configuration:[/bold]")
    console.print(f"  Mode: [cyan]{config.trading.mode}[/cyan]")
    console.print(f"  Level: [yellow]Level 1 - AI Trading Basics[/yellow]")
    console.print(f"  Assets: [cyan]{len(config.exchange.symbols)}[/cyan] [{assets_str}]")
    console.print(f"  Capital per model: [green]${config.trading.capital_per_model}[/green] (TOTAL)")
    console.print(f"  Decision interval: [cyan]{config.arena.decision_interval}s[/cyan]")

    if duration:
        console.print(f"  Duration: [yellow]{duration} minutes[/yellow]")
    if rounds:
        console.print(f"  Max rounds: [yellow]{rounds}[/yellow]")

    console.print(f"\n[bold]Models Enabled:[/bold]")

    # Show enabled models
    enabled_count = 0
    for provider in ["deepseek", "groq", "openai", "anthropic"]:
        model_config = getattr(config.models, provider, None)
        if model_config and model_config.enabled:
            enabled_count += 1
            console.print(f"  [green]✓[/green] {provider} (priority {model_config.priority})")

    if enabled_count == 0:
        console.print("[red]Error: No models enabled in config![/red]")
        sys.exit(1)

    console.print(f"\n[dim]Press Ctrl+C at any time to stop gracefully...[/dim]\n")

    # Run arena
    try:
        asyncio.run(run_competition(duration, rounds))

    except KeyboardInterrupt:
        console.print("\n[yellow]Competition interrupted by user[/yellow]")

    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        logger.error("Competition failed", error=str(e), exc_info=True)
        sys.exit(1)


async def run_competition(duration: int, rounds: int):
    """Run the competition"""
    arena = ArenaManager()

    # Initialize
    console.print("[cyan]Initializing arena components...[/cyan]")
    await arena.initialize()
    console.print(f"[green]✓ Arena initialized with {len(arena.symbols)} assets[/green]\n")

    # Run competition
    await arena.run_competition(
        duration_minutes=duration,
        max_rounds=rounds
    )


if __name__ == "__main__":
    main()
