"""Regras financeiras verificadas com valores conhecidos, inclusive cancelamento."""
import pandas as pd
import pytest
from dashboard.analytics import metric_value, grouped, metric_answer, money

def frame():
    return pd.DataFrame([
        {"sold_on": pd.Timestamp("2026-09-01"), "status": "concluida", "units": 2, "revenue_cents": 20000, "region": "Sul"},
        {"sold_on": pd.Timestamp("2026-09-02"), "status": "concluida", "units": 1, "revenue_cents": 5001, "region": "Norte"},
        {"sold_on": pd.Timestamp("2026-09-03"), "status": "cancelada", "units": 10, "revenue_cents": 999999, "region": "Sul"},
    ])

def test_totals_exclude_cancelled_and_round_half_up():
    df = frame()
    assert metric_value(df, "revenue") == 25001
    assert metric_value(df, "orders") == 2
    assert metric_value(df, "ticket") == 12501
    assert metric_value(df, "units") == 3
    assert metric_value(df, "cancellations") == 1
    assert money(25001) == "R$ 250,01"

def test_grouping_and_empty_selection():
    result = grouped(frame(), "revenue", "region")
    assert result.iloc[0].to_dict() == {"grupo": "Sul", "valor": 20000}
    assert metric_value(frame().iloc[:0], "ticket") == 0
    assert "Não há pedidos" in metric_answer(frame().iloc[:0], "revenue", "none", {"start": "2026-01-01", "end": "2026-01-02"})

def test_arbitrary_operations_are_rejected():
    with pytest.raises(ValueError):
        grouped(frame(), "DROP TABLE sales", "none")
    with pytest.raises(ValueError):
        grouped(frame(), "revenue", "__dict__")
