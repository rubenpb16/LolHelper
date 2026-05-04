"""
Test de email — simula que un usuario superó su límite
y verifica que el email llega correctamente a Resend.

Ejecuta: python test_email.py
"""
import sys
sys.path.insert(0, r"C:\Users\ruben\Desktop\LolHelp")  # ajusta si es necesario

import email_service

print("=" * 55)
print("  TEST DE EMAIL — LolHelper")
print("=" * 55)

# ── Datos simulados de una sesión de juego ────────────────
partidas_simuladas = [
    {"campeon": "Jinx",   "modo": "Ranked Solo", "resultado": "Derrota",
     "kda": 1.5, "duracion_min": 28.3, "rendicion": True,
     "rendicion_temprana": False, "apto_para_progresion": True},
    {"campeon": "Jinx",   "modo": "Ranked Solo", "resultado": "Derrota",
     "kda": 0.8, "duracion_min": 22.1, "rendicion": True,
     "rendicion_temprana": False, "apto_para_progresion": True},
    {"campeon": "Caitlyn","modo": "Ranked Solo", "resultado": "Victoria",
     "kda": 4.2, "duracion_min": 34.7, "rendicion": False,
     "rendicion_temprana": False, "apto_para_progresion": True},
]

resumen_semana_simulado = [
    {"fecha": __import__("datetime").date(2026, 4, 28), "horas": 1.2, "partidas": 3},
    {"fecha": __import__("datetime").date(2026, 4, 29), "horas": 2.8, "partidas": 7},
    {"fecha": __import__("datetime").date(2026, 4, 30), "horas": 2.17, "partidas": 3},
]

EMAIL_DESTINO = "Lewisbarrado@gmail.com"  # ← CAMBIA ESTO

print(f"\nDestino: {EMAIL_DESTINO}")
print("\n[1/3] Probando email de ALERTA UMBRAL (80%)...")
asunto, html = email_service.construir_email_umbral(
    nombre="zRamBoXx",
    horas_jugadas=1.62,
    limite=2.0,
    porcentaje=81.0,
    umbral=80,
    partidas=partidas_simuladas,
    racha=3,
    rendiciones=2,
    afks=0,
)
ok, err = email_service.enviar(EMAIL_DESTINO, asunto, html)
print(f"  {'✅ Enviado' if ok else '❌ Error: ' + str(err)}")

print("\n[2/3] Probando email de LÍMITE SUPERADO...")
asunto, html = email_service.construir_email_limite_superado(
    nombre="fakeZLynKs",
    horas_jugadas=2.8,
    limite=2.0,
    exceso=0.8,
    partidas=partidas_simuladas,
    racha=0,
    rendiciones=2,
    afks=1,
    campeon="Jinx",
)
ok, err = email_service.enviar(EMAIL_DESTINO, asunto, html)
print(f"  {'✅ Enviado' if ok else '❌ Error: ' + str(err)}")

print("\n[3/3] Probando email de RESUMEN NOCTURNO...")
asunto, html = email_service.construir_email_resumen_noche(
    nombre="CapiLewis",
    horas_hoy=0.58,
    horas_semana=3.71,
    limite_dia=2.0,
    limite_semana=10.0,
    partidas=partidas_simuladas[:1],
    resumen_semana=resumen_semana_simulado,
    racha=1,
    racha_maxima=5,
    objetivo_cumplido=True,
)
ok, err = email_service.enviar(EMAIL_DESTINO, asunto, html)
print(f"  {'✅ Enviado' if ok else '❌ Error: ' + str(err)}")

print("\n" + "=" * 55)
print("  Si ves ✅ en los tres, el sistema de email funciona.")
print("  Revisa tu bandeja de entrada (y spam).")
print("=" * 55)