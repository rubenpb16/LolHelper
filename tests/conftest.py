"""
Configuración global de tests.

Orden crítico:
  1. Setear env vars (DB_NAME → test DB, JWT_SECRET → valor de test)
  2. Crear la BD de test en PostgreSQL ANTES de importar api.py
     (db.py crea el pool al importarse; si la BD no existe, falla)
  3. Crear el esquema
  4. Importar la app y crear el TestClient
"""
import os

# ── 1. Env vars ANTES de cualquier import del proyecto ────────────────
os.environ["DB_NAME"]    = "lol_tracker_test"
os.environ["JWT_SECRET"] = "test-secret-32-chars-exactly-ok-x"

# ── 2. Cargar el resto del .env (host, user, password, etc.) ─────────
from dotenv import load_dotenv
load_dotenv(override=False)   # no sobreescribe lo que ya seteamos

import psycopg2
import pytest

_CFG_ADMIN = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   "postgres",              # conectar al sistema para crear DB
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", "root1234"),
}

_CFG_TEST = {**_CFG_ADMIN, "dbname": "lol_tracker_test"}


def _admin_conn():
    return psycopg2.connect(**_CFG_ADMIN)


def _test_conn():
    return psycopg2.connect(**_CFG_TEST)


# Recrear la BD de test en cada sesión para garantizar schema limpio ─
_adm = _admin_conn()
_adm.autocommit = True
_cur = _adm.cursor()
_cur.execute("DROP DATABASE IF EXISTS lol_tracker_test")
_cur.execute("CREATE DATABASE lol_tracker_test")
_adm.close()

# ── 3. Ahora podemos importar la app (el pool apunta a lol_tracker_test)
from fastapi.testclient import TestClient
from api import app
from database_setup import TABLAS


# ─────────────────────────────────────────────────────────────────────
#  Fixtures de sesión
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def create_schema():
    """Crea el esquema en la BD de test una sola vez por sesión."""
    conn = _test_conn()
    cur  = conn.cursor()
    for sql in TABLAS.values():
        cur.execute(sql)
    conn.commit()
    conn.close()
    yield
    # Limpiar todas las tablas al terminar la sesión (sin borrar la BD)
    conn = _test_conn()
    conn.autocommit = True
    conn.cursor().execute("""
        DO $$ DECLARE r RECORD;
        BEGIN
          FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public')
          LOOP
            EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE';
          END LOOP;
        END $$;
    """)
    conn.close()


@pytest.fixture(scope="session")
def client(create_schema):
    with TestClient(app) as c:
        yield c


# ─────────────────────────────────────────────────────────────────────
#  Datos y helpers de autenticación
# ─────────────────────────────────────────────────────────────────────

USUARIO_TEST = {
    "email":               "test@lolhelper.dev",
    "password":            "contraseña_test_8",
    "riot_game_name":      "TestUser",
    "riot_tag_line":       "TEST",
    "limite_horas_dia":    2.0,
    "limite_horas_semana": 10.0,
    "alerta_porcentaje":   80,
    "consentimiento_datos":  True,
    "consentimiento_emails": True,
}


@pytest.fixture
def usuario_registrado(client):
    """Registra un usuario fresco y lo borra al terminar."""
    client.post("/auth/register", json=USUARIO_TEST)
    yield USUARIO_TEST
    conn = _test_conn()
    conn.cursor().execute(
        "DELETE FROM usuarios_app WHERE email = %s", (USUARIO_TEST["email"],)
    )
    conn.commit()
    conn.close()


@pytest.fixture
def cookie_sesion(client, usuario_registrado):
    """Devuelve el TestClient ya autenticado (con cookie de sesión)."""
    r = client.post("/auth/login", data={
        "username": usuario_registrado["email"],
        "password": usuario_registrado["password"],
    })
    assert r.status_code == 200
    return client.cookies
