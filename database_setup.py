"""
═══════════════════════════════════════════════════════════════
  MÓDULO 1 — BASE DE DATOS
  LolHelper · db_setup.py
═══════════════════════════════════════════════════════════════

  Crea todas las tablas necesarias para la aplicación.
  Es SEGURO de ejecutar múltiples veces: usa IF NOT EXISTS
  y ON CONFLICT, nunca borra datos existentes.

  CÓMO USAR:
    python db_setup.py              → crea tablas + verifica
    python db_setup.py --reset      → ⚠️  borra todo y recrea (solo desarrollo)
    python db_setup.py --status     → muestra el estado actual de la DB

  PREREQUISITO:
    CREATE DATABASE lol_tracker;   (solo una vez, en psql o pgAdmin)
═══════════════════════════════════════════════════════════════
"""

import sys
import psycopg2
from config import DB_CONFIG

# ══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN — edita el fichero .env en la raíz del proyecto
# ══════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════
#  CONEXIÓN
# ══════════════════════════════════════════════════════════════

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# ══════════════════════════════════════════════════════════════
#  DEFINICIÓN DE TABLAS
# ══════════════════════════════════════════════════════════════

TABLAS = {}

# ─────────────────────────────────────────────────────────────
# BLOQUE 1: USUARIOS DE LA APLICACIÓN
# ─────────────────────────────────────────────────────────────

TABLAS["usuarios_app"] = """
CREATE TABLE IF NOT EXISTS usuarios_app (
    id                          SERIAL PRIMARY KEY,
    email                       VARCHAR(254) UNIQUE NOT NULL,
    riot_game_name              VARCHAR(50) NOT NULL,
    riot_tag_line               VARCHAR(10) NOT NULL,
    puuid                       VARCHAR(100) UNIQUE,         -- obtenido de la API tras registro
    region                      VARCHAR(10) DEFAULT 'EUW',

    -- Estado en la app
    activo                      BOOLEAN DEFAULT TRUE,
    fecha_registro              TIMESTAMP DEFAULT NOW(),
    ultima_sincronizacion       TIMESTAMP,

    -- RGPD — obligatorio
    consentimiento_datos        BOOLEAN DEFAULT FALSE,       -- aceptó política de privacidad
    consentimiento_emails       BOOLEAN DEFAULT FALSE,       -- aceptó recibir alertas
    fecha_consentimiento        TIMESTAMP,
    ip_consentimiento           VARCHAR(45),                 -- para registro RGPD (IPv4/IPv6)

    -- Autenticación
    password_hash               VARCHAR(255),

    -- Baja / derecho al olvido
    fecha_baja                  TIMESTAMP,
    datos_anonimizados          BOOLEAN DEFAULT FALSE,       -- TRUE cuando se ejerce derecho al olvido

    -- Seguridad: se incrementa al cambiar contraseña para invalidar tokens anteriores
    token_version               INT NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios_app(email);

COMMENT ON TABLE usuarios_app IS 'Usuarios registrados en la aplicación LolHelper';
COMMENT ON COLUMN usuarios_app.consentimiento_datos IS 'RGPD: aceptación explícita de política de privacidad';
COMMENT ON COLUMN usuarios_app.consentimiento_emails IS 'RGPD: consentimiento específico para emails de alerta';
COMMENT ON COLUMN usuarios_app.datos_anonimizados IS 'TRUE cuando el usuario ha ejercido el derecho al olvido (RGPD Art. 17)';
"""

# ─────────────────────────────────────────────────────────────
# BLOQUE 2: OBJETIVOS PERSONALIZADOS
# ─────────────────────────────────────────────────────────────

TABLAS["objetivos"] = """
CREATE TABLE IF NOT EXISTS objetivos (
    id                          SERIAL PRIMARY KEY,
    usuario_id                  INT NOT NULL REFERENCES usuarios_app(id) ON DELETE CASCADE,

    -- Límites de tiempo
    limite_horas_dia            NUMERIC(4,2),                -- ej: 2.0 → máx 2h al día
    limite_horas_semana         NUMERIC(5,2),                -- ej: 10.0 → máx 10h a la semana
    dias_descanso_semana        INT DEFAULT 0,               -- días sin jugar por semana (objetivo)

    -- Alertas
    alerta_al_porcentaje        INT DEFAULT 100,             -- 50 = alerta al llegar al 50% del límite
    resumen_nocturno            BOOLEAN DEFAULT FALSE,       -- email diario a las 23:00
    hora_resumen                TIME DEFAULT '23:00:00',     -- hora del resumen nocturno

    -- Metadata
    activo_desde                TIMESTAMP DEFAULT NOW(),
    activo                      BOOLEAN DEFAULT TRUE,        -- puede tener un objetivo activo/inactivo

    CONSTRAINT un_objetivo_activo UNIQUE (usuario_id, activo)  -- solo un objetivo activo por usuario
);

COMMENT ON TABLE objetivos IS 'Objetivos de control de tiempo de juego por usuario';
COMMENT ON COLUMN objetivos.alerta_al_porcentaje IS '50 = alerta cuando lleva el 50% del tiempo consumido';
COMMENT ON COLUMN objetivos.resumen_nocturno IS 'Si TRUE, se envía un email cada noche con el resumen del día';
"""

# ─────────────────────────────────────────────────────────────
# BLOQUE 3: JUGADORES (puente con la API de Riot)
# ─────────────────────────────────────────────────────────────

TABLAS["jugadores"] = """
CREATE TABLE IF NOT EXISTS jugadores (
    puuid                       VARCHAR(100) PRIMARY KEY,
    game_name                   VARCHAR(50) NOT NULL,
    tag_line                    VARCHAR(10) NOT NULL,
    region                      VARCHAR(10) NOT NULL,
    nivel_invocador             INT,
    icono_id                    INT,
    ultima_sincronizacion       TIMESTAMP,
    fecha_registro              TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE jugadores IS 'Datos de la cuenta de LoL obtenidos de la API de Riot';
"""

# ─────────────────────────────────────────────────────────────
# BLOQUE 4: INFORMACIÓN RANKED
# ─────────────────────────────────────────────────────────────

TABLAS["ranked_info"] = """
CREATE TABLE IF NOT EXISTS ranked_info (
    id                          SERIAL PRIMARY KEY,
    puuid                       VARCHAR(100) NOT NULL REFERENCES jugadores(puuid) ON DELETE CASCADE,
    queue_type                  VARCHAR(30) NOT NULL,        -- RANKED_SOLO_5x5, RANKED_FLEX_SR, etc.
    tier                        VARCHAR(20),                 -- IRON, BRONZE, ... CHALLENGER
    division                    VARCHAR(5),                  -- I, II, III, IV
    lp                          INT DEFAULT 0,
    victorias                   INT DEFAULT 0,
    derrotas                    INT DEFAULT 0,
    en_serie_de_promos          BOOLEAN DEFAULT FALSE,
    hot_streak                  BOOLEAN DEFAULT FALSE,
    actualizado_en              TIMESTAMP DEFAULT NOW(),

    UNIQUE (puuid, queue_type)
);

COMMENT ON TABLE ranked_info IS 'Información de ranked actualizada en cada sincronización';
"""

# ─────────────────────────────────────────────────────────────
# BLOQUE 5: PARTIDAS — tabla principal ampliada
# ─────────────────────────────────────────────────────────────

TABLAS["partidas"] = """
CREATE TABLE IF NOT EXISTS partidas (
    -- Identificación
    match_id                    VARCHAR(30) PRIMARY KEY,
    puuid                       VARCHAR(100) NOT NULL REFERENCES jugadores(puuid) ON DELETE CASCADE,

    -- Tiempo (clave para calcular horas jugadas)
    fecha                       DATE NOT NULL,
    hora_inicio                 TIME NOT NULL,
    hora_fin                    TIME,                        -- gameEndTimestamp
    duracion_min                NUMERIC(6,2) NOT NULL,       -- gameDuration / 60
    duracion_seg                INT,                         -- gameDuration en segundos (raw)

    -- Contexto de la partida
    modo                        VARCHAR(30),                 -- Ranked Solo, ARAM, URF...
    queue_id                    INT,                         -- ID numérico de la cola
    parche                      VARCHAR(20),                 -- gameVersion ej: "14.8.1"

    -- Campeón y rol
    campeon                     VARCHAR(40),
    campeon_id                  INT,
    rol                         VARCHAR(20),                 -- SUPPORT, JUNGLE, etc.
    rol_individual              VARCHAR(20),                 -- individualPosition (lo que realmente jugó)

    -- Resultado
    resultado                   VARCHAR(10) NOT NULL,        -- 'Victoria' / 'Derrota'
    rendicion                   BOOLEAN DEFAULT FALSE,       -- gameEndedInSurrender
    rendicion_temprana          BOOLEAN DEFAULT FALSE,       -- gameEndedInEarlySurrender
    equipo_rindio_temprano      BOOLEAN DEFAULT FALSE,       -- teamEarlySurrendered

    -- ── COMBATE ──────────────────────────────────────────────
    kills                       INT DEFAULT 0,
    deaths                      INT DEFAULT 0,
    assists                     INT DEFAULT 0,
    kda                         NUMERIC(6,2),
    primera_sangre              BOOLEAN DEFAULT FALSE,       -- firstBloodKill
    kills_solitarios            INT DEFAULT 0,              -- challenges.soloKills
    racha_maxima_kills          INT DEFAULT 0,              -- largestKillingSpree
    multi_kill_maximo           INT DEFAULT 0,              -- largestMultiKill (2=doble, 3=triple...)
    doble_kills                 INT DEFAULT 0,
    triple_kills                INT DEFAULT 0,
    cuadra_kills                INT DEFAULT 0,
    penta_kills                 INT DEFAULT 0,

    -- ── DAÑO ─────────────────────────────────────────────────
    dano_total_campeon          INT DEFAULT 0,              -- totalDamageDealtToChampions
    dano_magico_campeon         INT DEFAULT 0,              -- magicDamageDealtToChampions
    dano_fisico_campeon         INT DEFAULT 0,              -- physicalDamageDealtToChampions
    dano_verdadero_campeon      INT DEFAULT 0,              -- trueDamageDealtToChampions
    dano_total_recibido         INT DEFAULT 0,              -- totalDamageTaken
    dano_mitigado               INT DEFAULT 0,              -- damageSelfMitigated
    dano_a_objetivos            INT DEFAULT 0,              -- damageDealtToObjectives
    dano_a_torres               INT DEFAULT 0,              -- damageDealtToTurrets
    curacion_total              INT DEFAULT 0,              -- totalHeal
    curacion_a_aliados          INT DEFAULT 0,              -- totalHealsOnTeammates
    escudo_a_aliados            INT DEFAULT 0,              -- totalDamageShieldedOnTeammates
    porcentaje_dano_equipo      NUMERIC(5,2),               -- challenges.teamDamagePercentage

    -- ── ECONOMÍA ─────────────────────────────────────────────
    oro_ganado                  INT DEFAULT 0,
    oro_gastado                 INT DEFAULT 0,
    cs_total                    INT DEFAULT 0,              -- minions + neutrales
    cs_minions                  INT DEFAULT 0,              -- totalMinionsKilled
    cs_neutrales                INT DEFAULT 0,              -- neutralMinionsKilled
    cs_por_minuto               NUMERIC(5,2),
    objetos_comprados           INT DEFAULT 0,              -- itemsPurchased
    consumibles_comprados       INT DEFAULT 0,              -- consumablesPurchased
    item0                       INT,                        -- ítems finales (IDs)
    item1                       INT,
    item2                       INT,
    item3                       INT,
    item4                       INT,
    item5                       INT,
    item6                       INT,                        -- trinket

    -- ── VISIÓN ───────────────────────────────────────────────
    vision_score                INT DEFAULT 0,
    wards_colocados             INT DEFAULT 0,              -- wardsPlaced
    wards_eliminados            INT DEFAULT 0,              -- wardsKilled
    wards_control_comprados     INT DEFAULT 0,              -- visionWardsBoughtInGame
    wards_detector_colocados    INT DEFAULT 0,              -- detectorWardsPlaced

    -- ── OBJETIVOS DE MAPA ────────────────────────────────────
    kills_dragon                INT DEFAULT 0,
    kills_baron                 INT DEFAULT 0,
    kills_inhibidor             INT DEFAULT 0,
    kills_torre                 INT DEFAULT 0,
    objetivos_robados           INT DEFAULT 0,              -- objectivesStolen

    -- ── COMPORTAMIENTO ───────────────────────────────────────
    -- Estos son los más valiosos para la app de concienciación
    tiempo_muerto_seg           INT DEFAULT 0,              -- totalTimeSpentDead
    tiempo_vivo_max_seg         INT DEFAULT 0,              -- longestTimeSpentLiving
    hechizo1_lanzado            INT DEFAULT 0,              -- spell1Casts (Q)
    hechizo2_lanzado            INT DEFAULT 0,              -- spell2Casts (W)
    hechizo3_lanzado            INT DEFAULT 0,              -- spell3Casts (E)
    hechizo4_lanzado            INT DEFAULT 0,              -- spell4Casts (R)
    summoner1_lanzado           INT DEFAULT 0,              -- summoner1Casts
    summoner2_lanzado           INT DEFAULT 0,              -- summoner2Casts
    cc_aplicado_seg             INT DEFAULT 0,              -- totalTimeCCDealt
    saves_a_aliados             INT DEFAULT 0,              -- challenges.saveAllyFromDeath
    apto_para_progresion        BOOLEAN DEFAULT TRUE,       -- eligibleForProgression (FALSE = AFK)
    takedowns_primeros_10min    INT DEFAULT 0,              -- challenges.takedownsFirstXMinutes

    -- ── SOPORTE / CONTROL ─────────────────────────────────────
    control_aplicado_a_otros    INT DEFAULT 0,              -- timeCCingOthers
    intercepciones_habilidad    INT DEFAULT 0,              -- challenges.dodgeSkillShotsSmallWindow

    -- Metadata
    insertado_en                TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE partidas IS 'Partidas extraídas de la API de Riot Match V5 — todos los campos relevantes';
COMMENT ON COLUMN partidas.duracion_min IS 'Duración en minutos — base para calcular horas jugadas';
COMMENT ON COLUMN partidas.rendicion IS 'TRUE si el equipo del jugador rindió voluntariamente';
COMMENT ON COLUMN partidas.rendicion_temprana IS 'TRUE si se rindió en los primeros minutos (señal de frustración)';
COMMENT ON COLUMN partidas.apto_para_progresion IS 'FALSE indica posible AFK — relevante para análisis de comportamiento';
COMMENT ON COLUMN partidas.tiempo_muerto_seg IS 'Segundos pasados muerto — util para detectar partidas frustrantes';
"""

# ─────────────────────────────────────────────────────────────
# BLOQUE 6: PROGRESO DIARIO
# ─────────────────────────────────────────────────────────────

TABLAS["progreso_diario"] = """
CREATE TABLE IF NOT EXISTS progreso_diario (
    id                          SERIAL PRIMARY KEY,
    usuario_id                  INT NOT NULL REFERENCES usuarios_app(id) ON DELETE CASCADE,
    fecha                       DATE NOT NULL,

    -- Tiempo
    horas_jugadas_dia           NUMERIC(5,2) DEFAULT 0,
    minutos_jugados_dia         INT DEFAULT 0,
    horas_jugadas_semana        NUMERIC(5,2) DEFAULT 0,

    -- Cumplimiento del objetivo
    limite_dia                  NUMERIC(4,2),               -- copia del objetivo ese día
    limite_semana               NUMERIC(5,2),
    objetivo_dia_cumplido       BOOLEAN,                    -- NULL si no tiene objetivo diario
    objetivo_semana_cumplido    BOOLEAN,
    porcentaje_consumido_dia    NUMERIC(5,1),               -- ej: 75.5 → ha consumido el 75.5% del límite

    -- Racha (para gamificación positiva)
    racha_dias_cumplidos        INT DEFAULT 0,              -- días consecutivos cumpliendo el objetivo
    racha_maxima_historica      INT DEFAULT 0,

    -- Detalle de sesión
    partidas_jugadas            INT DEFAULT 0,
    modos_jugados               TEXT,                       -- ej: "Ranked Solo, ARAM" (CSV)
    campeon_mas_jugado          VARCHAR(40),
    rendiciones                 INT DEFAULT 0,              -- veces que rindió ese día
    afk_detectados              INT DEFAULT 0,              -- partidas con apto_para_progresion=FALSE

    -- Control de alertas del día
    alerta_50_enviada           BOOLEAN DEFAULT FALSE,
    alerta_100_enviada          BOOLEAN DEFAULT FALSE,
    resumen_nocturno_enviado    BOOLEAN DEFAULT FALSE,

    calculado_en                TIMESTAMP DEFAULT NOW(),

    UNIQUE (usuario_id, fecha)
);

COMMENT ON TABLE progreso_diario IS 'Snapshot diario del progreso de cada usuario — base para alertas y dashboard';
COMMENT ON COLUMN progreso_diario.racha_dias_cumplidos IS 'Días consecutivos cumpliendo el objetivo — para motivación positiva';
COMMENT ON COLUMN progreso_diario.rendiciones IS 'Número de rendiciones ese día — indicador de estado emocional';
"""

# ─────────────────────────────────────────────────────────────
# BLOQUE 7: ALERTAS ENVIADAS
# ─────────────────────────────────────────────────────────────

TABLAS["alertas_enviadas"] = """
CREATE TABLE IF NOT EXISTS alertas_enviadas (
    id                          SERIAL PRIMARY KEY,
    usuario_id                  INT NOT NULL REFERENCES usuarios_app(id) ON DELETE CASCADE,

    tipo                        VARCHAR(30) NOT NULL,
    -- Valores posibles:
    --   'alerta_50'       → llegó al 50% del límite diario
    --   'alerta_100'      → superó el límite diario
    --   'resumen_noche'   → resumen nocturno programado
    --   'resumen_semana'  → resumen semanal (lunes)

    -- Datos del momento de la alerta
    horas_jugadas               NUMERIC(5,2),               -- horas jugadas en el período
    limite_configurado          NUMERIC(5,2),               -- límite en ese momento
    porcentaje_consumido        NUMERIC(5,1),
    partidas_del_dia            INT,

    -- Comportamiento detectado (para personalizar el mensaje)
    rendiciones_detectadas      INT DEFAULT 0,
    afk_detectados              INT DEFAULT 0,
    campeon_del_dia             VARCHAR(40),
    racha_actual                INT DEFAULT 0,

    -- Email
    email_destino               VARCHAR(254),
    asunto                      TEXT,
    enviado_correctamente       BOOLEAN DEFAULT FALSE,
    error_envio                 TEXT,                       -- mensaje de error si falló

    enviado_en                  TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE alertas_enviadas IS 'Registro histórico de todos los emails enviados — para auditoría y evitar duplicados';
"""

# ─────────────────────────────────────────────────────────────
# BLOQUE 8: SYNC LOG (extracción de API)
# ─────────────────────────────────────────────────────────────

TABLAS["historial_rank"] = """
CREATE TABLE IF NOT EXISTS historial_rank (
    id              SERIAL PRIMARY KEY,
    puuid           VARCHAR(100) NOT NULL REFERENCES jugadores(puuid) ON DELETE CASCADE,
    fecha           DATE NOT NULL DEFAULT CURRENT_DATE,
    queue_type      VARCHAR(30) DEFAULT 'RANKED_SOLO_5x5',
    tier            VARCHAR(20),
    division        VARCHAR(5),
    lp              INT DEFAULT 0,
    puntos_totales  INT DEFAULT 0,
    victorias       INT DEFAULT 0,
    derrotas        INT DEFAULT 0,
    registrado_en   TIMESTAMP DEFAULT NOW(),
    UNIQUE (puuid, fecha, queue_type)
);

COMMENT ON TABLE historial_rank IS 'Snapshot diario de LP/rank para tracking de progresión ranked';
COMMENT ON COLUMN historial_rank.puntos_totales IS 'LP absoluto: tier*400 + division*100 + lp (útil para graficar tendencia)';
"""

# ─────────────────────────────────────────────────────────────
# BLOQUE B2B: PROFESIONALES, RELACIONES Y NOTAS
# ─────────────────────────────────────────────────────────────

TABLAS["profesionales"] = """
CREATE TABLE IF NOT EXISTS profesionales (
    id                  SERIAL PRIMARY KEY,
    usuario_id          INT NOT NULL UNIQUE REFERENCES usuarios_app(id) ON DELETE CASCADE,

    -- Datos profesionales
    nombre              VARCHAR(100) NOT NULL,
    apellidos           VARCHAR(100) NOT NULL,
    numero_colegiado    VARCHAR(50),
    especialidad        VARCHAR(100),

    -- Token único para el enlace de invitación (p.ej. /invitacion/<link_token>)
    link_token          VARCHAR(64) UNIQUE NOT NULL,

    -- Estado
    verificado          BOOLEAN DEFAULT FALSE,
    activo              BOOLEAN DEFAULT TRUE,
    fecha_registro      TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE profesionales IS 'Perfil del profesional sanitario (psicólogo, terapeuta, etc.)';
COMMENT ON COLUMN profesionales.link_token IS 'Token único para el enlace de invitación que el profesional comparte con sus pacientes';
"""

TABLAS["invitaciones_pro"] = """
CREATE TABLE IF NOT EXISTS invitaciones_pro (
    id              SERIAL PRIMARY KEY,
    profesional_id  INT NOT NULL REFERENCES profesionales(id) ON DELETE CASCADE,
    token           VARCHAR(64) UNIQUE NOT NULL,
    email_paciente  VARCHAR(254),
    riot_game_name  VARCHAR(50),
    riot_tag_line   VARCHAR(10),
    paciente_id     INT REFERENCES usuarios_app(id),
    estado          VARCHAR(30) DEFAULT 'pendiente_registro',
    fecha_creacion  TIMESTAMP DEFAULT NOW(),
    fecha_aceptacion TIMESTAMP
);

COMMENT ON TABLE invitaciones_pro IS 'Invitaciones pendientes de registro enviadas por profesionales a pacientes';
"""

TABLAS["relaciones_pro_paciente"] = """
CREATE TABLE IF NOT EXISTS relaciones_pro_paciente (
    id                  SERIAL PRIMARY KEY,
    profesional_id      INT NOT NULL REFERENCES profesionales(id) ON DELETE CASCADE,
    paciente_id         INT NOT NULL REFERENCES usuarios_app(id) ON DELETE CASCADE,

    -- Embudo de tratamiento
    estado_tratamiento  VARCHAR(30) DEFAULT 'evaluacion',
    -- evaluacion → tratamiento_activo → seguimiento → alta

    fecha_inicio        TIMESTAMP DEFAULT NOW(),
    fecha_alta          TIMESTAMP,                      -- se rellena al dar de alta
    activo              BOOLEAN DEFAULT TRUE,

    -- Registro de consentimiento RGPD explícito del paciente
    consentimiento_fecha TIMESTAMP DEFAULT NOW(),

    UNIQUE (profesional_id, paciente_id)
);

COMMENT ON TABLE relaciones_pro_paciente IS 'Relación muchos-a-muchos entre profesional y paciente con estado de tratamiento';
"""

TABLAS["notas_profesional"] = """
CREATE TABLE IF NOT EXISTS notas_profesional (
    id              SERIAL PRIMARY KEY,
    relacion_id     INT NOT NULL REFERENCES relaciones_pro_paciente(id) ON DELETE CASCADE,
    contenido       TEXT NOT NULL,
    creada_en       TIMESTAMP DEFAULT NOW(),
    editada_en      TIMESTAMP
);

COMMENT ON TABLE notas_profesional IS 'Notas privadas del profesional sobre el paciente — no visibles para el paciente';
"""

TABLAS["sync_log"] = """
CREATE TABLE IF NOT EXISTS sync_log (
    id                          SERIAL PRIMARY KEY,
    puuid                       VARCHAR(100),
    game_name                   VARCHAR(50),
    inicio_sync                 TIMESTAMP DEFAULT NOW(),
    fin_sync                    TIMESTAMP,
    partidas_nuevas             INT DEFAULT 0,
    estado                      VARCHAR(20) DEFAULT 'running',
    -- 'running' → en proceso
    -- 'ok'      → completado sin errores
    -- 'error'   → falló
    -- 'parcial' → completó con algunos errores
    error_msg                   TEXT
);

COMMENT ON TABLE sync_log IS 'Log de cada extracción de datos de la API de Riot';
"""

# ─────────────────────────────────────────────────────────────
# ÍNDICES (rendimiento en consultas frecuentes)
# ─────────────────────────────────────────────────────────────

INDICES = """
-- Partidas: consultas por usuario y fecha (las más frecuentes)
CREATE INDEX IF NOT EXISTS idx_partidas_puuid        ON partidas(puuid);
CREATE INDEX IF NOT EXISTS idx_partidas_fecha        ON partidas(fecha);
CREATE INDEX IF NOT EXISTS idx_partidas_puuid_fecha  ON partidas(puuid, fecha);
CREATE INDEX IF NOT EXISTS idx_partidas_modo         ON partidas(modo);
CREATE INDEX IF NOT EXISTS idx_partidas_resultado    ON partidas(resultado);

-- Progreso diario: consultas por usuario
CREATE INDEX IF NOT EXISTS idx_progreso_usuario_fecha ON progreso_diario(usuario_id, fecha);

-- Alertas: buscar si ya se envió una alerta hoy
CREATE INDEX IF NOT EXISTS idx_alertas_usuario_tipo   ON alertas_enviadas(usuario_id, tipo, enviado_en);

-- Historial rank
CREATE INDEX IF NOT EXISTS idx_historial_rank_puuid   ON historial_rank(puuid, fecha);

-- Sync log
CREATE INDEX IF NOT EXISTS idx_sync_puuid             ON sync_log(puuid);

-- B2B: profesionales y relaciones
CREATE INDEX IF NOT EXISTS idx_pro_usuario            ON profesionales(usuario_id);
CREATE INDEX IF NOT EXISTS idx_pro_link_token         ON profesionales(link_token);
CREATE INDEX IF NOT EXISTS idx_rel_profesional        ON relaciones_pro_paciente(profesional_id);
CREATE INDEX IF NOT EXISTS idx_rel_paciente           ON relaciones_pro_paciente(paciente_id);
CREATE INDEX IF NOT EXISTS idx_notas_relacion         ON notas_profesional(relacion_id);
"""

# Migración incremental: añade columnas a usuarios_app si no existen aún
MIGRACIONES = """
-- TFT: columnas en partidas
ALTER TABLE partidas ADD COLUMN IF NOT EXISTS juego     VARCHAR(10) DEFAULT 'lol';
ALTER TABLE partidas ADD COLUMN IF NOT EXISTS placement INT;
ALTER TABLE partidas ADD COLUMN IF NOT EXISTS top4      BOOLEAN;
CREATE INDEX IF NOT EXISTS idx_partidas_juego ON partidas(puuid, juego, fecha);

-- TFT: límites separados en objetivos
ALTER TABLE objetivos ADD COLUMN IF NOT EXISTS limite_horas_dia_tft     NUMERIC(4,2) DEFAULT 1.5;
ALTER TABLE objetivos ADD COLUMN IF NOT EXISTS limite_horas_semana_tft  NUMERIC(5,2) DEFAULT 8.0;
ALTER TABLE objetivos ADD COLUMN IF NOT EXISTS alerta_al_porcentaje_tft INT DEFAULT 80;

ALTER TABLE usuarios_app      ADD COLUMN IF NOT EXISTS rol           VARCHAR(20)  DEFAULT 'jugador';
ALTER TABLE usuarios_app      ADD COLUMN IF NOT EXISTS es_paciente   BOOLEAN      DEFAULT FALSE;
ALTER TABLE usuarios_app      ADD COLUMN IF NOT EXISTS nombre_real   VARCHAR(100);
ALTER TABLE usuarios_app      ADD COLUMN IF NOT EXISTS apellidos_real VARCHAR(100);
ALTER TABLE notas_profesional ADD COLUMN IF NOT EXISTS categoria      VARCHAR(30)  DEFAULT 'observacion';
ALTER TABLE invitaciones_pro  ADD COLUMN IF NOT EXISTS nombre_paciente   VARCHAR(100);
ALTER TABLE invitaciones_pro  ADD COLUMN IF NOT EXISTS apellidos_paciente VARCHAR(100);
ALTER TABLE invitaciones_pro  DROP CONSTRAINT IF EXISTS invitaciones_pro_token_key;
DO $$ BEGIN
    ALTER TABLE invitaciones_pro ADD CONSTRAINT inv_pro_paciente_unique
        UNIQUE (profesional_id, email_paciente);
EXCEPTION WHEN duplicate_table OR duplicate_object THEN NULL;
END $$;
"""


# ══════════════════════════════════════════════════════════════
#  FUNCIONES PRINCIPALES
# ══════════════════════════════════════════════════════════════

def crear_tablas():
    """Crea todas las tablas e índices. Seguro de ejecutar múltiples veces."""
    print("\n📦 Creando tablas...")
    with get_connection() as conn:
        cur = conn.cursor()
        for nombre, ddl in TABLAS.items():
            try:
                cur.execute(ddl)
                print(f"   ✅ {nombre}")
            except Exception as e:
                print(f"   ❌ {nombre}: {e}")
                raise
        try:
            cur.execute(INDICES)
            print("   ✅ índices")
        except Exception as e:
            print(f"   ❌ índices: {e}")
            raise
        try:
            cur.execute(MIGRACIONES)
            print("   ✅ migraciones incrementales")
        except Exception as e:
            print(f"   ❌ migraciones: {e}")
            raise
        conn.commit()
    print("\n✅ Base de datos lista\n")


def verificar_estado():
    """Muestra el estado actual de la base de datos."""
    print("\n📊 Estado de la base de datos")
    print("─" * 50)
    with get_connection() as conn:
        cur = conn.cursor()
        tablas_esperadas = list(TABLAS.keys())
        for tabla in tablas_esperadas:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = %s
                )
            """, (tabla,))
            existe = cur.fetchone()[0]
            if existe:
                cur.execute(f"SELECT COUNT(*) FROM {tabla}")
                n = cur.fetchone()[0]
                cur.execute(f"""
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_name = %s AND table_schema = 'public'
                """, (tabla,))
                cols = cur.fetchone()[0]
                print(f"   ✅ {tabla:<25} {n:>6} filas   {cols:>3} columnas")
            else:
                print(f"   ❌ {tabla:<25} NO EXISTE")

    print("─" * 50)


def reset_base_de_datos():
    """⚠️  PELIGROSO: borra y recrea todo. Solo para desarrollo."""
    respuesta = input("\n⚠️  Esto borrará TODOS los datos. Escribe 'CONFIRMAR' para continuar: ")
    if respuesta != "CONFIRMAR":
        print("Cancelado.")
        return
    print("\n🗑️  Borrando tablas...")
    orden_borrado = [
        "alertas_enviadas", "progreso_diario", "sync_log",
        "partidas", "ranked_info", "objetivos",
        "jugadores", "usuarios_app"
    ]
    with get_connection() as conn:
        cur = conn.cursor()
        for tabla in orden_borrado:
            cur.execute(f"DROP TABLE IF EXISTS {tabla} CASCADE")
            print(f"   🗑️  {tabla}")
        conn.commit()
    print("\n🔄 Recreando...")
    crear_tablas()


def insertar_usuario_prueba():
    """
    Inserta usuarios de prueba para testear el sistema.
    Llama a esta función con los datos reales de tus usuarios de prueba.
    """
    usuarios_prueba = [
        ("rubenpb16@gmail.com", "zRamBoXx", "EUW"),
        ("d.manza.o@gmail.com", "fakeZLynKs", "EUW"),
        ("lewisbarrado@gmail.com", "CapiLewis", "Capi"),
        ("rubenpb16@gmail.com", "TheBlasman", "Blas9"),
    ]
    if not usuarios_prueba:
        print("\n💡 Para añadir usuarios de prueba, edita la lista 'usuarios_prueba' en esta función.")
        return

    print(f"\n👥 Insertando {len(usuarios_prueba)} usuarios de prueba...")
    with get_connection() as conn:
        cur = conn.cursor()
        for email, game_name, tag in usuarios_prueba:
            cur.execute("""
                INSERT INTO usuarios_app (
                    email, riot_game_name, riot_tag_line,
                    consentimiento_datos, consentimiento_emails,
                    fecha_consentimiento
                )
                VALUES (%s, %s, %s, TRUE, TRUE, NOW())
                ON CONFLICT (email) DO NOTHING
                RETURNING id
            """, (email, game_name, tag))
            resultado = cur.fetchone()
            if resultado:
                user_id = resultado[0]
                # Objetivo por defecto: 2h/día, 10h/semana, alerta al 80%
                cur.execute("""
                    INSERT INTO objetivos (
                        usuario_id, limite_horas_dia, limite_horas_semana,
                        alerta_al_porcentaje, resumen_nocturno
                    )
                    VALUES (%s, 2.0, 10.0, 80, FALSE)
                    ON CONFLICT DO NOTHING
                """, (user_id,))
                print(f"   ✅ {email} (id={user_id})")
            else:
                print(f"   ⚠️  {email} ya existe, omitido")
        conn.commit()


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 55)
    print("  🎮 LolHelper — Módulo 1: Base de Datos")
    print("═" * 55)

    if "--reset" in sys.argv:
        reset_base_de_datos()

    elif "--status" in sys.argv:
        verificar_estado()

    else:
        crear_tablas()
        verificar_estado()
        insertar_usuario_prueba()
        print("\n💡 Próximos pasos:")
        print("   1. Edita DB_CONFIG con tus credenciales de PostgreSQL")
        print("   2. Añade tus usuarios de prueba en insertar_usuario_prueba()")
        print("   3. Ejecuta: python db_setup.py")
        print("   4. Continúa con: python extractor.py  (Módulo 2)\n")