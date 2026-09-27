"""Configuração central; nenhum segredo fica no código-fonte."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://dashboard:dashboard_local@localhost:5433/dashboard")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
AI_BACKEND = os.getenv("AI_BACKEND", "ollama")
if AI_BACKEND not in ("ollama", "llamacpp"):
    raise ValueError("AI_BACKEND deve ser ollama ou llamacpp")
