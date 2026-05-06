"""
═══════════════════════════════════════════════════════════════
  MÓDULO 3 — MOTOR DE ALERTAS
  LolHelper · alertas.py
═══════════════════════════════════════════════════════════════

  Calcula el progreso diario/semanal de cada usuario,
  compara con sus objetivos y decide qué alertas enviar.

  Este módulo NO envía emails directamente — llama al
  email_service.py (Módulo 4) para eso.

  Se llama desde scheduler.py (Módulo 5) tras cada sync.

  CÓMO USAR:
    from alertas import procesar_alertas_todos
    procesar_alertas_todos()
═══════════════════════════════════════════════════════════════
"""

import psycopg2
from datetime import datetime, date, timedelta
from db import get_db
# ══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════
#  CONEXIÓN
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
#  CONSULTAS A LA BASE DE DATOS
# ══════════════════════════════════════════════════════════════

def get_usuarios_con_objetivo():
    """
    Devuelve todos los usuarios activos que tienen un objetivo configurado.
    Incluye todo lo necesario para calcular alertas.
    """
    with get_db() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT
                u.id                    AS usuario_id,
                u.email,
                u.puuid,
                u.riot_game_name,
                u.riot_tag_line,
                u.consentimiento_emails,
                o.id                    AS objetivo_id,
                o.limite_horas_dia,
                o.limite_horas_semana,
                o.dias_descanso_semana,
                o.alerta_al_porcentaje,
                o.resumen_nocturno,
                o.hora_resumen
            FROM usuarios_app u
            JOIN objetivos o ON o.usuario_id = u.id AND o.activo = TRUE
            WHERE u.activo = TRUE
              AND u.consentimiento_datos = TRUE
              AND u.consentimiento_emails = TRUE
              AND u.datos_anonimizados = FALSE
              AND u.puuid IS NOT NULL
        """)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def calcular_horas_hoy(puuid):
    """Horas jugadas hoy (suma de duracion_min de todas las partidas de hoy)."""
    with get_db() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT
                COALESCE(SUM(duracion_min), 0) / 60.0  AS horas,
                COUNT(*)                                AS partidas,
                COALESCE(SUM(CASE WHEN rendicion AND resultado = 'Derrota' THEN 1 ELSE 0 END), 0) AS rendiciones,
                COALESCE(SUM(CASE WHEN NOT apto_para_progresion THEN 1 ELSE 0 END), 0) AS afks,
                MODE() WITHIN GROUP (ORDER BY campeon)  AS campeon_mas_jugado
            FROM partidas
            WHERE puuid = %s AND fecha = CURRENT_DATE
        """, (puuid,))
        row = cur.fetchone()
        return {
            "horas":            float(row[0] or 0),
            "partidas":         int(row[1] or 0),
            "rendiciones":      int(row[2] or 0),
            "afks":             int(row[3] or 0),
            "campeon_del_dia":  row[4] or "",
        }


def calcular_horas_semana(puuid):
    """Horas jugadas esta semana (lunes a hoy)."""
    lunes = date.today() - timedelta(days=date.today().weekday())
    with get_db() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(duracion_min), 0) / 60.0
            FROM partidas
            WHERE puuid = %s AND fecha >= %s AND fecha <= CURRENT_DATE
        """, (puuid, lunes))
        return float(cur.fetchone()[0] or 0)


def calcular_racha(usuario_id):
    """
    Calcula la racha actual de días cumpliendo el objetivo.
    Recorre hacia atrás desde ayer buscando días consecutivos con objetivo_dia_cumplido=TRUE.
    """
    with get_db() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT fecha, objetivo_dia_cumplido
            FROM progreso_diario
            WHERE usuario_id = %s AND fecha < CURRENT_DATE
            ORDER BY fecha DESC
            LIMIT 60
        """, (usuario_id,))
        rows = cur.fetchall()

    racha = 0
    fecha_esperada = date.today() - timedelta(days=1)
    for fecha, cumplido in rows:
        if fecha != fecha_esperada:
            break
        if cumplido:
            racha += 1
            fecha_esperada -= timedelta(days=1)
        else:
            break
    return racha


def calcular_racha_maxima(usuario_id):
    """Racha máxima histórica del usuario."""
    with get_db() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT COALESCE(MAX(racha_dias_cumplidos), 0)
            FROM progreso_diario
            WHERE usuario_id = %s
        """, (usuario_id,))
        return int(cur.fetchone()[0] or 0)


def ya_se_envio_alerta_hoy(usuario_id, tipo):
    """Comprueba si ya se envió este tipo de alerta hoy para no duplicar."""
    with get_db() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM alertas_enviadas
            WHERE usuario_id = %s
              AND tipo = %s
              AND DATE(enviado_en) = CURRENT_DATE
              AND enviado_correctamente = TRUE
        """, (usuario_id, tipo))
        return cur.fetchone()[0] > 0


def obtener_progreso_hoy(usuario_id):
    """Obtiene el registro de progreso de hoy si existe."""
    with get_db() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT alerta_50_enviada, alerta_100_enviada, resumen_nocturno_enviado
            FROM progreso_diario
            WHERE usuario_id = %s AND fecha = CURRENT_DATE
        """, (usuario_id,))
        row = cur.fetchone()
        if not row:
            return {"alerta_50_enviada": False, "alerta_100_enviada": False, "resumen_nocturno_enviado": False}
        return {
            "alerta_50_enviada":         row[0],
            "alerta_100_enviada":        row[1],
            "resumen_nocturno_enviado":  row[2],
        }


def upsert_progreso_diario(usuario_id, datos):
    """Guarda o actualiza el snapshot de progreso del día."""
    with get_db() as c:
        cur = c.cursor()
        cur.execute("""
            INSERT INTO progreso_diario (
                usuario_id, fecha,
                horas_jugadas_dia, minutos_jugados_dia, horas_jugadas_semana,
                limite_dia, limite_semana,
                objetivo_dia_cumplido, objetivo_semana_cumplido,
                porcentaje_consumido_dia,
                racha_dias_cumplidos, racha_maxima_historica,
                partidas_jugadas, campeon_mas_jugado,
                rendiciones, afk_detectados,
                alerta_50_enviada, alerta_100_enviada, resumen_nocturno_enviado,
                calculado_en
            ) VALUES (
                %(usuario_id)s, CURRENT_DATE,
                %(horas_dia)s, %(minutos_dia)s, %(horas_semana)s,
                %(limite_dia)s, %(limite_semana)s,
                %(objetivo_dia_cumplido)s, %(objetivo_semana_cumplido)s,
                %(porcentaje_dia)s,
                %(racha)s, %(racha_maxima)s,
                %(partidas)s, %(campeon_del_dia)s,
                %(rendiciones)s, %(afks)s,
                %(alerta_50_enviada)s, %(alerta_100_enviada)s, %(resumen_nocturno_enviado)s,
                NOW()
            )
            ON CONFLICT (usuario_id, fecha) DO UPDATE SET
                horas_jugadas_dia        = EXCLUDED.horas_jugadas_dia,
                minutos_jugados_dia      = EXCLUDED.minutos_jugados_dia,
                horas_jugadas_semana     = EXCLUDED.horas_jugadas_semana,
                objetivo_dia_cumplido    = EXCLUDED.objetivo_dia_cumplido,
                objetivo_semana_cumplido = EXCLUDED.objetivo_semana_cumplido,
                porcentaje_consumido_dia = EXCLUDED.porcentaje_consumido_dia,
                racha_dias_cumplidos     = EXCLUDED.racha_dias_cumplidos,
                racha_maxima_historica   = EXCLUDED.racha_maxima_historica,
                partidas_jugadas         = EXCLUDED.partidas_jugadas,
                campeon_mas_jugado       = EXCLUDED.campeon_mas_jugado,
                rendiciones              = EXCLUDED.rendiciones,
                afk_detectados           = EXCLUDED.afk_detectados,
                alerta_50_enviada        = EXCLUDED.alerta_50_enviada,
                alerta_100_enviada       = EXCLUDED.alerta_100_enviada,
                resumen_nocturno_enviado = EXCLUDED.resumen_nocturno_enviado,
                calculado_en             = NOW()
        """, {**datos, "usuario_id": usuario_id})
        c.commit()


def registrar_alerta_enviada(usuario_id, tipo, datos, email, asunto, ok, error=None):
    """Guarda en el historial que se envió (o intentó) una alerta."""
    with get_db() as c:
        cur = c.cursor()
        cur.execute("""
            INSERT INTO alertas_enviadas (
                usuario_id, tipo,
                horas_jugadas, limite_configurado, porcentaje_consumido,
                partidas_del_dia, rendiciones_detectadas, afk_detectados,
                campeon_del_dia, racha_actual,
                email_destino, asunto,
                enviado_correctamente, error_envio
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            usuario_id, tipo,
            datos.get("horas_dia"), datos.get("limite_dia"),
            datos.get("porcentaje_dia"), datos.get("partidas"),
            datos.get("rendiciones"), datos.get("afks"),
            datos.get("campeon_del_dia"), datos.get("racha"),
            email, asunto, ok, error,
        ))
        c.commit()


def marcar_alerta_en_progreso(usuario_id, tipo):
    """Marca en progreso_diario que se envió una alerta para no reenviarla."""
    col_map = {
        "alerta_50":     "alerta_50_enviada",
        "alerta_100":    "alerta_100_enviada",
        "resumen_noche": "resumen_nocturno_enviado",
    }
    col = col_map.get(tipo)
    if not col:
        return
    with get_db() as c:
        cur = c.cursor()
        cur.execute(f"""
            UPDATE progreso_diario SET {col} = TRUE
            WHERE usuario_id = %s AND fecha = CURRENT_DATE
        """, (usuario_id,))
        c.commit()


def get_partidas_hoy(puuid):
    """Devuelve el detalle de las partidas jugadas hoy para el resumen."""
    with get_db() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT campeon, modo, resultado, kda, duracion_min,
                   rendicion, rendicion_temprana, apto_para_progresion
            FROM partidas
            WHERE puuid = %s AND fecha = CURRENT_DATE
            ORDER BY hora_inicio DESC
        """, (puuid,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_resumen_semana(puuid):
    """Devuelve las horas jugadas por día esta semana para el resumen semanal."""
    lunes = date.today() - timedelta(days=date.today().weekday())
    with get_db() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT
                fecha,
                ROUND(SUM(duracion_min) / 60.0, 2) AS horas,
                COUNT(*) AS partidas
            FROM partidas
            WHERE puuid = %s AND fecha >= %s AND fecha <= CURRENT_DATE
            GROUP BY fecha
            ORDER BY fecha
        """, (puuid, lunes))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ══════════════════════════════════════════════════════════════
#  LÓGICA DE ALERTAS
# ══════════════════════════════════════════════════════════════

def procesar_usuario(usuario, email_service):
    """
    Procesa las alertas de un usuario concreto.
    Devuelve un dict con el resumen de lo que se hizo.
    """
    uid       = usuario["usuario_id"]
    puuid     = usuario["puuid"]
    email     = usuario["email"]
    nombre    = usuario["riot_game_name"]
    limite_d  = float(usuario["limite_horas_dia"] or 0)
    limite_s  = float(usuario["limite_horas_semana"] or 0)
    umbral    = int(usuario["alerta_al_porcentaje"] or 100)
    resumen_n = usuario["resumen_nocturno"]
    hora_res  = usuario["hora_resumen"]

    # ── Calcular estado actual ────────────────────────────────
    stats_hoy   = calcular_horas_hoy(puuid)
    horas_hoy   = round(stats_hoy["horas"], 2)
    horas_semana= round(calcular_horas_semana(puuid), 2)
    racha       = calcular_racha(uid)
    racha_max   = calcular_racha_maxima(uid)
    progreso    = obtener_progreso_hoy(uid)

    # ── Calcular porcentaje consumido del límite diario ───────
    pct_dia = round((horas_hoy / limite_d * 100), 1) if limite_d > 0 else 0.0

    # ── Determinar si el objetivo diario se está cumpliendo ───
    objetivo_dia_cumplido    = (horas_hoy <= limite_d) if limite_d > 0 else None
    objetivo_semana_cumplido = (horas_semana <= limite_s) if limite_s > 0 else None

    datos = {
        "horas_dia":               horas_hoy,
        "minutos_dia":             int(horas_hoy * 60),
        "horas_semana":            horas_semana,
        "limite_dia":              limite_d,
        "limite_semana":           limite_s,
        "porcentaje_dia":          pct_dia,
        "objetivo_dia_cumplido":   objetivo_dia_cumplido,
        "objetivo_semana_cumplido":objetivo_semana_cumplido,
        "racha":                   racha,
        "racha_maxima":            racha_max,
        "partidas":                stats_hoy["partidas"],
        "campeon_del_dia":         stats_hoy["campeon_del_dia"],
        "rendiciones":             stats_hoy["rendiciones"],
        "afks":                    stats_hoy["afks"],
        "alerta_50_enviada":       progreso["alerta_50_enviada"],
        "alerta_100_enviada":      progreso["alerta_100_enviada"],
        "resumen_nocturno_enviado":progreso["resumen_nocturno_enviado"],
    }

    alertas_enviadas = []

    # ─────────────────────────────────────────────────────────
    # ALERTA DE UMBRAL PERSONALIZADO (ej. al 50% del límite)
    # Solo si tiene límite diario y no se ha enviado ya hoy
    # ─────────────────────────────────────────────────────────
    if limite_d > 0 and umbral < 100 and not progreso["alerta_50_enviada"]:
        if pct_dia >= umbral:
            print(f"     ⚡ Alerta {umbral}% → {horas_hoy}h / {limite_d}h ({pct_dia}%)")
            partidas_hoy = get_partidas_hoy(puuid)
            asunto, html = email_service.construir_email_umbral(
                nombre=nombre,
                horas_jugadas=horas_hoy,
                limite=limite_d,
                porcentaje=pct_dia,
                umbral=umbral,
                partidas=partidas_hoy,
                racha=racha,
                rendiciones=stats_hoy["rendiciones"],
                afks=stats_hoy["afks"],
            )
            ok, err = email_service.enviar(email, asunto, html)
            registrar_alerta_enviada(uid, "alerta_50", datos, email, asunto, ok, err)
            if ok:
                datos["alerta_50_enviada"] = True
                alertas_enviadas.append("alerta_50")

    # ─────────────────────────────────────────────────────────
    # ALERTA AL 100% — límite superado
    # ─────────────────────────────────────────────────────────
    if limite_d > 0 and not progreso["alerta_100_enviada"]:
        if horas_hoy > limite_d:
            exceso = round(horas_hoy - limite_d, 2)
            print(f"     🚨 Límite superado → {horas_hoy}h / {limite_d}h (+{exceso}h)")
            partidas_hoy = get_partidas_hoy(puuid)
            asunto, html = email_service.construir_email_limite_superado(
                nombre=nombre,
                horas_jugadas=horas_hoy,
                limite=limite_d,
                exceso=exceso,
                partidas=partidas_hoy,
                racha=racha,
                rendiciones=stats_hoy["rendiciones"],
                afks=stats_hoy["afks"],
                campeon=stats_hoy["campeon_del_dia"],
            )
            ok, err = email_service.enviar(email, asunto, html)
            registrar_alerta_enviada(uid, "alerta_100", datos, email, asunto, ok, err)
            if ok:
                datos["alerta_100_enviada"] = True
                alertas_enviadas.append("alerta_100")

    # ─────────────────────────────────────────────────────────
    # RESUMEN NOCTURNO (si el usuario lo tiene activado)
    # Se envía si la hora actual >= hora configurada y no se envió hoy
    # ─────────────────────────────────────────────────────────
    if resumen_n and not progreso["resumen_nocturno_enviado"]:
        hora_ahora = datetime.now().time()
        hora_envio = hora_res if hora_res else __import__("datetime").time(23, 0)
        if hora_ahora >= hora_envio:
            print(f"     🌙 Resumen nocturno → {horas_hoy}h jugadas hoy")
            partidas_hoy  = get_partidas_hoy(puuid)
            resumen_semana = get_resumen_semana(puuid)
            asunto, html = email_service.construir_email_resumen_noche(
                nombre=nombre,
                horas_hoy=horas_hoy,
                horas_semana=horas_semana,
                limite_dia=limite_d,
                limite_semana=limite_s,
                partidas=partidas_hoy,
                resumen_semana=resumen_semana,
                racha=racha,
                racha_maxima=racha_max,
                objetivo_cumplido=objetivo_dia_cumplido,
            )
            ok, err = email_service.enviar(email, asunto, html)
            registrar_alerta_enviada(uid, "resumen_noche", datos, email, asunto, ok, err)
            if ok:
                datos["resumen_nocturno_enviado"] = True
                alertas_enviadas.append("resumen_noche")

    # ─────────────────────────────────────────────────────────
    # RESUMEN SEMANAL — solo los lunes
    # ─────────────────────────────────────────────────────────
    if date.today().weekday() == 0 and not ya_se_envio_alerta_hoy(uid, "resumen_semana"):
        resumen_semana = get_resumen_semana(puuid)
        total_semana_anterior = sum(float(r["horas"]) for r in resumen_semana)
        if total_semana_anterior > 0:
            print(f"     📅 Resumen semanal → {total_semana_anterior}h la semana pasada")
            asunto, html = email_service.construir_email_resumen_semana(
                nombre=nombre,
                resumen=resumen_semana,
                total_horas=total_semana_anterior,
                limite_semana=limite_s,
                racha=racha,
                racha_maxima=racha_max,
                objetivo_cumplido=objetivo_semana_cumplido,
            )
            ok, err = email_service.enviar(email, asunto, html)
            registrar_alerta_enviada(uid, "resumen_semana", datos, email, asunto, ok, err)
            if ok:
                alertas_enviadas.append("resumen_semana")

    # ── Guardar progreso del día en DB ────────────────────────
    upsert_progreso_diario(uid, datos)

    return {
        "usuario":         nombre,
        "horas_hoy":       horas_hoy,
        "horas_semana":    horas_semana,
        "porcentaje":      pct_dia,
        "racha":           racha,
        "alertas_enviadas": alertas_enviadas,
    }


def procesar_alertas_todos(email_service):
    """
    Punto de entrada principal.
    Procesa las alertas de todos los usuarios activos con objetivo.
    Llamado desde scheduler.py tras cada sync.
    """
    print("\n  🔔 Motor de alertas")
    print("  " + "─" * 50)

    usuarios = get_usuarios_con_objetivo()
    if not usuarios:
        print("  ℹ️  No hay usuarios con objetivo configurado")
        return

    resultados = []
    for u in usuarios:
        try:
            res = procesar_usuario(u, email_service)
            resultados.append(res)
            alertas = ", ".join(res["alertas_enviadas"]) or "ninguna"
            print(
                f"  ✅ {res['usuario']:<16} "
                f"{res['horas_hoy']:>5.2f}h hoy  "
                f"{res['horas_semana']:>6.2f}h semana  "
                f"racha:{res['racha']}d  "
                f"alertas:[{alertas}]"
            )
        except Exception as e:
            print(f"  ❌ {u['riot_game_name']}: {e}")

    print(f"\n  📊 {len(resultados)} usuarios procesados")
    total_alertas = sum(len(r["alertas_enviadas"]) for r in resultados)
    if total_alertas:
        print(f"  📧 {total_alertas} alertas enviadas")
    return resultados