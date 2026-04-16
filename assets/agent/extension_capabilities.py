"""
Extension Capabilities — Invoice Approval Monitor Agent.

Defines the extension capability for the agent, enabling customers to extend it
with additional tools (MCP servers), instructions, and hooks without code changes.
"""

import logging
import os
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try to import SAP Cloud SDK extensibility (graceful degradation if absent)
# ---------------------------------------------------------------------------
try:
    from sap_cloud_sdk.extensibility import (  # type: ignore
        ExtensionCapability,
        HookCapability,
        HookType,
        ToolAdditions,
        build_extension_capabilities,
    )
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False
    logger.warning(
        "sap-cloud-sdk extensibility build not available. "
        "Extension capabilities will be disabled."
    )

# ---------------------------------------------------------------------------
# Default configurable thresholds (overridable via env vars or extension YAML)
# ---------------------------------------------------------------------------

CAPABILITIES: dict = {
    "amount_threshold": float(os.environ.get("AMOUNT_THRESHOLD", 50_000)),
    "days_threshold": int(os.environ.get("DAYS_THRESHOLD", 3)),
    "notification_channels": [],
    "custom_flagging_rules": [],
}

# ---------------------------------------------------------------------------
# Extension capability definition
# ---------------------------------------------------------------------------

if _SDK_AVAILABLE:
    PRE_HOOK = HookCapability(
        type=HookType.BEFORE,
        id="invoice_monitor_pre_hook",
        display_name="Before Invoice Monitor Hook",
        description="Executed before invoice ingestion — can enrich context or block the run.",
    )

    POST_HOOK = HookCapability(
        type=HookType.AFTER,
        id="invoice_monitor_post_hook",
        display_name="After Invoice Monitor Hook",
        description="Executed after summary generation — can transform or augment the output.",
    )

    EXTENSION_CAPABILITIES = ExtensionCapability(
        id="default",
        display_name="Invoice Approval Monitor Extension",
        description=(
            "Allows customers to extend the Invoice Approval Monitor Agent with "
            "additional MCP tools, custom instructions, and pre/post execution hooks. "
            "Use this to add custom flagging rules, notification channels, or enrichment logic."
        ),
        instruction_supported=True,
        tool_additions_enabled=True,
        supported_hooks=[PRE_HOOK, POST_HOOK],
    )
else:
    EXTENSION_CAPABILITIES = None  # type: ignore


# ---------------------------------------------------------------------------
# Runtime extension loading
# ---------------------------------------------------------------------------

def register_extensions() -> dict:
    """
    Load any extension YAML files from the `extensions/` directory
    and merge their settings into CAPABILITIES.

    Expected YAML format:
        amount_threshold: 75000
        days_threshold: 5
        notification_channels:
          - slack
        custom_flagging_rules:
          - "vendor == 'Acme Corp'"

    Returns the merged CAPABILITIES dict.
    """
    ext_dir = Path(__file__).parent / "extensions"
    if not ext_dir.is_dir():
        logger.debug("No extensions/ directory found — using default capabilities.")
        return CAPABILITIES

    for yaml_file in sorted(ext_dir.glob("*.yaml")):
        try:
            with yaml_file.open() as fh:
                overrides = yaml.safe_load(fh) or {}
            _merge_capabilities(overrides)
            logger.info("Loaded extension overrides from %s", yaml_file.name)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to load extension file %s: %s", yaml_file.name, exc)

    return CAPABILITIES


def _merge_capabilities(overrides: dict) -> None:
    """Merge override dict into the global CAPABILITIES dict."""
    if "amount_threshold" in overrides:
        CAPABILITIES["amount_threshold"] = float(overrides["amount_threshold"])
    if "days_threshold" in overrides:
        CAPABILITIES["days_threshold"] = int(overrides["days_threshold"])
    if "notification_channels" in overrides:
        channels = overrides["notification_channels"]
        if isinstance(channels, list):
            CAPABILITIES["notification_channels"] = list(
                set(CAPABILITIES["notification_channels"]) | set(channels)
            )
    if "custom_flagging_rules" in overrides:
        rules = overrides["custom_flagging_rules"]
        if isinstance(rules, list):
            CAPABILITIES["custom_flagging_rules"] = list(
                set(CAPABILITIES["custom_flagging_rules"]) | set(rules)
            )


def get_capabilities() -> dict:
    """Return the current (possibly extended) capabilities dict."""
    return dict(CAPABILITIES)


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------

def on_before_ingest(context: dict) -> dict:
    """
    Pre-hook: called before invoice ingestion.

    Args:
        context: dict with optional keys — e.g., {'tenant_id': ..., 'user': ...}
    Returns:
        Possibly enriched context dict.
    """
    logger.debug("on_before_ingest called with context keys: %s", list(context.keys()))
    return context


def on_after_summary(summary: dict, context: dict) -> dict:
    """
    Post-hook: called after the weekly summary is generated.

    Args:
        summary: the generated summary dict.
        context: runtime context dict.
    Returns:
        Possibly enriched or transformed summary dict.
    """
    logger.debug(
        "on_after_summary called — total_flagged=%d", summary.get("total_flagged", 0)
    )
    return summary
