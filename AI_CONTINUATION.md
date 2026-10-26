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
- The local `coletar_piloto_100.py` script was just created and has **not been executed yet**. Do not claim that the 100-section pilot passed.

Next action:
1. Ask the user to run `& $python .\\coletar_piloto_100.py` from the local project directory and share the full terminal output.
2. Inspect pilot status, CSV, report, and checkpoint behavior; fix issues before scaling.
3. Validate the schema and election semantics against authoritative TSE sources.
4. Only after a successful pilot, plan a checkpointed, rate-limited statewide collection with complete reconciliation and explicit error reporting.

Do not commit local data files or raw BUs. Keep the second-round workstream separate from the first-round output schema and artifacts.
