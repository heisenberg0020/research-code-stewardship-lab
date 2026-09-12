"""Public lifecycle primitives for Research Code Stewardship Lab."""

from .audit import (
    AuditError,
    add_evidence,
    add_finding,
    assess_g0_gate,
    bind_audit,
    build_report_data,
    inspect_clean_project,
    list_findings,
    preflight,
    rebaseline,
    render_report_markdown,
    set_g0_gate,
    transition_finding,
    verify_audit_workspace,
)

__all__ = (
    "AuditError",
    "add_evidence",
    "add_finding",
    "assess_g0_gate",
    "bind_audit",
    "build_report_data",
    "inspect_clean_project",
    "list_findings",
    "preflight",
    "rebaseline",
    "render_report_markdown",
    "set_g0_gate",
    "transition_finding",
    "verify_audit_workspace",
)
