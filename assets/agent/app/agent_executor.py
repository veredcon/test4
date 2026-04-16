"""
Agent Executor — processes A2A task requests for the Invoice Approval Monitor Agent.
"""

import logging
import os
import sys

# Ensure the parent directory (assets/agent/) is on sys.path so sibling modules
# like invoice_monitor and summary_generator can be imported.
_AGENT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import InternalError
from a2a.utils.errors import ServerError

from invoice_monitor import InvoiceMonitor
from summary_generator import SummaryGenerator

logger = logging.getLogger(__name__)


class InvoiceApprovalAgentExecutor(AgentExecutor):
    """
    Handles incoming A2A task requests:
      - Fetches and flags overdue invoices.
      - Generates the weekly summary.
      - Returns the result as a text response.
    """

    def __init__(self) -> None:
        self._monitor = InvoiceMonitor(
            data_source_url=os.environ.get("DATA_SOURCE_URL", ""),
        )
        self._generator = SummaryGenerator()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        try:
            flagged = self._monitor.get_flagged_invoices()
            summary = self._generator.generate(flagged)

            # Format a human-readable response
            lines = [
                f"**Weekly Invoice Approval Summary** — Week ending {summary['week_ending']}",
                f"Generated at: {summary['generated_at']}",
                f"Total flagged invoices (>50K, >3 days pending): **{summary['total_flagged']}**",
                "",
            ]
            if summary["invoices"]:
                lines.append("| Invoice ID | Vendor | Amount | Currency | Days Pending |")
                lines.append("|-----------|--------|--------|----------|-------------|")
                for inv in summary["invoices"]:
                    lines.append(
                        f"| {inv['invoice_id']} | {inv['vendor']} "
                        f"| {inv['amount']:,.2f} | {inv['currency']} "
                        f"| {inv['days_pending']} |"
                    )
            else:
                lines.append("No invoices flagged this week.")

            response_text = "\n".join(lines)
            await event_queue.enqueue_event(
                context.get_task_complete_event(response_text)
            )

        except Exception as exc:
            logger.exception("Invoice Approval Agent execution error")
            raise ServerError(error=InternalError()) from exc

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=InternalError(message="Cancellation not supported."))
