# Product Requirements Document1!
## Invoice Approval Monitor Agent

**Date:** 2026-04-16
**Solution Category:** AI Agent (Python) + n8n Workflow
**Status:** Draft

---

## Product Purpose & Value Proposition

Finance teams have no proactive mechanism to detect high-value invoices (>50K) that are stalled in approval for more than 3 days. This creates cash flow risk and compliance exposure. The Invoice Approval Monitor Agent automates detection, generates a weekly summary, and ensures the CFO receives an actionable report every Monday morning — eliminating manual tracking and reducing approval cycle times.

---

## Goals (In Scope)

- Monitor invoice approval data and detect invoices >50K pending >3 days.
- Generate a structured weekly summary of flagged and overdue invoices.
- Deliver the summary to the CFO every Monday morning via email.
- Provide an extensible, observable agent with business step instrumentation.

## Non-Goals (Out of Scope)

- Automatic approval or rejection of invoices.
- Real-time alerting for individual invoices (only weekly summary).
- Replacement of SAP S/4HANA approval workflow engine.
- Multi-currency threshold logic (50K assumed in local currency).

---

## User Profiles & Personas

**CFO (Chief Financial Officer)**
Receives the weekly Monday summary email. Needs a concise, actionable report showing which high-value invoices are overdue for approval so they can escalate where necessary.

**Finance / AP Manager**
Relies on the agent to flag bottlenecks. Benefits from reduced manual monitoring effort and improved visibility into the approval pipeline.

---

## Must-Have Requirements

| ID | Requirement |
|----|-------------|
| R1 | Agent polls invoice approval data (from SAP S/4HANA OData API or a mock data store during development). |
| R2 | Agent flags all invoices with amount >50,000 (local currency) that have been in "Pending Approval" status for more than 3 calendar days. |
| R3 | Agent generates a weekly summary report listing all flagged invoices (invoice ID, vendor, amount, days pending, approver). |
| R4 | An n8n workflow runs every Monday morning, retrieves the latest summary from the agent, and sends it to the CFO via email. |
| R5 | The agent exposes an API endpoint that the n8n workflow can call to retrieve the current weekly summary. |
| R6 | All key business steps are instrumented with log statements for observability (see Milestones). |

---

## Solution Architecture Overview

```
┌─────────────────────────────────┐
│   Invoice Approval Monitor      │
│   Agent (Python, App Foundation)│
│                                 │
│  - Poll invoice data (OData/API)│
│  - Apply flagging logic         │
│  - Store flagged invoices       │
│  - Expose /summary endpoint     │
└────────────────┬────────────────┘
                 │ REST API call
┌────────────────▼────────────────┐
│   n8n Workflow                  │
│   (Scheduled: Mon 08:00)        │
│                                 │
│  - Call agent /summary endpoint │
│  - Format email body            │
│  - Send email to CFO            │
└─────────────────────────────────┘
         │
         ▼
  SAP S/4HANA / Invoice Data Source
  (OData API or mock data store)
```

---

## Automation & Agent Behaviour

- The agent runs on a configurable polling interval to check invoice statuses.
- Flagging rule: `amount > 50000 AND status == "Pending Approval" AND days_pending > 3`.
- The `/summary` endpoint returns the current week's flagged invoices as structured JSON.
- The n8n workflow is the sole consumer of the summary endpoint, scheduled for Monday 08:00.
- The agent does not take automated action on invoices; it only monitors and reports.

---

## Agent Extensibility & Instrumentation

The agent MUST be built with extension points to allow future customisation without core changes:

- **Extension points**: configurable threshold values (amount, days), additional notification channels, custom flagging rules.
- **Runtime instructions**: support for loading additional instructions at runtime.
- **MCP Tools**: the agent framework should allow additional tools to be registered by extensions.
- **Hooks**: pre- and post-processing hooks for invoice ingestion and summary generation steps.
- The `sap-agent-extensibility` skill will be applied during implementation to wire up the extensibility framework.

---

## Milestones

| ID | Milestone | Achieved when | Log on achievement | Log on miss/skip |
|----|-----------|---------------|--------------------|-----------------|
| M1 | Invoice Ingestion | Agent successfully retrieves invoice data from source system | `[M1] Invoice data ingested: {count} invoices retrieved from source.` | `[M1-MISS] Invoice ingestion failed or returned no data.` |
| M2 | Flag Detection | At least one evaluation cycle completes; flagged invoices identified | `[M2] Flag detection complete: {flagged_count} invoices flagged (>{50K}, >{3 days}).` | `[M2-MISS] Flag detection skipped or no invoices evaluated.` |
| M3 | Summary Generation | Weekly summary report is successfully compiled | `[M3] Weekly summary generated: {flagged_count} flagged invoices included.` | `[M3-MISS] Summary generation failed or produced empty report.` |
| M4 | CFO Notification | n8n workflow successfully sends the summary email to the CFO | `[M4] CFO notification sent via n8n workflow on {date}.` | `[M4-MISS] CFO notification workflow failed or was not triggered.` |

---

## Non-Functional Requirements

- The agent must be deployable to SAP App Foundation (Python runtime).
- The `/summary` API endpoint must respond within 3 seconds.
- The n8n workflow must be idempotent (safe to re-run on Mondays).

---

## Assumptions & Constraints

- Invoice data is accessible via a REST/OData API or a local mock data store for development.
- The CFO's email address is a known configuration value.
- Currency threshold (50K) is applied in the invoice's native currency without conversion.
- The n8n instance is available and can reach the agent's API endpoint.
