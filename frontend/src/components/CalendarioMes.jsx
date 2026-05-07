import { useState, useEffect, useCallback } from 'react'

const DIAS_SEMANA = ['L', 'M', 'X', 'J', 'V', 'S', 'D']
const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

// Colores para el tema oscuro (paciente) y claro (profesional)
const ESTADO_DARK = {
  vacio:    { bg: 'transparent',              border: 'rgba(255,255,255,0.06)', text: 'var(--muted)' },
  ok:       { bg: 'rgba(52,211,153,0.15)',    border: 'rgba(52,211,153,0.3)',   text: 'var(--success)' },
  warning:  { bg: 'rgba(251,191,36,0.15)',    border: 'rgba(251,191,36,0.3)',   text: 'var(--warning)' },
  excedido: { bg: 'rgba(248,113,113,0.15)',   border: 'rgba(248,113,113,0.3)',  text: 'var(--danger)' },
}
const ESTADO_LIGHT = {
  vacio:    { bg: '#f8fafc',  border: '#e2e8f0', text: '#94a3b8' },
  ok:       { bg: '#dcfce7',  border: '#86efac', text: '#059669' },
  warning:  { bg: '#fef9c3',  border: '#fde047', text: '#b45309' },
  excedido: { bg: '#fee2e2',  border: '#fca5a5', text: '#dc2626' },
}

function fmt(horas) {
  if (!horas) return '0min'
  const h = Math.floor(horas), m = Math.round((horas - h) * 60)
  if (h === 0) return `${m}min`
  if (m === 0) return `${h}h`
  return `${h}h ${m}min`
}

function fmtMin(min) { return fmt(min / 60) }

/**
 * CalendarioMes — componente reutilizable para paciente y profesional.
 *
 * Props:
 *   fetchMes(year, month)  → Promise → { year, month, limite_dia, dias[] }
 *   fetchDia(fecha)        → Promise → { fecha, horas, partidas, limite, matches[] }
 *   dark                   → boolean (tema oscuro para paciente, claro para profesional)
 */
export default function CalendarioMes({ fetchMes, fetchDia, dark = true }) {
  const hoy    = new Date()
  const [year,  setYear]  = useState(hoy.getFullYear())
  const [month, setMonth] = useState(hoy.getMonth() + 1)  // 1-12
  const [mesData,    setMesData]    = useState(null)
  const [diaData,    setDiaData]    = useState(null)
  const [selectedDay,setSelectedDay]= useState(null)
  const [loadingMes, setLoadingMes] = useState(true)
  const [loadingDia, setLoadingDia] = useState(false)

  const E = dark ? ESTADO_DARK : ESTADO_LIGHT

  const loadMes = useCallback(async (y, m) => {
    setLoadingMes(true)
    setDiaData(null); setSelectedDay(null)
    try {
      const r = await fetchMes(y, m)
      setMesData(r.data)
    } catch {}
    setLoadingMes(false)
  }, [fetchMes])

  useEffect(() => { loadMes(year, month) }, [year, month, loadMes])

  async function selectDay(fecha) {
    if (selectedDay === fecha) { setSelectedDay(null); setDiaData(null); return }
    setSelectedDay(fecha)
    setLoadingDia(true)
    try {
      const r = await fetchDia(fecha)
      setDiaData(r.data)
    } catch {}
    setLoadingDia(false)
  }

  function prevMes() {
    if (month === 1) { setYear(y => y - 1); setMonth(12) }
    else setMonth(m => m - 1)
  }
  function nextMes() {
    const now = new Date()
    if (year > now.getFullYear() || (year === now.getFullYear() && month >= now.getMonth() + 1)) return
    if (month === 12) { setYear(y => y + 1); setMonth(1) }
    else setMonth(m => m + 1)
  }

  // Construir la cuadrícula del mes
  const diasGrid = () => {
    if (!mesData) return []
    const primerDia = new Date(year, month - 1, 1)
    // lunes=0 ... domingo=6
    const offsetInicio = (primerDia.getDay() + 6) % 7
    const grid = Array(offsetInicio).fill(null)
    mesData.dias.forEach(d => grid.push(d))
    while (grid.length % 7 !== 0) grid.push(null)
    return grid
  }

  const hoyStr  = hoy.toISOString().slice(0, 10)
  const esHoy   = (fecha) => fecha === hoyStr
  const esFuturo= (fecha) => fecha > hoyStr

  const s = dark ? darkS : lightS

  return (
    <div style={s.wrap}>
      {/* ── Cabecera del mes ── */}
      <div style={s.header}>
        <button style={s.navBtn} onClick={prevMes}>‹</button>
        <span style={s.mesLabel}>{MESES[month - 1]} {year}</span>
        <button
          style={{ ...s.navBtn, opacity: (year === hoy.getFullYear() && month >= hoy.getMonth() + 1) ? 0.3 : 1 }}
          onClick={nextMes}
        >›</button>
      </div>

      {loadingMes ? (
        <div style={s.loading}>Cargando...</div>
      ) : (
        <>
          {/* ── Grid ── */}
          <div style={s.grid}>
            {DIAS_SEMANA.map(d => (
              <div key={d} style={s.diaSemana}>{d}</div>
            ))}
            {diasGrid().map((dia, i) => {
              if (!dia) return <div key={`empty-${i}`} />
              const estado = esFuturo(dia.fecha) ? 'vacio' : (dia.estado || 'vacio')
              const est    = E[estado] || E.vacio
              const sel    = selectedDay === dia.fecha
              return (
                <div key={dia.fecha}
                  style={{
                    ...s.diaCell,
                    background:   sel ? (dark ? 'var(--accent)' : '#2563eb') : est.bg,
                    borderColor:  sel ? (dark ? 'var(--accent)' : '#2563eb') : (esHoy(dia.fecha) ? (dark ? 'var(--accent)' : '#2563eb') : est.border),
                    color:        sel ? '#fff' : (esHoy(dia.fecha) && !sel ? (dark ? 'var(--accent)' : '#2563eb') : est.text),
                    fontWeight:   esHoy(dia.fecha) ? 700 : 400,
                    cursor:       esFuturo(dia.fecha) ? 'default' : 'pointer',
                    opacity:      esFuturo(dia.fecha) ? 0.35 : 1,
                    boxShadow:    esHoy(dia.fecha) && !sel ? `0 0 0 2px ${dark ? 'var(--accent)' : '#2563eb'}44` : 'none',
                  }}
                  onClick={() => !esFuturo(dia.fecha) && selectDay(dia.fecha)}
                  title={dia.horas > 0 ? `${fmt(dia.horas)} · ${dia.partidas}p` : ''}
                >
                  <span style={{ fontSize: 13, lineHeight: 1 }}>{new Date(dia.fecha + 'T00:00').getDate()}</span>
                  {dia.horas > 0 && !sel && (
                    <span style={{
                      display: 'block', width: '80%', height: 3, borderRadius: 2, marginTop: 3,
                      background: est.border,
                    }} />
                  )}
                </div>
              )
            })}
          </div>

          {/* ── Leyenda ── */}
          <div style={s.leyenda}>
            {Object.entries(E).filter(([k]) => k !== 'vacio').map(([k, v]) => (
              <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <div style={{ width: 10, height: 10, borderRadius: 3, background: v.bg, border: `1px solid ${v.border}` }} />
                <span style={{ fontSize: 11, color: dark ? 'var(--muted)' : '#94a3b8' }}>
                  {k === 'ok' ? 'Dentro del límite' : k === 'warning' ? '+75% del límite' : 'Límite superado'}
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── Detalle del día seleccionado ── */}
      {selectedDay && (
        <div style={s.diaDetalle}>
          <div style={s.detalleCabecera}>
            <span style={s.detalleFecha}>
              {new Date(selectedDay + 'T00:00').toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
            </span>
            <button style={s.cerrarBtn} onClick={() => { setSelectedDay(null); setDiaData(null) }}>✕</button>
          </div>

          {loadingDia ? (
            <p style={{ color: dark ? 'var(--muted)' : '#94a3b8', fontSize: 14 }}>Cargando...</p>
          ) : !diaData ? null : diaData.partidas === 0 ? (
            <p style={{ color: dark ? 'var(--muted)' : '#94a3b8', fontSize: 14 }}>Sin partidas este día.</p>
          ) : (
            <>
              <div style={s.diaStats}>
                <div style={s.diaStat}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: dark ? 'var(--text)' : '#1e293b' }}>{fmt(diaData.horas)}</div>
                  <div style={s.diaStatLbl}>jugadas</div>
                </div>
                <div style={s.diaStat}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: diaData.porcentaje > 100 ? (dark ? 'var(--danger)' : '#dc2626') : diaData.porcentaje >= 75 ? (dark ? 'var(--warning)' : '#d97706') : (dark ? 'var(--success)' : '#059669') }}>
                    {diaData.porcentaje.toFixed(0)}%
                  </div>
                  <div style={s.diaStatLbl}>del límite</div>
                </div>
                <div style={s.diaStat}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: dark ? 'var(--text)' : '#1e293b' }}>{diaData.partidas}</div>
                  <div style={s.diaStatLbl}>partidas</div>
                </div>
              </div>

              {/* Barra de progreso del día */}
              {diaData.limite > 0 && (
                <div style={s.barraWrap}>
                  <div style={{
                    height: '100%', borderRadius: 20,
                    width: `${Math.min(diaData.porcentaje, 100)}%`,
                    background: diaData.porcentaje > 100 ? (dark ? 'var(--danger)' : '#dc2626') : diaData.porcentaje >= 75 ? (dark ? 'var(--warning)' : '#d97706') : (dark ? 'var(--success)' : '#059669'),
                    transition: 'width .4s',
                  }} />
                </div>
              )}

              {/* Lista de partidas */}
              <div style={{ marginTop: 14 }}>
                {diaData.matches.map((p, i) => (
                  <div key={i} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '8px 0',
                    borderBottom: i < diaData.matches.length - 1 ? `1px solid ${dark ? 'var(--border)' : '#f1f5f9'}` : 'none',
                  }}>
                    <div>
                      <span style={{ fontSize: 14, fontWeight: 500, color: dark ? 'var(--text)' : '#1e293b' }}>{p.campeon}</span>
                      <span style={{ fontSize: 12, color: dark ? 'var(--muted)' : '#94a3b8', marginLeft: 8 }}>{p.hora} · {p.modo}</span>
                      {p.rendicion_negativa && <span style={{ marginLeft: 6, fontSize: 11 }} title="Tu equipo rindió">🏳</span>}
                      {p.rendicion_positiva && <span style={{ marginLeft: 4, fontSize: 11 }} title="Rival rindió">🤝</span>}
                      {p.afk               && <span style={{ marginLeft: 4, fontSize: 11 }} title="AFK">💤</span>}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                      <span style={{ fontSize: 12, color: dark ? 'var(--muted)' : '#94a3b8' }}>KDA {p.kda.toFixed(1)}</span>
                      <span style={{ fontSize: 12, color: dark ? 'var(--muted)' : '#94a3b8' }}>{fmtMin(p.duracion_min * 60)}</span>
                      <span style={{
                        fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 5,
                        background: p.resultado === 'Victoria' ? (dark ? 'rgba(52,211,153,.15)' : '#dcfce7') : (dark ? 'rgba(248,113,113,.15)' : '#fee2e2'),
                        color:      p.resultado === 'Victoria' ? (dark ? 'var(--success)' : '#059669') : (dark ? 'var(--danger)' : '#dc2626'),
                      }}>{p.resultado}</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ── Estilos tema oscuro (paciente) ────────────────────────────
const darkS = {
  wrap:           { background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '20px 22px' },
  header:         { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  navBtn:         { background: 'transparent', border: 'none', color: 'var(--muted)', fontSize: 20, cursor: 'pointer', padding: '2px 8px', borderRadius: 6, transition: 'color .15s' },
  mesLabel:       { fontFamily: "'Syne', sans-serif", fontSize: 15, fontWeight: 700, color: 'var(--text)' },
  loading:        { textAlign: 'center', color: 'var(--muted)', padding: '24px', fontSize: 14 },
  grid:           { display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 5 },
  diaSemana:      { textAlign: 'center', fontSize: 11, color: 'var(--muted)', padding: '4px 0', fontWeight: 600 },
  diaCell:        { textAlign: 'center', padding: '7px 4px', borderRadius: 8, border: '1px solid', transition: 'all .15s', display: 'flex', flexDirection: 'column', alignItems: 'center', minHeight: 38 },
  leyenda:        { display: 'flex', gap: 16, marginTop: 12, flexWrap: 'wrap' },
  diaDetalle:     { marginTop: 16, background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '16px 18px' },
  detalleCabecera:{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  detalleFecha:   { fontSize: 14, fontWeight: 600, color: 'var(--text)', textTransform: 'capitalize' },
  cerrarBtn:      { background: 'transparent', border: 'none', color: 'var(--muted)', fontSize: 16, cursor: 'pointer', padding: 4 },
  diaStats:       { display: 'flex', gap: 20, marginBottom: 12 },
  diaStat:        { textAlign: 'center', flex: 1, background: 'var(--bg2)', borderRadius: 8, padding: '10px 8px' },
  diaStatLbl:     { fontSize: 11, color: 'var(--muted)', marginTop: 3, textTransform: 'uppercase', letterSpacing: .6 },
  barraWrap:      { background: 'var(--bg)', borderRadius: 20, height: 8, overflow: 'hidden' },
}

// ── Estilos tema claro (profesional) ─────────────────────────
const lightS = {
  wrap:           { background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: '18px 20px' },
  header:         { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 },
  navBtn:         { background: 'transparent', border: 'none', color: '#94a3b8', fontSize: 20, cursor: 'pointer', padding: '2px 8px', borderRadius: 6 },
  mesLabel:       { fontFamily: "'Syne', sans-serif", fontSize: 15, fontWeight: 700, color: '#1e293b' },
  loading:        { textAlign: 'center', color: '#94a3b8', padding: '24px', fontSize: 14 },
  grid:           { display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 },
  diaSemana:      { textAlign: 'center', fontSize: 11, color: '#94a3b8', padding: '4px 0', fontWeight: 600 },
  diaCell:        { textAlign: 'center', padding: '6px 3px', borderRadius: 7, border: '1px solid', transition: 'all .15s', display: 'flex', flexDirection: 'column', alignItems: 'center', minHeight: 36, cursor: 'pointer' },
  leyenda:        { display: 'flex', gap: 14, marginTop: 10, flexWrap: 'wrap' },
  diaDetalle:     { marginTop: 14, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: '14px 16px' },
  detalleCabecera:{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  detalleFecha:   { fontSize: 13, fontWeight: 600, color: '#1e293b', textTransform: 'capitalize' },
  cerrarBtn:      { background: 'transparent', border: 'none', color: '#94a3b8', fontSize: 15, cursor: 'pointer', padding: 3 },
  diaStats:       { display: 'flex', gap: 14, marginBottom: 10 },
  diaStat:        { textAlign: 'center', flex: 1, background: '#fff', borderRadius: 8, padding: '10px 8px', border: '1px solid #e2e8f0' },
  diaStatLbl:     { fontSize: 11, color: '#94a3b8', marginTop: 3, textTransform: 'uppercase', letterSpacing: .6 },
  barraWrap:      { background: '#f1f5f9', borderRadius: 20, height: 8, overflow: 'hidden' },
}
