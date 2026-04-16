# Design: Invoice Approval Monitor Agent

## Architecture

```
assets/
  agent/                   # Python AI agent (SAP App Foundation)
    agent.py               # Main agent entry point (A2A protocol)
    invoice_monitor.py     # Core monitoring logic
    summary_generator.py   # Weekly summary compilation
    extension_capabilities.py  # Extensibility framework
    requirements.txt
    agent.yaml
  n8n-workflow/            # n8n workflow definition
    cfo-weekly-summary.json
```

## Components

### AI Agent (Python)
- **Runtime**: SAP App Foundation (Python)
- **Protocol**: Agent2Agent (A2A)
- **Polling**: Configurable interval (default: every 6 hours)
- **Flagging rule**: `amount > 50000 AND status == "Pending Approval" AND days_pending > 3`
- **Endpoint**: `GET /summary` — returns current week's flagged invoices as JSON
- **Data source**: SAP S/4HANA Invoice OData API (`/sap/opu/odata/sap/API_SUPPLIER_INVOICE_SRV`) or mock store for development

### n8n Workflow
- **Trigger**: CRON — every Monday at 08:00
- **Steps**:
  1. HTTP GET → agent `/summary` endpoint
  2. Format email body from JSON response
  3. Send email to CFO (configured address)

### Extensibility
- Extension points: configurable thresholds (amount, days), additional notification channels, custom flagging rules
- Runtime instruction loading
- Pre/post hooks for ingestion and summary generation steps
- Implemented via `extension_capabilities.py` using the `sap-agent-extensibility` pattern

## Business Step Instrumentation (Milestones)
| ID | Milestone | Log statement |
|----|-----------|---------------|
| M1 | Invoice Ingestion | `[M1] Invoice data ingested: {count} invoices retrieved from source.` |
| M2 | Flag Detection | `[M2] Flag detection complete: {flagged_count} invoices flagged (>50K, >3 days).` |
| M3 | Summary Generation | `[M3] Weekly summary generated: {flagged_count} flagged invoices included.` |
| M4 | CFO Notification | `[M4] CFO notification sent via n8n workflow on {date}.` |

## API References
- Invoice data source: SAP S/4HANA `API_SUPPLIER_INVOICE_SRV` (OData v2)
  - Entity: `A_SupplierInvoice` — fields: `SupplierInvoice`, `DocumentDate`, `InvoicingParty`, `DocumentCurrency`, `InvoiceGrossAmount`, `WorkflowStatus`
- Discovery results: `api-discovery-results.md` (if populated by ekx_search)
