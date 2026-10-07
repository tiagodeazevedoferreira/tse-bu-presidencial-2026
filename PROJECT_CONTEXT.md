# Project Context — TSE BU Presidencial 2026

> **Purpose:** persistent handoff/context for future prompts. Read this file before changing the project. It is intended to let a new assistant continue the work without reconstructing the history from chat.

## 1. Project identity

Repository: `tiagodeazevedoferreira/tse-bu-presidencial-2026`
Branch of record: `main`
Objective: build a reproducible, auditable pipeline from the TSE 2026 Boletim de Urna (BU) open data for the **1st round** of the Brazilian presidential election, producing one row per electoral section for the 27 Brazilian UFs.

Official TSE dataset:
`https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna`

The project deliberately excludes `ZZ` (voting abroad) because the target is the 27 Brazilian UFs.

## 2. Target output

The final consolidated table must contain these columns, in this order:

1. SG_UF
2. CD_MUNICIPIO
3. NM_MUNICIPIO
4. NR_ZONA
5. NR_SECAO
6. NR_LOCAL_VOTACAO
7. NR_URNA_EFETIVADA
8. QT_APTOS
9. QT_COMPARECIMENTO
10. QT_ABSTENCOES
11. DT_ABERTURA
12. DT_ENCERRAMENTO
13. DT_EMISSAO_BU
14. DT_BU_RECEBIDO
15. VOTOS_FLAVIO_BOLSONARO
16. VOTOS_LULA
17. VOTOS_BRANCO_PRES
18. VOTOS_NULO_PRES
19. TOTAL_VOTOS_PRES

Business definition:
- `CD_CARGO_PERGUNTA = 1` = presidential contest to process.
- Flávio Bolsonaro = vote code `22`.
- Lula = vote code `13`.
- Branco = `95`.
- Nulo = `96`.
- `TOTAL_VOTOS_PRES` is the sum of the four requested components (22 + 13 + 95 + 96). It is **not** the sum of every presidential candidate unless the requirements are later changed.

## 3. Intended repository structure

```
README.md
requirements.txt
.gitignore
.github/
  workflows/
    ci.yml
    validate_rr.yml
scripts/
  download_bu.py
  process_bu.py
  generate_table.py
data/
  raw/
    .gitkeep
  processed/
    .gitkeep
examples/
  caroebe_rr.md
tests/
  test_generate_table.py
PROJECT_CONTEXT.md
```

Raw ZIPs and generated data are ignored by Git. Do not commit the TSE ZIP archives or accidentally commit temporary SQLite files.

## 4. Pipeline architecture

### Download
`scripts/download_bu.py`
- Uses the official TSE CKAN API.
- Dataset ID: `resultados-2026-boletim-de-urna`.
- Finds resources named like `<UF> - Boletim de Urna - Primeiro turno`.
- Downloads the UF ZIP to `data/raw/<UF>/`.
- Uses streaming download with `tqdm`.
- Supports `--uf RR`, a specific UF, or `--uf ALL`.
- Supports `--force`.

### Processing
`scripts/process_bu.py`
- Python/pandas.
- Reads ZIP-contained CSVs directly with `zipfile`.
- Uses `sep=";"`, `encoding="latin1"`, `dtype=str`, chunk size 100,000.
- Filters `CD_CARGO_PERGUNTA == "1"`.
- Aggregates one row per section using SQLite as a disk-backed intermediate store.
- Calculates the four requested vote components from `NR_VOTAVEL` and `QT_VOTOS`.
- Exports per-UF CSV using `;` and `utf-8-sig`.
- Supports `--download` and `--uf ALL`.

### Consolidation
`scripts/generate_table.py`
- Reads per-UF processed CSVs in chunks.
- Validates chunks.
- Writes the final consolidated CSV incrementally, avoiding loading all UFs into RAM.
- Produces a Markdown summary.

## 5. Current technical state

The normal CI has been run five times during initial construction:
- #1 initial structure — failed
- #2 download pipeline — failed
- #3 processing pipeline — failed
- #4 generate table — passed
- #5 streaming/memory-safe consolidation — passed

The failures above were during incremental construction, not evidence that the final architecture is broken.

A real end-to-end RR workflow was then added:
`.github/workflows/validate_rr.yml`
It downloads RR from TSE, processes it, consolidates it, validates the output and uploads RR artifacts.

### First real-data failure

The first RR execution reached the actual TSE CSV and failed with:

`ValueError: bweb_1t_RR_051020261403.csv: colunas obrigatórias ausentes: ['TOTAL_VOTOS_PRES', 'VOTOS_BRANCO_PRES', 'VOTOS_FLAVIO_BOLSONARO', 'VOTOS_LULA', 'VOTOS_NULO_PRES']`

Root cause: the processor incorrectly treated five **derived output fields** as if they were raw TSE source columns.

### Fix already applied

Commit:
`9f6391f9f7fa6ef286b1bf738cd07cce0dee606d`

`process_bu.py` now has a separate `REQUIRED_RAW` set. It requires source fields only, while the five vote/output columns are derived during processing.

**Important:** the next action is to inspect the workflow run triggered by this fix. Do not declare RR validated until the workflow is green and its logs confirm actual output.

## 6. Known validated source facts

- TSE publishes the 2026 BU dataset by UF for 1st and 2nd rounds.
- The resource naming pattern observed for RR is:
  `bweb_1t_RR_051020261403.zip`
- The RR ZIP contains:
  `bweb_1t_RR_051020261403.csv`
- The real source file uses the expected semicolon-separated BU format sufficiently to reach schema validation.
- Candidate codes used by this project were checked against TSE's 2026 candidate information: Flávio Bolsonaro = 22; Lula = 13.

## 7. Non-negotiable data rules

1. Never fabricate electoral rows.
2. Never infer missing sections from another source unless a new explicit requirement authorizes it.
3. One row represents one section key:
   `SG_UF + CD_MUNICIPIO + NR_ZONA + NR_SECAO`.
4. Preserve source metadata from the BU.
5. Vote counts must originate from raw `NR_VOTAVEL` + `QT_VOTOS`.
6. Filter presidential contest using `CD_CARGO_PERGUNTA = 1`.
7. Do not silently accept schema changes. Add explicit aliases and validation.
8. Do not commit raw TSE ZIPs.
9. Avoid loading the entire national dataset into memory.
10. Do not claim the national dataset is complete until all 27 UFs have actually processed successfully.

## 8. Known implementation risks to investigate

### A. Duplicate/upsert semantics
The SQLite implementation currently uses the section key as primary key and adds vote fields on conflict. This was designed to handle chunk/file aggregation, but it must be validated against the actual TSE archive structure.

**Critical:** if a source archive ever contains duplicated records representing the same BU rather than complementary rows, additive upsert would double-count votes. Before national production, verify that each section/candidate record occurs exactly as expected.

### B. Metadata consistency
The processor takes the first metadata value in each section group. Validate that repeated metadata fields are consistent inside a section.

### C. Complete source schema
The RR run exposed the first incorrect assumption. Continue using real TSE files to validate every required field before running all UFs.

### D. Final Markdown
The current Markdown output is a summary, not necessarily a full Markdown table containing every national section. If the requirement is interpreted as a full Markdown view, redesign this deliberately rather than generating an enormous memory-heavy Markdown file.

### E. Large final CSV
The complete national CSV may be too large for normal GitHub source storage. Preferred delivery is GitHub Actions artifact and/or GitHub Release asset, while keeping source code and reproducibility in Git.

## 9. Testing requirements

Current CI:
`.github/workflows/ci.yml`
- Python 3.12
- installs `requirements.txt`
- runs `python -m pytest -q`

Existing tests:
`tests/test_generate_table.py`
- valid total passes;
- incorrect total raises `ValueError`.

Required future tests should include:
- raw schema validation;
- candidate-code aggregation;
- one-section aggregation;
- duplicate-section behavior;
- total calculation;
- encoding/separator;
- output column order;
- Caroebe/RR integration validation;
- no duplicated section keys in final output.

## 10. Exact next steps

### Step 1 — RR re-run
Inspect the GitHub Actions run triggered by commit `9f6391f`.

If it fails:
- read the exact error;
- inspect/validate the real source schema;
- make the smallest explicit code correction;
- rerun CI and RR validation.

If it passes:
- inspect reported RR section count;
- inspect Caroebe section count;
- inspect sample rows;
- inspect vote totals;
- inspect output artifact.

### Step 2 — strengthen validation
Before national processing, add automated checks for:
- duplicate section keys;
- non-negative vote counts;
- total formula;
- metadata consistency;
- expected UF code;
- numeric fields;
- absence of accidental double counting.

### Step 3 — RR example
Use the real generated RR data to populate/validate `examples/caroebe_rr.md`. Do not hardcode invented values.

### Step 4 — national workflow
Add a dedicated GitHub Actions workflow for all 27 UFs:
- download all 27 official 1st-round ZIPs;
- process incrementally;
- consolidate incrementally;
- run validation;
- upload final CSV + Markdown as artifacts;
- retain raw ZIPs only in the ephemeral runner.

### Step 5 — national quality control
Produce a summary per UF:
- sections processed;
- municipalities;
- total requested votes;
- duplicate count;
- validation status.

### Step 6 — final delivery
Only after all UFs pass:
- publish the national CSV as an artifact/release asset;
- retain reproducible scripts;
- document exact source snapshot/resource names and processing date;
- update README with final validation status.

## 11. Prompt continuation protocol

For any future prompt such as:
- "continue"
- "continue from here"
- "what next?"
- "execute the next step"

the assistant should:
1. Read `PROJECT_CONTEXT.md`.
2. Inspect the current `main` branch and latest GitHub Actions status.
3. Determine the first unfinished step in section 10.
4. Perform the next concrete action directly in GitHub when possible.
5. Do not repeat completed work.
6. Do not claim success without checking the resulting commit/workflow.
7. Update this context file whenever an important architectural decision, failure, correction, validation result, or completed milestone changes the project state.

## 12. Current checkpoint

**Checkpoint date:** 2026-10-07

**Last known code correction:** commit `9f6391f9f7fa6ef286b1bf738cd07cce0dee606d`.

**Current blocking task:** validate that correction against the real RR BU file.

**Do not proceed to all 27 UFs until RR end-to-end processing is green.**
