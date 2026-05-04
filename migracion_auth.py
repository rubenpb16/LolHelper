"""
Migración — añade password_hash a usuarios_app
Ejecuta UNA SOLA VEZ: python migracion_auth.py
"""
import psycopg2
from config import DB_CONFIG

with psycopg2.connect(**DB_CONFIG) as c:
    cur = c.cursor()

    # Añadir columna password_hash si no existe
    cur.execute("""
        ALTER TABLE usuarios_app
        ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)
    """)

    # Añadir índice en email para búsquedas de login rápidas
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios_app(email)
    """)

    c.commit()
    print("✅ Migración completada — columna password_hash añadida")

    # Verificar
    cur.execute("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_name = 'usuarios_app' AND column_name = 'password_hash'
    """)
    print(f"   Columna: {cur.fetchone()}")