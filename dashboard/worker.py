"""Reprocessamento opcional. Esperar mais tempo não cria informação nova.

O worker volta a consultar as fontes e o modelo. Uma resposta encontrada vira
SUGESTÃO, nunca conhecimento aprovado automaticamente. Lock evita dois lotes
simultâneos; cada pergunta também verifica seu status ao salvar o resultado.
"""
import argparse
import logging
import os
import time
from sqlalchemy import text
from . import db
from .assistant import answer

def retry_pending(question_id=None, limit=20, automatic=False):
    counts = {"processed": 0, "suggested": 0}
    with db.engine().connect() as lock:
        acquired = lock.execute(text("SELECT pg_try_advisory_lock(739253)")).scalar_one()
        if not acquired:
            return {**counts, "busy": True}
        try:
            sql = "SELECT * FROM questions WHERE status='pending'"
            params = {"limit": min(max(limit, 1), 20)}
            if question_id is not None:
                sql += " AND id=:id"
                params["id"] = question_id
            if automatic:
                # Até cinco tentativas por pergunta; uma atualização do conhecimento
                # permite uma nova tentativa mesmo após atingir esse limite.
                sql += """ AND (last_attempt_at IS NULL OR last_attempt_at < now() - interval '1 hour')
                    AND (attempts < 5 OR EXISTS (
                        SELECT 1 FROM knowledge WHERE updated_at > questions.last_attempt_at))"""
            for question in db.rows(sql + " ORDER BY last_attempt_at NULLS FIRST,id LIMIT :limit", params):
                result = answer(question["question"], question["filters"])
                db.save_result(question["id"], result, suggested=True)
                counts["processed"] += 1
                counts["suggested"] += int(result["answered"])
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(739253)"))
    return counts

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Repetir enquanto o processo estiver ativo")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    db.initialize()
    while True:
        try:
            logging.info("Reprocessamento: %s", retry_pending(automatic=True))
        except Exception:
            logging.exception("Falha no lote; perguntas permanecem no banco")
            if not args.loop:
                raise
        if not args.loop:
            break
        time.sleep(max(60, int(os.getenv("RETRY_INTERVAL_SECONDS", "3600"))))

if __name__ == "__main__":
    main()
