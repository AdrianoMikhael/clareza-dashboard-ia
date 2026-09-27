"""Entrada portátil: prepara o banco e inicia o dashboard."""
import os
import subprocess
import sys
from dashboard.seed import seed
from dashboard.config import ROOT

if __name__ == "__main__":
    try:
        seed()
    except Exception:
        print("Não foi possível preparar o PostgreSQL. Confira DATABASE_URL e se o banco está ligado.", file=sys.stderr)
        sys.exit(1)
    raise SystemExit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
        "--server.address", os.getenv("APP_ADDRESS", "127.0.0.1"), "--server.port", os.getenv("APP_PORT", "8501")], cwd=ROOT))
