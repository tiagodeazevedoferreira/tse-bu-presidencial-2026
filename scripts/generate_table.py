#!/usr/bin/env python3
"""Validate and consolidate per-UF presidential BU tables incrementally."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]
PROCESSED = Path("data/processed")
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


def validate(df: pd.DataFrame) -> None:
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Colunas ausentes: {sorted(missing)}")

    if df[KEY].duplicated().any():
        raise ValueError("Duplicidade encontrada na chave de seção.")

    if (df[VOTE_COLUMNS] < 0).any().any():
        raise ValueError("Há quantidade de votos negativa.")

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


def append_uf(
    uf: str,
    output_handle,
    first_output: bool,
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
        for col in VOTE_COLUMNS:
            chunk[col] = pd.to_numeric(chunk[col], errors="raise").astype("int64")

        validate(chunk)

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

    summary_rows = []
    first_output = True

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        for uf in selected:
            first_output, totals = append_uf(
                uf,
                handle,
                first_output,
            )
            summary_rows.append(
                {
                    "SG_UF": uf,
                    **totals,
                }
            )

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
