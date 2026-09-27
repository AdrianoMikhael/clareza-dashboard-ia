"""Comparações com datas, agregação correta e falta de cobertura explícita."""
from datetime import date
import pandas as pd
import pytest
from dashboard.period_comparison import periods_from_question, build_comparison
from dashboard.analysis_queries import UnsupportedAnalysis

F = dict(start="2026-04-01", end="2026-09-24", region=[], category=[])

@pytest.mark.parametrize("q,expected", [
    ("Compare junho com julho em faturamento e ticket médio", [("2026-06-01","2026-06-30"),("2026-07-01","2026-07-31")]),
    ("Julho x junho: faturamento", [("2026-07-01","2026-07-31"),("2026-06-01","2026-06-30")]),
    ("Compare abril a junho com julho a setembro", [("2026-04-01","2026-06-30"),("2026-07-01","2026-09-30")]),
    ("Compare 01/04/2026 a 30/06/2026 com 01/07/2026 a 24/09/2026", [("2026-04-01","2026-06-30"),("2026-07-01","2026-09-24")]),
    ("Compare primeiro semestre com segundo semestre de 2026", [("2026-01-01","2026-06-30"),("2026-07-01","2026-12-31")]),
    ("Compare 2025 com 2026", [("2025-01-01","2025-12-31"),("2026-01-01","2026-12-31")]),
    ("Compare junho de 2025 com junho de 2026", [("2025-06-01","2025-06-30"),("2026-06-01","2026-06-30")]),
])
def test_period_parser(q, expected):
    windows, _ = periods_from_question(q, F)
    assert [(s.isoformat(), e.isoformat()) for s,e in windows] == expected

@pytest.mark.parametrize("q", ["Compare 31/02/2026 a 30/06/2026 com 01/07/2026 a 30/09/2026", "Compare setembro a junho com julho a agosto", "Compare junho de 2025 com julho e agosto de 2026"])
def test_invalid_or_ambiguous_periods(q):
    with pytest.raises(UnsupportedAnalysis):
        periods_from_question(q, F)

def data(values, cancelled=0):
    rows = [dict(status="concluida", revenue_cents=v, units=1) for v in values]
    rows += [dict(status="cancelada", revenue_cents=99999, units=1)] * cancelled
    return pd.DataFrame(rows, columns=["status","revenue_cents","units"])

def test_all_metrics_compare_independently():
    windows, _ = periods_from_question("Compare junho com julho", F)
    reply = build_comparison([data([10000,30000], 2), data([15000,15000,30000], 1)], windows,
                             ["revenue","ticket","orders","cancel_rate"], (date(2026,4,1),date(2026,9,24)),F)
    raw = {r["metric"]:r for r in reply["evidence"]["data"]}
    assert raw["revenue"]["change_pct"] == 50
    assert raw["orders"]["change_pct"] == 50
    assert raw["ticket"]["a"] == 20000 and raw["ticket"]["b"] == 20000
    assert raw["ticket"]["change_pct"] == 0
    assert raw["cancel_rate"]["difference"] == -25
    assert raw["cancel_rate"]["change_pct"] == -50
    assert "durações diferentes" in reply["answer"]

def test_no_coverage_and_zero_baseline():
    windows, _ = periods_from_question("Compare 2025 com 2026", F)
    reply = build_comparison([data([]),data([10000])], windows,["revenue","ticket"],(date(2026,4,1),date(2026,9,24)),F)
    assert reply["evidence"]["periods"][0]["coverage"] == "Sem cobertura"
    assert reply["evidence"]["periods"][1]["coverage"] == "Parcial"
    assert reply["evidence"]["data"][0]["a"] is None
    assert reply["evidence"]["data"][0]["change_pct"] is None
    windows,_=periods_from_question("Compare junho com julho",F)
    reply=build_comparison([data([]),data([10000])],windows,["revenue","ticket"],(date(2026,4,1),date(2026,9,24)),F)
    assert reply["evidence"]["data"][0]["a"] == 0
    assert reply["evidence"]["data"][0]["change_pct"] is None
    assert reply["evidence"]["data"][1]["a"] is None

def test_single_month_with_percentage_is_not_comparison():
    assert periods_from_question("Faturamento de maio com porcentagem", F) is None
