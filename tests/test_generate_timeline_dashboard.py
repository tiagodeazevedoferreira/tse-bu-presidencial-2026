import pandas as pd

from scripts.generate_timeline_dashboard import (
    build_analysis_data,
    parse_time_minutes,
    prepare_analysis_payload,
)


def make_csv(path):
    df = pd.DataFrame({
        "SG_UF": ["RR", "RR", "AC"],
        "CD_MUNICIPIO": ["001", "001", "002"],
        "NM_MUNICIPIO": ["Boa Vista", "Boa Vista", "Rio Branco"],
        "NR_SECAO": ["1", "2", "3"],
        "NR_LOCAL_VOTACAO": ["Escola A", "Escola A", "Escola B"],
        "DT_ENCERRAMENTO": [
            "04/10/2026 07:11:00",
            "05/10/2026 07:12:00",
            "06/10/2026 07:13:00",
        ],
        "DT_EMISSAO_BU": [
            "04/10/2026 07:20:00",
            "05/10/2026 07:12:00",
            "06/10/2026 07:14:00",
        ],
        "DT_BU_RECEBIDO": [
            "04/10/2026 07:30:00",
            "05/10/2026 07:12:00",
            "06/10/2026 07:15:00",
        ],
        "VOTOS_FLAVIO_BOLSONARO": ["10", "20", "30"],
        "VOTOS_LULA": ["5", "8", "15"],
        "TOTAL_VOTOS_PRES": ["16", "29", "46"],
        # DT_ABERTURA is deliberately present: it must be ignored.
        "DT_ABERTURA": [
            "04/10/2026 01:00:00",
            "05/10/2026 01:00:00",
            "06/10/2026 01:00:00",
        ],
    })
    df.to_csv(path, sep=";", index=False, encoding="utf-8-sig")


def test_parse_time_minutes_ignores_date(tmp_path):
    values = pd.Series(["04/10/2026 07:12:59", "05/11/2030 07:13:01"])
    parsed = parse_time_minutes(values, "DT_TEST")
    assert parsed.tolist() == [432, 433]


def test_analysis_uses_only_three_event_fields(tmp_path):
    path = tmp_path / "national.csv"
    make_csv(path)

    data = build_analysis_data(path)
    assert set(data["event_counts"]) == {
        "DT_ENCERRAMENTO", "DT_EMISSAO_BU", "DT_BU_RECEBIDO"
    }
    assert "DT_ABERTURA" not in data["event_counts"]
    assert data["event_counts"]["DT_ENCERRAMENTO"]["RR"]["431"] == 1
    assert data["event_counts"]["DT_ENCERRAMENTO"]["RR"]["432"] == 1
    assert data["event_counts"]["DT_ENCERRAMENTO"]["AC"]["433"] == 1


def test_payload_contains_municipalities_and_sections(tmp_path):
    path = tmp_path / "national.csv"
    make_csv(path)

    payload = prepare_analysis_payload(build_analysis_data(path))
    assert payload["municipalities"]["RR"] == [{"code": "001", "name": "Boa Vista"}]
    assert len(payload["sections"]) == 3
    assert payload["sections"][0][0] == "RR"
    assert payload["sections"][0][4:] == [431, 440, 450, 10, 5, 16]


def test_missing_event_timestamp_is_skipped(tmp_path):
    path = tmp_path / "national.csv"
    make_csv(path)
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str)
    df.loc[1, "DT_EMISSAO_BU"] = ""
    df.to_csv(path, sep=";", index=False, encoding="utf-8-sig")

    data = build_analysis_data(path)
    assert "432" not in data["event_counts"]["DT_EMISSAO_BU"]["RR"]
    assert data["event_counts"]["DT_EMISSAO_BU"]["RR"]["440"] == 1
