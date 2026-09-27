"""Regressões para as consultas compostas, com valores independentes conhecidos."""
import pandas as pd
import pytest
from dashboard.analysis_queries import interpret, calculate, UnsupportedAnalysis

FILTERS = {"start": "2026-01-01", "end": "2026-03-31", "region": [], "category": []}
DIMENSIONS = {"region": ["Sul", "Norte"], "category": ["Casa", "Tecnologia"], "product": ["Monitor", "Caderno"]}

def orders():
    return pd.DataFrame([
        dict(sold_on=pd.Timestamp("2026-01-01"), status="concluida", revenue_cents=10000, units=2, region="Sul", category="Casa", product="Monitor"),
        dict(sold_on=pd.Timestamp("2026-01-31"), status="cancelada", revenue_cents=1000, units=1, region="Norte", category="Tecnologia", product="Caderno"),
        dict(sold_on=pd.Timestamp("2026-03-31"), status="concluida", revenue_cents=20000, units=1, region="Sul", category="Casa", product="Monitor"),
    ])

def result(q, filters=FILTERS, coverage=("2026-01-01", "2026-03-31")):
    spec = interpret(q, filters, DIMENSIONS)
    return calculate(orders(), spec, coverage)

@pytest.mark.parametrize("question", ["Mostre os valores mês a mês", "Faturamento mensal", "Quanto vendemos por mês?"])
def test_monthly_phrasings(question):
    data = result(question)["evidence"]["data"]
    assert [r["month"] for r in data] == ["2026-01", "2026-02", "2026-03"]
    assert [r["revenue"] for r in data] == [10000, 0, 20000]
    assert [r["change"] for r in data] == [None, -100.0, None]

def test_multiple_metrics_and_rate():
    reply = result("Faça uma análise completa das vendas")
    assert len(reply["evidence"]["metrics"]) == 6
    january = reply["evidence"]["data"][0]
    assert january["orders"] == 1
    assert january["ticket"] == 10000
    assert january["cancel_rate"] == 50
    assert "R$ 300,00" in reply["answer"]

def test_explicit_month_comparison_and_filters():
    spec = interpret("Compare o faturamento de janeiro e março de 2026 no Sul", FILTERS, DIMENSIONS)
    assert spec["filters"]["region"] == ["Sul"]
    assert spec["months"] == [1, 3]
    reply = calculate(orders(), spec, ("2026-01-01", "2026-03-31"))
    assert len(reply["evidence"]["data"]) == 2
    assert reply["evidence"]["data"][1]["change"] == 100
    assert "+100,00%" in reply["answer"]

def test_named_range_includes_middle_month():
    spec = interpret("Faturamento de janeiro a março de 2026", FILTERS, DIMENSIONS)
    assert spec["months"] == [1, 2, 3]

@pytest.mark.parametrize("question", ["quanto ela faturou no mes 5", "valor do faturamento do Norte do mês 05", "faturamento mes5"])
def test_numeric_month_from_real_questions(question):
    spec = interpret(question, FILTERS, DIMENSIONS)
    assert spec["filters"]["start"] == "2026-05-01"
    assert spec["filters"]["end"] == "2026-05-31"
    assert spec["months"] == [5]
    if "Norte" in question:
        assert spec["filters"]["region"] == ["Norte"]

def test_invalid_month_not_ignored():
    with pytest.raises(UnsupportedAnalysis):
        interpret("faturamento do mes 13", FILTERS, DIMENSIONS)

def test_reverse_comparison_and_named_regions():
    spec = interpret("Compare faturamento de março com janeiro", FILTERS, DIMENSIONS)
    assert spec["groups"] == ["month"]
    assert spec["filters"]["start"] == "2026-01-01"
    spec = interpret("Compare as vendas do Sul e Norte", FILTERS, DIMENSIONS)
    assert spec["groups"] == ["region"]

def test_two_dimensions_compute_growth_per_series():
    data = result("Faturamento e ticket médio por mês e região")["evidence"]["data"]
    assert len(data) == 6
    south = [r for r in data if r["region"] == "Sul"]
    assert [r["revenue"] for r in south] == [10000, 0, 20000]
    assert south[1]["change"] == -100

def test_top_products_share_uses_full_recorte():
    reply = result("Top 1 produtos por faturamento")
    assert len(reply["evidence"]["data"]) == 1
    assert reply["evidence"]["data"][0]["product"] == "Monitor"
    assert reply["evidence"]["data"][0]["share"] == 100

def test_partial_and_unavailable_months():
    reply = result("Faturamento por mês", {**FILTERS, "end": "2026-04-30"}, ("2026-01-01", "2026-03-24"))
    data = reply["evidence"]["data"]
    assert data[2]["coverage"] == "Parcial"
    assert data[3]["coverage"] == "Sem cobertura"
    assert data[3]["revenue"] is None
    assert "meses parciais" in reply["answer"]

@pytest.mark.parametrize("q", ["Faturamento e lucro por mês", "Faturamento do ano passado", "Vendas de 01/01/2026 a 10/01/2026", "Vendas de dezembro a janeiro", "Faturamento por cidade"])
def test_unsupported_constraints_are_not_ignored(q):
    with pytest.raises(UnsupportedAnalysis):
        interpret(q, FILTERS, DIMENSIONS)

def test_rule_questions_still_reach_knowledge():
    assert interpret("Como vocês calculam o faturamento?", FILTERS, DIMENSIONS) is None
    assert interpret("Qual é o prazo de entrega?", FILTERS, DIMENSIONS) is None
