# Project Context — TSE BU Presidencial 2026

> Persistent handoff for continuing this repository. The repository and its latest GitHub Actions results are the source of truth.

## 1. Project identity

Repository: `tiagodeazevedoferreira/tse-bu-presidencial-2026`  
Branch of record: `main`  
Objective: reproducible, auditable processing of official TSE 2026 Boletim de Urna data for the **1st round**, producing one row per electoral section for the 27 Brazilian UFs.

Official dataset:
`https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna`

Exclude `ZZ` (abroad).

## 2. Target output

Columns, in order:

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

Business rules:
- `CD_CARGO_PERGUNTA = 1` = presidential contest.
- Flávio Bolsonaro = `22`.
- Lula = `13`.
- Branco = `95`.
- Nulo = `96`.
- `TOTAL_VOTOS_PRES = 22 + 13 + 95 + 96` only; it is not all presidential candidates.
- Section key: `SG_UF + CD_MUNICIPIO + NR_ZONA + NR_SECAO`.

## 3. Repository architecture

```
README.md
requirements.txt
.gitignore
.github/workflows/
  ci.yml
  validate_rr.yml
  national.yml
scripts/
  download_bu.py
  process_bu.py
  generate_table.py
data/raw/.gitkeep
data/processed/.gitkeep
examples/caroebe_rr.md
tests/
PROJECT_CONTEXT.md
AI_CONTINUATION.md
```

Raw ZIPs and generated data are ignored. Never commit raw TSE ZIPs.

## 4. Pipeline

### Download
`scripts/download_bu.py`
- Uses official TSE CKAN API.
- Downloads the first-round resource for a selected UF.
- Streams the ZIP to `data/raw/<UF>/`.
- Supports one UF or ALL.

### Processing
`scripts/process_bu.py`
- Reads ZIP-contained CSV with `sep=";"`, `encoding="latin1"`, `dtype=str`, chunks of 100,000.
- Filters `CD_CARGO_PERGUNTA == 1`.
- The current 2026 source exposes `DT_EMISSAO_BU` and `DT_BU_RECEBIDO` as datetime fields; `HH_EMISSAO_BU` and `HH_BU_RECEBIDO` are derived deterministically from those timestamps for analytical compatibility.
- Uses SQLite as disk-backed aggregation.
- Derives only requested vote components from `NR_VOTAVEL` and `QT_VOTOS`.
- Exports one row per section as `; / utf-8-sig`.
- Explicit aliases exist for known source variants.

### Consolidation
`scripts/generate_table.py`
- Reads per-UF outputs in chunks.
- Uses a disk-backed SQLite key table to detect duplicate section keys across chunks and UFs.
- Validates UF identity, key completeness, non-negative votes/electorate, requested votes <= turnout, electorate reconciliation, and total formula.
- Writes the national CSV incrementally.
- Writes a Markdown summary by UF.

## 5. Real-data validation status

RR end-to-end validation is green. The RR workflow validates:
- required output schema;
- non-empty output;
- RR-only rows;
- numeric fields;
- requested presidential votes <= turnout;
- non-negative electorate/turnout;
- duplicate section keys;
- `QT_APTOS = QT_COMPARECIMENTO + QT_ABSTENCOES`;
- total formula;
- Caroebe presence.

Historical real-data failures were fixed:
1. Derived output columns were incorrectly treated as raw source columns. Fixed by separating `REQUIRED_RAW`.
2. NumPy scalar values could become SQLite BLOBs. Fixed by converting scalars with `.item()`.
3. Duplicate requested vote rows could silently interact with additive upsert. Fixed with `vote_rows` keyed by section + requested vote code.
4. Section metadata inconsistency is now explicitly rejected.

## 6. National workflow

Commit `d573865cc6a3b67f11d499223c9602ed14a23008` added `.github/workflows/national.yml`.

Design:
- Matrix over all 27 Brazilian UFs.
- Up to 8 UF jobs in parallel.
- Each UF runner downloads only its own official first-round ZIP.
- Raw ZIPs remain ephemeral and are never uploaded.
- Each UF is processed incrementally and validated before its processed CSV is uploaded.
- A consolidation job waits for all 27 UF jobs.
- Consolidation downloads all processed UF artifacts and runs `generate_table.py --uf ALL`.
- National QC verifies exact 27-UF coverage, global section-key uniqueness, numeric/non-negative values, requested votes <= turnout, electorate reconciliation, and total formula.
- Final national CSV and Markdown are uploaded as a 30-day artifact.

Current national workflow run #1:
- Run ID: `37640000936`
- Head: `d573865cc6a3b67f11d499223c9602ed14a23008`
- Final status: **success**, attempt 2.
- 27/27 UFs processed and consolidated successfully.
- National output: **497,897 sections** across **5,571 municipalities**.
- National requested-vote total: **115,641,794**.
- Audit checks: 0 duplicate keys, 0 negative rows, 0 total-formula failures, 0 requested-votes-over-turnout, 0 electorate-reconciliation failures.
- National artifact ID: `11498063146`.
- Artifact digest: `sha256:9a5d0f5bf056635e895d28b2c20e7c21b05d598c6fa79020ed6e3e7f9bc202cb`.
- Validated on 2026-10-07.

CI after the final test fix `bbffc0ee17ed683492445f2946ac64832772d6fd` is also green (run `37654500576`).

## 7. Non-negotiable integrity rules

1. Never fabricate electoral rows.
2. Never infer missing sections.
3. Preserve BU metadata.
4. Vote counts originate from raw `NR_VOTAVEL + QT_VOTOS`.
5. Presidential filter remains cargo 1.
6. Do not silently accept schema changes.
7. Do not commit raw ZIPs.
8. Do not load the complete national raw dataset into RAM.
9. Do not claim national completeness until all 27 UFs and consolidation pass.
10. Do not change the definition of `TOTAL_VOTOS_PRES` without an explicit requirement change.

## 8. Analytical dashboard

The project now includes an analytical dashboard focused on the relationship between BU emission and reception timing.

- Generator: `scripts/generate_analysis_dashboard.py`.
- Published file: `data/processed/dashboard_analise_emissao_recebimento_2026.html`.
- GitHub Pages publishes this analytical dashboard as `pages/index.html` from the national workflow.
- Cutoff: **04/10/2026 19:12:00**, treated as an analytical/system-monitoring marker because the public real-time apuração display stopped updating at that time. The cutoff is not treated as causal evidence.
- Main analyses: BU flow emitted vs received; cumulative Flávio/Lula votes by reception time; emission→reception latency distribution; median/mean/P90 latency over time; Pearson correlation between full BU emission and reception timestamps; emission×reception 15-minute matrix; before/after 19:12 comparison; UF and municipality comparison.
- Correlation is calculated over all valid BUs; scatter visualization is only a deterministic sample for browser performance.

## 9. Remaining work

1. Persist a machine-readable per-UF QC summary for the final audit trail.
2. Record the exact TSE resource snapshot and processing timestamp.
3. Validate the new analytical dashboard in the national GitHub Actions run and inspect the published Pages result.
4. Refine the dashboard only after the emission/reception timing analysis is validated against the national artifact.

## 10. Definition of done

The project is complete only when:
- all 27 UFs process successfully against official TSE first-round data;
- national consolidation passes;
- duplicate section keys are ruled out;
- the final CSV is available as an artifact/release;
- Caroebe/RR example is based on actual data;
- README and persistent context document the final validated state.

## 11. Continuation protocol

When the user says “continue”:
1. Read this file.
2. Inspect current main and latest Actions status.
3. Identify the first unfinished item above.
4. Perform the concrete GitHub change/action directly when possible.
5. Verify the result before claiming success.
6. Do not repeat completed work.
