"""Command-line interface: ``biosubmit check <file.soft>``."""

from __future__ import annotations

import argparse
import json
import sys

from . import ols, parser, rules


def _print_text(findings: list[dict]) -> None:
    if not findings:
        print("OK: no issues found.")
        return
    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    print(f"Found {errors} error(s), {warnings} warning(s):")
    for f in findings:
        print(f"  [{f['severity'].upper()}] {f['rule']} {f['sample']}: "
              f"{f['message']}")


def cmd_check(args: argparse.Namespace) -> int:
    try:
        samples = parser.parse_file(args.input)
    except OSError as exc:
        print(f"error: cannot read {args.input}: {exc}", file=sys.stderr)
        return 2
    if not samples:
        print("error: no ^SAMPLE records found in input", file=sys.stderr)
        return 2

    findings = rules.run_all(samples)

    if args.ols:
        # Optional: resolve tissue terms through EBI OLS (deterministic).
        for s in samples:
            tissue = s.get("characteristics", {}).get("tissue")
            if tissue:
                try:
                    hits = ols.lookup_term(tissue)
                except RuntimeError as exc:
                    print(f"warning: {exc}", file=sys.stderr)
                    continue
                if not hits:
                    findings.append({
                        "rule": "OLS", "severity": "warning",
                        "sample": s["id"],
                        "message": f"tissue '{tissue}' matched no UBERON term",
                    })

    if args.output == "json":
        print(json.dumps({"samples": len(samples), "findings": findings},
                         indent=2))
    else:
        _print_text(findings)

    has_errors = any(f["severity"] == "error" for f in findings)
    return 1 if has_errors else 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="biosubmit",
        description="Rule-based pre-flight auditor for GEO/SRA sample "
                    "metadata (SOFT format).")
    sub = ap.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="audit a GEO SOFT file")
    check.add_argument("input", help="path to a GEO SOFT file")
    check.add_argument("--ols", action="store_true",
                       help="also resolve tissue terms via EBI OLS "
                            "(needs network)")
    check.add_argument("--output", choices=["text", "json"], default="text",
                       help="output format (default: text)")
    check.set_defaults(func=cmd_check)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
