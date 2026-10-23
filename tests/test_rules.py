"""Tests for the rule-based auditing checks."""

from biosubmit_semantic import rules


def _sample(sid="GSM1", **kw):
    base = {"id": sid, "title": "t", "organism": "Homo sapiens",
            "characteristics": {}}
    base.update(kw)
    return base


def test_r1_missing_title_and_organism():
    findings = rules.check_required_fields([_sample(title="", organism="")])
    assert {f["rule"] for f in findings} == {"R1"}
    assert len(findings) == 2
    assert all(f["severity"] == "error" for f in findings)


def test_r1_clean_sample_no_findings():
    assert rules.check_required_fields([_sample()]) == []


def test_r2_rejects_uncontrolled_sex():
    s = _sample(characteristics={"sex": "M"})
    findings = rules.check_controlled_vocab([s])
    assert len(findings) == 1
    assert findings[0]["rule"] == "R2"


def test_r2_accepts_controlled_sex_case_insensitive():
    s = _sample(characteristics={"sex": "Female"})
    assert rules.check_controlled_vocab([s]) == []


def test_r3_duplicate_ids():
    findings = rules.check_duplicate_ids([_sample("GSM1"), _sample("GSM1")])
    assert len(findings) == 1
    assert findings[0]["rule"] == "R3"


def test_r3_unique_ids_clean():
    assert rules.check_duplicate_ids([_sample("GSM1"), _sample("GSM2")]) == []


def test_r4_empty_value():
    s = _sample(characteristics={"tissue": "  "})
    findings = rules.check_empty_values([s])
    assert len(findings) == 1
    assert findings[0]["severity"] == "warning"


def test_r5_placeholder():
    s = _sample(characteristics={"tissue": "N/A"})
    findings = rules.check_placeholders([s])
    assert len(findings) == 1
    assert findings[0]["rule"] == "R5"


def test_run_all_aggregates():
    samples = [_sample("GSM1", title=""),
               _sample("GSM1", characteristics={"sex": "M"})]
    findings = rules.run_all(samples)
    rule_ids = {f["rule"] for f in findings}
    assert {"R1", "R2", "R3"} <= rule_ids
