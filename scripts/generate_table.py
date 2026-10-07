#!/usr/bin/env python3
"""Validate and consolidate per-UF presidential BU tables incrementally."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]
PROCESSED = Path("data/processed")
TMP = Path("data/tmp")
OUTPUT = PROCESSED / "votacao_presidencial_por_secao_2026.csv"
MARKDOWN = PROCESSED / "votacao_presidencial_por_secao_2026.md"

COLUMNS = [
    "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO",
    "NR_LOCAL_VOTACAO", "NR_URNA_EFETIVADA", "QT_APTOS",
    "QT_COMPARECIMENTO", "QT_ABSTENCOES", "DT_ABERTURA",
    "DT_ENCERRAMENTO", "DT_EMISSAO_BU", "DT_BU_RECEBIDO",
    "VOTOS_FLAVIO_BOLSONARO", "VOTOS_LULA", "VOTOS_BRANCO_PRES",
    "VOTOS_NULO_PRES", "TOTAL_VOTOS_PRES",
]
KEY = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
VOTE_COLUMNS = [
    "VOTOS_FLAVIO_BOLSONARO",
    "VOTOS_LULA",
    "VOTOS_BRANCO_PRES",
    "VOTOS_NULO_PRES",
    "TOTAL_VOTOS_PRES",
]
ELECTORAL_COLUMNS = ["QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES"]


def validate(df: pd.DataFrame, expected_uf: str) -> None:
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Colunas ausentes: {sorted(missing)}")

    if df[KEY].isna().any().any():
        raise ValueError("Há valores nulos na chave de seção.")

    if (df["SG_UF"] != expected_uf).any():
        raise ValueError(
            f"Arquivo {expected_uf} contém registros de outra UF."
        )

    if df[KEY].duplicated().any():
        raise ValueError("Duplicidade encontrada na chave de seção.")

    for col in VOTE_COLUMNS + ELECTORAL_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="raise").astype("int64")

    if (df[VOTE_COLUMNS] < 0).any().any():
        raise ValueError("Há quantidade de votos negativa.")

    if (df[ELECTORAL_COLUMNS] < 0).any().any():
        raise ValueError("Há quantidade de eleitores/comparecimento negativa.")

    expected = (
        df["VOTOS_FLAVIO_BOLSONARO"]
        + df["VOTOS_LULA"]
        + df["VOTOS_BRANCO_PRES"]
        + df["VOTOS_NULO_PRES"]
    )
    if not expected.equals(df["TOTAL_VOTOS_PRES"]):
        raise ValueError(
            "TOTAL_VOTOS_PRES não corresponde à soma dos componentes."
        )

    if expected.gt(df["QT_COMPARECIMENTO"]).any():
        raise ValueError(
            "Votos presidenciais solicitados excedem o comparecimento."
        )

    if not df["QT_APTOS"].eq(
        df["QT_COMPARECIMENTO"] + df["QT_ABSTENCOES"]
    ).all():
        raise ValueError(
            "QT_APTOS não corresponde a QT_COMPARECIMENTO + QT_ABSTENCOES."
        )


def register_keys(
    key_conn: sqlite3.Connection,
    chunk: pd.DataFrame,
    uf: str,
) -> None:
    rows = list(chunk[KEY].itertuples(index=False, name=None))
    try:
        key_conn.executemany(
            "INSERT INTO section_keys VALUES (?, ?, ?, ?)",
            rows,
        )
        key_conn.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(
            f"Duplicidade global de seção detectada durante a consolidação da UF {uf}."
        ) from exc


def append_uf(
    uf: str,
    output_handle,
    first_output: bool,
    key_conn: sqlite3.Connection,
) -> tuple[bool, dict[str, int]]:
    path = PROCESSED / f"votacao_presidencial_{uf}_2026.csv"
    if not path.exists():
        raise FileNotFoundError(f"Resultado da UF não encontrado: {path}")

    totals = {
        "SECOES": 0,
        "FLAVIO_22": 0,
        "LULA_13": 0,
        "BRANCOS": 0,
        "NULOS": 0,
        "TOTAL_PRES": 0,
    }

    for chunk in pd.read_csv(
        path,
        sep=";",
        encoding="utf-8-sig",
        dtype=str,
        chunksize=50_000,
    ):
        validate(chunk, uf)
        register_keys(key_conn, chunk, uf)

        chunk = chunk[COLUMNS].sort_values(KEY, kind="stable")

        totals["SECOES"] += len(chunk)
        totals["FLAVIO_22"] += int(chunk["VOTOS_FLAVIO_BOLSONARO"].sum())
        totals["LULA_13"] += int(chunk["VOTOS_LULA"].sum())
        totals["BRANCOS"] += int(chunk["VOTOS_BRANCO_PRES"].sum())
        totals["NULOS"] += int(chunk["VOTOS_NULO_PRES"].sum())
        totals["TOTAL_PRES"] += int(chunk["TOTAL_VOTOS_PRES"].sum())

        chunk.to_csv(
            output_handle,
            sep=";",
            encoding="utf-8-sig",
            index=False,
            header=first_output,
        )
        first_output = False

    return first_output, totals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uf", default="ALL")
    args = parser.parse_args()

    selected = (
        UFS if args.uf.upper() == "ALL"
        else [args.uf.upper()]
    )
    invalid = [uf for uf in selected if uf not in UFS]
    if invalid:
        raise SystemExit(f"UF inválida: {', '.join(invalid)}")

    PROCESSED.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    key_db = TMP / "national_section_keys.sqlite"
    if key_db.exists():
        key_db.unlink()

    summary_rows = []
    first_output = True
    key_conn = sqlite3.connect(key_db)
    key_conn.execute(
        """
        CREATE TABLE section_keys (
            SG_UF TEXT NOT NULL,
            CD_MUNICIPIO TEXT NOT NULL,
            NR_ZONA TEXT NOT NULL,
            NR_SECAO TEXT NOT NULL,
            PRIMARY KEY (SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO)
        )
        """
    )
    key_conn.commit()

    try:
        with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
            for uf in selected:
                first_output, totals = append_uf(
                    uf,
                    handle,
                    first_output,
                    key_conn,
                )
                summary_rows.append(
                    {
                        "SG_UF": uf,
                        **totals,
                    }
                )
    finally:
        key_conn.close()
        if key_db.exists():
            key_db.unlink()

    summary = pd.DataFrame(summary_rows)
    MARKDOWN.write_text(
        "# Votação presidencial por seção — Eleições 2026\n\n"
        "## Resumo por UF\n\n"
        + summary.to_markdown(index=False)
        + "\n",
        encoding="utf-8",
    )

    print(f"CSV: {OUTPUT}")
    print(f"Markdown: {MARKDOWN}")
    print(f"Linhas: {int(summary['SECOES'].sum()):,}")


if __name__ == "__main__":
    main()
