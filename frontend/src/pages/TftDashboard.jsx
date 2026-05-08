import { useEffect, useState, useCallback } from 'react'
import { tft, sync } from '../api'

const TFT_GOLD = '#c89b3c'
const TFT_DARK = '#1a1520'

function fmt(horas) {
  const h = Math.floor(horas), m = Math.round((horas - h) * 60)
  if (h === 0) return `${m}min`; if (m === 0) return `${h}h`; return `${h}h ${m}min`
}

function PlacementBadge({ placement }) {
  const colors = {
    1: { bg: '#ffd700', color: '#1a1a1a', label: '🥇 1º' },
    2: { bg: '#c0c0c0', color: '#1a1a1a', label: '🥈 2º' },
    3: { bg: '#cd7f32', color: '#fff',     label: '🥉 3º' },
    4: { bg: 'rgba(52,211,153,.2)', color: '#34d399', label: `4º` },
  }
  const c = colors[placement] || { bg: 'rgba(248,113,113,.15)', color: '#f87171', label: `${placement}º` }
  return (
    <span style={{ background: c.bg, color: c.color, padding: '2px 10px', borderRadius: 20, fontSize: 12, fontWeight: 700 }}>
      {c.label}
    </span>
  )
}

// Modal de tilt TFT: 3+ Bot4 consecutivos
const TILT_TFT = {
  bot4: {
    icon: '💀',
    title: 'Llevas varios Bot4 seguidos',
    body: 'Encadenar Bot4s indica que el meta no está entrando o que el cansancio está afectando tu lectura del tablero. Un descanso ahora vale más que una partida más.',
  },
}

export default function TftDashboard() {
  const [data,          setData]          = useState(null)
  const [loading,       setLoading]       = useState(true)
  const [error,         setError]         = useState('')
  const [syncing,       setSyncing]       = useState(false)
  const [syncMsg,       setSyncMsg]       = useState(null)
  const [showTilt,      setShowTilt]      = useState(false)

  const loadData = useCallback(async () => {
    try {
      const r = await tft.dashboard()
      setData(r.data)
    } catch { setError('No se pudieron cargar los datos TFT') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  useEffect(() => {
    if (!data?.ultimas_partidas?.length) return
    const today = new Date().toISOString().slice(0, 10)
    const key   = `tft_tilt_${today}`
    if (localStorage.getItem(key)) return
    const recent = data.ultimas_partidas.slice(0, 3)
    if (recent.length >= 3 && recent.every(p => !p.top4)) {
      setShowTilt(true)
    }
  }, [data])

  function dismissTilt() {
    localStorage.setItem(`tft_tilt_${new Date().toISOString().slice(0, 10)}`, '1')
    setShowTilt(false)
  }

  async function handleSync() {
    setSyncing(true); setSyncMsg(null)
    try {
      const res = await sync.me()
      if (!res.data.en_curso) {
        setSyncMsg({ type: 'ok', text: 'Datos actualizados' })
        await loadData()
      } else {
        setSyncMsg({ type: 'info', text: 'Sincronizando… la página se actualizará sola.' })
        let n = 0
        const iv = setInterval(async () => {
          n++; await loadData()
          if (n >= 18) clearInterval(iv)
        }, 10000)
      }
    } catch { setSyncMsg({ type: 'error', text: 'Error al sincronizar' }) }
    finally { setSyncing(false) }
  }

  if (loading) return <div className="loader"><div className="spinner" /> Cargando TFT...</div>
  if (error)   return <div className="error-banner">{error}</div>

  if (!data?.sincronizado) return (
    <div>
      <h1 style={{ marginBottom: 8 }}>TFT Dashboard</h1>
      <div className="card" style={{ marginTop: 24, textAlign: 'center', padding: 48 }}>
        <div style={{ fontSize: 32, marginBottom: 16 }}>⏳</div>
        <h3 style={{ marginBottom: 8 }}>Primera sincronización pendiente</h3>
        <p style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 24 }}>
          Pulsa Actualizar en el Dashboard de LoL para importar también tus partidas de TFT.
        </p>
      </div>
    </div>
  )

  const { hoy, semana, objetivo, rendimiento, ranked, ultimas_partidas = [] } = data
  const pct = objetivo.porcentaje_dia

  return (
    <div>
      {/* Cabecera */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 26, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ color: TFT_GOLD }}>♟</span> TFT Dashboard
          </h1>
          <p style={{ color: 'var(--muted)', fontSize: 14 }}>
            {new Date().toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' })}
            {ranked?.tier && (
              <span style={{ marginLeft: 12, color: TFT_GOLD, fontWeight: 500 }}>
                · {ranked.tier} {ranked.division} — {ranked.lp} LP
              </span>
            )}
          </p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
          <button className="btn btn-sm" onClick={handleSync} disabled={syncing} style={{ minWidth: 130 }}>
            {syncing ? <><div className="spinner" style={{ width: 12, height: 12 }} /> Sincronizando...</> : '↻ Actualizar'}
          </button>
          {syncMsg && (
            <span style={{ fontSize: 12, color: syncMsg.type === 'error' ? 'var(--danger)' : syncMsg.type === 'ok' ? 'var(--success)' : 'var(--muted)' }}>
              {syncMsg.text}
            </span>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="stat-grid">
        <div className="stat-card">
          <div style={{ fontSize: 26, fontWeight: 700, color: pct > 100 ? 'var(--danger)' : pct >= 75 ? 'var(--warning)' : 'var(--success)', fontFamily: "'Syne', sans-serif", lineHeight: 1, marginBottom: 6 }}>
            {fmt(hoy.horas)}
          </div>
          <div className="lbl">jugadas hoy</div>
        </div>
        <div className="stat-card">
          <div style={{ fontSize: 26, fontWeight: 700, color: TFT_GOLD, fontFamily: "'Syne', sans-serif", lineHeight: 1, marginBottom: 6 }}>
            {fmt(objetivo.limite_dia)}
          </div>
          <div className="lbl">límite diario TFT</div>
        </div>
        <div className="stat-card">
          <div style={{ fontSize: 26, fontWeight: 700, color: rendimiento.avg_placement <= 4 ? 'var(--success)' : 'var(--warning)', fontFamily: "'Syne', sans-serif", lineHeight: 1, marginBottom: 6 }}>
            #{rendimiento.avg_placement.toFixed(1)}
          </div>
          <div className="lbl">placement medio</div>
        </div>
        <div className="stat-card">
          <div style={{ fontSize: 26, fontWeight: 700, color: rendimiento.top4_rate >= 50 ? 'var(--success)' : 'var(--warning)', fontFamily: "'Syne', sans-serif", lineHeight: 1, marginBottom: 6 }}>
            {rendimiento.top4_rate.toFixed(0)}%
          </div>
          <div className="lbl">top4 rate</div>
        </div>
      </div>

      {/* Barra de progreso diario */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
          <span style={{ fontSize: 14, fontWeight: 500 }}>Progreso de hoy (TFT)</span>
          <span style={{ fontSize: 14, fontWeight: 500, color: pct >= 100 ? 'var(--danger)' : pct >= 75 ? 'var(--warning)' : 'var(--success)' }}>{pct.toFixed(0)}%</span>
        </div>
        <div className="progress-wrap" style={{ height: 10 }}>
          <div className="progress-fill" style={{
            width: `${Math.min(pct, 100)}%`,
            background: pct >= 100 ? 'var(--danger)' : pct >= 75 ? 'var(--warning)' : TFT_GOLD,
          }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 12, color: 'var(--muted)' }}>
          <span>{fmt(hoy.horas)} jugadas</span>
          <span>{fmt(Math.max(0, objetivo.limite_dia - hoy.horas))} restantes</span>
        </div>
        {hoy.partidas > 0 && (
          <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: 13, color: 'var(--muted)' }}>
            <span>{hoy.partidas} partidas</span>
            {hoy.avg_placement > 0 && <span>· Placement medio hoy: <strong style={{ color: 'var(--text)' }}>#{hoy.avg_placement.toFixed(1)}</strong></span>}
          </div>
        )}
      </div>

      {/* Últimas partidas */}
      <div className="card">
        <p className="section-title">Últimas partidas TFT</p>
        {ultimas_partidas.length === 0
          ? <p style={{ color: 'var(--muted)', fontSize: 14 }}>No hay partidas TFT registradas.</p>
          : ultimas_partidas.map((p, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '9px 0',
              borderBottom: i < ultimas_partidas.length - 1 ? '1px solid var(--border)' : 'none',
            }}>
              <div>
                <PlacementBadge placement={p.placement} />
                <span style={{ fontSize: 12, color: 'var(--muted)', marginLeft: 10 }}>{p.modo}</span>
              </div>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center', fontSize: 12, color: 'var(--muted)' }}>
                <span>{fmt(p.duracion_min / 60)}</span>
                <span>{p.fecha}</span>
              </div>
            </div>
          ))}
      </div>

      {/* Modal tilt TFT */}
      {showTilt && (
        <div className="modal-overlay" onClick={dismissTilt}>
          <div className="modal-card tilt-modal" onClick={e => e.stopPropagation()}>
            <div className="tilt-modal-icon">{TILT_TFT.bot4.icon}</div>
            <h2>{TILT_TFT.bot4.title}</h2>
            <p>{TILT_TFT.bot4.body}</p>
            <p className="tilt-sub">Esto no es un juicio — es exactamente la razón por la que instalaste LolHelper.</p>
            <div className="tilt-actions">
              <button className="btn btn-primary" style={{ flex: 1 }} onClick={dismissTilt}>Tomar un descanso</button>
              <button className="btn" style={{ flex: 1, fontSize: 13 }} onClick={dismissTilt}>Seguir jugando de todas formas</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
