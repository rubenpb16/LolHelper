import { useEffect, useState } from 'react'
import { stats } from '../api'

// ── LP line chart (SVG puro, sin dependencias externas) ──────
const TIER_COLORS = {
  IRON: '#8b7355', BRONZE: '#cd7f32', SILVER: '#a8a9ad',
  GOLD: '#ffd700', PLATINUM: '#00c9a7', EMERALD: '#50c878',
  DIAMOND: '#9fc4e8', MASTER: '#c261f5', GRANDMASTER: '#f4c430',
  CHALLENGER: '#e6cc80',
}

function LpChart({ historia }) {
  const [tooltip, setTooltip] = useState(null)
  if (!historia || historia.length < 2)
    return <p style={{ color: 'var(--muted)', fontSize: 13 }}>Necesitas al menos 2 sincronizaciones con partidas ranked para ver el historial de LP.</p>

  const W = 560, H = 130
  const PAD = { top: 14, bottom: 26, left: 4, right: 4 }
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom

  const vals = historia.map(h => h.puntos)
  const minV = Math.min(...vals), maxV = Math.max(...vals)
  const range = maxV - minV || 100

  const xOf = i  => PAD.left + (i / (historia.length - 1)) * innerW
  const yOf = v  => PAD.top  + (1 - (v - minV) / range) * innerH

  const pts  = historia.map((h, i) => `${xOf(i)},${yOf(h.puntos)}`).join(' ')
  const poly = `${xOf(0)},${H - PAD.bottom} ${pts} ${xOf(historia.length - 1)},${H - PAD.bottom}`
  const diff = vals[vals.length - 1] - vals[0]
  const col  = diff >= 0 ? 'var(--success)' : 'var(--danger)'

  const labelIndices = historia.length <= 4
    ? historia.map((_, i) => i)
    : [0, Math.round(historia.length * 0.33), Math.round(historia.length * 0.66), historia.length - 1]

  return (
    <div style={{ position: 'relative' }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', overflow: 'visible' }}>
        <defs>
          <linearGradient id="lp-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor={diff >= 0 ? '#34d399' : '#f87171'} stopOpacity="0.18" />
            <stop offset="100%" stopColor={diff >= 0 ? '#34d399' : '#f87171'} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={poly} fill="url(#lp-fill)" />
        <polyline points={pts} fill="none" stroke={col} strokeWidth="2" strokeLinejoin="round" />
        {historia.map((h, i) => (
          <circle key={i}
            cx={xOf(i)} cy={yOf(h.puntos)} r={4}
            fill={TIER_COLORS[h.tier] || col}
            stroke="var(--bg2)" strokeWidth={1.5}
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => setTooltip({ i, x: xOf(i), y: yOf(h.puntos), h })}
            onMouseLeave={() => setTooltip(null)}
          />
        ))}
        {labelIndices.map(i => (
          <text key={i} x={xOf(i)} y={H - 6} textAnchor="middle"
            fontSize={9} fill="rgba(107,114,128,.9)">
            {historia[i].fecha.slice(5).replace('-', '/')}
          </text>
        ))}
      </svg>
      {tooltip && (
        <div style={{
          position: 'absolute',
          left:  Math.min(tooltip.x / W * 100, 78) + '%',
          top:   tooltip.y / H * 100 - 30 + '%',
          background: 'var(--bg3)', border: '1px solid var(--border2)',
          borderRadius: 8, padding: '6px 10px', fontSize: 12,
          pointerEvents: 'none', whiteSpace: 'nowrap', zIndex: 10,
          color: TIER_COLORS[tooltip.h.tier] || 'var(--text)',
        }}>
          <strong>{tooltip.h.tier} {tooltip.h.division} — {tooltip.h.lp} LP</strong>
          <div style={{ color: 'var(--muted)', marginTop: 2 }}>
            {tooltip.h.victorias}V {tooltip.h.derrotas}D · {tooltip.h.fecha}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────
function fmt(min) {
  if (!min && min !== 0) return '—'
  const h = Math.floor(min / 60), m = Math.round(min % 60)
  if (h === 0) return `${m}min`
  if (m === 0) return `${h}h`
  return `${h}h ${m}min`
}

function wrColor(wr) {
  if (wr >= 58) return 'var(--success)'
  if (wr >= 45) return 'var(--warning)'
  return 'var(--danger)'
}

function scoreColor(s) {
  if (s >= 75) return 'var(--success)'
  if (s >= 50) return 'var(--warning)'
  return 'var(--danger)'
}

function scoreLabel(s) {
  if (s >= 80) return 'Excelente'
  if (s >= 65) return 'Bueno'
  if (s >= 50) return 'Mejorable'
  if (s >= 35) return 'Preocupante'
  return 'Crítico'
}

function BarH({ value, max, color, label, sublabel }) {
  const w = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 4 }}>
        <span>{label}</span>
        <span style={{ color: 'var(--muted)', fontSize: 12 }}>{sublabel}</span>
      </div>
      <div style={{ background: 'var(--bg)', borderRadius: 4, height: 7, overflow: 'hidden' }}>
        <div style={{ width: `${w}%`, height: '100%', background: color || 'var(--accent)', borderRadius: 4, transition: 'width .4s' }} />
      </div>
    </div>
  )
}

// ── Flag card ─────────────────────────────────────────────────
function FlagCard({ flag }) {
  const isPos = flag.tipo === 'positivo'
  const borderColor = isPos ? 'rgba(52,211,153,.3)'
    : flag.nivel === 'danger' ? 'rgba(248,113,113,.3)' : 'rgba(251,191,36,.3)'
  const bg = isPos ? 'rgba(52,211,153,.06)'
    : flag.nivel === 'danger' ? 'rgba(248,113,113,.06)' : 'rgba(251,191,36,.06)'
  const metricaColor = isPos ? 'var(--success)'
    : flag.nivel === 'danger' ? 'var(--danger)' : 'var(--warning)'

  return (
    <div style={{
      border: `1px solid ${borderColor}`,
      background: bg,
      borderRadius: 'var(--radius)',
      padding: '14px 16px',
      marginBottom: 10,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
        <span style={{ fontSize: 14, fontWeight: 500 }}>
          {flag.icono} {flag.titulo}
        </span>
        <span style={{ fontSize: 12, fontWeight: 700, color: metricaColor, marginLeft: 8, whiteSpace: 'nowrap' }}>
          {flag.metrica}
        </span>
      </div>
      <p style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.5, margin: 0 }}>{flag.texto}</p>
    </div>
  )
}

const dateInputStyle = {
  background: 'var(--bg3)', border: '1px solid var(--border2)',
  borderRadius: 'var(--radius)', padding: '6px 10px',
  color: 'var(--text)', fontSize: 13, colorScheme: 'dark',
}

// ── Página ────────────────────────────────────────────────────
export default function Analisis() {
  const today = new Date().toISOString().slice(0, 10)

  const [data,       setData]       = useState(null)
  const [dias,       setDias]       = useState(30)
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState('')
  const [customFrom, setCustomFrom] = useState('')
  const [customTo,   setCustomTo]   = useState('')
  const [useCustom,  setUseCustom]  = useState(false)
  const [rankData,   setRankData]   = useState(null)

  async function load(params) {
    if (!data) setLoading(true)
    setError('')
    try {
      const res = await stats.analisis(params)
      setData(res.data)
    } catch {
      setError('No se pudieron cargar los datos.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (useCustom) {
      load({ fecha_inicio: customFrom, fecha_fin: customTo })
    } else {
      load({ dias })
    }
  }, [dias, useCustom, customFrom, customTo])

  // LP history se carga una sola vez (no depende del rango de análisis)
  useEffect(() => {
    stats.rankHistoria(60)
      .then(r => setRankData(r.data))
      .catch(() => {})
  }, [])

  function handleDiasChange(d) {
    setUseCustom(false); setDias(d)
  }

  function applyCustomRange() {
    if (customFrom && customTo && customFrom <= customTo) setUseCustom(true)
  }

  function clearCustomRange() {
    setCustomFrom(''); setCustomTo(''); setUseCustom(false)
  }

  const customValid = customFrom && customTo && customFrom <= customTo

  if (loading) return <div className="loader"><div className="spinner" /> Cargando análisis...</div>
  if (error)   return <div className="error-banner">{error}</div>
  if (!data || Object.keys(data).length === 0) return (
    <div>
      <h1 style={{ fontSize: 26, marginBottom: 20 }}>Análisis</h1>
      <div className="card" style={{ textAlign: 'center', padding: 48 }}>
        <p style={{ color: 'var(--muted)' }}>Necesitas más partidas para generar el análisis. Juega algunas partidas y sincroniza.</p>
      </div>
    </div>
  )

  const {
    bienestar_score: score,
    perfil, flags = [],
    sesiones = [], resumen_sesiones: res = {},
    curva_rendimiento: curva = [],
    correlacion_hora: horas = [],
    por_modo: modos = [],
    fatiga_consecutivos: fatiga = [],
    mejor_hora,
  } = data

  const flagsPos = flags.filter(f => f.tipo === 'positivo')
  const flagsNeg = flags.filter(f => f.tipo === 'negativo')
  const maxSes   = Math.max(...sesiones.map(s => parseFloat(s.duracion_min) || 0), 1)
  const maxPartidasH = Math.max(...horas.map(h => h.total_partidas), 1)
  const maxModo  = Math.max(...modos.map(m => m.partidas), 1)
  const kdaBase  = curva[0]?.kda_avg ? parseFloat(curva[0].kda_avg) : null
  const wrBase   = curva[0]?.winrate_pct ? parseFloat(curva[0].winrate_pct) : null
  const kdaFatBase = fatiga[0]?.kda_avg ? parseFloat(fatiga[0].kda_avg) : null

  return (
    <div>
      {/* Cabecera */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 26, marginBottom: 8 }}>Análisis</h1>

          {/* Selector rápido de días */}
          <div className="days-selector" style={{ marginBottom: 10 }}>
            {[14, 30, 60, 90].map(d => (
              <button key={d}
                className={!useCustom && dias === d ? 'active' : ''}
                onClick={() => handleDiasChange(d)}
              >{d} días</button>
            ))}
          </div>

          {/* Selector de rango personalizado */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, color: 'var(--muted)' }}>O elige rango:</span>
            <input type="date" max={today}
              value={customFrom}
              onChange={e => { setCustomFrom(e.target.value); setUseCustom(false) }}
              style={dateInputStyle}
            />
            <span style={{ fontSize: 13, color: 'var(--muted)' }}>—</span>
            <input type="date" max={today} min={customFrom || undefined}
              value={customTo}
              onChange={e => { setCustomTo(e.target.value); setUseCustom(false) }}
              style={dateInputStyle}
            />
            {customValid && !useCustom && (
              <button className="btn btn-sm btn-primary" onClick={applyCustomRange}>Aplicar</button>
            )}
            {useCustom && (
              <button className="btn btn-sm" onClick={clearCustomRange}>× Limpiar</button>
            )}
          </div>

          {useCustom && (
            <p style={{ fontSize: 12, color: 'var(--accent)', marginTop: 6 }}>
              Mostrando del {new Date(customFrom + 'T00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })} al {new Date(customTo + 'T00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}
            </p>
          )}
        </div>
        {mejor_hora && (
          <div style={{
            background: 'rgba(52,211,153,.08)', border: '1px solid rgba(52,211,153,.25)',
            borderRadius: 'var(--radius)', padding: '10px 16px', textAlign: 'right',
          }}>
            <div style={{ fontSize: 11, color: 'var(--success)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>Mejor hora para jugar</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--success)' }}>{String(mejor_hora.hora).padStart(2,'0')}:00h</div>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>{mejor_hora.winrate_pct}% WR · {mejor_hora.total_partidas} partidas</div>
          </div>
        )}
      </div>

      {/* ── Índice de bienestar ── */}
      <div className="card" style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 32 }}>
        {/* Score circular */}
        <div style={{ textAlign: 'center', flexShrink: 0 }}>
          <div style={{
            width: 100, height: 100, borderRadius: '50%',
            background: `conic-gradient(${scoreColor(score)} ${score}%, var(--bg) ${score}%)`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            position: 'relative',
          }}>
            <div style={{
              width: 76, height: 76, borderRadius: '50%',
              background: 'var(--bg2)',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            }}>
              <div style={{ fontSize: 24, fontWeight: 700, lineHeight: 1, color: scoreColor(score) }}>{score}</div>
              <div style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>/100</div>
            </div>
          </div>
          <div style={{ marginTop: 8, fontSize: 13, fontWeight: 600, color: scoreColor(score) }}>{scoreLabel(score)}</div>
        </div>

        <div style={{ flex: 1 }}>
          <p className="section-title" style={{ marginBottom: 8 }}>Índice de Bienestar</p>
          <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.6, marginBottom: 16 }}>
            Puntuación compuesta que evalúa tus patrones de juego: horario, duración de sesiones,
            respeto al límite, comportamiento en partida y constancia. Cuanto más alto, mejor equilibrio
            entre disfrute y bienestar.
          </p>
          {/* Mini barras de los factores clave */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 24px' }}>
            <BarH value={100 - Math.min(perfil.pct_nocturno * 2, 100)} max={100}
              color={perfil.pct_nocturno < 20 ? 'var(--success)' : perfil.pct_nocturno < 35 ? 'var(--warning)' : 'var(--danger)'}
              label="Horario saludable" sublabel={`${100 - perfil.pct_nocturno}% diurno`} />
            <BarH value={Math.max(0, 100 - parseFloat(res.duracion_media_min || 0) / 2)} max={100}
              color={parseFloat(res.duracion_media_min || 0) <= 75 ? 'var(--success)' : parseFloat(res.duracion_media_min || 0) <= 150 ? 'var(--warning)' : 'var(--danger)'}
              label="Sesiones equilibradas" sublabel={fmt(parseFloat(res.duracion_media_min || 0))} />
            <BarH value={Math.max(0, 100 - parseFloat(res.pct_sesiones_finde || 0) || 100)} max={100}
              color="var(--accent)"
              label="Balance semanal" sublabel={`${res.pct_sesiones_finde || 0}% en finde`} />
            <BarH value={data.racha_actual || 0} max={Math.max(data.racha_actual || 0, 7)}
              color="var(--success)"
              label="Racha activa" sublabel={`${data.racha_actual || 0} días`} />
          </div>
        </div>
      </div>

      {/* ── Flags positivas + negativas ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>

        <div className="card">
          <p className="section-title" style={{ marginBottom: 16, color: 'var(--success)' }}>
            ✅ Señales positivas ({flagsPos.length})
          </p>
          {flagsPos.length === 0 ? (
            <p style={{ color: 'var(--muted)', fontSize: 13 }}>
              Aún no hay señales positivas para este período. ¡Sigue jugando con hábitos saludables!
            </p>
          ) : flagsPos.map((f, i) => <FlagCard key={i} flag={f} />)}
        </div>

        <div className="card">
          <p className="section-title" style={{ marginBottom: 16, color: 'var(--danger)' }}>
            ⚠️ Señales a mejorar ({flagsNeg.length})
          </p>
          {flagsNeg.length === 0 ? (
            <p style={{ color: 'var(--muted)', fontSize: 13 }}>
              ¡Sin señales negativas detectadas! Mantén estos hábitos.
            </p>
          ) : flagsNeg.map((f, i) => <FlagCard key={i} flag={f} />)}
        </div>
      </div>

      {/* ── Sesiones ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>

        <div className="card">
          <p className="section-title" style={{ marginBottom: 16 }}>Resumen de sesiones</p>
          <div className="stat-grid" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: 0 }}>
            <div className="stat-card">
              <div className="val val-accent">{res.total_sesiones ?? '—'}</div>
              <div className="lbl">sesiones</div>
            </div>
            <div className="stat-card">
              <div className="val">{fmt(parseFloat(res.duracion_media_min) || 0)}</div>
              <div className="lbl">duración media</div>
            </div>
            <div className="stat-card">
              <div className="val val-warn">{parseFloat(res.partidas_media ?? 0).toFixed(1)}</div>
              <div className="lbl">partidas / sesión</div>
            </div>
            <div className="stat-card">
              <div className={`val ${res.sesiones_mas_3h > 0 ? 'val-danger' : 'val-ok'}`}>
                {res.sesiones_mas_3h ?? 0}
              </div>
              <div className="lbl">sesiones +3h</div>
            </div>
          </div>
        </div>

        <div className="card" style={{ maxHeight: 280, overflowY: 'auto' }}>
          <p className="section-title" style={{ marginBottom: 12 }}>Últimas sesiones</p>
          {sesiones.length === 0 ? (
            <p style={{ color: 'var(--muted)', fontSize: 13 }}>Sin datos</p>
          ) : sesiones.slice(0, 10).map((s, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '7px 0', borderBottom: '1px solid var(--border)', fontSize: 13,
            }}>
              <div>
                <span style={{ fontWeight: 500 }}>
                  {new Date(s.fecha + 'T00:00').toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' })}
                </span>
                <span style={{ color: 'var(--muted)', marginLeft: 8 }}>
                  {s.hora_inicio?.slice(0,5)} · {s.num_partidas}p · {fmt(parseFloat(s.duracion_min) || 0)}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ color: 'var(--muted)', fontSize: 12 }}>KDA {parseFloat(s.kda_avg || 0).toFixed(1)}</span>
                <span style={{ color: wrColor(s.winrate_pct), fontWeight: 600 }}>{s.winrate_pct}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Curva rendimiento + Fatiga días consecutivos ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>

        {/* Curva KDA en sesión */}
        <div className="card">
          <p className="section-title" style={{ marginBottom: 4 }}>Curva de rendimiento en sesión</p>
          <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>KDA y winrate por partida dentro de una misma sesión</p>
          {curva.length < 2 ? (
            <p style={{ color: 'var(--muted)', fontSize: 13 }}>Necesitas más sesiones con varias partidas.</p>
          ) : (() => {
            const maxKda = Math.max(...curva.map(c => parseFloat(c.kda_avg) || 0), 0.1)
            return curva.map((c, i) => {
              const kda   = parseFloat(c.kda_avg) || 0
              const pos   = c.pos >= 6 ? '6ª+' : `${c.pos}ª`
              const diff  = kdaBase && i > 0 ? Math.round((kda / kdaBase - 1) * 100) : null
              const color = !kdaBase || kda >= kdaBase * 0.9 ? 'var(--success)'
                          : kda >= kdaBase * 0.7 ? 'var(--warning)' : 'var(--danger)'
              return (
                <BarH key={i} value={kda} max={maxKda} color={color}
                  label={`Partida ${pos}`}
                  sublabel={`KDA ${kda.toFixed(2)}${diff !== null ? ` (${diff >= 0 ? '+' : ''}${diff}%)` : ' ←base'} · WR ${c.winrate_pct}%`}
                />
              )
            })
          })()}
        </div>

        {/* Fatiga por días consecutivos */}
        <div className="card">
          <p className="section-title" style={{ marginBottom: 4 }}>Fatiga por días consecutivos</p>
          <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>¿Cómo afectan los días seguidos jugando a tu rendimiento?</p>
          {fatiga.length < 2 ? (
            <p style={{ color: 'var(--muted)', fontSize: 13 }}>Necesitas más rachas de días consecutivos jugando.</p>
          ) : (() => {
            const maxKdaF = Math.max(...fatiga.map(f => parseFloat(f.kda_avg) || 0), 0.1)
            return fatiga.map((f, i) => {
              const kda   = parseFloat(f.kda_avg) || 0
              const label = f.dia_consecutivo >= 5 ? 'Día 5+' : `Día ${f.dia_consecutivo}`
              const diff  = kdaFatBase && i > 0 ? Math.round((kda / kdaFatBase - 1) * 100) : null
              const color = !kdaFatBase || kda >= kdaFatBase * 0.9 ? 'var(--success)'
                          : kda >= kdaFatBase * 0.75 ? 'var(--warning)' : 'var(--danger)'
              return (
                <BarH key={i} value={kda} max={maxKdaF} color={color}
                  label={label}
                  sublabel={`KDA ${kda.toFixed(2)}${diff !== null ? ` (${diff >= 0 ? '+' : ''}${diff}%)` : ' ←base'} · WR ${f.winrate_pct}%`}
                />
              )
            })
          })()}
        </div>
      </div>

      {/* ── Rendimiento por modo + Correlación horaria ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>

        {/* Por modo */}
        <div className="card">
          <p className="section-title" style={{ marginBottom: 16 }}>Rendimiento por modo de juego</p>
          {modos.length === 0 ? (
            <p style={{ color: 'var(--muted)', fontSize: 13 }}>Sin datos suficientes.</p>
          ) : modos.map((m, i) => {
            const wr = parseFloat(m.winrate_pct) || 0
            return (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 0', borderBottom: '1px solid var(--border)', gap: 12,
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 3 }}>{m.modo}</div>
                  <div style={{ background: 'var(--bg)', borderRadius: 3, height: 4 }}>
                    <div style={{
                      width: `${Math.round(m.partidas / maxModo * 100)}%`,
                      height: '100%', background: wrColor(wr), borderRadius: 3,
                    }} />
                  </div>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: wrColor(wr) }}>{wr}%</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>KDA {parseFloat(m.kda_avg || 0).toFixed(1)} · {m.partidas}p</div>
                </div>
              </div>
            )
          })}
        </div>

        {/* Correlación horaria */}
        <div className="card">
          <p className="section-title" style={{ marginBottom: 4 }}>Rendimiento por franja horaria</p>
          <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12 }}>Barra = volumen · Color = winrate</p>
          {horas.length === 0 ? (
            <p style={{ color: 'var(--muted)', fontSize: 13 }}>Sin datos.</p>
          ) : (
            <div style={{ maxHeight: 260, overflowY: 'auto' }}>
              {horas.map((h, i) => {
                const esMal = h.hora >= 22 || h.hora < 6
                return (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '5px 0', borderBottom: '1px solid var(--border)',
                  }}>
                    <span style={{ fontSize: 12, color: esMal ? 'var(--warning)' : 'var(--muted)', width: 40, flexShrink: 0 }}>
                      {String(h.hora).padStart(2,'0')}h{esMal ? ' 🌙' : ''}
                    </span>
                    <div style={{ flex: 1, background: 'var(--bg)', borderRadius: 3, height: 6 }}>
                      <div style={{
                        width: `${Math.round(h.total_partidas / maxPartidasH * 100)}%`,
                        height: '100%', background: wrColor(h.winrate_pct), borderRadius: 3,
                      }} />
                    </div>
                    <span style={{ fontSize: 12, fontWeight: 600, color: wrColor(h.winrate_pct), width: 36, textAlign: 'right' }}>
                      {h.winrate_pct}%
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--muted)', width: 28 }}>{h.total_partidas}p</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Historial de LP Ranked ── */}
      {rankData && (() => {
        const hist = rankData.historia || []
        if (hist.length === 0) return null
        const first = hist[0], last = hist[hist.length - 1]
        const diff  = last.puntos - first.puntos
        const diffColor = diff > 0 ? 'var(--success)' : diff < 0 ? 'var(--danger)' : 'var(--muted)'
        return (
          <div className="card" style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
              <p className="section-title">Progresión de LP — Ranked Solo/Duo (últimos 60 días)</p>
              <div style={{ textAlign: 'right', fontSize: 12 }}>
                <span style={{ color: 'var(--muted)' }}>
                  {first.tier} {first.division} {first.lp} LP → </span>
                <span style={{ color: TIER_COLORS[last.tier] || 'var(--text)', fontWeight: 600 }}>
                  {last.tier} {last.division} {last.lp} LP
                </span>
                <span style={{ color: diffColor, marginLeft: 8, fontWeight: 600 }}>
                  {diff > 0 ? '+' : ''}{diff} pts
                </span>
              </div>
            </div>
            <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16, lineHeight: 1.5 }}>
              Cada punto refleja tu LP acumulado (tier + división + LP). Pasa el ratón sobre los puntos para ver el detalle.
              Correlaciona esta curva con los días en que superaste tu límite para detectar si jugar más te ayuda o te perjudica.
            </p>
            <LpChart historia={hist} />
          </div>
        )
      })()}
    </div>
  )
}
