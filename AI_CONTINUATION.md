# AI Continuation Guide

## First read
1. `PROJECT_CONTEXT.md`
2. `README.md`
3. Current GitHub Actions status
4. Latest commits affecting `scripts/` and `.github/workflows/`

## Source of truth
Repository state plus actual GitHub Actions results. Do not infer success from unit tests alone.

## Current priority
The national 27-UF first-round pipeline is validated and green. Its existing data contract and results must remain separate from the second-round BU collection prototype documented in `PROJECT_CONTEXT.md`. The immediate active task is to run and audit the local 100-section second-round pilot before any statewide collection.

## Validated national checkpoint
- Workflow run: `37640000936`
- Attempt: `2`
- Head: `d573865cc6a3b67f11d499223c9602ed14a23008`
- Result: success
- UFs: 27
- Sections: 497,897
- Municipalities: 5,571
- National requested votes: 115,641,794
- Duplicate section keys: 0
- Negative rows: 0
- Total formula failures: 0
- Votes above turnout: 0
- Electorate reconciliation failures: 0
- National artifact ID: `11498063146`
- Artifact SHA-256: `sha256:9a5d0f5bf056635e895d28b2c20e7c21b05d598c6fa79020ed6e3e7f9bc202cb`
- Machine-readable audit: `audit/national_qc_2026-10-07.json`
- Audit commit: `41fa3d2e5a8c2970ce0a8b8d156a04373f8e637d`

## Integrity rules
Never:
- fabricate BU rows;
- infer missing sections;
- change vote codes silently;
- commit raw ZIPs;
- declare national completion before all 27 UFs and consolidation pass.

Always:
- use official TSE data;
- validate actual source schema;
- validate section uniqueness;
- validate metadata consistency;
- validate vote totals;
- process incrementally;
- preserve the existing 19-column output contract unless a deliberate versioned change is approved.

## Continue behavior
When the user says “continue”:
1. Inspect the latest national/CI workflow status and latest commits.
2. If a job failed, inspect its exact log and fix the smallest concrete defect.
3. If the national pipeline is green, verify the audit trail and source snapshot.
4. Then begin the analytical layer using the validated national artifact as immutable input.
5. Analytical work should be chunked and must not silently alter the source data contract.
6. Verify every resulting commit/workflow before reporting success.

## Analytical layer guardrails
The analytical layer may derive measures such as candidate vote differences, shares, turnout, and geographic aggregates, but must explicitly define denominators and preserve the distinction between:
- requested presidential vote total (22 + 13 + 95 + 96);
- candidate votes;
- blank/null votes;
- electorate and turnout.

Do not reinterpret `TOTAL_VOTOS_PRES` as all presidential candidates unless the project requirements are explicitly changed.

## Definition of done
### Data pipeline
- 27 UFs processed successfully.
- National consolidation passes.
- Duplicate section keys ruled out.
- National CSV artifact available.
- Caroebe/RR example based on actual data.
- README and persistent context reflect final validated state.

### Auditability
- Machine-readable national QC record committed.
- Exact TSE source resource snapshot recorded before analytical results are treated as reproducible.

### Analysis
- Analytical scripts consume the validated output without modifying it.
- Derived metrics have explicit definitions and tests.
- Analytical outputs are reproducible from the national artifact.


## Second-round BU prototype — active continuation (2026-10-26)

Read the new section 12 in `PROJECT_CONTEXT.md` before continuing. This is a separate local workstream; do not conflate it with the validated first-round national pipeline.

Local directory: `C:\\Users\\tiago.ferreira\\tse-bu-presidencial-2026-segundo-turno`.

Current confirmed state:
- TSE election-urna configuration for SP was parsed: 645 municipalities, 779 zones, 103,904 listed sections.
- The per-section auxiliary JSON was successfully queried for Motuca sections 0162–0166. All five listed a BU file under a section-specific hash directory and were marked `Totalizado`.
- Local ASN.1 decoding worked on the sample. The five-section collector reported each section's vote sum equal to turnout: 258, 269, 264, 244, 253. Total 1,288; 20 vote rows.
- Candidate labels are still numeric placeholders; verify names against an official source.
- The user ran `coletar_piloto_100.py`. Its summary reports 100 sections in the batch, 99 validated checkpoints, and one recorded error. The last six displayed sections (095–100) each reconciled vote sum to turnout. The failed section and cause are not yet known; do not claim that all 100 passed.

Next action:
1. Ask the user to inspect `relatorio_piloto_100.csv` for the one `ERRO` row. Suggested PowerShell command: `Import-Csv .\\relatorio_piloto_100.csv -Delimiter ';' | Where-Object { $_.status -eq 'ERRO' } | Format-List *`. If the column names differ, first run `Get-Content .\\relatorio_piloto_100.csv -TotalCount 3`.
2. Diagnose the exact failure, retry that section, and reconcile the report, status JSON, checkpoints, and CSV after rerunning. Audit resumability and ensure failed sections are not silently counted as completed.
3. Validate the schema and election semantics against authoritative TSE sources.
4. Do not begin statewide collection until the single failure is understood and the 100-section pilot is audited. After that, plan a checkpointed, rate-limited run with complete reconciliation and explicit error reporting.

Do not commit local data files or raw BUs. Keep the second-round workstream separate from the first-round output schema and artifacts.


## Exact handoff for next session — 2026-10-26

The latest state and all detailed evidence are recorded at the end of `PROJECT_CONTEXT.md`. Continue from that addendum, not from the older “100-section pilot” instructions above; those were superseded by the 200-section run.

Local project: `C:\Users\tiago.ferreira\tse-bu-presidencial-2026-segundo-turno`.

Confirmed latest result:
- `LIMITE = 200` in local `coletar_piloto_100.py`.
- Backup exists: `coletar_piloto_100.py.pre_lote_200.bak`.
- Python compilation passed.
- 200 sections selected; 196 BU records validated; 4 sections classified `SECAO_VINCULADA`; 196 checkpoints; 0 recorded errors.
- `relatorio_piloto_100.csv`: 200 rows; 196 `SUCESSO/OK`; 4 `SECAO_VINCULADA/NAO_APLICAVEL`.
- `resultados_piloto_100.csv`: 775 vote rows, all `OK`.
- SP configuration: 645 municipalities, 103,904 listed sections, 248 with `nsp`.

**First action tomorrow:** ask the user to run:
```powershell
Select-String -Path .\coletar_piloto_100.py -Pattern 'def chave_secao|def salvar_resultados|def salvar_status' -Context 0,12
```
Then inspect those functions and verify unique section keys, checkpoint reuse, linked-section exclusion, and output reconstruction. Do not launch another collection yet. Consider the proposed 500-section batch only after this audit; do not start a statewide run. Note that output filenames still say `100` although the limit is 200. The TSE's listed section count is not a verified BU availability count.

The earlier 100-section instructions in this document are historical and superseded by this handoff. Keep the second-round prototype separate from the first-round national pipeline and do not commit local raw BU files or generated local CSVs.
