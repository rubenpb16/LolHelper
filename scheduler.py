"""
═══════════════════════════════════════════════════════════════
  MÓDULO 5 — SCHEDULER
  LolHelper · scheduler.py
═══════════════════════════════════════════════════════════════

  Orquesta todo el sistema: extrae partidas, calcula alertas
  y envía emails de forma automática cada 6 horas.

  Flujo de cada ciclo:
    1. Sync de partidas (extractor.py)
    2. Motor de alertas (alertas.py)
    3. Esperar hasta el próximo ciclo

  CÓMO USAR:
    python scheduler.py              → arranca el loop infinito
    python scheduler.py --ahora      → ejecuta un ciclo ahora y sale
    python scheduler.py --solo-alertas → solo alertas, sin sync de API

  CONFIGURAR ARRANQUE AUTOMÁTICO EN WINDOWS:
    Ver instrucciones al final de este archivo.
═══════════════════════════════════════════════════════════════
"""

import sys
import time
from datetime import datetime, timedelta

import alertas       as modulo_alertas
import email_service as modulo_email
from extractor import sync_todos
from lol_logger import get_logger

# ══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════

# Frecuencia del ciclo automático.
# 5 minutos permite detectar partidas recién terminadas antes de que el
# usuario empiece la siguiente, que es cuando la alerta tiene sentido real.
# La Riot Match V5 API tarda 2-5 min en reflejar una partida terminada,
# así que ciclos más cortos que 5 min no aportarían más información.
INTERVALO_MINUTOS = 5

log = get_logger("scheduler")


# ══════════════════════════════════════════════════════════════
#  CICLO PRINCIPAL
# ══════════════════════════════════════════════════════════════

def ejecutar_ciclo():
    """
    Un ciclo completo:
      1. Sync de todas las partidas nuevas desde la API de Riot
      2. Procesar alertas y enviar emails
    """
    inicio = datetime.now()
    log.info("═" * 55)
    log.info("  🚀 Inicio de ciclo")
    log.info("═" * 55)

    errores = []

    # ── 1. Extracción de partidas ─────────────────────────────
    try:
        log.info("▶ Paso 1/2: Extracción de partidas...")
        partidas_nuevas = sync_todos()
        log.info(f"  ✅ Extracción completada — {partidas_nuevas} partidas nuevas")
    except Exception as e:
        log.error(f"  ❌ Error en extracción: {e}")
        errores.append(f"Extracción: {e}")

    # ── 2. Motor de alertas ───────────────────────────────────
    try:
        log.info("▶ Paso 2/2: Procesando alertas...")
        resultados = modulo_alertas.procesar_alertas_todos(modulo_email)
        total_alertas = sum(len(r.get("alertas_enviadas", [])) for r in (resultados or []))
        log.info(f"  ✅ Alertas procesadas — {total_alertas} emails enviados")
    except Exception as e:
        log.error(f"  ❌ Error en alertas: {e}")
        errores.append(f"Alertas: {e}")

    # ── Resumen del ciclo ─────────────────────────────────────
    duracion = round((datetime.now() - inicio).total_seconds() / 60, 1)
    if errores:
        log.warning(f"  ⚠️  Ciclo completado con errores en {duracion}min: {'; '.join(errores)}")
    else:
        log.info(f"  ✅ Ciclo completado en {duracion}min sin errores")


def ejecutar_solo_alertas():
    """Procesa alertas sin llamar a la API de Riot. Útil para pruebas."""
    log.info("▶ Procesando solo alertas (sin sync de API)...")
    try:
        resultados = modulo_alertas.procesar_alertas_todos(modulo_email)
        total = sum(len(r.get("alertas_enviadas", [])) for r in (resultados or []))
        log.info(f"  ✅ {total} emails enviados")
    except Exception as e:
        log.error(f"  ❌ Error: {e}")


# ══════════════════════════════════════════════════════════════
#  SCHEDULER LOOP
# ══════════════════════════════════════════════════════════════

def run_scheduler():
    """Loop infinito que ejecuta un ciclo cada INTERVALO_MINUTOS minutos."""
    log.info("╔══════════════════════════════════════════════════╗")
    log.info("║  LolHelper — Scheduler activo                   ║")
    log.info(f"║  Ciclos cada {INTERVALO_MINUTOS} min | Ctrl+C para parar            ║")
    log.info("╚══════════════════════════════════════════════════╝")

    while True:
        try:
            ejecutar_ciclo()
        except KeyboardInterrupt:
            log.info("Scheduler detenido manualmente")
            break
        except Exception as e:
            log.error(f"Error inesperado en el ciclo: {e}")
            log.info("Reintentando en 2 minutos...")
            time.sleep(120)
            continue

        proxima = datetime.now() + timedelta(minutes=INTERVALO_MINUTOS)
        log.info(f"Proximo ciclo: {proxima.strftime('%Y-%m-%d %H:%M')} (en {INTERVALO_MINUTOS} min)")

        try:
            time.sleep(INTERVALO_MINUTOS * 60)
        except KeyboardInterrupt:
            log.info("Scheduler detenido manualmente")
            break


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":

    if "--ahora" in sys.argv:
        # Ejecuta un ciclo completo ahora y sale — útil para probar
        log.info("Modo --ahora: ejecutando un ciclo y saliendo")
        ejecutar_ciclo()

    elif "--solo-alertas" in sys.argv:
        # Solo alertas, sin tocar la API de Riot
        ejecutar_solo_alertas()

    else:
        # Loop normal
        run_scheduler()


# ══════════════════════════════════════════════════════════════
#  INSTRUCCIONES: ARRANQUE AUTOMÁTICO EN WINDOWS
# ══════════════════════════════════════════════════════════════
"""
Para que el scheduler arranque automáticamente al iniciar Windows
sin necesidad de abrir una terminal:

OPCIÓN A — Programador de Tareas de Windows (recomendada):
──────────────────────────────────────────────────────────
1. Abre "Programador de Tareas" (busca en el menú inicio)
2. Crear tarea básica → dale un nombre: "LolHelper"
3. Desencadenador: "Al iniciar el equipo"
4. Acción: "Iniciar un programa"
5. Programa: C:\\Users\\ruben\\AppData\\Local\\Programs\\Python\\Python313\\python.exe
6. Argumentos: C:\\Users\\ruben\\Desktop\\LolHelp\\scheduler.py
7. Iniciar en: C:\\Users\\ruben\\Desktop\\LolHelp
8. En "Condiciones": desmarca "Iniciar solo si el equipo usa corriente alterna"
9. En "Configuración": marca "Ejecutar lo antes posible si se perdió el inicio"

OPCIÓN B — Script .bat para arrancar manualmente:
──────────────────────────────────────────────────
Crea un fichero "iniciar_tracker.bat" en tu escritorio:

    @echo off
    cd /d C:\\Users\\ruben\\Desktop\\LolHelp
    python scheduler.py
    pause

Doble clic para arrancar. La ventana muestra el log en tiempo real.

LOGS:
─────
El fichero lol_tracker.log en la carpeta del proyecto guarda
el historial completo de todos los ciclos y errores.
Para verlo en tiempo real en Windows PowerShell:
    Get-Content lol_tracker.log -Wait
"""