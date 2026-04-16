# Tasks: Invoice Approval Monitor Agent change

## Task 1 — Bootstrap the Agent Project
**Skill**: `sap-agent-bootstrap`
- Create the agent project under `assets/agent/` using the SAP App Foundation Python agent template.
- Ensure `agent.yaml`, `requirements.txt`, `agent.py` are generated.
- Set agent name: `invoice-approval-monitor`.

## Task 2 — Implement Invoice Monitor Core (`invoice_monitor.py`)
Create `assets/agent/invoice_monitor.py`:
- Class `InvoiceMonitor` with:
  - `__init__(self, data_source_url, amount_threshold=50000, days_threshold=3)` — configurable thresholds.
  - `fetch_invoices(self) -> list[dict]` — calls SAP S/4HANA OData endpoint `API_SUPPLIER_INVOICE_SRV/A_SupplierInvoice` (or uses mock data if `USE_MOCK_DATA=true` env var is set). Returns list of invoice dicts with fields: `invoice_id`, `vendor`, `amount`, `currency`, `status`, `submission_date`.
  - `flag_overdue(self, invoices: list[dict]) -> list[dict]` — filters invoices where `amount > self.amount_threshold` AND `status == "Pending Approval"` AND `(today - submission_date).days > self.days_threshold`.
  - `get_flagged_invoices(self) -> list[dict]` — calls `fetch_invoices()` then `flag_overdue()`. Logs M1 and M2 milestones.

Mock data (used when `USE_MOCK_DATA=true`): return 5-10 sample invoice dicts with varied amounts, statuses, and dates spanning the last 10 days.

Milestone logging requirements:
- After `fetch_invoices()` succeeds: `logger.info("[M1] Invoice data ingested: %d invoices retrieved from source.", count)`
- After `fetch_invoices()` fails: `logger.warning("[M1-MISS] Invoice ingestion failed or returned no data.")`
- After `flag_overdue()`: `logger.info("[M2] Flag detection complete: %d invoices flagged (>50K, >3 days).", flagged_count)`
- If no invoices evaluated: `logger.warning("[M2-MISS] Flag detection skipped or no invoices evaluated.")`

## Task 3 — Implement Summary Generator (`summary_generator.py`)
Create `assets/agent/summary_generator.py`:
- Class `SummaryGenerator` with:
  - `generate(self, flagged_invoices: list[dict]) -> dict` — builds a summary dict:
    ```json
    {
      "week_ending": "<ISO date of next Sunday>",
      "generated_at": "<ISO timestamp>",
      "total_flagged": <int>,
      "invoices": [ { "invoice_id": ..., "vendor": ..., "amount": ..., "currency": ..., "days_pending": ... } ]
    }
    ```
  - Logs M3 milestone: `logger.info("[M3] Weekly summary generated: %d flagged invoices included.", total_flagged)`
  - On failure: `logger.warning("[M3-MISS] Summary generation failed or produced empty report.")`

## Task 4 — Implement Agent Entry Point (`agent.py`)
Update/create `assets/agent/agent.py`:
- Initialize `InvoiceMonitor` and `SummaryGenerator` at startup.
- Expose HTTP endpoint `GET /summary` returning the JSON summary (call `get_flagged_invoices()` then `generate()`).
- Expose HTTP endpoint `GET /health` returning `{"status": "ok"}`.
- Run polling loop in background thread: every `POLL_INTERVAL_HOURS` (default 6) hours call `get_flagged_invoices()` and store result in memory for `/summary` to serve.
- On startup, log agent name and version.
- Load extension capabilities from `extension_capabilities.py` at startup (call `register_extensions()`).

## Task 5 — Implement Extensibility (`extension_capabilities.py`)
**Skill**: `sap-agent-extensibility`
Create `assets/agent/extension_capabilities.py` implementing the SAP agent extensibility pattern:
- Define `EXTENSION_CAPABILITIES` dict describing:
  - `amount_threshold`: configurable invoice amount threshold (default 50000)
  - `days_threshold`: configurable days pending threshold (default 3)
  - `notification_channels`: list of additional notification channels (default [])
  - `custom_flagging_rules`: list of additional rule expressions (default [])
- Implement `register_extensions()` — loads any extension YAML from `extensions/` directory at runtime and merges into capabilities.
- Implement pre-hook `on_before_ingest(context)` and post-hook `on_after_summary(summary, context)`.
- Export `get_capabilities() -> dict`.

## Task 6 — Configure `agent.yaml`
Update `assets/agent/agent.yaml`:
```yaml
name: invoice-approval-monitor
display_name: Invoice Approval Monitor Agent
description: Monitors invoice approvals, flags invoices >50K pending >3 days, generates weekly summaries.
version: "1.0.0"
runtime: python
entrypoint: agent.py
env:
  - name: USE_MOCK_DATA
    default: "true"
  - name: POLL_INTERVAL_HOURS
    default: "6"
  - name: AMOUNT_THRESHOLD
    default: "50000"
  - name: DAYS_THRESHOLD
    default: "3"
  - name: DATA_SOURCE_URL
    default: ""
  - name: CFO_EMAIL
    default: ""
```

## Task 7 — Update `requirements.txt`
`assets/agent/requirements.txt` must include:
```
requests>=2.31.0
flask>=3.0.0
python-dateutil>=2.8.2
opentelemetry-sdk>=1.20.0
opentelemetry-exporter-otlp>=1.20.0
```

## Task 8 — Business Step Instrumentation (OpenTelemetry)
In `invoice_monitor.py` and `summary_generator.py`:
- Import `opentelemetry.trace` and create a tracer: `tracer = trace.get_tracer("invoice-approval-monitor")`.
- Wrap `fetch_invoices()` in a span named `"invoice.ingest"`.
- Wrap `flag_overdue()` in a span named `"invoice.flag"`.
- Wrap `SummaryGenerator.generate()` in a span named `"invoice.summary"`.
- Add span attributes: `invoice.count`, `invoice.flagged_count`, `invoice.week_ending`.

## Task 9 — Create n8n Workflow (`assets/n8n-workflow/cfo-weekly-summary.json`)
Create `assets/n8n-workflow/cfo-weekly-summary.json` as a valid n8n workflow export:
- **Trigger node**: Cron — schedule `0 8 * * 1` (Monday 08:00).
- **HTTP Request node**: GET `{{$env.AGENT_SUMMARY_URL}}/summary` — parses JSON response.
- **Set node**: Formats email body:
  ```
  Weekly Invoice Approval Summary — Week ending {{week_ending}}

  Flagged Invoices (>50K, pending >3 days): {{total_flagged}}

  {{#each invoices}}
  - Invoice {{invoice_id}} | Vendor: {{vendor}} | Amount: {{amount}} {{currency}} | Days Pending: {{days_pending}}
  {{/each}}

  Generated by Invoice Approval Monitor Agent.
  ```
- **Email node** (SMTP or n8n email integration): Send to `{{$env.CFO_EMAIL}}`, subject `Weekly Invoice Approval Summary — {{week_ending}}`.
- Include `AGENT_SUMMARY_URL` and `CFO_EMAIL` as workflow-level environment variable references.
- Add a **success log node** that logs M4: `[M4] CFO notification sent via n8n workflow on {{$now}}.`

## Task 10 — Write Tests (`tests/`)
Create `assets/agent/tests/test_invoice_monitor.py`:
- Test `flag_overdue()` with mock invoices: assert correct invoices are flagged.
- Test `generate()` with flagged invoice list: assert summary structure is correct.
- Test `/summary` endpoint: mock `InvoiceMonitor.get_flagged_invoices()`, assert HTTP 200 and JSON shape.
- Test `/health` endpoint: assert HTTP 200.

## Task 11 — README (`assets/agent/README.md`)
Create a concise README covering:
- Purpose and architecture overview.
- Environment variables reference.
- How to run locally (with mock data).
- How to deploy to SAP App Foundation.
- n8n workflow setup instructions (env vars, importing the workflow JSON).
