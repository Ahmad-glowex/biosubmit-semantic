"""Data models for biosubmit-semantic.

Defines the core domain entities used across the parsing, validation,
and reporting pipeline:
- Finding: Individual audit diagnostic (errors, warnings, info).
- SampleRecord: Structured functional genomics sample metadata with
  channel attributes and preserved multi-valued characteristics.
- SeriesRecord: Study-level metadata and design declarations.
- AuditReport: Complete audit aggregation with summary statistics and
  JSON serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any


@dataclass
class Finding:
    """Represents a single diagnostic finding from an audit rule."""

    rule_id: str
    severity: str  # "ERROR", "WARNING", or "INFO"
    category: str  # e.g., "syntax", "minseqe", "controlled_vocab", "experimental_design"
    entity_id: str  # e.g., "GSM12345", "GSE67890", or "global"
    message: str

    def __post_init__(self) -> None:
        self.severity = self.severity.upper()
        if self.severity not in {"ERROR", "WARNING", "INFO"}:
            raise ValueError(
                f"Invalid severity '{self.severity}'. Must be ERROR, WARNING, or INFO."
            )

    def to_dict(self) -> dict[str, str]:
        """Return finding as a dictionary."""
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "category": self.category,
            "entity_id": self.entity_id,
            "message": self.message,
        }

    def __getitem__(self, item: str) -> Any:
        """Support dict-like subscripting for backward compatibility."""
        if item == "rule":
            return self.rule_id
        if item == "sample":
            return self.entity_id
        return getattr(self, item)


@dataclass
class SampleRecord:
    """Represents a functional genomics sample record (e.g., GEO GSM).

    Characteristics and protocols preserve multi-line and multi-valued
    declarations as lists of strings, preventing data loss from overwritten keys.
    """

    id: str
    title: str = ""
    source_name: str = ""
    organism: str = ""
    taxid: str = ""
    molecule: str = ""
    library_strategy: str = ""
    library_source: str = ""
    library_selection: str = ""
    instrument_model: str = ""
    protocols: dict[str, list[str]] = field(default_factory=dict)
    characteristics: dict[str, list[str]] = field(default_factory=dict)
    attributes: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Normalize characteristics to ensure dict of lists
        if self.characteristics:
            normalized_chars: dict[str, list[str]] = {}
            for k, v in self.characteristics.items():
                if isinstance(v, str):
                    normalized_chars[k] = [v]
                elif isinstance(v, (list, tuple)):
                    normalized_chars[k] = [str(item) for item in v]
                else:
                    normalized_chars[k] = [str(v)]
            self.characteristics = normalized_chars

        # Normalize protocols to ensure dict of lists
        if self.protocols:
            normalized_protos: dict[str, list[str]] = {}
            for k, v in self.protocols.items():
                if isinstance(v, str):
                    normalized_protos[k] = [v]
                elif isinstance(v, (list, tuple)):
                    normalized_protos[k] = [str(item) for item in v]
                else:
                    normalized_protos[k] = [str(v)]
            self.protocols = normalized_protos

        # Normalize attributes to ensure dict of lists
        if self.attributes:
            normalized_attrs: dict[str, list[str]] = {}
            for k, v in self.attributes.items():
                if isinstance(v, str):
                    normalized_attrs[k] = [v]
                elif isinstance(v, (list, tuple)):
                    normalized_attrs[k] = [str(item) for item in v]
                else:
                    normalized_attrs[k] = [str(v)]
            self.attributes = normalized_attrs

    def add_characteristic(self, key: str, value: str) -> None:
        """Append a value to a characteristic key without clobbering existing values."""
        key_stripped = key.strip()
        if not key_stripped:
            return
        self.characteristics.setdefault(key_stripped, []).append(value.strip())

    def add_attribute(self, key: str, value: str) -> None:
        """Append a value to an attribute key without clobbering existing values."""
        key_stripped = key.strip()
        if not key_stripped:
            return
        self.attributes.setdefault(key_stripped, []).append(value.strip())

    def add_protocol(self, protocol_type: str, text: str) -> None:
        """Append a protocol entry."""
        ptype_stripped = protocol_type.strip()
        if not ptype_stripped:
            return
        self.protocols.setdefault(ptype_stripped, []).append(text.strip())

    def get_characteristic(self, key: str) -> list[str]:
        """Case-insensitive lookup of all values for a given characteristic key."""
        target = key.strip().lower()
        for k, vals in self.characteristics.items():
            if k.strip().lower() == target:
                return vals
        return []

    def get_first_characteristic(self, key: str, default: str | None = None) -> str | None:
        """Retrieve the first value for a characteristic key, or default if missing."""
        vals = self.get_characteristic(key)
        return vals[0] if vals else default

    def to_dict(self) -> dict[str, Any]:
        """Return sample record as a serializable dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "source_name": self.source_name,
            "organism": self.organism,
            "taxid": self.taxid,
            "molecule": self.molecule,
            "library_strategy": self.library_strategy,
            "library_source": self.library_source,
            "library_selection": self.library_selection,
            "instrument_model": self.instrument_model,
            "protocols": self.protocols,
            "characteristics": self.characteristics,
            "attributes": self.attributes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SampleRecord:
        """Instantiate SampleRecord from a dictionary."""
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            source_name=str(data.get("source_name", "")),
            organism=str(data.get("organism", "")),
            taxid=str(data.get("taxid", "")),
            molecule=str(data.get("molecule", "")),
            library_strategy=str(data.get("library_strategy", "")),
            library_source=str(data.get("library_source", "")),
            library_selection=str(data.get("library_selection", "")),
            instrument_model=str(data.get("instrument_model", "")),
            protocols=data.get("protocols", {}) or {},
            characteristics=data.get("characteristics", {}) or {},
            attributes=data.get("attributes", {}) or {},
        )

    def __getitem__(self, item: str) -> Any:
        """Support dict-like indexing for legacy compatibility."""
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        """Support dict-like get method for legacy compatibility."""
        return getattr(self, item, default)


@dataclass
class SeriesRecord:
    """Represents study-level metadata for an experiment series (e.g., GEO GSE)."""

    id: str
    title: str = ""
    summary: str = ""
    overall_design: str = ""
    sample_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return series record as a serializable dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "overall_design": self.overall_design,
            "sample_ids": list(self.sample_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SeriesRecord:
        """Instantiate SeriesRecord from a dictionary."""
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            overall_design=str(data.get("overall_design", "")),
            sample_ids=list(data.get("sample_ids", [])),
        )


@dataclass
class AuditReport:
    """Aggregated audit result containing records, findings, and summary statistics."""

    series: SeriesRecord | None = None
    samples: list[SampleRecord] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    summary_stats: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.summary_stats:
            self.refresh_stats()

    def refresh_stats(self) -> dict[str, Any]:
        """Recalculate summary metrics across recorded findings and samples."""
        error_count = sum(1 for f in self.findings if f.severity.upper() == "ERROR")
        warning_count = sum(1 for f in self.findings if f.severity.upper() == "WARNING")
        info_count = sum(1 for f in self.findings if f.severity.upper() == "INFO")
        self.summary_stats = {
            "total_samples": len(self.samples),
            "total_findings": len(self.findings),
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "passed": error_count == 0,
        }
        return self.summary_stats

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity.upper() == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity.upper() == "WARNING")

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity.upper() == "INFO")

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    @property
    def summary(self) -> dict[str, Any]:
        """Convenience property matching summary_stats."""
        return self.refresh_stats()

    def add_finding(self, finding: Finding) -> None:
        """Add a finding and update summary statistics."""
        self.findings.append(finding)
        self.refresh_stats()

    def to_dict(self) -> dict[str, Any]:
        """Return the complete audit report as a JSON-serializable dictionary."""
        self.refresh_stats()
        return {
            "series": self.series.to_dict() if self.series is not None else None,
            "samples": [s.to_dict() for s in self.samples],
            "findings": [f.to_dict() for f in self.findings],
            "summary_stats": dict(self.summary_stats),
        }

    def to_json(self, indent: int | None = 2) -> str:
        """Serialize report to a formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
