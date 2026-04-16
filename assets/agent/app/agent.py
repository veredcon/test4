"""
Invoice Approval Monitor Agent — LangGraph-based agent definition.

Provides:
  - The LangChain/LangGraph agent used by the executor.
  - Background polling loop that refreshes the cached summary.
  - Flask sub-app for /summary and /health REST endpoints.
"""

import logging
import os
import sys
import threading
import time
from typing import Any

# Ensure the parent directory is on sys.path
_AGENT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

from flask import Flask, jsonify
from invoice_monitor import InvoiceMonitor
from summary_generator import SummaryGenerator
from extension_capabilities import register_extensions, get_capabilities

logger = logging.getLogger(__name__)

AGENT_NAME = "invoice-approval-monitor"
AGENT_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Shared state for the polling loop
# ---------------------------------------------------------------------------

_cached_summary: dict[str, Any] = {}
_cache_lock = threading.Lock()


# ---------------------------------------------------------------------------
# REST application for /summary and /health
# ---------------------------------------------------------------------------

rest_app = Flask(__name__)


@rest_app.route("/health")
def health() -> Any:
    return jsonify({"status": "ok", "agent": AGENT_NAME, "version": AGENT_VERSION})


@rest_app.route("/summary")
def get_summary() -> Any:
    """Return the latest cached weekly summary as JSON."""
    with _cache_lock:
        if not _cached_summary:
            # No cached result yet — generate on-demand
            caps = get_capabilities()
            monitor = InvoiceMonitor(
                data_source_url=os.environ.get("DATA_SOURCE_URL", ""),
                amount_threshold=caps["amount_threshold"],
                days_threshold=caps["days_threshold"],
            )
            generator = SummaryGenerator()
            flagged = monitor.get_flagged_invoices()
            summary = generator.generate(flagged)
            return jsonify(summary)
        return jsonify(dict(_cached_summary))


# ---------------------------------------------------------------------------
# Background polling loop
# ---------------------------------------------------------------------------

def _poll_loop() -> None:
    """Background thread: refresh flagged invoices every POLL_INTERVAL_HOURS."""
    interval_hours = float(os.environ.get("POLL_INTERVAL_HOURS", "6"))
    interval_seconds = interval_hours * 3600
    logger.info(
        "[%s] Starting polling loop (interval: %s hours).", AGENT_NAME, interval_hours
    )

    while True:
        try:
            caps = get_capabilities()
            monitor = InvoiceMonitor(
                data_source_url=os.environ.get("DATA_SOURCE_URL", ""),
                amount_threshold=caps["amount_threshold"],
                days_threshold=caps["days_threshold"],
            )
            generator = SummaryGenerator()
            flagged = monitor.get_flagged_invoices()
            summary = generator.generate(flagged)
            with _cache_lock:
                _cached_summary.clear()
                _cached_summary.update(summary)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Polling loop error: %s", exc)

        time.sleep(interval_seconds)


def start_polling_loop() -> None:
    """Start the background polling thread (daemon so it exits with the process)."""
    t = threading.Thread(target=_poll_loop, daemon=True, name="invoice-monitor-poll")
    t.start()
    logger.info("[%s] v%s — polling thread started.", AGENT_NAME, AGENT_VERSION)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def init_agent() -> None:
    """Call at application startup to register extensions and start polling."""
    register_extensions()
    logger.info("[%s] Extensions registered. Capabilities: %s", AGENT_NAME, get_capabilities())
    start_polling_loop()
