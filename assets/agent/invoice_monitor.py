"""
Invoice Monitor — Core logic for fetching and flagging overdue high-value invoices.

Milestones:
  M1 — Invoice Ingestion
  M2 — Flag Detection
"""

import logging
import os
from datetime import date, datetime, timedelta
from typing import Any

import requests
from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("invoice-approval-monitor")

# ---------------------------------------------------------------------------
# Mock data for local development (USE_MOCK_DATA=true)
# ---------------------------------------------------------------------------

_today = date.today()

MOCK_INVOICES: list[dict[str, Any]] = [
    {
        "invoice_id": "INV-1001",
        "vendor": "Acme Corp",
        "amount": 75000.00,
        "currency": "USD",
        "status": "Pending Approval",
        "submission_date": (_today - timedelta(days=5)).isoformat(),
    },
    {
        "invoice_id": "INV-1002",
        "vendor": "Global Supplies Ltd",
        "amount": 120000.00,
        "currency": "USD",
        "status": "Pending Approval",
        "submission_date": (_today - timedelta(days=4)).isoformat(),
    },
    {
        "invoice_id": "INV-1003",
        "vendor": "Tech Partners GmbH",
        "amount": 30000.00,
        "currency": "EUR",
        "status": "Pending Approval",
        "submission_date": (_today - timedelta(days=6)).isoformat(),
    },
    {
        "invoice_id": "INV-1004",
        "vendor": "MegaVend Inc",
        "amount": 95000.00,
        "currency": "USD",
        "status": "Approved",
        "submission_date": (_today - timedelta(days=2)).isoformat(),
    },
    {
        "invoice_id": "INV-1005",
        "vendor": "Office Direct",
        "amount": 8500.00,
        "currency": "USD",
        "status": "Pending Approval",
        "submission_date": (_today - timedelta(days=7)).isoformat(),
    },
    {
        "invoice_id": "INV-1006",
        "vendor": "Logistics Plus",
        "amount": 210000.00,
        "currency": "USD",
        "status": "Pending Approval",
        "submission_date": (_today - timedelta(days=1)).isoformat(),
    },
    {
        "invoice_id": "INV-1007",
        "vendor": "Cloud Services AG",
        "amount": 67500.00,
        "currency": "EUR",
        "status": "Pending Approval",
        "submission_date": (_today - timedelta(days=8)).isoformat(),
    },
    {
        "invoice_id": "INV-1008",
        "vendor": "Raw Materials Co",
        "amount": 55000.00,
        "currency": "USD",
        "status": "Rejected",
        "submission_date": (_today - timedelta(days=3)).isoformat(),
    },
]


class InvoiceMonitor:
    """
    Monitors invoice approval data.
    Flags invoices where amount > amount_threshold AND status == 'Pending Approval'
    AND days since submission > days_threshold.
    """

    def __init__(
        self,
        data_source_url: str = "",
        amount_threshold: float = 50_000,
        days_threshold: int = 3,
    ) -> None:
        self.data_source_url = data_source_url
        self.amount_threshold = float(
            os.environ.get("AMOUNT_THRESHOLD", amount_threshold)
        )
        self.days_threshold = int(
            os.environ.get("DAYS_THRESHOLD", days_threshold)
        )
        self._use_mock = os.environ.get("USE_MOCK_DATA", "true").lower() == "true"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_flagged_invoices(self) -> list[dict[str, Any]]:
        """Fetch invoices from source, apply flagging logic, return flagged list."""
        invoices = self.fetch_invoices()
        if not invoices:
            return []
        return self.flag_overdue(invoices)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def fetch_invoices(self) -> list[dict[str, Any]]:
        """
        Retrieve invoice records from the data source.

        Returns list of dicts with keys:
          invoice_id, vendor, amount, currency, status, submission_date
        """
        with tracer.start_as_current_span("invoice.ingest") as span:
            try:
                if self._use_mock:
                    invoices = list(MOCK_INVOICES)
                else:
                    invoices = self._fetch_from_odata()

                count = len(invoices)
                span.set_attribute("invoice.count", count)

                if count == 0:
                    logger.warning("[M1-MISS] Invoice ingestion failed or returned no data.")
                    return []

                logger.info("[M1] Invoice data ingested: %d invoices retrieved from source.", count)
                return invoices

            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("[M1-MISS] Invoice ingestion failed or returned no data. Error: %s", exc)
                span.record_exception(exc)
                return []

    def flag_overdue(self, invoices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Filter invoices that are:
          - amount > amount_threshold
          - status == 'Pending Approval'
          - days since submission_date > days_threshold
        """
        with tracer.start_as_current_span("invoice.flag") as span:
            if not invoices:
                logger.warning("[M2-MISS] Flag detection skipped or no invoices evaluated.")
                span.set_attribute("invoice.flagged_count", 0)
                return []

            today = date.today()
            flagged: list[dict[str, Any]] = []

            for inv in invoices:
                try:
                    submission = date.fromisoformat(str(inv["submission_date"]))
                    days_pending = (today - submission).days
                    if (
                        float(inv["amount"]) > self.amount_threshold
                        and inv.get("status") == "Pending Approval"
                        and days_pending > self.days_threshold
                    ):
                        flagged.append({**inv, "days_pending": days_pending})
                except (KeyError, ValueError) as exc:
                    logger.debug("Skipping malformed invoice record: %s", exc)

            flagged_count = len(flagged)
            span.set_attribute("invoice.flagged_count", flagged_count)
            logger.info(
                "[M2] Flag detection complete: %d invoices flagged (>%.0fK, >%d days).",
                flagged_count,
                self.amount_threshold / 1000,
                self.days_threshold,
            )
            return flagged

    def _fetch_from_odata(self) -> list[dict[str, Any]]:
        """
        Fetch invoices from SAP S/4HANA OData API.
        Entity: API_SUPPLIER_INVOICE_SRV/A_SupplierInvoice
        """
        url = f"{self.data_source_url}/sap/opu/odata/sap/API_SUPPLIER_INVOICE_SRV/A_SupplierInvoice"
        params = {
            "$format": "json",
            "$filter": "WorkflowStatus eq 'PEND'",
            "$select": (
                "SupplierInvoice,InvoicingParty,DocumentCurrency,"
                "InvoiceGrossAmount,WorkflowStatus,DocumentDate"
            ),
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        results = response.json().get("d", {}).get("results", [])

        return [
            {
                "invoice_id": r.get("SupplierInvoice", ""),
                "vendor": r.get("InvoicingParty", ""),
                "amount": float(r.get("InvoiceGrossAmount", 0)),
                "currency": r.get("DocumentCurrency", ""),
                "status": "Pending Approval",
                "submission_date": r.get("DocumentDate", date.today().isoformat()),
            }
            for r in results
        ]
