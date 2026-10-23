"""Command-line interface for biosubmit-semantic: ``biosubmit check <file>``.

Provides rule-based pre-flight metadata auditing for GEO SOFT files (.soft, .soft.gz),
with optional EBI OLS ontology grounding and SemanticAuditContext JSON export.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import context, ols, parser, rules
from .models import AuditReport, Finding, SampleRecord, SeriesRecord
from .vocab import is_junk_placeholder, is_sanctioned_missing_value


def _resolve_ols_terms(samples: list[SampleRecord], findings: list[Finding]) -> None:
    """Resolve unique tissue and cell-type values via EBI OLS and append findings."""
    unique_terms: dict[str, tuple[str, list[str]]] = {}
    target_keys = ("tissue", "cell_type", "cell type", "source_name")

    for s in samples:
        sid = getattr(s, "id", "") or "sample"
        chars = getattr(s, "characteristics", {}) or {}

        for key in target_keys:
            vals = s.get_characteristic(key) if hasattr(s, "get_characteristic") else chars.get(key, [])
            if isinstance(vals, str):
                vals = [vals]
            for v in vals:
                v_str = str(v).strip()
                if not v_str:
                    continue
                v_lower = v_str.lower()
                if (
                    v_lower in ols.KNOWN_PLACEHOLDERS
                    or is_junk_placeholder(v_str)
                    or is_sanctioned_missing_value(v_str)
                ):
                    continue
                if v_str not in unique_terms:
                    unique_terms[v_str] = (key, [sid])
                else:
                    if sid not in unique_terms[v_str][1]:
                        unique_terms[v_str][1].append(sid)

        s_source = getattr(s, "source_name", "")
        if s_source and isinstance(s_source, str):
            v_str = s_source.strip()
            if v_str:
                v_lower = v_str.lower()
                if not (
                    v_lower in ols.KNOWN_PLACEHOLDERS
                    or is_junk_placeholder(v_str)
                    or is_sanctioned_missing_value(v_str)
                ):
                    if v_str not in unique_terms:
                        unique_terms[v_str] = ("source_name", [sid])
                    else:
                        if sid not in unique_terms[v_str][1]:
                            unique_terms[v_str][1].append(sid)

    for term, (field_name, sids) in unique_terms.items():
        entity_id = ", ".join(sids) if sids else "global"
        try:
            try:
                hits = ols.lookup(term, ontologies=("uberon", "cl"))
            except TypeError:
                hits = ols.lookup(term)
        except Exception as exc:
            findings.append(
                Finding(
                    rule_id="OLS",
                    severity="WARNING",
                    category="ontology",
                    entity_id=entity_id,
                    message=f"OLS lookup failed for {field_name} '{term}': {exc}",
                )
            )
            continue

        if hits:
            top = hits[0]
            curie = top.get("curie") or top.get("obo_id") or ""
            label = top.get("label") or term
            findings.append(
                Finding(
                    rule_id="OLS",
                    severity="INFO",
                    category="ontology",
                    entity_id=entity_id,
                    message=f"{field_name} '{term}' -> {curie} ({label})",
                )
            )
        else:
            findings.append(
                Finding(
                    rule_id="OLS",
                    severity="WARNING",
                    category="ontology",
                    entity_id=entity_id,
                    message=f"{field_name} '{term}' matched no ontology term",
                )
            )


def cmd_check(args: argparse.Namespace) -> int:
    """Execute the check subcommand to audit a GEO SOFT metadata file."""
    file_path = getattr(args, "file", None) or getattr(args, "input", None)
    if not file_path:
        sys.stderr.write("Error: missing file argument.\n")
        return 2

    try:
        records = list(parser.iter_records(file_path))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        sys.stderr.write(f"Error reading {file_path}: {exc}\n")
        return 2

    series: SeriesRecord | None = None
    samples: list[SampleRecord] = []
    for rec in records:
        if isinstance(rec, SeriesRecord):
            if series is None:
                series = rec
        elif isinstance(rec, SampleRecord):
            samples.append(rec)

    if not samples:
        sys.stderr.write(f"Error: no ^SAMPLE records found in {file_path}\n")
        return 2

    findings = list(rules.run_all(series, samples))

    if getattr(args, "ols", False):
        _resolve_ols_terms(samples, findings)

    report = AuditReport(series=series, samples=samples, findings=findings)

    if getattr(args, "export_context", None):
        try:
            ctx_payload = context.build_semantic_audit_context(series, samples, findings)
            with open(args.export_context, "w", encoding="utf-8") as fh:
                json.dump(ctx_payload, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            sys.stderr.write(f"Error writing context to {args.export_context}: {exc}\n")
            return 2

    fmt = getattr(args, "format", "text") or "text"
    if fmt.lower() == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        err_noun = "error" if report.error_count == 1 else "errors"
        warn_noun = "warning" if report.warning_count == 1 else "warnings"
        print(f"{report.error_count} {err_noun}, {report.warning_count} {warn_noun}, {report.info_count} info")
        for f in report.findings:
            print(f"[{f.severity.upper()}] {f.rule_id} {f.entity_id}: {f.message}")

    return 1 if report.error_count > 0 else 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for biosubmit."""
    parser_obj = argparse.ArgumentParser(
        prog="biosubmit",
        description="Rule-based pre-flight auditor for GEO sample metadata (SOFT format).",
    )
    subparsers = parser_obj.add_subparsers(dest="subcommand", required=True)

    check_parser = subparsers.add_parser("check", help="Audit a GEO SOFT metadata file.")
    check_parser.add_argument(
        "file",
        help="Path to GEO SOFT file (.soft or .soft.gz)",
    )
    check_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format: 'text' (default) or 'json'.",
    )
    check_parser.add_argument(
        "--output",
        dest="format",
        choices=["text", "json"],
        help=argparse.SUPPRESS,
    )
    check_parser.add_argument(
        "--ols",
        action="store_true",
        default=False,
        help="Enable EBI OLS tissue/cell-term validation (network-backed, cached).",
    )
    check_parser.add_argument(
        "--export-context",
        dest="export_context",
        metavar="OUT_JSON",
        help="Export SemanticAuditContext JSON to specified path.",
    )
    check_parser.set_defaults(func=cmd_check)
    return parser_obj


def main(argv: list[str] | None = None) -> int:
    """Main CLI entrypoint returning integer exit status code."""
    ap = build_parser()
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else (0 if code is None else 2)

    func = getattr(args, "func", None)
    if func is not None:
        return func(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
