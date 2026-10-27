#!/usr/bin/env python3
"""Build a compact, auditable comparison dataset from the official TSE section CSV.

Input is the original TSE file containing both rounds. The raw CSV is never changed.
Output is a gzip-compressed JSON file suitable for a static GitHub Pages dashboard.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

UFS_REGIONS = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte",
    "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste",
    "MA": "Nordeste", "PB": "Nordeste", "PE": "Nordeste",
    "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste",
    "MS": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
    "ZZ": "Exterior",
}
CODES = (13, 22, 95, 96)
EXPECTED_ELECTION = {"1": "6257", "2": "6258"}
CHUNK_SIZE = 200_000

def text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="votacao_secao_2026_BR.csv", help="CSV original do TSE")
    parser.add_argument("--output", default="data/dashboard/votos_turnos_2026.json.gz", help="JSON gzip de saída")
    parser.add_argument("--chunksize", type=int, default=CHUNK_SIZE)
    args = parser.parse_args()

    source = Path(args.input)
    output = Path(args.output)
    if not source.is_file():
        raise SystemExit(f"Arquivo de entrada não encontrado: {source}")
    if args.chunksize < 1:
        raise SystemExit("--chunksize deve ser maior que zero")

    required = [
        "NR_TURNO", "CD_ELEICAO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO",
        "NR_ZONA", "NR_SECAO", "DS_CARGO", "NR_VOTAVEL", "QT_VOTOS",
        "NR_LOCAL_VOTACAO", "NM_LOCAL_VOTACAO", "DS_LOCAL_VOTACAO_ENDERECO",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    row_counts = Counter()
    vote_totals = Counter()

    with tempfile.TemporaryDirectory(prefix="tse-turnos-") as tempdir:
        db_path = Path(tempdir) / "aggregate.sqlite"
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("PRAGMA temp_store=FILE")
        conn.executescript("""
            CREATE TABLE sections (
                uf TEXT NOT NULL, mun TEXT NOT NULL, mun_name TEXT NOT NULL,
                zone TEXT NOT NULL, section TEXT NOT NULL,
                local TEXT NOT NULL, local_name TEXT NOT NULL, address TEXT NOT NULL,
                region TEXT NOT NULL, metadata_conflict INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (uf, mun, zone, section)
            );
            CREATE TABLE section_turns (
                uf TEXT NOT NULL, mun TEXT NOT NULL, zone TEXT NOT NULL,
                section TEXT NOT NULL, turn INTEGER NOT NULL,
                PRIMARY KEY (uf, mun, zone, section, turn)
            );
            CREATE TABLE votes (
                uf TEXT NOT NULL, mun TEXT NOT NULL, zone TEXT NOT NULL,
                section TEXT NOT NULL, turn INTEGER NOT NULL,
                code INTEGER NOT NULL, votes INTEGER NOT NULL,
                PRIMARY KEY (uf, mun, zone, section, turn, code)
            );
        """)

        seen_required = None
        for chunk_no, chunk in enumerate(pd.read_csv(
            source, sep=";", encoding="latin1", dtype=str,
            usecols=lambda col: col in required, chunksize=args.chunksize,
            keep_default_na=False,
        ), start=1):
            if seen_required is None:
                missing = sorted(set(required) - set(chunk.columns))
                if missing:
                    raise SystemExit(f"Colunas obrigatórias ausentes no CSV: {missing}")
                seen_required = True

            row_counts["source_rows"] += len(chunk)
            chunk["NR_TURNO"] = chunk["NR_TURNO"].str.strip()
            chunk["CD_ELEICAO"] = chunk["CD_ELEICAO"].str.strip()
            chunk["DS_CARGO"] = chunk["DS_CARGO"].str.strip().str.casefold()
            chunk["NR_VOTAVEL"] = chunk["NR_VOTAVEL"].str.strip()
            mask = (
                chunk["NR_TURNO"].isin(["1", "2"])
                & chunk.apply(lambda r: r["CD_ELEICAO"] == EXPECTED_ELECTION.get(r["NR_TURNO"], ""), axis=1)
                & chunk["DS_CARGO"].eq("presidente")
                & chunk["NR_VOTAVEL"].isin([str(c) for c in CODES])
            )
            part = chunk.loc[mask].copy()
            if part.empty:
                continue
            row_counts["presidential_vote_rows"] += len(part)
            part["QT_VOTOS"] = pd.to_numeric(part["QT_VOTOS"], errors="raise").astype("int64")
            if (part["QT_VOTOS"] < 0).any():
                raise SystemExit(f"Quantidade de votos negativa no bloco {chunk_no}")

            for turn, group in part.groupby("NR_TURNO", sort=False):
                row_counts[f"round_{turn}_vote_rows"] += len(group)
                vote_totals[f"{turn}|rows"] += len(group)
                for code, total in group.groupby("NR_VOTAVEL")["QT_VOTOS"].sum().items():
                    vote_totals[f"{turn}|{code}"] += int(total)

            part["SG_UF"] = part["SG_UF"].map(text)
            part["CD_MUNICIPIO"] = part["CD_MUNICIPIO"].map(text)
            part["NM_MUNICIPIO"] = part["NM_MUNICIPIO"].map(text)
            part["NR_ZONA"] = part["NR_ZONA"].map(text)
            part["NR_SECAO"] = part["NR_SECAO"].map(text)
            part["NR_LOCAL_VOTACAO"] = part["NR_LOCAL_VOTACAO"].map(text)
            part["NM_LOCAL_VOTACAO"] = part["NM_LOCAL_VOTACAO"].map(text)
            part["DS_LOCAL_VOTACAO_ENDERECO"] = part["DS_LOCAL_VOTACAO_ENDERECO"].map(text)
            unknown = sorted(set(part["SG_UF"]) - set(UFS_REGIONS))
            if unknown:
                raise SystemExit(f"UF/código geográfico inesperado: {unknown}")
            if (part[["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]] == "").any().any():
                raise SystemExit(f"Chave geográfica vazia no bloco {chunk_no}")

            # Check metadata consistency within each chunk before writing.
            metadata_cols = [
                "SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO",
                "NM_MUNICIPIO", "NR_LOCAL_VOTACAO", "NM_LOCAL_VOTACAO",
                "DS_LOCAL_VOTACAO_ENDERECO",
            ]
            metadata = part[metadata_cols].drop_duplicates()
            key_cols = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
            if metadata.duplicated(key_cols, keep=False).any():
                raise SystemExit(f"Metadados conflitantes para uma seção no bloco {chunk_no}")

            section_rows = []
            for uf, mun, zone, section, mun_name, local, local_name, address in metadata.itertuples(index=False, name=None):
                section_rows.append((
                    uf, mun, mun_name, zone, section, local, local_name, address,
                    UFS_REGIONS[uf], 0,
                ))
            conn.executemany("""
                INSERT INTO sections VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(uf,mun,zone,section) DO UPDATE SET
                    metadata_conflict = CASE WHEN
                        sections.mun_name != excluded.mun_name OR
                        sections.local != excluded.local OR
                        sections.local_name != excluded.local_name OR
                        sections.address != excluded.address OR
                        sections.region != excluded.region
                    THEN 1 ELSE sections.metadata_conflict END
            """, section_rows)

            turns = part[["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO"]].drop_duplicates()
            conn.executemany(
                "INSERT OR IGNORE INTO section_turns VALUES (?,?,?,?,?)",
                [(u, m, z, s, int(t)) for u, m, z, s, t in turns.itertuples(index=False, name=None)],
            )
            grouped = part.groupby(
                ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_TURNO", "NR_VOTAVEL"],
                as_index=False, sort=False,
            )["QT_VOTOS"].sum()
            vote_rows = [
                (u, m, z, s, int(t), int(c), int(v))
                for u, m, z, s, t, c, v in grouped.itertuples(index=False, name=None)
            ]
            conn.executemany("""
                INSERT INTO votes VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(uf,mun,zone,section,turn,code)
                DO UPDATE SET votes = votes.votes + excluded.votes
            """, vote_rows)
            if chunk_no % 5 == 0:
                conn.commit()
                print(f"Blocos processados: {chunk_no:,}; linhas lidas: {row_counts['source_rows']:,}")

        conn.commit()
        if seen_required is None:
            raise SystemExit("Nenhum bloco foi lido do CSV")
        conflicts = conn.execute("SELECT COUNT(*) FROM sections WHERE metadata_conflict=1").fetchone()[0]
        if conflicts:
            raise SystemExit(f"Metadados inconsistentes em {conflicts} seções; saída não gerada")
        found_turns = {
            str(r[0]): int(r[1])
            for r in conn.execute("SELECT turn, COUNT(*) FROM section_turns GROUP BY turn")
        }
        if "1" not in found_turns or "2" not in found_turns:
            raise SystemExit(f"Não foram encontrados os dois turnos esperados: {found_turns}")

        records = []
        query = """
            SELECT s.uf,s.region,s.mun,s.mun_name,s.zone,s.section,
                   s.local,s.local_name,s.address,
                   CASE WHEN t1.turn IS NULL THEN NULL ELSE 1 END AS has1,
                   CASE WHEN t2.turn IS NULL THEN NULL ELSE 1 END AS has2
            FROM sections s
            LEFT JOIN section_turns t1
              ON t1.uf=s.uf AND t1.mun=s.mun AND t1.zone=s.zone AND t1.section=s.section AND t1.turn=1
            LEFT JOIN section_turns t2
              ON t2.uf=s.uf AND t2.mun=s.mun AND t2.zone=s.zone AND t2.section=s.section AND t2.turn=2
            ORDER BY s.uf,s.mun,s.zone,s.section
        """
        only1 = only2 = both = 0
        for row in conn.execute(query):
            uf, region, mun, name, zone, section, local, local_name, address, has1, has2 = row
            if has1 and has2:
                both += 1
            elif has1:
                only1 += 1
            else:
                only2 += 1
            by_turn = []
            for turn, present in ((1, has1), (2, has2)):
                if not present:
                    by_turn.append(None)
                    continue
                values = dict(conn.execute("""
                    SELECT code,votes FROM votes
                    WHERE uf=? AND mun=? AND zone=? AND section=? AND turn=?
                """, (uf, mun, zone, section, turn)).fetchall())
                by_turn.append([int(values.get(code, 0)) for code in CODES])
            records.append({
                "u": uf, "r": region, "m": mun, "n": name,
                "z": zone, "s": section, "l": local,
                "ln": local_name, "a": address,
                "v1": by_turn[0], "v2": by_turn[1],
            })

        payload = {
            "schemaVersion": 1,
            "source": source.name,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "turns": {"1": {"electionCode": 6257}, "2": {"electionCode": 6258}},
            "voteCodes": {"flavio": 22, "lula": 13, "branco": 95, "nulo": 96},
            "fieldOrder": ["flavio", "lula", "branco", "nulo"],
            "coverage": {
                "sections": len(records), "round1Sections": found_turns.get("1", 0),
                "round2Sections": found_turns.get("2", 0), "commonSections": both,
                "onlyRound1": only1, "onlyRound2": only2,
                "sourceRows": row_counts["source_rows"],
                "presidentialVoteRows": row_counts["presidential_vote_rows"],
                "votesByTurnAndCode": {
                    f"{turn}_{code}": vote_totals[f"{turn}|{code}"]
                    for turn in ("1", "2") for code in CODES
                },
            },
            "records": records,
        }
        conn.close()

    with output.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz:
            gz.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    print("\n=== DATASET PARA O DASHBOARD ===")
    print(f"Arquivo: {output}")
    print(f"Tamanho gzip: {output.stat().st_size:,} bytes")
    print(f"Seções únicas: {len(records):,}")
    print(f"Com dados nos dois turnos: {both:,}")
    print(f"Somente 1º turno: {only1:,}")
    print(f"Somente 2º turno: {only2:,}")
    print(f"Registros de voto presidencial selecionados: {row_counts['presidential_vote_rows']:,}")
    print("Totais oficiais por turno/código:")
    for turn in ("1", "2"):
        print(f"  Turno {turn}: " + ", ".join(f"{code}={vote_totals[f'{turn}|{code}']:,}" for code in CODES))

if __name__ == "__main__":
    main()
