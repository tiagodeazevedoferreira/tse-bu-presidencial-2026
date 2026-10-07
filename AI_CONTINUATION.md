# AI Continuation Guide

This repository is designed to be continued by another assistant from a short prompt.

## First read

Always read:
1. PROJECT_CONTEXT.md
2. README.md
3. the current GitHub Actions status
4. the latest commits affecting scripts/ and .github/workflows/

## Source of truth

The project state is the repository plus its latest CI/workflow results. Chat history is supplemental.

## Current priority

The immediate priority is RR end-to-end validation after commit 9f6391f9f7fa6ef286b1bf738cd07cce0dee606d.

The first RR attempt failed because derived columns were incorrectly treated as raw source columns. That was fixed.

Do not move to all 27 UFs until RR passes.

## Continuation behavior

When the user says continue:
- do not explain the whole history again;
- inspect the current workflow/commit state;
- execute the next unfinished task from PROJECT_CONTEXT.md;
- make repository changes directly when possible;
- verify the resulting workflow;
- report only the relevant result and next checkpoint.

## Data integrity

Never:
- invent BU rows;
- infer electoral results;
- silently alter vote codes;
- silently accept source schema changes;
- commit raw TSE ZIPs;
- declare completion based only on unit tests.

Always:
- use official TSE data;
- preserve reproducibility;
- validate section uniqueness;
- validate vote totals;
- validate the actual raw schema;
- process incrementally.

## Important project decisions

- 27 Brazilian UFs only; exclude ZZ.
- 1st round only.
- Presidential contest: CD_CARGO_PERGUNTA = 1.
- Flávio Bolsonaro: 22.
- Lula: 13.
- Branco: 95.
- Nulo: 96.
- Total requested: 22 + 13 + 95 + 96.
- CSV separator: ;.
- Raw encoding: latin1.
- Processed encoding: utf-8-sig.
- Python: 3.10+.
- Memory-safe processing is mandatory.
- SQLite is used as disk-backed intermediate storage.

## Definition of done

The project is not finished until:
1. RR passes end-to-end against the real TSE BU file;
2. the 27 UFs process successfully;
3. national consolidation passes validation;
4. duplicate section keys are ruled out;
5. generated CSV is available as an artifact/release;
6. Caroebe/RR example is based on actual processed data;
7. README and PROJECT_CONTEXT.md reflect the final state.