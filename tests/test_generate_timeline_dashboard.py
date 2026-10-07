import pandas as pd

from scripts.generate_timeline_dashboard import build_event_series, build_series, prepare_payload


def make_csv(path):
    df = pd.DataFrame({
        "SG_UF": ["RR", "RR", "AC"],
        "DT_ABERTURA": [
            "04/10/2026 17:00:00",
            "04/10/2026 17:01:00",
            "04/10/2026 17:02:00",
        ],
        "DT_ENCERRAMENTO": [
            "04/10/2026 17:30:00",
            "04/10/2026 17:31:00",
            "04/10/2026 17:32:00",
        ],
        "DT_EMISSAO_BU": [
            "04/10/2026 17:40:00",
            "04/10/2026 17:41:00",
            "04/10/2026 17:42:00",
        ],
        "DT_BU_RECEBIDO": [
            "04/10/2026 18:01:00",
            "04/10/2026 18:04:59",
            "04/10/2026 18:06:00",
        ],
    })
    df.to_csv(path, sep=";", index=False, encoding="utf-8-sig")


def test_timeline_preserves_section_count_and_bins(tmp_path):
    path = tmp_path / "national.csv"
    make_csv(path)

    counts, totals = build_series(path)
    assert totals["RR"] == 2
    assert totals["AC"] == 1
    assert totals["BR"] == 3
    assert counts["RR"]["2026-10-04T18:00"] == 2
    assert "2026-10-04T18:05" not in counts["RR"]
    assert counts["AC"]["2026-10-04T18:05"] == 1


def test_payload_cumulative_percentage_reaches_100():
    counts = {
        "RR": {
            "2026-10-04T18:00": 2,
            "2026-10-04T18:05": 1,
        }
    }
    totals = {"RR": 3}
    payload = prepare_payload(counts, totals)
    assert payload["series"]["RR"][-1]["cum"] == 3
    assert payload["series"]["RR"][-1]["pct"] == 100.0


def test_payload_exposes_peak_and_completion_milestones():
    counts = {
        "RR": {
            "2026-10-04T18:00": 1,
            "2026-10-04T18:05": 2,
            "2026-10-04T18:10": 1,
        }
    }
    totals = {"RR": 4}
    payload = prepare_payload(counts, totals)
    kpi = payload["kpis"]["RR"]

    assert kpi["peak_count"] == 2
    assert kpi["peak_time"] == "2026-10-04T18:05"
    assert kpi["milestones"]["25"] == "2026-10-04T18:00"
    assert kpi["milestones"]["50"] == "2026-10-04T18:05"
    assert kpi["milestones"]["100"] == "2026-10-04T18:10"
    assert kpi["duration_25_95_min"] == 10
    assert kpi["duration_90_100_min"] == 0
    assert kpi["peak_share_pct"] == 50.0


def test_event_timeline_preserves_all_four_event_series(tmp_path):
    path = tmp_path / "national.csv"
    make_csv(path)

    event_counts, event_totals = build_event_series(path)
    assert set(event_counts) == {
        "DT_ABERTURA", "DT_ENCERRAMENTO", "DT_EMISSAO_BU", "DT_BU_RECEBIDO"
    }
    assert event_totals["DT_ABERTURA"]["RR"] == 2
    assert event_counts["DT_BU_RECEBIDO"]["RR"]["2026-10-04T18:00"] == 2

    counts, totals = build_series(path)
    payload = prepare_payload(counts, totals, event_counts, event_totals)
    assert set(payload["events"]) == set(event_counts)
    for event in event_counts:
        assert payload["events"][event]["RR"][-1]["pct"] == 100.0

