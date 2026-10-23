"""Tests for SemanticAuditContext construction, schema integrity, and JSON serialization."""

from __future__ import annotations

import json

import pytest

from biosubmit_semantic.context import (
    GRANT_NOTE,
    build_semantic_audit_context,
    export_semantic_audit_context_json,
)
from biosubmit_semantic.models import Finding, SampleRecord, SeriesRecord


def test_build_semantic_audit_context_keys_and_grant_note() -> None:
    """Build context from tiny series + 2 samples + 1 finding and verify keys and grant note."""
    series = SeriesRecord(
        id="GSE5000",
        title="Hepatic Transcriptomics",
        summary="Transcriptional changes in mouse hepatocytes.",
        overall_design="RNA-seq across control and treated groups.",
        sample_ids=["GSM5001", "GSM5002"],
    )
    s1 = SampleRecord(
        id="GSM5001",
        title="Control Hepatocytes Rep 1",
        source_name="Liver",
        characteristics={"tissue": ["liver"], "treatment": ["vehicle"]},
        protocols={"extract_protocol": ["Standard TRIzol reagent extraction."]},
    )
    s2 = SampleRecord(
        id="GSM5002",
        title="Treated Hepatocytes Rep 1",
        source_name="Liver",
        characteristics={"tissue": ["liver"], "treatment": ["inhibitor_A"]},
        protocols={"extract_protocol": ["Standard TRIzol reagent extraction."]},
    )
    f1 = Finding(
        rule_id="R205",
        severity="WARNING",
        category="minseqe",
        entity_id="GSM5001",
        message="Sample 'GSM5001' declares library_strategy 'RNA-Seq' but is missing instrument_model.",
    )

    ctx = build_semantic_audit_context(series, [s1, s2], [f1])

    # 1. Assert top-level keys exist
    expected_keys = {"study_narrative", "sample_matrix", "deterministic_findings", "grant_note"}
    assert expected_keys.issubset(ctx.keys())

    # 2. Assert grant_note explicitly mentions PROPOSED
    assert "PROPOSED" in ctx["grant_note"]

    # 3. Assert study narrative fields
    narrative = ctx["study_narrative"]
    assert narrative["series_id"] == "GSE5000"
    assert narrative["series_title"] == "Hepatic Transcriptomics"
    assert narrative["series_summary"] == "Transcriptional changes in mouse hepatocytes."
    assert narrative["overall_design"] == "RNA-seq across control and treated groups."
    assert "GSM5001" in narrative["sample_protocols"]
    assert narrative["sample_protocols"]["GSM5001"]["extract_protocol"] == [
        "Standard TRIzol reagent extraction."
    ]

    # 4. Assert sample matrix
    matrix = ctx["sample_matrix"]
    assert len(matrix) == 2
    assert matrix[0]["sample_id"] == "GSM5001"
    assert matrix[0]["sample_title"] == "Control Hepatocytes Rep 1"
    assert matrix[0]["factors"]["treatment"] == ["vehicle"]
    assert matrix[1]["sample_id"] == "GSM5002"
    assert matrix[1]["sample_title"] == "Treated Hepatocytes Rep 1"
    assert matrix[1]["factors"]["treatment"] == ["inhibitor_A"]

    # 5. Assert deterministic findings
    findings_list = ctx["deterministic_findings"]
    assert len(findings_list) == 1
    assert findings_list[0]["rule_id"] == "R205"
    assert findings_list[0]["severity"] == "WARNING"

    # 6. Assert JSON serialization roundtrips cleanly without error
    json_output = json.dumps(ctx, indent=2)
    deserialized = json.loads(json_output)
    assert deserialized["grant_note"] == GRANT_NOTE
    assert len(deserialized["sample_matrix"]) == 2


def test_export_semantic_audit_context_json() -> None:
    """Ensure export_semantic_audit_context_json produces valid formatted JSON."""
    series = SeriesRecord(id="GSE1", title="Liver Study")
    s = SampleRecord(id="GSM1", title="Liver Rep 1")
    json_str = export_semantic_audit_context_json(series, [s], [])
    data = json.loads(json_str)
    assert "study_narrative" in data
    assert data["study_narrative"]["series_id"] == "GSE1"
    assert data["study_narrative"]["series_title"] == "Liver Study"
    assert data["sample_matrix"][0]["sample_id"] == "GSM1"
    assert data["sample_matrix"][0]["sample_title"] == "Liver Rep 1"
    assert "PROPOSED" in data["grant_note"]
