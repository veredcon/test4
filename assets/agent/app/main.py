"""
Invoice Approval Monitor Agent — Entry point for SAP App Foundation (A2A protocol).
"""

from sap.aif.app_foundation import set_aicore_config, auto_instrument

# IMPORTANT: These must be called FIRST, before any AI framework imports
set_aicore_config()
auto_instrument()

import logging
import os
import sys

# Ensure the parent agent root is on sys.path
_AGENT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

from a2a.server.apps import A2AStarlette
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from app.agent_executor import InvoiceApprovalAgentExecutor
from app.agent import init_agent

# Extension capability integration (graceful degradation if SDK absent)
try:
    from sap_cloud_sdk.extensibility import build_extension_capabilities  # type: ignore
    from extension_capabilities import EXTENSION_CAPABILITIES
    _EXT_ENABLED = EXTENSION_CAPABILITIES is not None
except ImportError:
    _EXT_ENABLED = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AGENT_ID = "invoice-approval-monitor"
AGENT_NAME = "invoice-approval-monitor"
AGENT_VERSION = "1.0.0"
AGENT_DESCRIPTION = (
    "Monitors invoice approvals, flags invoices >50K pending >3 days, "
    "and generates weekly summaries for the CFO."
)


def create_agent_card() -> AgentCard:
    skill = AgentSkill(
        id="invoice-monitoring",
        name="Invoice Monitoring",
        description=AGENT_DESCRIPTION,
        tags=["invoice", "approval", "monitor", "finance", "cfo"],
        examples=[
            "Show me invoices over 50K that are pending approval for more than 3 days.",
            "Generate the weekly invoice approval summary.",
        ],
    )

    extensions = (
        build_extension_capabilities(EXTENSION_CAPABILITIES)
        if _EXT_ENABLED
        else []
    )

    return AgentCard(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        version=AGENT_VERSION,
        url=os.environ.get("AGENT_URL", "http://localhost:8080"),
        capabilities=AgentCapabilities(
            streaming=False,
            extensions=extensions,
        ),
        skills=[skill],
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
    )


def build_app() -> A2AStarlette:
    init_agent()
    logger.info("Starting %s v%s", AGENT_NAME, AGENT_VERSION)

    executor = InvoiceApprovalAgentExecutor()
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )
    return A2AStarlette(
        http_handler=request_handler,
        agent_card=create_agent_card(),
    )


app = build_app()
