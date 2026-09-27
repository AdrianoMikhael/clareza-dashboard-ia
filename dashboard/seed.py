"""Dados fictícios reproduzíveis. Uma linha representa um pedido de um produto."""
import random
from datetime import date, timedelta
from sqlalchemy import text
from .db import engine, initialize
from .text import normalize

FAQ = [
    ("Como o faturamento é calculado?", "O faturamento soma quantidade × preço unitário dos pedidos concluídos. Pedidos cancelados são excluídos. Este exemplo não modela impostos, frete ou descontos.", "Dicionário de indicadores • exemplo"),
    ("O que é ticket médio?", "É o faturamento dividido pelo número de pedidos concluídos no recorte selecionado. Cada linha deste exemplo representa um pedido de um único produto.", "Dicionário de indicadores • exemplo"),
    ("Os dados são reais?", "Não. Os pedidos foram gerados artificialmente com uma semente fixa para permitir reproduzir a demonstração.", "Documentação da demonstração"),
    ("O que acontece com perguntas sem resposta?", "A pergunta e os filtros ficam salvos no PostgreSQL. Um responsável pode cadastrar conhecimento e reprocessar as pendências. Sugestões de reprocessamento exigem revisão.", "Fluxo do assistente • exemplo"),
]

def seed():
    initialize()
    rng = random.Random(42)
    catalog = [("Tecnologia", "Monitor", 129900), ("Tecnologia", "Teclado", 24990),
               ("Escritório", "Cadeira", 89900), ("Escritório", "Caderno", 2990),
               ("Casa", "Luminária", 15990), ("Casa", "Organizador", 7990)]
    with engine().begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(739252)"))
        if conn.execute(text("SELECT count(*) FROM sales")).scalar_one() == 0:
            records = []
            for i in range(1, 1801):
                category, product, cents = rng.choice(catalog)
                records.append(dict(id=i, sold_on=date(2026, 4, 1) + timedelta(days=rng.randrange(177)),
                    region=rng.choice(["Sudeste", "Sul", "Nordeste", "Centro-Oeste", "Norte"]),
                    category=category, product=product, units=rng.randint(1, 5), unit_price=cents / 100,
                    status="cancelada" if rng.random() < 0.08 else "concluida"))
            conn.execute(text("""INSERT INTO sales(id,sold_on,region,category,product,units,unit_price,status)
                VALUES (:id,:sold_on,:region,:category,:product,:units,:unit_price,:status)"""), records)
        # Inicializar conhecimento só em uma base vazia: editar uma pergunta
        # original não deve fazer sua versão antiga reaparecer no próximo boot.
        if conn.execute(text("SELECT count(*) FROM knowledge")).scalar_one() > 0:
            return
        for q, a, source in FAQ:
            # Não reativa nem substitui conhecimento alterado pelo usuário.
            record = conn.execute(text("""INSERT INTO knowledge(question,normalized_question,answer,source)
                VALUES (:q,:n,:a,:s) ON CONFLICT(normalized_question) DO NOTHING RETURNING *"""),
                {"q": q, "n": normalize(q), "a": a, "s": source}).mappings().first()
            if record:
                from .db import _history
                _history(conn, record)

if __name__ == "__main__":
    seed()
    print("Banco preparado: 1.800 pedidos fictícios e conhecimento inicial (sem sobrescrever dados).")
