import pandas as pd
import pytest

from scripts.generate_table import validate


def make_df(total: int) -> pd.DataFrame:
    df = pd.DataFrame({
        "SG_UF": ["RR"],
        "CD_MUNICIPIO": ["0001"],
        "NM_MUNICIPIO": ["CAROEBE"],
        "NR_ZONA": ["1"],
        "NR_SECAO": ["1"],
        "NR_LOCAL_VOTACAO": ["1"],
        "NR_URNA_EFETIVADA": ["1"],
        "QT_APTOS": ["100"],
        "QT_COMPARECIMENTO": ["90"],
        "QT_ABSTENCOES": ["10"],
        "DT_ABERTURA": ["04/10/2026 07:00:00"],
        "DT_ENCERRAMENTO": ["04/10/2026 17:00:00"],
        "DT_EMISSAO_BU": ["04/10/2026 17:10:00"],
        "HH_EMISSAO_BU": ["17:10:00"],
        "DT_BU_RECEBIDO": ["04/10/2026 18:00:00"],
        "HH_BU_RECEBIDO": ["18:00:00"],
        "VOTOS_FLAVIO_BOLSONARO": [10],
        "VOTOS_LULA": [20],
        "VOTOS_BRANCO_PRES": [2],
        "VOTOS_NULO_PRES": [3],
        "TOTAL_VOTOS_PRES": [total],
    })
    return df


def test_total_presidencial():
    validate(make_df(35), "RR")


def test_total_incorreto():
    with pytest.raises(ValueError):
        validate(make_df(99), "RR")
