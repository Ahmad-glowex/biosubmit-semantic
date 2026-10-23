"""Client for the EBI Ontology Lookup Service (OLS4).

Provides deterministic resolution of biomedical terms (tissue, anatomy, cell type,
disease, taxon) to standard CURIE identifiers without model hallucination.

OLS4 Search API specifics:
- Ontology identifier is returned in 'obo_id' (e.g. 'UBERON:0002107') or 'short_form'.
- Search term must be sanitized of Solr/Lucene operators to avoid 15s hangs.
- Common missing/placeholder tokens are filtered locally without network overhead.
"""

from __future__ import annotations

import functools
import json
import re
import urllib.parse
import urllib.request

OLS_SEARCH_URL: str = "https://www.ebi.ac.uk/ols4/api/search"
DEFAULT_TIMEOUT: float = 5.0

# Supported canonical ontology namespaces
ONTOLOGY_ANATOMY: str = "uberon"
ONTOLOGY_CELL: str = "cl"
ONTOLOGY_DISEASE: str = "mondo"
ONTOLOGY_TAXON: str = "ncbitaxon"

# Disallowed placeholder values that indicate missing data; no network call needed
KNOWN_PLACEHOLDERS: frozenset[str] = frozenset({
    "n/a",
    "na",
    "unknown",
    "tbd",
    "todo",
    "none",
    "-",
    "--",
    "null",
    "?",
    "",
})

# Solr/Lucene reserved characters that trigger syntax errors or severe query hangs
_LUCENE_SPECIAL_CHARS: re.Pattern[str] = re.compile(r'[+\-=&|><!(){}\[\]^"~*?:/\\]')


class OLSLookupError(RuntimeError):
    """Raised when an OLS lookup fails due to network, timeout, or payload issues."""
    pass


def sanitize_query(term: str) -> str:
    """Strip or replace Lucene special characters with spaces and collapse whitespace."""
    cleaned = _LUCENE_SPECIAL_CHARS.sub(" ", term)
    return " ".join(cleaned.split())


def _fetch_ontology_docs(
    sanitized_term: str,
    ontology: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict]:
    """Execute a single ontology class search against the OLS4 API."""
    params = urllib.parse.urlencode({
        "q": sanitized_term,
        "ontology": ontology,
        "type": "class",
        "rows": 10,
    })
    url = f"{OLS_SEARCH_URL}?{params}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "biosubmit-semantic/0.2.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw_bytes = response.read()
            payload = json.loads(raw_bytes.decode("utf-8", errors="replace"))
    except Exception as exc:
        err = OLSLookupError(
            f"OLS lookup failed for query '{sanitized_term}' on ontology '{ontology}': {exc}"
        )
        err.__cause__ = None
        err.__context__ = None
        raise err

    response_block = payload.get("response")
    if not isinstance(response_block, dict):
        return []
    docs = response_block.get("docs")
    if not isinstance(docs, list):
        return []
    return docs


@functools.lru_cache(maxsize=1024)
def lookup(
    term: str,
    ontologies: tuple[str, ...] = ("uberon",),
) -> list[dict]:
    """Resolve a term across one or more ontologies using the EBI OLS4 search API.

    Args:
        term: Biomedical term to search (e.g. 'liver', 'CD4-positive T cell').
        ontologies: Tuple of target ontology prefixes (e.g. ('uberon', 'cl')).

    Returns:
        List of dicts with keys 'curie', 'label', 'ontology_name'.
        Returns [] if the term is empty/placeholder or if zero hits are found.

    Raises:
        OLSLookupError: On network, HTTP, or JSON decode failure (no leaked tracebacks).
    """
    raw_lower = term.strip().lower()
    if not raw_lower or raw_lower in KNOWN_PLACEHOLDERS:
        return []

    sanitized = sanitize_query(term)
    if not sanitized or sanitized.lower() in KNOWN_PLACEHOLDERS:
        return []

    merged: list[dict] = []
    seen_curies: set[str] = set()

    for ont in ontologies:
        ont_clean = ont.strip().lower()
        if not ont_clean:
            continue

        docs = _fetch_ontology_docs(sanitized, ont_clean, timeout=DEFAULT_TIMEOUT)
        for doc in docs:
            # OLS4 search API returns ontology ID in 'obo_id' or 'short_form', NOT 'curie'
            curie = doc.get("obo_id") or doc.get("short_form")
            if not curie:
                continue

            if curie in seen_curies:
                continue
            seen_curies.add(curie)

            label = doc.get("label") or ""
            ontology_name = doc.get("ontology_name") or ont_clean

            merged.append({
                "curie": curie,
                "label": label,
                "ontology_name": ontology_name,
                "ontology": ontology_name,
            })

    return merged


def lookup_term(
    term: str,
    ontology: str = "uberon",
    size: int = 5,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict]:
    """Single-ontology lookup wrapper for backward compatibility."""
    return lookup(term, (ontology,))
