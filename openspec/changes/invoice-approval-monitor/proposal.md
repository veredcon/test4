# Proposal: Invoice Approval Monitor Agent

## What
Build a Python-based AI agent deployed on SAP App Foundation that monitors invoice approval data, flags invoices exceeding 50,000 (local currency) that have been pending for more than 3 calendar days, generates a weekly summary report, and exposes a REST endpoint. An n8n workflow calls this endpoint every Monday morning and emails the summary to the CFO.

## Why
Finance teams currently have no proactive mechanism to detect high-value invoices stalled in approval. This creates cash flow risk and compliance exposure. The agent automates detection and reporting, eliminating manual tracking and ensuring timely executive visibility.

## Key Outcomes
- Invoices >50K pending >3 days are automatically identified every polling cycle.
- A structured weekly summary is always available via the agent's `/summary` endpoint.
- The CFO receives the summary by email every Monday at 08:00 without any manual action.
