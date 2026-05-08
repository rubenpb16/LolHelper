"""
═══════════════════════════════════════════════════════════════
  MÓDULO 2 — EXTRACTOR
  LolHelper · extractor.py
═══════════════════════════════════════════════════════════════

  Extrae partidas de la API de Riot para todos los usuarios
  registrados en la app y las guarda en PostgreSQL.

  Solo descarga partidas nuevas (evita duplicados).
  Respeta el rate limit de la API automáticamente.
  Actualiza puuid, nivel, ranked y progreso diario.

  CÓMO USAR:
    python extractor.py                → sync todos los usuarios
    python extractor.py --usuario EUW zRamBoXx → sync un usuario
    python extractor.py --dias 7      → solo últimos 7 días
═══════════════════════════════════════════════════════════════
"""

import sys
import time
import requests
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta, date
from config import RIOT_API_KEY as API_KEY, SYNC_DIAS_INICIAL
from db import get_db
# ══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════

SLEEP_ENTRE_REQUESTS    = 1.3       # Con Production Key (100 req/s) es suficiente
SLEEP_ENTRE_USUARIOS    = 1.0
MAX_PARTIDAS_POR_PAGINA = 100       # Máximo por llamada que permite la API
DIAS_ATRAS_DEFAULT      = SYNC_DIAS_INICIAL   # Configurable via env SYNC_DIAS_INICIAL
DIAS_VENTANA_PAGINACION = 30        # Tamaño de cada ventana al paginar


REGION_MAP = {
    "EUW":  ("euw1", "europe"),
    "EUNE": ("eun1", "europe"),
    "NA1":  ("na1",  "americas"),
    "LAS":  ("la2",  "americas"),
    "LAN":  ("la1",  "americas"),
    "BR1":  ("br1",  "americas"),
    "KR":   ("kr",   "asia"),
    "JP1":  ("jp1",  "asia"),
}
 
QUEUE_NOMBRES = {
    420:  "Ranked Solo",
    440:  "Ranked Flex",
    400:  "Normal Draft",
    430:  "Normal Ciego",
    450:  "ARAM",
    900:  "URF",
    1020: "One for All",
    1300: "Nexus Blitz",
    1700: "Arena",
    1900: "URF Pick",
    720:  "ARAM Clash",
    700:  "Clash",
    830:  "Co-op Fácil",
    840:  "Co-op Normal",
    850:  "Co-op Difícil",
    0:    "Personalizada",
}
 
HEADERS = {"X-Riot-Token": API_KEY}
 
 
# ══════════════════════════════════════════════════════════════
#  BASE DE DATOS
# ══════════════════════════════════════════════════════════════
 
def get_usuarios_activos():
    """Devuelve todos los usuarios activos con consentimiento."""
    with get_db() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT
                u.id,
                u.email,
                u.riot_game_name,
                u.riot_tag_line,
                u.puuid,
                u.region,
                u.ultima_sincronizacion
            FROM usuarios_app u
            WHERE u.activo = TRUE
              AND u.consentimiento_datos = TRUE
              AND u.datos_anonimizados = FALSE
            ORDER BY u.ultima_sincronizacion ASC NULLS FIRST
        """)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
 
 
def get_match_ids_en_db(puuid):
    """IDs de partidas ya guardadas para este jugador."""
    with get_db() as c:
        cur = c.cursor()
        cur.execute("SELECT match_id FROM partidas WHERE puuid = %s", (puuid,))
        return {r[0] for r in cur.fetchall()}
 
 
def get_fecha_ultima_partida(puuid):
    """Fecha de la partida más reciente guardada en DB."""
    with get_db() as c:
        cur = c.cursor()
        cur.execute(
            "SELECT MAX(fecha) FROM partidas WHERE puuid = %s", (puuid,)
        )
        resultado = cur.fetchone()[0]
        return resultado  # date o None
 
 
def upsert_jugador(puuid, game_name, tag_line, region, nivel, icono_id):
    sql = """
    INSERT INTO jugadores (puuid, game_name, tag_line, region, nivel_invocador, icono_id, ultima_sincronizacion)
    VALUES (%s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (puuid) DO UPDATE SET
        game_name             = EXCLUDED.game_name,
        nivel_invocador       = EXCLUDED.nivel_invocador,
        icono_id              = EXCLUDED.icono_id,
        ultima_sincronizacion = NOW()
    """
    with get_db() as c:
        c.cursor().execute(sql, (puuid, game_name, tag_line, region, nivel, icono_id))
        c.commit()
 
 
def upsert_puuid_en_usuario(usuario_id, puuid):
    with get_db() as c:
        c.cursor().execute(
            "UPDATE usuarios_app SET puuid = %s, ultima_sincronizacion = NOW() WHERE id = %s",
            (puuid, usuario_id)
        )
        c.commit()
 
 
def upsert_ranked(puuid, ranked_list):
    sql = """
    INSERT INTO ranked_info
        (puuid, queue_type, tier, division, lp, victorias, derrotas, hot_streak, en_serie_de_promos, actualizado_en)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (puuid, queue_type) DO UPDATE SET
        tier              = EXCLUDED.tier,
        division          = EXCLUDED.division,
        lp                = EXCLUDED.lp,
        victorias         = EXCLUDED.victorias,
        derrotas          = EXCLUDED.derrotas,
        hot_streak        = EXCLUDED.hot_streak,
        en_serie_de_promos= EXCLUDED.en_serie_de_promos,
        actualizado_en    = NOW()
    """
    with get_db() as c:
        cur = c.cursor()
        for q in ranked_list:
            cur.execute(sql, (
                puuid,
                q.get("queueType"),
                q.get("tier"),
                q.get("rank"),
                q.get("leaguePoints", 0),
                q.get("wins", 0),
                q.get("losses", 0),
                q.get("hotStreak", False),
                q.get("miniSeries") is not None,
            ))
        c.commit()
 
 
_TIER_PTS     = {'IRON': 0, 'BRONZE': 400, 'SILVER': 800, 'GOLD': 1200,
                  'PLATINUM': 1600, 'EMERALD': 2000, 'DIAMOND': 2400,
                  'MASTER': 2800, 'GRANDMASTER': 3200, 'CHALLENGER': 3600}
_DIVISION_PTS = {'IV': 0, 'III': 100, 'II': 200, 'I': 300}


def snapshot_rank(puuid, ranked_list):
    """Guarda un snapshot diario de LP para tracking histórico de progresión."""
    with get_db() as c:
        cur = c.cursor()
        for q in ranked_list:
            if q.get('queueType') != 'RANKED_SOLO_5x5':
                continue
            tier     = q.get('tier', '')
            division = q.get('rank', '')
            lp       = q.get('leaguePoints', 0)
            puntos   = _TIER_PTS.get(tier, 0) + _DIVISION_PTS.get(division, 0) + lp
            cur.execute("""
                INSERT INTO historial_rank
                    (puuid, fecha, queue_type, tier, division, lp, puntos_totales, victorias, derrotas)
                VALUES (%s, CURRENT_DATE, 'RANKED_SOLO_5x5', %s, %s, %s, %s, %s, %s)
                ON CONFLICT (puuid, fecha, queue_type) DO UPDATE SET
                    tier           = EXCLUDED.tier,
                    division       = EXCLUDED.division,
                    lp             = EXCLUDED.lp,
                    puntos_totales = EXCLUDED.puntos_totales,
                    victorias      = EXCLUDED.victorias,
                    derrotas       = EXCLUDED.derrotas,
                    registrado_en  = NOW()
            """, (puuid, tier, division, lp, puntos, q.get('wins', 0), q.get('losses', 0)))
        c.commit()


def insertar_partidas(partidas):
    if not partidas:
        return 0
 
    sql = """
    INSERT INTO partidas (
        match_id, puuid, fecha, hora_inicio, hora_fin, duracion_min, duracion_seg,
        modo, queue_id, parche,
        campeon, campeon_id, rol, rol_individual,
        resultado, rendicion, rendicion_temprana, equipo_rindio_temprano,
        kills, deaths, assists, kda, primera_sangre, kills_solitarios,
        racha_maxima_kills, multi_kill_maximo,
        doble_kills, triple_kills, cuadra_kills, penta_kills,
        dano_total_campeon, dano_magico_campeon, dano_fisico_campeon, dano_verdadero_campeon,
        dano_total_recibido, dano_mitigado, dano_a_objetivos, dano_a_torres,
        curacion_total, curacion_a_aliados, escudo_a_aliados, porcentaje_dano_equipo,
        oro_ganado, oro_gastado,
        cs_total, cs_minions, cs_neutrales, cs_por_minuto,
        objetos_comprados, consumibles_comprados,
        item0, item1, item2, item3, item4, item5, item6,
        vision_score, wards_colocados, wards_eliminados,
        wards_control_comprados, wards_detector_colocados,
        kills_dragon, kills_baron, kills_inhibidor, kills_torre, objetivos_robados,
        tiempo_muerto_seg, tiempo_vivo_max_seg,
        hechizo1_lanzado, hechizo2_lanzado, hechizo3_lanzado, hechizo4_lanzado,
        summoner1_lanzado, summoner2_lanzado,
        cc_aplicado_seg, saves_a_aliados, apto_para_progresion, takedowns_primeros_10min,
        control_aplicado_a_otros, intercepciones_habilidad
    ) VALUES %s
    ON CONFLICT (match_id) DO NOTHING
    """
 
    rows = [(
        p["match_id"], p["puuid"], p["fecha"], p["hora_inicio"], p["hora_fin"],
        p["duracion_min"], p["duracion_seg"],
        p["modo"], p["queue_id"], p["parche"],
        p["campeon"], p["campeon_id"], p["rol"], p["rol_individual"],
        p["resultado"], p["rendicion"], p["rendicion_temprana"], p["equipo_rindio_temprano"],
        p["kills"], p["deaths"], p["assists"], p["kda"], p["primera_sangre"], p["kills_solitarios"],
        p["racha_maxima_kills"], p["multi_kill_maximo"],
        p["doble_kills"], p["triple_kills"], p["cuadra_kills"], p["penta_kills"],
        p["dano_total_campeon"], p["dano_magico_campeon"], p["dano_fisico_campeon"], p["dano_verdadero_campeon"],
        p["dano_total_recibido"], p["dano_mitigado"], p["dano_a_objetivos"], p["dano_a_torres"],
        p["curacion_total"], p["curacion_a_aliados"], p["escudo_a_aliados"], p["porcentaje_dano_equipo"],
        p["oro_ganado"], p["oro_gastado"],
        p["cs_total"], p["cs_minions"], p["cs_neutrales"], p["cs_por_minuto"],
        p["objetos_comprados"], p["consumibles_comprados"],
        p["item0"], p["item1"], p["item2"], p["item3"], p["item4"], p["item5"], p["item6"],
        p["vision_score"], p["wards_colocados"], p["wards_eliminados"],
        p["wards_control_comprados"], p["wards_detector_colocados"],
        p["kills_dragon"], p["kills_baron"], p["kills_inhibidor"], p["kills_torre"], p["objetivos_robados"],
        p["tiempo_muerto_seg"], p["tiempo_vivo_max_seg"],
        p["hechizo1_lanzado"], p["hechizo2_lanzado"], p["hechizo3_lanzado"], p["hechizo4_lanzado"],
        p["summoner1_lanzado"], p["summoner2_lanzado"],
        p["cc_aplicado_seg"], p["saves_a_aliados"], p["apto_para_progresion"], p["takedowns_primeros_10min"],
        p["control_aplicado_a_otros"], p["intercepciones_habilidad"],
    ) for p in partidas]
 
    with get_db() as c:
        execute_values(c.cursor(), sql, rows)
        c.commit()
    return len(rows)
 
 
def actualizar_sync_usuario(usuario_id):
    with get_db() as c:
        c.cursor().execute(
            "UPDATE usuarios_app SET ultima_sincronizacion = NOW() WHERE id = %s",
            (usuario_id,)
        )
        c.commit()
 
 
def log_sync(puuid, game_name, estado="running", partidas_nuevas=0, error=None, sync_id=None):
    with get_db() as c:
        cur = c.cursor()
        if not sync_id:
            cur.execute(
                "INSERT INTO sync_log (puuid, game_name, estado) VALUES (%s, %s, %s) RETURNING id",
                (puuid, game_name, estado)
            )
            sid = cur.fetchone()[0]
            c.commit()
            return sid
        else:
            cur.execute("""
                UPDATE sync_log
                SET fin_sync = NOW(), estado = %s, partidas_nuevas = %s, error_msg = %s
                WHERE id = %s
            """, (estado, partidas_nuevas, error, sync_id))
            c.commit()
 
 
# ══════════════════════════════════════════════════════════════
#  LLAMADAS A LA API DE RIOT
# ══════════════════════════════════════════════════════════════
 
def api_get(url, reintentos=3):
    """GET con manejo automático de rate limit y reintentos."""
    for intento in range(reintentos):
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
 
            if r.status_code == 429:
                espera = int(r.headers.get("Retry-After", 10))
                print(f"      ⏳ Rate limit → esperando {espera}s...")
                time.sleep(espera + 1)
                continue
 
            if r.status_code == 404:
                return None  # jugador/partida no encontrado

            if r.status_code == 403:
                raise PermissionError(f"403 Forbidden: la API key no tiene acceso a {url.split('riotgames.com')[1].split('?')[0]}")
 
            r.raise_for_status()
            return r.json()
 
        except requests.exceptions.Timeout:
            print(f"      ⚠️  Timeout (intento {intento + 1}/{reintentos})")
            time.sleep(3)
        except requests.exceptions.RequestException as e:
            if intento == reintentos - 1:
                raise
            print(f"      ⚠️  Error de red (intento {intento + 1}/{reintentos}): {e}")
            time.sleep(3)
 
    return None
 
 
def get_account(game_name, tag_line, routing):
    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    return api_get(url)
 
 
def get_summoner(puuid, region):
    url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    return api_get(url)
 
 
def get_ranked(puuid, region):
    url = f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    return api_get(url) or []
 
 
def get_match_ids_pagina(puuid, routing, ts_inicio, ts_fin, start=0):
    """Una sola página de 100 IDs dentro de una ventana de tiempo."""
    params = (
        f"start={start}&count={MAX_PARTIDAS_POR_PAGINA}"
        f"&startTime={ts_inicio}"
        f"&endTime={ts_fin}"
    )
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?{params}"
    return api_get(url) or []
 
 
def get_todos_match_ids(puuid, routing, fecha_inicio, fecha_fin, existentes=None):
    """
    Obtiene TODOS los IDs de partidas entre fecha_inicio y fecha_fin
    usando paginación por ventanas de tiempo de DIAS_VENTANA_PAGINACION días.
 
    La API limita 100 partidas por llamada, así que dividimos el rango
    total en ventanas más pequeñas y paginamos dentro de cada una.
 
    Esquema:
        [──── ventana 1 ────][──── ventana 2 ────] ... [──── ventana N ────]
        inicio              +30d                       fin
 
    Dentro de cada ventana, si hay exactamente 100 resultados, paginamos
    con start=100, start=200... hasta que devuelva menos de 100.
    """
    if existentes is None:
        existentes = set()
 
    todos_ids   = []
    cursor      = fecha_inicio  # avanzamos de ventana en ventana
 
    while cursor < fecha_fin:
        ventana_fin = min(cursor + timedelta(days=DIAS_VENTANA_PAGINACION), fecha_fin)
 
        ts_inicio_v = int(datetime.combine(cursor, datetime.min.time()).timestamp())
        ts_fin_v    = int(datetime.combine(ventana_fin, datetime.max.time()).timestamp())
 
        print(f"       📆 Ventana {cursor} → {ventana_fin}", end="", flush=True)
 
        # Paginar dentro de esta ventana
        start     = 0
        ids_ventana = []
        while True:
            time.sleep(SLEEP_ENTRE_REQUESTS)
            pagina = get_match_ids_pagina(puuid, routing, ts_inicio_v, ts_fin_v, start=start)
            ids_nuevos = [m for m in pagina if m not in existentes and m not in ids_ventana]
            ids_ventana.extend(ids_nuevos)
 
            if len(pagina) < MAX_PARTIDAS_POR_PAGINA:
                break  # última página de esta ventana
            start += MAX_PARTIDAS_POR_PAGINA
 
        print(f" → {len(ids_ventana)} partidas")
        todos_ids.extend(ids_ventana)
        cursor = ventana_fin + timedelta(days=1)
 
    return todos_ids
 
 
def get_match(match_id, routing):
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    return api_get(url)
 
 
# ══════════════════════════════════════════════════════════════
#  EXTRACCIÓN DE CAMPOS DE UNA PARTIDA
# ══════════════════════════════════════════════════════════════
 
def extraer_stats(match, puuid):
    """
    Extrae todos los campos relevantes de una partida para un jugador.
    Devuelve None si el jugador no está en la partida.
    """
    info = match.get("info", {})
    participants = info.get("participants", [])
    p = next((x for x in participants if x.get("puuid") == puuid), None)
    if not p:
        return None
 
    # ── Tiempo ──────────────────────────────────────────────
    ts_inicio    = info.get("gameStartTimestamp", 0) / 1000
    ts_fin       = info.get("gameEndTimestamp", 0) / 1000 if info.get("gameEndTimestamp") else None
    duracion_seg = info.get("gameDuration", 0)
    duracion_min = round(duracion_seg / 60, 2)
 
    dt_inicio = datetime.fromtimestamp(ts_inicio)
    dt_fin    = datetime.fromtimestamp(ts_fin) if ts_fin else None
 
    # ── Contexto ─────────────────────────────────────────────
    queue_id = info.get("queueId", 0)
    modo     = QUEUE_NOMBRES.get(queue_id, f"Cola {queue_id}")
    parche   = info.get("gameVersion", "")[:10]
 
    # ── Desafíos (sub-objeto con métricas avanzadas) ─────────
    ch = p.get("challenges", {})
 
    # ── KDA ──────────────────────────────────────────────────
    k, d, a = p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0)
    kda = round((k + a) / max(d, 1), 2)
 
    # ── CS ───────────────────────────────────────────────────
    cs_minions  = p.get("totalMinionsKilled", 0)
    cs_neutrales= p.get("neutralMinionsKilled", 0)
    cs_total    = cs_minions + cs_neutrales
    cs_min      = round(cs_total / duracion_min, 2) if duracion_min > 0 else 0
 
    return {
        # Identificación
        "match_id":   match["metadata"]["matchId"],
        "puuid":      puuid,
 
        # Tiempo
        "fecha":        dt_inicio.strftime("%Y-%m-%d"),
        "hora_inicio":  dt_inicio.strftime("%H:%M:%S"),
        "hora_fin":     dt_fin.strftime("%H:%M:%S") if dt_fin else None,
        "duracion_min": duracion_min,
        "duracion_seg": duracion_seg,
 
        # Contexto
        "modo":          modo,
        "queue_id":      queue_id,
        "parche":        parche,
 
        # Campeón y rol
        "campeon":       p.get("championName", ""),
        "campeon_id":    p.get("championId"),
        "rol":           p.get("teamPosition", "") or "FILL",
        "rol_individual":p.get("individualPosition", "") or "FILL",
 
        # Resultado y rendición
        "resultado":              "Victoria" if p.get("win") else "Derrota",
        "rendicion":              p.get("gameEndedInSurrender", False),
        "rendicion_temprana":     p.get("gameEndedInEarlySurrender", False),
        "equipo_rindio_temprano": p.get("teamEarlySurrendered", False),
 
        # Combate
        "kills":              k,
        "deaths":             d,
        "assists":            a,
        "kda":                kda,
        "primera_sangre":     p.get("firstBloodKill", False),
        "kills_solitarios":   int(ch.get("soloKills", 0)),
        "racha_maxima_kills": p.get("largestKillingSpree", 0),
        "multi_kill_maximo":  p.get("largestMultiKill", 0),
        "doble_kills":        p.get("doubleKills", 0),
        "triple_kills":       p.get("tripleKills", 0),
        "cuadra_kills":       p.get("quadraKills", 0),
        "penta_kills":        p.get("pentaKills", 0),
 
        # Daño
        "dano_total_campeon":     p.get("totalDamageDealtToChampions", 0),
        "dano_magico_campeon":    p.get("magicDamageDealtToChampions", 0),
        "dano_fisico_campeon":    p.get("physicalDamageDealtToChampions", 0),
        "dano_verdadero_campeon": p.get("trueDamageDealtToChampions", 0),
        "dano_total_recibido":    p.get("totalDamageTaken", 0),
        "dano_mitigado":          p.get("damageSelfMitigated", 0),
        "dano_a_objetivos":       p.get("damageDealtToObjectives", 0),
        "dano_a_torres":          p.get("damageDealtToTurrets", 0),
        "curacion_total":         p.get("totalHeal", 0),
        "curacion_a_aliados":     p.get("totalHealsOnTeammates", 0),
        "escudo_a_aliados":       p.get("totalDamageShieldedOnTeammates", 0),
        "porcentaje_dano_equipo": round(float(ch.get("teamDamagePercentage", 0)) * 100, 2),
 
        # Economía
        "oro_ganado":        p.get("goldEarned", 0),
        "oro_gastado":       p.get("goldSpent", 0),
        "cs_total":          cs_total,
        "cs_minions":        cs_minions,
        "cs_neutrales":      cs_neutrales,
        "cs_por_minuto":     cs_min,
        "objetos_comprados": p.get("itemsPurchased", 0),
        "consumibles_comprados": p.get("consumablesPurchased", 0),
        "item0": p.get("item0"), "item1": p.get("item1"),
        "item2": p.get("item2"), "item3": p.get("item3"),
        "item4": p.get("item4"), "item5": p.get("item5"),
        "item6": p.get("item6"),
 
        # Visión
        "vision_score":             p.get("visionScore", 0),
        "wards_colocados":          p.get("wardsPlaced", 0),
        "wards_eliminados":         p.get("wardsKilled", 0),
        "wards_control_comprados":  p.get("visionWardsBoughtInGame", 0),
        "wards_detector_colocados": p.get("detectorWardsPlaced", 0),
 
        # Objetivos de mapa
        "kills_dragon":    p.get("dragonKills", 0),
        "kills_baron":     p.get("baronKills", 0),
        "kills_inhibidor": p.get("inhibitorKills", 0),
        "kills_torre":     p.get("turretKills", 0),
        "objetivos_robados": p.get("objectivesStolen", 0),
 
        # Comportamiento
        "tiempo_muerto_seg":      p.get("totalTimeSpentDead", 0),
        "tiempo_vivo_max_seg":    p.get("longestTimeSpentLiving", 0),
        "hechizo1_lanzado":       p.get("spell1Casts", 0),
        "hechizo2_lanzado":       p.get("spell2Casts", 0),
        "hechizo3_lanzado":       p.get("spell3Casts", 0),
        "hechizo4_lanzado":       p.get("spell4Casts", 0),
        "summoner1_lanzado":      p.get("summoner1Casts", 0),
        "summoner2_lanzado":      p.get("summoner2Casts", 0),
        "cc_aplicado_seg":        p.get("totalTimeCCDealt", 0),
        "saves_a_aliados":        int(ch.get("saveAllyFromDeath", 0)),
        "apto_para_progresion":   p.get("eligibleForProgression", True),
        "takedowns_primeros_10min": int(ch.get("takedownsFirstXMinutes", 0)),
        "control_aplicado_a_otros": p.get("timeCCingOthers", 0),
        "intercepciones_habilidad": int(ch.get("dodgeSkillShotsSmallWindow", 0)),
    }
 
 
# ══════════════════════════════════════════════════════════════
#  SYNC DE UN USUARIO
# ══════════════════════════════════════════════════════════════
 
def sync_usuario(usuario):
    """
    Sincroniza las partidas de un usuario.
    Devuelve el número de partidas nuevas insertadas.
    """
    uid       = usuario["id"]
    email     = usuario["email"]
    game_name = usuario["riot_game_name"]
    tag_line  = usuario["riot_tag_line"]
    region_key= (usuario.get("region") or "EUW").upper()
 
    region, routing = REGION_MAP.get(region_key, ("euw1", "europe"))
 
    print(f"\n  👤 {game_name}#{tag_line} ({email})")
 
    sync_id = None
    try:
        # ── 1. Obtener PUUID si no lo tenemos ────────────────
        puuid = usuario.get("puuid")
        if not puuid:
            time.sleep(SLEEP_ENTRE_REQUESTS)
            account = get_account(game_name, tag_line, routing)
            if not account:
                print(f"     ❌ Cuenta no encontrada en Riot")
                return 0
            puuid = account["puuid"]
            upsert_puuid_en_usuario(uid, puuid)
            print(f"     🔑 PUUID obtenido")
 
        sync_id = log_sync(puuid, game_name)
 
        # ── 2. Jugador + Ranked ───────────────────────────────
        # Summoner v4 ya no acepta PUUIDs del nuevo formato (>50 chars)
        # Guardamos el jugador con los datos que ya tenemos del Account endpoint
        upsert_jugador(puuid, game_name, tag_line, region, None, None)
 
        time.sleep(SLEEP_ENTRE_REQUESTS)
        ranked = get_ranked(puuid, region)
        if ranked:
            upsert_ranked(puuid, ranked)
            try:
                snapshot_rank(puuid, ranked)
            except Exception as e_snap:
                print(f"     ⚠️  historial_rank no disponible: {e_snap}")
            for q in ranked:
                if q.get("queueType") == "RANKED_SOLO_5x5":
                    print(f"     🏆 {q['tier']} {q['rank']} — {q['leaguePoints']}LP")
 
        # ── 3. Calcular rango de fechas ───────────────────────
        # Primera ejecución: carga histórica de 6 meses (DIAS_ATRAS_DEFAULT=180)
        # Ejecuciones siguientes: desde la última partida en DB (incremental)
        ultima_partida = get_fecha_ultima_partida(puuid)
        if ultima_partida:
            # Incremental: empezamos un día antes por si hay partidas del mismo día
            fecha_inicio = ultima_partida - timedelta(days=1)
            print(f"     📅 Modo incremental desde {fecha_inicio}")
        else:
            # Carga histórica inicial: 6 meses
            fecha_inicio = date.today() - timedelta(days=DIAS_ATRAS_DEFAULT)
            print(f"     📅 Carga histórica: {DIAS_ATRAS_DEFAULT} días ({fecha_inicio} → hoy)")
 
        fecha_fin  = date.today()
        existentes = get_match_ids_en_db(puuid)
 
        # ── 4. Obtener IDs con paginación por ventanas ────────
        print(f"     🔄 Paginando ventanas de {DIAS_VENTANA_PAGINACION} días...")
        nuevos_ids = get_todos_match_ids(puuid, routing, fecha_inicio, fecha_fin, existentes)
 
        print(f"     📊 {len(nuevos_ids)} partidas nuevas encontradas")
 
        if not nuevos_ids:
            log_sync(puuid, game_name, estado="ok", partidas_nuevas=0, sync_id=sync_id)
            actualizar_sync_usuario(uid)
            return 0
 
        # ── 5. Descargar y parsear partidas nuevas ────────────
        partidas_nuevas = []
        errores = 0
 
        for i, match_id in enumerate(nuevos_ids, 1):
            time.sleep(SLEEP_ENTRE_REQUESTS)
            try:
                match = get_match(match_id, routing)
                if not match:
                    continue
 
                stats = extraer_stats(match, puuid)
                if stats:
                    partidas_nuevas.append(stats)
                    icono = "✅" if stats["resultado"] == "Victoria" else "❌"
                    rindio = " 🏳️" if stats["rendicion"] else ""
                    afk    = " 💤" if not stats["apto_para_progresion"] else ""
                    print(
                        f"     [{i:2}/{len(nuevos_ids)}] {icono}{rindio}{afk} "
                        f"{stats['campeon']:<14} {stats['modo']:<14} "
                        f"KDA:{stats['kda']} | {stats['duracion_min']}min | {stats['fecha']}"
                    )
            except Exception as e:
                errores += 1
                print(f"     [{i:2}/{len(nuevos_ids)}] ⚠️  Error en {match_id}: {e}")
 
        # ── 6. Insertar en DB ─────────────────────────────────
        insertadas = insertar_partidas(partidas_nuevas)
        estado = "ok" if errores == 0 else "parcial"
        log_sync(puuid, game_name, estado=estado, partidas_nuevas=insertadas, sync_id=sync_id)
        actualizar_sync_usuario(uid)
 
        horas_nuevas = round(sum(p["duracion_min"] for p in partidas_nuevas) / 60, 2)
        print(f"     💾 {insertadas} partidas LoL guardadas ({horas_nuevas}h de juego)")

        # ── 7. TFT sync ───────────────────────────────────────────
        try:
            sync_tft_usuario(usuario)
        except PermissionError as e_tft:
            print(f"     ℹ️  TFT desactivado: {e_tft}")
            print(f"     ℹ️  Activa el acceso TFT en developer.riotgames.com para sincronizar partidas TFT.")
        except Exception as e_tft:
            print(f"     ⚠️  Error en TFT sync: {e_tft}")

        return insertadas
 
    except Exception as e:
        print(f"     ❌ Error crítico: {e}")
        if sync_id:
            log_sync(None, game_name, estado="error", error=str(e), sync_id=sync_id)
        return 0


# ══════════════════════════════════════════════════════════════
#  TFT — EXTRACCIÓN
# ══════════════════════════════════════════════════════════════

TFT_QUEUE_NOMBRES = {
    1100: "Ranked TFT",
    1090: "Normal TFT",
    1130: "Hyper Roll",
    1160: "Double Up",
    1400: "TFT Especial",
}


def get_tft_match_ids(puuid, routing, fecha_inicio, fecha_fin, existentes=None):
    """IDs de partidas TFT paginando por ventanas de tiempo."""
    if existentes is None:
        existentes = set()
    todos_ids = []
    cursor    = fecha_inicio
    while cursor < fecha_fin:
        ventana_fin = min(cursor + timedelta(days=DIAS_VENTANA_PAGINACION), fecha_fin)
        ts_inicio_v = int(datetime.combine(cursor, datetime.min.time()).timestamp())
        ts_fin_v    = int(datetime.combine(ventana_fin, datetime.max.time()).timestamp())
        print(f"       📆 TFT {cursor} → {ventana_fin}", end="", flush=True)
        start = 0; ids_ventana = []
        while True:
            time.sleep(SLEEP_ENTRE_REQUESTS)
            url    = (f"https://{routing}.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids"
                      f"?start={start}&count={MAX_PARTIDAS_POR_PAGINA}"
                      f"&startTime={ts_inicio_v}&endTime={ts_fin_v}")
            pagina = api_get(url) or []
            nuevos = [m for m in pagina if m not in existentes and m not in ids_ventana]
            ids_ventana.extend(nuevos)
            if len(pagina) < MAX_PARTIDAS_POR_PAGINA:
                break
            start += MAX_PARTIDAS_POR_PAGINA
        print(f" → {len(ids_ventana)}")
        todos_ids.extend(ids_ventana)
        cursor = ventana_fin + timedelta(days=1)
    return todos_ids


def get_tft_match(match_id, routing):
    url = f"https://{routing}.api.riotgames.com/tft/match/v1/matches/{match_id}"
    return api_get(url)


def extraer_stats_tft(match, puuid):
    """Extrae los campos relevantes de una partida TFT."""
    info         = match.get("info", {})
    participants = info.get("participants", [])
    p = next((x for x in participants if x.get("puuid") == puuid), None)
    if not p:
        return None
    ts_inicio    = info.get("game_datetime", 0) / 1000
    duracion_seg = int(info.get("game_length", 0))
    duracion_min = round(duracion_seg / 60, 2)
    dt_inicio    = datetime.fromtimestamp(ts_inicio)
    placement    = int(p.get("placement", 8))
    top4         = placement <= 4
    queue_id     = info.get("queue_id", 0)
    return {
        "match_id":    match["metadata"]["match_id"],
        "puuid":       puuid,
        "fecha":       dt_inicio.strftime("%Y-%m-%d"),
        "hora_inicio": dt_inicio.strftime("%H:%M:%S"),
        "duracion_min":duracion_min,
        "duracion_seg":duracion_seg,
        "modo":        TFT_QUEUE_NOMBRES.get(queue_id, "TFT"),
        "queue_id":    queue_id,
        "parche":      info.get("game_version", "")[:10],
        "placement":   placement,
        "top4":        top4,
        "resultado":   "Top4" if top4 else "Bot4",
        "nivel_tft":   int(p.get("level", 0)),
    }


def insertar_partidas_tft(partidas):
    """Inserta partidas TFT en la tabla `partidas`."""
    if not partidas:
        return 0
    sql = """
    INSERT INTO partidas (
        match_id, puuid, fecha, hora_inicio, duracion_min, duracion_seg,
        modo, queue_id, parche, resultado, juego, placement, top4,
        campeon, kills, deaths, assists, kda, rendicion, apto_para_progresion
    ) VALUES %s ON CONFLICT (match_id) DO NOTHING
    """
    rows = [(
        p["match_id"], p["puuid"], p["fecha"], p["hora_inicio"],
        p["duracion_min"], p["duracion_seg"],
        p["modo"], p["queue_id"], p["parche"], p["resultado"],
        "tft", p["placement"], p["top4"],
        f"TFT Lvl {p['nivel_tft']}",
        0, 0, 0, 0.0, False, True,
    ) for p in partidas]
    with get_db() as c:
        execute_values(c.cursor(), sql, rows)
        c.commit()
    return len(rows)


def get_tft_ids_en_db(puuid):
    with get_db() as c:
        cur = c.cursor()
        cur.execute("SELECT match_id FROM partidas WHERE puuid=%s AND juego='tft'", (puuid,))
        return {r[0] for r in cur.fetchall()}


def get_tft_fecha_ultima(puuid):
    with get_db() as c:
        cur = c.cursor()
        cur.execute("SELECT MAX(fecha) FROM partidas WHERE puuid=%s AND juego='tft'", (puuid,))
        return cur.fetchone()[0]


def sync_tft_usuario(usuario):
    """Sincroniza partidas TFT de un usuario. Devuelve número de partidas nuevas."""
    puuid      = usuario.get("puuid")
    game_name  = usuario["riot_game_name"]
    region_key = (usuario.get("region") or "EUW").upper()
    _region, routing = REGION_MAP.get(region_key, ("euw1", "europe"))
    if not puuid:
        return 0

    print(f"     🎲 TFT sync...")
    ultima = get_tft_fecha_ultima(puuid)
    fecha_inicio = (ultima - timedelta(days=1)) if ultima else (date.today() - timedelta(days=DIAS_ATRAS_DEFAULT))
    existentes   = get_tft_ids_en_db(puuid)
    nuevos_ids   = get_tft_match_ids(puuid, routing, fecha_inicio, date.today(), existentes)
    if not nuevos_ids:
        return 0

    partidas_nuevas = []
    for i, match_id in enumerate(nuevos_ids, 1):
        time.sleep(SLEEP_ENTRE_REQUESTS)
        try:
            match = get_tft_match(match_id, routing)
            if not match:
                continue
            stats = extraer_stats_tft(match, puuid)
            if stats:
                partidas_nuevas.append(stats)
                icono = "🥇" if stats["placement"] == 1 else ("🏆" if stats["top4"] else "💀")
                print(f"     [{i:2}/{len(nuevos_ids)}] {icono} {stats['modo']:<14} "
                      f"#{stats['placement']} | {stats['duracion_min']}min | {stats['fecha']}")
        except Exception as e:
            print(f"     [{i:2}/{len(nuevos_ids)}] ⚠️  Error TFT {match_id}: {e}")

    insertadas = insertar_partidas_tft(partidas_nuevas)
    print(f"     💾 {insertadas} partidas TFT guardadas")
    return insertadas


# ══════════════════════════════════════════════════════════════
#  SYNC COMPLETO — TODOS LOS USUARIOS
# ══════════════════════════════════════════════════════════════

def sync_todos():
    """Sincroniza todos los usuarios activos de la app."""
    print("═" * 60)
    print("  🎮 LolHelper — Extractor")
    print(f"  Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("═" * 60)
 
    usuarios = get_usuarios_activos()
 
    if not usuarios:
        print("\n⚠️  No hay usuarios activos. Añádelos en db_setup.py")
        return
 
    print(f"\n👥 {len(usuarios)} usuario(s) activo(s)")
 
    total_partidas = 0
    for i, usuario in enumerate(usuarios, 1):
        print(f"\n[{i}/{len(usuarios)}]", end="")
        nuevas = sync_usuario(usuario)
        total_partidas += nuevas
        if i < len(usuarios):
            time.sleep(SLEEP_ENTRE_USUARIOS)
 
    print("\n" + "═" * 60)
    print(f"  ✅ Sync completado — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  📊 Total partidas nuevas: {total_partidas}")
    print("═" * 60 + "\n")
 
    return total_partidas
 
 
def sync_un_usuario(game_name, tag_line):
    """Sincroniza solo un usuario específico."""
    print("═" * 60)
    print(f"  🎮 LolHelper — Sync individual: {game_name}#{tag_line}")
    print("═" * 60)
 
    with get_db() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT id, email, riot_game_name, riot_tag_line, puuid, region, ultima_sincronizacion
            FROM usuarios_app
            WHERE LOWER(riot_game_name) = LOWER(%s) AND LOWER(riot_tag_line) = LOWER(%s)
              AND activo = TRUE
        """, (game_name, tag_line))
        row = cur.fetchone()
 
    if not row:
        print(f"\n❌ Usuario {game_name}#{tag_line} no encontrado en la DB.")
        print("   Asegúrate de haberlo añadido en db_setup.py")
        return
 
    cols   = ["id", "email", "riot_game_name", "riot_tag_line", "puuid", "region", "ultima_sincronizacion"]
    usuario = dict(zip(cols, row))
    sync_usuario(usuario)
 
 
# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════
 
if __name__ == "__main__":
    if "--usuario" in sys.argv:
        # python extractor.py --usuario zRamBoXx EUW
        idx = sys.argv.index("--usuario")
        try:
            gn = sys.argv[idx + 1]
            tl = sys.argv[idx + 2]
            sync_un_usuario(gn, tl)
        except IndexError:
            print("Uso: python extractor.py --usuario <GameName> <TagLine>")
    else:
        sync_todos()