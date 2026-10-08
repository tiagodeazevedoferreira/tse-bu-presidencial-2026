import pandas as pd
import pytest

from scripts.generate_timeline_dashboard import build_analysis_data, combine_timestamp


def make_csv(path, sep=";"):
    df = pd.DataFrame({
        "SG_UF":["RR","RR","AC"],
        "CD_MUNICIPIO":["001","001","002"],
        "NM_MUNICIPIO":["Boa Vista","Boa Vista","Rio Branco"],
        "NR_ZONA":["1","1","2"],
        "NR_SECAO":["1","2","3"],
        "NR_LOCAL_VOTACAO":["Escola A","Escola A","Escola B"],
        "DT_EMISSAO_BU":["04/10/2026","04/10/2026","05/10/2026"],
        "HH_EMISSAO_BU":["18:55:00","19:10:00","00:17:00"],
        "DT_BU_RECEBIDO":["04/10/2026","05/10/2026","05/10/2026"],
        "HH_BU_RECEBIDO":["19:05:00","00:17:00","01:03:00"],
        "VOTOS_FLAVIO_BOLSONARO":["10","20","30"],
        "VOTOS_LULA":["5","8","15"],
        "VOTOS_BRANCO_PRES":["1","2","3"],
        "VOTOS_NULO_PRES":["0","1","2"],
    })
    df.to_csv(path, sep=sep, index=False, encoding="utf-8-sig")


def test_combine_timestamp_preserves_date_and_time():
    date = pd.Series(["04/10/2026","05/10/2026"])
    hour = pd.Series(["18:55:00","00:17:00"])
    parsed = combine_timestamp(date, hour, "DT_TEST")
    assert parsed.iloc[0].strftime("%d/%m/%Y %H:%M:%S") == "04/10/2026 18:55:00"
    assert parsed.iloc[1].strftime("%d/%m/%Y %H:%M:%S") == "05/10/2026 00:17:00"


def test_tab_and_semicolon_csv_are_supported(tmp_path):
    for sep in [";", "\t"]:
        path = tmp_path / ("data_tab.csv" if sep == "\t" else "data_semicolon.csv")
        make_csv(path, sep)
        data = build_analysis_data(path)
        assert data["range"] == ["2026-10-04T18:00:00","2026-10-05T01:00:00"]


def test_hourly_event_aggregation_uses_full_timestamp(tmp_path):
    path = tmp_path / "data.csv"
    make_csv(path)
    data = build_analysis_data(path)
    emitted = data["hours"]["DT_EMISSAO_BU"]
    received = data["hours"]["DT_BU_RECEBIDO"]
    assert ["RR","001","2026-10-04T18:00:00",1,10,5,1,0,15] in emitted
    assert ["RR","001","2026-10-04T19:00:00",1,20,8,2,1,28] in emitted
    assert ["RR","001","2026-10-05T00:00:00",1,20,8,2,1,28] in received
    assert ["AC","002","2026-10-05T01:00:00",1,30,15,3,2,45] in received


def test_total_presidente_is_only_flavio_plus_lula(tmp_path):
    path = tmp_path / "data.csv"
    make_csv(path)
    data = build_analysis_data(path)
    totals = data["vote_totals"]
    assert totals["RR|001"] == [30,13,3,1,43]
    assert totals["AC|002"] == [30,15,3,2,45]


def test_missing_or_invalid_timestamp_is_handled(tmp_path):
    path = tmp_path / "data.csv"
    make_csv(path)
    df = pd.read_csv(path, sep=";", dtype=str)
    df.loc[1,"HH_EMISSAO_BU"]=""
    df.to_csv(path, sep=";", index=False, encoding="utf-8-sig")
    data = build_analysis_data(path)
    assert ["RR","001","2026-10-04T18:00:00",1,10,5,1,0,15] in data["hours"]["DT_EMISSAO_BU"]

    df.loc[1,"HH_EMISSAO_BU"]="bad"
    df.to_csv(path, sep=";", index=False, encoding="utf-8-sig")
    with pytest.raises(ValueError):
        build_analysis_data(path)
