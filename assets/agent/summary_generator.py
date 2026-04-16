"""
Summary Generator — Compiles the weekly invoice approval summary.

Milestone:
  M3 — Summary Generation
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any

from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("invoice-approval-monitor")


def _next_sunday(ref: date) -> date:
    """Return the date of the Sunday that ends the current week (Mon–Sun)."""
    days_ahead = 6 - ref.weekday()  # weekday(): Mon=0 … Sun=6
    if days_ahead < 0:
        days_ahead += 7
    return ref + timedelta(days=days_ahead)


class SummaryGenerator:
    """Builds a structured weekly summary from a list of flagged invoices."""

    def generate(self, flagged_invoices: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Compile the weekly summary.

        Returns:
            {
                "week_ending": "<ISO date>",
                "generated_at": "<ISO timestamp>",
                "total_flagged": <int>,
                "invoices": [...]
            }
        """
        with tracer.start_as_current_span("invoice.summary") as span:
            try:
                today = date.today()
                week_ending = _next_sunday(today).isoformat()
                generated_at = datetime.utcnow().isoformat() + "Z"
                total_flagged = len(flagged_invoices)

                invoice_list = [
                    {
                        "invoice_id": inv.get("invoice_id", ""),
                        "vendor": inv.get("vendor", ""),
                        "amount": inv.get("amount", 0),
                        "currency": inv.get("currency", ""),
                        "days_pending": inv.get("days_pending", 0),
                    }
                    for inv in flagged_invoices
                ]

                summary = {
                    "week_ending": week_ending,
                    "generated_at": generated_at,
                    "total_flagged": total_flagged,
                    "invoices": invoice_list,
                }

                span.set_attribute("invoice.flagged_count", total_flagged)
                span.set_attribute("invoice.week_ending", week_ending)

                logger.info(
                    "[M3] Weekly summary generated: %d flagged invoices included.",
                    total_flagged,
                )
                return summary

            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("[M3-MISS] Summary generation failed or produced empty report. Error: %s", exc)
                span.record_exception(exc)
                return {
                    "week_ending": "",
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "total_flagged": 0,
                    "invoices": [],
                }
