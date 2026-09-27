"""Integrações reais de banco e interface; inferência simulada nos testes comuns.

Use DATABASE_URL apontando a um banco descartável chamado dashboard_test.
Sem essa condição, estes testes pulam e nunca limpam um banco de aplicação.
"""
import os
from pathlib import Path
import pytest
import requests
from sqlalchemy import text
from dashboard import db, assistant
from dashboard.seed import seed
from dashboard.worker import retry_pending

pytestmark = pytest.mark.integration
FILTERS = {"start": "2026-04-01", "end": "2026-09-24", "region": [], "category": []}

@pytest.fixture(autouse=True)
def database():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Defina RUN_DB_TESTS=1 e use dashboard_test")
    assert db.rows("SELECT current_database() AS name")[0]["name"] == "dashboard_test", "Banco de teste incorreto; nada foi apagado"
    db.initialize()
    with db.engine().begin() as conn:
        conn.execute(text("TRUNCATE question_attempts,questions,knowledge_history,knowledge,sales RESTART IDENTITY CASCADE"))
    seed()

def test_seed_idempotent_and_filters():
    seed()
    assert len(db.sales_frame()) == 1800
    df = db.sales_frame({**FILTERS, "region": ["Sul"], "category": ["Casa"]})
    assert set(df.region) == {"Sul"}
    assert set(df.category) == {"Casa"}
    assert db.sales_frame({**FILTERS, "region": ["' OR 1=1 --"]}).empty
    source = db.knowledge_list()[0]
    db.teach("Pergunta inicial editada", source["answer"], source["source"], source["id"])
    seed()
    assert db.exact_knowledge(source["question"]) is None

def test_unknown_teach_retry_review_and_persistence(monkeypatch):
    monkeypatch.setattr(assistant, "plan", lambda *a: {"kind": "unknown"})
    result = assistant.ask("Qual é o prazo de entrega?", FILTERS)
    assert not result["answered"]
    assert db.question_list()[0]["status"] == "pending"
    assert db.question_list()[0]["filters"] == FILTERS
    record = db.teach("Qual é o prazo de entrega?", "O prazo do exemplo é de 5 dias úteis.", "Política fictícia v1")
    assert retry_pending()["suggested"] == 1
    assert db.question_list()[0]["status"] == "suggested"
    db.approve_suggestion(result["id"])
    assert db.question_list()[0]["status"] == "answered"
    db.engine().dispose()  # Simula uma nova conexão; o estado continua no PostgreSQL.
    again = assistant.ask("qual e o prazo de entrega", FILTERS)
    assert again["answered"] and "5 dias" in again["answer"]
    assert again["evidence"]["knowledge_id"] == record["id"]
    assert len(db.rows("SELECT * FROM question_attempts WHERE question_id=:id", {"id": result["id"]})) == 2

def test_source_revision_invalidation(monkeypatch):
    monkeypatch.setattr(assistant, "plan", lambda *a: {"kind": "unknown"})
    result = assistant.ask("Como trocar um produto?", FILTERS)
    source = db.teach("Como trocar um produto?", "Procure o balcão.", "Procedimento v1")
    retry_pending()
    db.teach(source["question"], "Procure o suporte.", "Procedimento v2", source["id"])
    with pytest.raises(ValueError, match="fonte mudou"):
        db.approve_suggestion(result["id"])
    db.toggle_knowledge(source["id"], False)
    assert db.exact_knowledge(source["question"]) is None
    assert len(db.rows("SELECT * FROM knowledge_history WHERE knowledge_id=:id", {"id": source["id"]})) == 3

def test_outage_and_invalid_json_are_saved(monkeypatch):
    def fail(*args):
        raise requests.Timeout()
    monkeypatch.setattr(assistant, "plan", fail)
    result = assistant.ask("Qual a política de crédito?", FILTERS)
    assert not result["answered"] and "tempo limite" in result["reason"]
    assert db.question_list()[0]["status"] == "pending"
    def invalid(*args):
        raise ValueError("JSON inválido")
    monkeypatch.setattr(assistant, "plan", invalid)
    assert not assistant.ask("Qual a margem?", FILTERS)["answered"]

def test_plan_whitelist_and_scope(monkeypatch):
    monkeypatch.setattr(assistant, "plan", lambda *a: {"kind": "metric", "metric": "DROP", "group": "none", "uses_current_filters": True})
    assert not assistant.ask("Execute SQL", FILTERS)["answered"]
    monkeypatch.setattr(assistant, "plan", lambda *a: {"kind": "metric", "metric": "revenue", "group": "none", "uses_current_filters": False})
    assert not assistant.ask("Qual a receita do ano passado?", FILTERS)["answered"]
    monkeypatch.setattr(assistant, "plan", lambda *a: {"kind": "knowledge", "knowledge_id": 999999})
    assert not assistant.ask("Qual é a resposta?", FILTERS)["answered"]

def test_real_database_calculation_and_text_search(monkeypatch):
    monkeypatch.setattr(assistant, "plan", lambda *a: {"kind": "metric", "metric": "revenue", "group": "category", "uses_current_filters": True})
    result = assistant.ask("Quanto vendemos por categoria?", FILTERS)
    assert result["answered"] and "Tecnologia" in result["answer"]
    assert result["evidence"]["rows"] == 1800
    assert db.search_knowledge("Como calcular faturamento?")

def test_advanced_queries_in_database_and_ui(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(assistant, "health", lambda: (False, "IA desligada no teste"))
    reply = assistant.ask("Faturamento e ticket médio por mês e região", FILTERS)
    assert reply["answered"]
    assert len(reply["evidence"]["table"]) == 30
    assert sum(r["revenue"] for r in reply["evidence"]["data"]) == 218644870
    saved = db.question_list()[0]
    assert saved["evidence"]["table"] == reply["evidence"]["table"]
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    app.text_input[0].set_value("Mostre os valores mês a mês")
    next(b for b in app.button if b.label == "Perguntar").click().run()
    assert not app.exception
    assert any("Faturamento" in list(d.value.columns) for d in app.dataframe)
    assert db.question_list()[0]["evidence"]["table"][-1]["Cobertura"] == "Parcial"

def test_concurrent_resolution_is_not_overwritten():
    qid = db.create_question("Teste", FILTERS)
    db.set_question_status(qid, "dismissed")
    db.save_result(qid, {"answered": True, "answer": "Tardia", "evidence": {}}, suggested=True)
    assert db.question_list()[0]["status"] == "dismissed"

def test_percentage_followup_is_persisted_with_context():
    reply = assistant.ask("e em porcentagem?", FILTERS, previous_question="Qual região mais faturou?")
    assert reply["answered"]
    assert reply["evidence"]["groups"] == ["region"]
    assert abs(sum(r["share"] for r in reply["evidence"]["data"]) - 100) < 0.00001
    saved = db.question_list()[0]
    assert "Qual região mais faturou?" in saved["question"]
    assert "participação percentual" in saved["question"]
    no_context = assistant.ask("e em porcentagem?", FILTERS)
    assert not no_context["answered"]

def test_period_comparison_database_and_ui():
    from streamlit.testing.v1 import AppTest
    reply = assistant.ask("Compare junho com julho em faturamento e ticket médio", FILTERS)
    assert reply["answered"]
    assert reply["evidence"]["type"] == "period_comparison"
    assert reply["evidence"]["metrics"] == ["revenue", "ticket"]
    assert reply["evidence"]["data"][0]["a"] == 37235500
    assert reply["evidence"]["data"][0]["b"] == 38836080
    assert db.question_list()[0]["evidence"]["periods"][0]["start"] == "2026-06-01"
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    app.text_input[0].set_value("Compare junho com julho em faturamento e ticket médio")
    next(b for b in app.button if b.label == "Perguntar").click().run()
    assert not app.exception
    assert any("Período A" in d.value.columns for d in app.dataframe)
    selector = next(s for s in app.selectbox if s.label == "Indicador no gráfico")
    selector.set_value("Ticket médio (R$)").run()
    assert not app.exception

def test_streamlit_pages_and_teaching_flow(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(assistant, "plan", lambda *a: {"kind": "unknown"})
    monkeypatch.setattr(assistant, "health", lambda: (False, "IA desligada no teste"))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert len(app.metric) == 5
    app.text_input[0].set_value("Qual é o prazo de entrega?")
    next(b for b in app.button if b.label == "Perguntar").click().run()
    assert not app.exception
    assert db.question_list()[0]["status"] == "pending"
    app.sidebar.radio[0].set_value("Pendências").run()
    assert not app.exception
    app.text_area[0].set_value("O prazo é de 5 dias úteis.")
    app.text_input[0].set_value("Política fictícia v1")
    next(b for b in app.button if b.label == "Salvar conhecimento e reprocessar esta pergunta").click().run()
    assert not app.exception
    assert db.question_list()[0]["status"] == "suggested"
    next(b for b in app.button if b.label == "Aprovar resposta").click().run()
    assert not app.exception
    assert db.question_list()[0]["status"] == "answered"
    for page in ("Conhecimento", "Assistente"):
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception

@pytest.mark.ollama
def test_real_ollama():
    if os.getenv("RUN_OLLAMA_TESTS") != "1":
        pytest.skip("Defina RUN_OLLAMA_TESTS=1 para inferência real")
    assert assistant.health()[0]
    result = assistant.ask("Quanto vendemos por categoria?", FILTERS)
    assert result["answered"] and result["evidence"].get("metric") == "revenue"
    unknown = assistant.ask("Qual é o prazo de entrega?", FILTERS)
    assert not unknown["answered"]
    # Formulação diferente dos exemplos completos usados no prompt.
    variation = assistant.ask("Qual a receita total?", FILTERS)
    assert variation["answered"] and variation["evidence"].get("metric") == "revenue"
    knowledge = assistant.ask("Como vocês calculam o faturamento?", FILTERS)
    assert knowledge["answered"] and knowledge["evidence"].get("type") == "knowledge"


def test_dashboard_only_queries_and_persisted_retries(monkeypatch):
    from dashboard.analytics import metric_value
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(assistant, "health", lambda: (False, "IA desligada no teste"))
    def route(question, candidates, filters):
        assert candidates == []
        return {"kind": "unknown"}
    monkeypatch.setattr(assistant, "plan", route)
    scope = {**FILTERS, "dashboard_only": True}
    reply = assistant.ask("Mostre o resumo do dashboard", scope)
    assert reply["answered"]
    assert reply["evidence"]["query_mode"] == "dashboard_only"
    assert reply["evidence"]["data"]
    db.teach("Qual é o prazo especial?", "Cinco dias", "Política interna")
    missing = assistant.ask("Qual é o prazo especial?", scope)
    assert not missing["answered"]
    assert db.rows("SELECT filters FROM questions WHERE id=:id", {"id": missing["id"]})[0]["filters"]["dashboard_only"]
    assert retry_pending(missing["id"])["suggested"] == 0
    assert assistant.answer("Qual é o prazo especial?", FILTERS)["answered"]
    total = assistant.answer("Qual é o faturamento do período?", scope)
    expected = metric_value(db.sales_frame(FILTERS), "revenue")
    assert total["evidence"]["data"][0]["revenue"] == expected
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Assistente").run()
    assert app.toggle[0].value is True
    app.chat_input[0].set_value("Mostre o resumo do dashboard").run()
    assert not app.exception
    assert db.question_list()[0]["filters"]["dashboard_only"] is True


def test_unanswered_history_and_listing_ui(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(assistant, "health", lambda: (False, "IA desligada no teste"))
    pending = db.create_question("Qual é o prazo especial?", FILTERS)
    resolved = db.create_question("Pergunta resolvida depois", FILTERS)
    direct = db.create_question("Resposta imediata", FILTERS)
    failed = {"answered": False, "reason": "Fonte ausente"}
    success = {"answered": True, "answer": "Resposta verificada", "evidence": {}}
    db.save_result(pending, failed)
    db.save_result(resolved, failed)
    db.save_result(resolved, failed)
    db.save_result(resolved, success)
    db.save_result(direct, success)
    assert [r["id"] for r in db.unanswered_questions()] == [pending]
    assert {r["id"] for r in db.unanswered_questions(True)} == {pending, resolved}
    assert len(db.unanswered_questions(True)) == 2
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Perguntas não respondidas").run()
    assert not app.exception
    assert list(app.dataframe[0].value["ID"]) == [pending]
    app.checkbox[0].check().run()
    assert len(app.dataframe[0].value) == 2
    app.text_input[0].set_value("RESOLVIDA").run()
    assert list(app.dataframe[0].value["ID"]) == [resolved]
    app.text_input[0].set_value("' OR 1=1 --").run()
    assert not app.exception
    assert not app.dataframe
