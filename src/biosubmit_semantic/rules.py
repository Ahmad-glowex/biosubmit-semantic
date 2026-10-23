"""Tiered rule-based auditing engine for GEO/SRA functional genomics metadata.

Organized into four strict audit categories:
1. Syntax & record integrity (R101 - R102)
2. MINSEQE & mandatory core fields (R201 - R205)
3. Controlled vocabulary & standards (R301 - R305)
4. Cohort & experimental design QC (R401 - R402)

Every rule adheres to the signature:
    (series: SeriesRecord | None, samples: list[SampleRecord]) -> list[Finding]
and `run_all(series, samples)` runs all registered rules.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from .models import Finding, SampleRecord, SeriesRecord
from .vocab import (
    CONTROLLED_SEX,
    INSDC_LIBRARY_SOURCES,
    INSDC_LIBRARY_STRATEGIES,
    INSDC_MISSING_VALUE_TOKENS,
    JUNK_PLACEHOLDERS,
    NCBI_MOLECULES,
    is_junk_placeholder,
    is_sanctioned_missing_value,
    is_valid_library_source,
    is_valid_library_strategy,
    is_valid_molecule,
    is_valid_sex,
)

# Molecules that strongly indicate high-throughput sequencing
_SEQ_SUGGESTING_MOLECULES: frozenset[str] = frozenset({
    "total rna",
    "polya rna",
    "genomic dna",
})


# ---------------------------------------------------------------------------
# Internal defensive helpers (guarantee no crashes on None/empty/dict inputs)
# ---------------------------------------------------------------------------

def _get_str_field(obj: Any, field_name: str, default: str = "") -> str:
    """Safely extract a stripped string field from a dataclass or dictionary."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        val = obj.get(field_name, default)
    else:
        val = getattr(obj, field_name, default)
    if val is None:
        return default
    return str(val).strip()


def _get_sample_id(sample: Any, index: int | None = None) -> str:
    """Extract sample identifier or fallback to default."""
    sid = _get_str_field(sample, "id")
    if not sid:
        sid = _get_str_field(sample, "sample_id")
    if not sid:
        return f"sample_{index}" if index is not None else "unknown"
    return sid


def _get_characteristics_dict(sample: Any) -> dict[str, list[str]]:
    """Safely extract characteristics mapping preserving list values."""
    if sample is None:
        return {}
    if isinstance(sample, dict):
        raw = sample.get("characteristics", {})
    else:
        raw = getattr(sample, "characteristics", {})
    if not isinstance(raw, dict):
        return {}

    normalized: dict[str, list[str]] = {}
    for k, v in raw.items():
        key_str = str(k) if k is not None else ""
        if v is None:
            normalized[key_str] = []
        elif isinstance(v, (list, tuple)):
            normalized[key_str] = [str(item) if item is not None else "" for item in v]
        elif isinstance(v, str):
            normalized[key_str] = [v]
        else:
            normalized[key_str] = [str(v)]
    return normalized


def _normalize_rule_args(
    series: SeriesRecord | list[SampleRecord] | None,
    samples: list[SampleRecord] | None = None,
) -> tuple[SeriesRecord | None, list[SampleRecord]]:
    """Normalize rule arguments to permit both (series, samples) and (samples,) calls."""
    if samples is None:
        if isinstance(series, list):
            return None, series
        if isinstance(series, SeriesRecord):
            return series, []
        return None, []
    if isinstance(series, list) and not isinstance(samples, list):
        return None, series
    return series, samples


# ---------------------------------------------------------------------------
# Category 1: Syntax & Record Integrity
# ---------------------------------------------------------------------------

def r101_duplicate_entity_ids(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """R101 (ERROR): Flag any GSM or GSE entity identifier appearing more than once."""
    series_rec, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []
    counts: dict[str, int] = defaultdict(int)

    if series_rec is not None:
        series_id = _get_str_field(series_rec, "id")
        if series_id:
            counts[series_id] += 1

    for s in sample_list:
        sid = _get_str_field(s, "id")
        if sid:
            counts[sid] += 1

    for eid, count in counts.items():
        if count > 1:
            findings.append(
                Finding(
                    rule_id="R101",
                    severity="ERROR",
                    category="syntax",
                    entity_id=eid,
                    message=f"Duplicate entity identifier '{eid}' appears {count} times.",
                )
            )
    return findings


def r102_malformed_characteristics(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """R102 (WARNING): Flag empty keys or empty values in any characteristic."""
    _, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []

    for idx, s in enumerate(sample_list):
        sid = _get_sample_id(s, idx)
        chars = _get_characteristics_dict(s)
        for key, vals in chars.items():
            if not key.strip():
                findings.append(
                    Finding(
                        rule_id="R102",
                        severity="WARNING",
                        category="syntax",
                        entity_id=sid,
                        message=f"Sample '{sid}' has a characteristic entry with an empty or whitespace key.",
                    )
                )

            if not vals:
                findings.append(
                    Finding(
                        rule_id="R102",
                        severity="WARNING",
                        category="syntax",
                        entity_id=sid,
                        message=f"Sample '{sid}' characteristic '{key}' has no values declared.",
                    )
                )
            else:
                for val in vals:
                    if not str(val).strip():
                        findings.append(
                            Finding(
                                rule_id="R102",
                                severity="WARNING",
                                category="syntax",
                                entity_id=sid,
                                message=f"Sample '{sid}' characteristic '{key}' contains an empty or whitespace value.",
                            )
                        )
    return findings


# ---------------------------------------------------------------------------
# Category 2: MINSEQE & Mandatory Core Fields
# ---------------------------------------------------------------------------

def r201_missing_title(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """R201 (ERROR): Flag missing or empty sample title."""
    _, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []

    for idx, s in enumerate(sample_list):
        sid = _get_sample_id(s, idx)
        title = _get_str_field(s, "title")
        if not title:
            findings.append(
                Finding(
                    rule_id="R201",
                    severity="ERROR",
                    category="minseqe",
                    entity_id=sid,
                    message=f"Sample '{sid}' is missing required field: title.",
                )
            )
    return findings


def r202_missing_organism(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """R202 (ERROR): Flag missing or empty organism specification."""
    _, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []

    for idx, s in enumerate(sample_list):
        sid = _get_sample_id(s, idx)
        organism = _get_str_field(s, "organism")
        if not organism:
            findings.append(
                Finding(
                    rule_id="R202",
                    severity="ERROR",
                    category="minseqe",
                    entity_id=sid,
                    message=f"Sample '{sid}' is missing required field: organism.",
                )
            )
    return findings


def r203_missing_source_name(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """R203 (WARNING): Flag missing source_name (tissue/cell description)."""
    _, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []

    for idx, s in enumerate(sample_list):
        sid = _get_sample_id(s, idx)
        source = _get_str_field(s, "source_name")
        if not source:
            findings.append(
                Finding(
                    rule_id="R203",
                    severity="WARNING",
                    category="minseqe",
                    entity_id=sid,
                    message=f"Sample '{sid}' is missing recommended field: source_name (tissue/cell description).",
                )
            )
    return findings


def r204_missing_molecule(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """R204 (ERROR): Flag missing or empty molecule type."""
    _, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []

    for idx, s in enumerate(sample_list):
        sid = _get_sample_id(s, idx)
        molecule = _get_str_field(s, "molecule")
        if not molecule:
            findings.append(
                Finding(
                    rule_id="R204",
                    severity="ERROR",
                    category="minseqe",
                    entity_id=sid,
                    message=f"Sample '{sid}' is missing required field: molecule.",
                )
            )
    return findings


def r205_hts_completeness(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """R205 (WARNING): Flag missing instrument_model when sequencing, or missing strategy when molecule suggests HTS."""
    _, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []

    for idx, s in enumerate(sample_list):
        sid = _get_sample_id(s, idx)
        lib_strat = _get_str_field(s, "library_strategy")
        inst_model = _get_str_field(s, "instrument_model")
        molecule = _get_str_field(s, "molecule")

        # 1. Sequencing detected (library_strategy set) but instrument_model missing
        if lib_strat and not inst_model:
            findings.append(
                Finding(
                    rule_id="R205",
                    severity="WARNING",
                    category="minseqe",
                    entity_id=sid,
                    message=(
                        f"Sample '{sid}' declares library_strategy '{lib_strat}' "
                        f"(sequencing detected) but is missing instrument_model."
                    ),
                )
            )

        # 2. Molecule suggests sequencing (total RNA/polyA RNA/genomic DNA) but library_strategy missing
        if (molecule.lower() in _SEQ_SUGGESTING_MOLECULES) and not lib_strat:
            findings.append(
                Finding(
                    rule_id="R205",
                    severity="WARNING",
                    category="minseqe",
                    entity_id=sid,
                    message=(
                        f"Sample '{sid}' specifies molecule '{molecule}' suggesting "
                        f"sequencing, but is missing library_strategy."
                    ),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Category 3: Controlled Vocabulary & Standards
# ---------------------------------------------------------------------------

def r301_invalid_molecule(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """R301 (ERROR): Molecule not in NCBI_MOLECULES and not a sanctioned missing-value token."""
    _, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []

    for idx, s in enumerate(sample_list):
        sid = _get_sample_id(s, idx)
        mol = _get_str_field(s, "molecule")
        if mol:
            if not is_valid_molecule(mol) and not is_sanctioned_missing_value(mol):
                findings.append(
                    Finding(
                        rule_id="R301",
                        severity="ERROR",
                        category="controlled_vocab",
                        entity_id=sid,
                        message=(
                            f"Sample '{sid}' has invalid molecule '{mol}'. "
                            f"Must be a recognized NCBI molecule type or sanctioned missing-value token."
                        ),
                    )
                )
    return findings


def r302_invalid_library_strategy(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """R302 (ERROR): Library strategy not in INSDC_LIBRARY_STRATEGIES and not sanctioned."""
    _, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []

    for idx, s in enumerate(sample_list):
        sid = _get_sample_id(s, idx)
        strat = _get_str_field(s, "library_strategy")
        if strat:
            if not is_valid_library_strategy(strat) and not is_sanctioned_missing_value(strat):
                findings.append(
                    Finding(
                        rule_id="R302",
                        severity="ERROR",
                        category="controlled_vocab",
                        entity_id=sid,
                        message=(
                            f"Sample '{sid}' has invalid library_strategy '{strat}'. "
                            f"Must be an INSDC library strategy or sanctioned missing-value token."
                        ),
                    )
                )
    return findings


def r303_invalid_library_source(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """R303 (WARNING): Library source not in INSDC_LIBRARY_SOURCES and not sanctioned."""
    _, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []

    for idx, s in enumerate(sample_list):
        sid = _get_sample_id(s, idx)
        source = _get_str_field(s, "library_source")
        if source:
            if not is_valid_library_source(source) and not is_sanctioned_missing_value(source):
                findings.append(
                    Finding(
                        rule_id="R303",
                        severity="WARNING",
                        category="controlled_vocab",
                        entity_id=sid,
                        message=(
                            f"Sample '{sid}' has invalid library_source '{source}'. "
                            f"Must be an INSDC library source or sanctioned missing-value token."
                        ),
                    )
                )
    return findings


def r304_invalid_sex(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """R304 (WARNING): Characteristics 'sex' value not in CONTROLLED_SEX and not sanctioned."""
    _, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []

    for idx, s in enumerate(sample_list):
        sid = _get_sample_id(s, idx)
        chars = _get_characteristics_dict(s)
        for k, vals in chars.items():
            if k.strip().lower() == "sex":
                for val in vals:
                    val_str = str(val).strip()
                    if val_str:
                        if not is_valid_sex(val_str) and not is_sanctioned_missing_value(val_str):
                            findings.append(
                                Finding(
                                    rule_id="R304",
                                    severity="WARNING",
                                    category="controlled_vocab",
                                    entity_id=sid,
                                    message=(
                                        f"Sample '{sid}' characteristic 'sex' has invalid value '{val_str}'. "
                                        f"Must be in CONTROLLED_SEX or a sanctioned missing-value token."
                                    ),
                                )
                            )
    return findings


def r305_junk_placeholder(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """R305 (WARNING): Any characteristic value matching JUNK_PLACEHOLDERS (case-insensitive).

    Correctness guarantee: Sanctioned INSDC missing-value tokens must NEVER trigger this rule.
    """
    _, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []

    for idx, s in enumerate(sample_list):
        sid = _get_sample_id(s, idx)
        chars = _get_characteristics_dict(s)
        for k, vals in chars.items():
            for val in vals:
                val_str = str(val).strip()
                if not val_str:
                    continue
                # Sanctioned INSDC tokens are explicit submission standards; NEVER flag as junk
                if is_sanctioned_missing_value(val_str):
                    continue
                if is_junk_placeholder(val_str):
                    findings.append(
                        Finding(
                            rule_id="R305",
                            severity="WARNING",
                            category="controlled_vocab",
                            entity_id=sid,
                            message=(
                                f"Sample '{sid}' characteristic '{k}' contains disallowed "
                                f"junk placeholder '{val_str}'."
                            ),
                        )
                    )
    return findings


# ---------------------------------------------------------------------------
# Category 4: Cohort & Experimental Design QC
# ---------------------------------------------------------------------------

def r401_schema_parity(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """R401 (WARNING): Characteristic keys present in some samples but missing in others."""
    series_rec, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []
    total_samples = len(sample_list)
    if total_samples < 2:
        return findings

    key_display: dict[str, str] = {}
    key_presence: dict[str, set[int]] = defaultdict(set)

    for idx, s in enumerate(sample_list):
        chars = _get_characteristics_dict(s)
        for k in chars.keys():
            k_clean = str(k).strip()
            if not k_clean:
                continue
            k_norm = k_clean.lower()
            if k_norm not in key_display:
                key_display[k_norm] = k_clean
            key_presence[k_norm].add(idx)

    series_id = _get_str_field(series_rec, "id") if series_rec else "global"
    entity_id = series_id or "global"

    for k_norm in sorted(key_display.keys()):
        present_count = len(key_presence[k_norm])
        if 0 < present_count < total_samples:
            missing_count = total_samples - present_count
            display_k = key_display[k_norm]
            findings.append(
                Finding(
                    rule_id="R401",
                    severity="WARNING",
                    category="experimental_design",
                    entity_id=entity_id,
                    message=(
                        f"Characteristic key '{display_k}' has uneven schema parity across series: "
                        f"present in {present_count}/{total_samples} samples (missing in {missing_count} samples)."
                    ),
                )
            )
    return findings


def r402_singleton_replicate(
    series: SeriesRecord | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """R402 (WARNING): Group samples by full characteristic signature; flag singletons (n=1)."""
    _, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []
    if not sample_list:
        return findings

    groups: dict[tuple[str, ...], list[tuple[int, Any]]] = defaultdict(list)

    for idx, s in enumerate(sample_list):
        chars = _get_characteristics_dict(s)
        pairs: list[str] = []
        for k in sorted(chars.keys(), key=lambda x: str(x).lower()):
            k_clean = str(k).strip()
            if not k_clean:
                continue
            vals = chars[k]
            if not vals:
                pairs.append(f"{k_clean}=")
            else:
                for v in sorted(vals, key=lambda x: str(x).lower()):
                    pairs.append(f"{k_clean}={str(v).strip()}")
        sig = tuple(pairs)
        groups[sig].append((idx, s))

    for sig, grp in groups.items():
        if len(grp) == 1:
            idx, s = grp[0]
            sid = _get_sample_id(s, idx)
            sig_desc = ", ".join(sig) if sig else "no characteristics declared"
            findings.append(
                Finding(
                    rule_id="R402",
                    severity="WARNING",
                    category="experimental_design",
                    entity_id=sid,
                    message=(
                        f"Sample '{sid}' represents a singleton replicate (n=1) "
                        f"with characteristic signature [{sig_desc}]. Experimental design lacks replication."
                    ),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Aggregators and Registry
# ---------------------------------------------------------------------------

CATEGORY_1_RULES: list[Callable[..., list[Finding]]] = [
    r101_duplicate_entity_ids,
    r102_malformed_characteristics,
]

CATEGORY_2_RULES: list[Callable[..., list[Finding]]] = [
    r201_missing_title,
    r202_missing_organism,
    r203_missing_source_name,
    r204_missing_molecule,
    r205_hts_completeness,
]

CATEGORY_3_RULES: list[Callable[..., list[Finding]]] = [
    r301_invalid_molecule,
    r302_invalid_library_strategy,
    r303_invalid_library_source,
    r304_invalid_sex,
    r305_junk_placeholder,
]

CATEGORY_4_RULES: list[Callable[..., list[Finding]]] = [
    r401_schema_parity,
    r402_singleton_replicate,
]

ALL_RULES: list[Callable[..., list[Finding]]] = [
    *CATEGORY_1_RULES,
    *CATEGORY_2_RULES,
    *CATEGORY_3_RULES,
    *CATEGORY_4_RULES,
]


def run_all(
    series: SeriesRecord | list[SampleRecord] | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """Execute all audit rules over the series and samples."""
    series_rec, sample_list = _normalize_rule_args(series, samples)
    findings: list[Finding] = []
    for rule_fn in ALL_RULES:
        findings.extend(rule_fn(series_rec, sample_list))
    return findings


# ---------------------------------------------------------------------------
# Backward compatibility aliases
# ---------------------------------------------------------------------------

check_duplicate_ids = r101_duplicate_entity_ids
check_empty_values = r102_malformed_characteristics
check_placeholders = r305_junk_placeholder


def check_required_fields(
    series: SeriesRecord | list[SampleRecord] | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """Compatibility runner for required core fields."""
    series_rec, sample_list = _normalize_rule_args(series, samples)
    return [
        *r201_missing_title(series_rec, sample_list),
        *r202_missing_organism(series_rec, sample_list),
    ]


def check_controlled_vocab(
    series: SeriesRecord | list[SampleRecord] | None = None,
    samples: list[SampleRecord] | None = None,
) -> list[Finding]:
    """Compatibility runner for controlled vocabulary rules."""
    series_rec, sample_list = _normalize_rule_args(series, samples)
    return r304_invalid_sex(series_rec, sample_list)
