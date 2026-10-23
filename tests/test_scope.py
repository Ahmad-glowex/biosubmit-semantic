"""Tests for the scope-scaffolding logic (no network needed)."""

from biosubmit_semantic.scope import classify_mention, tier_warning


def test_in_scope_mention():
    assert classify_mention("24h", {"24h", "48h"}) == "in_scope"


def test_out_of_scope_mention():
    # Text mentions 2h/6h/12h but the accession only has 24h samples.
    assert classify_mention("2h", {"24h"}) == "out_of_scope"


def test_case_insensitive():
    assert classify_mention("Liver", {"liver"}) == "in_scope"


def test_tiering():
    assert tier_warning("genotype mismatch", "in_scope") == "Definite Conflict"
    assert (tier_warning("missing timepoint", "out_of_scope")
            == "Potential Out-of-Scope Mention")
