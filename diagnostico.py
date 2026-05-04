"""
Script de diagnóstico — ejecuta esto en tu carpeta LolHelp
para ver exactamente qué hay en la DB y simular una alerta.
"""
import psycopg2
from datetime import date, timedelta
from config import DB_CONFIG

def conn():
    return psycopg2.connect(**DB_CONFIG)

print("=" * 60)
print("  DIAGNÓSTICO LolHelper")
print("=" * 60)

with conn() as c:
    cur = c.cursor()

    # 1. Usuarios y sus objetivos
    print("\n[1] USUARIOS Y OBJETIVOS")
    cur.execute("""
        SELECT u.riot_game_name, u.riot_tag_line, u.puuid,
               o.limite_horas_dia, o.limite_horas_semana,
               o.alerta_al_porcentaje, o.resumen_nocturno
        FROM usuarios_app u
        LEFT JOIN objetivos o ON o.usuario_id = u.id AND o.activo = TRUE
        WHERE u.activo = TRUE
    """)
    for r in cur.fetchall():
        print(f"  {r[0]}#{r[1]}  |  puuid: {'OK' if r[2] else '❌ NULL'}  |  "
              f"límite_día: {r[3]}h  |  límite_semana: {r[4]}h  |  "
              f"umbral: {r[5]}%  |  resumen_noche: {r[6]}")

    # 2. Partidas por usuario — últimos 7 días
    print("\n[2] PARTIDAS POR USUARIO (últimos 7 días)")
    cur.execute("""
        SELECT j.game_name, p.fecha,
               COUNT(*) AS partidas,
               ROUND(SUM(p.duracion_min)/60.0, 2) AS horas
        FROM partidas p
        JOIN jugadores j ON j.puuid = p.puuid
        WHERE p.fecha >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY j.game_name, p.fecha
        ORDER BY j.game_name, p.fecha DESC
    """)
    rows = cur.fetchall()
    if not rows:
        print("  ⚠️  No hay partidas en los últimos 7 días")
        print("     → Ejecuta primero: python extractor.py")
    else:
        for r in rows:
            print(f"  {r[0]:<16} {r[1]}  {r[2]} partidas  {r[3]}h")

    # 3. Partidas de HOY
    print("\n[3] PARTIDAS DE HOY")
    cur.execute("""
        SELECT j.game_name, COUNT(*), ROUND(SUM(p.duracion_min)/60.0, 2)
        FROM partidas p
        JOIN jugadores j ON j.puuid = p.puuid
        WHERE p.fecha = CURRENT_DATE
        GROUP BY j.game_name
    """)
    rows = cur.fetchall()
    if not rows:
        print("  ℹ️  Nadie ha jugado hoy todavía (normal si es pronto)")
    else:
        for r in rows:
            print(f"  {r[0]:<16} {r[1]} partidas  {r[2]}h")

    # 4. Rango de fechas en DB
    print("\n[4] RANGO DE DATOS EN DB")
    cur.execute("""
        SELECT j.game_name,
               MIN(p.fecha) AS primera,
               MAX(p.fecha) AS ultima,
               COUNT(*) AS total_partidas,
               ROUND(SUM(p.duracion_min)/60.0, 1) AS total_horas
        FROM partidas p
        JOIN jugadores j ON j.puuid = p.puuid
        GROUP BY j.game_name
    """)
    rows = cur.fetchall()
    if not rows:
        print("  ❌ No hay partidas en la DB — ejecuta python extractor.py primero")
    else:
        for r in rows:
            print(f"  {r[0]:<16} {r[1]} → {r[2]}  |  {r[3]} partidas  |  {r[4]}h totales")

    # 5. Estado de alertas_enviadas
    print("\n[5] ALERTAS ENVIADAS (últimas 10)")
    cur.execute("""
        SELECT u.riot_game_name, a.tipo, a.horas_jugadas,
               a.enviado_correctamente, a.enviado_en::date
        FROM alertas_enviadas a
        JOIN usuarios_app u ON u.id = a.usuario_id
        ORDER BY a.enviado_en DESC LIMIT 10
    """)
    rows = cur.fetchall()
    if not rows:
        print("  ℹ️  Ninguna alerta enviada aún")
    else:
        for r in rows:
            ok = "✅" if r[3] else "❌"
            print(f"  {ok} {r[0]:<16} {r[1]:<20} {r[2]}h  {r[4]}")

print("\n" + "=" * 60)
print("  FIN DIAGNÓSTICO")
print("=" * 60)