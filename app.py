"""Interface Streamlit em português. Regras e persistência estão em dashboard/."""
import logging
from datetime import date
import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError
from dashboard import db
from dashboard.analytics import metric_value, money, grouped
from dashboard.assistant import ask, health, EXAMPLES
from dashboard.worker import retry_pending
from dashboard.query_catalog import CATALOG

st.set_page_config(page_title="Clareza • vendas e conhecimento", page_icon="◈", layout="wide")
st.markdown("""<style>
.block-container{padding-top:4rem;padding-bottom:2rem;max-width:1600px}
h1{font-size:2.15rem!important;letter-spacing:-.055rem}
[data-testid="stMetric"]{background:white;border:1px solid #dce4ec;border-radius:12px;padding:18px}
[data-testid="stMetricLabel"]{color:#50647d}
[data-testid="stMetricValue"]{font-size:1.85rem}
[data-testid="stSidebar"]{border-right:1px solid #dce4ec}
.eyebrow{font-size:13px;font-weight:700;letter-spacing:.14em;color:#087f8c;margin-bottom:12px}
</style>""", unsafe_allow_html=True)

@st.cache_data(ttl=20)
def ai_health():
    return health()

def flash(text):
    st.session_state["notice"] = text
    st.rerun()

def evidence_ui(evidence):
    if evidence.get("query_mode") == "dashboard_only":
        st.caption("Origem: consultas cadastradas do dashboard • valores calculados no código")
    if evidence.get("table"):
        data = pd.DataFrame(evidence["table"])
        st.dataframe(data, hide_index=True, width="stretch")
        st.download_button("Baixar análise em CSV", data.to_csv(index=False).encode("utf-8-sig"),
                           "analise.csv", "text/csv", key="csv_" + evidence["calculated_at"])
        chart_data, chart_label = evidence.get("chart", []), evidence.get("chart_label", "Valor")
        if evidence.get("charts"):
            choices = {c["label"]: c["data"] for c in evidence["charts"]}
            chart_label = st.selectbox("Indicador no gráfico", list(choices), key="metric_" + evidence["calculated_at"])
            chart_data = choices[chart_label]
        if len(chart_data) > 1:
            chart = pd.DataFrame(chart_data)
            fig = px.bar(chart, x="Recorte", y="Valor", color_discrete_sequence=["#087F8C"],
                         labels={"Valor": chart_label})
            fig.update_layout(height=290, margin=dict(l=0, r=0, t=10, b=0))
            fig.update_xaxes(type="category")
            st.plotly_chart(fig, width="stretch", key="chart_" + evidence["calculated_at"])
    st.caption(f"Fonte: {evidence.get('source', 'não disponível')}")
    st.caption(evidence.get("method", ""))
    with st.expander("Ver evidência e recorte"):
        st.json(evidence)

def result_ui(result):
    if result["answered"]:
        st.write(result["answer"])
        evidence_ui(result["evidence"])
        if st.button("A resposta não resolveu", key=f"flag_{result['id']}"):
            db.set_question_status(result["id"], "pending")
            result["answered"] = False
            result["reason"] = "Resposta sinalizada para revisão pelo usuário."
            st.success("Pergunta devolvida à fila de pendências.")
    else:
        st.info(f"{result['reason']} Pergunta #{result['id']} salva em Pendências.")

def ask_ui(question, filters):
    with st.spinner("Consultando dados e fontes locais…"):
        try:
            history = st.session_state.get("chat", [])
            previous = history[-1].get("evidence", {}).get("resolved_question", history[-1]["question"]) if history else None
            result = ask(question, filters, previous_question=previous)
        except ValueError as error:
            st.warning(str(error))
            return
    st.session_state.setdefault("chat", []).append(result)
    st.session_state["latest"] = result

try:
    # Somente leitura neste ponto: run.py é responsável por preparar o banco.
    bounds = db.rows("SELECT min(sold_on) AS first,max(sold_on) AS last,count(*) AS n FROM sales")[0]
    if not bounds["n"]:
        st.warning("Banco vazio. Execute python -m dashboard.seed e atualize esta página.")
        st.stop()
    dimensions = db.rows("SELECT DISTINCT region,category FROM sales")
except SQLAlchemyError:
    st.title("Clareza")
    st.error("Não foi possível acessar o PostgreSQL. Confira o serviço e a configuração DATABASE_URL.")
    st.code("docker compose up --build -d")
    st.caption("Na execução sem Docker, prepare o banco com python -m dashboard.seed.")
    st.stop()

with st.sidebar:
    st.markdown("## ◈ clareza")
    st.caption("VENDAS & CONHECIMENTO")
    page = st.radio("Navegação", ["Visão geral", "Assistente", "Perguntas não respondidas", "Pendências", "Conhecimento"], label_visibility="collapsed")
    st.divider()
    st.markdown("**Recorte dos dados**")
    period = st.date_input("Período", (bounds["first"], bounds["last"]), format="DD/MM/YYYY")
    regions = st.multiselect("Regiões", sorted({r["region"] for r in dimensions}), placeholder="Todas as regiões")
    categories = st.multiselect("Categorias", sorted({r["category"] for r in dimensions}), placeholder="Todas as categorias")
    st.caption("Seleção vazia inclui todas as opções. As perguntas usam este recorte.")
    st.divider()
    available, status = ai_health()
    st.markdown("**IA local**")
    (st.success if available else st.warning)(status)
    if st.button("Verificar conexão", width="stretch"):
        ai_health.clear()
        st.rerun()
    st.caption("Sem conta de IA • execução local\n\nDados fictícios de abril a setembro/2026")

if len(period) != 2:
    st.info("Escolha as duas datas para continuar.")
    st.stop()
filters = {"start": period[0].isoformat(), "end": period[1].isoformat(), "region": regions, "category": categories}
if "notice" in st.session_state:
    st.success(st.session_state.pop("notice"))

def overview():
    st.markdown('<div class="eyebrow">VISÃO GERAL / COMERCIAL</div>', unsafe_allow_html=True)
    st.title("Visão de vendas")
    st.caption(f"{period[0]:%d/%m/%Y} — {period[1]:%d/%m/%Y}  ·  Atualização por consulta  ·  Demonstração")
    df = db.sales_frame(filters)
    cols = st.columns(4)
    cols[0].metric("Faturamento", money(metric_value(df, "revenue")))
    cols[1].metric("Pedidos concluídos", f"{metric_value(df, 'orders'):,}".replace(",", "."))
    cols[2].metric("Ticket médio", money(metric_value(df, "ticket")))
    cols[3].metric("Unidades vendidas", f"{metric_value(df, 'units'):,}".replace(",", "."))
    st.caption(f"Pedidos cancelados: {metric_value(df, 'cancellations')} · Cancelamentos não entram no faturamento.")
    left, right = st.columns([1.7, 1], gap="large")
    with left:
        st.subheader("Evolução do faturamento")
        if df.empty:
            st.info("Não há pedidos para os filtros selecionados.")
        else:
            trend = grouped(df, "revenue", "month")
            trend["Faturamento (R$)"] = trend["valor"] / 100
            fig = px.area(trend, x="grupo", y="Faturamento (R$)", color_discrete_sequence=["#087F8C"], labels={"grupo": "Mês"})
            fig.update_layout(height=290, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            fig.update_traces(line_width=3)
            fig.update_xaxes(type="category")
            st.plotly_chart(fig, width="stretch")
            region = grouped(df, "revenue", "region").sort_values("valor")
            region["Faturamento (R$)"] = region["valor"] / 100
            st.subheader("Vendas por região")
            bar = px.bar(region, x="Faturamento (R$)", y="grupo", orientation="h", color_discrete_sequence=["#315681"], labels={"grupo": ""})
            bar.update_layout(height=260, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(bar, width="stretch")
    with right:
        with st.container(border=True):
            st.subheader("Converse com seus dados")
            st.write("Pergunte sobre vendas ou sobre as regras do painel.")
            with st.form("quick_chat", clear_on_submit=True):
                question = st.text_input("Sua pergunta", placeholder="Quanto vendemos por categoria?", max_chars=1000)
                sent = st.form_submit_button("Perguntar", type="primary", width="stretch")
            if sent:
                ask_ui(question, filters)
            if st.session_state.get("latest"):
                result_ui(st.session_state["latest"])
            else:
                st.caption("Experimente: “Qual é o faturamento do período?” ou “Qual é o prazo de entrega?”")
            st.divider()
            pending = db.rows("SELECT count(*) AS n FROM questions WHERE status='pending'")[0]["n"]
            st.metric("Perguntas para ensinar", pending)
            st.caption("O que faltar fica salvo. Revise na seção Pendências.")
    with st.expander("Explorar os pedidos e baixar o recorte"):
        display = df.drop(columns=["unit_cents", "revenue_cents"])
        st.dataframe(display, hide_index=True, width="stretch")
        st.download_button("Baixar CSV", display.to_csv(index=False).encode("utf-8-sig"), "pedidos.csv", "text/csv")

def chat_page():
    st.markdown('<div class="eyebrow">ASSISTENTE / CONSULTA LOCAL</div>', unsafe_allow_html=True)
    st.title("Pergunte. Confira a fonte.")
    dashboard_only = st.toggle("Consultar somente os dados do dashboard", value=True)
    chat_filters = {**filters, "dashboard_only": dashboard_only}
    if dashboard_only:
        st.info("Diga o indicador, o período e a região ou categoria desejada. O assistente usa as consultas existentes e entrega o resultado aqui, sem precisar abrir os gráficos. Pedidos sem consulta compatível ficam salvos para revisão.")
        with st.expander("O que posso consultar por conversa?"):
            st.dataframe(pd.DataFrame(CATALOG), hide_index=True, width="stretch")
            st.caption("Também experimente: Mostre o resumo do dashboard. As consultas usam os mesmos dados e cálculos do painel; a IA não cria SQL. Desative o modo para consultar também o conhecimento aprovado.")
    st.write("Peça tabelas mensais, comparações, rankings e análises com vários indicadores. Meses e dimensões escritos na pergunta substituem os filtros correspondentes do painel; confira o recorte na resposta.")
    with st.expander("Perguntas prontas e limites"):
        st.write("Faturamento, pedidos, ticket, unidades, cancelamentos e taxa de cancelamento. Até dois agrupamentos: mês, região, categoria ou produto. Meses parciais são sinalizados.")
        st.caption("Análises reconhecidas são calculadas diretamente com pandas. A IA local interpreta outras formulações e busca explicações na base aprovada.")
        examples = ["Mostre os valores mês a mês", "Faça uma análise completa das vendas",
                    "Compare o faturamento de agosto e setembro de 2026",
                    "Faturamento e ticket médio por mês e região", "Top 3 produtos por faturamento",
                    "Taxa de cancelamento por categoria", "Qual região mais faturou?",
                    "Qual a participação de cada região no faturamento em porcentagem?",
                    "Qual região teve a maior taxa de cancelamento?",
                    "Compare junho com julho em faturamento e ticket médio",
                    "Compare 01/04/2026 a 30/06/2026 com 01/07/2026 a 24/09/2026",
                    "Compare o primeiro semestre com o segundo semestre de 2026", *EXAMPLES]
        for i, example in enumerate(examples):
            if st.button(example, key=f"example_{i}"):
                ask_ui(example, chat_filters)
    for result in st.session_state.get("chat", []):
        with st.chat_message("user"):
            st.write(result["question"])
        with st.chat_message("assistant"):
            result_ui(result)
    if question := st.chat_input("Ex.: Quanto vendemos por categoria?", max_chars=1000):
        ask_ui(question, chat_filters)
        st.rerun()
    st.caption("O histórico desta tela dura a sessão; todas as perguntas e tentativas ficam persistidas no PostgreSQL.")

def unanswered_page():
    st.title("Perguntas não respondidas")
    st.write("Consulte as perguntas salvas no PostgreSQL que ainda precisam de uma resposta ou da aprovação de uma sugestão.")
    st.caption("Esta lista usa o histórico de perguntas de todos os períodos. Os filtros de vendas da barra lateral não restringem esta consulta. Para ensinar ou reprocessar, acesse Pendências e selecione o mesmo ID.")
    if st.button("Atualizar lista"):
        st.rerun()
    history = st.checkbox("Incluir perguntas que falharam e depois foram respondidas ou arquivadas")
    items = db.unanswered_questions(include_resolved=history)
    labels = {"pending": "Pendente", "suggested": "Sugestão para revisar", "answered": "Respondida", "dismissed": "Arquivada"}
    cols = st.columns(3)
    cols[0].metric("Perguntas na consulta", len(items))
    cols[1].metric("Pendentes", sum(r["status"] == "pending" for r in items))
    cols[2].metric("Sugestões para revisar", sum(r["status"] == "suggested" for r in items))
    search = st.text_input("Buscar no texto da pergunta", max_chars=1000)
    statuses = st.multiselect("Situação", list(labels.values()), placeholder="Todas as situações")
    # Busca literal: caracteres como % e aspas não viram SQL ou expressões regulares.
    selected = [r for r in items if search.casefold().strip() in r["question"].casefold()
                and (not statuses or labels[r["status"]] in statuses)]
    st.caption(f"{len(selected)} pergunta(s) encontrada(s). Datas exibidas no horário de Brasília.")
    if not selected:
        st.info("Nenhuma pergunta encontrada nesta seleção.")
        return
    display = pd.DataFrame([{
        "ID": r["id"], "Pergunta": r["question"], "Situação": labels[r["status"]],
        "Recebida em": pd.Timestamp(r["created_at"]).tz_convert("America/Sao_Paulo").strftime("%d/%m/%Y %H:%M"),
        "Tentativas": r["attempts"], "Motivo atual": r["reason"] or "—",
    } for r in selected])
    st.dataframe(display, hide_index=True, width="stretch", column_config={"Pergunta": st.column_config.TextColumn(width="large")})
    st.download_button("Baixar perguntas em CSV", display.to_csv(index=False).encode("utf-8-sig"), "perguntas-nao-respondidas.csv", "text/csv")
    chosen = st.selectbox("Ver pergunta completa", [r["id"] for r in selected],
                          format_func=lambda value: f"#{value}")
    record = next(r for r in selected if r["id"] == chosen)
    st.text(record["question"])
    st.caption(f"Situação: {labels[record['status']]}")
    with st.expander("Filtros usados na pergunta e histórico de tentativas"):
        st.json(record["filters"])
        attempts = db.rows("SELECT created_at,answered,reason,answer FROM question_attempts WHERE question_id=:id ORDER BY id", {"id": chosen})
        if attempts:
            st.dataframe(pd.DataFrame(attempts).rename(columns={"created_at": "Data", "answered": "Gerou resposta", "reason": "Motivo", "answer": "Resposta"}), hide_index=True, width="stretch")
        else:
            st.caption("Nenhuma tentativa registrada ainda.")


def pending_page():
    st.markdown('<div class="eyebrow">REVISÃO / MEMÓRIA DO ASSISTENTE</div>', unsafe_allow_html=True)
    st.title("O que ainda falta responder")
    st.write("Ensine uma resposta com fonte ou tente novamente após atualizar os dados. Sugestões precisam da sua revisão.")
    counts = {r["status"]: r["n"] for r in db.rows("SELECT status,count(*) AS n FROM questions GROUP BY status")}
    for col, (label, key) in zip(st.columns(3), [("Pendentes", "pending"), ("Sugestões para revisar", "suggested"), ("Respondidas", "answered")]):
        col.metric(label, counts.get(key, 0))
    if st.button("Reprocessar até 20 pendências", type="primary"):
        with st.spinner("Reavaliando perguntas com as fontes disponíveis…"):
            result = retry_pending()
        flash("Outro lote está em andamento." if result.get("busy") else f"{result['processed']} perguntas reavaliadas; {result['suggested']} sugestões disponíveis.")
    status_labels = {"Em aberto": None, "Pendentes": "pending", "Sugestões": "suggested", "Respondidas": "answered", "Arquivadas": "dismissed", "Todas": "all"}
    selection = st.selectbox("Mostrar", list(status_labels))
    status = status_labels[selection]
    if status is None:
        items = db.rows("SELECT * FROM questions WHERE status IN ('pending','suggested') ORDER BY created_at DESC LIMIT 200")
    else:
        items = db.question_list(None if status == "all" else status)
    if not items:
        st.info("Nenhuma pergunta nesta seleção. Faça uma pergunta no assistente para começar.")
        return
    st.caption("Exibindo até 200 perguntas mais recentes da seleção. A fila de reprocessamento prioriza as tentativas mais antigas.")
    labels = {r["id"]: f"#{r['id']} · {r['question']}" for r in items}
    chosen = st.selectbox("Pergunta", list(labels), format_func=labels.get)
    record = next(r for r in items if r["id"] == chosen)
    st.subheader(record["question"])
    st.caption(f"Estado: {record['status']} · Tentativas: {record['attempts']} · Recebida: {record['created_at']:%d/%m/%Y %H:%M %Z}")
    if record["reason"]:
        st.info(record["reason"])
    with st.expander("Recorte original e histórico de tentativas"):
        st.json(record["filters"])
        st.dataframe(pd.DataFrame(db.rows("SELECT created_at,answered,answer,reason,evidence FROM question_attempts WHERE question_id=:id ORDER BY id", {"id": chosen})), hide_index=True, width="stretch")
    if record["answer"]:
        st.write(record["answer"])
        evidence_ui(record["evidence"])
    if record["status"] == "suggested":
        c1, c2 = st.columns(2)
        if c1.button("Aprovar resposta", type="primary"):
            try:
                db.approve_suggestion(chosen)
                flash("Resposta aprovada. Isso resolve a pergunta; não cria conhecimento novo automaticamente.")
            except ValueError as error:
                st.warning(str(error))
        if c2.button("Rejeitar e devolver à fila"):
            db.set_question_status(chosen, "pending")
            flash("Sugestão rejeitada; pergunta devolvida à fila.")
    if record["status"] == "pending":
        with st.form(f"teach_pending_{chosen}"):
            st.markdown("### Ensinar uma resposta")
            answer_text = st.text_area("Resposta correta", max_chars=6000, height=140)
            source = st.text_input("Fonte / referência", placeholder="Ex.: Política de entregas, versão 1", max_chars=500)
            st.caption("Cadastre regras estáveis. Valores de vendas devem vir do banco, pois mudam com o tempo.")
            submitted = st.form_submit_button("Salvar conhecimento e reprocessar esta pergunta", type="primary")
        if submitted:
            try:
                db.teach(record["question"], answer_text, source)
                retry_pending(chosen)
                flash("Conhecimento salvo e pergunta reprocessada. Revise a sugestão gerada.")
            except ValueError as error:
                st.warning(str(error))
        c1, c2 = st.columns(2)
        if c1.button("Tentar esta pergunta novamente"):
            with st.spinner("Consultando novamente…"):
                result = retry_pending(chosen)
            flash(f"Reprocessamento concluído: {result['suggested']} sugestão.")
        if c2.button("Arquivar pergunta"):
            db.set_question_status(chosen, "dismissed")
            flash("Pergunta arquivada; o histórico foi preservado.")
    if record["status"] in ("answered", "dismissed") and st.button("Reabrir pergunta"):
        db.set_question_status(chosen, "pending")
        flash("Pergunta reaberta.")

def knowledge_page():
    st.markdown('<div class="eyebrow">CONHECIMENTO / FONTES APROVADAS</div>', unsafe_allow_html=True)
    st.title("Ensine uma vez. Consulte depois.")
    st.write("Cadastre definições e regras. Cada alteração mantém uma revisão no PostgreSQL.")
    items = db.knowledge_list()
    options = {0: "＋ Novo conhecimento", **{r["id"]: f"{'✓' if r['active'] else '—'} {r['question']}" for r in items}}
    chosen = st.selectbox("Entrada", list(options), format_func=options.get)
    record = next((r for r in items if r["id"] == chosen), None)
    with st.form(f"knowledge_{chosen}"):
        question = st.text_input("Pergunta de referência", value=record["question"] if record else "", max_chars=1000)
        answer_text = st.text_area("Resposta aprovada", value=record["answer"] if record else "", height=180, max_chars=6000)
        source = st.text_input("Fonte / referência", value=record["source"] if record else "", max_chars=500)
        submitted = st.form_submit_button("Salvar conhecimento", type="primary")
    if submitted:
        try:
            db.teach(question, answer_text, source, knowledge_id=chosen or None)
            flash("Conhecimento salvo. Você já pode perguntar novamente ou reprocessar as pendências.")
        except ValueError as error:
            st.warning(str(error))
        except SQLAlchemyError:
            st.warning("Já existe uma entrada para essa pergunta. Selecione a entrada existente para editá-la.")
    if record:
        st.caption(f"Revisão {record['revision']} · {'Ativo' if record['active'] else 'Inativo'} · Atualizado em {record['updated_at']:%d/%m/%Y %H:%M %Z}")
        if st.button("Desativar fonte" if record["active"] else "Reativar fonte"):
            db.toggle_knowledge(chosen, not record["active"])
            flash("Estado da fonte atualizado.")
        with st.expander("Histórico de revisões"):
            st.dataframe(pd.DataFrame(db.rows("SELECT revision,question,answer,source,active,recorded_at FROM knowledge_history WHERE knowledge_id=:id ORDER BY revision DESC", {"id": chosen})), hide_index=True, width="stretch")
    st.divider()
    st.caption("Aprender aqui significa consultar uma base revisada, não retreinar o modelo. Mais tempo permite tentar de novo; não substitui informação ausente.")

try:
    {"Visão geral": overview, "Assistente": chat_page, "Perguntas não respondidas": unanswered_page, "Pendências": pending_page, "Conhecimento": knowledge_page}[page]()
except SQLAlchemyError:
    logging.exception("Falha de banco na interface")
    st.error("O banco ficou indisponível. Reestabeleça a conexão e atualize a página; confira a fila antes de reenviar uma pergunta.")
