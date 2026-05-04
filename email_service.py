"""
═══════════════════════════════════════════════════════════════
  MÓDULO 4 — SERVICIO DE EMAIL
  LolHelper · email_service.py
═══════════════════════════════════════════════════════════════

  Construye y envía todos los emails de la aplicación usando
  la API de Resend (resend.com — gratuito hasta 3000/mes).

  Tipos de email:
    · alerta_umbral        → al llegar al X% del límite
    · alerta_limite        → al superar el límite diario
    · resumen_noche        → resumen del día (opcional)
    · resumen_semana       → resumen semanal (los lunes)

  El tono de todos los emails es empático y de apoyo,
  nunca punitivo. El objetivo es concienciar, no juzgar.
═══════════════════════════════════════════════════════════════
"""

import resend
from datetime import date
from config import RESEND_API_KEY, FROM_EMAIL

# ══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════

APP_NAME = "LolHelper"

resend.api_key = RESEND_API_KEY


# ══════════════════════════════════════════════════════════════
#  UTILIDADES DE FORMATO
# ══════════════════════════════════════════════════════════════

def fmt_horas(horas):
    """Convierte horas decimales a formato legible. Ej: 1.75 → '1h 45min'"""
    h = int(horas)
    m = int((horas - h) * 60)
    if h == 0:
        return f"{m} min"
    if m == 0:
        return f"{h}h"
    return f"{h}h {m}min"


def barra_progreso(porcentaje, ancho=20):
    """Genera una barra de progreso en texto para el email."""
    pct  = min(porcentaje, 100)
    fill = int(pct / 100 * ancho)
    empty = ancho - fill
    color = "#e74c3c" if pct >= 100 else "#f39c12" if pct >= 75 else "#2ecc71"
    return color, fill, empty


def emoji_resultado(resultado):
    return "✅" if resultado == "Victoria" else "❌"


def mensaje_motivacional(horas_hoy, limite, racha, rendiciones, afks):
    """
    Genera un mensaje personalizado según el contexto del jugador.
    El tono siempre es empático, nunca acusatorio.
    """
    exceso = horas_hoy - limite if limite > 0 else 0

    # Detectar señales de juego compulsivo / frustrado
    hay_frustacion = rendiciones >= 2 or afks >= 1
    mucho_exceso   = exceso > 1.0
    racha_buena    = racha >= 3

    if hay_frustacion and mucho_exceso:
        return (
            "Hemos notado que hoy ha sido una sesión dura — varias partidas "
            "terminaron antes de tiempo. Eso suele pasar cuando el cansancio "
            "se acumula. Tu mente y tu bienestar merecen un descanso. "
            "Mañana juegas mejor descansado."
        )
    elif hay_frustacion:
        return (
            "Parece que hoy no ha sido tu mejor día en la Grieta. "
            "Está bien, todos los tenemos. Lo importante es reconocer cuándo "
            "el juego deja de ser disfrute. Un respiro ahora puede hacer "
            "que vuelvas con mucha más energía."
        )
    elif mucho_exceso:
        return (
            "Llevas bastante tiempo jugando hoy. No es un juicio — es una "
            "señal que tú mismo quisiste recibir. Tu yo futuro te agradecerá "
            "haber parado ahora. ¿Qué tal un paseo o una conversación con alguien?"
        )
    elif racha_buena:
        return (
            f"Llevas {racha} días cumpliendo tu objetivo. Eso no es casualidad, "
            "es disciplina real. Hoy has llegado al límite que tú mismo pusiste "
            "— respetarlo hoy hace que la racha siga mañana."
        )
    else:
        return (
            "Has llegado al límite que tú mismo decidiste. Eso significa que "
            "una parte de ti quiere cambiar. Escúchala. Puedes cerrar el juego "
            "sabiendo que has cumplido con tu compromiso contigo mismo."
        )


def mensaje_racha(racha, racha_maxima, objetivo_cumplido):
    """Mensaje sobre la racha, siempre positivo."""
    if racha == 0 and objetivo_cumplido is False:
        return "Hoy no ha sido el día, pero mañana es una nueva oportunidad. 💪"
    elif racha == 0:
        return "¡Empieza tu racha hoy cumpliendo el objetivo!"
    elif racha >= racha_maxima and racha > 1:
        return f"🏆 ¡{racha} días seguidos! ¡Es tu récord personal! Sigue así."
    elif racha >= 7:
        return f"🔥 ¡{racha} días seguidos cumpliendo tu objetivo! Una semana completa. Increíble."
    elif racha >= 3:
        return f"⚡ {racha} días seguidos. La constancia es el verdadero progreso."
    else:
        return f"✨ {racha} día{'s' if racha > 1 else ''} cumpliendo tu objetivo. ¡Buen comienzo!"


# ══════════════════════════════════════════════════════════════
#  PLANTILLA BASE HTML
# ══════════════════════════════════════════════════════════════

def _base_html(titulo, contenido, color_header="#1a1a2e"):
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{titulo}</title>
</head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:30px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:12px;overflow:hidden;
                    box-shadow:0 2px 12px rgba(0,0,0,0.08);">

        <!-- HEADER -->
        <tr>
          <td style="background:{color_header};padding:28px 36px;">
            <p style="margin:0;color:#ffffff;font-size:13px;opacity:0.7;
                      letter-spacing:2px;text-transform:uppercase;">{APP_NAME}</p>
            <h1 style="margin:8px 0 0;color:#ffffff;font-size:24px;
                       font-weight:700;line-height:1.3;">{titulo}</h1>
          </td>
        </tr>

        <!-- CONTENIDO -->
        <tr>
          <td style="padding:32px 36px;">
            {contenido}
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="background:#f8f9fb;padding:20px 36px;
                     border-top:1px solid #eee;">
            <p style="margin:0;font-size:12px;color:#999;line-height:1.6;">
              Este email fue enviado por <strong>{APP_NAME}</strong> porque
              activaste las alertas de tiempo de juego.<br>
              Si quieres cambiar tus preferencias o darte de baja, accede a
              tu perfil en la aplicación.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def _bloque_partidas(partidas):
    """Genera la tabla HTML con el resumen de partidas."""
    if not partidas:
        return "<p style='color:#999;font-size:14px;'>No hay partidas registradas hoy.</p>"

    filas = ""
    for p in partidas:
        color_fila = "#f0faf4" if p["resultado"] == "Victoria" else "#fff5f5"
        color_res  = "#27ae60" if p["resultado"] == "Victoria" else "#e74c3c"
        flags = ""
        if p.get("rendicion") or p.get("rendicion_temprana"):
            flags += " 🏳️"
        if not p.get("apto_para_progresion", True):
            flags += " 💤"
        filas += f"""
        <tr style="background:{color_fila};">
          <td style="padding:8px 12px;font-size:13px;border-bottom:1px solid #eee;">
            <strong>{p['campeon']}</strong>
          </td>
          <td style="padding:8px 12px;font-size:12px;color:#666;border-bottom:1px solid #eee;">
            {p['modo']}
          </td>
          <td style="padding:8px 12px;font-size:12px;font-weight:600;
                     color:{color_res};border-bottom:1px solid #eee;">
            {p['resultado']}{flags}
          </td>
          <td style="padding:8px 12px;font-size:12px;color:#666;border-bottom:1px solid #eee;">
            KDA {p['kda']}
          </td>
          <td style="padding:8px 12px;font-size:12px;color:#666;border-bottom:1px solid #eee;">
            {fmt_horas(float(p['duracion_min']) / 60)}
          </td>
        </tr>"""

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse;border:1px solid #eee;border-radius:8px;
                  overflow:hidden;margin-top:8px;">
      <tr style="background:#f0f4ff;">
        <th style="padding:10px 12px;font-size:12px;color:#666;
                   text-align:left;font-weight:600;">Campeón</th>
        <th style="padding:10px 12px;font-size:12px;color:#666;
                   text-align:left;font-weight:600;">Modo</th>
        <th style="padding:10px 12px;font-size:12px;color:#666;
                   text-align:left;font-weight:600;">Resultado</th>
        <th style="padding:10px 12px;font-size:12px;color:#666;
                   text-align:left;font-weight:600;">KDA</th>
        <th style="padding:10px 12px;font-size:12px;color:#666;
                   text-align:left;font-weight:600;">Duración</th>
      </tr>
      {filas}
    </table>"""


def _stat_card(valor, etiqueta, color="#1a1a2e"):
    return f"""
    <td style="text-align:center;padding:0 12px;">
      <p style="margin:0;font-size:28px;font-weight:700;color:{color};">{valor}</p>
      <p style="margin:4px 0 0;font-size:12px;color:#999;text-transform:uppercase;
                letter-spacing:1px;">{etiqueta}</p>
    </td>"""


# ══════════════════════════════════════════════════════════════
#  CONSTRUCTORES DE EMAIL
# ══════════════════════════════════════════════════════════════

def construir_email_umbral(nombre, horas_jugadas, limite, porcentaje,
                           umbral, partidas, racha, rendiciones, afks):
    """Email de alerta al llegar al X% del límite diario."""

    color_bar, fill, empty = barra_progreso(porcentaje)
    msg = mensaje_motivacional(horas_jugadas, limite, racha, rendiciones, afks)
    tiempo_restante = max(0, limite - horas_jugadas)

    titulo  = f"Llevas el {int(porcentaje)}% de tu límite diario"
    asunto  = f"⚡ {APP_NAME}: llevas {fmt_horas(horas_jugadas)} jugadas hoy"

    contenido = f"""
    <p style="font-size:16px;color:#333;margin:0 0 20px;">
      Hola, <strong>{nombre}</strong> 👋
    </p>

    <p style="font-size:15px;color:#555;line-height:1.7;margin:0 0 24px;">
      Querías que te avisáramos cuando llevaras el <strong>{umbral}%</strong>
      de tu objetivo diario. Ya estás ahí.
    </p>

    <!-- Barra de progreso -->
    <div style="background:#f0f4ff;border-radius:10px;padding:20px 24px;margin:0 0 24px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          {_stat_card(fmt_horas(horas_jugadas), "jugadas hoy", "#e74c3c" if porcentaje >= 80 else "#f39c12")}
          {_stat_card(fmt_horas(limite), "tu límite", "#1a1a2e")}
          {_stat_card(fmt_horas(tiempo_restante), "tiempo restante", "#27ae60")}
        </tr>
      </table>
      <div style="margin-top:20px;">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
        </div>
        <div style="background:#e0e0e0;border-radius:20px;height:12px;overflow:hidden;">
          <div style="background:{color_bar};height:100%;width:{min(porcentaje,100):.0f}%;
                      border-radius:20px;transition:width 0.3s;"></div>
        </div>
        <p style="margin:8px 0 0;text-align:right;font-size:13px;
                  color:{color_bar};font-weight:600;">{porcentaje:.0f}%</p>
      </div>
    </div>

    <!-- Mensaje empático -->
    <div style="border-left:4px solid #6c63ff;padding:16px 20px;
                background:#fafafa;border-radius:0 8px 8px 0;margin:0 0 24px;">
      <p style="margin:0;font-size:15px;color:#444;line-height:1.7;">{msg}</p>
    </div>

    <!-- Partidas de hoy -->
    <h3 style="font-size:14px;color:#333;margin:0 0 8px;font-weight:600;">
      Partidas de hoy
    </h3>
    {_bloque_partidas(partidas)}

    <!-- Racha -->
    <div style="background:#f0faf4;border-radius:8px;padding:16px 20px;margin:24px 0 0;">
      <p style="margin:0;font-size:14px;color:#27ae60;">
        {mensaje_racha(racha, racha, None)}
      </p>
    </div>
    """

    return asunto, _base_html(titulo, contenido, color_header="#6c63ff")


def construir_email_limite_superado(nombre, horas_jugadas, limite, exceso,
                                    partidas, racha, rendiciones, afks, campeon):
    """Email cuando se supera el límite diario."""

    msg    = mensaje_motivacional(horas_jugadas, limite, racha, rendiciones, afks)
    titulo = "Has superado tu límite de hoy"
    asunto = f"🚨 {APP_NAME}: llevas {fmt_horas(horas_jugadas)} — {fmt_horas(exceso)} sobre tu límite"

    notas_comportamiento = ""
    if rendiciones >= 2:
        notas_comportamiento += f"""
        <div style="background:#fff3cd;border-radius:8px;padding:12px 16px;
                    margin:12px 0;border-left:4px solid #f39c12;">
          <p style="margin:0;font-size:13px;color:#856404;">
            🏳️ <strong>{rendiciones} rendiciones hoy.</strong>
            Cuando rendimos mucho, suele ser señal de que el cansancio
            o la frustración están afectando nuestra experiencia.
          </p>
        </div>"""
    if afks >= 1:
        notas_comportamiento += f"""
        <div style="background:#f8d7da;border-radius:8px;padding:12px 16px;
                    margin:12px 0;border-left:4px solid #e74c3c;">
          <p style="margin:0;font-size:13px;color:#721c24;">
            💤 <strong>AFK detectado.</strong>
            A veces necesitamos parar aunque estemos en medio de una partida.
            No hay nada malo en eso — escucha lo que tu cuerpo te pide.
          </p>
        </div>"""

    contenido = f"""
    <p style="font-size:16px;color:#333;margin:0 0 20px;">
      Hola, <strong>{nombre}</strong>
    </p>

    <p style="font-size:15px;color:#555;line-height:1.7;margin:0 0 20px;">
      Hoy has superado el límite de tiempo de juego que tú mismo estableciste.
      Esta alerta existe porque te importa cuidarte — y eso ya es un gran paso.
    </p>

    <!-- Stats principales -->
    <div style="background:#fff5f5;border-radius:10px;padding:20px 24px;
                border:1px solid #f5c6cb;margin:0 0 20px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          {_stat_card(fmt_horas(horas_jugadas), "jugadas hoy", "#e74c3c")}
          {_stat_card(fmt_horas(limite), "tu límite", "#666")}
          {_stat_card("+" + fmt_horas(exceso), "tiempo extra", "#e74c3c")}
        </tr>
      </table>
    </div>

    {notas_comportamiento}

    <!-- Mensaje principal -->
    <div style="border-left:4px solid #e74c3c;padding:16px 20px;
                background:#fafafa;border-radius:0 8px 8px 0;margin:0 0 24px;">
      <p style="margin:0;font-size:15px;color:#444;line-height:1.7;">{msg}</p>
    </div>

    <!-- Partidas de hoy -->
    <h3 style="font-size:14px;color:#333;margin:0 0 8px;font-weight:600;">
      Partidas de hoy
    </h3>
    {_bloque_partidas(partidas)}

    <!-- Racha -->
    <div style="background:#f0f4ff;border-radius:8px;padding:16px 20px;margin:24px 0 0;">
      <p style="margin:0;font-size:14px;color:#6c63ff;">
        Recuerda: un día difícil no borra todo tu progreso.
        {mensaje_racha(racha, racha, False)}
      </p>
    </div>
    """

    return asunto, _base_html(titulo, contenido, color_header="#c0392b")


def construir_email_resumen_noche(nombre, horas_hoy, horas_semana, limite_dia,
                                   limite_semana, partidas, resumen_semana,
                                   racha, racha_maxima, objetivo_cumplido):
    """Resumen nocturno del día."""

    cumplido      = objetivo_cumplido is True
    color_header  = "#27ae60" if cumplido else "#6c63ff"
    titulo        = "Tu resumen de hoy" + (" ✓" if cumplido else "")
    asunto        = f"🌙 {APP_NAME}: resumen de {date.today().strftime('%A %d de %B')}"

    msg_racha  = mensaje_racha(racha, racha_maxima, objetivo_cumplido)
    pct        = round(horas_hoy / limite_dia * 100, 1) if limite_dia > 0 else 0
    color_pct  = "#27ae60" if pct <= 100 else "#e74c3c"

    # Mini gráfico de la semana
    dias_semana_html = ""
    if resumen_semana:
        dias_semana_html = "<div style='margin-top:16px;'>"
        dias_es = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        for r in resumen_semana:
            h = float(r["horas"])
            pct_bar = min(h / (limite_dia or 2) * 100, 100)
            bar_color = "#e74c3c" if pct_bar >= 100 else "#6c63ff"
            dia_nombre = dias_es[r["fecha"].weekday()] if hasattr(r["fecha"], 'weekday') else ""
            dias_semana_html += f"""
            <div style="display:inline-block;width:12%;text-align:center;
                        vertical-align:bottom;margin:0 1%;">
              <div style="background:{bar_color};width:100%;
                          height:{max(int(pct_bar * 0.6), 4)}px;
                          border-radius:4px 4px 0 0;margin-bottom:4px;"></div>
              <p style="margin:0;font-size:11px;color:#999;">{dia_nombre}</p>
              <p style="margin:2px 0 0;font-size:11px;color:#666;font-weight:600;">
                {fmt_horas(h)}
              </p>
            </div>"""
        dias_semana_html += "</div>"

    contenido = f"""
    <p style="font-size:16px;color:#333;margin:0 0 20px;">
      Buenas noches, <strong>{nombre}</strong> 🌙
    </p>

    <!-- Resumen del día -->
    <div style="background:#f8f9fb;border-radius:10px;padding:20px 24px;margin:0 0 20px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          {_stat_card(fmt_horas(horas_hoy), "jugadas hoy", color_pct)}
          {_stat_card(fmt_horas(horas_semana), "esta semana", "#6c63ff")}
          {_stat_card(f"{racha}d", "racha actual", "#27ae60")}
        </tr>
      </table>
      {"<p style='margin:16px 0 0;font-size:13px;color:#27ae60;font-weight:600;text-align:center;'>" + "✅ Objetivo diario cumplido" + "</p>" if cumplido else "<p style='margin:16px 0 0;font-size:13px;color:#e74c3c;font-weight:600;text-align:center;'>⚠️ Límite diario superado (" + str(pct) + "%)</p>"}
    </div>

    <!-- Gráfico semanal -->
    {"<h3 style='font-size:14px;color:#333;margin:0 0 4px;font-weight:600;'>Tu semana hasta hoy</h3>" + dias_semana_html if dias_semana_html else ""}

    <!-- Partidas -->
    <h3 style="font-size:14px;color:#333;margin:24px 0 8px;font-weight:600;">
      Partidas de hoy ({len(partidas)})
    </h3>
    {_bloque_partidas(partidas)}

    <!-- Racha y motivación -->
    <div style="background:#f0faf4;border-radius:8px;padding:16px 20px;margin:24px 0 0;">
      <p style="margin:0;font-size:14px;color:#27ae60;">{msg_racha}</p>
      {"<p style='margin:8px 0 0;font-size:13px;color:#999;'>🏆 Tu récord personal: " + str(racha_maxima) + " días</p>" if racha_maxima > 0 else ""}
    </div>
    """

    return asunto, _base_html(titulo, contenido, color_header=color_header)


def construir_email_resumen_semana(nombre, resumen, total_horas,
                                    limite_semana, racha, racha_maxima, objetivo_cumplido):
    """Resumen semanal enviado los lunes."""

    cumplido     = objetivo_cumplido is True
    color_header = "#27ae60" if cumplido else "#1a1a2e"
    titulo       = "Tu resumen de la semana"
    asunto       = f"📊 {APP_NAME}: resumen semanal — {fmt_horas(total_horas)} jugadas"

    pct_semana  = round(total_horas / limite_semana * 100, 1) if limite_semana > 0 else 0
    dias_con_juego = len(resumen)
    dias_es        = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

    filas_semana = ""
    for r in resumen:
        h        = float(r["horas"])
        sobre    = h > float(limite_semana / 7) if limite_semana else False
        color_h  = "#e74c3c" if sobre else "#333"
        dia_nombre = dias_es[r["fecha"].weekday()] if hasattr(r["fecha"], 'weekday') else str(r["fecha"])
        filas_semana += f"""
        <tr>
          <td style="padding:10px 12px;font-size:13px;color:#666;
                     border-bottom:1px solid #eee;">{dia_nombre} {r['fecha']}</td>
          <td style="padding:10px 12px;font-size:13px;font-weight:600;
                     color:{color_h};border-bottom:1px solid #eee;">{fmt_horas(h)}</td>
          <td style="padding:10px 12px;font-size:13px;color:#999;
                     border-bottom:1px solid #eee;">{r['partidas']} partidas</td>
        </tr>"""

    msg_objetivo = (
        f"✅ ¡Has cumplido tu objetivo semanal! Llevabas como máximo {fmt_horas(limite_semana)} y has jugado {fmt_horas(total_horas)}."
        if cumplido else
        f"Esta semana has jugado {fmt_horas(total_horas - limite_semana)} más de tu objetivo de {fmt_horas(limite_semana)}. La próxima semana puedes hacerlo mejor."
    ) if limite_semana > 0 else f"Has jugado {fmt_horas(total_horas)} esta semana."

    contenido = f"""
    <p style="font-size:16px;color:#333;margin:0 0 20px;">
      Hola, <strong>{nombre}</strong> 👋
    </p>

    <p style="font-size:15px;color:#555;line-height:1.7;margin:0 0 20px;">
      Aquí tienes tu resumen de la semana pasada. La reflexión es el primer
      paso para el cambio.
    </p>

    <!-- Stats semana -->
    <div style="background:#f8f9fb;border-radius:10px;padding:20px 24px;margin:0 0 20px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          {_stat_card(fmt_horas(total_horas), "total semana",
                      "#27ae60" if cumplido else "#e74c3c")}
          {_stat_card(f"{dias_con_juego}/7", "días jugados", "#6c63ff")}
          {_stat_card(f"{racha}d", "racha actual", "#27ae60")}
        </tr>
      </table>
    </div>

    <!-- Mensaje objetivo -->
    <div style="border-left:4px solid {'#27ae60' if cumplido else '#e74c3c'};
                padding:16px 20px;background:#fafafa;
                border-radius:0 8px 8px 0;margin:0 0 24px;">
      <p style="margin:0;font-size:15px;color:#444;line-height:1.7;">{msg_objetivo}</p>
    </div>

    <!-- Tabla por días -->
    <h3 style="font-size:14px;color:#333;margin:0 0 8px;font-weight:600;">
      Desglose por día
    </h3>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse;border:1px solid #eee;border-radius:8px;
                  overflow:hidden;">
      <tr style="background:#f0f4ff;">
        <th style="padding:10px 12px;font-size:12px;color:#666;
                   text-align:left;font-weight:600;">Día</th>
        <th style="padding:10px 12px;font-size:12px;color:#666;
                   text-align:left;font-weight:600;">Tiempo</th>
        <th style="padding:10px 12px;font-size:12px;color:#666;
                   text-align:left;font-weight:600;">Partidas</th>
      </tr>
      {filas_semana}
    </table>

    <!-- Racha -->
    <div style="background:#f0faf4;border-radius:8px;padding:16px 20px;margin:24px 0 0;">
      <p style="margin:0;font-size:14px;color:#27ae60;">
        {mensaje_racha(racha, racha_maxima, objetivo_cumplido)}
      </p>
      <p style="margin:8px 0 0;font-size:13px;color:#555;line-height:1.6;">
        Esta nueva semana es una oportunidad para mejorar. Tú decidiste usar
        esta app porque quieres un cambio. Eso ya es valioso.
      </p>
    </div>
    """

    return asunto, _base_html(titulo, contenido, color_header=color_header)


# ══════════════════════════════════════════════════════════════
#  ENVÍO
# ══════════════════════════════════════════════════════════════

def enviar(to_email, asunto, html):
    """
    Envía un email usando la API de Resend.
    Devuelve (True, None) si ok, (False, mensaje_error) si falla.
    """
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to":   [to_email],
            "subject": asunto,
            "html": html,
        })
        return True, None
    except Exception as e:
        return False, str(e)