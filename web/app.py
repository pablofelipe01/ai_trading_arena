"""
Real-time Web Dashboard for AI Trading Arena

FastAPI server with WebSocket for live competition updates.

Usage:
    python web/app.py

Then open: http://localhost:8000
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Set
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from core.arena_manager import ArenaManager


# ============================================================================
# WebSocket Connection Manager
# ============================================================================


class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Accept new connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"✓ Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove connection"""
        self.active_connections.discard(websocket)
        print(f"✗ Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return

        message_json = json.dumps(message)

        # Send to all connections, remove dead ones
        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                dead_connections.add(connection)

        # Clean up dead connections
        for connection in dead_connections:
            self.disconnect(connection)


# ============================================================================
# FastAPI Application
# ============================================================================


app = FastAPI(title="AI Trading Arena - Live Dashboard")
manager = ConnectionManager()

# Global state
arena: ArenaManager = None
arena_task: asyncio.Task = None
competition_state = {
    "running": False,
    "paused": False,
    "round": 0,
    "session_id": None,
    "symbol": "BTC/USDT"
}


# ============================================================================
# WebSocket Endpoint
# ============================================================================


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)

    try:
        # Send initial state
        await websocket.send_json({
            "type": "state",
            "data": competition_state
        })

        # Keep connection alive
        while True:
            # Wait for client messages (ping/pong)
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============================================================================
# API Endpoints
# ============================================================================


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the dashboard HTML"""
    html_file = Path(__file__).parent / "static" / "index.html"

    if not html_file.exists():
        return HTMLResponse(
            content="<h1>Dashboard not found</h1><p>Run setup to create static files</p>",
            status_code=404
        )

    return FileResponse(html_file)


@app.get("/api/status")
async def get_status():
    """Get current competition status"""
    return competition_state


@app.post("/api/start")
async def start_competition(config: Dict[str, Any] = None):
    """Start a new competition"""
    global arena, arena_task, competition_state

    if competition_state["running"]:
        return {"error": "Competition already running"}

    # Create new arena
    arena = ArenaManager(symbol=config.get("symbol", "BTC/USDT") if config else "BTC/USDT")

    # Initialize
    await arena.initialize()

    # Start competition in background
    arena_task = asyncio.create_task(run_competition_with_events(
        duration_minutes=config.get("duration") if config else None,
        max_rounds=config.get("rounds") if config else None
    ))

    competition_state["running"] = True
    competition_state["session_id"] = arena.session_id
    competition_state["symbol"] = arena.symbol

    await manager.broadcast({
        "type": "competition_started",
        "data": competition_state
    })

    return {"status": "started", "session_id": arena.session_id}


@app.post("/api/stop")
async def stop_competition():
    """Stop the competition"""
    global arena, arena_task, competition_state

    if not competition_state["running"]:
        return {"error": "No competition running"}

    if arena:
        arena.shutdown_requested = True

    if arena_task:
        arena_task.cancel()

    competition_state["running"] = False
    competition_state["paused"] = False

    await manager.broadcast({
        "type": "competition_stopped",
        "data": competition_state
    })

    return {"status": "stopped"}


@app.post("/api/pause")
async def pause_competition():
    """Pause the competition"""
    global competition_state

    if not competition_state["running"]:
        return {"error": "No competition running"}

    competition_state["paused"] = not competition_state["paused"]

    await manager.broadcast({
        "type": "competition_paused" if competition_state["paused"] else "competition_resumed",
        "data": competition_state
    })

    return {"status": "paused" if competition_state["paused"] else "resumed"}


# ============================================================================
# Competition Runner with Events
# ============================================================================


async def run_competition_with_events(duration_minutes: int = None, max_rounds: int = None):
    """Run competition and broadcast events"""
    global arena, competition_state

    try:
        round_num = 0

        while not arena.shutdown_requested:
            # Check max rounds
            if max_rounds and round_num >= max_rounds:
                break

            # Check pause
            while competition_state["paused"]:
                await asyncio.sleep(1)

            round_num += 1
            competition_state["round"] = round_num

            # Broadcast round start
            await manager.broadcast({
                "type": "round_start",
                "data": {
                    "round": round_num,
                    "timestamp": datetime.now().isoformat()
                }
            })

            # Run trading round
            try:
                await arena._run_trading_round()

                # Get current state
                leaderboard = arena.get_leaderboard()

                # Broadcast round complete
                await manager.broadcast({
                    "type": "round_complete",
                    "data": {
                        "round": round_num,
                        "leaderboard": leaderboard,
                        "timestamp": datetime.now().isoformat()
                    }
                })

            except Exception as e:
                await manager.broadcast({
                    "type": "error",
                    "data": {
                        "round": round_num,
                        "error": str(e)
                    }
                })

            # Wait for next round
            await asyncio.sleep(arena.config.arena.decision_interval)

    except asyncio.CancelledError:
        pass

    finally:
        # Cleanup
        if arena:
            await arena.cleanup()

        competition_state["running"] = False

        await manager.broadcast({
            "type": "competition_finished",
            "data": {
                "total_rounds": round_num,
                "session_id": arena.session_id
            }
        })


# ============================================================================
# Startup
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    print("\n" + "="*70)
    print("🚀 AI Trading Arena - Live Dashboard")
    print("="*70)
    print("\n📊 Dashboard: http://localhost:8000")
    print("🔌 WebSocket: ws://localhost:8000/ws")
    print("\n" + "="*70 + "\n")


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """Run the web server"""
    uvicorn.run(
        "web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
