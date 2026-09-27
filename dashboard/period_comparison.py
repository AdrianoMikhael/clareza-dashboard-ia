"""Compara duas janelas explícitas: cada indicador é agregado em seu período.

Ticket médio usa faturamento / pedidos do período inteiro, não média das médias
mensais. Variação relativa é (B - A) / A. Nenhum valor é calculado pela IA.
"""
import calendar
import re
from datetime import date, datetime, timezone
from .analytics import METRICS, metric_value, format_value
from .text import normalize

def periods_from_question(question, filters):
    from .analysis_queries import MONTHS, UnsupportedAnalysis
    q = normalize(question)
    comparison = bool(re.search(r"compar|diferenca|variacao|versus|\bvs\b|\bcontra\b|\bcom\b|\bx\b|em relacao", q))
    if not comparison:
        return None
    default_year = date.fromisoformat(filters["end"]).year
    years = [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", q)]
    unique_years = list(dict.fromkeys(years))
    year = unique_years[0] if len(unique_years) == 1 else default_year
    notes = []

    def window(y1, m1, y2, m2):
        return (date(y1, m1, 1), date(y2, m2, calendar.monthrange(y2, m2)[1]))

    # Quatro datas explícitas constituem dois intervalos, na ordem da pergunta.
    dates = re.findall(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b", question)
    windows = None
    if dates:
        if len(dates) != 4:
            raise UnsupportedAnalysis("Para comparar intervalos, informe quatro datas: início e fim do período A e início e fim do período B. Ex.: 01/04/2026 a 30/06/2026 com 01/07/2026 a 24/09/2026.")
        try:
            parsed = [datetime.strptime(d, "%Y-%m-%d" if "-" in d else "%d/%m/%Y").date() for d in dates]
        except ValueError:
            raise UnsupportedAnalysis("Uma das datas é inválida. Use DD/MM/AAAA ou AAAA-MM-DD.")
        windows = [(parsed[0], parsed[1]), (parsed[2], parsed[3])]
    else:
        # Captura anos junto a cada mês, permitindo junho/2025 versus junho/2026
        # por extenso: 'junho de 2025 com junho de 2026'.
        month_pattern = r"\b(" + "|".join(MONTHS) + r")\b(?:\s+(?:de\s+)?((?:19|20)\d{2})\b)?"
        mentions = [(MONTHS[m.group(1)], int(m.group(2)) if m.group(2) else year, bool(m.group(2)))
                    for m in re.finditer(month_pattern, q)]
        if len(mentions) in (2, 4):
            if len(unique_years) > 1 and not all(m[2] for m in mentions):
                raise UnsupportedAnalysis("Informe o ano junto a cada mês ao comparar anos diferentes.")
            if len(mentions) == 2:
                windows = [window(y, m, y, m) for m, y, _ in mentions]
            else:
                windows = [window(mentions[i][1], mentions[i][0], mentions[i+1][1], mentions[i+1][0]) for i in (0, 2)]
        elif len(mentions) > 0:
            if re.search(r"compar|diferenca|variacao|versus|\bvs\b|\bcontra\b|\bx\b|em relacao", q):
                raise UnsupportedAnalysis("Informe dois meses ou dois intervalos completos de meses para a comparação.")
            return None
        else:
            semesters = list(re.finditer(r"\b(primeiro|segundo|1|2)\s+semestre(?:\s+(?:de\s+)?((?:19|20)\d{2}))?", q))
            if len(semesters) == 2:
                windows = []
                for s in semesters:
                    sy = int(s.group(2)) if s.group(2) else year
                    sm = 1 if s.group(1) in ("primeiro", "1") else 7
                    windows.append(window(sy, sm, sy, sm + 5))
                if len(unique_years) > 1 and not all(s.group(2) for s in semesters):
                    raise UnsupportedAnalysis("Informe o ano junto a cada semestre ao comparar anos diferentes.")
            elif len(unique_years) == 2:
                windows = [(date(y, 1, 1), date(y, 12, 31)) for y in unique_years]
            elif semesters:
                raise UnsupportedAnalysis("Informe dois semestres para comparar.")
    if windows is None:
        return None  # Ex.: comparar regiões continua no interpretador regional.
    for start, end in windows:
        if end < start:
            raise UnsupportedAnalysis("O fim de cada período deve ser posterior ao início. Para atravessar anos, informe as quatro datas completas.")
        if (end - start).days > 3660:
            raise UnsupportedAnalysis("Cada período pode ter até dez anos por consulta.")
    if not years:
        notes.append(f"Ano assumido: {default_year}, conforme a data final do painel.")
    return windows, notes

def build_comparison(frames, windows, metrics, coverage, filters, notes=None):
    """Frames já vêm filtrados. Exibe falta de cobertura sem inventar zeros."""
    first, last = coverage
    statuses = []
    for start, end in windows:
        statuses.append("Sem cobertura" if end < first or start > last else
                        "Parcial" if start < first or end > last else "Dentro da cobertura")
    durations = [(end - start).days + 1 for start, end in windows]
    lines = [f"**Período A:** {windows[0][0]:%d/%m/%Y} a {windows[0][1]:%d/%m/%Y} ({durations[0]} dias; {statuses[0]}).",
             f"**Período B:** {windows[1][0]:%d/%m/%Y} a {windows[1][1]:%d/%m/%Y} ({durations[1]} dias; {statuses[1]}).",
             "Regiões: " + ", ".join(filters.get("region") or ["todas"]) + ". Categorias: " + ", ".join(filters.get("category") or ["todas"]) + ". Produtos: " + ", ".join(filters.get("product") or ["todos"]) + "."]
    table, raw, charts = [], [], []
    for metric in metrics:
        values = []
        for frame, status in zip(frames, statuses):
            # Ticket e taxa sem denominador não são médias de valor zero.
            undefined = metric == "ticket" and metric_value(frame, "orders") == 0 or metric == "cancel_rate" and frame.empty
            values.append(None if status == "Sem cobertura" or undefined else metric_value(frame, metric))
        a, b = values
        delta = b - a if a is not None and b is not None else None
        pct = delta / a * 100 if delta is not None and a != 0 else None
        diff = "N/D" if delta is None else (f"{delta:+.2f} p.p.".replace(".", ",") if metric == "cancel_rate" else format_value(delta, metric))
        pct_text = "N/D" if pct is None else f"{pct:+.2f}%".replace(".", ",")
        table.append({"Indicador": METRICS[metric], "Período A": "N/D" if a is None else format_value(a, metric),
                      "Período B": "N/D" if b is None else format_value(b, metric), "Diferença (B − A)": diff,
                      "Variação relativa (%)": pct_text})
        raw.append(dict(metric=metric, a=a, b=b, difference=delta, change_pct=pct))
        if delta is not None:
            lines.append(f"**{METRICS[metric]}:** {format_value(a, metric)} → {format_value(b, metric)}; diferença {diff}; variação {pct_text}.")
        charts.append({"label": METRICS[metric] + (" (R$)" if metric in ("revenue", "ticket") else ""),
                       "data": [{"Recorte": name, "Valor": v / 100 if metric in ("revenue", "ticket") else v}
                                for name, v in zip(("Período A", "Período B"), values) if v is not None]})
    if statuses != ["Dentro da cobertura", "Dentro da cobertura"]:
        lines.append(f"**Atenção à cobertura:** o banco contém registros de {first:%d/%m/%Y} a {last:%d/%m/%Y}. Períodos parciais mostram apenas o que está registrado; a variação não equivale à comparação de períodos completos. Sem cobertura é N/D.")
    if durations[0] != durations[1]:
        lines.append("Os períodos têm durações diferentes. Os totais não foram normalizados por dia.")
    if max(w[0] for w in windows) <= min(w[1] for w in windows):
        lines.append("Os períodos se sobrepõem; pedidos nas datas comuns participam dos dois totais.")
    lines.extend(notes or [])
    lines.append("Variação relativa = (B − A) ÷ A × 100. Base zero ou ausente: N/D. Ticket médio = faturamento ÷ pedidos concluídos de todo o período. Diferenças de taxas são exibidas em pontos percentuais (p.p.).")
    return {"answered": True, "answer": "\n\n".join(lines), "reason": None,
            "evidence": {"type": "period_comparison", "method": "Comparação de períodos • cálculos com pandas",
                "source": "PostgreSQL • tabela sales", "filters": filters, "metrics": metrics,
                "periods": [{"start": s.isoformat(), "end": e.isoformat(), "coverage": status, "rows": len(f)}
                            for (s, e), status, f in zip(windows, statuses, frames)],
                "table": table, "data": raw, "charts": charts,
                "calculated_at": datetime.now(timezone.utc).isoformat()}}

def try_comparison(question, filters, dimensions):
    from . import db
    from .analysis_queries import interpret, MONTHS, UnsupportedAnalysis
    parsed = periods_from_question(question, filters)
    if parsed is None:
        return None
    windows, notes = parsed
    # Reaproveita as validações e a escolha de métricas, removendo APENAS as
    # expressões temporais já interpretadas nesta etapa.
    clean = re.sub(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b", " ", question)
    clean = normalize(clean)
    clean = re.sub(r"\b(" + "|".join(MONTHS) + r"|primeiro|segundo|semestre|analise|resumo|relatorio|panorama)\b|\b(?:19|20)\d{2}\b", " ", clean)
    spec = interpret(clean, filters, dimensions)
    if spec is not None and any(g == "month" or len(spec["filters"].get(g, [])) != 1 for g in spec["groups"]):
        raise UnsupportedAnalysis("Compare os totais dos dois períodos nesta consulta. Para detalhar por região, categoria ou produto, faça outra pergunta ou indique um nome como filtro.")
    metrics = spec["metrics"] if spec else list(METRICS)
    if not re.search(r"fatur|receita|venda|vend\w*|valor|ticket|pedid|unidad|cancel", normalize(question)):
        metrics = list(METRICS)
    effective = dict(spec["filters"] if spec else filters)
    # Nomes de dimensões sobrevivem à limpeza e são parâmetros, nunca SQL livre.
    for key in ("region", "category", "product"):
        matches = [v for v in dimensions.get(key, []) if re.search(r"\b" + re.escape(normalize(v)) + r"\b", normalize(question))]
        if matches:
            effective[key] = matches
    frames = [db.sales_frame({**effective, "start": s.isoformat(), "end": e.isoformat()}) for s, e in windows]
    bounds = db.rows("SELECT min(sold_on) AS first,max(sold_on) AS last FROM sales")[0]
    if bounds["first"] is None:
        raise UnsupportedAnalysis("Não há registros no banco para comparar períodos.")
    notes.append("As datas informadas na pergunta substituem o período do painel. O primeiro período mencionado é A; o segundo é B.")
    return build_comparison(frames, windows, metrics, (bounds["first"], bounds["last"]), effective, notes)
