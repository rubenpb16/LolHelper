"""
Carga las variables de entorno y las expone al resto del proyecto.

Prioridad de configuración de la BD:
  1. DATABASE_URL  — inyectada automáticamente por Railway cuando se enlaza el plugin PostgreSQL
  2. DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD  — variables propias del proyecto
  3. PGHOST / PGPORT / PGDATABASE / PGUSER / PGPASSWORD   — nombres estándar de PostgreSQL
  4. localhost:5432/lol_tracker  — fallback para desarrollo local
"""
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

_database_url = os.getenv("DATABASE_URL")

if _database_url:
    _u = urlparse(_database_url)
    DB_CONFIG = {
        "host":     _u.hostname,
        "port":     _u.port or 5432,
        "dbname":   _u.path.lstrip("/"),
        "user":     _u.username,
        "password": _u.password,
    }
else:
    DB_CONFIG = {
        "host":     os.getenv("DB_HOST") or os.getenv("PGHOST",     "localhost"),
        "port":     int(os.getenv("DB_PORT") or os.getenv("PGPORT", "5432")),
        "dbname":   os.getenv("DB_NAME") or os.getenv("PGDATABASE", "lol_tracker"),
        "user":     os.getenv("DB_USER") or os.getenv("PGUSER",     "postgres"),
        "password": os.getenv("DB_PASSWORD") or os.getenv("PGPASSWORD"),
    }

RIOT_API_KEY   = os.getenv("RIOT_API_KEY")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL     = os.getenv("FROM_EMAIL", "onboarding@resend.dev")
JWT_SECRET     = os.getenv("JWT_SECRET")
JWT_ALGO       = "HS256"
JWT_MINUTOS    = 60 * 24 * 7

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:3000"
    ).split(",")
    if o.strip()
]
