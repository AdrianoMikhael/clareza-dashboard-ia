"""Perguntas regionais em linguagem natural e denominadores de porcentagem."""
import pandas as pd
import pytest
from dashboard.analysis_queries import interpret, calculate, UnsupportedAnalysis

FILTERS = dict(start="2026-05-01", end="2026-05-31", region=[], category=[])
DIMS = dict(region=["Sul", "Norte"], category=["Casa"], product=["Monitor"])

def frame():
    return pd.DataFrame([
        dict(sold_on=pd.Timestamp("2026-05-01"), region="Sul", category="Casa", product="Monitor", status="concluida", units=2, revenue_cents=30000),
        dict(sold_on=pd.Timestamp("2026-05-02"), region="Norte", category="Casa", product="Monitor", status="concluida", units=4, revenue_cents=10000),
        dict(sold_on=pd.Timestamp("2026-05-31"), region="Norte", category="Casa", product="Monitor", status="cancelada", units=1, revenue_cents=90000),
    ])

@pytest.mark.parametrize("q,metric,ascending", [
    ("Qual região mais faturou?", "revenue", False),
    ("Qual região menos faturou?", "revenue", True),
    ("Mostre as regiões que mais faturaram", "revenue", False),
    ("Qual região vendeu mais unidades?", "units", False),
    ("Qual região teve mais pedidos concluídos?", "orders", False),
    ("Qual região cancelou mais pedidos?", "cancellations", False),
    ("Qual região teve a maior taxa de cancelamento?", "cancel_rate", False),
])
def test_regional_phrasings(q, metric, ascending):
    spec = interpret(q, FILTERS, DIMS)
    assert spec["groups"] == ["region"]
    assert spec["metrics"][0] == metric
    assert spec["ascending"] == ascending

def test_revenue_shares_ignore_cancelled_money():
    spec = interpret("Faturamento por região em porcentagem", FILTERS, DIMS)
    answer = calculate(frame(), spec, ("2026-05-01", "2026-05-31"))
    rows = answer["evidence"]["data"]
    assert rows[0]["region"] == "Sul"
    assert [r["share"] for r in rows] == [75, 25]
    assert sum(r["share"] for r in rows) == 100
    assert rows[0]["denominators"]["revenue"] == 40000

def test_named_region_uses_all_regions_as_denominator():
    spec = interpret("Qual a porcentagem do Sul no faturamento?", FILTERS, DIMS)
    assert spec["regional_denominator"]
    full = frame()
    answer = calculate(full[full.region == "Sul"], spec, ("2026-05-01", "2026-05-31"), full)
    assert answer["evidence"]["data"][0]["share"] == 75
    assert answer["evidence"]["percentage_base_filters"]["region"] == []

def test_cancel_rate_differs_from_share_of_cancellations():
    rate = calculate(frame(), interpret("Taxa de cancelamento por região", FILTERS, DIMS), ("2026-05-01", "2026-05-31"))
    assert rate["evidence"]["data"][0]["cancel_rate"] == 50
    share = calculate(frame(), interpret("Participação percentual nos cancelamentos por região", FILTERS, DIMS), ("2026-05-01", "2026-05-31"))
    assert share["evidence"]["data"][0]["share"] == 100

def test_missing_metric_requests_clarification():
    with pytest.raises(UnsupportedAnalysis):
        interpret("Qual região fez alguma coisa?", FILTERS, DIMS)

def test_zero_denominator_is_not_a_fictitious_percentage():
    df = frame()
    df["status"] = "cancelada"
    answer = calculate(df, interpret("Faturamento por região em porcentagem", FILTERS, DIMS), ("2026-05-01", "2026-05-31"))
    assert all(r["share"] is None for r in answer["evidence"]["data"])
