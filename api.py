"""
═══════════════════════════════════════════════════════════════
  API — FASTAPI
  LolHelper · api.py
═══════════════════════════════════════════════════════════════

  Servidor REST que expone todos los datos al frontend React.

  CÓMO ARRANCAR:
    uvicorn api:app --reload --port 8000

  DOCUMENTACIÓN INTERACTIVA (generada automáticamente):
    http://localhost:8000/docs

  ENDPOINTS:
    POST /auth/register     → registro de nuevo usuario
    POST /auth/login        → login, devuelve token JWT
    GET  /auth/me           → datos del usuario actual
    GET  /dashboard         → datos del dashboard principal
    GET  /historial         → partidas de los últimos N días
    GET  /objetivo          → objetivo activo del usuario
    PUT  /objetivo          → actualizar objetivo
    GET  /stats/campeon     → stats agrupadas por campeón
    GET  /stats/comportamiento → análisis de comportamiento
    DELETE /cuenta          → baja del usuario (RGPD)
═══════════════════════════════════════════════════════════════
"""
from fastapi import FastAPI, HTTPException, Depends, status, Response, Cookie, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from contextlib import asynccontextmanager
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime, date, timedelta
import time
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt as _bcrypt
from jose import jwt, JWTError
from config import JWT_SECRET, JWT_ALGO, JWT_MINUTOS, CORS_ORIGINS, SYNC_INTERVALO_MIN
from db import get_db_api, _get_pool
from lol_logger import get_logger

log = get_logger("api")


def _scheduler_loop():
    """
    Fase 1 — Carga histórica inicial (bloqueante):
        Extrae hasta SYNC_DIAS_INICIAL días de historial para cada usuario que
        aún no tiene partidas en la BD. Solo se ejecuta una vez al arrancar.

    Fase 2 — Ciclo periódico (cada SYNC_INTERVALO_MIN minutos):
        Sync incremental: solo descarga partidas nuevas desde la última fecha
        registrada. Procesa alertas al terminar cada ciclo.
    """
    import alertas as modulo_alertas
    import email_service as modulo_email
    from extractor import sync_todos

    INTERVALO = SYNC_INTERVALO_MIN * 60

    # ── FASE 1: carga histórica inicial ──────────────────────────
    log.info("Scheduler — FASE 1: iniciando carga histórica inicial…")
    try:
        sync_todos()
        log.info("Scheduler — FASE 1 completada. Iniciando ciclo periódico.")
    except Exception as e:
        log.error(f"Scheduler — error en carga inicial: {e}")

    try:
        modulo_alertas.procesar_alertas_todos(modulo_email)
    except Exception as e:
        log.error(f"Scheduler — error en alertas post-carga: {e}")

    # ── FASE 2: ciclo periódico ───────────────────────────────────
    log.info(f"Scheduler — FASE 2: ciclo periódico cada {SYNC_INTERVALO_MIN} min")
    while True:
        time.sleep(INTERVALO)
        try:
            sync_todos()
        except Exception as e:
            log.error(f"Scheduler — error en sync periódico: {e}")
        try:
            modulo_alertas.procesar_alertas_todos(modulo_email)
        except Exception as e:
            log.error(f"Scheduler — error en alertas: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Hilo daemon: muere automáticamente cuando el proceso principal para
    t = threading.Thread(target=_scheduler_loop, daemon=True)
    t.start()
    yield
# ══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════
 
# ══════════════════════════════════════════════════════════════
#  APP
# ══════════════════════════════════════════════════════════════
 
app = FastAPI(
    title="LolHelper API",
    description="API para el seguimiento de tiempo de juego en League of Legends",
    version="1.0.0",
    lifespan=lifespan,
)
 
# CORS — orígenes configurables via CORS_ORIGINS en .env / Railway
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
 
_SKIP_LOG = {"/health", "/favicon.ico", "/"}

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    if request.url.path not in _SKIP_LOG:
        ms = round((time.monotonic() - start) * 1000)
        log.info(f"{request.method} {request.url.path} -> {response.status_code} ({ms}ms)")
    return response


COOKIE_MAX_AGE = JWT_MINUTOS * 60  # segundos

def set_auth_cookie(response: Response, token: str):
    # Cross-origin (frontend y API en dominios distintos) requiere
    # SameSite=None + Secure=True para que el navegador envíe la cookie.
    # En local (HTTP) usamos SameSite=Lax porque Secure no está disponible.
    _https = len(CORS_ORIGINS) > 0 and CORS_ORIGINS[0].startswith("https")
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        max_age=COOKIE_MAX_AGE,
        samesite="none" if _https else "lax",
        secure=_https,
    )

# ══════════════════════════════════════════════════════════════
#  BASE DE DATOS
# ══════════════════════════════════════════════════════════════

get_db = get_db_api
 
 
# ══════════════════════════════════════════════════════════════
#  AUTENTICACIÓN — JWT
# ══════════════════════════════════════════════════════════════
 
def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
 
def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False
 
def crear_token(usuario_id: int, email: str, token_version: int, rol: str = "jugador") -> str:
    payload = {
        "sub":   str(usuario_id),
        "email": email,
        "ver":   token_version,
        "rol":   rol,
        "exp":   datetime.utcnow() + timedelta(minutes=JWT_MINUTOS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
 
def get_usuario_actual(
    token: Optional[str] = Cookie(default=None),
    db = Depends(get_db),
):
    credenciales_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado o sesión expirada",
    )
    if not token:
        raise credenciales_error
    try:
        payload    = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        usuario_id = int(payload.get("sub"))
        token_ver  = int(payload.get("ver", 1))
    except Exception:
        raise credenciales_error

    cur = db.cursor()
    cur.execute(
        "SELECT * FROM usuarios_app WHERE id = %s AND activo = TRUE",
        (usuario_id,)
    )
    usuario = cur.fetchone()
    if not usuario or usuario["token_version"] != token_ver:
        raise credenciales_error
    return dict(usuario)
 
 
def get_profesional_actual(
    token: Optional[str] = Cookie(default=None),
    db = Depends(get_db),
):
    """Dependencia que exige rol='profesional' en el JWT."""
    credenciales_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Acceso restringido a profesionales",
    )
    if not token:
        raise credenciales_error
    try:
        payload    = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        usuario_id = int(payload.get("sub"))
        token_ver  = int(payload.get("ver", 1))
        if payload.get("rol") != "profesional":
            raise credenciales_error
    except HTTPException:
        raise
    except Exception:
        raise credenciales_error

    cur = db.cursor()
    cur.execute(
        "SELECT * FROM usuarios_app WHERE id = %s AND activo = TRUE",
        (usuario_id,)
    )
    usuario = cur.fetchone()
    if not usuario or usuario["token_version"] != token_ver:
        raise credenciales_error

    cur.execute(
        "SELECT * FROM profesionales WHERE usuario_id = %s AND activo = TRUE",
        (usuario_id,)
    )
    profesional = cur.fetchone()
    if not profesional:
        raise credenciales_error

    return {**dict(usuario), "profesional": dict(profesional)}


# ══════════════════════════════════════════════════════════════
#  MODELOS PYDANTIC — validación de entrada y salida
# ══════════════════════════════════════════════════════════════
 
class RegistroRequest(BaseModel):
    email:               EmailStr
    password:            str
    riot_game_name:      str
    riot_tag_line:       str
    limite_horas_dia:    float = 2.0
    limite_horas_semana: float = 10.0
    alerta_porcentaje:   int   = 80
    consentimiento_datos:  bool = False
    consentimiento_emails: bool = False
 
    @field_validator("password")
    @classmethod
    def password_minimo(cls, v):
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v
 
    @field_validator("consentimiento_datos")
    @classmethod
    def debe_aceptar_datos(cls, v):
        if not v:
            raise ValueError("Debes aceptar la política de privacidad")
        return v
 
    @field_validator("alerta_porcentaje")
    @classmethod
    def porcentaje_valido(cls, v):
        if not (10 <= v <= 100):
            raise ValueError("El porcentaje debe estar entre 10 y 100")
        return v
 
 
class ObjetivoUpdate(BaseModel):
    limite_horas_dia:         Optional[float] = None
    limite_horas_semana:      Optional[float] = None
    alerta_porcentaje:        Optional[int]   = None
    resumen_nocturno:         Optional[bool]  = None
    hora_resumen:             Optional[str]   = None
    # TFT
    limite_horas_dia_tft:     Optional[float] = None
    limite_horas_semana_tft:  Optional[float] = None
    alerta_porcentaje_tft:    Optional[int]   = None
 
 
class CambioPasswordRequest(BaseModel):
    password_actual: str
    password_nueva:  str
 
    @field_validator("password_nueva")
    @classmethod
    def password_minimo(cls, v):
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v
 
 
# ── Waitlist ─────────────────────────────────────────────────

class WaitlistInput(BaseModel):
    email:               EmailStr
    riot_game_name:      str
    riot_tag_line:       str
    consentimiento_datos:  bool
    consentimiento_emails: bool = False

    @field_validator("riot_game_name")
    @classmethod
    def nombre_no_vacio(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("El nombre de invocador no puede estar vacío")
        return v

    @field_validator("riot_tag_line")
    @classmethod
    def tag_no_vacio(cls, v):
        v = v.strip().lstrip("#")
        if not v:
            raise ValueError("El TAG no puede estar vacío")
        return v


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS — WAITLIST (sin autenticación)
# ══════════════════════════════════════════════════════════════

@app.post("/waitlist", summary="Registro en la beta pública")
def waitlist_register(data: WaitlistInput, db = Depends(get_db)):
    if not data.consentimiento_datos:
        raise HTTPException(400, detail="El consentimiento de datos es obligatorio")

    cur = db.cursor()
    cur.execute(
        "SELECT id FROM usuarios_app WHERE email = %s",
        (data.email.lower().strip(),),
    )
    if cur.fetchone():
        raise HTTPException(
            409,
            detail="Este email ya está en nuestra lista. ¡Pronto recibirás noticias del lanzamiento!"
        )

    pwd_hash = hash_password("root1234")

    cur.execute("""
        INSERT INTO usuarios_app (
            email, riot_game_name, riot_tag_line,
            password_hash,
            consentimiento_datos, consentimiento_emails,
            fecha_consentimiento, activo
        ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), TRUE)
        RETURNING id
    """, (
        data.email.lower().strip(),
        data.riot_game_name.strip(),
        data.riot_tag_line.strip().lstrip("#"),
        pwd_hash,
        data.consentimiento_datos,
        data.consentimiento_emails,
    ))
    user_id = cur.fetchone()["id"]

    # Objetivo por defecto para que el extractor los procese automáticamente
    cur.execute("""
        INSERT INTO objetivos (
            usuario_id, limite_horas_dia, limite_horas_semana, alerta_al_porcentaje
        ) VALUES (%s, 2.0, 14.0, 80)
        ON CONFLICT DO NOTHING
    """, (user_id,))

    db.commit()
    log.info(f"Waitlist: {data.email} ({data.riot_game_name}#{data.riot_tag_line})")
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS — AUTENTICACIÓN
# ══════════════════════════════════════════════════════════════

@app.post("/auth/register", summary="Registro de nuevo usuario")
def register(req: RegistroRequest, db = Depends(get_db), response: Response = None):
    cur = db.cursor()
 
    # Comprobar si el email ya existe
    cur.execute("SELECT id FROM usuarios_app WHERE email = %s", (req.email,))
    if cur.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este email ya está registrado"
        )
 
    # Comprobar si el Riot ID ya está en uso
    cur.execute(
        "SELECT id FROM usuarios_app WHERE riot_game_name = %s AND riot_tag_line = %s",
        (req.riot_game_name, req.riot_tag_line)
    )
    if cur.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este Riot ID ya está registrado en la aplicación"
        )
 
    # Crear usuario
    password_hash = hash_password(req.password)
    cur.execute("""
        INSERT INTO usuarios_app (
            email, password_hash, riot_game_name, riot_tag_line, region,
            consentimiento_datos, consentimiento_emails, fecha_consentimiento,
            activo
        ) VALUES (%s, %s, %s, %s, 'EUW', %s, %s, NOW(), TRUE)
        RETURNING id
    """, (
        req.email, password_hash,
        req.riot_game_name, req.riot_tag_line,
        req.consentimiento_datos, req.consentimiento_emails,
    ))
    usuario_id = cur.fetchone()["id"]
 
    # Crear objetivo inicial
    cur.execute("""
        INSERT INTO objetivos (
            usuario_id, limite_horas_dia, limite_horas_semana,
            alerta_al_porcentaje, activo
        ) VALUES (%s, %s, %s, %s, TRUE)
    """, (
        usuario_id,
        req.limite_horas_dia,
        req.limite_horas_semana,
        req.alerta_porcentaje,
    ))
 
    # Vincular invitaciones pendientes de profesionales para este email
    email_lower = req.email.lower().strip()
    cur.execute("""
        SELECT id, profesional_id FROM invitaciones_pro
        WHERE email_paciente = %s AND estado = 'pendiente_registro'
    """, (email_lower,))
    invitaciones = cur.fetchall()
    if invitaciones:
        # Tomar nombre real de la primera invitación que lo tenga
        nombre_inv    = next((i["nombre_paciente"]    for i in invitaciones if i.get("nombre_paciente")),    None)
        apellidos_inv = next((i["apellidos_paciente"] for i in invitaciones if i.get("apellidos_paciente")), None)
        cur.execute(
            "UPDATE usuarios_app SET es_paciente = TRUE, nombre_real = COALESCE(%s, nombre_real), apellidos_real = COALESCE(%s, apellidos_real) WHERE id = %s",
            (nombre_inv, apellidos_inv, usuario_id)
        )
        for inv in invitaciones:
            cur.execute("""
                INSERT INTO relaciones_pro_paciente (profesional_id, paciente_id, estado_tratamiento)
                VALUES (%s, %s, 'evaluacion')
                ON CONFLICT (profesional_id, paciente_id) DO NOTHING
            """, (inv["profesional_id"], usuario_id))
            cur.execute(
                "UPDATE invitaciones_pro SET estado = 'completada', paciente_id = %s WHERE id = %s",
                (usuario_id, inv["id"])
            )

    db.commit()

    token = crear_token(usuario_id, req.email, 1)
    set_auth_cookie(response, token)
    return {
        "message":    "Cuenta creada correctamente",
        "usuario_id": usuario_id,
        "game_name":  req.riot_game_name,
        "tag_line":   req.riot_tag_line,
    }
 
 
@app.post("/auth/login", summary="Login")
def login(form: OAuth2PasswordRequestForm = Depends(), db = Depends(get_db), response: Response = None):
    cur = db.cursor()
    cur.execute(
        "SELECT * FROM usuarios_app WHERE email = %s AND activo = TRUE",
        (form.username,)   # OAuth2 usa 'username' aunque sea un email
    )
    usuario = cur.fetchone()
 
    if not usuario or not verify_password(form.password, usuario["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )
 
    rol   = usuario.get("rol") or "jugador"
    token = crear_token(usuario["id"], usuario["email"], usuario["token_version"], rol=rol)
    set_auth_cookie(response, token)
    return {
        "game_name": usuario["riot_game_name"],
        "tag_line":  usuario["riot_tag_line"],
        "rol":       rol,
    }
 
 
@app.get("/auth/me", summary="Datos del usuario autenticado")
def me(usuario = Depends(get_usuario_actual)):
    return {
        "id":            usuario["id"],
        "email":         usuario["email"],
        "riot_game_name":usuario["riot_game_name"],
        "riot_tag_line": usuario["riot_tag_line"],
        "fecha_registro":str(usuario["fecha_registro"]),
    }
 
 
@app.post("/auth/logout", summary="Cerrar sesión")
def logout(response: Response):
    response.delete_cookie("token")
    return {"message": "Sesión cerrada correctamente"}


@app.put("/auth/password", summary="Cambiar contraseña")
def cambiar_password(
    req:      CambioPasswordRequest,
    usuario   = Depends(get_usuario_actual),
    db        = Depends(get_db),
    response: Response = None,
):
    if not verify_password(req.password_actual, usuario["password_hash"]):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")

    cur = db.cursor()
    cur.execute(
        """UPDATE usuarios_app
           SET password_hash = %s, token_version = token_version + 1
           WHERE id = %s
           RETURNING token_version""",
        (hash_password(req.password_nueva), usuario["id"])
    )
    nueva_version = cur.fetchone()["token_version"]
    db.commit()

    nuevo_token = crear_token(usuario["id"], usuario["email"], nueva_version)
    set_auth_cookie(response, nuevo_token)
    return {"message": "Contraseña actualizada correctamente"}
 
 
# ══════════════════════════════════════════════════════════════
#  ENDPOINTS — DASHBOARD
# ══════════════════════════════════════════════════════════════
 
@app.get("/dashboard", summary="Datos del dashboard principal")
def dashboard(usuario = Depends(get_usuario_actual), db = Depends(get_db)):
    cur   = db.cursor()
    puuid = usuario.get("puuid")
    uid   = usuario["id"]
 
    if not puuid:
        return {
            "sincronizado": False,
            "mensaje": "Tu cuenta de Riot todavía no está sincronizada. "
                       "El primer sync se realizará en las próximas horas."
        }
 
    # ── Hoy ──────────────────────────────────────────────────
    cur.execute("""
        SELECT
            COALESCE(ROUND(SUM(duracion_min)::numeric / 60, 2), 0)   AS horas_hoy,
            COALESCE(COUNT(*), 0)                                      AS partidas_hoy,
            COALESCE(SUM(CASE WHEN rendicion AND resultado = 'Derrota'  THEN 1 ELSE 0 END), 0) AS rendiciones_hoy,
            COALESCE(SUM(CASE WHEN NOT apto_para_progresion THEN 1 ELSE 0 END), 0) AS afks_hoy,
            MODE() WITHIN GROUP (ORDER BY campeon)                     AS campeon_hoy
        FROM partidas
        WHERE puuid = %s AND fecha = CURRENT_DATE
    """, (puuid,))
    hoy = dict(cur.fetchone())
 
    # ── Esta semana ───────────────────────────────────────────
    lunes = date.today() - timedelta(days=date.today().weekday())
    cur.execute("""
        SELECT COALESCE(ROUND(SUM(duracion_min)::numeric / 60, 2), 0) AS horas_semana
        FROM partidas
        WHERE puuid = %s AND fecha >= %s AND fecha <= CURRENT_DATE
    """, (puuid, lunes))
    horas_semana = float(cur.fetchone()["horas_semana"])
 
    # ── Objetivo activo ───────────────────────────────────────
    cur.execute("""
        SELECT limite_horas_dia, limite_horas_semana, alerta_al_porcentaje
        FROM objetivos WHERE usuario_id = %s AND activo = TRUE
    """, (uid,))
    obj = dict(cur.fetchone() or {})
 
    limite_d = float(obj.get("limite_horas_dia") or 0)
    limite_s = float(obj.get("limite_horas_semana") or 0)
    horas_hoy = float(hoy["horas_hoy"])
 
    # ── Progreso por días esta semana ─────────────────────────
    cur.execute("""
        SELECT
            fecha,
            ROUND(SUM(duracion_min)::numeric / 60, 2) AS horas,
            COUNT(*) AS partidas
        FROM partidas
        WHERE puuid = %s AND fecha >= %s AND fecha <= CURRENT_DATE
        GROUP BY fecha ORDER BY fecha
    """, (puuid, lunes))
    semana = [dict(r) for r in cur.fetchall()]

    # ── Semana anterior (lunes-7 a domingo pasado) ────────────
    lunes_anterior   = lunes - timedelta(days=7)
    domingo_anterior = lunes - timedelta(days=1)
    cur.execute("""
        SELECT COALESCE(ROUND(SUM(duracion_min)::numeric / 60, 2), 0) AS horas_ant
        FROM partidas
        WHERE puuid = %s AND fecha >= %s AND fecha <= %s
    """, (puuid, lunes_anterior, domingo_anterior))
    horas_semana_anterior = float(cur.fetchone()["horas_ant"])
 
    # ── Racha ─────────────────────────────────────────────────
    cur.execute("""
        SELECT racha_dias_cumplidos, racha_maxima_historica
        FROM progreso_diario
        WHERE usuario_id = %s
        ORDER BY fecha DESC LIMIT 1
    """, (uid,))
    racha_row = cur.fetchone()
    racha     = int(racha_row["racha_dias_cumplidos"] if racha_row else 0)
    racha_max = int(racha_row["racha_maxima_historica"] if racha_row else 0)
 
    # ── Últimas 5 partidas ────────────────────────────────────
    cur.execute("""
        SELECT campeon, modo, resultado, kda, duracion_min,
               rendicion, apto_para_progresion, fecha, hora_inicio
        FROM partidas
        WHERE puuid = %s
        ORDER BY fecha DESC, hora_inicio DESC
        LIMIT 5
    """, (puuid,))
    ultimas = [dict(r) for r in cur.fetchall()]
 
    # ── Ranked info ───────────────────────────────────────────
    cur.execute("""
        SELECT tier, division, lp, victorias, derrotas
        FROM ranked_info
        WHERE puuid = %s AND queue_type = 'RANKED_SOLO_5x5'
    """, (puuid,))
    ranked = dict(cur.fetchone() or {})
 
    # ── Calcular porcentaje y estado ──────────────────────────
    pct_dia    = round(horas_hoy / limite_d * 100, 1) if limite_d > 0 else 0
    pct_semana = round(horas_semana / limite_s * 100, 1) if limite_s > 0 else 0
 
    return {
        "sincronizado":   True,
        "nombre":         usuario["riot_game_name"],
        "tag":            usuario["riot_tag_line"],
        "hoy": {
            "horas":        horas_hoy,
            "partidas":     int(hoy["partidas_hoy"]),
            "rendiciones":  int(hoy["rendiciones_hoy"]),
            "afks":         int(hoy["afks_hoy"]),
            "campeon":      hoy["campeon_hoy"] or "",
        },
        "semana": {
            "horas":        horas_semana,
            "porcentaje":   pct_semana,
            "dias":         semana,
            "anterior":     horas_semana_anterior,
        },
        "objetivo": {
            "limite_dia":     limite_d,
            "limite_semana":  limite_s,
            "porcentaje_dia": pct_dia,
            "estado_dia": (
                "ok"      if pct_dia < float(obj.get("alerta_al_porcentaje") or 80)
                else "warning" if pct_dia < 100
                else "danger"
            ),
        },
        "racha":        racha,
        "racha_maxima": racha_max,
        "ultimas_partidas": [
            {
                "campeon":    r["campeon"],
                "modo":       r["modo"],
                "resultado":  r["resultado"],
                "kda":        float(r["kda"] or 0),
                "duracion_min": float(r["duracion_min"]),
                "rendicion":          r["rendicion"],
                "rendicion_negativa": r["rendicion"] and r["resultado"] == "Derrota",
                "rendicion_positiva": r["rendicion"] and r["resultado"] == "Victoria",
                "afk":        not r["apto_para_progresion"],
                "fecha":      str(r["fecha"]),
            }
            for r in ultimas
        ],
        "ranked": ranked,
    }
 
 
# ══════════════════════════════════════════════════════════════
#  ENDPOINTS — CALENDARIO (mes y día)
# ══════════════════════════════════════════════════════════════

def _mes_data(puuid: str, uid: int, year: int, month: int, cur):
    """Resumen de actividad por día para un mes dado."""
    import calendar as _cal
    primer_dia = date(year, month, 1)
    ultimo_dia = date(year, month, _cal.monthrange(year, month)[1])

    cur.execute("""
        SELECT
            fecha,
            ROUND(SUM(duracion_min)::numeric / 60, 2) AS horas,
            COUNT(*) AS partidas,
            SUM(CASE WHEN rendicion AND resultado='Derrota' THEN 1 ELSE 0 END) AS rendiciones,
            SUM(CASE WHEN NOT apto_para_progresion THEN 1 ELSE 0 END)          AS afks
        FROM partidas
        WHERE puuid = %s AND fecha >= %s AND fecha <= %s
        GROUP BY fecha
    """, (puuid, primer_dia, ultimo_dia))
    dias_db = {str(r["fecha"]): dict(r) for r in cur.fetchall()}

    cur.execute(
        "SELECT limite_horas_dia FROM objetivos WHERE usuario_id = %s AND activo = TRUE",
        (uid,)
    )
    obj     = cur.fetchone()
    limite  = float(obj["limite_horas_dia"]) if obj else 0

    dias = []
    for d in range(1, ultimo_dia.day + 1):
        fecha = str(date(year, month, d))
        row   = dias_db.get(fecha)
        horas = float(row["horas"]) if row else 0
        pct   = round(horas / limite * 100, 1) if limite > 0 else 0
        estado = "vacio"
        if horas > 0:
            if   pct > 100: estado = "excedido"
            elif pct >= 75: estado = "warning"
            else:           estado = "ok"
        dias.append({
            "fecha":      fecha,
            "horas":      horas,
            "partidas":   int(row["partidas"]) if row else 0,
            "rendiciones":int(row["rendiciones"]) if row else 0,
            "afks":       int(row["afks"]) if row else 0,
            "porcentaje": pct,
            "estado":     estado,
        })

    return {"year": year, "month": month, "limite_dia": limite, "dias": dias}


def _dia_data(puuid: str, uid: int, fecha_str: str, cur):
    """Detalle de partidas de un día concreto."""
    try:
        fecha_obj = date.fromisoformat(fecha_str)
    except ValueError:
        raise HTTPException(400, detail="Formato de fecha inválido (YYYY-MM-DD)")

    cur.execute("""
        SELECT campeon, modo, resultado, kda, duracion_min,
               hora_inicio, rendicion, apto_para_progresion
        FROM partidas
        WHERE puuid = %s AND fecha = %s
        ORDER BY hora_inicio ASC
    """, (puuid, fecha_obj))
    partidas = [dict(r) for r in cur.fetchall()]

    horas = sum(float(p["duracion_min"]) for p in partidas) / 60
    cur.execute(
        "SELECT limite_horas_dia FROM objetivos WHERE usuario_id = %s AND activo = TRUE",
        (uid,)
    )
    obj    = cur.fetchone()
    limite = float(obj["limite_horas_dia"]) if obj else 0
    pct    = round(horas / limite * 100, 1) if limite > 0 else 0

    return {
        "fecha":      fecha_str,
        "horas":      round(horas, 2),
        "partidas":   len(partidas),
        "limite":     limite,
        "porcentaje": pct,
        "matches": [
            {
                "campeon":            p["campeon"],
                "modo":               p["modo"],
                "resultado":          p["resultado"],
                "kda":                float(p["kda"] or 0),
                "duracion_min":       float(p["duracion_min"]),
                "hora":               str(p["hora_inicio"])[:5],
                "rendicion_negativa": p["rendicion"] and p["resultado"] == "Derrota",
                "rendicion_positiva": p["rendicion"] and p["resultado"] == "Victoria",
                "afk":                not p["apto_para_progresion"],
            }
            for p in partidas
        ],
    }


@app.get("/dashboard/mes", summary="Resumen de actividad mensual para el calendario")
def dashboard_mes(
    year:    int = None,
    month:   int = None,
    usuario  = Depends(get_usuario_actual),
    db       = Depends(get_db),
):
    hoy = date.today()
    y   = year  or hoy.year
    m   = month or hoy.month
    puuid = usuario.get("puuid")
    if not puuid:
        return {"year": y, "month": m, "limite_dia": 0, "dias": []}
    return _mes_data(puuid, usuario["id"], y, m, db.cursor())


@app.get("/dashboard/dia", summary="Detalle de partidas de un día concreto")
def dashboard_dia(
    fecha:   str,
    usuario  = Depends(get_usuario_actual),
    db       = Depends(get_db),
):
    puuid = usuario.get("puuid")
    if not puuid:
        return {"fecha": fecha, "horas": 0, "partidas": 0, "limite": 0, "porcentaje": 0, "matches": []}
    return _dia_data(puuid, usuario["id"], fecha, db.cursor())


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS — HISTORIAL
# ══════════════════════════════════════════════════════════════
 
@app.get("/historial", summary="Historial de partidas")
def historial(
    dias:         int          = 30,
    limit:        int          = 50,
    offset:       int          = 0,
    fecha_inicio: Optional[str] = None,
    fecha_fin:    Optional[str] = None,
    usuario = Depends(get_usuario_actual),
    db      = Depends(get_db),
):
    # Validar el rango de fechas antes de cualquier otra comprobación
    if fecha_inicio and fecha_fin:
        try:
            f_ini = date.fromisoformat(fecha_inicio)
            f_fin = date.fromisoformat(fecha_fin)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido. Usa YYYY-MM-DD")
        if f_ini > f_fin:
            raise HTTPException(status_code=400, detail="fecha_inicio no puede ser posterior a fecha_fin")
    else:
        f_ini = date.today() - timedelta(days=dias)
        f_fin = date.today()

    puuid = usuario.get("puuid")
    if not puuid:
        return {
            "partidas": [], "total": 0, "limit": limit, "offset": offset,
            "periodo_dias": dias, "resumen": {}, "dias_excedidos": [], "por_campeon": [],
        }

    cur   = db.cursor()
    rango = (puuid, f_ini, f_fin)

    # Total de partidas en el período (para la paginación)
    cur.execute(
        "SELECT COUNT(*) FROM partidas WHERE puuid = %s AND fecha >= %s AND fecha <= %s",
        rango
    )
    total_partidas_periodo = cur.fetchone()["count"]

    # Partidas paginadas
    cur.execute("""
        SELECT
            match_id, fecha, hora_inicio, campeon, modo, rol,
            resultado, kills, deaths, assists, kda,
            duracion_min, cs_por_minuto, dano_total_campeon,
            vision_score, oro_ganado,
            rendicion, rendicion_temprana, apto_para_progresion,
            tiempo_muerto_seg, parche
        FROM partidas
        WHERE puuid = %s AND fecha >= %s AND fecha <= %s
        ORDER BY fecha DESC, hora_inicio DESC
        LIMIT %s OFFSET %s
    """, (*rango, limit, offset))
    partidas = [dict(r) for r in cur.fetchall()]
 
    # Resumen del período
    cur.execute("""
        SELECT
            COUNT(*)                                                    AS total_partidas,
            ROUND(SUM(duracion_min)::numeric / 60, 2)                  AS total_horas,
            ROUND(AVG(kda)::numeric, 2)                                AS kda_avg,
            ROUND(AVG(cs_por_minuto)::numeric, 2)                      AS cs_avg,
            ROUND(AVG(dano_total_campeon)::numeric)                    AS dano_avg,
            SUM(CASE WHEN resultado = 'Victoria' THEN 1 ELSE 0 END)                          AS victorias,
            SUM(CASE WHEN rendicion AND resultado = 'Derrota'  THEN 1 ELSE 0 END)           AS rendiciones,
            SUM(CASE WHEN rendicion AND resultado = 'Victoria' THEN 1 ELSE 0 END)           AS rendiciones_pos,
            SUM(CASE WHEN NOT apto_para_progresion THEN 1 ELSE 0 END)                       AS afks,
            COUNT(DISTINCT fecha)                                                             AS dias_jugados
        FROM partidas
        WHERE puuid = %s AND fecha >= %s AND fecha <= %s
    """, rango)
    resumen = dict(cur.fetchone())
 
    # Días que superaron el límite
    cur.execute(
        "SELECT o.limite_horas_dia FROM objetivos o WHERE o.usuario_id = %s AND o.activo = TRUE",
        (usuario["id"],)
    )
    obj_row  = cur.fetchone()
    limite_d = float(obj_row["limite_horas_dia"]) if obj_row else 0
 
    dias_excedidos = []
    if limite_d > 0:
        cur.execute("""
            SELECT
                fecha,
                ROUND(SUM(duracion_min)::numeric / 60, 2) AS horas,
                COUNT(*) AS partidas,
                SUM(CASE WHEN rendicion AND resultado = 'Derrota' THEN 1 ELSE 0 END) AS rendiciones,
                SUM(CASE WHEN NOT apto_para_progresion THEN 1 ELSE 0 END) AS afks,
                MODE() WITHIN GROUP (ORDER BY campeon) AS campeon
            FROM partidas
            WHERE puuid = %s AND fecha >= %s AND fecha <= %s
            GROUP BY fecha
            HAVING SUM(duracion_min) / 60.0 > %s
            ORDER BY fecha DESC
        """, (*rango, limite_d))
        dias_excedidos = [dict(r) for r in cur.fetchall()]
 
    # Stats por campeón
    cur.execute("""
        SELECT
            campeon,
            COUNT(*)                                                  AS partidas,
            SUM(CASE WHEN resultado = 'Victoria' THEN 1 ELSE 0 END)  AS victorias,
            ROUND(AVG(kda)::numeric, 2)                               AS kda_avg,
            ROUND(SUM(duracion_min)::numeric / 60, 2)                 AS horas
        FROM partidas
        WHERE puuid = %s AND fecha >= %s AND fecha <= %s
        GROUP BY campeon
        ORDER BY partidas DESC
        LIMIT 8
    """, rango)
    por_campeon = [dict(r) for r in cur.fetchall()]
 
    return {
        "periodo_dias":   dias,
        "total":          total_partidas_periodo,
        "limit":          limit,
        "offset":         offset,
        "resumen":        resumen,
        "dias_excedidos": dias_excedidos,
        "por_campeon":    por_campeon,
        "partidas":       [
            {
                "match_id":    r["match_id"],
                "fecha":       str(r["fecha"]),
                "hora":        str(r["hora_inicio"])[:5],
                "campeon":     r["campeon"],
                "modo":        r["modo"],
                "rol":         r["rol"],
                "resultado":   r["resultado"],
                "kills":       r["kills"],
                "deaths":      r["deaths"],
                "assists":     r["assists"],
                "kda":         float(r["kda"] or 0),
                "duracion_min":float(r["duracion_min"]),
                "cs_min":      float(r["cs_por_minuto"] or 0),
                "dano":        r["dano_total_campeon"],
                "vision":      r["vision_score"],
                "rendicion":          r["rendicion"],
                "rendicion_negativa": r["rendicion"] and r["resultado"] == "Derrota",
                "rendicion_positiva": r["rendicion"] and r["resultado"] == "Victoria",
                "afk":         not r["apto_para_progresion"],
                "tiempo_muerto_seg": r["tiempo_muerto_seg"],
                "parche":      r["parche"],
            }
            for r in partidas
        ],
    }
 
 
# ══════════════════════════════════════════════════════════════
#  ENDPOINTS — TFT
# ══════════════════════════════════════════════════════════════

@app.get("/tft/dashboard", summary="Dashboard TFT del usuario")
def tft_dashboard(usuario = Depends(get_usuario_actual), db = Depends(get_db)):
    puuid = usuario.get("puuid")
    uid   = usuario["id"]
    if not puuid:
        return {"sincronizado": False}

    cur   = db.cursor()
    lunes = date.today() - timedelta(days=date.today().weekday())

    cur.execute("""
        SELECT
            COALESCE(ROUND(SUM(duracion_min)::numeric/60,2),0)  AS horas_hoy,
            COALESCE(COUNT(*),0)                                 AS partidas_hoy,
            COALESCE(ROUND(AVG(placement)::numeric,1),0)         AS avg_placement_hoy
        FROM partidas
        WHERE puuid=%s AND fecha=CURRENT_DATE AND juego='tft'
    """, (puuid,))
    hoy = dict(cur.fetchone())

    cur.execute("""
        SELECT COALESCE(ROUND(SUM(duracion_min)::numeric/60,2),0) AS horas_semana
        FROM partidas
        WHERE puuid=%s AND fecha>=%s AND fecha<=CURRENT_DATE AND juego='tft'
    """, (puuid, lunes))
    horas_semana = float(cur.fetchone()["horas_semana"])

    cur.execute("""
        SELECT
            limite_horas_dia_tft    AS limite_dia,
            limite_horas_semana_tft AS limite_semana,
            alerta_al_porcentaje_tft AS alerta_pct
        FROM objetivos WHERE usuario_id=%s AND activo=TRUE
    """, (uid,))
    obj      = dict(cur.fetchone() or {})
    limite_d = float(obj.get("limite_dia") or 1.5)
    limite_s = float(obj.get("limite_semana") or 8.0)
    horas_hoy= float(hoy["horas_hoy"])
    pct_dia  = round(horas_hoy / limite_d * 100, 1) if limite_d else 0

    # Últimas 10 partidas TFT
    cur.execute("""
        SELECT campeon, modo, resultado, placement, top4, kda, duracion_min, fecha, hora_inicio
        FROM partidas WHERE puuid=%s AND juego='tft'
        ORDER BY fecha DESC, hora_inicio DESC LIMIT 10
    """, (puuid,))
    ultimas = [dict(r) for r in cur.fetchall()]

    # Avg placement últimas 20
    cur.execute("""
        SELECT
            COALESCE(ROUND(AVG(placement)::numeric,2),0)                   AS avg_placement,
            COALESCE(ROUND(SUM(CASE WHEN top4 THEN 1 ELSE 0 END)::numeric
                / NULLIF(COUNT(*),0)*100,1),0)                             AS top4_rate,
            COUNT(*)                                                        AS total
        FROM partidas WHERE puuid=%s AND juego='tft'
        ORDER BY fecha DESC LIMIT 20
    """, (puuid,))  # NOTE: subquery needed — simplify with window
    # Use simpler subquery approach
    cur.execute("""
        SELECT
            COALESCE(ROUND(AVG(placement)::numeric,2),0) AS avg_placement,
            COALESCE(ROUND(SUM(CASE WHEN top4 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)*100,1),0) AS top4_rate,
            COUNT(*) AS total
        FROM (SELECT placement, top4 FROM partidas WHERE puuid=%s AND juego='tft'
              ORDER BY fecha DESC, hora_inicio DESC LIMIT 20) sub
    """, (puuid,))
    perf = dict(cur.fetchone())

    # Ranked TFT
    cur.execute("""
        SELECT tier, division, lp, victorias, derrotas
        FROM ranked_info WHERE puuid=%s AND queue_type='RANKED_TFT'
    """, (puuid,))
    ranked = dict(cur.fetchone() or {})

    return {
        "sincronizado": True,
        "hoy": {
            "horas":    horas_hoy,
            "partidas": int(hoy["partidas_hoy"]),
            "avg_placement": float(hoy["avg_placement_hoy"]),
        },
        "semana": {
            "horas":      horas_semana,
            "porcentaje": round(horas_semana / limite_s * 100, 1) if limite_s else 0,
        },
        "objetivo": {
            "limite_dia":     limite_d,
            "limite_semana":  limite_s,
            "porcentaje_dia": pct_dia,
        },
        "rendimiento": {
            "avg_placement": float(perf["avg_placement"]),
            "top4_rate":     float(perf["top4_rate"]),
            "total_partidas":int(perf["total"]),
        },
        "ranked": ranked,
        "ultimas_partidas": [
            {
                "modo":       r["modo"],
                "resultado":  r["resultado"],
                "placement":  r["placement"],
                "top4":       r["top4"],
                "duracion_min": float(r["duracion_min"]),
                "fecha":      str(r["fecha"]),
                "hora":       str(r["hora_inicio"])[:5],
            }
            for r in ultimas
        ],
    }


@app.get("/tft/historial", summary="Historial de partidas TFT")
def tft_historial(
    dias:         int          = 30,
    limit:        int          = 50,
    offset:       int          = 0,
    fecha_inicio: Optional[str] = None,
    fecha_fin:    Optional[str] = None,
    usuario = Depends(get_usuario_actual),
    db      = Depends(get_db),
):
    if fecha_inicio and fecha_fin:
        try:
            f_ini = date.fromisoformat(fecha_inicio)
            f_fin = date.fromisoformat(fecha_fin)
        except ValueError:
            raise HTTPException(400, detail="Formato de fecha inválido (YYYY-MM-DD)")
    else:
        f_ini = date.today() - timedelta(days=dias)
        f_fin = date.today()

    puuid = usuario.get("puuid")
    if not puuid:
        return {"partidas": [], "total": 0, "resumen": {}}

    cur   = db.cursor()
    rango = (puuid, f_ini, f_fin)

    cur.execute("SELECT COUNT(*) FROM partidas WHERE puuid=%s AND fecha>=%s AND fecha<=%s AND juego='tft'", rango)
    total = cur.fetchone()["count"]

    cur.execute("""
        SELECT modo, resultado, placement, top4, duracion_min, fecha, hora_inicio, parche
        FROM partidas
        WHERE puuid=%s AND fecha>=%s AND fecha<=%s AND juego='tft'
        ORDER BY fecha DESC, hora_inicio DESC
        LIMIT %s OFFSET %s
    """, (*rango, limit, offset))
    partidas = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT
            COUNT(*)                                                                          AS total,
            COALESCE(ROUND(SUM(duracion_min)::numeric/60,2),0)                               AS horas_total,
            COALESCE(ROUND(AVG(placement)::numeric,2),0)                                     AS avg_placement,
            COALESCE(ROUND(SUM(CASE WHEN top4 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)*100,1),0) AS top4_rate,
            SUM(CASE WHEN placement=1 THEN 1 ELSE 0 END)                                     AS primeros
        FROM partidas WHERE puuid=%s AND fecha>=%s AND fecha<=%s AND juego='tft'
    """, rango)
    resumen = dict(cur.fetchone())

    return {
        "total":   total,
        "limit":   limit,
        "offset":  offset,
        "resumen": {
            "total_partidas": int(resumen["total"] or 0),
            "horas_total":    float(resumen["horas_total"] or 0),
            "avg_placement":  float(resumen["avg_placement"] or 0),
            "top4_rate":      float(resumen["top4_rate"] or 0),
            "primeros":       int(resumen["primeros"] or 0),
        },
        "partidas": [
            {
                "modo":        r["modo"],
                "resultado":   r["resultado"],
                "placement":   r["placement"],
                "top4":        r["top4"],
                "duracion_min":float(r["duracion_min"]),
                "fecha":       str(r["fecha"]),
                "hora":        str(r["hora_inicio"])[:5],
                "parche":      r["parche"],
            }
            for r in partidas
        ],
    }


@app.get("/tft/stats/analisis", summary="Análisis TFT: patrones de comportamiento y rendimiento")
def tft_analisis(
    dias:         int          = 30,
    fecha_inicio: Optional[str] = None,
    fecha_fin_p:  Optional[str] = None,
    usuario = Depends(get_usuario_actual),
    db      = Depends(get_db),
):
    puuid = usuario.get("puuid")
    if not puuid:
        return {}
    cur = db.cursor()

    if fecha_inicio and fecha_fin_p:
        try:
            f_ini = date.fromisoformat(fecha_inicio)
            f_fin = date.fromisoformat(fecha_fin_p)
        except ValueError:
            raise HTTPException(400, "Formato de fecha inválido")
    else:
        f_ini = date.today() - timedelta(days=dias)
        f_fin = date.today()

    params = {"puuid": puuid, "f_ini": f_ini, "f_fin": f_fin}

    # Estadísticas globales
    cur.execute("""
        SELECT
            COUNT(*)                                                                          AS total,
            COALESCE(ROUND(AVG(placement)::numeric,2),0)                                     AS avg_placement,
            COALESCE(ROUND(SUM(CASE WHEN top4 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)*100,1),0) AS top4_rate,
            COALESCE(ROUND(SUM(CASE WHEN placement=1 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)*100,1),0) AS first_rate,
            COALESCE(ROUND(SUM(duracion_min)::numeric/60,2),0)                               AS horas_total,
            COUNT(DISTINCT fecha)                                                             AS dias_jugados,
            SUM(CASE WHEN EXTRACT(HOUR FROM hora_inicio)>=23 OR EXTRACT(HOUR FROM hora_inicio)<6
                     THEN 1 ELSE 0 END)                                                       AS partidas_nocturnas
        FROM partidas
        WHERE puuid=%(puuid)s AND fecha>=%(f_ini)s AND fecha<=%(f_fin)s AND juego='tft'
    """, params)
    stats = dict(cur.fetchone())

    # Rendimiento por modo
    cur.execute("""
        SELECT modo, COUNT(*) AS partidas,
               ROUND(AVG(placement)::numeric,2) AS avg_placement,
               ROUND(SUM(CASE WHEN top4 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)*100,0) AS top4_rate
        FROM partidas
        WHERE puuid=%(puuid)s AND fecha>=%(f_ini)s AND fecha<=%(f_fin)s AND juego='tft'
        GROUP BY modo ORDER BY partidas DESC
    """, params)
    por_modo = [dict(r) for r in cur.fetchall()]

    # Rendimiento por franja horaria
    cur.execute("""
        SELECT EXTRACT(HOUR FROM hora_inicio)::int AS hora,
               COUNT(*) AS total,
               ROUND(AVG(placement)::numeric,2) AS avg_placement,
               ROUND(SUM(CASE WHEN top4 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)*100,0) AS top4_rate
        FROM partidas
        WHERE puuid=%(puuid)s AND fecha>=%(f_ini)s AND fecha<=%(f_fin)s AND juego='tft'
        GROUP BY hora ORDER BY hora
    """, params)
    por_hora = [dict(r) for r in cur.fetchall()]

    # Últimas 20 partidas para tendencia de placement
    cur.execute("""
        SELECT fecha, placement, top4, modo
        FROM partidas
        WHERE puuid=%(puuid)s AND fecha>=%(f_ini)s AND fecha<=%(f_fin)s AND juego='tft'
        ORDER BY fecha DESC, hora_inicio DESC LIMIT 20
    """, params)
    tendencia = [dict(r) for r in cur.fetchall()]

    total     = int(stats["total"] or 0)
    pct_noct  = round(int(stats["partidas_nocturnas"] or 0) / total * 100, 1) if total else 0
    avg_pl    = float(stats["avg_placement"] or 0)
    top4_rate = float(stats["top4_rate"] or 0)

    # Señales de comportamiento TFT
    señales = []
    if avg_pl > 5.5 and total >= 10:
        señales.append({"tipo": "rendimiento", "nivel": "danger",
            "mensaje": f"Tu placement medio es {avg_pl:.1f}. Encadenar Bot4s es señal de tilt — considera hacer pausas entre partidas."})
    elif avg_pl > 4.5 and total >= 10:
        señales.append({"tipo": "rendimiento", "nivel": "warning",
            "mensaje": f"Placement medio de {avg_pl:.1f}. Estás más en Bot4 que en Top4. Un descanso puede mejorar tu lectura del meta."})
    if pct_noct > 25:
        señales.append({"tipo": "madrugada", "nivel": "warning",
            "mensaje": f"El {pct_noct:.0f}% de tus partidas TFT son de madrugada. La fatiga afecta al tempo de TFT especialmente."})

    return {
        "total_partidas":     total,
        "avg_placement":      avg_pl,
        "top4_rate":          top4_rate,
        "first_rate":         float(stats["first_rate"] or 0),
        "horas_total":        float(stats["horas_total"] or 0),
        "dias_jugados":       int(stats["dias_jugados"] or 0),
        "pct_nocturno":       pct_noct,
        "por_modo":           [{"modo": r["modo"], "partidas": int(r["partidas"]),
                                "avg_placement": float(r["avg_placement"] or 0),
                                "top4_rate": float(r["top4_rate"] or 0)} for r in por_modo],
        "por_hora":           [{"hora": r["hora"], "total": int(r["total"]),
                                "avg_placement": float(r["avg_placement"] or 0),
                                "top4_rate": float(r["top4_rate"] or 0)} for r in por_hora],
        "tendencia_reciente": [{"fecha": str(r["fecha"]), "placement": r["placement"],
                                "top4": r["top4"], "modo": r["modo"]} for r in tendencia],
        "señales_comportamiento": señales,
    }


# Proxies para el portal profesional
@app.get("/pro/pacientes/{paciente_id}/tft/dashboard")
def pro_tft_dashboard(paciente_id: int, ctx = Depends(get_profesional_actual), db = Depends(get_db)):
    cur = db.cursor()
    _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)
    cur.execute("SELECT * FROM usuarios_app WHERE id=%s AND activo=TRUE", (paciente_id,))
    paciente = cur.fetchone()
    if not paciente: raise HTTPException(404)
    return tft_dashboard(usuario=dict(paciente), db=db)

@app.get("/pro/pacientes/{paciente_id}/tft/historial")
def pro_tft_historial(paciente_id: int, dias: int = 30, limit: int = 50, offset: int = 0,
    fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
    ctx = Depends(get_profesional_actual), db = Depends(get_db)):
    cur = db.cursor()
    _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)
    cur.execute("SELECT * FROM usuarios_app WHERE id=%s AND activo=TRUE", (paciente_id,))
    paciente = cur.fetchone()
    if not paciente: raise HTTPException(404)
    return tft_historial(dias=dias, limit=limit, offset=offset,
        fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, usuario=dict(paciente), db=db)


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS — OBJETIVO
# ══════════════════════════════════════════════════════════════
 
@app.get("/objetivo", summary="Objetivo activo del usuario")
def get_objetivo(usuario = Depends(get_usuario_actual), db = Depends(get_db)):
    cur = db.cursor()
    cur.execute("""
        SELECT id, limite_horas_dia, limite_horas_semana,
               dias_descanso_semana, alerta_al_porcentaje,
               resumen_nocturno, hora_resumen, activo_desde,
               limite_horas_dia_tft, limite_horas_semana_tft, alerta_al_porcentaje_tft
        FROM objetivos
        WHERE usuario_id = %s AND activo = TRUE
    """, (usuario["id"],))
    obj = cur.fetchone()
    if not obj:
        raise HTTPException(status_code=404, detail="No tienes un objetivo configurado")
    return dict(obj)
 
 
@app.put("/objetivo", summary="Actualizar objetivo")
def update_objetivo(
    req:     ObjetivoUpdate,
    usuario = Depends(get_usuario_actual),
    db      = Depends(get_db),
):
    cur = db.cursor()
    cur.execute(
        "SELECT id FROM objetivos WHERE usuario_id = %s AND activo = TRUE",
        (usuario["id"],)
    )
    obj = cur.fetchone()
    if not obj:
        raise HTTPException(status_code=404, detail="No tienes un objetivo configurado")
 
    # Actualizar solo los campos que se envían
    campos = {}
    if req.limite_horas_dia        is not None: campos["limite_horas_dia"]         = req.limite_horas_dia
    if req.limite_horas_semana     is not None: campos["limite_horas_semana"]      = req.limite_horas_semana
    if req.alerta_porcentaje       is not None: campos["alerta_al_porcentaje"]     = req.alerta_porcentaje
    if req.resumen_nocturno        is not None: campos["resumen_nocturno"]         = req.resumen_nocturno
    if req.hora_resumen            is not None: campos["hora_resumen"]             = req.hora_resumen
    if req.limite_horas_dia_tft    is not None: campos["limite_horas_dia_tft"]     = req.limite_horas_dia_tft
    if req.limite_horas_semana_tft is not None: campos["limite_horas_semana_tft"]  = req.limite_horas_semana_tft
    if req.alerta_porcentaje_tft   is not None: campos["alerta_al_porcentaje_tft"] = req.alerta_porcentaje_tft
 
    if not campos:
        return {"message": "No hay cambios que guardar"}
 
    set_clause = ", ".join(f"{k} = %s" for k in campos)
    valores    = list(campos.values()) + [obj["id"]]
    cur.execute(f"UPDATE objetivos SET {set_clause} WHERE id = %s", valores)
    db.commit()
 
    return {"message": "Objetivo actualizado correctamente", "campos_actualizados": list(campos.keys())}
 
 
# ══════════════════════════════════════════════════════════════
#  ENDPOINTS — ESTADÍSTICAS DE COMPORTAMIENTO
# ══════════════════════════════════════════════════════════════
 
@app.get("/stats/comportamiento", summary="Análisis de comportamiento del jugador")
def stats_comportamiento(
    dias:    int = 30,
    usuario = Depends(get_usuario_actual),
    db      = Depends(get_db),
):
    """
    Devuelve métricas de comportamiento para el dashboard de concienciación.
    Estos datos son los más relevantes para el objetivo de la app.
    """
    puuid     = usuario.get("puuid")
    if not puuid:
        return {}
 
    cur       = db.cursor()
    fecha_ini = date.today() - timedelta(days=dias)
 
    cur.execute("""
        SELECT
            COUNT(*)                                                      AS total_partidas,
            SUM(CASE WHEN rendicion AND resultado = 'Derrota'  THEN 1 ELSE 0 END) AS total_rendiciones,
            SUM(CASE WHEN rendicion AND resultado = 'Victoria' THEN 1 ELSE 0 END) AS total_rendiciones_pos,
            SUM(CASE WHEN rendicion_temprana THEN 1 ELSE 0 END)          AS rendiciones_tempranas,
            SUM(CASE WHEN NOT apto_para_progresion THEN 1 ELSE 0 END)    AS afks,
            ROUND(AVG(tiempo_muerto_seg)::numeric / 60, 1)               AS avg_min_muerto,
            ROUND(AVG(duracion_min)::numeric, 1)                         AS avg_duracion,
            SUM(CASE WHEN resultado = 'Victoria' THEN 1 ELSE 0 END)      AS victorias,
            ROUND(
                SUM(CASE WHEN rendicion AND resultado = 'Derrota' THEN 1 ELSE 0 END)::numeric
                / NULLIF(COUNT(*), 0) * 100
            , 1)                                                          AS pct_rendiciones,
            ROUND(AVG(kda)::numeric, 2)                                  AS kda_avg,
 
            -- Horas por franja horaria (para detectar juego nocturno)
            SUM(CASE WHEN EXTRACT(HOUR FROM hora_inicio) BETWEEN 0  AND 5  THEN 1 ELSE 0 END) AS partidas_madrugada,
            SUM(CASE WHEN EXTRACT(HOUR FROM hora_inicio) BETWEEN 22 AND 23 THEN 1 ELSE 0 END) AS partidas_noche_tarde,
 
            -- Días de la semana más activos
            MODE() WITHIN GROUP (ORDER BY EXTRACT(DOW FROM fecha))        AS dia_semana_mas_activo
        FROM partidas
        WHERE puuid = %s AND fecha >= %s
    """, (puuid, fecha_ini))
    stats = dict(cur.fetchone())
 
    # Evolución semanal — horas por semana en el período
    cur.execute("""
        SELECT
            DATE_TRUNC('week', fecha)::date                            AS semana,
            ROUND(SUM(duracion_min)::numeric / 60, 2)                  AS horas,
            COUNT(*)                                                    AS partidas,
            SUM(CASE WHEN rendicion AND resultado = 'Derrota'  THEN 1 ELSE 0 END) AS rendiciones,
            SUM(CASE WHEN rendicion AND resultado = 'Victoria' THEN 1 ELSE 0 END) AS rendiciones_pos
        FROM partidas
        WHERE puuid = %s AND fecha >= %s
        GROUP BY DATE_TRUNC('week', fecha)
        ORDER BY semana
    """, (puuid, fecha_ini))
    evolucion_semanal = [dict(r) for r in cur.fetchall()]
 
    # Racha de pérdidas (tilt detector)
    cur.execute("""
        SELECT resultado, fecha, hora_inicio
        FROM partidas
        WHERE puuid = %s
        ORDER BY fecha DESC, hora_inicio DESC
        LIMIT 20
    """, (puuid,))
    ultimas_20 = [r["resultado"] for r in cur.fetchall()]
    racha_derrotas = 0
    for r in ultimas_20:
        if r == "Derrota":
            racha_derrotas += 1
        else:
            break
 
    # Señales de alerta de comportamiento
    total = int(stats["total_partidas"] or 0)
    pct_rend = float(stats["pct_rendiciones"] or 0)
    afks = int(stats["afks"] or 0)
    madrugada = int(stats["partidas_madrugada"] or 0)
    noche_tarde = int(stats["partidas_noche_tarde"] or 0)
 
    señales = []
    if pct_rend > 30:
        señales.append({
            "tipo":    "rendiciones",
            "nivel":   "warning" if pct_rend < 50 else "danger",
            "mensaje": f"Rindes en el {pct_rend:.0f}% de tus partidas. "
                       "Puede ser señal de frustración acumulada.",
        })
    if afks > 2:
        señales.append({
            "tipo":    "afk",
            "nivel":   "danger",
            "mensaje": f"{afks} partidas con AFK detectado. "
                       "Abandonar partidas afecta a otros jugadores y puede ser "
                       "señal de impulsividad.",
        })
    if madrugada + noche_tarde > 5:
        señales.append({
            "tipo":    "horario",
            "nivel":   "warning",
            "mensaje": f"{madrugada + noche_tarde} partidas jugadas de noche o madrugada. "
                       "El juego nocturno suele asociarse con peor rendimiento y "
                       "mayor impacto en el descanso.",
        })
    if racha_derrotas >= 3:
        señales.append({
            "tipo":    "tilt",
            "nivel":   "warning" if racha_derrotas < 5 else "danger",
            "mensaje": f"Llevas {racha_derrotas} derrotas consecutivas. "
                       "Este es el mejor momento para tomar un descanso.",
        })
 
    dias_semana_nombres = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
    dow = stats.get("dia_semana_mas_activo")
    dia_nombre = dias_semana_nombres[int(dow) - 1] if dow is not None else ""
 
    return {
        "periodo_dias":        dias,
        "total_partidas":      total,
        "pct_rendiciones":     pct_rend,
        "rendiciones_tempranas": int(stats["rendiciones_tempranas"] or 0),
        "afks":                afks,
        "avg_min_muerto":      float(stats["avg_min_muerto"] or 0),
        "avg_duracion_min":    float(stats["avg_duracion"] or 0),
        "kda_avg":             float(stats["kda_avg"] or 0),
        "partidas_madrugada":  madrugada,
        "partidas_noche_tarde":noche_tarde,
        "racha_derrotas_actual": racha_derrotas,
        "dia_mas_activo":      dia_nombre,
        "evolucion_semanal":   [
            {
                "semana":     str(r["semana"]),
                "horas":      float(r["horas"]),
                "partidas":   int(r["partidas"]),
                "rendiciones":int(r["rendiciones"]),
            }
            for r in evolucion_semanal
        ],
        "señales_comportamiento": señales,
    }
 
 
# ══════════════════════════════════════════════════════════════
#  ENDPOINT — BAJA / DERECHO AL OLVIDO (RGPD)
# ══════════════════════════════════════════════════════════════
 
@app.delete("/cuenta", summary="Baja del usuario — derecho al olvido (RGPD Art. 17)")
def baja_cuenta(
    usuario   = Depends(get_usuario_actual),
    db        = Depends(get_db),
    response: Response = None,
):
    """
    Anonimiza los datos del usuario en cumplimiento del RGPD.
    No borra las partidas (datos de Riot, no personales)
    pero desvincula el email y datos identificativos.
    """
    cur = db.cursor()
    uid = usuario["id"]
    anonimo = f"usuario_eliminado_{uid}"
 
    cur.execute("""
        UPDATE usuarios_app SET
            email                  = %s,
            password_hash          = 'ELIMINADO',
            riot_game_name         = %s,
            riot_tag_line          = 'DEL',
            activo                 = FALSE,
            datos_anonimizados     = TRUE,
            fecha_baja             = NOW()
        WHERE id = %s
    """, (f"{anonimo}@eliminado.local", anonimo, uid))
 
    cur.execute("UPDATE objetivos SET activo = FALSE WHERE usuario_id = %s", (uid,))
    db.commit()
    response.delete_cookie("token")

    return {
        "message": "Tu cuenta ha sido eliminada y tus datos anonimizados "
                   "en cumplimiento del RGPD (Art. 17)."
    }


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS — ANÁLISIS DESCRIPTIVO (Nivel 1)
# ══════════════════════════════════════════════════════════════

# CTE reutilizable para detección de sesiones.
# Agrupa partidas consecutivas separadas por menos de 30 minutos.
_SESSION_CTE = """
WITH partidas_ts AS (
    SELECT
        match_id,
        (fecha + hora_inicio)                                              AS ts_inicio,
        (fecha + hora_inicio + (duracion_min * INTERVAL '1 minute'))       AS ts_fin,
        kda, resultado, rendicion, apto_para_progresion,
        duracion_min, campeon, modo, dano_total_campeon,
        fecha, hora_inicio,
        EXTRACT(DOW  FROM fecha)        AS dow,
        EXTRACT(HOUR FROM hora_inicio)  AS hora
    FROM partidas
    WHERE puuid = %(puuid)s AND fecha >= %(fecha_ini)s AND fecha <= %(fecha_fin)s
),
with_gaps AS (
    SELECT *,
        EXTRACT(EPOCH FROM (
            ts_inicio - LAG(ts_fin) OVER (ORDER BY ts_inicio)
        )) / 60.0 AS gap_min
    FROM partidas_ts
),
with_session AS (
    SELECT *,
        SUM(CASE WHEN gap_min IS NULL OR gap_min > 30 THEN 1 ELSE 0 END)
            OVER (ORDER BY ts_inicio ROWS UNBOUNDED PRECEDING) AS session_num
    FROM with_gaps
)
"""


@app.get("/stats/rank-historia", summary="Historial de LP diario en Ranked Solo")
def rank_historia(
    dias:    int = 60,
    usuario = Depends(get_usuario_actual),
    db      = Depends(get_db),
):
    puuid = usuario.get("puuid")
    if not puuid:
        return {"historia": []}

    cur = db.cursor()
    cur.execute("""
        SELECT fecha, tier, division, lp, puntos_totales, victorias, derrotas
        FROM historial_rank
        WHERE puuid = %s
          AND queue_type = 'RANKED_SOLO_5x5'
          AND fecha >= CURRENT_DATE - (%s * INTERVAL '1 day')
        ORDER BY fecha ASC
    """, (puuid, dias))

    return {
        "historia": [
            {
                "fecha":     str(r["fecha"]),
                "tier":      r["tier"],
                "division":  r["division"],
                "lp":        r["lp"],
                "puntos":    r["puntos_totales"],
                "victorias": r["victorias"],
                "derrotas":  r["derrotas"],
            }
            for r in cur.fetchall()
        ]
    }


@app.get("/stats/analisis", summary="Análisis descriptivo: sesiones, curva, perfil y bienestar")
def stats_analisis(
    dias:         int          = 30,
    fecha_inicio: Optional[str] = None,
    fecha_fin_p:  Optional[str] = None,
    usuario = Depends(get_usuario_actual),
    db      = Depends(get_db),
):
    puuid = usuario.get("puuid")
    if not puuid:
        return {}

    cur = db.cursor()

    if fecha_inicio and fecha_fin_p:
        try:
            fecha_ini = date.fromisoformat(fecha_inicio)
            fecha_fin = date.fromisoformat(fecha_fin_p)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido. Usa YYYY-MM-DD")
        if fecha_ini > fecha_fin:
            raise HTTPException(status_code=400, detail="fecha_inicio no puede ser posterior a fecha_fin")
    else:
        fecha_ini = date.today() - timedelta(days=dias)
        fecha_fin = date.today()

    params = {"puuid": puuid, "fecha_ini": fecha_ini, "fecha_fin": fecha_fin}

    # ── 1. Lista de sesiones ──────────────────────────────────
    cur.execute(_SESSION_CTE + """
        SELECT
            session_num,
            MIN(fecha)::text                                                        AS fecha,
            MIN(hora_inicio)::text                                                  AS hora_inicio,
            COUNT(*)                                                                AS num_partidas,
            ROUND((EXTRACT(EPOCH FROM (MAX(ts_fin)-MIN(ts_inicio)))/60)::numeric,0) AS duracion_min,
            ROUND(AVG(kda)::numeric, 2)                                             AS kda_avg,
            ROUND(SUM(CASE WHEN resultado='Victoria' THEN 1 ELSE 0 END)::numeric
                  / NULLIF(COUNT(*),0) * 100, 0)                                    AS winrate_pct,
            SUM(CASE WHEN rendicion AND resultado = 'Derrota'  THEN 1 ELSE 0 END) AS rendiciones,
            SUM(CASE WHEN rendicion AND resultado = 'Victoria' THEN 1 ELSE 0 END) AS rendiciones_pos,
            SUM(CASE WHEN NOT apto_para_progresion THEN 1 ELSE 0 END)               AS afks,
            MODE() WITHIN GROUP (ORDER BY campeon)                                  AS campeon_principal
        FROM with_session
        GROUP BY session_num
        ORDER BY MIN(ts_inicio) DESC
        LIMIT 20
    """, params)
    sesiones = [dict(r) for r in cur.fetchall()]

    # ── 2. Resumen de sesiones ────────────────────────────────
    cur.execute(_SESSION_CTE + """
        SELECT
            COUNT(*)                                                        AS total_sesiones,
            ROUND(AVG(dur)::numeric, 0)                                     AS duracion_media_min,
            ROUND(AVG(num_p)::numeric, 1)                                   AS partidas_media,
            SUM(CASE WHEN dur > 180 THEN 1 ELSE 0 END)                      AS sesiones_mas_3h,
            SUM(CASE WHEN dur > 60  THEN 1 ELSE 0 END)                      AS sesiones_mas_1h,
            ROUND(SUM(CASE WHEN dow_inicio IN (0,6) THEN 1 ELSE 0 END)::numeric
                  / NULLIF(COUNT(*),0) * 100, 0)                            AS pct_sesiones_finde
        FROM (
            SELECT session_num,
                COUNT(*)                                                     AS num_p,
                EXTRACT(EPOCH FROM (MAX(ts_fin)-MIN(ts_inicio)))/60.0       AS dur,
                EXTRACT(DOW FROM MIN(fecha))                                 AS dow_inicio
            FROM with_session
            GROUP BY session_num
        ) s
    """, params)
    resumen_sesiones = dict(cur.fetchone() or {})

    # ── 3. Curva de rendimiento por posición en sesión ────────
    cur.execute(_SESSION_CTE + """
        , numbered AS (
            SELECT *,
                ROW_NUMBER() OVER (PARTITION BY session_num ORDER BY ts_inicio) AS pos
            FROM with_session
        )
        SELECT
            LEAST(pos::int, 6)                                              AS pos,
            COUNT(*)                                                        AS total_partidas,
            ROUND(AVG(kda)::numeric, 2)                                     AS kda_avg,
            ROUND(SUM(CASE WHEN resultado='Victoria' THEN 1 ELSE 0 END)::numeric
                  / NULLIF(COUNT(*),0) * 100, 0)                            AS winrate_pct,
            ROUND(AVG(dano_total_campeon)::numeric)                         AS dano_avg,
            ROUND(SUM(CASE WHEN rendicion AND resultado = 'Derrota' THEN 1 ELSE 0 END)::numeric
                  / NULLIF(COUNT(*),0) * 100, 0)                            AS pct_rendicion
        FROM numbered
        GROUP BY LEAST(pos::int, 6)
        HAVING COUNT(*) >= 2
        ORDER BY pos
    """, params)
    curva_rendimiento = [dict(r) for r in cur.fetchall()]

    # ── 4. Correlación hora → resultado ──────────────────────
    cur.execute("""
        SELECT
            EXTRACT(HOUR FROM hora_inicio)::int                             AS hora,
            COUNT(*)                                                        AS total_partidas,
            ROUND(AVG(kda)::numeric, 2)                                     AS kda_avg,
            ROUND(SUM(CASE WHEN resultado='Victoria' THEN 1 ELSE 0 END)::numeric
                  / NULLIF(COUNT(*),0) * 100, 0)                            AS winrate_pct,
            ROUND(SUM(CASE WHEN rendicion AND resultado = 'Derrota' THEN 1 ELSE 0 END)::numeric
                  / NULLIF(COUNT(*),0) * 100, 0)                            AS pct_rendicion,
            ROUND(AVG(dano_total_campeon)::numeric)                         AS dano_avg
        FROM partidas
        WHERE puuid = %(puuid)s AND fecha >= %(fecha_ini)s AND fecha <= %(fecha_fin)s
        GROUP BY EXTRACT(HOUR FROM hora_inicio)
        ORDER BY hora
    """, params)
    correlacion_hora = [dict(r) for r in cur.fetchall()]

    # ── 5. Rendimiento por modo de juego ──────────────────────
    cur.execute("""
        SELECT
            modo,
            COUNT(*)                                                        AS partidas,
            ROUND(AVG(kda)::numeric, 2)                                     AS kda_avg,
            ROUND(SUM(CASE WHEN resultado='Victoria' THEN 1 ELSE 0 END)::numeric
                  / NULLIF(COUNT(*),0) * 100, 0)                            AS winrate_pct,
            ROUND(SUM(CASE WHEN rendicion AND resultado = 'Derrota' THEN 1 ELSE 0 END)::numeric
                  / NULLIF(COUNT(*),0) * 100, 0)                            AS pct_rendicion,
            ROUND(AVG(cs_por_minuto)::numeric, 2)                           AS cs_min_avg
        FROM partidas
        WHERE puuid = %(puuid)s AND fecha >= %(fecha_ini)s AND fecha <= %(fecha_fin)s
        GROUP BY modo
        HAVING COUNT(*) >= 3
        ORDER BY partidas DESC
        LIMIT 6
    """, params)
    por_modo = [dict(r) for r in cur.fetchall()]

    # ── 6. Fatiga por días consecutivos ──────────────────────
    cur.execute("""
        WITH dias AS (
            SELECT fecha,
                ROUND(AVG(kda)::numeric, 2)                                 AS kda_avg,
                ROUND(SUM(CASE WHEN resultado='Victoria' THEN 1 ELSE 0 END)::numeric
                      / NULLIF(COUNT(*),0) * 100, 0)                        AS winrate_pct
            FROM partidas
            WHERE puuid = %(puuid)s AND fecha >= %(fecha_ini)s AND fecha <= %(fecha_fin)s
            GROUP BY fecha
        ),
        con_gap AS (
            SELECT fecha, kda_avg, winrate_pct,
                fecha - LAG(fecha) OVER (ORDER BY fecha)                    AS gap
            FROM dias
        ),
        con_streak AS (
            SELECT fecha, kda_avg, winrate_pct,
                SUM(CASE WHEN gap IS NULL OR gap > 1 THEN 1 ELSE 0 END)
                    OVER (ORDER BY fecha ROWS UNBOUNDED PRECEDING)           AS streak_id
            FROM con_gap
        ),
        con_pos AS (
            SELECT fecha, kda_avg, winrate_pct,
                ROW_NUMBER() OVER (PARTITION BY streak_id ORDER BY fecha)   AS dia_n
            FROM con_streak
        )
        SELECT
            LEAST(dia_n::int, 5)                                            AS dia_consecutivo,
            COUNT(*)                                                        AS total_dias,
            ROUND(AVG(kda_avg)::numeric, 2)                                 AS kda_avg,
            ROUND(AVG(winrate_pct)::numeric, 0)                             AS winrate_pct
        FROM con_pos
        GROUP BY LEAST(dia_n::int, 5)
        HAVING COUNT(*) >= 2
        ORDER BY dia_consecutivo
    """, params)
    fatiga_consecutivos = [dict(r) for r in cur.fetchall()]

    # ── 7. Stats adicionales para perfil y flags ─────────────
    cur.execute("""
        SELECT
            COUNT(*)                                                             AS total_partidas,
            COUNT(DISTINCT fecha)                                                AS dias_jugados,
            SUM(CASE WHEN EXTRACT(DOW FROM fecha) IN (0,6) THEN 1 ELSE 0 END)::float
                / NULLIF(COUNT(*),0)                                             AS pct_finde,
            SUM(CASE WHEN EXTRACT(HOUR FROM hora_inicio) >= 22
                       OR  EXTRACT(HOUR FROM hora_inicio) < 6
                     THEN 1 ELSE 0 END)::float
                / NULLIF(COUNT(*),0)                                             AS pct_nocturno,
            ROUND(AVG(kda)::numeric, 2)                                          AS kda_global,
            ROUND(SUM(CASE WHEN rendicion AND resultado = 'Derrota' THEN 1 ELSE 0 END)::numeric
                  / NULLIF(COUNT(*),0) * 100, 1)                                 AS pct_rendicion,
            ROUND(SUM(CASE WHEN rendicion AND resultado = 'Victoria' THEN 1 ELSE 0 END)::numeric
                  / NULLIF(COUNT(*),0) * 100, 1)                                 AS pct_rendicion_pos,
            SUM(CASE WHEN NOT apto_para_progresion THEN 1 ELSE 0 END)            AS total_afks
        FROM partidas
        WHERE puuid = %(puuid)s AND fecha >= %(fecha_ini)s AND fecha <= %(fecha_fin)s
    """, params)
    row_stats = dict(cur.fetchone() or {})

    # Días que superaron el límite en el período
    cur.execute("""
        SELECT o.limite_horas_dia FROM objetivos o
        WHERE o.usuario_id = %(uid)s AND o.activo = TRUE
    """, {"uid": usuario["id"]})
    obj_row  = cur.fetchone()
    limite_d = float(obj_row["limite_horas_dia"]) if obj_row else 0

    dias_excedidos = 0
    if limite_d > 0:
        cur.execute("""
            SELECT COUNT(DISTINCT fecha) AS n
            FROM partidas
            WHERE puuid = %(puuid)s AND fecha >= %(fecha_ini)s AND fecha <= %(fecha_fin)s
            GROUP BY fecha
            HAVING SUM(duracion_min) / 60.0 > %(limite)s
        """, {**params, "limite": limite_d})
        dias_excedidos = len(cur.fetchall())

    # Racha actual del usuario
    cur.execute("""
        SELECT COALESCE(racha_dias_cumplidos, 0) AS racha
        FROM progreso_diario
        WHERE usuario_id = %(uid)s
        ORDER BY fecha DESC LIMIT 1
    """, {"uid": usuario["id"]})
    racha_row    = cur.fetchone()
    racha_actual = int(racha_row["racha"] if racha_row else 0)

    # ── Python: construir perfil, flags y score ───────────────
    pct_finde     = float(row_stats.get("pct_finde",     0) or 0)
    pct_nocturno  = float(row_stats.get("pct_nocturno",  0) or 0)
    pct_rendicion     = float(row_stats.get("pct_rendicion",     0) or 0)
    pct_rendicion_pos = float(row_stats.get("pct_rendicion_pos", 0) or 0)
    kda_global        = float(row_stats.get("kda_global",        0) or 0)
    total_afks    = int(row_stats.get("total_afks",      0) or 0)
    total_dias    = max(int(row_stats.get("dias_jugados", 1) or 1), 1)
    ses_mas_3h    = int(resumen_sesiones.get("sesiones_mas_3h", 0) or 0)
    total_ses     = max(int(resumen_sesiones.get("total_sesiones", 1) or 1), 1)
    dur_media     = float(resumen_sesiones.get("duracion_media_min", 0) or 0)
    pct_maraton   = round(ses_mas_3h / total_ses * 100)
    pct_excedidos = round(dias_excedidos / total_dias * 100)

    kda_pos1 = next((float(r["kda_avg"]) for r in curva_rendimiento if r["pos"] == 1), None)
    kda_pos3 = next((float(r["kda_avg"]) for r in curva_rendimiento if r["pos"] >= 3), None)
    es_tilt  = kda_pos1 and kda_pos3 and kda_pos3 < kda_pos1 * 0.75

    perfil = {
        "jugador_finde":          pct_finde    >= 0.55,
        "jugador_nocturno":       pct_nocturno >= 0.35,
        "maratonista":            pct_maraton  >= 25,
        "tilt_chaser":            bool(es_tilt),
        "kda_global":             kda_global,
        "pct_finde":              round(pct_finde    * 100),
        "pct_nocturno":           round(pct_nocturno * 100),
        "pct_sesiones_maratones": pct_maraton,
        "kda_pos1":               kda_pos1,
        "kda_pos3":               kda_pos3,
    }

    # Mejor franja horaria (mínimo 3 partidas, winrate más alto)
    horas_validas = [h for h in correlacion_hora if h["total_partidas"] >= 3]
    mejor_hora    = max(horas_validas, key=lambda h: float(h["winrate_pct"] or 0), default=None)

    # Score de bienestar 0-100
    score = 100
    if pct_nocturno * 100 >= 40:   score -= 20
    elif pct_nocturno * 100 >= 25: score -= 12
    elif pct_nocturno * 100 >= 15: score -= 6
    if pct_maraton >= 30:          score -= 18
    elif pct_maraton >= 15:        score -= 10
    elif pct_maraton >= 5:         score -= 4
    if pct_rendicion >= 35:        score -= 18
    elif pct_rendicion >= 20:      score -= 10
    elif pct_rendicion >= 10:      score -= 4
    if pct_excedidos >= 40:        score -= 18
    elif pct_excedidos >= 20:      score -= 10
    elif pct_excedidos >= 5:       score -= 4
    score -= min(total_afks * 4, 16)
    if es_tilt:                    score -= 8
    if racha_actual >= 7:          score += 12
    elif racha_actual >= 3:        score += 6
    elif racha_actual >= 1:        score += 3
    if pct_nocturno * 100 < 10:   score += 5
    if pct_maraton < 5:            score += 5
    if pct_rendicion < 10:         score += 5
    bienestar_score = max(0, min(100, round(score)))

    # Flags (negativas + positivas)
    flags = []

    # ── Negativas ────────────────────────────────────────────
    pct_n = round(pct_nocturno * 100)
    if pct_n >= 40:
        flags.append({"tipo": "negativo", "nivel": "danger", "icono": "🌙",
            "titulo": "Juego nocturno recurrente",
            "texto": f"El {pct_n}% de tus partidas son después de las 22h o antes de las 6h. El juego nocturno reduce el rendimiento cognitivo y fragmenta el descanso.",
            "metrica": f"{pct_n}%"})
    elif pct_n >= 20:
        flags.append({"tipo": "negativo", "nivel": "warning", "icono": "🌙",
            "titulo": "Tendencia a jugar tarde",
            "texto": f"El {pct_n}% de tus partidas empiezan tarde. Adelantar las sesiones mejora el rendimiento y protege el sueño.",
            "metrica": f"{pct_n}%"})

    if pct_maraton >= 30:
        flags.append({"tipo": "negativo", "nivel": "danger", "icono": "⏰",
            "titulo": "Sesiones maratón frecuentes",
            "texto": f"El {pct_maraton}% de tus sesiones superan las 3 horas. La fatiga mental acumulada empeora la toma de decisiones y aumenta el comportamiento impulsivo.",
            "metrica": f"{ses_mas_3h} sesiones +3h"})
    elif pct_maraton >= 15:
        flags.append({"tipo": "negativo", "nivel": "warning", "icono": "⏰",
            "titulo": "Sesiones largas",
            "texto": f"{ses_mas_3h} sesiones han superado las 3 horas. El rendimiento cae significativamente a partir de la 2ª hora continua.",
            "metrica": f"{ses_mas_3h} sesiones +3h"})

    if pct_excedidos >= 40:
        flags.append({"tipo": "negativo", "nivel": "danger", "icono": "🚨",
            "titulo": "Límite diario superado frecuentemente",
            "texto": f"Has superado tu límite en el {pct_excedidos}% de los días jugados. El límite lo pusiste tú como compromiso contigo mismo — respetarlo es la clave del cambio.",
            "metrica": f"{pct_excedidos}% de días"})
    elif pct_excedidos >= 20:
        flags.append({"tipo": "negativo", "nivel": "warning", "icono": "⚠️",
            "titulo": "Límite superado ocasionalmente",
            "texto": f"Has superado tu límite en el {pct_excedidos}% de los días jugados. La tendencia importa más que los días aislados.",
            "metrica": f"{pct_excedidos}% de días"})

    if pct_rendicion >= 35:
        flags.append({"tipo": "negativo", "nivel": "danger", "icono": "🏳️",
            "titulo": "Alta tasa de rendición negativa",
            "texto": f"Tu equipo rindió en el {pct_rendicion:.0f}% de tus derrotas. Una tasa tan alta es indicador claro de frustración acumulada — el tilt está afectando a tu juego. Considera pausas activas entre partidas.",
            "metrica": f"{pct_rendicion:.0f}% derrotas"})
    elif pct_rendicion >= 20:
        flags.append({"tipo": "negativo", "nivel": "warning", "icono": "🏳️",
            "titulo": "Tasa de rendición elevada",
            "texto": f"Tu equipo rindió en el {pct_rendicion:.0f}% de tus partidas. Prueba a hacer una pausa de 10 minutos después de cada derrota antes de empezar la siguiente.",
            "metrica": f"{pct_rendicion:.0f}%"})

    if total_afks >= 3:
        flags.append({"tipo": "negativo", "nivel": "danger", "icono": "💤",
            "titulo": "AFK repetido",
            "texto": f"Se han detectado {total_afks} partidas con AFK. Abandonar partidas perjudica a otros jugadores y es señal de gestión emocional bajo presión.",
            "metrica": f"{total_afks} partidas"})
    elif total_afks >= 1:
        flags.append({"tipo": "negativo", "nivel": "warning", "icono": "💤",
            "titulo": "AFK detectado",
            "texto": f"{total_afks} partida(s) con AFK en el período. Cuando quieras irte, la rendición del equipo es la alternativa responsable.",
            "metrica": f"{total_afks}"})

    if es_tilt and kda_pos1 and kda_pos3:
        caida = round((1 - kda_pos3 / max(kda_pos1, 0.01)) * 100)
        flags.append({"tipo": "negativo", "nivel": "warning", "icono": "📉",
            "titulo": "Rendimiento cae en sesión larga",
            "texto": f"Tu KDA cae un {caida}% en la partida 3ª o posterior de una sesión. Tu cerebro ya está fatigado — parar después de 2 partidas seguidas es lo más inteligente.",
            "metrica": f"-{caida}% KDA"})

    if fatiga_consecutivos and len(fatiga_consecutivos) >= 3:
        wr_d1 = float(fatiga_consecutivos[0]["winrate_pct"] or 0)
        wr_d3 = float(fatiga_consecutivos[-1]["winrate_pct"] or 0)
        if wr_d3 < wr_d1 * 0.85:
            caida_dias = round(wr_d1 - wr_d3)
            flags.append({"tipo": "negativo", "nivel": "warning", "icono": "😴",
                "titulo": "Fatiga acumulada por días consecutivos",
                "texto": f"Tu winrate cae {caida_dias} puntos porcentuales en el día 3+ de juego consecutivo. Un día de descanso entre sesiones mantiene el rendimiento.",
                "metrica": f"-{caida_dias}pp WR"})

    # ── Positivas ────────────────────────────────────────────
    if dias_excedidos == 0 and total_dias >= 3:
        flags.append({"tipo": "positivo", "nivel": "good", "icono": "✅",
            "titulo": "Límite respetado en todo el período",
            "texto": "No has superado tu límite diario en ningún día. Cumplir el compromiso contigo mismo de forma consistente es el primer paso hacia un hábito saludable.",
            "metrica": "0 excesos"})

    if pct_n < 10 and total_dias >= 5:
        flags.append({"tipo": "positivo", "nivel": "good", "icono": "☀️",
            "titulo": "Horario de juego saludable",
            "texto": f"Más del 90% de tus partidas empiezan antes de las 22h. Jugar en horario diurno protege el descanso y permite rendir mejor.",
            "metrica": f"{100 - pct_n}% diurno"})

    if 0 < dur_media <= 75 and total_ses >= 3:
        flags.append({"tipo": "positivo", "nivel": "good", "icono": "⚡",
            "titulo": "Sesiones equilibradas",
            "texto": f"Tus sesiones duran {round(dur_media)}min de media. Sesiones enfocadas y cortas maximizan el disfrute sin la fatiga de las maratones.",
            "metrica": f"{round(dur_media)}min media"})

    if pct_rendicion < 10 and int(row_stats.get("total_partidas", 0) or 0) >= 10:
        extra = f" Además, el {pct_rendicion_pos:.0f}% de tus victorias fueron por rendición rival — señal de que presionas bien." if pct_rendicion_pos >= 20 else ""
        flags.append({"tipo": "positivo", "nivel": "good", "icono": "💪",
            "titulo": "Buena gestión emocional — pocas rendiciones",
            "texto": f"Tu equipo rindió en apenas el {pct_rendicion:.0f}% de tus partidas. Indica compromiso con el equipo y resiliencia ante situaciones difíciles.{extra}",
            "metrica": f"{pct_rendicion:.0f}% neg."})

    if pct_rendicion_pos >= 25 and int(row_stats.get("total_partidas", 0) or 0) >= 10:
        flags.append({"tipo": "positivo", "nivel": "good", "icono": "🏆",
            "titulo": "El rival rinde con frecuencia",
            "texto": f"El {pct_rendicion_pos:.0f}% de tus victorias fueron por rendición del equipo contrario. Significa que estás ejecutando bien las ventajas y cerrando partidas de forma convincente.",
            "metrica": f"{pct_rendicion_pos:.0f}% victorias"})

    if racha_actual >= 7:
        flags.append({"tipo": "positivo", "nivel": "good", "icono": "🔥",
            "titulo": f"Racha de {racha_actual} días",
            "texto": f"Llevas {racha_actual} días consecutivos respetando tu límite. Esta constancia es el indicador más sólido de un cambio de hábito real.",
            "metrica": f"{racha_actual} días"})
    elif racha_actual >= 3:
        flags.append({"tipo": "positivo", "nivel": "good", "icono": "⚡",
            "titulo": f"Racha activa: {racha_actual} días",
            "texto": f"Llevas {racha_actual} días cumpliendo tu objetivo. La constancia es lo que convierte una intención en un hábito.",
            "metrica": f"{racha_actual} días"})

    if mejor_hora and float(mejor_hora["winrate_pct"] or 0) >= 60:
        flags.append({"tipo": "positivo", "nivel": "good", "icono": "🎯",
            "titulo": f"Tu mejor franja: {mejor_hora['hora']:02d}:00h",
            "texto": f"Tienes un {mejor_hora['winrate_pct']}% de victorias cuando juegas a las {mejor_hora['hora']:02d}:00h. Organiza tus sesiones en este horario para maximizar el rendimiento.",
            "metrica": f"{mejor_hora['winrate_pct']}% WR"})

    return {
        "periodo_dias":      dias,
        "bienestar_score":   bienestar_score,
        "perfil":            perfil,
        "flags":             flags,
        "sesiones":          sesiones,
        "resumen_sesiones":  resumen_sesiones,
        "curva_rendimiento": curva_rendimiento,
        "correlacion_hora":  correlacion_hora,
        "por_modo":          por_modo,
        "fatiga_consecutivos": fatiga_consecutivos,
        "mejor_hora":        dict(mejor_hora) if mejor_hora else None,
        "racha_actual":      racha_actual,
    }
 
 
# ══════════════════════════════════════════════════════════════
#  SYNC MANUAL
# ══════════════════════════════════════════════════════════════

# Mínimo de segundos entre sincronizaciones manuales del mismo usuario.
# Evita que se abuse del endpoint mientras la Riot API actualiza datos
# (Match V5 tarda 2-5 min en reflejar una partida terminada).
_SYNC_COOLDOWN_SEG = 120

@app.post("/sync/me", summary="Sincronizar partidas del usuario actual")
def sync_me(usuario = Depends(get_usuario_actual), db = Depends(get_db)):
    """
    Lanza la sincronización en un hilo de fondo y responde inmediatamente.
    Esto evita timeouts en Render y en el navegador durante la carga inicial,
    que puede tardar varios minutos si hay mucho historial por importar.
    """
    from extractor import sync_usuario

    # Cooldown: evitar spam al endpoint
    ultima = usuario.get("ultima_sincronizacion")
    if ultima:
        ahora = datetime.now()
        if hasattr(ultima, "tzinfo") and ultima.tzinfo is not None:
            from datetime import timezone
            ahora = datetime.now(timezone.utc)
        diff = (ahora - ultima).total_seconds()
        if diff < _SYNC_COOLDOWN_SEG:
            espera = int(_SYNC_COOLDOWN_SEG - diff)
            raise HTTPException(
                status_code=429,
                detail=f"Sincronización reciente. Espera {espera}s antes de volver a sincronizar."
            )

    # Marcar sync como iniciada antes de lanzar el hilo
    cur = db.cursor()
    cur.execute(
        "UPDATE usuarios_app SET ultima_sincronizacion = NOW() WHERE id = %s",
        (usuario["id"],)
    )
    db.commit()

    usuario_data = {
        "id":                    usuario["id"],
        "email":                 usuario["email"],
        "riot_game_name":        usuario["riot_game_name"],
        "riot_tag_line":         usuario["riot_tag_line"],
        "puuid":                 usuario.get("puuid"),
        "region":                usuario.get("region", "EUW"),
        "ultima_sincronizacion": ultima,
    }

    def _run():
        try:
            nuevas = sync_usuario(usuario_data)
            log.info(f"Sync manual completada: {usuario['riot_game_name']} -> {nuevas or 0} partidas nuevas")
        except Exception as e:
            log.error(f"Error en sync manual de {usuario['email']}: {e}")

    threading.Thread(target=_run, daemon=True).start()

    return {
        "message":  "Sincronización iniciada. Los datos aparecerán en el dashboard en unos minutos.",
        "en_curso": True,
    }


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS — PROFESIONALES (B2B)
# ══════════════════════════════════════════════════════════════

import secrets as _secrets

_ESTADOS_TRATAMIENTO = ["evaluacion", "tratamiento_activo", "seguimiento", "alta"]

# ── Modelos ────────────────────────────────────────────────────

class ProRegistroRequest(BaseModel):
    email:              EmailStr
    password:           str
    nombre:             str
    apellidos:          str
    numero_colegiado:   str
    especialidad:       str
    consentimiento_datos: bool = False

    @field_validator("password")
    @classmethod
    def pwd_min(cls, v):
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v

    @field_validator("consentimiento_datos")
    @classmethod
    def debe_aceptar(cls, v):
        if not v:
            raise ValueError("Debes aceptar el tratamiento de datos")
        return v

_CATEGORIAS_NOTA = ["observacion", "plan", "alerta", "logro"]

class NotaRequest(BaseModel):
    contenido: str
    categoria: str = "observacion"

    @field_validator("categoria")
    @classmethod
    def categoria_valida(cls, v):
        if v not in _CATEGORIAS_NOTA:
            raise ValueError(f"Categoría debe ser una de: {_CATEGORIAS_NOTA}")
        return v

class EstadoRequest(BaseModel):
    estado: str

    @field_validator("estado")
    @classmethod
    def estado_valido(cls, v):
        if v not in _ESTADOS_TRATAMIENTO:
            raise ValueError(f"Estado debe ser uno de: {_ESTADOS_TRATAMIENTO}")
        return v


# ── Registro y perfil ──────────────────────────────────────────

@app.post("/pro/registro", summary="Registro de profesional sanitario")
def pro_registro(req: ProRegistroRequest, response: Response, db = Depends(get_db)):
    cur = db.cursor()
    cur.execute("SELECT id FROM usuarios_app WHERE email = %s", (req.email.lower(),))
    if cur.fetchone():
        raise HTTPException(409, detail="Este email ya está registrado")

    pwd_hash   = hash_password(req.password)
    link_token = _secrets.token_urlsafe(32)

    cur.execute("""
        INSERT INTO usuarios_app (
            email, riot_game_name, riot_tag_line, password_hash,
            consentimiento_datos, fecha_consentimiento, activo, rol
        ) VALUES (%s, %s, %s, %s, %s, NOW(), TRUE, 'profesional')
        RETURNING id, token_version
    """, (req.email.lower(), f"{req.nombre} {req.apellidos}"[:50], "PRO", pwd_hash, req.consentimiento_datos))
    row        = cur.fetchone()
    usuario_id = row["id"]

    cur.execute("""
        INSERT INTO profesionales (usuario_id, nombre, apellidos, numero_colegiado, especialidad, link_token)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (usuario_id, req.nombre.strip(), req.apellidos.strip(),
          req.numero_colegiado.strip(), req.especialidad.strip(), link_token))

    db.commit()
    token = crear_token(usuario_id, req.email.lower(), row["token_version"], rol="profesional")
    set_auth_cookie(response, token)
    log.info(f"Nuevo profesional registrado: {req.email}")
    return {"ok": True, "email": req.email.lower(), "rol": "profesional"}


@app.get("/pro/me", summary="Perfil del profesional autenticado")
def pro_me(ctx = Depends(get_profesional_actual)):
    pro = ctx["profesional"]
    return {
        "id":                pro["id"],
        "nombre":            pro["nombre"],
        "apellidos":         pro["apellidos"],
        "email":             ctx["email"],
        "especialidad":      pro["especialidad"],
        "numero_colegiado":  pro["numero_colegiado"],
        "verificado":        pro["verificado"],
        "link_token":        pro["link_token"],
    }


# ── Invitación ─────────────────────────────────────────────────

@app.get("/invitacion/{token}", summary="Info pública del profesional para la página de invitación")
def invitacion_info(token: str, db = Depends(get_db)):
    cur = db.cursor()
    cur.execute("""
        SELECT p.nombre, p.apellidos, p.especialidad
        FROM profesionales p
        WHERE p.link_token = %s AND p.activo = TRUE
    """, (token,))
    pro = cur.fetchone()
    if not pro:
        raise HTTPException(404, detail="Enlace de invitación no válido o expirado")
    return {
        "nombre":      pro["nombre"],
        "apellidos":   pro["apellidos"],
        "especialidad":pro["especialidad"],
    }


class AceptarInvitacionRequest(BaseModel):
    nombre:                str
    apellidos:             str
    email:                 EmailStr
    riot_game_name:        str
    riot_tag_line:         str
    consentimiento_datos:  bool
    consentimiento_emails: bool = False

    @field_validator("consentimiento_datos")
    @classmethod
    def debe_aceptar(cls, v):
        if not v:
            raise ValueError("El consentimiento de datos es obligatorio")
        return v

    @field_validator("nombre", "apellidos")
    @classmethod
    def no_vacio(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Este campo no puede estar vacío")
        return v


@app.post("/invitacion/{token}/aceptar", summary="Paciente acepta la invitación del profesional")
def invitacion_aceptar(token: str, data: AceptarInvitacionRequest, db = Depends(get_db)):
    """
    NO crea cuenta de usuario. Solo guarda los datos en invitaciones_pro como
    'pendiente_registro'. Cuando el paciente complete el registro con el mismo
    email, se crea la relación automáticamente.
    """
    cur = db.cursor()

    cur.execute(
        "SELECT id FROM profesionales WHERE link_token = %s AND activo = TRUE",
        (token,)
    )
    pro = cur.fetchone()
    if not pro:
        raise HTTPException(404, detail="Enlace de invitación no válido")

    email = data.email.lower().strip()

    # Upsert por (profesional_id, email_paciente) — evita duplicados si el paciente
    # vuelve a rellenar el formulario, sin colisionar con otras invitaciones del mismo pro
    nombre    = data.nombre.strip()
    apellidos = data.apellidos.strip()

    inv_token = _secrets.token_urlsafe(16)
    cur.execute("""
        INSERT INTO invitaciones_pro
            (profesional_id, token, email_paciente, riot_game_name, riot_tag_line,
             nombre_paciente, apellidos_paciente, estado)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'pendiente_registro')
        ON CONFLICT (profesional_id, email_paciente) DO UPDATE SET
            riot_game_name     = EXCLUDED.riot_game_name,
            riot_tag_line      = EXCLUDED.riot_tag_line,
            nombre_paciente    = EXCLUDED.nombre_paciente,
            apellidos_paciente = EXCLUDED.apellidos_paciente,
            estado             = 'pendiente_registro'
    """, (
        pro["id"], inv_token, email,
        data.riot_game_name.strip(),
        data.riot_tag_line.strip().lstrip("#"),
        nombre, apellidos,
    ))

    # Si el paciente ya tiene cuenta, vincular directamente y actualizar nombre real
    cur.execute("SELECT id FROM usuarios_app WHERE email = %s", (email,))
    existing = cur.fetchone()
    if existing:
        cur.execute(
            "UPDATE usuarios_app SET es_paciente = TRUE, nombre_real = %s, apellidos_real = %s WHERE id = %s",
            (nombre, apellidos, existing["id"])
        )
        cur.execute("""
            INSERT INTO relaciones_pro_paciente (profesional_id, paciente_id, estado_tratamiento)
            VALUES (%s, %s, 'evaluacion')
            ON CONFLICT (profesional_id, paciente_id) DO NOTHING
        """, (pro["id"], existing["id"]))
        cur.execute(
            "UPDATE invitaciones_pro SET estado = 'completada', paciente_id = %s WHERE token = %s",
            (existing["id"], token)
        )

    db.commit()
    log.info(f"Invitación pendiente: pro_id={pro['id']} email={email}")
    return {"ok": True}


# ── Lista de pacientes ──────────────────────────────────────────

def _calcular_alertas_paciente(r: dict) -> list:
    """Genera la lista de alertas automáticas para un paciente en la lista del profesional."""
    alertas = []
    excesos   = int(r.get("excesos_7d") or 0)
    madrugada = int(r.get("partidas_madrugada_7d") or 0)
    pct_rend  = float(r.get("pct_rendicion_7d") or 0)
    dias_sin  = int(r.get("dias_sin_jugar") or 0)

    if excesos >= 3:
        alertas.append({"tipo": "exceso", "nivel": "danger",
            "texto": f"Superó el límite {excesos} días esta semana"})
    elif excesos >= 1:
        alertas.append({"tipo": "exceso", "nivel": "warning",
            "texto": f"Superó el límite {excesos} día{'s' if excesos > 1 else ''} esta semana"})

    if madrugada >= 3:
        alertas.append({"tipo": "madrugada", "nivel": "warning",
            "texto": f"Jugó de madrugada (+23h) {madrugada} veces esta semana"})

    if pct_rend >= 40:
        alertas.append({"tipo": "rendicion", "nivel": "danger",
            "texto": f"Tasa de rendición del {pct_rend:.0f}% en los últimos 7 días"})
    elif pct_rend >= 25:
        alertas.append({"tipo": "rendicion", "nivel": "warning",
            "texto": f"Tasa de rendición del {pct_rend:.0f}% en los últimos 7 días"})

    if dias_sin >= 14:
        alertas.append({"tipo": "inactividad", "nivel": "info",
            "texto": f"Sin actividad hace {dias_sin} días"})

    return alertas


@app.get("/pro/pacientes", summary="Lista de pacientes del profesional")
def pro_pacientes(ctx = Depends(get_profesional_actual), db = Depends(get_db)):
    cur = db.cursor()
    cur.execute("""
        SELECT
            u.id,
            u.riot_game_name,
            u.riot_tag_line,
            u.email,
            u.nombre_real,
            u.apellidos_real,
            u.ultima_sincronizacion,
            u.puuid,
            r.id                  AS relacion_id,
            r.estado_tratamiento,
            r.fecha_inicio,
            r.fecha_alta,
            r.activo              AS relacion_activa,
            -- Última partida
            (SELECT MAX(p.fecha) FROM partidas p WHERE p.puuid = u.puuid) AS ultima_partida,
            -- Horas última semana
            (SELECT COALESCE(ROUND(SUM(p.duracion_min)::numeric / 60, 1), 0)
             FROM partidas p
             WHERE p.puuid = u.puuid
               AND p.fecha >= CURRENT_DATE - INTERVAL '7 days') AS horas_semana,
            -- pct limite ultimo dia con actividad
            (SELECT pd.porcentaje_consumido_dia
             FROM progreso_diario pd
             WHERE pd.usuario_id = u.id
             ORDER BY pd.fecha DESC LIMIT 1) AS ultimo_pct_limite,
            -- Alertas automáticas: excesos recientes
            (SELECT COUNT(*) FROM progreso_diario pd
             WHERE pd.usuario_id = u.id
               AND pd.fecha >= CURRENT_DATE - INTERVAL '7 days'
               AND pd.objetivo_dia_cumplido = FALSE) AS excesos_7d,
            -- Partidas de madrugada últimos 7 días (después de las 23h)
            (SELECT COUNT(*) FROM partidas p
             WHERE p.puuid = u.puuid
               AND p.fecha >= CURRENT_DATE - INTERVAL '7 days'
               AND EXTRACT(HOUR FROM p.hora_inicio) >= 23) AS partidas_madrugada_7d,
            -- Tasa de rendición negativa últimos 7 días
            (SELECT ROUND(
                SUM(CASE WHEN rendicion AND resultado='Derrota' THEN 1 ELSE 0 END)::numeric
                / NULLIF(COUNT(*),0) * 100, 0)
             FROM partidas p
             WHERE p.puuid = u.puuid
               AND p.fecha >= CURRENT_DATE - INTERVAL '7 days') AS pct_rendicion_7d,
            -- Días sin jugar (para detectar abandono de la app)
            (CURRENT_DATE - MAX(p2.fecha)) AS dias_sin_jugar
        FROM relaciones_pro_paciente r
        JOIN usuarios_app u ON u.id = r.paciente_id
        LEFT JOIN partidas p2 ON p2.puuid = u.puuid
        WHERE r.profesional_id = %s
        GROUP BY u.id, u.riot_game_name, u.riot_tag_line, u.email,
                 u.ultima_sincronizacion, u.puuid,
                 r.id, r.estado_tratamiento, r.fecha_inicio, r.fecha_alta, r.activo
        ORDER BY r.estado_tratamiento, u.riot_game_name
    """, (ctx["profesional"]["id"],))

    pacientes = []
    for row in cur.fetchall():
        r = dict(row)
        pacientes.append({
            "id":                 r["id"],
            "riot_game_name":     r["riot_game_name"],
            "riot_tag_line":      r["riot_tag_line"],
            "nombre_real":        r["nombre_real"] or "",
            "apellidos_real":     r["apellidos_real"] or "",
            "nombre_display":     f"{r['nombre_real']} {r['apellidos_real']}".strip() if r["nombre_real"] else r["riot_game_name"],
            "email":              r["email"],
            "relacion_id":        r["relacion_id"],
            "estado_tratamiento": r["estado_tratamiento"],
            "fecha_inicio":       str(r["fecha_inicio"])[:10] if r["fecha_inicio"] else None,
            "fecha_alta":         str(r["fecha_alta"])[:10] if r["fecha_alta"] else None,
            "activo":             r["relacion_activa"],
            "ultima_partida":     str(r["ultima_partida"]) if r["ultima_partida"] else None,
            "horas_semana":       float(r["horas_semana"] or 0),
            "sincronizado":       r["puuid"] is not None,
            "ultimo_pct_limite":  float(r["ultimo_pct_limite"] or 0),
            "alertas":            _calcular_alertas_paciente(r),
        })
    return {"pacientes": pacientes}


# ── Detalle del paciente (reutiliza lógica existente) ──────────

def _verificar_acceso_paciente(profesional_id: int, paciente_id: int, cur):
    cur.execute("""
        SELECT r.id, r.estado_tratamiento, r.activo
        FROM relaciones_pro_paciente r
        WHERE r.profesional_id = %s AND r.paciente_id = %s
    """, (profesional_id, paciente_id))
    rel = cur.fetchone()
    if not rel:
        raise HTTPException(403, detail="No tienes acceso a este paciente")
    return dict(rel)


@app.get("/pro/pacientes/{paciente_id}/resumen-consulta", summary="Resumen pre-consulta del paciente (últimos 7 días)")
def pro_resumen_consulta(
    paciente_id: int,
    dias: int = 7,
    ctx = Depends(get_profesional_actual),
    db  = Depends(get_db),
):
    cur = db.cursor()
    _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)
    cur.execute("SELECT * FROM usuarios_app WHERE id = %s AND activo = TRUE", (paciente_id,))
    paciente = cur.fetchone()
    if not paciente or not paciente["puuid"]:
        return {"sincronizado": False}

    puuid = paciente["puuid"]
    uid   = paciente["id"]

    # ── Estadísticas del período actual ──────────────────────────
    cur.execute("""
        SELECT
            COUNT(*)                                                             AS partidas,
            COALESCE(ROUND(SUM(duracion_min)::numeric/60, 2), 0)                AS horas_total,
            COALESCE(ROUND(AVG(kda)::numeric, 2), 0)                            AS kda_avg,
            SUM(CASE WHEN resultado='Victoria'                  THEN 1 ELSE 0 END) AS victorias,
            SUM(CASE WHEN rendicion AND resultado='Derrota'     THEN 1 ELSE 0 END) AS rendiciones_neg,
            SUM(CASE WHEN NOT apto_para_progresion             THEN 1 ELSE 0 END) AS afks,
            SUM(CASE WHEN EXTRACT(HOUR FROM hora_inicio) >= 23 THEN 1 ELSE 0 END) AS partidas_madrugada,
            COUNT(DISTINCT fecha)                                                AS dias_jugados,
            ROUND(AVG(duracion_min)::numeric, 1)                                AS duracion_media
        FROM partidas
        WHERE puuid = %s AND fecha >= CURRENT_DATE - (%s * INTERVAL '1 day')
    """, (puuid, dias))
    stats_row = dict(cur.fetchone())

    # ── Días que superaron el límite ──────────────────────────────
    cur.execute("""
        SELECT COUNT(*) AS excesos
        FROM progreso_diario
        WHERE usuario_id = %s
          AND fecha >= CURRENT_DATE - (%s * INTERVAL '1 day')
          AND objetivo_dia_cumplido = FALSE
    """, (uid, dias))
    excesos = int(cur.fetchone()["excesos"] or 0)

    # ── Peor día del período ──────────────────────────────────────
    cur.execute("""
        SELECT fecha, ROUND(SUM(duracion_min)::numeric/60, 2) AS horas
        FROM partidas
        WHERE puuid = %s AND fecha >= CURRENT_DATE - (%s * INTERVAL '1 day')
        GROUP BY fecha ORDER BY horas DESC LIMIT 1
    """, (puuid, dias))
    peor_dia = dict(cur.fetchone()) if cur.rowcount else None

    # ── Racha actual ──────────────────────────────────────────────
    cur.execute("""
        SELECT racha_dias_cumplidos FROM progreso_diario
        WHERE usuario_id = %s ORDER BY fecha DESC LIMIT 1
    """, (uid,))
    racha_row = cur.fetchone()
    racha = int(racha_row["racha_dias_cumplidos"] if racha_row else 0)

    # ── Señales críticas automáticas ─────────────────────────────
    total     = int(stats_row["partidas"] or 0)
    horas     = float(stats_row["horas_total"] or 0)
    victorias = int(stats_row["victorias"] or 0)
    rend_neg  = int(stats_row["rendiciones_neg"] or 0)
    afks      = int(stats_row["afks"] or 0)
    madrugada = int(stats_row["partidas_madrugada"] or 0)
    pct_rend  = round(rend_neg / total * 100, 1) if total > 0 else 0
    pct_vic   = round(victorias / total * 100, 1) if total > 0 else 0

    señales_criticas  = []
    señales_positivas = []

    if excesos >= 3:
        señales_criticas.append(f"Superó el límite en {excesos} de los últimos {dias} días")
    elif excesos >= 1:
        señales_criticas.append(f"Superó el límite {excesos} día{'s' if excesos > 1 else ''}")

    if pct_rend >= 30:
        señales_criticas.append(f"Alta tasa de rendición: {pct_rend:.0f}% de las partidas")

    if madrugada >= 3:
        señales_criticas.append(f"Jugó de madrugada en {madrugada} ocasiones esta semana")

    if afks >= 2:
        señales_criticas.append(f"{afks} partidas con AFK detectado")

    if pct_vic >= 55 and total >= 5:
        señales_positivas.append(f"Buen winrate: {pct_vic:.0f}% ({victorias}V/{total - victorias}D)")

    if racha >= 3:
        señales_positivas.append(f"Racha activa de {racha} días cumpliendo el objetivo")

    if excesos == 0 and total > 0:
        señales_positivas.append(f"Respetó el límite todos los días del período")

    # ── Tendencia vs período anterior ────────────────────────────
    cur.execute("""
        SELECT COALESCE(ROUND(SUM(duracion_min)::numeric/60, 2), 0) AS horas_ant
        FROM partidas
        WHERE puuid = %s
          AND fecha >= CURRENT_DATE - (%s * INTERVAL '1 day') * 2
          AND fecha <  CURRENT_DATE - (%s * INTERVAL '1 day')
    """, (puuid, dias, dias))
    horas_ant = float(cur.fetchone()["horas_ant"] or 0)

    if horas_ant == 0:
        tendencia = "sin_datos_anteriores"
    elif horas < horas_ant * 0.85:
        tendencia = "mejorando"
    elif horas > horas_ant * 1.15:
        tendencia = "empeorando"
    else:
        tendencia = "estable"

    return {
        "sincronizado":      True,
        "periodo_dias":      dias,
        "stats": {
            "partidas":         total,
            "horas_total":      horas,
            "kda_avg":          float(stats_row["kda_avg"] or 0),
            "winrate_pct":      pct_vic,
            "dias_jugados":     int(stats_row["dias_jugados"] or 0),
            "excesos_limite":   excesos,
            "rendicion_pct":    pct_rend,
            "afks":             afks,
            "madrugada":        madrugada,
            "duracion_media_min": float(stats_row["duracion_media"] or 0),
            "racha_actual":     racha,
        },
        "peor_dia":           {"fecha": str(peor_dia["fecha"]), "horas": float(peor_dia["horas"])} if peor_dia else None,
        "señales_criticas":   señales_criticas,
        "señales_positivas":  señales_positivas,
        "tendencia":          tendencia,
        "horas_periodo_anterior": horas_ant,
    }


@app.get("/pro/pacientes/{paciente_id}/comparativa", summary="Comparativa de dos períodos del paciente")
def pro_comparativa(
    paciente_id:    int,
    dias_actual:    int = 30,
    dias_anterior:  int = 30,
    ctx = Depends(get_profesional_actual),
    db  = Depends(get_db),
):
    cur = db.cursor()
    _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)
    cur.execute("SELECT puuid FROM usuarios_app WHERE id = %s AND activo = TRUE", (paciente_id,))
    row = cur.fetchone()
    if not row or not row["puuid"]:
        return {"sincronizado": False}
    puuid = row["puuid"]

    def _periodo_stats(desde_dias, hasta_dias):
        cur.execute("""
            SELECT
                COUNT(*)                                                              AS partidas,
                COALESCE(ROUND(SUM(duracion_min)::numeric/60, 2), 0)                 AS horas,
                COALESCE(ROUND(AVG(duracion_min)::numeric/60/NULLIF(COUNT(DISTINCT fecha),0), 2), 0) AS horas_dia_media,
                SUM(CASE WHEN resultado='Victoria'              THEN 1 ELSE 0 END)   AS victorias,
                SUM(CASE WHEN rendicion AND resultado='Derrota' THEN 1 ELSE 0 END)   AS rendiciones,
                SUM(CASE WHEN NOT apto_para_progresion          THEN 1 ELSE 0 END)   AS afks,
                SUM(CASE WHEN EXTRACT(HOUR FROM hora_inicio)>=23 THEN 1 ELSE 0 END)  AS madrugada,
                COUNT(DISTINCT fecha)                                                 AS dias_jugados,
                (CURRENT_DATE - INTERVAL '1 day' * %s)::text                         AS fecha_desde,
                (CURRENT_DATE - INTERVAL '1 day' * %s)::text                         AS fecha_hasta
            FROM partidas
            WHERE puuid = %s
              AND fecha >= CURRENT_DATE - (%s * INTERVAL '1 day')
              AND fecha <  CURRENT_DATE - (%s * INTERVAL '1 day')
        """, (hasta_dias, desde_dias, puuid, hasta_dias, desde_dias))
        r = dict(cur.fetchone())
        total = int(r["partidas"] or 0)
        return {
            "desde":          r["fecha_desde"],
            "hasta":          r["fecha_hasta"],
            "partidas":       total,
            "horas":          float(r["horas"] or 0),
            "horas_dia":      float(r["horas_dia_media"] or 0),
            "winrate_pct":    round(int(r["victorias"] or 0) / total * 100, 1) if total else 0,
            "rendicion_pct":  round(int(r["rendiciones"] or 0) / total * 100, 1) if total else 0,
            "afks":           int(r["afks"] or 0),
            "madrugada":      int(r["madrugada"] or 0),
            "dias_jugados":   int(r["dias_jugados"] or 0),
        }

    actual   = _periodo_stats(0, dias_actual)
    anterior = _periodo_stats(dias_actual, dias_actual + dias_anterior)

    def _cambio(nuevo, viejo):
        if viejo == 0: return None
        return round(nuevo - viejo, 2)

    return {
        "actual":   actual,
        "anterior": anterior,
        "cambio": {
            "horas_dia":     _cambio(actual["horas_dia"], anterior["horas_dia"]),
            "winrate_pct":   _cambio(actual["winrate_pct"], anterior["winrate_pct"]),
            "rendicion_pct": _cambio(actual["rendicion_pct"], anterior["rendicion_pct"]),
            "madrugada":     _cambio(actual["madrugada"], anterior["madrugada"]),
        },
    }


@app.get("/pro/pacientes/{paciente_id}/mes", summary="Calendario mensual del paciente")
def pro_paciente_mes(
    paciente_id: int,
    year:  int = None,
    month: int = None,
    ctx = Depends(get_profesional_actual),
    db  = Depends(get_db),
):
    cur = db.cursor()
    _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)
    cur.execute("SELECT * FROM usuarios_app WHERE id = %s AND activo = TRUE", (paciente_id,))
    paciente = cur.fetchone()
    if not paciente:
        raise HTTPException(404, detail="Paciente no encontrado")
    puuid = paciente["puuid"]
    if not puuid:
        hoy = date.today()
        return {"year": year or hoy.year, "month": month or hoy.month, "limite_dia": 0, "dias": []}
    hoy = date.today()
    return _mes_data(puuid, paciente_id, year or hoy.year, month or hoy.month, cur)


@app.get("/pro/pacientes/{paciente_id}/dia", summary="Detalle de un día concreto del paciente")
def pro_paciente_dia(
    paciente_id: int,
    fecha: str,
    ctx = Depends(get_profesional_actual),
    db  = Depends(get_db),
):
    cur = db.cursor()
    _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)
    cur.execute("SELECT * FROM usuarios_app WHERE id = %s AND activo = TRUE", (paciente_id,))
    paciente = cur.fetchone()
    if not paciente or not paciente["puuid"]:
        return {"fecha": fecha, "horas": 0, "partidas": 0, "limite": 0, "porcentaje": 0, "matches": []}
    return _dia_data(paciente["puuid"], paciente_id, fecha, cur)


@app.get("/pro/pacientes/{paciente_id}/historial", summary="Historial de partidas del paciente visto por el profesional")
def pro_paciente_historial(
    paciente_id:  int,
    dias:         int          = 30,
    limit:        int          = 50,
    offset:       int          = 0,
    fecha_inicio: Optional[str] = None,
    fecha_fin:    Optional[str] = None,
    ctx = Depends(get_profesional_actual),
    db  = Depends(get_db),
):
    cur = db.cursor()
    _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)
    cur.execute("SELECT * FROM usuarios_app WHERE id = %s AND activo = TRUE", (paciente_id,))
    paciente = cur.fetchone()
    if not paciente:
        raise HTTPException(404, detail="Paciente no encontrado")
    return historial(
        dias=dias, limit=limit, offset=offset,
        fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
        usuario=dict(paciente), db=db,
    )


@app.get("/pro/pacientes/{paciente_id}/analisis", summary="Análisis del paciente visto por el profesional")
def pro_paciente_analisis(
    paciente_id:  int,
    dias:         int          = 30,
    fecha_inicio: Optional[str] = None,
    fecha_fin_p:  Optional[str] = None,
    ctx = Depends(get_profesional_actual),
    db  = Depends(get_db),
):
    cur = db.cursor()
    _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)
    cur.execute("SELECT * FROM usuarios_app WHERE id = %s AND activo = TRUE", (paciente_id,))
    paciente = cur.fetchone()
    if not paciente:
        raise HTTPException(404, detail="Paciente no encontrado")
    return stats_analisis(
        dias=dias, fecha_inicio=fecha_inicio, fecha_fin_p=fecha_fin_p,
        usuario=dict(paciente), db=db,
    )


@app.get("/pro/pacientes/{paciente_id}/rank-historia", summary="Historial de LP del paciente")
def pro_paciente_rank_historia(
    paciente_id: int,
    dias:        int = 60,
    ctx = Depends(get_profesional_actual),
    db  = Depends(get_db),
):
    cur = db.cursor()
    _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)
    cur.execute("SELECT * FROM usuarios_app WHERE id = %s AND activo = TRUE", (paciente_id,))
    paciente = cur.fetchone()
    if not paciente:
        raise HTTPException(404, detail="Paciente no encontrado")
    return rank_historia(dias=dias, usuario=dict(paciente), db=db)


@app.get("/pro/pacientes/{paciente_id}/dashboard", summary="Dashboard del paciente visto por el profesional")
def pro_paciente_dashboard(
    paciente_id: int,
    ctx = Depends(get_profesional_actual),
    db  = Depends(get_db),
):
    cur = db.cursor()
    rel = _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)

    cur.execute("SELECT * FROM usuarios_app WHERE id = %s AND activo = TRUE", (paciente_id,))
    paciente = cur.fetchone()
    if not paciente:
        raise HTTPException(404, detail="Paciente no encontrado")

    from datetime import date, timedelta
    puuid = paciente["puuid"]
    uid   = paciente["id"]

    if not puuid:
        return {"sincronizado": False, "nombre": paciente["riot_game_name"]}

    lunes = date.today() - timedelta(days=date.today().weekday())

    cur.execute("""
        SELECT
            COALESCE(ROUND(SUM(duracion_min)::numeric/60,2),0) AS horas_hoy,
            COALESCE(COUNT(*),0) AS partidas_hoy,
            COALESCE(SUM(CASE WHEN rendicion AND resultado='Derrota' THEN 1 ELSE 0 END),0) AS rendiciones_hoy,
            COALESCE(SUM(CASE WHEN NOT apto_para_progresion THEN 1 ELSE 0 END),0) AS afks_hoy
        FROM partidas WHERE puuid = %s AND fecha = CURRENT_DATE
    """, (puuid,))
    hoy = dict(cur.fetchone())

    cur.execute("""
        SELECT COALESCE(ROUND(SUM(duracion_min)::numeric/60,2),0) AS horas
        FROM partidas WHERE puuid = %s AND fecha >= %s AND fecha <= CURRENT_DATE
    """, (puuid, lunes))
    horas_semana = float(cur.fetchone()["horas"])

    cur.execute("""
        SELECT limite_horas_dia, limite_horas_semana FROM objetivos
        WHERE usuario_id = %s AND activo = TRUE
    """, (uid,))
    obj = dict(cur.fetchone() or {})
    limite_d = float(obj.get("limite_horas_dia") or 0)
    limite_s = float(obj.get("limite_horas_semana") or 0)

    cur.execute("""
        SELECT fecha, ROUND(SUM(duracion_min)::numeric/60,2) AS horas, COUNT(*) AS partidas
        FROM partidas WHERE puuid = %s AND fecha >= %s AND fecha <= CURRENT_DATE
        GROUP BY fecha ORDER BY fecha
    """, (puuid, lunes))
    dias_semana = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT racha_dias_cumplidos, racha_maxima_historica FROM progreso_diario
        WHERE usuario_id = %s ORDER BY fecha DESC LIMIT 1
    """, (uid,))
    racha_row = cur.fetchone()
    racha     = int(racha_row["racha_dias_cumplidos"] if racha_row else 0)

    cur.execute("""
        SELECT campeon, modo, resultado, kda, duracion_min, rendicion,
               apto_para_progresion, fecha, hora_inicio
        FROM partidas WHERE puuid = %s ORDER BY fecha DESC, hora_inicio DESC LIMIT 10
    """, (puuid,))
    ultimas = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT tier, division, lp, victorias, derrotas
        FROM ranked_info WHERE puuid = %s AND queue_type = 'RANKED_SOLO_5x5'
    """, (puuid,))
    ranked = dict(cur.fetchone() or {})

    horas_hoy = float(hoy["horas_hoy"])
    pct_dia   = round(horas_hoy / limite_d * 100, 1) if limite_d > 0 else 0

    return {
        "sincronizado":   True,
        "nombre":         paciente["riot_game_name"],
        "tag":            paciente["riot_tag_line"],
        "nombre_real":    paciente["nombre_real"] or "",
        "apellidos_real": paciente["apellidos_real"] or "",
        "nombre_display": f"{paciente['nombre_real']} {paciente['apellidos_real']}".strip() if paciente["nombre_real"] else paciente["riot_game_name"],
        "email":          paciente["email"],
        "hoy": {
            "horas":       horas_hoy,
            "partidas":    int(hoy["partidas_hoy"]),
            "rendiciones": int(hoy["rendiciones_hoy"]),
            "afks":        int(hoy["afks_hoy"]),
        },
        "semana": {
            "horas":      horas_semana,
            "porcentaje": round(horas_semana / limite_s * 100, 1) if limite_s else 0,
            "dias":       dias_semana,
        },
        "objetivo": {
            "limite_dia":     limite_d,
            "limite_semana":  limite_s,
            "porcentaje_dia": pct_dia,
        },
        "racha":              racha,
        "ranked":             ranked,
        "estado_tratamiento": rel["estado_tratamiento"],
        "ultimas_partidas": [
            {
                "campeon":          r["campeon"],
                "modo":             r["modo"],
                "resultado":        r["resultado"],
                "kda":              float(r["kda"] or 0),
                "duracion_min":     float(r["duracion_min"]),
                "rendicion_negativa": r["rendicion"] and r["resultado"] == "Derrota",
                "rendicion_positiva": r["rendicion"] and r["resultado"] == "Victoria",
                "afk":              not r["apto_para_progresion"],
                "fecha":            str(r["fecha"]),
            }
            for r in ultimas
        ],
    }


@app.patch("/pro/pacientes/{paciente_id}/estado", summary="Actualizar estado de tratamiento del paciente")
def pro_actualizar_estado(
    paciente_id: int,
    body: EstadoRequest,
    ctx = Depends(get_profesional_actual),
    db  = Depends(get_db),
):
    cur = db.cursor()
    _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)
    es_alta = body.estado == "alta"
    cur.execute("""
        UPDATE relaciones_pro_paciente
        SET estado_tratamiento = %s,
            fecha_alta = CASE WHEN %s THEN NOW() ELSE NULL END,
            activo = %s
        WHERE profesional_id = %s AND paciente_id = %s
    """, (
        body.estado,
        es_alta,
        not es_alta,
        ctx["profesional"]["id"],
        paciente_id,
    ))
    db.commit()
    return {"ok": True, "estado": body.estado}


# ── Notas del profesional sobre el paciente ────────────────────

@app.get("/pro/pacientes/{paciente_id}/notas", summary="Listar notas del profesional sobre un paciente")
def pro_notas_list(
    paciente_id: int,
    ctx = Depends(get_profesional_actual),
    db  = Depends(get_db),
):
    cur = db.cursor()
    rel = _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)
    cur.execute("""
        SELECT id, contenido, categoria, creada_en, editada_en
        FROM notas_profesional
        WHERE relacion_id = %s
        ORDER BY creada_en DESC
    """, (rel["id"],))
    return {
        "notas": [
            {
                "id":        r["id"],
                "contenido": r["contenido"],
                "categoria": r["categoria"] or "observacion",
                "creada_en": r["creada_en"].isoformat() if r["creada_en"] else None,
                "editada_en":r["editada_en"].isoformat() if r["editada_en"] else None,
            }
            for r in cur.fetchall()
        ]
    }


@app.post("/pro/pacientes/{paciente_id}/notas", summary="Añadir nota sobre un paciente")
def pro_notas_crear(
    paciente_id: int,
    body: NotaRequest,
    ctx = Depends(get_profesional_actual),
    db  = Depends(get_db),
):
    cur = db.cursor()
    rel = _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)
    cur.execute(
        "INSERT INTO notas_profesional (relacion_id, contenido, categoria) VALUES (%s, %s, %s) RETURNING id, creada_en",
        (rel["id"], body.contenido.strip(), body.categoria)
    )
    row = cur.fetchone()
    db.commit()
    return {"id": row["id"], "creada_en": row["creada_en"].isoformat()}


@app.put("/pro/pacientes/{paciente_id}/notas/{nota_id}", summary="Editar nota")
def pro_notas_editar(
    paciente_id: int,
    nota_id: int,
    body: NotaRequest,
    ctx = Depends(get_profesional_actual),
    db  = Depends(get_db),
):
    cur = db.cursor()
    rel = _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)
    cur.execute("""
        UPDATE notas_profesional SET contenido = %s, categoria = %s, editada_en = NOW()
        WHERE id = %s AND relacion_id = %s
    """, (body.contenido.strip(), body.categoria, nota_id, rel["id"]))
    if cur.rowcount == 0:
        raise HTTPException(404, detail="Nota no encontrada")
    db.commit()
    return {"ok": True}


@app.delete("/pro/pacientes/{paciente_id}/notas/{nota_id}", summary="Eliminar nota")
def pro_notas_borrar(
    paciente_id: int,
    nota_id: int,
    ctx = Depends(get_profesional_actual),
    db  = Depends(get_db),
):
    cur = db.cursor()
    rel = _verificar_acceso_paciente(ctx["profesional"]["id"], paciente_id, cur)
    cur.execute(
        "DELETE FROM notas_profesional WHERE id = %s AND relacion_id = %s",
        (nota_id, rel["id"])
    )
    db.commit()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ══════════════════════════════════════════════════════════════
 
@app.get("/health", include_in_schema=False)
def health():
    db_status = "ok"
    try:
        pool = _get_pool()
        conn = pool.getconn()
        conn.cursor().execute("SELECT 1")
        pool.putconn(conn)
    except Exception as e:
        db_status = f"error: {e}"

    ok = db_status == "ok"
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status":    "ok" if ok else "degraded",
            "database":  db_status,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )