"""Controlled vocabularies and sanctioned tokens for functional genomics metadata.

Sourced and verified against:
- NCBI GEO SOFT specification (Sample_molecule_ch1)
- INSDC / NCBI SRA / ENA XML schema (SRA.experiment.xsd: typeLibraryStrategy,
  typeLibrarySource, typeLibrarySelection)
- INSDC Missing Value Reporting Standards (not applicable, not collected, etc.)
- Disallowed junk placeholder strings (tbd, todo, test, etc.)
"""

from __future__ import annotations

# 1. NCBI GEO Molecule Types (Sample_molecule_ch1)
# Verified from NCBI Gene Expression Omnibus SOFT specification
NCBI_MOLECULES: frozenset[str] = frozenset({
    "total RNA",
    "polyA RNA",
    "cytoplasmic RNA",
    "nuclear RNA",
    "genomic DNA",
    "protein",
    "other",
})

# 2. INSDC Library Strategies
# Verified against INSDC SRA.experiment.xsd (typeLibraryStrategy)
INSDC_LIBRARY_STRATEGIES: frozenset[str] = frozenset({
    "WGS",
    "WGA",
    "WXS",
    "RNA-Seq",
    "ssRNA-seq",
    "snRNA-seq",
    "miRNA-Seq",
    "ncRNA-Seq",
    "FL-cDNA",
    "EST",
    "Hi-C",
    "ATAC-seq",
    "WCS",
    "RAD-Seq",
    "CLONE",
    "POOLCLONE",
    "AMPLICON",
    "CLONEEND",
    "FINISHING",
    "ChIP-Seq",
    "MNase-Seq",
    "DNase-Hypersensitivity",
    "Bisulfite-Seq",
    "CTS",
    "MRE-Seq",
    "MeDIP-Seq",
    "MBD-Seq",
    "Tn-Seq",
    "VALIDATION",
    "FAIRE-seq",
    "SELEX",
    "RIP-Seq",
    "ChIA-PET",
    "Synthetic-Long-Read",
    "Targeted-Capture",
    "Tethered Chromatin Conformation Capture",
    "NOMe-Seq",
    "ChM-Seq",
    "GBS",
    "Ribo-Seq",
    "OTHER",
})

# 3. INSDC Library Sources
# Verified against INSDC SRA.experiment.xsd (typeLibrarySource)
INSDC_LIBRARY_SOURCES: frozenset[str] = frozenset({
    "GENOMIC",
    "GENOMIC SINGLE CELL",
    "TRANSCRIPTOMIC",
    "TRANSCRIPTOMIC SINGLE CELL",
    "METAGENOMIC",
    "METATRANSCRIPTOMIC",
    "SYNTHETIC",
    "VIRAL RNA",
    "OTHER",
})

# 4. INSDC Library Selections
# Verified against INSDC SRA.experiment.xsd (typeLibrarySelection)
INSDC_LIBRARY_SELECTIONS: frozenset[str] = frozenset({
    "RANDOM",
    "PCR",
    "RANDOM PCR",
    "RT-PCR",
    "HMPR",
    "MF",
    "repeat fractionation",
    "size fractionation",
    "MSLL",
    "cDNA",
    "cDNA_randomPriming",
    "cDNA_oligo_dT",
    "PolyA",
    "Oligo-dT",
    "Inverse rRNA",
    "Inverse rRNA selection",
    "ChIP",
    "ChIP-Seq",
    "MNase",
    "DNase",
    "Hybrid Selection",
    "Reduced Representation",
    "Restriction Digest",
    "5-methylcytidine antibody",
    "MBD2 protein methyl-CpG binding domain",
    "CAGE",
    "RACE",
    "MDA",
    "padlock probes capture method",
    "other",
    "unspecified",
})

# 5. INSDC Sanctioned Missing Value Tokens
# Formally recognized by INSDC and NCBI BioSample Package rules; must NOT be flagged as junk
INSDC_MISSING_VALUE_TOKENS: frozenset[str] = frozenset({
    "not applicable",
    "not collected",
    "missing",
    "not provided",
    "restricted access",
})

# 6. Disallowed Junk Placeholders
# Uninformative, casual, or test entries that violate submission quality standards
JUNK_PLACEHOLDERS: frozenset[str] = frozenset({
    "tbd",
    "todo",
    "test",
    "asdf",
    "xxx",
    "?",
    "--",
    "-",
    "none",
    "null",
})

# 7. Controlled Biological Sex Values
# Standard biological sexes plus sanctioned missing-value tokens
CONTROLLED_SEX: frozenset[str] = frozenset({
    "male",
    "female",
    "hermaphrodite",
    "mixed",
    # Sanctioned INSDC missing value tokens
    "not applicable",
    "not collected",
    "missing",
    "not provided",
    "restricted access",
})

# Internal case-normalized sets for fast case-insensitive lookups
_LOWER_NCBI_MOLECULES: frozenset[str] = frozenset(x.lower() for x in NCBI_MOLECULES)
_LOWER_INSDC_LIBRARY_STRATEGIES: frozenset[str] = frozenset(x.lower() for x in INSDC_LIBRARY_STRATEGIES)
_LOWER_INSDC_LIBRARY_SOURCES: frozenset[str] = frozenset(x.lower() for x in INSDC_LIBRARY_SOURCES)
_LOWER_INSDC_LIBRARY_SELECTIONS: frozenset[str] = frozenset(x.lower() for x in INSDC_LIBRARY_SELECTIONS)
_LOWER_INSDC_MISSING_VALUE_TOKENS: frozenset[str] = frozenset(x.lower() for x in INSDC_MISSING_VALUE_TOKENS)
_LOWER_JUNK_PLACEHOLDERS: frozenset[str] = frozenset(x.lower() for x in JUNK_PLACEHOLDERS)
_LOWER_CONTROLLED_SEX: frozenset[str] = frozenset(x.lower() for x in CONTROLLED_SEX)


def is_valid_molecule(val: str, case_sensitive: bool = False) -> bool:
    """Check if value is a valid NCBI GEO molecule type."""
    cleaned = val.strip()
    if case_sensitive:
        return cleaned in NCBI_MOLECULES
    return cleaned.lower() in _LOWER_NCBI_MOLECULES


def is_valid_library_strategy(val: str, case_sensitive: bool = False) -> bool:
    """Check if value is a valid INSDC library strategy."""
    cleaned = val.strip()
    if case_sensitive:
        return cleaned in INSDC_LIBRARY_STRATEGIES
    return cleaned.lower() in _LOWER_INSDC_LIBRARY_STRATEGIES


def is_valid_library_source(val: str, case_sensitive: bool = False) -> bool:
    """Check if value is a valid INSDC library source."""
    cleaned = val.strip()
    if case_sensitive:
        return cleaned in INSDC_LIBRARY_SOURCES
    return cleaned.lower() in _LOWER_INSDC_LIBRARY_SOURCES


def is_valid_library_selection(val: str, case_sensitive: bool = False) -> bool:
    """Check if value is a valid INSDC library selection."""
    cleaned = val.strip()
    if case_sensitive:
        return cleaned in INSDC_LIBRARY_SELECTIONS
    return cleaned.lower() in _LOWER_INSDC_LIBRARY_SELECTIONS


def is_sanctioned_missing_value(val: str) -> bool:
    """Check if value matches an official INSDC missing-value token."""
    return val.strip().lower() in _LOWER_INSDC_MISSING_VALUE_TOKENS


def is_junk_placeholder(val: str) -> bool:
    """Check if value matches a disallowed junk placeholder."""
    return val.strip().lower() in _LOWER_JUNK_PLACEHOLDERS


def is_valid_sex(val: str) -> bool:
    """Check if value is a recognized sex attribute or sanctioned missing token."""
    return val.strip().lower() in _LOWER_CONTROLLED_SEX
