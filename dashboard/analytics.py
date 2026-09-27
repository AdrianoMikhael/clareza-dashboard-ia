"""Todas as contas são feitas com pandas, nunca pelo modelo de linguagem."""
from decimal import Decimal, ROUND_HALF_UP
import pandas as pd

METRICS = {"revenue": "Faturamento", "orders": "Pedidos concluídos", "ticket": "Ticket médio",
           "units": "Unidades vendidas", "cancellations": "Pedidos cancelados", "cancel_rate": "Taxa de cancelamento"}
GROUPS = {"none": "Total", "region": "Região", "category": "Categoria", "month": "Mês", "product": "Produto"}

def money(cents):
    value = f"{int(cents) / 100:,.2f}"
    return "R$ " + value.replace(",", "X").replace(".", ",").replace("X", ".")

def metric_value(df, metric):
    if metric not in METRICS:
        raise ValueError("Indicador não permitido.")
    completed = df[df["status"] == "concluida"]
    cents = int(completed["revenue_cents"].sum())
    if metric == "revenue":
        return cents
    if metric == "orders":
        return len(completed)
    if metric == "units":
        return int(completed["units"].sum())
    if metric == "cancellations":
        return int((df["status"] == "cancelada").sum())
    if metric == "cancel_rate":
        return float((df["status"] == "cancelada").sum() / len(df) * 100) if len(df) else 0.0
    return int((Decimal(cents) / len(completed)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if len(completed) else 0

def format_value(value, metric):
    if metric == "cancel_rate":
        return f"{value:.2f}%".replace(".", ",")
    return money(value) if metric in ("revenue", "ticket") else f"{value:,}".replace(",", ".")

def grouped(df, metric, group):
    if group not in GROUPS or metric not in METRICS:
        raise ValueError("Consulta não permitida.")
    if group == "none":
        return pd.DataFrame([{"grupo": "Total", "valor": metric_value(df, metric)}])
    copy = df.copy()
    if group == "month":
        copy["month"] = copy["sold_on"].dt.strftime("%Y-%m")
    items = [{"grupo": str(name), "valor": metric_value(part, metric)} for name, part in copy.groupby(group)]
    result = pd.DataFrame(items, columns=["grupo", "valor"])
    return result.sort_values("grupo" if group == "month" else "valor", ascending=group == "month")

def metric_answer(df, metric, group, filters):
    period = f"{filters['start']} a {filters['end']}"
    scope = f"Regiões: {', '.join(filters.get('region') or ['todas'])}. Categorias: {', '.join(filters.get('category') or ['todas'])}."
    if df.empty:
        return f"Não há pedidos no recorte de {period}. {scope}"
    result = grouped(df, metric, group)
    lines = [f"{row.grupo}: {format_value(row.valor, metric)}" for row in result.itertuples()]
    return f"{METRICS[metric]} — {period}\n\n" + "\n\n".join(lines) + f"\n\n{scope}"
