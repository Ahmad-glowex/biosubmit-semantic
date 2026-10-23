"""Tests for the GEO SOFT parser."""

from biosubmit_semantic.parser import parse_soft

SAMPLE_SOFT = """\
^SAMPLE = GSM123456
!Sample_title = liver rep1
!Sample_organism = Homo sapiens
!Sample_characteristics = tissue: liver
!Sample_characteristics = sex: male
^SAMPLE = GSM123457
!Sample_title = liver rep2
!Sample_organism = Homo sapiens
!Sample_characteristics = tissue: liver
!Sample_characteristics = sex: Female
"""


def test_parses_two_samples():
    samples = parse_soft(SAMPLE_SOFT)
    assert len(samples) == 2
    assert samples[0]["id"] == "GSM123456"
    assert samples[1]["id"] == "GSM123457"


def test_characteristics_lowercased_keys():
    samples = parse_soft(SAMPLE_SOFT)
    assert samples[0]["characteristics"] == {"tissue": "liver", "sex": "male"}
    # Value case is preserved; keys are normalized.
    assert samples[1]["characteristics"]["sex"] == "Female"


def test_empty_input_gives_no_samples():
    assert parse_soft("") == []
    assert parse_soft("^SERIES = GSE1\n") == []


def test_free_text_characteristic_kept():
    text = ("^SAMPLE = GSM1\n"
            "!Sample_title = t\n"
            "!Sample_characteristics = just some notes\n")
    samples = parse_soft(text)
    assert samples[0]["characteristics"]["_free_text"] == ["just some notes"]
