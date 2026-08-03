"""
FAP-Insurance — Audit Report HTML Generator
EvidenceEnvelope · C2PA · Oracle Observations · Investor-demo quality
"""

from __future__ import annotations

from typing import Any, Dict

from audit import AuditRecord


def generate_audit_report(record: AuditRecord, chain_status: Dict[str, Any]) -> str:
    components = record.components
    verdict_color = {
        "STRICT": "#22c55e", "PROBABLE": "#3b82f6",
        "SUSPICIOUS": "#f59e0b", "QUARANTINE": "#ef4444",
    }.get(record.verdict, "#6b7280")

    components_html = "\n".join(
        f"""<div class="component-row">
            <span class="component-name">{k.replace('_', ' ').title()}</span>
            <div class="component-bar"><div class="component-fill" style="width: {v*100:.1f}%; background: {verdict_color if v > 0.5 else '#ef4444'}"></div></div>
            <span class="component-score">{v:.4f}</span>
        </div>"""
        for k, v in sorted(components.items())
    )

    # Oracle observations from envelope
    observations_html = ""
    if record.envelope and "observations" in record.envelope:
        observations_html = "<h2>Oracle Observations</h2><div class='observations'>"
        for obs in record.envelope["observations"]:
            status_color = {"OK": "#22c55e", "DEGRADED": "#f59e0b", "FAILED": "#ef4444", "DISCREPANCY": "#ef4444"}.get(obs.get("status"), "#6b7280")
            observations_html += f"""
            <div class="obs-card">
                <div class="obs-header">
                    <span class="obs-type">{obs.get("oracle_type", "unknown").upper()}</span>
                    <span class="obs-source">{obs.get("source", "unknown")}</span>
                    <span class="obs-status" style="color:{status_color}">{obs.get("status", "UNKNOWN")}</span>
                </div>
                <div class="obs-confidence">Confidence: {obs.get("confidence", 0.0):.4f}</div>
                {f'<div class="obs-discrepancy">⚠ {obs["discrepancy_note"]}</div>' if obs.get("discrepancy_note") else ""}
            </div>
            """
        observations_html += "</div>"

    # C2PA section
    c2pa_html = ""
    if record.envelope and record.envelope.get("c2pa_present"):
        c2pa_html = f"""
        <div class="c2pa-section">
            <h2>C2PA Content Credentials</h2>
            <div class="c2pa-status" style="color: {'#22c55e' if record.envelope.get('c2pa_valid') else '#ef4444'}">
                {'✓ C2PA Manifest Valid' if record.envelope.get('c2pa_valid') else '✗ C2PA Manifest Invalid'}
            </div>
            <div class="hash-row">Manifest Hash: {record.envelope.get('c2pa_manifest_hash', 'N/A')}</div>
        </div>
        """
    else:
        c2pa_html = """
        <div class="c2pa-section">
            <h2>C2PA Content Credentials</h2>
            <div class="c2pa-status" style="color: #64748b">No C2PA manifest detected</div>
        </div>
        """

    integrity_badge = "✓ INTACT" if chain_status.get("status") == "intact" else "✗ COMPROMISED"
    integrity_color = "#22c55e" if chain_status.get("status") == "intact" else "#ef4444"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>FAP Audit — {record.claim_id}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; line-height: 1.6; padding: 2rem; }}
.container {{ max-width: 900px; margin: 0 auto; }}
.header {{ text-align: center; padding: 2rem 0; border-bottom: 1px solid #334155; margin-bottom: 2rem; }}
.header h1 {{ font-size: 2rem; font-weight: 700; letter-spacing: -0.02em; }}
.header .subtitle {{ color: #94a3b8; margin-top: 0.5rem; }}
.verdict-banner {{ background: {verdict_color}15; border: 1px solid {verdict_color}40; border-radius: 12px; padding: 1.5rem; text-align: center; margin-bottom: 2rem; }}
.verdict-banner .verdict-label {{ font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.1em; color: {verdict_color}; }}
.verdict-banner .verdict-value {{ font-size: 2.5rem; font-weight: 800; color: {verdict_color}; margin: 0.5rem 0; }}
.verdict-banner .verdict-score {{ font-size: 1.125rem; color: #94a3b8; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 2rem; }}
@media (max-width: 640px) {{ .grid {{ grid-template-columns: 1fr; }} }}
.card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem; }}
.card h3 {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; margin-bottom: 0.5rem; }}
.card .value {{ font-size: 1rem; font-weight: 600; color: #f1f5f9; word-break: break-all; }}
.components {{ margin-bottom: 2rem; }}
.components h2 {{ font-size: 1.25rem; margin-bottom: 1rem; color: #f8fafc; }}
.component-row {{ display: flex; align-items: center; gap: 1rem; padding: 0.75rem 0; border-bottom: 1px solid #334155; }}
.component-name {{ width: 140px; font-size: 0.875rem; color: #94a3b8; flex-shrink: 0; }}
.component-bar {{ flex: 1; height: 8px; background: #334155; border-radius: 4px; overflow: hidden; }}
.component-fill {{ height: 100%; border-radius: 4px; transition: width 0.5s ease; }}
.component-score {{ width: 60px; text-align: right; font-family: 'SF Mono', monospace; font-size: 0.875rem; color: #e2e8f0; }}
.observations {{ margin-bottom: 2rem; }}
.observations h2 {{ font-size: 1.25rem; margin-bottom: 1rem; color: #f8fafc; }}
.obs-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1rem; margin-bottom: 0.75rem; }}
.obs-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }}
.obs-type {{ font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #0ea5e9; }}
.obs-source {{ font-size: 0.75rem; color: #64748b; }}
.obs-status {{ font-size: 0.75rem; font-weight: 600; }}
.obs-confidence {{ font-size: 0.875rem; color: #94a3b8; }}
.obs-discrepancy {{ margin-top: 0.5rem; padding: 0.5rem; background: #ef444415; border: 1px solid #ef444440; border-radius: 6px; font-size: 0.875rem; color: #fca5a5; }}
.c2pa-section {{ margin-bottom: 2rem; }}
.c2pa-section h2 {{ font-size: 1.25rem; margin-bottom: 0.75rem; color: #f8fafc; }}
.c2pa-status {{ font-size: 1rem; font-weight: 600; margin-bottom: 0.5rem; }}
.integrity {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem; margin-bottom: 2rem; }}
.integrity h2 {{ font-size: 1.25rem; margin-bottom: 0.75rem; }}
.integrity-badge {{ display: inline-block; padding: 0.35rem 0.75rem; border-radius: 6px; font-size: 0.875rem; font-weight: 600; background: {integrity_color}20; color: {integrity_color}; border: 1px solid {integrity_color}40; }}
.hash-row {{ font-family: 'SF Mono', monospace; font-size: 0.75rem; color: #64748b; margin-top: 0.5rem; word-break: break-all; }}
.footer {{ text-align: center; padding-top: 2rem; border-top: 1px solid #334155; color: #475569; font-size: 0.875rem; }}
.footer .badge {{ display: inline-block; background: #0ea5e920; color: #0ea5e9; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; margin-top: 0.5rem; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>FAP Evidence Audit</h1>
        <div class="subtitle">Fraud-resistant Authentication & Provenance</div>
    </div>

    <div class="verdict-banner">
        <div class="verdict-label">Verdict</div>
        <div class="verdict-value">{record.verdict}</div>
        <div class="verdict-score">Confidence Score: {record.confidence_score:.4f}</div>
    </div>

    <div class="grid">
        <div class="card"><h3>Evidence ID</h3><div class="value">{record.evidence_id}</div></div>
        <div class="card"><h3>Claim ID</h3><div class="value">{record.claim_id}</div></div>
        <div class="card"><h3>Request ID</h3><div class="value">{record.request_id}</div></div>
        <div class="card"><h3>Processed At</h3><div class="value">{record.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")}</div></div>
        <div class="card"><h3>Engine Version</h3><div class="value">{record.engine_version}</div></div>
        <div class="card"><h3>Policy Version</h3><div class="value">{record.policy_version}</div></div>
        <div class="card"><h3>Total Records in Chain</h3><div class="value">{chain_status.get("total_records", 0)}</div></div>
        <div class="card"><h3>Chain Head Hash</h3><div class="value">{chain_status.get("head_hash", "N/A")[:24]}...</div></div>
    </div>

    <div class="components">
        <h2>Signal Components</h2>
        {components_html}
    </div>

    {observations_html}

    {c2pa_html}

    <div class="integrity">
        <h2>Chain Integrity</h2>
        <span class="integrity-badge">{integrity_badge}</span>
        <div class="hash-row">Record Hash: {record.record_hash}</div>
        <div class="hash-row">Previous Hash: {record.previous_hash or "GENESIS"}</div>
        <div class="hash-row">Replay Inputs Hash: {record.replay_inputs_hash}</div>
    </div>

    <div class="footer">
        <p>Generated by FAP-Insurance {record.engine_version}</p>
        <span class="badge">Tamper-evident SHA-256 hash chain · Independent reality oracles · C2PA-ready</span>
    </div>
</div>
</body>
</html>"""
