"""Rule-based auditing checks over parsed GEO sample records.

Each rule is a function ``(samples) -> list[Finding]``. A finding is a dict::

    {"rule": "R2", "severity": "error" | "warning",
     "sample": "GSM123", "message": "..."}

Rules implemented:
- R1: required fields present (id, title, organism)
- R2: controlled vocabulary for known attributes (e.g. sex)
- R3: duplicate sample ids
- R4: empty characteristic values
- R5: placeholder junk values ("n/a", "unknown", "tbd", ...)
"""

from __future__ import annotations

CONTROLLED_VOCAB = {
    "sex": {"male", "female", "unknown", "not applicable"},
}

PLACEHOLDER_VALUES = {"n/a", "na", "unknown", "tbd", "todo", "none", "-", "--",
                      "null", "?"}


def _finding(rule: str, severity: str, sample: str, message: str) -> dict:
    return {"rule": rule, "severity": severity, "sample": sample,
            "message": message}


def check_required_fields(samples: list[dict]) -> list[dict]:
    """R1: every sample needs id, title and organism."""
    findings = []
    for s in samples:
        sid = s.get("id") or "<unknown>"
        for field in ("title", "organism"):
            if not s.get(field):
                findings.append(_finding(
                    "R1", "error", sid,
                    f"missing required field: {field}"))
    return findings


def check_controlled_vocab(samples: list[dict]) -> list[dict]:
    """R2: known attributes must use controlled vocabulary values."""
    findings = []
    for s in samples:
        sid = s.get("id") or "<unknown>"
        for attr, allowed in CONTROLLED_VOCAB.items():
            value = s.get("characteristics", {}).get(attr)
            if value is not None and value.lower() not in allowed:
                findings.append(_finding(
                    "R2", "error", sid,
                    f"attribute '{attr}' has non-controlled value "
                    f"'{value}' (allowed: {sorted(allowed)})"))
    return findings


def check_duplicate_ids(samples: list[dict]) -> list[dict]:
    """R3: sample ids must be unique."""
    findings = []
    seen: dict[str, int] = {}
    for s in samples:
        sid = s.get("id") or "<unknown>"
        seen[sid] = seen.get(sid, 0) + 1
    for sid, count in seen.items():
        if count > 1:
            findings.append(_finding(
                "R3", "error", sid,
                f"duplicate sample id appears {count} times"))
    return findings


def check_empty_values(samples: list[dict]) -> list[dict]:
    """R4: characteristic values must not be empty."""
    findings = []
    for s in samples:
        sid = s.get("id") or "<unknown>"
        for key, value in s.get("characteristics", {}).items():
            if isinstance(value, str) and not value.strip():
                findings.append(_finding(
                    "R4", "warning", sid,
                    f"characteristic '{key}' has an empty value"))
    return findings


def check_placeholders(samples: list[dict]) -> list[dict]:
    """R5: flag placeholder junk values."""
    findings = []
    for s in samples:
        sid = s.get("id") or "<unknown>"
        for key, value in s.get("characteristics", {}).items():
            if isinstance(value, str) and value.strip().lower() in PLACEHOLDER_VALUES:
                findings.append(_finding(
                    "R5", "warning", sid,
                    f"characteristic '{key}' looks like a placeholder "
                    f"('{value}')"))
    return findings


ALL_RULES = [
    check_required_fields,
    check_controlled_vocab,
    check_duplicate_ids,
    check_empty_values,
    check_placeholders,
]


def run_all(samples: list[dict]) -> list[dict]:
    """Run every rule over the samples, returning all findings."""
    findings: list[dict] = []
    for rule in ALL_RULES:
        findings.extend(rule(samples))
    return findings
