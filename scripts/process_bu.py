#!/usr/bin/env python3
"""Process TSE BU files incrementally and aggregate votes by section."""

from __future__ import annotations

import argparse
import logging
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd
from tqdm import tqdm

UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]
RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
TMP_DIR = Path("data/tmp")
CHUNK_SIZE = 100_000

OUTPUT_COLUMNS = [
    "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO",
    "NR_LOCAL_VOTACAO", "NR_URNA_EFETIVADA", "QT_APTOS",
    "QT_COMPARECIMENTO", "QT_ABSTENCOES", "DT_ABERTURA",
    "DT_ENCERRAMENTO", "DT_EMISSAO_BU", "HH_EMISSAO_BU", "DT_BU_RECEBIDO", "HH_BU_RECEBIDO",
    "VOTOS_FLAVIO_BOLSONARO", "VOTOS_LULA", "VOTOS_BRANCO_PRES",
    "VOTOS_NULO_PRES", "TOTAL_VOTOS_PRES",
]

REQUIRED_RAW = {
    "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO",
    "NR_LOCAL_VOTACAO", "NR_URNA_EFETIVADA", "QT_APTOS",
    "QT_COMPARECIMENTO", "QT_ABSTENCOES", "DT_ABERTURA",
    "DT_ENCERRAMENTO", "DT_EMISSAO_BU", "DT_BU_RECEBIDO",
    "CD_CARGO_PERGUNTA", "NR_VOTAVEL", "QT_VOTOS",
}
SECTION_KEY = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]


def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize known schema variants without silently dropping fields."""
    rename = {}
    aliases = {
        "QT_VOTOS": ["QT_VOTOS", "QT_VOTOS_NOMINAIS"],
        "NR_URNA_EFETIVADA": ["NR_URNA_EFETIVADA", "NR_URNA"],
        "DT_BU_RECEBIDO": ["DT_BU_RECEBIDO", "DT_RECEBIMENTO_BU"],
    }
    for target, names in aliases.items():
        if target not in df.columns:
            for name in names:
                if name in df.columns:
                    rename[name] = target
                    break
    return df.rename(columns=rename)



def derive_hour_fields(chunk: pd.DataFrame, member: str) -> pd.DataFrame:
    """Derive BU emission/reception time fields from the TSE datetime fields.

    The current 2026 BU source exposes DT_EMISSAO_BU and DT_BU_RECEBIDO as
    full datetime fields; HH_* is not a raw column. Keep HH_* in the processed
    contract because downstream analysis needs the time component, but derive
    it deterministically from the official datetime values.
    """
    for source, target in [
        ("DT_EMISSAO_BU", "HH_EMISSAO_BU"),
        ("DT_BU_RECEBIDO", "HH_BU_RECEBIDO"),
    ]:
        text = chunk[source].fillna("").astype(str).str.strip()
        missing = text.eq("") | text.isin(["#NULO", "#NE"])
        parsed = pd.to_datetime(text.mask(missing), errors="coerce", dayfirst=True)
        invalid = (~missing) & parsed.isna()
        if invalid.any():
            examples = text.loc[invalid].head(5).tolist()
            raise ValueError(
                f"{member}: {source} contém timestamp inválido: {examples}"
            )
        chunk[target] = parsed.dt.strftime("%H:%M:%S")
    return chunk

def discover_csv(zips: list[Path]) -> list[tuple[Path, str]]:
    found = []
    for archive in zips:
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                if member.lower().endswith(".csv"):
                    found.append((archive, member))
    return found


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vote_rows (
            SG_UF TEXT NOT NULL,
            CD_MUNICIPIO TEXT NOT NULL,
            NR_ZONA TEXT NOT NULL,
            NR_SECAO TEXT NOT NULL,
            NR_VOTAVEL INTEGER NOT NULL,
            QT_VOTOS INTEGER NOT NULL,
            PRIMARY KEY (SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, NR_VOTAVEL)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sections (
            SG_UF TEXT NOT NULL,
            CD_MUNICIPIO TEXT NOT NULL,
            NM_MUNICIPIO TEXT,
            NR_ZONA TEXT NOT NULL,
            NR_SECAO TEXT NOT NULL,
            NR_LOCAL_VOTACAO TEXT,
            NR_URNA_EFETIVADA TEXT,
            QT_APTOS INTEGER,
            QT_COMPARECIMENTO INTEGER,
            QT_ABSTENCOES INTEGER,
            DT_ABERTURA TEXT,
            DT_ENCERRAMENTO TEXT,
            DT_EMISSAO_BU TEXT,
            HH_EMISSAO_BU TEXT,
            DT_BU_RECEBIDO TEXT,
            HH_BU_RECEBIDO TEXT,
            VOTOS_FLAVIO_BOLSONARO INTEGER NOT NULL DEFAULT 0,
            VOTOS_LULA INTEGER NOT NULL DEFAULT 0,
            VOTOS_BRANCO_PRES INTEGER NOT NULL DEFAULT 0,
            VOTOS_NULO_PRES INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO)
        )
        """
    )
    conn.commit()
    return conn


def first(series: pd.Series):
    values = series.dropna()
    if values.empty:
        return None
    value = values.iloc[0]
    # sqlite3 does not natively serialize NumPy scalar integers/floats as
    # INTEGER/REAL; without conversion they can become BLOB values.
    return value.item() if hasattr(value, "item") else value


def process_csv(zf: zipfile.ZipFile, member: str, conn: sqlite3.Connection) -> None:
    with zf.open(member) as raw:
        reader = pd.read_csv(
            raw, sep=";", encoding="latin1", dtype=str,
            chunksize=CHUNK_SIZE, low_memory=False,
        )
        for chunk in reader:
            chunk = normalize_headers(chunk)
            missing = REQUIRED_RAW - set(chunk.columns)
            if missing:
                raise ValueError(
                    f"{member}: colunas obrigatórias ausentes: {sorted(missing)}"
                )

            chunk = derive_hour_fields(chunk, member)

            cargo = chunk["CD_CARGO_PERGUNTA"].astype(str).str.strip()
            chunk = chunk[cargo == "1"].copy()
            if chunk.empty:
                continue

            chunk["NR_VOTAVEL"] = pd.to_numeric(
                chunk["NR_VOTAVEL"], errors="coerce"
            )
            chunk["QT_VOTOS"] = pd.to_numeric(
                chunk["QT_VOTOS"], errors="coerce"
            ).fillna(0)

            for col in ["QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES"]:
                chunk[col] = pd.to_numeric(chunk[col], errors="coerce")

            for key, group in chunk.groupby(SECTION_KEY, dropna=False):
                metadata_columns = [
                    "NM_MUNICIPIO", "NR_LOCAL_VOTACAO", "NR_URNA_EFETIVADA",
                    "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES",
                    "DT_ABERTURA", "DT_ENCERRAMENTO", "DT_EMISSAO_BU",
                    "DT_BU_RECEBIDO",
                ]
                for column in metadata_columns:
                    values = group[column].dropna().astype(str).str.strip().unique()
                    if len(values) > 1:
                        raise ValueError(
                            f"{member}: inconsistent {column} for "
                            f"section={key}"
                        )

                requested = group[group["NR_VOTAVEL"].isin([22, 13, 95, 96])][
                    SECTION_KEY + ["NR_VOTAVEL", "QT_VOTOS"]
                ]
                for vote_key, vote_group in requested.groupby(
                    SECTION_KEY + ["NR_VOTAVEL"], dropna=False
                ):
                    if len(vote_group) != 1:
                        raise ValueError(
                            f"{member}: duplicate requested vote row for "
                            f"section={vote_key[:-1]} vote={vote_key[-1]}"
                        )
                    params = dict(
                        SG_UF=vote_key[0],
                        CD_MUNICIPIO=vote_key[1],
                        NR_ZONA=vote_key[2],
                        NR_SECAO=vote_key[3],
                        NR_VOTAVEL=int(vote_key[4]),
                        QT_VOTOS=int(vote_group["QT_VOTOS"].iloc[0]),
                    )
                    try:
                        conn.execute(
                            """
                            INSERT INTO vote_rows
                            VALUES (
                                :SG_UF, :CD_MUNICIPIO, :NR_ZONA, :NR_SECAO,
                                :NR_VOTAVEL, :QT_VOTOS
                            )
                            """,
                            params,
                        )
                    except sqlite3.IntegrityError as exc:
                        raise ValueError(
                            f"{member}: duplicate requested vote row across "
                            f"chunks/files for section={vote_key[:-1]} "
                            f"vote={vote_key[-1]}"
                        ) from exc

                row = {
                    "SG_UF": key[0],
                    "CD_MUNICIPIO": key[1],
                    "NM_MUNICIPIO": first(group["NM_MUNICIPIO"]),
                    "NR_ZONA": key[2],
                    "NR_SECAO": key[3],
                    "NR_LOCAL_VOTACAO": first(group["NR_LOCAL_VOTACAO"]),
                    "NR_URNA_EFETIVADA": first(group["NR_URNA_EFETIVADA"]),
                    "QT_APTOS": first(group["QT_APTOS"]),
                    "QT_COMPARECIMENTO": first(group["QT_COMPARECIMENTO"]),
                    "QT_ABSTENCOES": first(group["QT_ABSTENCOES"]),
                    "DT_ABERTURA": first(group["DT_ABERTURA"]),
                    "DT_ENCERRAMENTO": first(group["DT_ENCERRAMENTO"]),
                    "DT_EMISSAO_BU": first(group["DT_EMISSAO_BU"]),
                    "HH_EMISSAO_BU": first(group["HH_EMISSAO_BU"]),
                    "DT_BU_RECEBIDO": first(group["DT_BU_RECEBIDO"]),
                    "HH_BU_RECEBIDO": first(group["HH_BU_RECEBIDO"]),
                    "VOTOS_FLAVIO_BOLSONARO": int(
                        group.loc[group["NR_VOTAVEL"] == 22, "QT_VOTOS"].sum()
                    ),
                    "VOTOS_LULA": int(
                        group.loc[group["NR_VOTAVEL"] == 13, "QT_VOTOS"].sum()
                    ),
                    "VOTOS_BRANCO_PRES": int(
                        group.loc[group["NR_VOTAVEL"] == 95, "QT_VOTOS"].sum()
                    ),
                    "VOTOS_NULO_PRES": int(
                        group.loc[group["NR_VOTAVEL"] == 96, "QT_VOTOS"].sum()
                    ),
                }

                conn.execute(
                    """
                    INSERT INTO sections VALUES (
                        :SG_UF, :CD_MUNICIPIO, :NM_MUNICIPIO, :NR_ZONA,
                        :NR_SECAO, :NR_LOCAL_VOTACAO, :NR_URNA_EFETIVADA,
                        :QT_APTOS, :QT_COMPARECIMENTO, :QT_ABSTENCOES,
                        :DT_ABERTURA, :DT_ENCERRAMENTO, :DT_EMISSAO_BU,
                        :HH_EMISSAO_BU, :DT_BU_RECEBIDO, :HH_BU_RECEBIDO,
                        :VOTOS_FLAVIO_BOLSONARO,
                        :VOTOS_LULA, :VOTOS_BRANCO_PRES, :VOTOS_NULO_PRES
                    )
                    ON CONFLICT(SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO)
                    DO UPDATE SET
                        VOTOS_FLAVIO_BOLSONARO =
                            sections.VOTOS_FLAVIO_BOLSONARO
                            + excluded.VOTOS_FLAVIO_BOLSONARO,
                        VOTOS_LULA =
                            sections.VOTOS_LULA + excluded.VOTOS_LULA,
                        VOTOS_BRANCO_PRES =
                            sections.VOTOS_BRANCO_PRES
                            + excluded.VOTOS_BRANCO_PRES,
                        VOTOS_NULO_PRES =
                            sections.VOTOS_NULO_PRES
                            + excluded.VOTOS_NULO_PRES
                    """,
                    row,
                )
            conn.commit()


def export_uf(conn: sqlite3.Connection, uf: str) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output = PROCESSED_DIR / f"votacao_presidencial_{uf}_2026.csv"
    query = """
        SELECT
            SG_UF, CD_MUNICIPIO, NM_MUNICIPIO, NR_ZONA, NR_SECAO,
            NR_LOCAL_VOTACAO, NR_URNA_EFETIVADA, QT_APTOS,
            QT_COMPARECIMENTO, QT_ABSTENCOES, DT_ABERTURA,
            DT_ENCERRAMENTO, DT_EMISSAO_BU, HH_EMISSAO_BU,
            DT_BU_RECEBIDO, HH_BU_RECEBIDO, VOTOS_FLAVIO_BOLSONARO, VOTOS_LULA, VOTOS_BRANCO_PRES,
            VOTOS_NULO_PRES,
            VOTOS_FLAVIO_BOLSONARO + VOTOS_LULA
                + VOTOS_BRANCO_PRES + VOTOS_NULO_PRES
                AS TOTAL_VOTOS_PRES
        FROM sections
        WHERE SG_UF = ?
        ORDER BY CAST(CD_MUNICIPIO AS INTEGER),
                 CAST(NR_ZONA AS INTEGER),
                 CAST(NR_SECAO AS INTEGER)
    """
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        first_chunk = True
        for df in pd.read_sql_query(
            query, conn, params=[uf], chunksize=50_000
        ):
            df = df[OUTPUT_COLUMNS]
            df.to_csv(
                handle, sep=";", index=False, header=first_chunk
            )
            first_chunk = False
    return output


def process_uf(uf: str) -> Path:
    zips = sorted((RAW_DIR / uf).glob("bweb_1t_*.zip"))
    if not zips:
        raise FileNotFoundError(f"Nenhum ZIP encontrado para {uf}.")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    db_path = TMP_DIR / f"{uf}.sqlite"
    conn = connect(db_path)
    try:
        files = discover_csv(zips)
        logging.info("%s: %d CSV(s) encontrados", uf, len(files))
        for archive, member in tqdm(files, desc=f"Processando {uf}"):
            logging.info("%s: %s", archive.name, member)
            with zipfile.ZipFile(archive) as zf:
                process_csv(zf, member, conn)
        return export_uf(conn, uf)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uf", default="ALL")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    selected = UFS if args.uf.upper() == "ALL" else [args.uf.upper()]
    invalid = [uf for uf in selected if uf not in UFS]
    if invalid:
        raise SystemExit(f"UF inválida: {', '.join(invalid)}")

    if args.download:
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("download_bu.py")),
                "--uf",
                args.uf,
            ],
            check=True,
        )

    for uf in selected:
        output = process_uf(uf)
        logging.info("%s: resultado em %s", uf, output)


if __name__ == "__main__":
    main()
