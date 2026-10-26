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
3. Validate the new analytical dashboard in the national GitHub Actions run and inspect the published Pages result. Latest dashboard generator fix: KPI formatting corrected in commit `95eaba0ede47f5d7a8e9ba876cb15613d25f241a`. Test fixtures were then aligned with the current TSE source schema in commits `c06c0a07dda93465ffa18f6d647642a58e583fd8` and `276e0cca009bb1ced631fffb2c78b0948d20989b`.
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


## 12. Exploratory second-round 2026 BU collection (separate workstream)

This workstream was started locally on 2026-10-26 in:
`C:\\Users\\tiago.ferreira\\tse-bu-presidencial-2026-segundo-turno`

**Important scope distinction:** the existing national pipeline and its validated artifact above concern the first-round open-data ZIP workflow. The second-round work described here is a separate exploratory collector using the TSE's election-urna file endpoints. Do not reinterpret or replace the validated first-round national dataset with these results.

### Source and configuration discovered

- Election-urna directory: `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/`
- State configuration tested: `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/config/sp/sp-p003221-cs.json`
- The configuration identifies São Paulo (`sp`) and lists 645 municipalities, 779 municipality-zone entries, and 103,904 sections. These are counts from the configuration, not proof that every section has an available or validated BU.
- The second-round presidential election code observed in decoded BU: `6258`.
- The auxiliary JSON pattern tested for a section is:
  `.../dados/sp/{municipio}/{zona}/{secao}/p003221-sp-m{municipio}-z{zona}-s{secao}-aux.json`
- The auxiliary JSON provides `hashes[]`, each hash's `arq[]`, and the BU file where `tp == "bu"`. The BU URL uses the hash as a directory and the listed filename. Do not assume the hash or filename across sections.
- A `HEAD` request to the section directory returned 404; this was a directory-path test and does not establish that a BU is missing. The auxiliary JSON is the working discovery method.

### Local prototype and evidence

Files created locally (not assumed to be committed to this repository):
- `bu_2026.asn1`: ASN.1 schema obtained from a third-party GitHub project; it is not yet verified as an official TSE schema for the second round.
- `testar_bu.py`, `inspecionar_bu.py`, `identificar_candidatos.py`
- `exportar_secao.py`: single-section prototype reading `bu-teste.dat`.
- `coletar_amostra.py`: sample collector for five sections.
- `coletar_piloto_100.py`: resumable 100-section pilot script created locally; it has **not yet been run or validated**.
- Local outputs include `resultados_amostra.csv`, `relatorio_amostra.csv`, `resultado_secao_0162.csv`, and downloaded sample BU/VSC files.

The ASN.1 decoder successfully decoded the BU for Motuca (municipality code `61069`), zone `0239`, section `0162`. The decoded BU identified election `6258`, presidential office, candidate codes `13` and `22`, plus blank and null votes. The sample's turnout was 258 and the vote sum was 258.

The sample collector then downloaded and decoded sections `0162`–`0166` in Motuca, zone `0239`. All five were reported as `Totalizado`, and each section's sum of decoded votes equaled its turnout:
- 0162: 258
- 0163: 269
- 0164: 264
- 0165: 244
- 0166: 253

Total across this sample: 1,288 votes/turnout; 20 vote rows were written. This validates only this five-section sample, not the whole state or the schema generally.

### Immediate next steps

1. Run the local `coletar_piloto_100.py` script and inspect its output, `status_piloto_100.json`, `resultados_piloto_100.csv`, and `relatorio_piloto_100.csv`.
2. Audit the pilot script carefully before scaling. Confirm retry behavior, checkpoints, CSV integrity, status reconciliation, and whether failed sections can be retried without corrupting previous outputs.
3. Confirm the source configuration's election/turn semantics and validate the ASN.1 schema against authoritative second-round TSE documentation or independent known-good decoding.
4. Resolve candidate codes to candidate names using an official TSE candidate source; do not treat labels like `Candidato codigo 13` as verified names.
5. Only after the pilot passes, design a controlled statewide run with checkpointing, rate limiting, retries, durable per-section logs, and a final reconciliation of listed, downloaded, decoded, validated, and failed sections.
6. Keep second-round output in separate paths and clearly label it as a distinct dataset. Do not change the first-round 19-column output contract without an explicit requirement change.

### Integrity constraints for this workstream

- Do not infer missing BUs from section listings.
- Do not count a section as complete unless its BU is downloaded, decoded, and its vote sum reconciles to turnout.
- Preserve raw downloaded BUs for reproducibility, while keeping large raw datasets out of Git.
- Record failures explicitly; never silently discard failed sections.
- Do not report statewide completeness based only on the configuration's section count.
- Candidate names must come from a verified source, not from guesswork.
