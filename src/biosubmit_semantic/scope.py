"""Scope-scaffolding for cross-modal semantic checks.

Background (from the project design review): protocol/methods text pasted
into a GEO submission often describes a LARGER study than the accession
being uploaded (e.g. text mentions 2h/6h/12h/24h cohorts, but this Series
only contains the 24h samples). A naive text-vs-table contradiction check
would flood such compliant partial submissions with false alerts.

The rule below is the deterministic part of the mitigation: it classifies
whether a condition mention plausibly belongs to the current accession's
declared sample set. The Claude-powered semantic layer (proposed research)
builds on this by doing the same classification with full protocol context
and by tiering every warning as Definite Conflict vs Potential
Out-of-Scope Mention.
"""

from __future__ import annotations


def classify_mention(mention: str, sample_conditions: set[str]) -> str:
    """Classify a condition *mention* from protocol text.

    Returns ``"in_scope"`` if the mention matches a condition declared in
    the accession's sample table, otherwise ``"out_of_scope"``.

    This is intentionally conservative: anything not clearly declared is
    treated as out-of-scope rather than flagged as an error, which is what
    keeps the false-positive rate down on partial-series submissions.
    """
    normalized = mention.strip().lower()
    declared = {c.strip().lower() for c in sample_conditions}
    if normalized in declared:
        return "in_scope"
    return "out_of_scope"


def tier_warning(conflict_type: str, scope: str) -> str:
    """Tier a cross-modal warning by confidence.

    - Definite Conflict: direct contradiction inside the accession scope
      (e.g. genotype mismatch between text and table).
    - Potential Out-of-Scope Mention: text mentions something not in the
      accession; likely collateral from a larger study, not an error.
    """
    if scope == "in_scope":
        return "Definite Conflict"
    return "Potential Out-of-Scope Mention"
