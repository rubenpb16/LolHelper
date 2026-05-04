"""
Migración — añade token_version a usuarios_app
Ejecuta UNA SOLA VEZ: python migracion_token_version.py
"""
import psycopg2
from config import DB_CONFIG

with psycopg2.connect(**DB_CONFIG) as c:
    cur = c.cursor()
    cur.execute("""
        ALTER TABLE usuarios_app
        ADD COLUMN IF NOT EXISTS token_version INT NOT NULL DEFAULT 1
    """)
    c.commit()
    print("Migracion completada - columna token_version añadida")

    cur.execute("SELECT COUNT(*) FROM usuarios_app")
    total = cur.fetchone()[0]
    print(f"Usuarios existentes: {total} (token_version = 1 para todos)")
