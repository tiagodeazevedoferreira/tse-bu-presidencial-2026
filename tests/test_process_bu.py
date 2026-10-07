import sqlite3
import zipfile

import pandas as pd
import pytest

from scripts.process_bu import connect, process_csv


def _raw_csv(rows):
    columns = [
        "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO",
        "NR_LOCAL_VOTACAO", "NR_URNA_EFETIVADA", "QT_APTOS",
        "QT_COMPARECIMENTO", "QT_ABSTENCOES", "DT_ABERTURA",
        "DT_ENCERRAMENTO", "DT_EMISSAO_BU", "DT_BU_RECEBIDO",
        "CD_CARGO_PERGUNTA", "NR_VOTAVEL", "QT_VOTOS",
    ]
    return pd.DataFrame(rows, columns=columns).to_csv(
        sep=";", index=False
    ).encode("latin1")


def test_processor_derives_vote_columns_from_raw_source(tmp_path):
    rows = [
        ["RR", "001", "CAROEBE", "1", "10", "5", "7", "100", "90", "10",
         "04/10/2026 07:00:00", "04/10/2026 17:00:00",
         "04/10/2026 17:10:00", "04/10/2026 18:00:00", "1", "22", "10"],
        ["RR", "001", "CAROEBE", "1", "10", "5", "7", "100", "90", "10",
         "04/10/2026 07:00:00", "04/10/2026 17:00:00",
         "04/10/2026 17:10:00", "04/10/2026 18:00:00", "1", "13", "20"],
        ["RR", "001", "CAROEBE", "1", "10", "5", "7", "100", "90", "10",
         "04/10/2026 07:00:00", "04/10/2026 17:00:00",
         "04/10/2026 17:10:00", "04/10/2026 18:00:00", "1", "95", "2"],
        ["RR", "001", "CAROEBE", "1", "10", "5", "7", "100", "90", "10",
         "04/10/2026 07:00:00", "04/10/2026 17:00:00",
         "04/10/2026 17:10:00", "04/10/2026 18:00:00", "1", "96", "3"],
    ]

    zip_path = tmp_path / "bweb_1t_RR_test.zip"
    csv_bytes = _raw_csv(rows)
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("bweb_1t_RR_test.csv", csv_bytes)

    conn = connect(tmp_path / "test.sqlite")
    try:
        with zipfile.ZipFile(zip_path) as zf:
            process_csv(zf, "bweb_1t_RR_test.csv", conn)

        row = conn.execute(
            """
            SELECT VOTOS_FLAVIO_BOLSONARO, VOTOS_LULA,
                   VOTOS_BRANCO_PRES, VOTOS_NULO_PRES
            FROM sections
            WHERE SG_UF = 'RR' AND CD_MUNICIPIO = '001'
              AND NR_ZONA = '1' AND NR_SECAO = '10'
            """
        ).fetchone()
        assert row == (10, 20, 2, 3)
    finally:
        conn.close()

def test_processor_rejects_duplicate_requested_vote_rows(tmp_path):
    rows = [
        ["RR", "001", "CAROEBE", "1", "10", "5", "7", "100", "90", "10",
         "04/10/2026 07:00:00", "04/10/2026 17:00:00",
         "04/10/2026 17:10:00", "04/10/2026 18:00:00", "1", "22", "10"],
    ]

    zip_path = tmp_path / "bweb_1t_RR_test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("bweb_1t_RR_test.csv", _raw_csv(rows))

    conn = connect(tmp_path / "test.sqlite")
    try:
        with zipfile.ZipFile(zip_path) as zf:
            process_csv(zf, "bweb_1t_RR_test.csv", conn)
            with pytest.raises(ValueError, match="duplicate requested vote row"):
                process_csv(zf, "bweb_1t_RR_test.csv", conn)
    finally:
        conn.close()


def test_processor_rejects_inconsistent_section_metadata(tmp_path):
    rows = [
        ["RR", "001", "CAROEBE", "1", "10", "5", "7", "100", "90", "10",
         "04/10/2026 07:00:00", "04/10/2026 17:00:00",
         "04/10/2026 17:10:00", "04/10/2026 18:00:00", "1", "22", "10"],
        ["RR", "001", "CAROEBE", "1", "10", "5", "8", "100", "90", "10",
         "04/10/2026 07:00:00", "04/10/2026 17:00:00",
         "04/10/2026 17:10:00", "04/10/2026 18:00:00", "1", "13", "20"],
    ]

    zip_path = tmp_path / "bweb_1t_RR_test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("bweb_1t_RR_test.csv", _raw_csv(rows))

    conn = connect(tmp_path / "test.sqlite")
    try:
        with zipfile.ZipFile(zip_path) as zf:
            with __import__("pytest").raises(ValueError, match="inconsistent NR_URNA_EFETIVADA"):
                process_csv(zf, "bweb_1t_RR_test.csv", conn)
    finally:
        conn.close()
