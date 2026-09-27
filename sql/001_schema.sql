-- Esquema inicial idempotente. Nunca apaga dados existentes.
CREATE TABLE IF NOT EXISTS sales (
    id BIGINT PRIMARY KEY,
    sold_on DATE NOT NULL,
    region TEXT NOT NULL,
    category TEXT NOT NULL,
    product TEXT NOT NULL,
    units INTEGER NOT NULL CHECK (units > 0),
    unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
    status TEXT NOT NULL CHECK (status IN ('concluida','cancelada'))
);
CREATE INDEX IF NOT EXISTS sales_date_idx ON sales(sold_on);

CREATE TABLE IF NOT EXISTS knowledge (
    id BIGSERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    normalized_question TEXT NOT NULL UNIQUE,
    answer TEXT NOT NULL,
    source TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS knowledge_search_idx ON knowledge
USING GIN (to_tsvector('portuguese', question || ' ' || answer));

CREATE TABLE IF NOT EXISTS knowledge_history (
    id BIGSERIAL PRIMARY KEY,
    knowledge_id BIGINT NOT NULL REFERENCES knowledge(id),
    revision INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    source TEXT NOT NULL,
    active BOOLEAN NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS questions (
    id BIGSERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    filters JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','answered','suggested','dismissed')),
    answer TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempt_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS questions_pending_idx ON questions(status, created_at);

-- Cada processamento preserva o resultado anterior para avaliação.
CREATE TABLE IF NOT EXISTS question_attempts (
    id BIGSERIAL PRIMARY KEY,
    question_id BIGINT NOT NULL REFERENCES questions(id),
    answered BOOLEAN NOT NULL,
    answer TEXT,
    reason TEXT,
    evidence JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
