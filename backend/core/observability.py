"""
NEXUS — Observability / Logging
Structured JSON logs with timing. WebSocket broadcast for live agent trace.
"""
import time
import structlog
from datetime import datetime
from typing import Any, Dict, Optional, Set
from fastapi import WebSocket

logger = structlog.get_logger()

# Active WebSocket connections keyed by analysis_id
_ws_connections: Dict[str, Set[WebSocket]] = {}


def configure_logging():
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

class LayerTrace:
    """Context manager that times a pipeline layer and broadcasts to WS clients."""

    def __init__(self, analysis_id: str, layer: str, meta: Optional[Dict] = None):
        self.analysis_id = analysis_id
        self.layer = layer
        self.meta = meta or {}
        self._start: float = 0.0

    async def __aenter__(self):
        self._start = time.time()
        await broadcast(self.analysis_id, {
            "type": "layer_start",
            "layer": self.layer,
            "timestamp": datetime.utcnow().isoformat(),
            **self.meta,
        })
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self._start) * 1000)
        status = "error" if exc_type else "success"
        await broadcast(self.analysis_id, {
            "type": "layer_end",
            "layer": self.layer,
            "status": status,
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow().isoformat(),
            **self.meta,
        })
        log = logger.bind(layer=self.layer, analysis_id=self.analysis_id, duration_ms=duration_ms)
        if exc_type:
            log.error("layer_failed", error=str(exc_val))
        else:
            log.info("layer_complete")


async def broadcast(analysis_id: str, payload: Dict[str, Any]):
    """Send a trace event to all WebSocket clients watching this analysis."""
    connections = _ws_connections.get(analysis_id, set())
    dead = set()
    for ws in connections:
        try:
            import json
            await ws.send_text(json.dumps(payload))
        except Exception:
            dead.add(ws)
    _ws_connections[analysis_id] = connections - dead


def register_ws(analysis_id: str, ws: WebSocket):
    _ws_connections.setdefault(analysis_id, set()).add(ws)


def unregister_ws(analysis_id: str, ws: WebSocket):
    if analysis_id in _ws_connections:
        _ws_connections[analysis_id].discard(ws)