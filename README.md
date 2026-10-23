# biosubmit-semantic

Rule-based pre-flight auditor for GEO sample metadata (SOFT format).

`biosubmit-semantic` is the deterministic validation layer for NCBI Gene Expression Omnibus (GEO) metadata submissions. It validates study- and sample-level metadata against MINSEQE guidelines, INSDC controlled vocabularies, and experimental cohort structure before submission to public repositories.

> **Scope Notice:** This tool supports **NCBI GEO SOFT format only** (`.soft` and `.soft.gz`). It does **NOT** audit NCBI SRA XML or FASTQ submission packages, which use distinct schemas.

---

## What This Package Does

- **Streaming SOFT Parser:** Parses `.soft` and `.soft.gz` files line-by-line with automatic UTF-8 / Windows-1252 fallback. Preserves multi-valued characteristic tags, joins multi-line series narratives, and fast-skips multi-megabyte expression tables (`!sample_table_begin` to `!sample_table_end`) without parsing overhead or memory exhaustion.
- **Deterministic Rules Engine:** Audits records across four strict quality tiers:
  - **Syntax & Record Integrity:** Duplicate identifiers and malformed attribute entries.
  - **MINSEQE & Mandatory Fields:** Core sample declarations (title, organism, source, molecule, HTS instrument/strategy pairing).
  - **Controlled Vocabularies:** INSDC library strategies, sources, NCBI molecule types, biological sex, and rejection of junk placeholder text while honoring sanctioned missing-value tokens (`not applicable`, `not collected`, etc.).
  - **Cohort QC & Experimental Design:** Schema parity across samples and singleton replicate detection ($n=1$).
- **Optional EBI OLS Grounding:** Validates unique tissue and cell-type values against the EBI Ontology Lookup Service (OLS4; UBERON and CL ontologies) with query sanitization and local LRU caching.
- **SemanticAuditContext Export:** Generates structured JSON context aggregating study narratives, sample factor matrices, and deterministic findings for handoff to downstream research pipelines.

---

## What This Is NOT

- **No LLM inference in this package:** The Claude-powered semantic contradiction layer (evaluating free-text protocols against sample matrix declarations) is **PROPOSED** research under a grant application. It is not implemented here.
- **Handoff schema only:** The `--export-context` command exports structured payloads designed for that future research layer; no machine learning inference or API calls to foundation model providers take place within this codebase.
- **Not for SRA packages:** This package strictly targets NCBI GEO SOFT specifications. It does not validate SRA experiment/run XML or BioSample XML schemas.

---

## Installation

Requires Python 3.10+.

```bash
pip install -e .
```

---

## Usage

### 1. Basic Metadata Audit (Text Output)

```bash
biosubmit check GSE123456_family.soft
```

Outputs a grouped diagnostic summary followed by line-by-line findings:

```text
0 errors, 1 warning, 0 info
[WARNING] R402 GSM123456: Sample 'GSM123456' represents a singleton replicate (n=1) with characteristic signature [genotype=WT, treatment=vehicle]. Experimental design lacks replication.
```

Exit codes:
- `0`: Clean audit (no `ERROR` findings; warnings/info permitted).
- `1`: Validation failed (one or more `ERROR` findings present).
- `2`: File not found, I/O error, or unparseable input.

### 2. Machine-Readable JSON Output

```bash
biosubmit check GSE123456_family.soft --format json
```

Outputs the full `AuditReport` payload containing study metadata, sample records, diagnostic findings, and summary statistics.

### 3. Compressed SOFT Files (.soft.gz)

Decompression is handled transparently:

```bash
biosubmit check GSE123456_family.soft.gz
```

### 4. EBI OLS Ontology Grounding

Resolve declared tissue and cell-type terms against EBI OLS (UBERON / CL) without failing the audit if network is unavailable:

```bash
biosubmit check GSE123456_family.soft --ols
```

Example finding:
```text
[INFO] OLS GSM123456: tissue 'liver' -> UBERON:0002107 (liver)
```

### 5. Export Semantic Context

Export structured context for downstream semantic evaluation:

```bash
biosubmit check GSE123456_family.soft --export-context audit_context.json
```

---

## Rule Reference Table

| Rule ID | Category | Severity | Description |
|---|---|---|---|
| **R101** | Syntax | ERROR | Duplicate entity IDs across series or samples |
| **R102** | Syntax | WARNING | Malformed characteristic keys or empty values |
| **R201** | MINSEQE | ERROR | Missing required sample title |
| **R202** | MINSEQE | ERROR | Missing required organism specification |
| **R203** | MINSEQE | WARNING | Missing recommended `source_name` (tissue/cell description) |
| **R204** | MINSEQE | ERROR | Missing required molecule type |
| **R205** | MINSEQE | WARNING | HTS completeness: missing `instrument_model` when sequencing declared, or missing `library_strategy` when molecule indicates HTS |
| **R301** | Controlled Vocab | ERROR | Molecule type not in NCBI controlled vocabulary |
| **R302** | Controlled Vocab | ERROR | Library strategy not in INSDC standard |
| **R303** | Controlled Vocab | WARNING | Library source not in INSDC standard |
| **R304** | Controlled Vocab | WARNING | Biological sex not in `CONTROLLED_SEX` standard |
| **R305** | Controlled Vocab | WARNING | Disallowed junk placeholders (`tbd`, `todo`, etc.; sanctioned missing tokens permitted) |
| **R401** | Experimental Design | WARNING | Schema parity: characteristic keys present in some samples but absent in others |
| **R402** | Experimental Design | WARNING | Singleton replicate: samples with unique characteristic signatures ($n=1$) lacking biological replication |

---

## Running Tests

Run the full pytest suite with no network requirements (all external endpoints mocked):

```bash
python -m pytest tests/ -q
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
