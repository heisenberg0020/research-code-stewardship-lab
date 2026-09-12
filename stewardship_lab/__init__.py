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
from .release import (
    ReleaseError,
    export_open_demo,
    package_blind,
    verify_blind_staging,
    verify_export,
)
from .view import ViewError, build_static_view, verify_static_view

__all__ = (
    "AuditError",
    "ReleaseError",
    "ViewError",
    "add_evidence",
    "add_finding",
    "assess_g0_gate",
    "bind_audit",
    "build_report_data",
    "build_static_view",
    "export_open_demo",
    "inspect_clean_project",
    "list_findings",
    "package_blind",
    "preflight",
    "rebaseline",
    "render_report_markdown",
    "set_g0_gate",
    "transition_finding",
    "verify_audit_workspace",
    "verify_blind_staging",
    "verify_export",
    "verify_static_view",
)
