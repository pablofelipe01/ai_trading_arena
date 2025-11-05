"""
Chart Builder for AI Trading Arena

Provides utilities for creating beautiful, interactive charts using Plotly.

Supports:
- Line charts (equity curves, price series)
- Bar charts (performance comparisons)
- Scatter plots (decision visualization)
- Candlestick charts (price action)
- Heatmaps (correlation matrices)
- Multi-subplot layouts
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
from datetime import datetime


# ============================================================================
# Color Schemes
# ============================================================================

COLORS = {
    "deepseek": "#4CAF50",    # Green
    "openai": "#00A67E",      # Teal
    "anthropic": "#CC785C",   # Coral
    "groq": "#F55036",        # Red-Orange
    "profit": "#27ae60",      # Green
    "loss": "#e74c3c",        # Red
    "neutral": "#95a5a6",     # Gray
    "background": "#ffffff",  # White
    "grid": "#ecf0f1"         # Light gray
}


# ============================================================================
# Chart Builder Class
# ============================================================================


class ChartBuilder:
    """Builds various types of charts for trading visualization"""

    def __init__(self, theme: str = "plotly_white"):
        """
        Initialize chart builder

        Args:
            theme: Plotly theme (plotly, plotly_white, plotly_dark, etc.)
        """
        self.theme = theme

    def create_equity_curve(
        self,
        equity_data: Dict[str, List[Dict[str, Any]]],
        title: str = "Equity Curves",
        show_drawdown: bool = True
    ) -> go.Figure:
        """
        Create equity curve chart

        Args:
            equity_data: Dict mapping model names to equity history
                        [{timestamp, value, round}, ...]
            title: Chart title
            show_drawdown: Show drawdown subplot

        Returns:
            Plotly Figure
        """
        if show_drawdown:
            fig = make_subplots(
                rows=2, cols=1,
                row_heights=[0.7, 0.3],
                subplot_titles=(title, "Drawdown %"),
                shared_xaxes=True,
                vertical_spacing=0.1
            )
        else:
            fig = go.Figure()

        # Add equity curves
        for model_name, equity in equity_data.items():
            if not equity:
                continue

            timestamps = [e["timestamp"] for e in equity]
            values = [e["value"] for e in equity]

            color = COLORS.get(model_name.lower(), COLORS["neutral"])

            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=values,
                    name=model_name,
                    mode="lines",
                    line=dict(color=color, width=2),
                    hovertemplate=f"{model_name}<br>Value: $%{{y:.2f}}<br>%{{x}}<extra></extra>"
                ),
                row=1, col=1
            )

            # Calculate and plot drawdown
            if show_drawdown:
                peak = values[0]
                drawdowns = []
                for value in values:
                    if value > peak:
                        peak = value
                    dd = (value - peak) / peak * 100 if peak > 0 else 0
                    drawdowns.append(dd)

                fig.add_trace(
                    go.Scatter(
                        x=timestamps,
                        y=drawdowns,
                        name=f"{model_name} DD",
                        mode="lines",
                        line=dict(color=color, width=1, dash="dot"),
                        fill="tozeroy",
                        fillcolor=f"rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.1)",
                        showlegend=False,
                        hovertemplate=f"{model_name} DD<br>%{{y:.2f}}%<br>%{{x}}<extra></extra>"
                    ),
                    row=2, col=1
                )

        # Update layout
        fig.update_layout(
            template=self.theme,
            hovermode="x unified",
            height=600 if show_drawdown else 400,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        fig.update_xaxes(title_text="Time", row=2 if show_drawdown else 1, col=1)
        fig.update_yaxes(title_text="Account Value ($)", row=1, col=1)
        if show_drawdown:
            fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)

        return fig

    def create_performance_comparison(
        self,
        models: List[Dict[str, Any]],
        metric: str = "return_pct",
        title: str = "Model Performance"
    ) -> go.Figure:
        """
        Create performance comparison bar chart

        Args:
            models: List of model data dicts
            metric: Metric to compare (return_pct, win_rate, etc.)
            title: Chart title

        Returns:
            Plotly Figure
        """
        fig = go.Figure()

        model_names = [m["provider"] for m in models]
        values = [m.get(metric, 0) for m in models]
        colors = [COLORS.get(name.lower(), COLORS["neutral"]) for name in model_names]

        # Color bars based on positive/negative
        if metric == "return_pct":
            colors = [COLORS["profit"] if v >= 0 else COLORS["loss"] for v in values]

        fig.add_trace(
            go.Bar(
                x=model_names,
                y=values,
                marker_color=colors,
                text=[f"{v:.2f}" for v in values],
                textposition="outside",
                hovertemplate="%{x}<br>%{y:.2f}<extra></extra>"
            )
        )

        fig.update_layout(
            title=title,
            xaxis_title="Model",
            yaxis_title=metric.replace("_", " ").title(),
            template=self.theme,
            showlegend=False
        )

        return fig

    def create_decision_scatter(
        self,
        decisions: List[Dict[str, Any]],
        title: str = "Decision Visualization"
    ) -> go.Figure:
        """
        Create scatter plot of decisions (confidence vs. outcome)

        Args:
            decisions: List of decision dicts
                      [{model, action, confidence, outcome, timestamp}, ...]
            title: Chart title

        Returns:
            Plotly Figure
        """
        fig = go.Figure()

        # Group by action
        actions = {"BUY": [], "SELL": [], "HOLD": []}

        for decision in decisions:
            action = decision.get("action", "HOLD")
            if action in actions:
                actions[action].append(decision)

        action_colors = {
            "BUY": "#27ae60",
            "SELL": "#e74c3c",
            "HOLD": "#95a5a6"
        }

        for action, decisions_list in actions.items():
            if not decisions_list:
                continue

            confidences = [d.get("confidence", 0.5) for d in decisions_list]
            outcomes = [d.get("outcome", 0) for d in decisions_list]
            models = [d.get("model", "Unknown") for d in decisions_list]

            fig.add_trace(
                go.Scatter(
                    x=confidences,
                    y=outcomes,
                    mode="markers",
                    name=action,
                    marker=dict(
                        color=action_colors[action],
                        size=10,
                        line=dict(width=1, color="white")
                    ),
                    text=models,
                    hovertemplate="%{text}<br>Confidence: %{x:.2f}<br>Outcome: %{y:.2f}%<extra></extra>"
                )
            )

        fig.update_layout(
            title=title,
            xaxis_title="Confidence",
            yaxis_title="Outcome (%)",
            template=self.theme,
            hovermode="closest"
        )

        return fig

    def create_trade_timeline(
        self,
        trades: List[Dict[str, Any]],
        title: str = "Trade Timeline"
    ) -> go.Figure:
        """
        Create trade timeline visualization

        Args:
            trades: List of trade dicts
                   [{timestamp, action, price, size, model, pnl}, ...]
            title: Chart title

        Returns:
            Plotly Figure
        """
        fig = go.Figure()

        # Separate by action
        buys = [t for t in trades if t.get("action") == "BUY"]
        sells = [t for t in trades if t.get("action") == "SELL"]

        # Plot buys
        if buys:
            fig.add_trace(
                go.Scatter(
                    x=[t["timestamp"] for t in buys],
                    y=[t["price"] for t in buys],
                    mode="markers",
                    name="BUY",
                    marker=dict(
                        symbol="triangle-up",
                        size=12,
                        color=COLORS["profit"],
                        line=dict(width=2, color="white")
                    ),
                    text=[f"{t['model']}: {t.get('pnl', 0):.2f}" for t in buys],
                    hovertemplate="BUY<br>%{text}<br>Price: $%{y:.2f}<br>%{x}<extra></extra>"
                )
            )

        # Plot sells
        if sells:
            fig.add_trace(
                go.Scatter(
                    x=[t["timestamp"] for t in sells],
                    y=[t["price"] for t in sells],
                    mode="markers",
                    name="SELL",
                    marker=dict(
                        symbol="triangle-down",
                        size=12,
                        color=COLORS["loss"],
                        line=dict(width=2, color="white")
                    ),
                    text=[f"{t['model']}: {t.get('pnl', 0):.2f}" for t in sells],
                    hovertemplate="SELL<br>%{text}<br>Price: $%{y:.2f}<br>%{x}<extra></extra>"
                )
            )

        fig.update_layout(
            title=title,
            xaxis_title="Time",
            yaxis_title="Price ($)",
            template=self.theme,
            hovermode="closest"
        )

        return fig

    def create_candlestick_chart(
        self,
        candles: List[Dict[str, Any]],
        title: str = "Price Chart",
        show_volume: bool = True
    ) -> go.Figure:
        """
        Create candlestick chart with optional volume

        Args:
            candles: List of candle dicts
                    [{timestamp, open, high, low, close, volume}, ...]
            title: Chart title
            show_volume: Show volume subplot

        Returns:
            Plotly Figure
        """
        if show_volume:
            fig = make_subplots(
                rows=2, cols=1,
                row_heights=[0.7, 0.3],
                subplot_titles=(title, "Volume"),
                shared_xaxes=True,
                vertical_spacing=0.05
            )
        else:
            fig = go.Figure()

        # Add candlestick
        fig.add_trace(
            go.Candlestick(
                x=[c["timestamp"] for c in candles],
                open=[c["open"] for c in candles],
                high=[c["high"] for c in candles],
                low=[c["low"] for c in candles],
                close=[c["close"] for c in candles],
                name="Price",
                increasing_line_color=COLORS["profit"],
                decreasing_line_color=COLORS["loss"]
            ),
            row=1, col=1
        )

        # Add volume
        if show_volume:
            colors = [
                COLORS["profit"] if candles[i]["close"] >= candles[i]["open"] else COLORS["loss"]
                for i in range(len(candles))
            ]

            fig.add_trace(
                go.Bar(
                    x=[c["timestamp"] for c in candles],
                    y=[c["volume"] for c in candles],
                    name="Volume",
                    marker_color=colors,
                    showlegend=False
                ),
                row=2, col=1
            )

        fig.update_layout(
            template=self.theme,
            xaxis_rangeslider_visible=False,
            height=600 if show_volume else 400
        )

        fig.update_xaxes(title_text="Time", row=2 if show_volume else 1, col=1)
        fig.update_yaxes(title_text="Price ($)", row=1, col=1)
        if show_volume:
            fig.update_yaxes(title_text="Volume", row=2, col=1)

        return fig

    def create_metrics_heatmap(
        self,
        data: pd.DataFrame,
        title: str = "Performance Heatmap"
    ) -> go.Figure:
        """
        Create heatmap of metrics across models

        Args:
            data: DataFrame with models as rows and metrics as columns
            title: Chart title

        Returns:
            Plotly Figure
        """
        fig = go.Figure(
            data=go.Heatmap(
                z=data.values,
                x=data.columns,
                y=data.index,
                colorscale="RdYlGn",
                text=data.values,
                texttemplate="%{text:.2f}",
                textfont={"size": 10},
                hovertemplate="Model: %{y}<br>Metric: %{x}<br>Value: %{z:.2f}<extra></extra>"
            )
        )

        fig.update_layout(
            title=title,
            xaxis_title="Metrics",
            yaxis_title="Models",
            template=self.theme
        )

        return fig

    def create_multi_metric_chart(
        self,
        models: List[Dict[str, Any]],
        metrics: List[str],
        title: str = "Multi-Metric Comparison"
    ) -> go.Figure:
        """
        Create radar/spider chart for multi-metric comparison

        Args:
            models: List of model data dicts
            metrics: List of metric names to compare
            title: Chart title

        Returns:
            Plotly Figure
        """
        fig = go.Figure()

        for model in models:
            values = [model.get(metric, 0) for metric in metrics]
            # Close the loop
            values.append(values[0])
            metrics_loop = metrics + [metrics[0]]

            color = COLORS.get(model["provider"].lower(), COLORS["neutral"])

            fig.add_trace(
                go.Scatterpolar(
                    r=values,
                    theta=metrics_loop,
                    fill="toself",
                    name=model["provider"],
                    line=dict(color=color, width=2)
                )
            )

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100]
                )
            ),
            showlegend=True,
            title=title,
            template=self.theme
        )

        return fig


# ============================================================================
# Helper Functions
# ============================================================================


def save_chart(fig: go.Figure, filepath: str, format: str = "html"):
    """
    Save chart to file

    Args:
        fig: Plotly Figure
        filepath: Output file path
        format: Output format (html, png, jpg, svg)
    """
    if format == "html":
        fig.write_html(filepath)
    elif format in ["png", "jpg", "jpeg", "svg"]:
        fig.write_image(filepath)
    else:
        raise ValueError(f"Unsupported format: {format}")


def combine_charts(
    charts: List[go.Figure],
    layout: Tuple[int, int],
    title: str = "Combined Charts"
) -> go.Figure:
    """
    Combine multiple charts into subplots

    Args:
        charts: List of Plotly Figures
        layout: (rows, cols) layout
        title: Overall title

    Returns:
        Combined Plotly Figure
    """
    rows, cols = layout
    fig = make_subplots(rows=rows, cols=cols)

    for i, chart in enumerate(charts):
        row = i // cols + 1
        col = i % cols + 1

        for trace in chart.data:
            fig.add_trace(trace, row=row, col=col)

    fig.update_layout(title=title)
    return fig
