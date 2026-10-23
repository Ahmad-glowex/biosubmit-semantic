"""Tests for GEO SOFT metadata parsing, multi-value preservation, table skipping, and .gz support."""

from __future__ import annotations

import gzip
from pathlib import Path
import time

import pytest

from biosubmit_semantic.models import SampleRecord, SeriesRecord
from biosubmit_semantic.parser import iter_records, parse_file, parse_soft


def test_parse_inline_soft_repeated_keys_and_malformed_lines() -> None:
    """Ensure repeated characteristic keys are preserved in order and malformed lines do not crash."""
    soft_text = (
        "^SERIES = GSE100\n"
        "!Series_title = Experimental Drug Study\n"
        "^SAMPLE = GSM101\n"
        "!Sample_title = Liver Treated 1\n"
        "!Sample_organism = Homo sapiens\n"
        "!Sample_source_name = liver tissue\n"
        "!Sample_characteristics = treatment: DrugA\n"
        "!Sample_characteristics = treatment: DrugB\n"
        "THIS_LINE_HAS_NO_EQUALS_SIGN_AND_MUST_BE_SAFELY_SKIPPED\n"
        "^SAMPLE = GSM102\n"
        "!Sample_title = Liver Control 1\n"
        "!Sample_organism = Homo sapiens\n"
        "!Sample_source_name = liver tissue\n"
        "!Sample_characteristics = tissue: liver\n"
    )
    samples = parse_soft(soft_text)
    assert len(samples) == 2

    # Check GSM101 repeated characteristics
    s1 = samples[0]
    assert s1.id == "GSM101"
    assert s1.title == "Liver Treated 1"
    assert "treatment" in s1.characteristics
    assert s1.characteristics["treatment"] == ["DrugA", "DrugB"]

    # Check GSM102
    s2 = samples[1]
    assert s2.id == "GSM102"
    assert s2.title == "Liver Control 1"
    assert s2.characteristics["tissue"] == ["liver"]


def test_parse_gzipped_soft(tmp_path: Path) -> None:
    """Ensure gzip-compressed SOFT files (.soft.gz) are decompressed and parsed transparently."""
    gz_path = tmp_path / "experiment.soft.gz"
    payload = (
        "^SERIES = GSE200\n"
        "!Series_title = Gzip Test Study\n"
        "^SAMPLE = GSM201\n"
        "!Sample_title = Sample Alpha\n"
        "!Sample_organism = Mus musculus\n"
        "!Sample_molecule = total RNA\n"
        "^SAMPLE = GSM202\n"
        "!Sample_title = Sample Beta\n"
        "!Sample_organism = Mus musculus\n"
        "!Sample_molecule = total RNA\n"
    ).encode("utf-8")

    with gzip.open(gz_path, "wb") as gz_out:
        gz_out.write(payload)

    records = list(iter_records(gz_path))
    series = [r for r in records if isinstance(r, SeriesRecord)]
    samples = [r for r in records if isinstance(r, SampleRecord)]

    assert len(series) == 1
    assert series[0].id == "GSE200"
    assert series[0].title == "Gzip Test Study"

    assert len(samples) == 2
    assert samples[0].id == "GSM201"
    assert samples[0].title == "Sample Alpha"
    assert samples[1].id == "GSM202"
    assert samples[1].title == "Sample Beta"


def test_table_skip_large_expression_block(tmp_path: Path) -> None:
    """Ensure 2000+ line data tables between !sample_table_begin/end are fast-skipped."""
    table_file = tmp_path / "study_with_table.soft"
    # Construct 2000 mock microarray/RNA expression rows
    expression_rows = "\n".join(
        f"PROBE_{idx:05d}\t{idx * 1.25:.2f}\t{idx * 0.75:.2f}" for idx in range(2000)
    )

    content = (
        "^SAMPLE = GSM301\n"
        "!Sample_title = Sample Prior to Expression Table\n"
        "!Sample_organism = Homo sapiens\n"
        "!sample_table_begin\n"
        f"{expression_rows}\n"
        "!sample_table_end\n"
        "^SAMPLE = GSM302\n"
        "!Sample_title = Sample Following Expression Table\n"
        "!Sample_organism = Homo sapiens\n"
    )
    table_file.write_text(content, encoding="utf-8")

    start_time = time.perf_counter()
    samples = parse_file(table_file)
    elapsed = time.perf_counter() - start_time

    assert len(samples) == 2
    assert samples[0].id == "GSM301"
    assert samples[0].title == "Sample Prior to Expression Table"
    assert samples[1].id == "GSM302"
    assert samples[1].title == "Sample Following Expression Table"
    assert elapsed < 1.0


def test_series_extraction_multiline_joined(tmp_path: Path) -> None:
    """Ensure multi-line !Series_summary and !Series_overall_design are joined with newlines."""
    series_file = tmp_path / "multiline_study.soft"
    content = (
        "^SERIES = GSE400\n"
        "!Series_title = Transcriptional Dynamics of Stem Cells\n"
        "!Series_summary = Paragraph 1: Background of the stem cell differentiation study.\n"
        "!Series_summary = Paragraph 2: Comprehensive RNA sequencing was performed.\n"
        "!Series_overall_design = Component A: Time course across 4 time points.\n"
        "!Series_overall_design = Component B: 3 biological replicates per condition.\n"
        "^SAMPLE = GSM401\n"
        "!Sample_title = D0_Rep1\n"
        "^SAMPLE = GSM402\n"
        "!Sample_title = D0_Rep2\n"
    )
    series_file.write_text(content, encoding="utf-8")

    records = list(iter_records(series_file))
    series_list = [r for r in records if isinstance(r, SeriesRecord)]
    assert len(series_list) == 1
    s = series_list[0]

    assert s.id == "GSE400"
    assert s.title == "Transcriptional Dynamics of Stem Cells"
    assert s.summary == (
        "Paragraph 1: Background of the stem cell differentiation study.\n"
        "Paragraph 2: Comprehensive RNA sequencing was performed."
    )
    assert s.overall_design == (
        "Component A: Time course across 4 time points.\n"
        "Component B: 3 biological replicates per condition."
    )
    assert s.sample_ids == ["GSM401", "GSM402"]
