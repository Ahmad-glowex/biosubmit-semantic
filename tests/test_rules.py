"""Tests for rule-based metadata auditing engine (Rules R101-R402)."""

from __future__ import annotations

import pytest

from biosubmit_semantic.models import SampleRecord, SeriesRecord
from biosubmit_semantic import rules


def _make_sample(
    id: str = "GSM1",
    title: str = "Sample 1",
    organism: str = "Homo sapiens",
    source_name: str = "Liver tissue",
    molecule: str = "total RNA",
    library_strategy: str = "RNA-Seq",
    library_source: str = "TRANSCRIPTOMIC",
    instrument_model: str = "Illumina NovaSeq 6000",
    characteristics: dict[str, list[str]] | None = None,
    protocols: dict[str, list[str]] | None = None,
) -> SampleRecord:
    """Helper to construct a fully-compliant SampleRecord."""
    return SampleRecord(
        id=id,
        title=title,
        organism=organism,
        source_name=source_name,
        molecule=molecule,
        library_strategy=library_strategy,
        library_source=library_source,
        instrument_model=instrument_model,
        characteristics=characteristics if characteristics is not None else {"tissue": ["liver"]},
        protocols=protocols if protocols is not None else {},
    )


# --- Category 1: Syntax & Record Integrity ---

def test_r101_duplicate_entity_ids_positive() -> None:
    """R101 flags duplicated entity identifiers with ERROR."""
    s1 = _make_sample(id="GSM100")
    s2 = _make_sample(id="GSM100")
    findings = rules.r101_duplicate_entity_ids(samples=[s1, s2])
    assert len(findings) == 1
    assert findings[0].rule_id == "R101"
    assert findings[0].severity == "ERROR"
    assert findings[0].entity_id == "GSM100"


def test_r101_duplicate_entity_ids_negative() -> None:
    """R101 produces no findings when all IDs are unique."""
    s1 = _make_sample(id="GSM101")
    s2 = _make_sample(id="GSM102")
    assert rules.r101_duplicate_entity_ids(samples=[s1, s2]) == []


def test_r102_malformed_characteristics_positive() -> None:
    """R102 flags empty keys or empty values in characteristics with WARNING."""
    s = _make_sample(id="GSM1", characteristics={"tissue": [""]})
    findings = rules.r102_malformed_characteristics(samples=[s])
    assert len(findings) == 1
    assert findings[0].rule_id == "R102"
    assert findings[0].severity == "WARNING"


def test_r102_malformed_characteristics_negative() -> None:
    """R102 passes when all keys and values are non-empty."""
    s = _make_sample(id="GSM1", characteristics={"tissue": ["liver"], "age": ["8w"]})
    assert rules.r102_malformed_characteristics(samples=[s]) == []


# --- Category 2: MINSEQE & Mandatory Core Fields ---

def test_r201_missing_title_positive() -> None:
    """R201 flags missing or blank sample title with ERROR."""
    s = _make_sample(title="")
    findings = rules.r201_missing_title(samples=[s])
    assert len(findings) == 1
    assert findings[0].rule_id == "R201"
    assert findings[0].severity == "ERROR"


def test_r201_missing_title_negative() -> None:
    """R201 passes when sample title is present."""
    s = _make_sample(title="Liver Wildtype Rep1")
    assert rules.r201_missing_title(samples=[s]) == []


def test_r202_missing_organism_positive() -> None:
    """R202 flags missing or blank organism with ERROR."""
    s = _make_sample(organism="")
    findings = rules.r202_missing_organism(samples=[s])
    assert len(findings) == 1
    assert findings[0].rule_id == "R202"
    assert findings[0].severity == "ERROR"


def test_r202_missing_organism_negative() -> None:
    """R202 passes when organism is declared."""
    s = _make_sample(organism="Homo sapiens")
    assert rules.r202_missing_organism(samples=[s]) == []


def test_r203_missing_source_name_positive() -> None:
    """R203 flags missing source_name with WARNING."""
    s = _make_sample(source_name="")
    findings = rules.r203_missing_source_name(samples=[s])
    assert len(findings) == 1
    assert findings[0].rule_id == "R203"
    assert findings[0].severity == "WARNING"


def test_r203_missing_source_name_negative() -> None:
    """R203 passes when source_name is declared."""
    s = _make_sample(source_name="Whole blood")
    assert rules.r203_missing_source_name(samples=[s]) == []


def test_r204_missing_molecule_positive() -> None:
    """R204 flags missing molecule type with ERROR."""
    s = _make_sample(molecule="")
    findings = rules.r204_missing_molecule(samples=[s])
    assert len(findings) == 1
    assert findings[0].rule_id == "R204"
    assert findings[0].severity == "ERROR"


def test_r204_missing_molecule_negative() -> None:
    """R204 passes when molecule is declared."""
    s = _make_sample(molecule="total RNA")
    assert rules.r204_missing_molecule(samples=[s]) == []


def test_r205_hts_completeness_positive() -> None:
    """R205 flags sequencing without instrument_model or HTS molecule without strategy with WARNING."""
    s = _make_sample(library_strategy="RNA-Seq", instrument_model="")
    findings = rules.r205_hts_completeness(samples=[s])
    assert len(findings) == 1
    assert findings[0].rule_id == "R205"
    assert findings[0].severity == "WARNING"


def test_r205_hts_completeness_negative() -> None:
    """R205 passes when HTS declarations are complete."""
    s = _make_sample(
        molecule="total RNA",
        library_strategy="RNA-Seq",
        instrument_model="Illumina NovaSeq 6000",
    )
    assert rules.r205_hts_completeness(samples=[s]) == []


# --- Category 3: Controlled Vocabulary & Standards ---

def test_r301_invalid_molecule_positive() -> None:
    """R301 flags unrecognized molecule values with ERROR."""
    s = _make_sample(molecule="synthetic oligo DNA-RNA hybrid")
    findings = rules.r301_invalid_molecule(samples=[s])
    assert len(findings) == 1
    assert findings[0].rule_id == "R301"
    assert findings[0].severity == "ERROR"


def test_r301_invalid_molecule_negative() -> None:
    """R301 passes valid NCBI molecules."""
    s = _make_sample(molecule="total RNA")
    assert rules.r301_invalid_molecule(samples=[s]) == []


def test_r302_invalid_library_strategy_positive() -> None:
    """R302 flags unrecognized library strategy with ERROR."""
    s = _make_sample(library_strategy="Random-Shotgun-Tag")
    findings = rules.r302_invalid_library_strategy(samples=[s])
    assert len(findings) == 1
    assert findings[0].rule_id == "R302"
    assert findings[0].severity == "ERROR"


def test_r302_invalid_library_strategy_negative() -> None:
    """R302 passes valid INSDC library strategies."""
    s = _make_sample(library_strategy="RNA-Seq")
    assert rules.r302_invalid_library_strategy(samples=[s]) == []


def test_r303_invalid_library_source_positive() -> None:
    """R303 flags unrecognized library source with WARNING."""
    s = _make_sample(library_source="SOIL_METAGENOME_CUSTOM")
    findings = rules.r303_invalid_library_source(samples=[s])
    assert len(findings) == 1
    assert findings[0].rule_id == "R303"
    assert findings[0].severity == "WARNING"


def test_r303_invalid_library_source_negative() -> None:
    """R303 passes valid INSDC library sources."""
    s = _make_sample(library_source="TRANSCRIPTOMIC")
    assert rules.r303_invalid_library_source(samples=[s]) == []


def test_r304_invalid_sex_positive() -> None:
    """R304 flags uncontrolled sex values with WARNING."""
    s = _make_sample(characteristics={"sex": ["unknown_sex"]})
    findings = rules.r304_invalid_sex(samples=[s])
    assert len(findings) == 1
    assert findings[0].rule_id == "R304"
    assert findings[0].severity == "WARNING"


def test_r304_invalid_sex_negative() -> None:
    """R304 passes controlled sex values case-insensitively."""
    s1 = _make_sample(characteristics={"sex": ["female"]})
    s2 = _make_sample(characteristics={"sex": ["Male"]})
    assert rules.r304_invalid_sex(samples=[s1, s2]) == []


def test_r305_junk_placeholder_positive() -> None:
    """R305 flags disallowed placeholder junk such as 'tbd' with WARNING."""
    s = _make_sample(characteristics={"tissue": ["tbd"]})
    findings = rules.r305_junk_placeholder(samples=[s])
    assert len(findings) == 1
    assert findings[0].rule_id == "R305"
    assert findings[0].severity == "WARNING"


def test_r305_junk_placeholder_negative_sanctioned_token() -> None:
    """CRITICAL: R305 must NEVER flag sanctioned INSDC missing-value tokens like 'not applicable'."""
    s = _make_sample(characteristics={"tissue": ["not applicable"], "cell_type": ["not collected"]})
    findings = rules.r305_junk_placeholder(samples=[s])
    assert findings == []


# --- Category 4: Cohort & Experimental Design QC ---

def test_r401_schema_parity_positive() -> None:
    """R401 flags uneven characteristic key distribution across samples with WARNING."""
    s1 = _make_sample(id="GSM1", characteristics={"genotype": ["WT"], "age": ["8w"]})
    s2 = _make_sample(id="GSM2", characteristics={"genotype": ["KO"]})  # missing 'age'
    findings = rules.r401_schema_parity(samples=[s1, s2])
    assert len(findings) == 1
    assert findings[0].rule_id == "R401"
    assert findings[0].severity == "WARNING"
    assert "age" in findings[0].message


def test_r401_schema_parity_negative() -> None:
    """R401 passes when all samples declare the same characteristic keys."""
    s1 = _make_sample(id="GSM1", characteristics={"genotype": ["WT"], "age": ["8w"]})
    s2 = _make_sample(id="GSM2", characteristics={"genotype": ["KO"], "age": ["8w"]})
    assert rules.r401_schema_parity(samples=[s1, s2]) == []


def test_r402_singleton_replicate_positive() -> None:
    """R402 flags singleton replicates (n=1); two sharing signature + one unique -> exactly one finding."""
    s1 = _make_sample(id="GSM1", characteristics={"genotype": ["WT"], "treatment": ["ctrl"]})
    s2 = _make_sample(id="GSM2", characteristics={"genotype": ["WT"], "treatment": ["ctrl"]})
    s3 = _make_sample(id="GSM3", characteristics={"genotype": ["WT"], "treatment": ["drugX"]})  # singleton
    findings = rules.r402_singleton_replicate(samples=[s1, s2, s3])
    assert len(findings) == 1
    assert findings[0].rule_id == "R402"
    assert findings[0].severity == "WARNING"
    assert findings[0].entity_id == "GSM3"


def test_r402_singleton_replicate_negative() -> None:
    """R402 passes when all experimental conditions have biological replicates (n >= 2)."""
    s1 = _make_sample(id="GSM1", characteristics={"genotype": ["WT"], "treatment": ["ctrl"]})
    s2 = _make_sample(id="GSM2", characteristics={"genotype": ["WT"], "treatment": ["ctrl"]})
    s3 = _make_sample(id="GSM3", characteristics={"genotype": ["KO"], "treatment": ["ctrl"]})
    s4 = _make_sample(id="GSM4", characteristics={"genotype": ["KO"], "treatment": ["ctrl"]})
    assert rules.r402_singleton_replicate(samples=[s1, s2, s3, s4]) == []


def test_run_all_aggregates_all_rules() -> None:
    """run_all executes all categories and returns aggregated findings."""
    clean_sample = _make_sample(id="GSM1")
    findings = rules.run_all(samples=[clean_sample])
    # Fully clean sample has no errors or warnings (only singleton replicate if n=1)
    # With a single sample, R402 fires because n=1
    rule_ids = {f.rule_id for f in findings}
    assert "R402" in rule_ids
    assert not any(f.severity == "ERROR" for f in findings)
