"""biosubmit-semantic: rule-based pre-flight auditor for GEO/SRA sample metadata.

This package implements the deterministic (rule-based) layer of the
BioSubmit-Semantic project: it parses GEO SOFT sample records, runs a set of
auditing rules over sample attributes, and can resolve ontology terms through
the EBI Ontology Lookup Service.

The Claude-powered semantic contradiction engine (protocol text vs. sample
table cross-checks) is the proposed research extension and plugs in at
``biosubmit_semantic.scope``.
"""

__version__ = "0.1.0"
