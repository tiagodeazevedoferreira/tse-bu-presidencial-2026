# AI Continuation Guide

## First read
1. `PROJECT_CONTEXT.md`
2. `README.md`
3. Current GitHub Actions status
4. Latest commits affecting `scripts/` and `.github/workflows/`

## Source of truth
Repository state plus actual GitHub Actions results. Do not infer success from unit tests alone.

## Current priority
The RR end-to-end pipeline is green. The active milestone is the national 27-UF workflow in `.github/workflows/national.yml`.

National workflow design:
- 27 Brazilian UFs only; exclude ZZ.
- 1st round.
- `CD_CARGO_PERGUNTA = 1`.
- Requested vote codes: 22, 13, 95, 96.
- Incremental/chunked processing.
- Raw ZIPs remain ephemeral.
- Per-UF processed CSV artifacts feed a final national consolidation job.
- National consolidation uses SQLite-backed global section-key validation.
- Final artifacts: national CSV and Markdown summary.

## Current checkpoint
National workflow run #1:
- Run ID: `37640000936`
- Head: `d573865cc6a3b67f11d499223c9602ed14a23008`
- The workflow contains 27 matrix jobs plus a consolidation job.

Latest implementation:
- `298dc8718bd671dfd0a97fd39cb0c440d4c404ce`: strengthened national consolidation validation.
- `d573865cc6a3b67f11d499223c9602ed14a23008`: national 27-UF workflow.
- `2bdc5096a4c714a5220462958c39c0bd749a2852`: persistent context updated.

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
- process incrementally.

## Continue behavior
When the user says “continue”:
1. Inspect the latest national/CI workflow status.
2. If a job failed, inspect its exact log and fix the smallest concrete defect.
3. If all 27 UF jobs pass, inspect national consolidation and artifact.
4. Then close remaining audit/documentation work.
5. Verify every resulting commit/workflow before reporting success.

## Definition of done
- 27 UFs processed successfully.
- National consolidation passes.
- Duplicate section keys ruled out.
- National CSV artifact available.
- Caroebe/RR example based on actual data.
- README and persistent context reflect final validated state.
