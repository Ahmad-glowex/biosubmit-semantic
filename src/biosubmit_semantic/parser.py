"""Parse GEO SOFT-format sample records into structured dicts.

Supported input: the ``^SAMPLE`` blocks of a GEO SOFT file, specifically the
``!Sample_title``, ``!Sample_organism`` and ``!Sample_characteristics`` lines::

    ^SAMPLE = GSM123456
    !Sample_title = liver rep1
    !Sample_organism = Homo sapiens
    !Sample_characteristics = tissue: liver
    !Sample_characteristics = sex: male

Each sample becomes::

    {"id": "GSM123456", "title": "liver rep1",
     "organism": "Homo sapiens",
     "characteristics": {"tissue": "liver", "sex": "male"}}
"""

from __future__ import annotations


def parse_soft(text: str) -> list[dict]:
    """Parse GEO SOFT text, returning one dict per ``^SAMPLE`` block."""
    samples: list[dict] = []
    current: dict | None = None

    def flush() -> None:
        if current is not None:
            samples.append(current)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("^SAMPLE"):
            flush()
            sample_id = line.split("=", 1)[1].strip()
            current = {"id": sample_id, "title": "", "organism": "",
                       "characteristics": {}}
        elif current is not None and line.startswith("!Sample_title"):
            current["title"] = line.split("=", 1)[1].strip()
        elif current is not None and line.startswith("!Sample_organism"):
            current["organism"] = line.split("=", 1)[1].strip()
        elif current is not None and line.startswith("!Sample_characteristics"):
            kv = line.split("=", 1)[1].strip()
            if ":" in kv:
                key, _, value = kv.partition(":")
                current["characteristics"][key.strip().lower()] = value.strip()
            else:
                # Free-text characteristic without a key; keep it verbatim.
                current["characteristics"].setdefault("_free_text", []).append(kv)
    flush()
    return samples


def parse_file(path: str) -> list[dict]:
    """Read a SOFT file from disk and parse it."""
    with open(path, encoding="utf-8") as fh:
        return parse_soft(fh.read())
