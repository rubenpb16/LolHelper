"""
Pool de conexiones PostgreSQL compartido por todos los módulos.

El pool se inicializa de forma lazy (al primer uso) con reintentos,
para que el contenedor no crashee si la BD tarda en estar disponible
al arrancar (situación habitual en despliegues en la nube).
"""
import time
import logging
from contextlib import contextmanager
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from psycopg2 import OperationalError
from psycopg2.extensions import cursor as _DefaultCursor
from config import DB_CONFIG

_pool = None
_log  = logging.getLogger("db")


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is not None:
        return _pool

    last_err = None
    for attempt in range(1, 11):          # hasta 10 intentos (30 s)
        try:
            _pool = ThreadedConnectionPool(minconn=2, maxconn=10, **DB_CONFIG)
            _log.info(f"Pool de BD listo (intento {attempt})")
            return _pool
        except OperationalError as e:
            last_err = e
            _log.warning(f"BD no disponible (intento {attempt}/10): {e} — reintentando en 3s")
            time.sleep(3)

    raise RuntimeError(f"No se pudo conectar a la BD tras 10 intentos: {last_err}")


@contextmanager
def get_db():
    """Context manager para extractor, alertas y scripts. Auto-commit/rollback."""
    conn = _get_pool().getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _get_pool().putconn(conn)


def get_db_api():
    """Generador FastAPI (Depends). Usa RealDictCursor; el endpoint hace commit explícito."""
    conn = _get_pool().getconn()
    conn.cursor_factory = RealDictCursor
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.cursor_factory = _DefaultCursor  # evita contaminar el pool
        _get_pool().putconn(conn)
