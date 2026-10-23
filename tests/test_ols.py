"""Tests for EBI OLS client, response parsing, error handling, and query sanitization."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import urllib.parse
import urllib.request

import pytest

from biosubmit_semantic import ols
from biosubmit_semantic.ols import OLSLookupError


@pytest.fixture(autouse=True)
def clear_ols_lru_cache() -> None:
    """Clear lru_cache between tests to prevent memoized responses across test cases."""
    ols.lookup.cache_clear()


def test_ols_lookup_resolves_obo_id_to_curie() -> None:
    """Mock urlopen returning OLS payload with obo_id; assert curie equals obo_id value."""
    fake_response = {
        "response": {
            "docs": [
                {
                    "obo_id": "UBERON:0002107",
                    "label": "liver",
                    "ontology_name": "uberon",
                }
            ]
        }
    }
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value.read.return_value = json.dumps(fake_response).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=mock_cm) as mock_urlopen:
        hits = ols.lookup("liver", ontologies=("uberon",))
        assert len(hits) == 1
        assert hits[0]["curie"] == "UBERON:0002107"
        assert hits[0]["label"] == "liver"
        assert hits[0]["ontology_name"] == "uberon"
        mock_urlopen.assert_called_once()


def test_ols_lookup_zero_docs_returns_empty_list() -> None:
    """Mock empty docs response; assert empty list is returned."""
    fake_response = {"response": {"docs": []}}
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value.read.return_value = json.dumps(fake_response).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=mock_cm):
        hits = ols.lookup("unknown_tissue_xyz", ontologies=("uberon",))
        assert hits == []


def test_ols_lookup_timeout_raises_ols_lookup_error() -> None:
    """Mock timeout error; assert OLSLookupError is raised without leaking socket traces."""
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
        with pytest.raises(OLSLookupError) as exc_info:
            ols.lookup("kidney", ontologies=("uberon",))
        assert "OLS lookup failed" in str(exc_info.value)


def test_ols_lookup_placeholder_skips_network_call() -> None:
    """Placeholder input 'N/A' returns [] immediately with urlopen NOT called."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        for placeholder in ("N/A", "na", "unknown", "tbd", "none", "-"):
            hits = ols.lookup(placeholder, ontologies=("uberon",))
            assert hits == []
        mock_urlopen.assert_not_called()


def test_ols_lookup_sanitizes_lucene_special_chars() -> None:
    """Lucene special chars like '+' and '/' in 'CD4+/CD8+' are sanitized before query."""
    fake_response = {
        "response": {
            "docs": [
                {
                    "obo_id": "CL:0000084",
                    "label": "T cell",
                    "ontology_name": "cl",
                }
            ]
        }
    }
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value.read.return_value = json.dumps(fake_response).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=mock_cm) as mock_urlopen:
        hits = ols.lookup("CD4+/CD8+", ontologies=("cl",))
        assert not isinstance(hits, Exception)
        assert len(hits) == 1
        assert hits[0]["curie"] == "CL:0000084"

        # Inspect the query URL passed to urlopen
        assert mock_urlopen.called
        called_req = mock_urlopen.call_args[0][0]
        parsed_url = urllib.parse.urlparse(called_req.full_url)
        params = urllib.parse.parse_qs(parsed_url.query)
        # q param value should be 'CD4 CD8' without '+' operator from original term
        assert "q" in params
        assert params["q"][0] == "CD4 CD8"
