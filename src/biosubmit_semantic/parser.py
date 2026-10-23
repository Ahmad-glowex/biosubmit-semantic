"""GEO SOFT-format metadata parser for functional genomics submissions.

Parses NCBI GEO SOFT files (plain text or gzip-compressed) line-by-line,
yielding structured SeriesRecord and SampleRecord objects while safely
skipping large expression data tables and guarding against malformed lines.
"""

from __future__ import annotations

from contextlib import contextmanager
import gzip
from pathlib import Path
from typing import Iterator

from .models import SampleRecord, SeriesRecord

# Known protocol field identifiers normalized to canonical protocol dictionary keys
_KNOWN_PROTOCOL_NAMES: frozenset[str] = frozenset({
    "extract_protocol",
    "growth_protocol",
    "label_protocol",
    "hyb_protocol",
    "scan_protocol",
    "data_processing",
    "treatment_protocol",
})


def _is_gzipped_file(path: str | Path) -> bool:
    """Check if file is gzip-compressed by path extension or magic bytes."""
    path_str = str(path)
    if path_str.endswith(".gz"):
        return True
    try:
        with open(path, "rb") as fh:
            magic = fh.read(2)
            return magic == b"\x1f\x8b"
    except OSError:
        return False


def _decode_line(raw_bytes: bytes) -> str:
    """Decode raw bytes trying UTF-8, then Windows-1252, then replace.

    Guarantees no UnicodeDecodeError is raised to the caller.
    """
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw_bytes.decode("windows-1252")
        except UnicodeDecodeError:
            return raw_bytes.decode("windows-1252", errors="replace")


@contextmanager
def _open_line_stream(path: str | Path) -> Iterator[Iterator[str]]:
    """Open a plain or gzipped file and stream decoded lines safely.

    Fast-skips large table rows directly on raw bytes to prevent unnecessary
    string allocations and decodes on 100MB+ expression tables.
    """
    is_gz = _is_gzipped_file(path)
    raw_stream = gzip.open(path, "rb") if is_gz else open(path, "rb")
    try:
        def line_generator() -> Iterator[str]:
            in_table = False
            for raw_line in raw_stream:
                if in_table:
                    if b"_table_end" in raw_line:
                        stripped = raw_line.strip()
                        if stripped.startswith((b"!sample_table_end", b"!platform_table_end", b"!series_table_end")):
                            in_table = False
                    continue

                if b"_table_begin" in raw_line:
                    stripped = raw_line.strip()
                    if stripped.startswith((b"!sample_table_begin", b"!platform_table_begin", b"!series_table_begin")):
                        in_table = True
                        continue

                yield _decode_line(raw_line).rstrip("\r\n")

        yield line_generator()
    finally:
        raw_stream.close()


def _normalize_protocol_key(tag: str) -> str | None:
    """Normalize a protocol line tag into a canonical key.

    Maps e.g. '!Sample_extract_protocol_ch1' -> 'extract_protocol'.
    """
    lower = tag.lower()
    if not lower.startswith("!sample_"):
        return None
    key = lower[len("!sample_"):]
    if key.endswith("_ch1"):
        key = key[:-4]
    if key in _KNOWN_PROTOCOL_NAMES or key.endswith("_protocol"):
        return key
    return None


def _parse_lines(lines: Iterator[str]) -> Iterator[SeriesRecord | SampleRecord]:
    """Parse an iterator of SOFT lines into SeriesRecord and SampleRecord objects."""
    current_series: SeriesRecord | None = None
    series_pending_yield: bool = False
    current_sample: SampleRecord | None = None
    in_table: bool = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Fast-skip expression and platform data rows without string operations
        if in_table:
            if line.startswith(("!sample_table_end", "!platform_table_end", "!series_table_end")):
                in_table = False
            continue

        if line.startswith(("!sample_table_begin", "!platform_table_begin", "!series_table_begin")):
            in_table = True
            continue

        # Guard every split: lines without '=' must be safely skipped
        if "=" not in line:
            continue

        tag, _, value = line.partition("=")
        tag = tag.strip()
        value = value.strip()

        # Handle entity declarations (^DATABASE, ^SERIES, ^PLATFORM, ^SAMPLE)
        if tag.startswith("^"):
            entity_type = tag[1:].strip().upper()
            entity_id = value

            if current_sample is not None:
                yield current_sample
                current_sample = None

            if entity_type == "SAMPLE":
                if series_pending_yield and current_series is not None:
                    yield current_series
                    series_pending_yield = False
                current_sample = SampleRecord(id=entity_id)
                if current_series is not None and entity_id not in current_series.sample_ids:
                    current_series.sample_ids.append(entity_id)

            elif entity_type == "SERIES":
                if series_pending_yield and current_series is not None:
                    yield current_series
                current_series = SeriesRecord(id=entity_id)
                series_pending_yield = True

            elif entity_type in {"PLATFORM", "DATABASE"}:
                if series_pending_yield and current_series is not None:
                    yield current_series
                    series_pending_yield = False
            continue

        # Series metadata lines
        if current_series is not None and tag.lower().startswith("!series_"):
            tag_lower = tag.lower()
            if tag_lower == "!series_title":
                current_series.title = value
            elif tag_lower == "!series_summary":
                if current_series.summary:
                    current_series.summary += "\n" + value
                else:
                    current_series.summary = value
            elif tag_lower == "!series_overall_design":
                if current_series.overall_design:
                    current_series.overall_design += "\n" + value
                else:
                    current_series.overall_design = value
            elif tag_lower == "!series_sample_id":
                if value and value not in current_series.sample_ids:
                    current_series.sample_ids.append(value)
            continue

        # Sample metadata lines
        if current_sample is not None and tag.lower().startswith("!sample_"):
            tag_lower = tag.lower()

            if tag_lower == "!sample_title":
                current_sample.title = value
            elif tag_lower.startswith("!sample_supplementary_file"):
                current_sample.protocols.setdefault("supplementary_files", []).append(value)
            elif tag_lower.startswith("!sample_characteristics"):
                suffix = tag_lower[len("!sample_characteristics"):]
                if suffix.startswith("_") and suffix[1:] != "ch1":
                    ch_suffix = suffix[1:]
                    if ":" in value:
                        ckey, _, cval = value.partition(":")
                        clean_key = f"{ckey.strip().lower()}_{ch_suffix}"
                        current_sample.characteristics.setdefault(clean_key, []).append(cval.strip())
                    else:
                        current_sample.characteristics.setdefault(f"characteristics_{ch_suffix}", []).append(value)
                else:
                    if ":" in value:
                        ckey, _, cval = value.partition(":")
                        clean_key = ckey.strip().lower()
                        clean_val = cval.strip()
                        current_sample.characteristics.setdefault(clean_key, []).append(clean_val)
                    else:
                        current_sample.characteristics.setdefault("_free_text", []).append(value)
            else:
                proto_key = _normalize_protocol_key(tag)
                if proto_key:
                    current_sample.protocols.setdefault(proto_key, []).append(value)
                elif tag_lower in {"!sample_source_name", "!sample_source_name_ch1"}:
                    current_sample.source_name = value
                elif tag_lower in {"!sample_organism", "!sample_organism_ch1"}:
                    current_sample.organism = value
                elif tag_lower in {"!sample_taxid", "!sample_taxid_ch1"}:
                    current_sample.taxid = value
                elif tag_lower in {"!sample_molecule", "!sample_molecule_ch1"}:
                    current_sample.molecule = value
                elif tag_lower == "!sample_library_strategy":
                    current_sample.library_strategy = value
                elif tag_lower == "!sample_library_source":
                    current_sample.library_source = value
                elif tag_lower == "!sample_library_selection":
                    current_sample.library_selection = value
                elif tag_lower == "!sample_instrument_model":
                    current_sample.instrument_model = value
                else:
                    attr_name = tag_lower[len("!sample_"):]
                    current_sample.attributes.setdefault(attr_name, []).append(value)
            continue

    if current_sample is not None:
        yield current_sample
    if series_pending_yield and current_series is not None:
        yield current_series


def iter_records(path: str | Path) -> Iterator[SeriesRecord | SampleRecord]:
    """Stream SeriesRecord and SampleRecord objects from a GEO SOFT file (.soft or .soft.gz).

    Handles encoding transparently (UTF-8 with Windows-1252 fallback) and never
    raises UnicodeDecodeError. Fast-skips high-volume table rows.
    """
    with _open_line_stream(path) as lines:
        yield from _parse_lines(lines)


def parse_file(path: str | Path) -> list[SampleRecord]:
    """Read a SOFT file from disk and return all parsed SampleRecords."""
    return [r for r in iter_records(path) if isinstance(r, SampleRecord)]


def parse_soft(text: str) -> list[SampleRecord]:
    """Parse GEO SOFT text in-memory and return all parsed SampleRecords."""
    return [r for r in _parse_lines(iter(text.splitlines())) if isinstance(r, SampleRecord)]
