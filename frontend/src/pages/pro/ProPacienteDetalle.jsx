import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate }            from 'react-router-dom'
import ProNavbar                             from './ProNavbar'
import CalendarioMes                         from '../../components/CalendarioMes'
import { proPacientes }                      from '../../api'

// ── Helpers ───────────────────────────────────────────────────
function fmt(horas) {
  if (!horas && horas !== 0) return '—'
  const h = Math.floor(horas), m = Math.round((horas - h) * 60)
  if (h === 0) return `${m}min`
  if (m === 0) return `${h}h`
  return `${h}h ${m}min`
}
function fmtMin(min) { return fmt((min || 0) / 60) }
function wr(v)  { return parseFloat(v || 0) }
function wrCol(v) { return v >= 58 ? '#059669' : v >= 45 ? '#d97706' : '#dc2626' }
function scoreCol(s) { return s >= 75 ? '#059669' : s >= 50 ? '#d97706' : '#dc2626' }
function scoreLabel(s) {
  if (s >= 80) return 'Excelente' ; if (s >= 65) return 'Bueno'
  if (s >= 50) return 'Mejorable' ; if (s >= 35) return 'Preocupante'
  return 'Crítico'
}

const CAT_MAP = {
  observacion: { l: '📋 Observación',       c: '#2563eb', bg: '#eff6ff' },
  plan:        { l: '🎯 Plan terapéutico',  c: '#7c3aed', bg: '#f5f3ff' },
  alerta:      { l: '⚠️ Alerta',            c: '#dc2626', bg: '#fee2e2' },
  logro:       { l: '🏆 Logro',             c: '#059669', bg: '#dcfce7' },
}

const ESTADOS = {
  evaluacion:         { label: 'Evaluación inicial',  color: '#f59e0b' },
  tratamiento_activo: { label: 'Tratamiento activo',  color: '#2563eb' },
  seguimiento:        { label: 'Seguimiento',          color: '#8b5cf6' },
  alta:               { label: 'Alta médica',          color: '#059669' },
}
const ESTADOS_LIST = Object.entries(ESTADOS).map(([v, e]) => ({ value: v, ...e }))

const DIAS_OPTIONS = [14, 30, 60, 90]

// ── Mini bar ──────────────────────────────────────────────────
function Bar({ value, max, color }) {
  const w = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div style={{ background: '#f1f5f9', borderRadius: 4, height: 7, overflow: 'hidden', marginTop: 4 }}>
      <div style={{ width: `${w}%`, height: '100%', background: color || '#2563eb', borderRadius: 4, transition: 'width .4s' }} />
    </div>
  )
}

// ── Flag card (análisis) ──────────────────────────────────────
function FlagCard({ flag }) {
  const pos = flag.tipo === 'positivo'
  const bc  = pos ? 'rgba(5,150,105,.2)' : flag.nivel === 'danger' ? 'rgba(220,38,38,.2)' : 'rgba(217,119,6,.2)'
  const bg  = pos ? 'rgba(5,150,105,.05)' : flag.nivel === 'danger' ? 'rgba(220,38,38,.05)' : 'rgba(217,119,6,.05)'
  const mc  = pos ? '#059669' : flag.nivel === 'danger' ? '#dc2626' : '#d97706'
  return (
    <div style={{ border: `1px solid ${bc}`, background: bg, borderRadius: 8, padding: '12px 14px', marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{flag.icono} {flag.titulo}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color: mc }}>{flag.metrica}</span>
      </div>
      <p style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5, margin: 0 }}>{flag.texto}</p>
    </div>
  )
}

// ── LP chart (SVG) ────────────────────────────────────────────
const TIER_COLORS = {
  IRON:'#78716c',BRONZE:'#92400e',SILVER:'#6b7280',GOLD:'#b45309',
  PLATINUM:'#0d9488',EMERALD:'#059669',DIAMOND:'#3b82f6',
  MASTER:'#7c3aed',GRANDMASTER:'#dc2626',CHALLENGER:'#d97706',
}
function LpChart({ historia }) {
  const [tip, setTip] = useState(null)
  if (!historia || historia.length < 2)
    return <p style={{ color: '#94a3b8', fontSize: 13 }}>Sin suficientes datos de LP para mostrar la curva.</p>
  const W = 560, H = 120, P = { top: 12, bottom: 24, left: 4, right: 4 }
  const vals = historia.map(h => h.puntos)
  const minV = Math.min(...vals), maxV = Math.max(...vals)
  const range = maxV - minV || 100
  const xOf = i => P.left + (i / (historia.length - 1)) * (W - P.left - P.right)
  const yOf = v => P.top  + (1 - (v - minV) / range) * (H - P.top - P.bottom)
  const pts  = historia.map((h, i) => `${xOf(i)},${yOf(h.puntos)}`).join(' ')
  const poly = `${xOf(0)},${H - P.bottom} ${pts} ${xOf(historia.length - 1)},${H - P.bottom}`
  const diff = vals[vals.length - 1] - vals[0]
  const col  = diff >= 0 ? '#059669' : '#dc2626'
  const lbls = historia.length <= 4
    ? historia.map((_, i) => i)
    : [0, Math.round(historia.length * .33), Math.round(historia.length * .66), historia.length - 1]
  return (
    <div style={{ position: 'relative' }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', overflow: 'visible' }}>
        <defs>
          <linearGradient id="lp-pro" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor={col} stopOpacity=".15" />
            <stop offset="100%" stopColor={col} stopOpacity="0"   />
          </linearGradient>
        </defs>
        <polygon points={poly} fill="url(#lp-pro)" />
        <polyline points={pts} fill="none" stroke={col} strokeWidth="2" strokeLinejoin="round" />
        {historia.map((h, i) => (
          <circle key={i} cx={xOf(i)} cy={yOf(h.puntos)} r={4}
            fill={TIER_COLORS[h.tier] || col} stroke="#fff" strokeWidth={1.5}
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => setTip({ i, x: xOf(i), y: yOf(h.puntos), h })}
            onMouseLeave={() => setTip(null)} />
        ))}
        {lbls.map(i => (
          <text key={i} x={xOf(i)} y={H - 6} textAnchor="middle" fontSize={9} fill="#94a3b8">
            {historia[i].fecha.slice(5).replace('-', '/')}
          </text>
        ))}
      </svg>
      {tip && (
        <div style={{
          position: 'absolute', left: Math.min(tip.x / W * 100, 78) + '%',
          top: tip.y / H * 100 - 30 + '%',
          background: '#1e293b', color: '#f8fafc',
          borderRadius: 8, padding: '6px 10px', fontSize: 12, pointerEvents: 'none',
          whiteSpace: 'nowrap', zIndex: 10,
        }}>
          <strong style={{ color: TIER_COLORS[tip.h.tier] || '#f8fafc' }}>
            {tip.h.tier} {tip.h.division} — {tip.h.lp} LP
          </strong>
          <div style={{ color: '#94a3b8', marginTop: 2 }}>{tip.h.fecha}</div>
        </div>
      )}
    </div>
  )
}

// ── Componente principal ──────────────────────────────────────
export default function ProPacienteDetalle() {
  const { pacienteId } = useParams()
  const navigate       = useNavigate()
  const proUser        = JSON.parse(localStorage.getItem('pro_user') || '{}')

  const [tab,            setTab]            = useState('preconsulta')
  const [dashData,       setDashData]       = useState(null)
  const [preConsulta,    setPreConsulta]    = useState(null)
  const [comparativa,    setComparativa]    = useState(null)
  const [notas,          setNotas]          = useState([])
  const [analisisData,   setAnalisisData]   = useState(null)
  const [historialData,  setHistorialData]  = useState(null)
  const [rankData,       setRankData]       = useState(null)
  const [loading,        setLoading]        = useState(true)
  const [analisisLoad,   setAnalisisLoad]   = useState(false)
  const [historialLoad,  setHistorialLoad]  = useState(false)
  const [error,          setError]          = useState('')
  const [cambiandoEstado,setCambiandoEstado]= useState(false)
  const [nuevaNota,      setNuevaNota]      = useState('')
  const [nuevaCategoria, setNuevaCategoria] = useState('observacion')
  const [savingNota,     setSavingNota]     = useState(false)
  const [estadoActual,   setEstadoActual]   = useState('evaluacion')

  // Análisis: filtros
  const [analisisDias,   setAnalisisDias]   = useState(30)
  const [aCustomFrom,    setACustomFrom]    = useState('')
  const [aCustomTo,      setACustomTo]      = useState('')
  const [aUseCustom,     setAUseCustom]     = useState(false)

  // Historial: filtros
  const [hDias,          setHDias]          = useState(30)
  const [hFrom,          setHFrom]          = useState('')
  const [hTo,            setHTo]            = useState('')
  const [hUseCustom,     setHUseCustom]     = useState(false)
  const [hOffset,        setHOffset]        = useState(0)
  const H_LIMIT = 50
  const today = new Date().toISOString().slice(0, 10)

  // Carga inicial (resumen + notas + pre-consulta)
  useEffect(() => {
    Promise.all([
      proPacientes.dashboard(pacienteId),
      proPacientes.notas(pacienteId),
      proPacientes.resumenConsulta(pacienteId, 7),
      proPacientes.comparativa(pacienteId, 30, 30),
    ]).then(([d, n, pc, comp]) => {
      setPreConsulta(pc.data)
      setComparativa(comp.data)
      setDashData(d.data)
      setNotas(n.data.notas)
      setEstadoActual(d.data.estado_tratamiento || 'evaluacion')
    }).catch(() => setError('No se pudieron cargar los datos del paciente'))
      .finally(() => setLoading(false))
  }, [pacienteId])

  // Carga análisis cuando se activa el tab (o cambia el filtro)
  const loadAnalisis = useCallback(async (params) => {
    setAnalisisLoad(true)
    try {
      const [a, r] = await Promise.all([
        proPacientes.analisis(pacienteId, params),
        proPacientes.rankHistoria(pacienteId, 60),
      ])
      setAnalisisData(a.data)
      setRankData(r.data)
    } catch { /* silencioso */ }
    setAnalisisLoad(false)
  }, [pacienteId])

  useEffect(() => {
    if (tab !== 'analisis') return
    if (aUseCustom && aCustomFrom && aCustomTo) {
      loadAnalisis({ fecha_inicio: aCustomFrom, fecha_fin: aCustomTo })
    } else {
      loadAnalisis({ dias: analisisDias })
    }
  }, [tab, analisisDias, aUseCustom, aCustomFrom, aCustomTo, loadAnalisis])

  // Carga historial cuando se activa el tab (o cambia el filtro)
  const loadHistorial = useCallback(async (params) => {
    setHistorialLoad(true)
    try {
      const r = await proPacientes.historial(pacienteId, params)
      setHistorialData(r.data)
    } catch { /* silencioso */ }
    setHistorialLoad(false)
  }, [pacienteId])

  useEffect(() => {
    if (tab !== 'historial') return
    if (hUseCustom && hFrom && hTo) {
      loadHistorial({ fecha_inicio: hFrom, fecha_fin: hTo, limit: H_LIMIT, offset: hOffset })
    } else {
      loadHistorial({ dias: hDias, limit: H_LIMIT, offset: hOffset })
    }
  }, [tab, hDias, hUseCustom, hFrom, hTo, hOffset, loadHistorial])

  async function cambiarEstado(estado) {
    setCambiandoEstado(true)
    try {
      await proPacientes.actualizarEstado(pacienteId, estado)
      setEstadoActual(estado)
    } catch { /* silencioso */ }
    setCambiandoEstado(false)
  }

  async function agregarNota(e) {
    e.preventDefault()
    if (!nuevaNota.trim()) return
    setSavingNota(true)
    try {
      const r = await proPacientes.crearNota(pacienteId, nuevaNota.trim(), nuevaCategoria)
      setNotas(prev => [{ id: r.data.id, contenido: nuevaNota.trim(), categoria: nuevaCategoria, creada_en: r.data.creada_en, editada_en: null }, ...prev])
      setNuevaNota('')
    } catch { /* silencioso */ }
    setSavingNota(false)
  }

  async function borrarNota(notaId) {
    await proPacientes.borrarNota(pacienteId, notaId)
    setNotas(prev => prev.filter(n => n.id !== notaId))
  }

  if (loading) return <div style={s.page}><ProNavbar user={proUser} /><div style={s.center}>Cargando...</div></div>
  if (error)   return <div style={s.page}><ProNavbar user={proUser} /><div style={{ ...s.center, color: '#dc2626' }}>{error}</div></div>

  const { nombre, tag, email, hoy, semana, objetivo, racha, ranked, ultimas_partidas = [], sincronizado } = dashData || {}

  return (
    <div style={s.page}>
      <ProNavbar user={proUser} />
      <div style={s.content}>

        {/* ── Cabecera ── */}
        <div style={s.cabecera}>
          <button style={s.back} onClick={() => navigate('/pro/dashboard')}>← Volver</button>
          <div style={s.pacienteInfo}>
            <div style={s.avatar}>
              {(dashData?.nombre_real || nombre)?.charAt(0)?.toUpperCase()}
            </div>
            <div>
              {dashData?.nombre_real
                ? <>
                    <h1 style={s.h1}>
                      {dashData.nombre_real} {dashData.apellidos_real}
                    </h1>
                    <p style={{ fontSize: 13, color: '#64748b', marginBottom: 2 }}>
                      {nombre}<span style={{ color: '#94a3b8' }}>#{tag}</span>
                    </p>
                  </>
                : <h1 style={s.h1}>{nombre}<span style={s.tag}>#{tag}</span></h1>
              }
              <p style={s.sub}>{email}</p>
              {ranked?.tier && (
                <span style={{ fontSize: 13, color: '#2563eb', fontWeight: 500 }}>
                  {ranked.tier} {ranked.division} · {ranked.lp} LP
                </span>
              )}
            </div>
          </div>
          <div style={s.estadoBox}>
            <label style={s.estadoLabel}>Estado del tratamiento</label>
            <select style={{ ...s.estadoSelect, borderColor: (ESTADOS[estadoActual]?.color || '#64748b') + '66', color: ESTADOS[estadoActual]?.color || '#64748b' }}
              value={estadoActual} onChange={e => cambiarEstado(e.target.value)} disabled={cambiandoEstado}>
              {ESTADOS_LIST.map(e => <option key={e.value} value={e.value}>{e.label}</option>)}
            </select>
          </div>
        </div>

        {!sincronizado && (
          <div style={s.warning}>⚠️ Este paciente aún no ha sido sincronizado con Riot. Los datos aparecerán en el próximo ciclo automático.</div>
        )}

        {/* ── Tabs ── */}
        <div style={s.tabs}>
          {[
            ['preconsulta', '🩺 Pre-consulta'],
            ['resumen',     'Resumen'],
            ['analisis',    'Análisis'],
            ['historial',   'Historial'],
            ['notas',       `Notas (${notas.length})`],
          ].map(([k, l]) => (
            <button key={k} style={{ ...s.tab, ...(tab === k ? s.tabActive : {}) }} onClick={() => setTab(k)}>{l}</button>
          ))}
        </div>

        {/* ════════════ TAB: PRE-CONSULTA ════════════ */}
        {tab === 'preconsulta' && (() => {
          const PC_TENDENCIA = {
            mejorando:             { label: '↓ Mejorando',        color: '#059669', bg: '#dcfce7' },
            empeorando:            { label: '↑ Empeorando',       color: '#dc2626', bg: '#fee2e2' },
            estable:               { label: '→ Estable',           color: '#d97706', bg: '#fef9c3' },
            sin_datos_anteriores:  { label: 'Sin datos previos',  color: '#94a3b8', bg: '#f1f5f9' },
          }
          const pc   = preConsulta
          const comp = comparativa
          if (!pc || !pc.sincronizado) return (
            <div style={s.emptyCard}>Sin datos suficientes para el resumen de consulta.</div>
          )
          const tendencia = PC_TENDENCIA[pc.tendencia] || PC_TENDENCIA.estable
          const fmt7 = (h) => { const hh = Math.floor(h), m = Math.round((h-hh)*60); return hh ? `${hh}h${m?` ${m}min`:''}` : `${m}min` }
          const cambio = comp?.cambio || {}

          return (
            <>
              {/* Cabecera resumen */}
              <div style={{ ...s.card, display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                <div>
                  <p style={{ ...s.cardTitle, marginBottom: 4 }}>Resumen últimos {pc.periodo_dias} días</p>
                  <p style={{ fontSize: 13, color: '#64748b' }}>
                    {pc.stats.partidas} partidas · {fmt7(pc.stats.horas_total)} · {pc.stats.dias_jugados} días jugados
                  </p>
                </div>
                <div style={{ background: tendencia.bg, color: tendencia.color, fontWeight: 700, fontSize: 14, padding: '8px 16px', borderRadius: 8 }}>
                  {tendencia.label}
                </div>
              </div>

              {/* KPIs */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 14 }}>
                {[
                  { val: `${pc.stats.winrate_pct.toFixed(0)}%`,    lbl: 'Winrate',              color: pc.stats.winrate_pct >= 50 ? '#059669' : '#dc2626' },
                  { val: pc.stats.excesos_limite,                   lbl: 'Días excedió límite',  color: pc.stats.excesos_limite > 0 ? '#dc2626' : '#059669' },
                  { val: `${pc.stats.rendicion_pct.toFixed(0)}%`,   lbl: 'Rendición propia',     color: pc.stats.rendicion_pct > 20 ? '#dc2626' : '#059669' },
                  { val: pc.stats.madrugada,                        lbl: 'Partidas de madrugada',color: pc.stats.madrugada > 2 ? '#d97706' : '#059669' },
                ].map((st, i) => (
                  <div key={i} style={{ ...s.statCard, textAlign: 'center' }}>
                    <div style={{ fontSize: 24, fontWeight: 700, color: st.color, fontFamily: "'Syne', sans-serif" }}>{st.val}</div>
                    <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>{st.lbl}</div>
                  </div>
                ))}
              </div>

              {/* Señales */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
                <div style={s.card}>
                  <p style={{ ...s.cardTitle, color: '#dc2626', marginBottom: 10 }}>⚠️ Señales críticas</p>
                  {pc.señales_criticas.length === 0
                    ? <p style={{ color: '#94a3b8', fontSize: 13 }}>Sin señales críticas este período.</p>
                    : pc.señales_criticas.map((msg, i) => (
                      <div key={i} style={{ display: 'flex', gap: 8, padding: '8px 0', borderBottom: '1px solid #fef2f2', fontSize: 13, color: '#1e293b' }}>
                        <span style={{ color: '#dc2626', flexShrink: 0 }}>●</span> {msg}
                      </div>
                    ))}
                </div>
                <div style={s.card}>
                  <p style={{ ...s.cardTitle, color: '#059669', marginBottom: 10 }}>✅ Avances positivos</p>
                  {pc.señales_positivas.length === 0
                    ? <p style={{ color: '#94a3b8', fontSize: 13 }}>Sin avances destacables este período.</p>
                    : pc.señales_positivas.map((msg, i) => (
                      <div key={i} style={{ display: 'flex', gap: 8, padding: '8px 0', borderBottom: '1px solid #f0fdf4', fontSize: 13, color: '#1e293b' }}>
                        <span style={{ color: '#059669', flexShrink: 0 }}>●</span> {msg}
                      </div>
                    ))}
                </div>
              </div>

              {/* Comparativa 30d vs 30d anteriores */}
              {comp && comp.actual && comp.anterior && (
                <div style={s.card}>
                  <p style={s.cardTitle}>Comparativa de períodos (últimos 30 días vs 30 días anteriores)</p>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
                    {[
                      { lbl: 'Horas/día',      actual: comp.actual.horas_dia.toFixed(1),      prev: comp.anterior.horas_dia.toFixed(1),      cambio: cambio.horas_dia,     inv: true  },
                      { lbl: 'Winrate %',      actual: comp.actual.winrate_pct.toFixed(0)+'%', prev: comp.anterior.winrate_pct.toFixed(0)+'%', cambio: cambio.winrate_pct,   inv: false },
                      { lbl: 'Rendición %',    actual: comp.actual.rendicion_pct.toFixed(0)+'%',prev: comp.anterior.rendicion_pct.toFixed(0)+'%',cambio: cambio.rendicion_pct, inv: true  },
                      { lbl: 'Madrugada',      actual: comp.actual.madrugada,                  prev: comp.anterior.madrugada,                   cambio: cambio.madrugada,     inv: true  },
                    ].map((item, i) => {
                      const mejora = item.cambio !== null && (item.inv ? item.cambio < 0 : item.cambio > 0)
                      const empeora= item.cambio !== null && (item.inv ? item.cambio > 0 : item.cambio < 0)
                      return (
                        <div key={i} style={{ background: '#f8fafc', borderRadius: 10, padding: '14px', border: '1px solid #e2e8f0' }}>
                          <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 8, fontWeight: 600, textTransform: 'uppercase' }}>{item.lbl}</div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                              <div style={{ fontSize: 18, fontWeight: 700, color: '#1e293b' }}>{item.actual}</div>
                              <div style={{ fontSize: 11, color: '#94a3b8' }}>antes: {item.prev}</div>
                            </div>
                            {item.cambio !== null && (
                              <div style={{
                                fontSize: 13, fontWeight: 700, padding: '3px 8px', borderRadius: 6,
                                background: mejora ? '#dcfce7' : empeora ? '#fee2e2' : '#f1f5f9',
                                color: mejora ? '#059669' : empeora ? '#dc2626' : '#64748b',
                              }}>
                                {item.cambio > 0 ? '+' : ''}{typeof item.cambio === 'number' ? item.cambio.toFixed(1) : item.cambio}
                              </div>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </>
          )
        })()}

        {/* ════════════ TAB: RESUMEN ════════════ */}
        {tab === 'resumen' && (
          <>
            <div style={s.statsGrid}>
              {[
                { val: hoy ? fmt(hoy.horas) : '—', lbl: 'Hoy', color: '#1e293b' },
                { val: objetivo ? fmt(objetivo.limite_dia) : '—', lbl: 'Límite diario', color: '#2563eb' },
                { val: semana ? fmt(semana.horas) : '—', lbl: 'Esta semana', color: (semana?.porcentaje || 0) >= 100 ? '#dc2626' : '#059669' },
                { val: racha ?? '—', lbl: 'Días de racha', color: '#8b5cf6' },
              ].map((st, i) => (
                <div key={i} style={s.statCard}>
                  <div style={{ fontSize: 26, fontWeight: 700, color: st.color, fontFamily: "'Syne', sans-serif" }}>{st.val}</div>
                  <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>{st.lbl}</div>
                </div>
              ))}
            </div>

            {objetivo && (
              <div style={s.card}>
                <p style={s.cardTitle}>Progreso de hoy</p>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ fontSize: 13, color: '#64748b' }}>{hoy ? fmt(hoy.horas) : '—'} jugadas</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: (objetivo.porcentaje_dia || 0) >= 100 ? '#dc2626' : (objetivo.porcentaje_dia || 0) >= 75 ? '#d97706' : '#059669' }}>
                    {(objetivo.porcentaje_dia || 0).toFixed(0)}%
                  </span>
                </div>
                <div style={{ background: '#f1f5f9', borderRadius: 20, height: 10, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%', borderRadius: 20,
                    width: `${Math.min(objetivo.porcentaje_dia || 0, 100)}%`,
                    background: (objetivo.porcentaje_dia || 0) >= 100 ? '#dc2626' : (objetivo.porcentaje_dia || 0) >= 75 ? '#d97706' : '#059669',
                  }} />
                </div>
                <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: 12, color: '#94a3b8' }}>
                  {hoy?.rendiciones > 0 && <span style={{ color: '#d97706' }}>🏳 {hoy.rendiciones} rendiciones propias</span>}
                  {hoy?.afks > 0         && <span style={{ color: '#dc2626' }}>💤 {hoy.afks} AFK</span>}
                </div>
              </div>
            )}

            <div style={s.card}>
              <p style={s.cardTitle}>Últimas 10 partidas</p>
              {ultimas_partidas.length === 0 ? (
                <p style={{ color: '#94a3b8', fontSize: 14 }}>Sin partidas registradas.</p>
              ) : (
                <table style={s.tbl}>
                  <thead><tr>
                    {['Campeón','Modo','Resultado','KDA','Duración','Fecha'].map(h => (
                      <th key={h} style={s.th}>{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {ultimas_partidas.map((p, i) => (
                      <tr key={i}>
                        <td style={s.td}><strong>{p.campeon}</strong></td>
                        <td style={{ ...s.td, color: '#94a3b8' }}>{p.modo}</td>
                        <td style={s.td}>
                          <span style={{
                            fontSize: 12, fontWeight: 600, padding: '2px 8px', borderRadius: 5,
                            background: p.resultado === 'Victoria' ? '#dcfce7' : '#fee2e2',
                            color:      p.resultado === 'Victoria' ? '#059669' : '#dc2626',
                          }}>{p.resultado}</span>
                          {p.rendicion_negativa && <span style={{ marginLeft: 4 }} title="Tu equipo rindió">🏳</span>}
                          {p.rendicion_positiva && <span style={{ marginLeft: 4 }} title="Rival rindió">🤝</span>}
                          {p.afk               && <span style={{ marginLeft: 4 }} title="AFK">💤</span>}
                        </td>
                        <td style={{ ...s.td, fontWeight: 600 }}>{p.kda.toFixed(2)}</td>
                        <td style={{ ...s.td, color: '#94a3b8' }}>{fmtMin(p.duracion_min * 60)}</td>
                        <td style={{ ...s.td, color: '#94a3b8' }}>{p.fecha}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Calendario de actividad */}
            <div style={s.card}>
              <p style={s.cardTitle}>Calendario de actividad</p>
              <CalendarioMes
                dark={false}
                fetchMes={(y, m) => proPacientes.mes(pacienteId, y, m)}
                fetchDia={(f)    => proPacientes.dia(pacienteId, f)}
              />
            </div>
          </>
        )}

        {/* ════════════ TAB: ANÁLISIS ════════════ */}
        {tab === 'analisis' && (
          <>
            {/* Filtros */}
            <div style={s.filterBar}>
              <div style={s.filterLeft}>
                {DIAS_OPTIONS.map(d => (
                  <button key={d}
                    style={{ ...s.filterBtn, ...((!aUseCustom && analisisDias === d) ? s.filterBtnActive : {}) }}
                    onClick={() => { setAUseCustom(false); setAnalisisDias(d) }}>
                    {d} días
                  </button>
                ))}
              </div>
              <div style={s.filterRight}>
                <input type="date" max={today} value={aCustomFrom}
                  style={s.dateInput}
                  onChange={e => { setACustomFrom(e.target.value); setAUseCustom(false) }} />
                <span style={{ color: '#94a3b8' }}>—</span>
                <input type="date" max={today} min={aCustomFrom || undefined} value={aCustomTo}
                  style={s.dateInput}
                  onChange={e => { setACustomTo(e.target.value); setAUseCustom(false) }} />
                {aCustomFrom && aCustomTo && !aUseCustom && (
                  <button style={s.applyBtn} onClick={() => setAUseCustom(true)}>Aplicar</button>
                )}
                {aUseCustom && (
                  <button style={s.clearBtn} onClick={() => { setACustomFrom(''); setACustomTo(''); setAUseCustom(false) }}>× Limpiar</button>
                )}
              </div>
            </div>

            {analisisLoad ? (
              <div style={s.center}>Cargando análisis...</div>
            ) : !analisisData || Object.keys(analisisData).length === 0 ? (
              <div style={s.emptyCard}>Necesita más partidas para generar el análisis.</div>
            ) : (() => {
              const {
                bienestar_score: score, perfil, flags = [],
                sesiones = [], resumen_sesiones: res = {},
                curva_rendimiento: curva = [],
                correlacion_hora: horas = [],
                por_modo: modos = [],
                fatiga_consecutivos: fatiga = [],
                mejor_hora,
              } = analisisData

              const flagsPos = flags.filter(f => f.tipo === 'positivo')
              const flagsNeg = flags.filter(f => f.tipo === 'negativo')
              const maxPartidasH = Math.max(...horas.map(h => h.total_partidas), 1)
              const maxModo = Math.max(...modos.map(m => m.partidas), 1)
              const kdaBase = curva[0]?.kda_avg ? parseFloat(curva[0].kda_avg) : null

              return (
                <>
                  {/* Wellbeing score */}
                  <div style={{ ...s.card, display: 'flex', gap: 28, alignItems: 'center', marginBottom: 16 }}>
                    <div style={{ textAlign: 'center', flexShrink: 0 }}>
                      <div style={{
                        width: 90, height: 90, borderRadius: '50%',
                        background: `conic-gradient(${scoreCol(score)} ${score}%, #f1f5f9 ${score}%)`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}>
                        <div style={{
                          width: 68, height: 68, borderRadius: '50%', background: '#fff',
                          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                        }}>
                          <div style={{ fontSize: 22, fontWeight: 700, color: scoreCol(score) }}>{score}</div>
                          <div style={{ fontSize: 9, color: '#94a3b8' }}>/100</div>
                        </div>
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: scoreCol(score), marginTop: 6 }}>{scoreLabel(score)}</div>
                    </div>
                    <div style={{ flex: 1 }}>
                      <p style={{ ...s.cardTitle, marginBottom: 8 }}>Índice de Bienestar</p>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 20px' }}>
                        {[
                          { label: 'Horario saludable', val: `${100 - (perfil?.pct_nocturno || 0)}% diurno`, color: (perfil?.pct_nocturno || 0) < 20 ? '#059669' : '#dc2626' },
                          { label: 'Sesiones equilibradas', val: fmtMin(parseFloat(res.duracion_media_min || 0)), color: parseFloat(res.duracion_media_min || 0) <= 75 ? '#059669' : '#d97706' },
                          { label: 'Partidas semanales', val: `${res.total_sesiones || 0} sesiones`, color: '#2563eb' },
                          { label: 'Racha activa', val: `${analisisData.racha_actual || 0} días`, color: '#059669' },
                        ].map((item, i) => (
                          <div key={i} style={{ marginBottom: 10 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                              <span style={{ color: '#64748b' }}>{item.label}</span>
                              <span style={{ color: item.color, fontWeight: 600 }}>{item.val}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                      {mejor_hora && (
                        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: '8px 12px', marginTop: 8, fontSize: 13 }}>
                          <strong style={{ color: '#059669' }}>Mejor hora para jugar:</strong>{' '}
                          <span style={{ color: '#059669', fontWeight: 700 }}>{String(mejor_hora.hora).padStart(2,'0')}:00h</span>
                          <span style={{ color: '#64748b' }}> · {mejor_hora.winrate_pct}% WR · {mejor_hora.total_partidas}p</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Flags */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
                    <div style={s.card}>
                      <p style={{ ...s.cardTitle, color: '#059669', marginBottom: 12 }}>✅ Señales positivas ({flagsPos.length})</p>
                      {flagsPos.length === 0
                        ? <p style={{ color: '#94a3b8', fontSize: 13 }}>Sin señales positivas en este período.</p>
                        : flagsPos.map((f, i) => <FlagCard key={i} flag={f} />)}
                    </div>
                    <div style={s.card}>
                      <p style={{ ...s.cardTitle, color: '#dc2626', marginBottom: 12 }}>⚠️ Señales a mejorar ({flagsNeg.length})</p>
                      {flagsNeg.length === 0
                        ? <p style={{ color: '#94a3b8', fontSize: 13 }}>Sin señales negativas.</p>
                        : flagsNeg.map((f, i) => <FlagCard key={i} flag={f} />)}
                    </div>
                  </div>

                  {/* Sesiones + modo */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
                    <div style={s.card}>
                      <p style={s.cardTitle}>Resumen de sesiones</p>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                        {[
                          { val: res.total_sesiones ?? '—', lbl: 'Sesiones', color: '#2563eb' },
                          { val: fmtMin(parseFloat(res.duracion_media_min) || 0), lbl: 'Duración media', color: '#1e293b' },
                          { val: parseFloat(res.partidas_media ?? 0).toFixed(1), lbl: 'Partidas / sesión', color: '#d97706' },
                          { val: res.sesiones_mas_3h ?? 0, lbl: 'Sesiones +3h', color: (res.sesiones_mas_3h || 0) > 0 ? '#dc2626' : '#059669' },
                        ].map((st, i) => (
                          <div key={i} style={{ background: '#f8fafc', borderRadius: 8, padding: '12px 14px', textAlign: 'center' }}>
                            <div style={{ fontSize: 20, fontWeight: 700, color: st.color }}>{st.val}</div>
                            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 3 }}>{st.lbl}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div style={s.card}>
                      <p style={s.cardTitle}>Rendimiento por modo</p>
                      {modos.length === 0 ? <p style={{ color: '#94a3b8', fontSize: 13 }}>Sin datos.</p>
                        : modos.map((m, i) => {
                          const w = wr(m.winrate_pct)
                          return (
                            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid #f1f5f9', gap: 10 }}>
                              <div style={{ flex: 1 }}>
                                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 3 }}>{m.modo}</div>
                                <Bar value={m.partidas} max={maxModo} color={wrCol(w)} />
                              </div>
                              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                                <div style={{ fontSize: 14, fontWeight: 600, color: wrCol(w) }}>{w}%</div>
                                <div style={{ fontSize: 11, color: '#94a3b8' }}>KDA {parseFloat(m.kda_avg||0).toFixed(1)} · {m.partidas}p</div>
                              </div>
                            </div>
                          )
                        })}
                    </div>
                  </div>

                  {/* Curva rendimiento + franja horaria */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
                    <div style={s.card}>
                      <p style={s.cardTitle}>Curva de rendimiento en sesión</p>
                      <p style={{ fontSize: 12, color: '#94a3b8', marginBottom: 12 }}>KDA por número de partida dentro de una sesión</p>
                      {curva.length < 2 ? <p style={{ color: '#94a3b8', fontSize: 13 }}>Necesita más sesiones con varias partidas.</p>
                        : curva.map((c, i) => {
                          const kda  = parseFloat(c.kda_avg) || 0
                          const maxK = Math.max(...curva.map(x => parseFloat(x.kda_avg)||0), 0.1)
                          const diff = kdaBase && i > 0 ? Math.round((kda/kdaBase-1)*100) : null
                          const col  = !kdaBase || kda >= kdaBase*.9 ? '#059669' : kda >= kdaBase*.7 ? '#d97706' : '#dc2626'
                          return (
                            <div key={i} style={{ marginBottom: 8 }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                                <span style={{ color: '#64748b' }}>Partida {c.pos >= 6 ? '6ª+' : `${c.pos}ª`}</span>
                                <span style={{ color: col, fontWeight: 600 }}>KDA {kda.toFixed(2)}{diff !== null ? ` (${diff>=0?'+':''}${diff}%)` : ' ←base'}</span>
                              </div>
                              <Bar value={kda} max={maxK} color={col} />
                            </div>
                          )
                        })}
                    </div>
                    <div style={s.card}>
                      <p style={s.cardTitle}>Rendimiento por franja horaria</p>
                      <p style={{ fontSize: 12, color: '#94a3b8', marginBottom: 12 }}>Barra = volumen · Color = winrate</p>
                      <div style={{ maxHeight: 220, overflowY: 'auto' }}>
                        {horas.map((h, i) => {
                          const esMal = h.hora >= 22 || h.hora < 6
                          return (
                            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', borderBottom: '1px solid #f1f5f9' }}>
                              <span style={{ fontSize: 12, color: esMal ? '#d97706' : '#94a3b8', width: 40, flexShrink: 0 }}>
                                {String(h.hora).padStart(2,'0')}h{esMal ? ' 🌙' : ''}
                              </span>
                              <div style={{ flex: 1, background: '#f1f5f9', borderRadius: 3, height: 6 }}>
                                <div style={{ width: `${Math.round(h.total_partidas/maxPartidasH*100)}%`, height: '100%', background: wrCol(h.winrate_pct), borderRadius: 3 }} />
                              </div>
                              <span style={{ fontSize: 12, fontWeight: 600, color: wrCol(h.winrate_pct), width: 34, textAlign: 'right' }}>{h.winrate_pct}%</span>
                              <span style={{ fontSize: 11, color: '#94a3b8', width: 26 }}>{h.total_partidas}p</span>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  </div>

                  {/* Historial LP */}
                  {rankData?.historia?.length >= 2 && (() => {
                    const hist  = rankData.historia
                    const first = hist[0], last = hist[hist.length - 1]
                    const diff  = last.puntos - first.puntos
                    return (
                      <div style={s.card}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                          <p style={s.cardTitle}>Progresión de LP — Ranked Solo</p>
                          <span style={{ fontSize: 12, color: diff > 0 ? '#059669' : '#dc2626', fontWeight: 600 }}>
                            {first.tier} {first.division} {first.lp}LP → {last.tier} {last.division} {last.lp}LP
                            <span style={{ marginLeft: 8 }}>{diff > 0 ? '+' : ''}{diff} pts</span>
                          </span>
                        </div>
                        <LpChart historia={hist} />
                      </div>
                    )
                  })()}
                </>
              )
            })()}
          </>
        )}

        {/* ════════════ TAB: HISTORIAL ════════════ */}
        {tab === 'historial' && (
          <>
            {/* Filtros */}
            <div style={s.filterBar}>
              <div style={s.filterLeft}>
                {[7, 30, 60, 90].map(d => (
                  <button key={d}
                    style={{ ...s.filterBtn, ...(!hUseCustom && hDias === d ? s.filterBtnActive : {}) }}
                    onClick={() => { setHUseCustom(false); setHDias(d); setHOffset(0) }}>
                    {d} días
                  </button>
                ))}
              </div>
              <div style={s.filterRight}>
                <input type="date" max={today} value={hFrom} style={s.dateInput}
                  onChange={e => { setHFrom(e.target.value); setHUseCustom(false) }} />
                <span style={{ color: '#94a3b8' }}>—</span>
                <input type="date" max={today} min={hFrom || undefined} value={hTo} style={s.dateInput}
                  onChange={e => { setHTo(e.target.value); setHUseCustom(false) }} />
                {hFrom && hTo && !hUseCustom && (
                  <button style={s.applyBtn} onClick={() => { setHUseCustom(true); setHOffset(0) }}>Aplicar</button>
                )}
                {hUseCustom && (
                  <button style={s.clearBtn} onClick={() => { setHFrom(''); setHTo(''); setHUseCustom(false) }}>× Limpiar</button>
                )}
              </div>
            </div>

            {historialLoad ? (
              <div style={s.center}>Cargando historial...</div>
            ) : !historialData ? null : (
              <>
                {/* Resumen período */}
                {historialData.resumen && (
                  <div style={{ ...s.card, marginBottom: 16 }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 12 }}>
                      {[
                        { val: historialData.resumen.total_partidas, lbl: 'Partidas' },
                        { val: `${historialData.resumen.victorias || 0}V / ${(historialData.resumen.total_partidas||0) - (historialData.resumen.victorias||0)}D`, lbl: 'Resultados' },
                        { val: parseFloat(historialData.resumen.kda_avg||0).toFixed(2), lbl: 'KDA medio' },
                        { val: fmt(parseFloat(historialData.resumen.total_horas||0)), lbl: 'Tiempo total' },
                        { val: historialData.resumen.rendiciones || 0, lbl: 'Rendiciones propias 🏳' },
                      ].map((st, i) => (
                        <div key={i} style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: 18, fontWeight: 700, color: '#1e293b' }}>{st.val}</div>
                          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 3 }}>{st.lbl}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Tabla partidas */}
                <div style={{ ...s.card, padding: 0, overflow: 'hidden' }}>
                  <table style={{ ...s.tbl, fontSize: 13 }}>
                    <thead><tr>
                      {['Fecha','Campeón','Modo','Resultado','KDA','Dur.','CS/min','Flags'].map(h => (
                        <th key={h} style={s.th}>{h}</th>
                      ))}
                    </tr></thead>
                    <tbody>
                      {(historialData.partidas || []).map((p, i) => (
                        <tr key={i}>
                          <td style={s.td}>{p.fecha} <span style={{ color: '#94a3b8' }}>{p.hora}</span></td>
                          <td style={s.td}><strong>{p.campeon}</strong></td>
                          <td style={{ ...s.td, color: '#94a3b8' }}>{p.modo}</td>
                          <td style={s.td}>
                            <span style={{
                              fontSize: 11, fontWeight: 600, padding: '2px 7px', borderRadius: 4,
                              background: p.resultado === 'Victoria' ? '#dcfce7' : '#fee2e2',
                              color:      p.resultado === 'Victoria' ? '#059669' : '#dc2626',
                            }}>{p.resultado}</span>
                          </td>
                          <td style={{ ...s.td, fontWeight: 600 }}>{parseFloat(p.kda||0).toFixed(2)}</td>
                          <td style={{ ...s.td, color: '#94a3b8' }}>{fmtMin(p.duracion_min * 60)}</td>
                          <td style={{ ...s.td, color: '#94a3b8' }}>{parseFloat(p.cs_min||0).toFixed(1)}</td>
                          <td style={s.td}>
                            {p.rendicion_negativa && <span title="Tu equipo rindió">🏳</span>}
                            {p.rendicion_positiva && <span title="Rival rindió">🤝</span>}
                            {p.afk               && <span title="AFK">💤</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Paginación */}
                {historialData.total > H_LIMIT && (
                  <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
                    <button style={s.pageBtn} disabled={hOffset === 0}
                      onClick={() => setHOffset(Math.max(0, hOffset - H_LIMIT))}>← Anterior</button>
                    <span style={{ padding: '7px 14px', fontSize: 13, color: '#64748b' }}>
                      {Math.floor(hOffset / H_LIMIT) + 1} / {Math.ceil(historialData.total / H_LIMIT)}
                    </span>
                    <button style={s.pageBtn} disabled={hOffset + H_LIMIT >= historialData.total}
                      onClick={() => setHOffset(hOffset + H_LIMIT)}>Siguiente →</button>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* ════════════ TAB: NOTAS ════════════ */}
        {tab === 'notas' && (
          <>
            <div style={s.card}>
              <p style={s.cardTitle}>Nueva nota</p>
              <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 12 }}>Estas notas son privadas — el paciente no puede verlas.</p>
              <form onSubmit={agregarNota}>
                <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                  {[
                    { v: 'observacion', l: '📋 Observación',      c: '#2563eb', bg: '#eff6ff' },
                    { v: 'plan',        l: '🎯 Plan terapéutico', c: '#7c3aed', bg: '#f5f3ff' },
                    { v: 'alerta',      l: '⚠️ Alerta',           c: '#dc2626', bg: '#fee2e2' },
                    { v: 'logro',       l: '🏆 Logro',            c: '#059669', bg: '#dcfce7' },
                  ].map(cat => (
                    <button key={cat.v} type="button"
                      style={{
                        padding: '5px 12px', borderRadius: 20, border: '1px solid',
                        fontSize: 12, fontWeight: 600, cursor: 'pointer',
                        fontFamily: "'DM Sans', sans-serif",
                        background: nuevaCategoria === cat.v ? cat.bg : '#fff',
                        borderColor: nuevaCategoria === cat.v ? cat.c : '#e2e8f0',
                        color:       nuevaCategoria === cat.v ? cat.c : '#94a3b8',
                      }}
                      onClick={() => setNuevaCategoria(cat.v)}>
                      {cat.l}
                    </button>
                  ))}
                </div>
                <textarea style={s.textarea} rows={4}
                  placeholder="Observación de sesión, plan terapéutico, evolución..."
                  value={nuevaNota} onChange={e => setNuevaNota(e.target.value)} />
                <button style={{ ...s.addBtn, opacity: savingNota ? .7 : 1 }} disabled={savingNota || !nuevaNota.trim()}>
                  {savingNota ? 'Guardando...' : 'Guardar nota'}
                </button>
              </form>
            </div>
            {notas.length === 0
              ? <div style={{ ...s.card, textAlign: 'center', color: '#94a3b8', padding: 40 }}>Sin notas todavía.</div>
              : notas.map(n => {
                const cat = CAT_MAP[n.categoria] || CAT_MAP.observacion
                return (
                  <div key={n.id} style={{ ...s.notaCard, borderLeft: `3px solid ${cat.c}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 20, background: cat.bg, color: cat.c }}>{cat.l}</span>
                        <span style={{ fontSize: 12, color: '#94a3b8' }}>
                          {n.editada_en ? '(editada) ' : ''}
                          {new Date(n.creada_en).toLocaleString('es-ES', { day:'numeric', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' })}
                        </span>
                      </div>
                      <button style={s.deletBtn} onClick={() => borrarNota(n.id)}>Borrar</button>
                    </div>
                    <p style={{ fontSize: 14, color: '#334155', lineHeight: 1.7, whiteSpace: 'pre-wrap', margin: 0 }}>{n.contenido}</p>
                  </div>
                )
              })}
          </>
        )}
      </div>
    </div>
  )
}

// ── Estilos ───────────────────────────────────────────────────
const s = {
  page:         { minHeight: '100vh', background: '#f0f4f8', fontFamily: "'DM Sans', sans-serif" },
  content:      { maxWidth: 1100, margin: '0 auto', padding: '24px 20px' },
  center:       { display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300, color: '#64748b' },
  cabecera:     { display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20, flexWrap: 'wrap' },
  back:         { padding: '8px 14px', borderRadius: 8, background: '#fff', border: '1px solid #e2e8f0', color: '#2563eb', fontSize: 14, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif", fontWeight: 500 },
  pacienteInfo: { display: 'flex', alignItems: 'center', gap: 14, flex: 1, minWidth: 200 },
  avatar:       { width: 46, height: 46, borderRadius: '50%', background: '#dbeafe', color: '#2563eb', fontFamily: "'Syne', sans-serif", fontSize: 18, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  h1:           { fontFamily: "'Syne', sans-serif", fontSize: 20, fontWeight: 700, color: '#1e293b', marginBottom: 2 },
  tag:          { color: '#94a3b8', fontWeight: 400, fontSize: 15 },
  sub:          { fontSize: 13, color: '#64748b', marginBottom: 2 },
  estadoBox:    { display: 'flex', flexDirection: 'column', gap: 5, minWidth: 190 },
  estadoLabel:  { fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: .6 },
  estadoSelect: { padding: '7px 10px', borderRadius: 8, border: '2px solid', fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif", background: '#fff', outline: 'none' },
  warning:      { background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#92400e', marginBottom: 16 },
  tabs:         { display: 'flex', gap: 4, marginBottom: 18 },
  tab:          { padding: '8px 18px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', color: '#64748b', fontSize: 14, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif" },
  tabActive:    { background: '#eff6ff', borderColor: '#2563eb', color: '#2563eb', fontWeight: 600 },
  statsGrid:    { display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 14 },
  statCard:     { background: '#fff', borderRadius: 10, padding: '14px 16px', border: '1px solid #e2e8f0', textAlign: 'center' },
  card:         { background: '#fff', borderRadius: 12, border: '1px solid #e2e8f0', padding: '18px 20px', marginBottom: 14 },
  cardTitle:    { fontFamily: "'Syne', sans-serif", fontSize: 12, fontWeight: 700, color: '#64748b', marginBottom: 12, textTransform: 'uppercase', letterSpacing: .6 },
  tbl:          { width: '100%', borderCollapse: 'collapse' },
  th:           { padding: '10px 12px', fontSize: 11, color: '#94a3b8', textAlign: 'left', borderBottom: '1px solid #f1f5f9', fontWeight: 600, textTransform: 'uppercase', letterSpacing: .5 },
  td:           { padding: '10px 12px', color: '#334155', borderBottom: '1px solid #f8fafc', fontSize: 13 },
  filterBar:    { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, gap: 12, flexWrap: 'wrap' },
  filterLeft:   { display: 'flex', gap: 4 },
  filterRight:  { display: 'flex', gap: 8, alignItems: 'center' },
  filterBtn:    { padding: '6px 14px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', color: '#64748b', fontSize: 13, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif" },
  filterBtnActive:{ background: '#eff6ff', borderColor: '#2563eb', color: '#2563eb', fontWeight: 600 },
  dateInput:    { padding: '6px 10px', borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 13, fontFamily: "'DM Sans', sans-serif", outline: 'none', colorScheme: 'light' },
  applyBtn:     { padding: '6px 14px', borderRadius: 8, background: '#2563eb', border: 'none', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif" },
  clearBtn:     { padding: '6px 12px', borderRadius: 8, background: '#f1f5f9', border: 'none', color: '#64748b', fontSize: 13, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif" },
  emptyCard:    { background: '#fff', borderRadius: 12, border: '1px solid #e2e8f0', padding: 48, textAlign: 'center', color: '#94a3b8', fontSize: 15 },
  pageBtn:      { padding: '7px 16px', borderRadius: 8, background: '#fff', border: '1px solid #e2e8f0', color: '#2563eb', fontSize: 13, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif' " },
  textarea:     { width: '100%', padding: '12px 14px', borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 14, fontFamily: "'DM Sans', sans-serif", resize: 'vertical', outline: 'none', boxSizing: 'border-box', color: '#1e293b' },
  addBtn:       { marginTop: 10, padding: '10px 20px', borderRadius: 8, background: '#2563eb', border: 'none', color: '#fff', fontSize: 14, fontWeight: 600, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif" },
  notaCard:     { background: '#fff', borderRadius: 10, border: '1px solid #e2e8f0', padding: '14px 16px', marginBottom: 10 },
  deletBtn:     { padding: '3px 10px', borderRadius: 6, background: 'transparent', border: '1px solid #fecaca', color: '#dc2626', fontSize: 12, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif" },
}
