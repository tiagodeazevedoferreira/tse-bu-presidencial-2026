#!/usr/bin/env python3
"""Validate and consolidate per-UF presidential BU tables."""

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
OUTPUT = (
    PROCESSED
    / "votacao_presidencial_por_secao_2026.csv"
)
MARKDOWN = (
    PROCESSED
    / "votacao_presidencial_por_secao_2026.md"
)

COLUMNS = [
    "SG_UF",
    "CD_MUNICIPIO",
    "NM_MUNICIPIO",
    "NR_ZONA",
    "NR_SECAO",
    "NR_LOCAL_VOTACAO",
    "NR_URNA_EFETIVADA",
    "QT_APTOS",
    "QT_COMPARECIMENTO",
    "QT_ABSTENCOES",
    "DT_ABERTURA",
    "DT_ENCERRAMENTO",
    "DT_EMISSAO_BU",
    "DT_BU_RECEBIDO",
    "VOTOS_FLAVIO_BOLSONARO",
    "VOTOS_LULA",
    "VOTOS_BRANCO_PRES",
    "VOTOS_NULO_PRES",
    "TOTAL_VOTOS_PRES",
]
KEY = [
    "SG_UF",
    "CD_MUNICIPIO",
    "NR_ZONA",
    "NR_SECAO",
]


def validate(df: pd.DataFrame) -> None:
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(
            f"Colunas ausentes: {sorted(missing)}"
        )

    if df[KEY].duplicated().any():
        raise ValueError(
            "Duplicidade encontrada na chave de seção."
        )

    vote_cols = [
        "VOTOS_FLAVIO_BOLSONARO",
        "VOTOS_LULA",
        "VOTOS_BRANCO_PRES",
        "VOTOS_NULO_PRES",
        "TOTAL_VOTOS_PRES",
    ]

    if (df[vote_cols] < 0).any().any():
        raise ValueError(
            "Há quantidade de votos negativa."
        )

    expected = (
        df["VOTOS_FLAVIO_BOLSONARO"]
        + df["VOTOS_LULA"]
        + df["VOTOS_BRANCO_PRES"]
        + df["VOTOS_NULO_PRES"]
    )

    if not expected.equals(df["TOTAL_VOTOS_PRES"]):
        raise ValueError(
            "TOTAL_VOTOS_PRES não corresponde à soma "
            "dos componentes."
        )


def consolidate(ufs: list[str]) -> pd.DataFrame:
    frames = []

    for uf in ufs:
        path = (
            PROCESSED
            / f"votacao_presidencial_{uf}_2026.csv"
        )
        if not path.exists():
            raise FileNotFoundError(
                f"Resultado da UF não encontrado: {path}"
            )

        frames.append(
            pd.read_csv(
                path,
                sep=";",
                encoding="utf-8-sig",
                dtype=str,
            )
        )

    df = pd.concat(
        frames,
        ignore_index=True,
    )

    for col in [
        "VOTOS_FLAVIO_BOLSONARO",
        "VOTOS_LULA",
        "VOTOS_BRANCO_PRES",
        "VOTOS_NULO_PRES",
        "TOTAL_VOTOS_PRES",
    ]:
        df[col] = pd.to_numeric(
            df[col],
            errors="raise",
        ).astype("int64")

    validate(df)

    return (
        df[COLUMNS]
        .sort_values(KEY, kind="stable")
        .reset_index(drop=True)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uf", default="ALL")
    args = parser.parse_args()

    selected = (
        UFS if args.uf.upper() == "ALL"
        else [args.uf.upper()]
    )

    if any(uf not in UFS for uf in selected):
        raise SystemExit("UF inválida.")

    df = consolidate(selected)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    df.to_csv(
        OUTPUT,
        sep=";",
        encoding="utf-8-sig",
        index=False,
    )

    summary = (
        df.groupby("SG_UF")
        .agg(
            SECOES=("NR_SECAO", "count"),
            FLAVIO_22=(
                "VOTOS_FLAVIO_BOLSONARO",
                "sum",
            ),
            LULA_13=("VOTOS_LULA", "sum"),
            BRANCOS=("VOTOS_BRANCO_PRES", "sum"),
            NULOS=("VOTOS_NULO_PRES", "sum"),
            TOTAL_PRES=("TOTAL_VOTOS_PRES", "sum"),
        )
        .reset_index()
    )

    MARKDOWN.write_text(
        "# Votação presidencial por seção — Eleições 2026\n\n"
        "## Resumo por UF\n\n"
        + summary.to_markdown(index=False)
        + "\n",
        encoding="utf-8",
    )

    print(f"CSV: {OUTPUT}")
    print(f"Markdown: {MARKDOWN}")
    print(f"Linhas: {len(df):,}")


if __name__ == "__main__":
    main()
