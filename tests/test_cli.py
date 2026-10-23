"""End-to-end tests for biosubmit CLI (text, JSON, OLS grounding, context export, exit codes)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from biosubmit_semantic import cli


@pytest.fixture
def clean_soft_file(tmp_path: Path) -> Path:
    """Fixture providing a valid, error-free GEO SOFT file with replicated samples."""
    file_path = tmp_path / "clean_experiment.soft"
    content = (
        "^SERIES = GSE1000\n"
        "!Series_title = Clean Reference Study\n"
        "!Series_summary = Investigating wildtype liver gene expression.\n"
        "!Series_overall_design = Paired biological duplicates.\n"
        "^SAMPLE = GSM1001\n"
        "!Sample_title = Liver_WT_Rep1\n"
        "!Sample_organism = Homo sapiens\n"
        "!Sample_source_name = liver tissue\n"
        "!Sample_molecule = total RNA\n"
        "!Sample_library_strategy = RNA-Seq\n"
        "!Sample_library_source = TRANSCRIPTOMIC\n"
        "!Sample_instrument_model = Illumina NovaSeq 6000\n"
        "!Sample_characteristics = tissue: liver\n"
        "!Sample_characteristics = genotype: WT\n"
        "^SAMPLE = GSM1002\n"
        "!Sample_title = Liver_WT_Rep2\n"
        "!Sample_organism = Homo sapiens\n"
        "!Sample_source_name = liver tissue\n"
        "!Sample_molecule = total RNA\n"
        "!Sample_library_strategy = RNA-Seq\n"
        "!Sample_library_source = TRANSCRIPTOMIC\n"
        "!Sample_instrument_model = Illumina NovaSeq 6000\n"
        "!Sample_characteristics = tissue: liver\n"
        "!Sample_characteristics = genotype: WT\n"
    )
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def error_soft_file(tmp_path: Path) -> Path:
    """Fixture providing a GEO SOFT file with critical validation errors."""
    file_path = tmp_path / "error_experiment.soft"
    content = (
        "^SAMPLE = GSM2001\n"
        "!Sample_organism = Homo sapiens\n"
        "!Sample_molecule = invalid_synthetic_construct\n"
    )
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_cli_clean_file_text_output_exit_0(clean_soft_file: Path, capsys: pytest.CaptureFixture) -> None:
    """Audit of clean SOFT file in text mode returns exit code 0 with zero errors and warnings."""
    exit_code = cli.main(["check", str(clean_soft_file)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "0 errors" in captured.out
    assert "0 warnings" in captured.out
    assert "0 info" in captured.out


def test_cli_clean_file_json_output_exit_0(clean_soft_file: Path, capsys: pytest.CaptureFixture) -> None:
    """Audit of clean SOFT file in --format json returns exit code 0 and valid JSON report."""
    exit_code = cli.main(["check", str(clean_soft_file), "--format", "json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["summary_stats"]["passed"] is True
    assert data["summary_stats"]["error_count"] == 0
    assert len(data["samples"]) == 2


def test_cli_error_file_exit_1(error_soft_file: Path, capsys: pytest.CaptureFixture) -> None:
    """Audit of invalid file returns exit code 1 with ERROR diagnostics in text and JSON."""
    exit_code = cli.main(["check", str(error_soft_file)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "[ERROR]" in captured.out
    assert "R201" in captured.out  # missing title

    # Test in JSON mode
    exit_code_json = cli.main(["check", str(error_soft_file), "--format", "json"])
    assert exit_code_json == 1

    captured_json = capsys.readouterr()
    data = json.loads(captured_json.out)
    assert data["summary_stats"]["passed"] is False
    assert data["summary_stats"]["error_count"] > 0


def test_cli_missing_file_io_error_exit_2(capsys: pytest.CaptureFixture) -> None:
    """Non-existent file triggers clean I/O error message and returns exit code 2."""
    exit_code = cli.main(["check", "/nonexistent/invalid/path/study.soft"])
    assert exit_code == 2

    captured = capsys.readouterr()
    assert "Error reading" in captured.err


def test_cli_export_context_writes_valid_json(
    clean_soft_file: Path,
    tmp_path: Path,
) -> None:
    """--export-context outputs valid SemanticAuditContext JSON schema to target path."""
    context_out = tmp_path / "semantic_context.json"
    exit_code = cli.main(["check", str(clean_soft_file), "--export-context", str(context_out)])
    assert exit_code == 0
    assert context_out.exists()

    data = json.loads(context_out.read_text(encoding="utf-8"))
    assert "study_narrative" in data
    assert "sample_matrix" in data
    assert "deterministic_findings" in data
    assert "grant_note" in data
    assert "PROPOSED" in data["grant_note"]
    assert len(data["sample_matrix"]) == 2


def test_cli_ols_grounding_flag(clean_soft_file: Path, capsys: pytest.CaptureFixture) -> None:
    """--ols flag queries unique tissue terms and logs INFO finding without failing audit."""
    fake_hits = [{"curie": "UBERON:0002107", "label": "liver", "ontology_name": "uberon"}]

    with patch("biosubmit_semantic.ols.lookup", return_value=fake_hits) as mock_lookup:
        exit_code = cli.main(["check", str(clean_soft_file), "--ols"])
        assert exit_code == 0
        # Two unique terms in clean_soft_file: 'liver' (from tissue) and 'liver tissue' (from source_name)
        assert mock_lookup.call_count == 2

    captured = capsys.readouterr()
    assert "2 info" in captured.out
    assert "[INFO] OLS" in captured.out
    assert "tissue 'liver' -> UBERON:0002107 (liver)" in captured.out
    assert "source_name 'liver tissue' -> UBERON:0002107 (liver)" in captured.out
