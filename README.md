# biosubmit-semantic

Rule-based pre-flight auditor for functional genomics sample metadata
(GEO/SRA, SOFT format). This is the **deterministic foundation layer** of the
BioSubmit-Semantic project: it parses GEO SOFT sample records and runs a set
of auditing rules over sample attributes — required fields, controlled
vocabularies, duplicate ids, empty/placeholder values — with optional
ontology resolution through the EBI Ontology Lookup Service (OLS).

The Claude-powered **semantic contradiction engine** (protocol text vs.
sample-table cross-checks, scope-aware warning tiers) is the proposed
research extension and plugs in at `biosubmit_semantic/scope.py`.

## Install

```bash
pip install -e .
```

## Usage

```bash
# Audit a GEO SOFT file (text report, exit 1 if errors found)
biosubmit check examples/sample_soft.txt

# JSON output
biosubmit check examples/sample_soft.txt --output json

# Also resolve tissue terms against EBI OLS (needs network)
biosubmit check examples/sample_soft.txt --ols
```

## Rules

| ID  | Severity | Check |
|-----|----------|-------|
| R1  | error    | required fields present (title, organism) |
| R2  | error    | controlled vocabulary (e.g. `sex: male/female/unknown`) |
| R3  | error    | duplicate sample ids |
| R4  | warning  | empty characteristic values |
| R5  | warning  | placeholder junk values (`N/A`, `unknown`, `TBD`, …) |
| OLS | warning  | tissue term with no UBERON match (with `--ols`) |

## Tests

```bash
python -m pytest tests/ -q
```

## Design notes

- **No LLM-invented ontology IDs**: free-text mentions are normalized by
  models, but CURIE assignment comes strictly from the deterministic EBI
  OLS API (`ols.py`).
- **Scope-aware by design** (`scope.py`): protocol text often describes a
  larger study than the accession being uploaded. Mentions that don't match
  the accession's declared sample set are classified `out_of_scope` and
  tiered as *Potential Out-of-Scope Mention* instead of errors — this is
  what keeps false positives down on partial-series submissions.

## License

MIT — see [LICENSE](LICENSE).
