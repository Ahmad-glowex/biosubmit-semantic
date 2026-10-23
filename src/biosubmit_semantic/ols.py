"""Minimal client for the EBI Ontology Lookup Service (OLS4).

Used to resolve free-text entity mentions (e.g. "liver") to canonical
ontology identifiers WITHOUT letting an LLM invent IDs: the LLM may
normalize phrasing, but CURIE assignment comes strictly from this
deterministic API.

API docs: https://www.ebi.ac.uk/ols4/help
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

OLS_SEARCH_URL = "https://www.ebi.ac.uk/ols4/api/search"


def lookup_term(term: str, ontology: str = "uberon",
                size: int = 5, timeout: int = 15) -> list[dict]:
    """Search OLS for *term* within *ontology*.

    Returns a list of ``{"curie": ..., "label": ..., "ontology": ...}``.
    Raises ``RuntimeError`` on network/API failure so callers can decide
    how to degrade (the CLI treats OLS as optional).
    """
    params = urllib.parse.urlencode({
        "q": term,
        "ontology": ontology,
        "type": "class",
        "rows": size,
    })
    url = f"{OLS_SEARCH_URL}?{params}"
    request = urllib.request.Request(
        url, headers={"Accept": "application/json",
                      "User-Agent": "biosubmit-semantic/0.1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # network errors, timeouts, bad JSON
        raise RuntimeError(f"OLS lookup failed for {term!r}: {exc}") from exc

    results = []
    for doc in payload.get("response", {}).get("docs", []):
        results.append({
            "curie": doc.get("curie"),
            "label": doc.get("label"),
            "ontology": doc.get("ontology_name"),
        })
    return results
