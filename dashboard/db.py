"""Acesso ao PostgreSQL. SQL é fixo e valores sempre são parametrizados."""
import json
from functools import lru_cache
import pandas as pd
from sqlalchemy import create_engine, text
from .config import DATABASE_URL, ROOT
from .text import normalize

@lru_cache(maxsize=1)
def engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 5})

def initialize():
    """Lock transacional permite app e worker iniciarem simultaneamente."""
    with engine().begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(739251)"))
        for statement in (ROOT / "sql/001_schema.sql").read_text(encoding="utf-8").split(";"):
            if statement.strip():
                conn.execute(text(statement))

def rows(sql, params=None):
    with engine().connect() as conn:
        return [dict(row) for row in conn.execute(text(sql), params or {}).mappings()]

def sales_frame(filters=None):
    # A IA não escreve SQL: estes filtros são a única porta de entrada para vendas.
    sql = "SELECT * FROM sales WHERE TRUE"
    params = {}
    if filters:
        sql += " AND sold_on BETWEEN :start AND :end"
        params.update(start=filters["start"], end=filters["end"])
        for field in ("region", "category", "product"):
            if filters.get(field):
                sql += f" AND {field} = ANY(:{field})"  # field vem da lista fixa acima.
                params[field] = filters[field]
    with engine().connect() as conn:
        df = pd.read_sql_query(text(sql + " ORDER BY sold_on, id"), conn, params=params)
    df["sold_on"] = pd.to_datetime(df["sold_on"])
    # Guardar centavos inteiros evita acumular erro de ponto flutuante nos totais.
    df["unit_price"] = pd.to_numeric(df["unit_price"])
    df["units"] = pd.to_numeric(df["units"])
    df["unit_cents"] = (df["unit_price"] * 100).round().astype("int64")
    df["revenue_cents"] = df["unit_cents"] * df["units"]
    return df

def knowledge_list(active_only=False):
    return rows("SELECT * FROM knowledge " + ("WHERE active " if active_only else "") + "ORDER BY updated_at DESC")

def exact_knowledge(question):
    result = rows("SELECT * FROM knowledge WHERE normalized_question=:q AND active", {"q": normalize(question)})
    return result[0] if result else None

def search_knowledge(question):
    # Busca textual em português; só conteúdo aprovado e ativo é elegível.
    terms = normalize(question).split()[:40]
    query = " OR ".join(terms)
    return rows("""SELECT *, ts_rank(to_tsvector('portuguese', question || ' ' || answer),
        websearch_to_tsquery('portuguese', :q)) AS rank
        FROM knowledge WHERE active AND to_tsvector('portuguese', question || ' ' || answer)
        @@ websearch_to_tsquery('portuguese', :q) ORDER BY rank DESC, id LIMIT 6""", {"q": query})

def teach(question, answer, source, knowledge_id=None):
    question, answer, source = question.strip(), answer.strip(), source.strip()
    if not question or not normalize(question) or not answer or not source:
        raise ValueError("Preencha pergunta, resposta e fonte.")
    if len(question) > 1000 or len(answer) > 6000 or len(source) > 500:
        raise ValueError("Limites: pergunta 1.000, resposta 6.000 e fonte 500 caracteres.")
    values = {"q": question, "n": normalize(question), "a": answer, "s": source}
    with engine().begin() as conn:
        if knowledge_id is not None:
            values["id"] = knowledge_id
            record = conn.execute(text("""UPDATE knowledge SET question=:q, normalized_question=:n,
                answer=:a, source=:s, revision=revision+1, updated_at=now()
                WHERE id=:id RETURNING *"""), values).mappings().one()
        else:
            record = conn.execute(text("""INSERT INTO knowledge(question,normalized_question,answer,source)
                VALUES (:q,:n,:a,:s) ON CONFLICT(normalized_question) DO UPDATE SET
                question=EXCLUDED.question, answer=EXCLUDED.answer, source=EXCLUDED.source,
                active=TRUE, revision=knowledge.revision+1, updated_at=now() RETURNING *"""), values).mappings().one()
        _history(conn, record)
        return dict(record)

def _history(conn, record):
    conn.execute(text("""INSERT INTO knowledge_history(knowledge_id,revision,question,answer,source,active)
        VALUES (:id,:revision,:question,:answer,:source,:active)"""), dict(record))

def toggle_knowledge(knowledge_id, active):
    with engine().begin() as conn:
        record = conn.execute(text("""UPDATE knowledge SET active=:active, revision=revision+1,
            updated_at=now() WHERE id=:id RETURNING *"""), {"id": knowledge_id, "active": active}).mappings().one()
        _history(conn, record)

def create_question(question, filters):
    with engine().begin() as conn:
        return conn.execute(text("INSERT INTO questions(question,filters) VALUES (:q,CAST(:f AS jsonb)) RETURNING id"),
                            {"q": question, "f": json.dumps(filters)}).scalar_one()

def save_result(question_id, result, suggested=False):
    status = ("suggested" if suggested else "answered") if result["answered"] else "pending"
    values = {"id": question_id, "status": status, "answered": result["answered"],
              "answer": result.get("answer"), "reason": result.get("reason"),
              "evidence": json.dumps(result.get("evidence", {}), ensure_ascii=False)}
    with engine().begin() as conn:
        # Não sobrescrever resolução feita enquanto o modelo estava processando.
        updated = conn.execute(text("""UPDATE questions SET status=:status,answer=:answer,reason=:reason,
            evidence=CAST(:evidence AS jsonb), attempts=attempts+1,last_attempt_at=now(),updated_at=now()
            WHERE id=:id AND status='pending' RETURNING id"""), values).scalar_one_or_none()
        if updated is not None:
            conn.execute(text("""INSERT INTO question_attempts(question_id,answered,answer,reason,evidence)
                VALUES (:id,:answered,:answer,:reason,CAST(:evidence AS jsonb))"""), values)

def question_list(status=None, limit=200):
    return rows("SELECT * FROM questions " + ("WHERE status=:status " if status else "") +
                "ORDER BY created_at DESC LIMIT :limit", {"status": status, "limit": limit})


def unanswered_questions(include_resolved=False):
    """Inclui sugestões ainda não aprovadas e, opcionalmente, falhas históricas.

    EXISTS evita duplicar perguntas que falharam em várias tentativas.
    Esta consulta não reprocessa nem altera os registros.
    """
    return rows("""SELECT q.* FROM questions q
        WHERE q.status IN ('pending', 'suggested')
        OR (:history AND EXISTS (SELECT 1 FROM question_attempts a
            WHERE a.question_id=q.id AND NOT a.answered))
        ORDER BY q.created_at DESC, q.id DESC""", {"history": include_resolved})

def approve_suggestion(question_id):
    with engine().begin() as conn:
        row = conn.execute(text("SELECT * FROM questions WHERE id=:id FOR UPDATE"), {"id": question_id}).mappings().one()
        if row["status"] != "suggested":
            raise ValueError("Esta pergunta não tem sugestão pendente.")
        evidence = row["evidence"]
        if evidence.get("knowledge_id"):
            current = conn.execute(text("SELECT active,revision FROM knowledge WHERE id=:id FOR SHARE"),
                                   {"id": evidence["knowledge_id"]}).mappings().one()
            if not current["active"] or current["revision"] != evidence["revision"]:
                raise ValueError("A fonte mudou. Rejeite a sugestão e reprocesse a pergunta.")
        conn.execute(text("UPDATE questions SET status='answered',updated_at=now() WHERE id=:id"), {"id": question_id})

def set_question_status(question_id, status):
    if status not in ("pending", "dismissed"):
        raise ValueError("Status inválido.")
    with engine().begin() as conn:
        conn.execute(text("""UPDATE questions SET status=:status,answer=NULL,evidence='{}'::jsonb,
            reason=NULL,updated_at=now() WHERE id=:id"""), {"status": status, "id": question_id})
