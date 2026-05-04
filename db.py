"""
Pool de conexiones PostgreSQL compartido por todos los módulos.
Evita abrir/cerrar una conexión nueva por cada operación.
"""
from contextlib import contextmanager
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG

_pool = ThreadedConnectionPool(minconn=2, maxconn=10, **DB_CONFIG)


@contextmanager
def get_db():
    """Context manager para extractor, alertas y scripts. Auto-commit/rollback."""
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def get_db_api():
    """Generador FastAPI (Depends). Usa RealDictCursor; el endpoint hace commit explícito."""
    conn = _pool.getconn()
    conn.cursor_factory = RealDictCursor
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
