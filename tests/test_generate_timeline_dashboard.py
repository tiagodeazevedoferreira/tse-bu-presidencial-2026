import pandas as pd

from scripts.generate_timeline_dashboard import build_series, prepare_payload


def make_csv(path):
    df = pd.DataFrame({
        "SG_UF": ["RR", "RR", "AC"],
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
