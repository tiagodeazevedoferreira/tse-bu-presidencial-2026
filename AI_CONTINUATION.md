# AI Continuation Guide

## First read
1. `PROJECT_CONTEXT.md`
2. `README.md`
3. Current GitHub Actions status
4. Latest commits affecting `scripts/` and `.github/workflows/`

## Source of truth
Repository state plus actual GitHub Actions results. Do not infer success from unit tests alone.

## Current priority
The national 27-UF pipeline is validated and green. The next milestone is to preserve the audit trail and then begin the analytical layer without changing the validated data contract.

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
