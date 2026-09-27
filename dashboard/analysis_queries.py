"""Análises compostas em português, com operações fechadas e resultados auditáveis.

Interpreta pedidos analíticos comuns sem depender da classificação de um modelo
pequeno. Não executa texto como código. A IA continua atendendo outras formulações
e buscando conhecimento. Datas/dimensões explícitas substituem o filtro correspondente
do painel; todo resultado informa o recorte efetivo.
"""
import calendar
import re
from datetime import date, datetime, timezone
import pandas as pd
from .text import normalize
from .analytics import METRICS, metric_value, format_value

MONTHS = dict(zip("janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro".split(), range(1, 13)))
LABELS = {"month": "Mês", "region": "Região", "category": "Categoria", "product": "Produto"}

class UnsupportedAnalysis(ValueError):
    """Pede esclarecimento sem responder apenas uma parte da pergunta."""

def contains(q, pattern):
    return bool(re.search(pattern, q))

def interpret(question, filters, dimensions):
    q = normalize(question)
    # Explicações de regras continuam passando pela busca de conhecimento.
    if contains(q, r"\bcomo\b.*\b(calcul\w*|defin\w*)|\b(o que e|o que significa|formula|politica|prazo)\b"):
        return None
    requested_percentage = contains(q, r"porcentagem|percentagem|percentual|participacao") or "%" in question
    analytical = contains(q, r"\b(fatur\w*|receita|vend\w*|vendas|valores|ticket|pedidos|unidades|cancel\w*|ranking|analise|resumo|mes a mes|mensal|crescimento|variacao|compare|comparar)\b") or requested_percentage
    if not analytical and contains(q, r"\bregiao\b|\bregioes\b"):
        raise UnsupportedAnalysis("Qual indicador você quer comparar entre as regiões: faturamento, pedidos concluídos, unidades, ticket médio ou cancelamentos?")
    if not analytical:
        return None
    if contains(q, r"\b(lucro|margem|custo\w*|previ\w*|projec\w*|meta\w*|cliente\w*|imposto\w*|desconto\w*|mediana|desvio|correlacao|trimestre|seman\w*|cidade\w*|estado\w*|vendedor\w*)\b"):
        raise UnsupportedAnalysis("Essa análise pede uma medida ou dimensão ainda não disponível. Posso analisar faturamento, pedidos, ticket, unidades e cancelamentos por mês, região, categoria ou produto.")
    if contains(q, r"\b(exceto|excluindo|sem a|sem o|ano passado|ano anterior|mes passado|mes anterior|periodo anterior|ultimos|ontem|hoje|amanha|acumulad\w*)\b"):
        raise UnsupportedAnalysis("Para essa condição, informe meses e ano explicitamente ou ajuste os filtros. Não vou ignorar a restrição pedida.")
    metrics = []
    if contains(q, r"\b(fatur\w*|receita|valor\w*|vendemos|vendeu|vendas)\b"):
        metrics.append("revenue")
    if contains(q, r"\b(pedidos|compras)\b") and (not contains(q, r"pedidos (foram )?cancelad|taxa de cancelamento") or contains(q, r"concluid|aprovad|pedidos e|e pedidos")):
        metrics.append("orders")
    if "ticket" in q:
        metrics.append("ticket")
    if contains(q, r"\b(unidades|quantidade de produtos|itens vendidos)\b"):
        metrics.append("units")
    if "cancel" in q:
        rate = (contains(q, r"taxa|percentual|porcentagem|percentagem") or "%" in question) and "participacao" not in q
        metrics.append("cancel_rate" if rate else "cancellations")
        if "orders" in metrics and not contains(q, r"concluid|aprovad|pedidos e|e pedidos"):
            metrics.remove("orders")
    if "units" in metrics and "revenue" in metrics and not contains(q, r"fatur|receita|valor"):
        metrics.remove("revenue")
    summary = contains(q, r"\b(analise|resumo|panorama|relatorio)\b")
    if summary and (not metrics or metrics == ["revenue"]):
        metrics = ["revenue", "orders", "ticket", "units", "cancellations", "cancel_rate"]
    if not metrics and contains(q, r"mais vendidos|menos vendidos"):
        metrics = ["units"]
    if not metrics:
        metrics = ["revenue"]
    effective = {**filters, "region": list(filters.get("region", [])), "category": list(filters.get("category", []))}
    explicit = []
    for field in ("region", "category", "product"):
        matches = [v for v in dimensions.get(field, []) if contains(q, r"\b" + re.escape(normalize(v)) + r"\b")]
        if matches:
            effective[field] = matches
            explicit.append(LABELS[field])

    years = list(dict.fromkeys(int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", q)))
    if len(years) > 1:
        raise UnsupportedAnalysis("Para comparar anos diferentes, selecione o intervalo no painel e peça a evolução mês a mês. Nesta versão, meses escritos na pergunta usam um único ano.")
    year = years[0] if years else date.fromisoformat(filters["end"]).year
    month_mentions = [(m.start(), MONTHS[m.group()]) for m in re.finditer(r"\b(" + "|".join(MONTHS) + r")\b", q)]
    # Aceita a forma usada no painel: 'mês 5', 'mês 05' e 'mês de 5'.
    for match in re.finditer(r"\bmes\s*(?:de\s+)?(\d+)\b", q):
        number = int(match.group(1))
        if number not in range(1, 13):
            raise UnsupportedAnalysis("O número do mês deve estar entre 1 e 12.")
        month_mentions.append((match.start(), number))
    named = [number for _, number in sorted(month_mentions)]
    compare = contains(q, r"compar| versus |\bvs\b|diferenca|crescimento|variacao|evolucao|aument|caiu|queda")
    notes = []
    if named:
        named = list(dict.fromkeys(named))
        if len(named) > 1 and named[-1] < named[0] and not compare:
            raise UnsupportedAnalysis("O intervalo atravessa anos. Selecione as datas no painel e peça a análise mensal.")
        if len(named) == 2 and contains(q, r"\b(de|entre)\b.*\b(a|ate)\b") and not contains(q, r"compar|versus|\bvs\b"):
            named = list(range(named[0], named[-1] + 1))
        effective["start"] = date(year, min(named), 1).isoformat()
        effective["end"] = date(year, max(named), calendar.monthrange(year, max(named))[1]).isoformat()
        explicit.append("Período")
        if not years:
            notes.append(f"Ano assumido: {year}, com base na data final do painel.")
    elif years:
        effective["start"], effective["end"] = f"{year}-01-01", f"{year}-12-31"
        explicit.append("Período")
    # Datas numéricas exigem seleção no painel; não fingir ter interpretado.
    if re.search(r"\d{1,4}[-/]\d{1,2}", question):
        raise UnsupportedAnalysis("Selecione as datas numéricas no painel ou escreva os meses por extenso, por exemplo: de abril a junho de 2026.")
    groups = []
    if named and len(named) > 1 or contains(q, r"mes a mes|mensal|mensais|por mes|cada mes|e mes\b|meses|evolucao|crescimento|variacao|melhor mes|pior mes") or summary:
        groups.append("month")
    for field, pattern in (("region", r"\bregiao\b|\bregioes\b"), ("category", r"por categoria|categorias|cada categoria|e categoria"), ("product", r"por produto|produtos|cada produto|e produto")):
        if contains(q, pattern) or compare and len(effective.get(field, [])) > 1 and LABELS[field] in explicit:
            groups.append(field)
    if requested_percentage and "Região" in explicit and "region" not in groups:
        groups.append("region")
    if compare and named and len(named) == 1 and not groups:
        raise UnsupportedAnalysis("Informe dois meses para comparar, por exemplo agosto e setembro de 2026.")
    if len(groups) > 2:
        raise UnsupportedAnalysis("Use até dois agrupamentos por consulta, por exemplo mês e região.")
    limit = None
    top = re.search(r"\b(?:top|primeiros|melhores|piores)\s+(\d+)\b", q)
    if top:
        limit = min(max(int(top.group(1)), 1), 50)
    rank = top is not None or contains(q, r"ranking|maior|menor|melhor|pior|mais vende|mais vendido|menos vendido") or ("region" in groups and contains(q, r"\bmais\b|\bmenos\b"))
    if rank and not groups:
        if contains(q, r"\bregiao\b"):
            groups = ["region"]
        elif contains(q, r"\bcategoria\b"):
            groups = ["category"]
        elif contains(q, r"\bproduto\b"):
            groups = ["product"]
        else:
            groups = ["month"]
    if rank and len(groups) > 1:
        raise UnsupportedAnalysis("Para um ranking, escolha um agrupamento por pergunta. Posso mostrar a evolução por mês e região sem limitar ao top.")
    if explicit:
        notes.append("Filtros informados na pergunta substituíram o painel em: " + ", ".join(explicit) + ".")
    if contains(q, r"por que|porque|motivo|causa"):
        notes.append("Os dados mostram variações, mas não permitem afirmar a causa. A análise abaixo é descritiva.")
    if requested_percentage and metrics == ["revenue"] and not contains(q, r"fatur|receita|vend|valor"):
        notes.append("Participação interpretada como participação no faturamento.")
    return dict(metrics=metrics, groups=groups, filters=effective, months=named, notes=notes,
                rank=rank, limit=limit, ascending=contains(q, r"pior|menor|\bmenos\b"), compare=compare,
                percentage=requested_percentage, regional_denominator=requested_percentage and "Região" in explicit and "region" in groups)

def percentage(value):
    return "N/D" if value is None else f"{value:+.2f}%".replace(".", ",")

def calculate(df, spec, coverage, denominator_df=None):
    """Retorna texto, tabela e gráfico serializáveis; a evidência salva os números."""
    metrics, groups, filters = spec["metrics"], spec["groups"], spec["filters"]
    if any(m not in METRICS for m in metrics) or any(g not in LABELS for g in groups):
        raise UnsupportedAnalysis("Operação analítica inválida.")
    periods = pd.period_range(filters["start"], filters["end"], freq="M")
    if len(periods) > 36:
        raise UnsupportedAnalysis("Limite esta análise a até 36 meses por consulta.")
    if spec["months"]:
        periods = [p for p in periods if p.month in spec["months"]]
    df = df.copy()
    df["month"] = df["sold_on"].dt.strftime("%Y-%m")
    if spec["months"]:
        df = df[df["sold_on"].dt.month.isin(spec["months"])]
    notes = list(spec["notes"])
    cov_start, cov_end = pd.Timestamp(coverage[0]), pd.Timestamp(coverage[1])
    start, end = pd.Timestamp(filters["start"]), pd.Timestamp(filters["end"])
    if start < cov_start or end > cov_end:
        notes.append(f"Cobertura de registros do banco: {cov_start:%d/%m/%Y} a {cov_end:%d/%m/%Y}. Datas fora dessa cobertura não são tratadas como vendas zero.")
    raw = []
    if "month" in groups:
        other = next((g for g in groups if g != "month"), None)
        values = sorted(df[other].unique()) if other else [None]
        for p in periods:
            for value in values:
                part = df[df["month"] == str(p)]
                if other:
                    part = part[part[other] == value]
                observed = max(p.start_time.normalize(), start, cov_start) <= min(p.end_time.normalize(), end, cov_end)
                complete = start <= p.start_time.normalize() and end >= p.end_time.normalize() and cov_start <= p.start_time.normalize() and cov_end >= p.end_time.normalize()
                row = {"month": str(p), "coverage": "Completo" if complete else "Parcial" if observed else "Sem cobertura"}
                if other:
                    row[other] = str(value)
                row.update({m: metric_value(part, m) if observed else None for m in metrics})
                raw.append(row)
        if any(r["coverage"] == "Parcial" for r in raw):
            notes.append("Há meses parciais. Variações com esses meses comparam valores observados, não meses completos equivalentes.")
    elif groups:
        for keys, part in df.groupby(groups, sort=True):
            keys = keys if isinstance(keys, tuple) else (keys,)
            raw.append({**dict(zip(groups, map(str, keys))), **{m: metric_value(part, m) for m in metrics}})
    elif not df.empty:
        raw = [{"total": "Total", **{m: metric_value(df, m) for m in metrics}}]
    primary = metrics[0]
    if "month" in groups:
        previous = {}
        for row in raw:
            key = tuple(row[g] for g in groups if g != "month")
            before = previous.get(key)
            current = row[primary]
            row["change"] = ((current - before) / before * 100) if before is not None and before != 0 and current is not None else None
            previous[key] = current
    if groups:
        base = df if denominator_df is None else denominator_df.copy()
        if spec["months"]:
            base = base[base["sold_on"].dt.month.isin(spec["months"])]
        for row in raw:
            denominator = base[base["sold_on"].dt.strftime("%Y-%m") == row["month"]] if "month" in row and len(groups) > 1 else base
            row["shares"] = {}
            row["denominators"] = {}
            for metric in metrics:
                if metric not in ("ticket", "cancel_rate"):
                    total = metric_value(denominator, metric)
                    row["denominators"][metric] = total
                    row["shares"][metric] = row[metric] / total * 100 if total and row[metric] is not None else None
            if primary in row["shares"]:
                row["share"] = row["shares"][primary]
        notes.append("Participação (%) = valor do grupo ÷ total do recorte. Em mês + região, o denominador é o total daquele mês. Base zero é N/D.")
        if denominator_df is not None:
            notes.append("Para a participação da região nomeada, o denominador inclui todas as regiões, mantendo período, categoria e produto.")
        if any(m == "cancel_rate" for m in metrics):
            notes.append("Taxa de cancelamento (%) = pedidos cancelados da região/grupo ÷ todos os pedidos desse mesmo grupo; não é participação no total de cancelamentos.")
    if spec["rank"] or groups and "month" not in groups:
        raw.sort(key=lambda r: (r[primary] is None, (r[primary] or 0) * (1 if spec["ascending"] else -1)))
    if spec["limit"]:
        raw = raw[:spec["limit"]]
        notes.append(f"Exibindo até {spec['limit']} resultados; participação calculada sobre todo o recorte.")
    if len(raw) > 240:
        raise UnsupportedAnalysis("O resultado ultrapassa 240 linhas. Reduza o período ou os agrupamentos.")
    table = []
    for r in raw:
        row = {LABELS[g]: r[g] for g in groups} if groups else {"Recorte": "Total"}
        for m in metrics:
            row[METRICS[m]] = format_value(r[m], m) if r[m] is not None else "N/D"
        if "change" in r:
            row[f"Variação de {METRICS[primary]} (%)"] = percentage(r["change"])
        for m, share in r.get("shares", {}).items():
            row[f"Participação em {METRICS[m]} (%)"] = "N/D" if share is None else f"{share:.2f}%".replace(".", ",")
        if "coverage" in r:
            row["Cobertura"] = r["coverage"]
        table.append(row)
    scope = f"Período consultado: {filters['start']} a {filters['end']}. "
    scope += " · ".join(f"{LABELS[g]}: {', '.join(filters.get(g) or ['todos'])}" for g in ("region", "category", "product"))
    text = [scope]
    if df.empty:
        text.append("Não há pedidos registrados no recorte consultado.")
    else:
        text.append("**Resumo do recorte:** " + "; ".join(f"{METRICS[m]}: {format_value(metric_value(df, m), m)}" for m in metrics) + ".")
        if groups == ["month"]:
            valid = [r for r in raw if r[primary] is not None]
            if valid:
                best = max(valid, key=lambda r: r[primary])
                if spec["rank"]:
                    best = valid[0]
                    text.append(f"Primeiro mês no ranking solicitado: **{best['month']}**, com **{format_value(best[primary], primary)}**.")
                else:
                    text.append(f"Maior {METRICS[primary].lower()} observado: **{best['month']}**, com **{format_value(best[primary], primary)}**.")
            if len(valid) > 1 and spec["compare"] and not spec["rank"]:
                first, last = valid[0], valid[-1]
                delta = last[primary] - first[primary]
                pct = delta / first[primary] * 100 if first[primary] else None
                unit = " pontos percentuais" if primary == "cancel_rate" else ""
                difference = f"{delta:+.2f}{unit}" if primary == "cancel_rate" else format_value(delta, primary)
                text.append(f"De {first['month']} para {last['month']}: diferença de {difference}; variação relativa de {percentage(pct)}.")
        elif groups and raw:
            name = " / ".join(str(raw[0][g]) for g in groups)
            direction = "Menor" if spec["ascending"] else "Maior"
            text.append(f"{direction} {METRICS[primary].lower()}: **{name}**, com **{format_value(raw[0][primary], primary)}**.")
            ties = [" / ".join(str(r[g]) for g in groups) for r in raw[1:] if r[primary] == raw[0][primary]]
            if ties:
                text.append("Empate nesse valor com: " + ", ".join(ties) + ".")
            if raw[0].get("share") is not None:
                share_text = f"{raw[0]['share']:.2f}%".replace(".", ",")
                text.append(f"Participação desse resultado: **{share_text}** do total de {METRICS[primary].lower()} usado como base.")
    if "month" in groups:
        notes.append("Variação calculada contra o mês listado anteriormente na mesma série. N/D indica ausência de base ou base zero. Taxa de cancelamento = cancelados ÷ todos os pedidos.")
    text.extend(notes)
    chart = []
    for r in raw:
        if r[primary] is not None:
            chart.append({"Recorte": " / ".join(str(r[g]) for g in groups) if groups else "Total",
                          "Valor": r[primary] / 100 if primary in ("revenue", "ticket") else r[primary]})
    return {"answered": True, "answer": "\n\n".join(text), "reason": None,
            "evidence": {"type": "metric", "method": "Análise estruturada em português • cálculos com pandas",
                "source": "PostgreSQL • tabela sales", "metric": primary, "metrics": metrics, "groups": groups,
                "filters": filters, "selected_months": spec["months"], "rows": len(df), "table": table, "data": raw,
                "percentage_base_filters": {**filters, "region": []} if denominator_df is not None else filters,
                "chart": chart, "chart_label": METRICS[primary] + (" (R$)" if primary in ("revenue", "ticket") else ""),
                "calculated_at": datetime.now(timezone.utc).isoformat()}}

def try_analysis(question, filters):
    from . import db
    dims = db.rows("SELECT DISTINCT region,category,product FROM sales")
    dimensions = {g: sorted({r[g] for r in dims}) for g in ("region", "category", "product")}
    from .period_comparison import try_comparison
    comparison = try_comparison(question, filters, dimensions)
    if comparison is not None:
        return comparison
    spec = interpret(question, filters, dimensions)
    if spec is None:
        return None
    bounds = db.rows("SELECT min(sold_on) AS first,max(sold_on) AS last FROM sales")[0]
    if not bounds["first"]:
        raise UnsupportedAnalysis("O banco ainda não tem pedidos para analisar.")
    denominator = db.sales_frame({**spec["filters"], "region": []}) if spec.get("regional_denominator") else None
    return calculate(db.sales_frame(spec["filters"]), spec, (bounds["first"], bounds["last"]), denominator)
