"""
Carga las variables de entorno desde .env y las expone al resto del proyecto.
Todos los módulos deben importar credenciales desde aquí, nunca hardcodearlas.

En Railway las variables de la BD se inyectan como PG* (PGHOST, PGDATABASE…),
por lo que se usan como fallback cuando las propias del proyecto no están definidas.
"""
import os
from dotenv import load_dotenv

load_dotenv()

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

# Orígenes permitidos en CORS.
# En local: localhost:5173 y localhost:3000.
# En Railway: añadir la URL pública del frontend separada por comas.
# Ejemplo: CORS_ORIGINS=https://lolhelper.up.railway.app
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:3000"
    ).split(",")
    if o.strip()
]
