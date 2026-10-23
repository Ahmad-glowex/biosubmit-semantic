"""Export and context structuring for downstream semantic evaluation.

Provides the bridge between deterministic rule-based auditing findings and
the proposed LLM-powered semantic contradiction analysis layer.

Honest by construction:
Performs zero mock classification or heuristic guessing. Formats declared study
narratives, sample factors, and deterministic findings into a clean,
JSON-serializable schema for external evaluation.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from typing import Any

from .models import Finding, SampleRecord, SeriesRecord

GRANT_NOTE: str = (
    "The semantic contradiction analysis (protocol text vs sample table) is "
    "PROPOSED research under the BioSubmit-Semantic grant application. "
    "This export provides the structured context that the proposed Claude layer "
    "will evaluate; no LLM inference is performed by this package."
)


def _serialize_finding(finding: Any) -> dict[str, Any]:
    """Defensively convert a Finding or finding-like object into a JSON-serializable dict."""
    if hasattr(finding, "to_dict") and callable(finding.to_dict):
        return finding.to_dict()
    if is_dataclass(finding) and not isinstance(finding, type):
        return asdict(finding)
    if isinstance(finding, dict):
        return dict(finding)
    if hasattr(finding, "__dict__"):
        return vars(finding)
    return {"raw": str(finding)}


def _extract_sample_protocols(sample: Any) -> dict[str, list[str]]:
    """Safely extract protocols from a SampleRecord or dict as dict[str, list[str]]."""
    if sample is None:
        return {}
    if isinstance(sample, dict):
        raw = sample.get("protocols", {})
    else:
        raw = getattr(sample, "protocols", {})
    if not isinstance(raw, dict):
        return {}

    result: dict[str, list[str]] = {}
    for k, v in raw.items():
        key_str = str(k) if k is not None else ""
        if v is None:
            result[key_str] = []
        elif isinstance(v, (list, tuple)):
            result[key_str] = [str(x) if x is not None else "" for x in v]
        elif isinstance(v, str):
            result[key_str] = [v]
        else:
            result[key_str] = [str(v)]
    return result


def _extract_sample_factors(sample: Any) -> dict[str, list[str]]:
    """Safely extract characteristics / factors from a SampleRecord or dict."""
    if sample is None:
        return {}
    if isinstance(sample, dict):
        raw = sample.get("characteristics", {})
    else:
        raw = getattr(sample, "characteristics", {})
    if not isinstance(raw, dict):
        return {}

    result: dict[str, list[str]] = {}
    for k, v in raw.items():
        key_str = str(k) if k is not None else ""
        if v is None:
            result[key_str] = []
        elif isinstance(v, (list, tuple)):
            result[key_str] = [str(x) if x is not None else "" for x in v]
        elif isinstance(v, str):
            result[key_str] = [v]
        else:
            result[key_str] = [str(v)]
    return result


def _extract_sample_id(sample: Any, index: int | None = None) -> str:
    """Safely extract sample ID."""
    if sample is None:
        return f"sample_{index}" if index is not None else "unknown"
    if isinstance(sample, dict):
        sid = sample.get("id") or sample.get("sample_id", "")
    else:
        sid = getattr(sample, "id", "") or getattr(sample, "sample_id", "")
    if sid:
        return str(sid).strip()
    return f"sample_{index}" if index is not None else "unknown"


def build_semantic_audit_context(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
    findings: list[Finding] | None = None,
) -> dict[str, Any]:
    """Build a structured, JSON-serializable context payload for semantic analysis.

    Parameters:
        series: Study-level series record (or None).
        samples: List of sample records.
        findings: Diagnostic findings from deterministic rules engine.

    Returns:
        JSON-serializable dictionary with study_narrative, sample_matrix,
        deterministic_findings, and grant_note.
    """
    # 1. Study narrative: study-level text & sample-level protocol declarations
    series_summary = ""
    overall_design = ""
    if series is not None:
        if isinstance(series, dict):
            series_summary = str(series.get("summary", "") or "").strip()
            overall_design = str(series.get("overall_design", "") or "").strip()
        else:
            series_summary = str(getattr(series, "summary", "") or "").strip()
            overall_design = str(getattr(series, "overall_design", "") or "").strip()

    sample_protocols: dict[str, dict[str, list[str]]] = {}
    sample_matrix: list[dict[str, Any]] = []

    if samples:
        for idx, s in enumerate(samples):
            sid = _extract_sample_id(s, idx)
            sample_protocols[sid] = _extract_sample_protocols(s)
            sample_matrix.append({
                "sample_id": sid,
                "factors": _extract_sample_factors(s),
            })

    study_narrative: dict[str, Any] = {
        "series_summary": series_summary,
        "overall_design": overall_design,
        "sample_protocols": sample_protocols,
    }

    # 2. Deterministic findings serialization
    deterministic_findings: list[dict[str, Any]] = []
    if findings:
        for f in findings:
            deterministic_findings.append(_serialize_finding(f))

    # 3. Assemble honest semantic context
    return {
        "study_narrative": study_narrative,
        "sample_matrix": sample_matrix,
        "deterministic_findings": deterministic_findings,
        "grant_note": GRANT_NOTE,
    }


def export_semantic_audit_context_json(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
    findings: list[Finding] | None = None,
    indent: int = 2,
) -> str:
    """Serialize the semantic audit context directly to a JSON string."""
    context = build_semantic_audit_context(series, samples, findings)
    return json.dumps(context, indent=indent, ensure_ascii=False)
