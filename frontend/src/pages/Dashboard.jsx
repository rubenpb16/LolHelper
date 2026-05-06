import { useEffect, useState, useCallback } from 'react'
import { dashboard, stats, sync } from '../api'

function fmt(horas) {
  const h = Math.floor(horas)
  const m = Math.round((horas - h) * 60)
  if (h === 0) return `${m}min`
  if (m === 0) return `${h}h`
  return `${h}h ${m}min`
}

function BarColor(pct) {
  if (pct >= 100) return 'var(--danger)'
  if (pct >= 75)  return 'var(--warning)'
  return 'var(--success)'
}

const DIAS = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom']

// Mensajes empáticos según el tipo de tilt detectado
const TILT_CONTENT = {
  losses: {
    icon: '🔴',
    title: 'Llevas varias derrotas seguidas',
    body:  'Perder en racha es señal de que algo no está funcionando — puede ser el cansancio, la frustración o simplemente un mal momento. Lo más inteligente suele ser parar aquí y volver fresco.',
  },
  surrenders: {
    icon: '🏳️',
    title: 'Varias rendiciones seguidas',
    body:  'Rendir varias veces seguidas indica que el juego está generando más frustración que disfrute. No es un juicio — es la señal que estás esperando para hacer una pausa.',
  },
}

export default function Dashboard() {
  const [data,          setData]          = useState(null)
  const [behavior,      setBehavior]      = useState(null)
  const [loading,       setLoading]       = useState(true)
  const [error,         setError]         = useState('')
  const [syncing,       setSyncing]       = useState(false)
  const [syncMsg,       setSyncMsg]       = useState(null)   // { type: 'ok'|'info'|'error', text }
  const [showTiltModal, setShowTiltModal] = useState(false)
  const [tiltType,      setTiltType]      = useState(null)   // 'losses' | 'surrenders'

  const loadData = useCallback(async () => {
    try {
      const [d, b] = await Promise.all([
        dashboard.get(),
        stats.comportamiento(30),
      ])
      setData(d.data)
      setBehavior(b.data)
    } catch {
      setError('No se pudieron cargar los datos')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  // Detectar tilt al cargar datos (una vez por día)
  useEffect(() => {
    if (!data?.ultimas_partidas?.length) return
    const today = new Date().toISOString().slice(0, 10)
    const key   = `tilt_dismissed_${today}`
    if (localStorage.getItem(key)) return

    const recent = data.ultimas_partidas.slice(0, 3)
    const allLosses      = recent.length >= 3 && recent.every(p => p.resultado !== 'Victoria')
    const manySurrenders = recent.filter(p => p.rendicion_negativa).length >= 2

    if (allLosses) {
      setTiltType('losses')
      setShowTiltModal(true)
    } else if (manySurrenders) {
      setTiltType('surrenders')
      setShowTiltModal(true)
    }
  }, [data])

  async function handleSync() {
    setSyncing(true)
    setSyncMsg(null)
    try {
      const res = await sync.me()

      if (res.data.en_curso) {
        // Sync asíncrona: refrescar cada 10s hasta que aparezcan datos
        setSyncMsg({ type: 'info', text: 'Importando partidas… esto puede tardar 1-2 minutos. La página se actualizará sola.' })
        let intentos = 0
        const intervalo = setInterval(async () => {
          intentos++
          await loadData()
          if (intentos >= 18) clearInterval(intervalo) // máx 3 min
        }, 10000)
      } else {
        const n = res.data.partidas_nuevas ?? 0
        setSyncMsg({
          type: n > 0 ? 'ok' : 'info',
          text: n > 0
            ? `${n} partida${n !== 1 ? 's' : ''} nueva${n !== 1 ? 's' : ''} importada${n !== 1 ? 's' : ''}`
            : 'Todo al día — no hay partidas nuevas desde el último sync',
        })
        await loadData()
      }
    } catch (err) {
      const status = err.response?.status
      const detail = err.response?.data?.detail || 'Error al sincronizar'
      setSyncMsg({
        type: 'error',
        text: status === 429
          ? detail
          : status === 404
          ? detail
          : 'Error al conectar con Riot. Comprueba tu conexión e inténtalo de nuevo.',
      })
    } finally {
      setSyncing(false)
    }
  }

  function dismissTilt() {
    const today = new Date().toISOString().slice(0, 10)
    localStorage.setItem(`tilt_dismissed_${today}`, '1')
    setShowTiltModal(false)
  }

  if (loading) return <div className="loader"><div className="spinner" /> Cargando...</div>
  if (error)   return <div className="error-banner">{error}</div>

  if (!data?.sincronizado) return (
    <div>
      <h1 style={{ marginBottom: 8 }}>Dashboard</h1>
      <div className="card" style={{ marginTop: 24, textAlign: 'center', padding: 48 }}>
        <div style={{ fontSize: 32, marginBottom: 16 }}>⏳</div>
        <h3 style={{ marginBottom: 8 }}>Primera sincronización pendiente</h3>
        <p style={{ color: 'var(--muted)', fontSize: 14, maxWidth: 420, margin: '0 auto 8px' }}>
          Pulsa el botón para importar tu historial de partidas de Riot Games.
          La primera carga puede tardar unos segundos.
        </p>
        <p style={{ color: 'var(--muted)', fontSize: 12, maxWidth: 420, margin: '0 auto 24px' }}>
          Asegúrate de que tu nombre de invocador y TAG sean correctos —
          puedes cambiarlos en <strong>Cuenta</strong>.
        </p>
        <button className="btn btn-primary" onClick={handleSync} disabled={syncing}>
          {syncing
            ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Sincronizando...</>
            : 'Importar partidas'}
        </button>
        {syncMsg && (
          <div className={syncMsg.type === 'error' ? 'error-banner' : 'success-banner'}
               style={{ marginTop: 16, maxWidth: 420, margin: '16px auto 0', textAlign: 'left' }}>
            {syncMsg.text}
          </div>
        )}
      </div>
    </div>
  )

  const { hoy, semana, objetivo, racha, racha_maxima, ultimas_partidas, ranked } = data
  const pct = objetivo.porcentaje_dia

  const limite  = objetivo.limite_dia
  const maxHoras = Math.max(...(semana.dias.map(d => parseFloat(d.horas))), limite, 0.1)

  const today    = new Date()
  const weekBars = Array.from({ length: 7 }, (_, i) => {
    const d    = new Date(today)
    d.setDate(today.getDate() - today.getDay() + i + 1)
    const key  = d.toISOString().slice(0, 10)
    const found = semana.dias.find(r => r.fecha === key)
    return { dia: DIAS[i], horas: found ? parseFloat(found.horas) : 0, fecha: key }
  })

  return (
    <div>
      {/* Cabecera */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 26, marginBottom: 4 }}>
            Hola, {data.nombre}
            <span style={{ color: 'var(--muted)', fontWeight: 400, fontSize: 16 }}>
              {' '}#{data.tag}
            </span>
          </h1>
          <p style={{ color: 'var(--muted)', fontSize: 14 }}>
            {new Date().toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' })}
            {ranked?.tier && (
              <span style={{ marginLeft: 12, color: 'var(--accent)', fontWeight: 500 }}>
                · {ranked.tier} {ranked.division} — {ranked.lp} LP
              </span>
            )}
          </p>
        </div>

        {/* Botón de sincronización */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
          <button
            className="btn btn-sm"
            onClick={handleSync}
            disabled={syncing}
            style={{ minWidth: 130 }}
          >
            {syncing
              ? <><div className="spinner" style={{ width: 12, height: 12 }} /> Sincronizando...</>
              : '↻ Actualizar'}
          </button>
          {syncMsg && (
            <span style={{
              fontSize: 12,
              color: syncMsg.type === 'error' ? 'var(--danger)'
                   : syncMsg.type === 'ok'    ? 'var(--success)'
                   : 'var(--muted)',
            }}>
              {syncMsg.text}
            </span>
          )}
        </div>
      </div>

      {/* Stats principales */}
      <div className="stat-grid">
        <div className="stat-card">
          <div className={`val val-${objetivo.estado_dia === 'ok' ? 'ok' : objetivo.estado_dia === 'warning' ? 'warn' : 'danger'}`}>
            {fmt(hoy.horas)}
          </div>
          <div className="lbl">jugadas hoy</div>
        </div>
        <div className="stat-card">
          <div className="val val-accent">{fmt(objetivo.limite_dia)}</div>
          <div className="lbl">tu límite diario</div>
        </div>
        <div className="stat-card">
          <div className={`val ${semana.porcentaje >= 100 ? 'val-danger' : semana.porcentaje >= 80 ? 'val-warn' : 'val-ok'}`}>
            {fmt(semana.horas)}
          </div>
          <div className="lbl">esta semana</div>
        </div>
        <div className="stat-card">
          <div className="val val-accent">{racha}</div>
          <div className="lbl">días de racha</div>
        </div>
      </div>

      {/* Barra progreso diario */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <span style={{ fontSize: 14, fontWeight: 500 }}>Progreso de hoy</span>
          <span style={{ fontSize: 14, color: BarColor(pct), fontWeight: 500 }}>{pct.toFixed(0)}%</span>
        </div>
        <div className="progress-wrap" style={{ height: 10 }}>
          <div className="progress-fill" style={{ width: `${Math.min(pct, 100)}%`, background: BarColor(pct) }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 12, color: 'var(--muted)' }}>
          <span>{fmt(hoy.horas)} jugadas</span>
          <span>{fmt(Math.max(0, objetivo.limite_dia - hoy.horas))} restantes</span>
        </div>
        {hoy.partidas > 0 && (
          <div style={{ display: 'flex', gap: 16, marginTop: 14, fontSize: 13, color: 'var(--muted)' }}>
            <span>{hoy.partidas} partidas</span>
            {hoy.rendiciones > 0 && <span style={{ color: 'var(--warning)' }}>🏳 {hoy.rendiciones} rendici{hoy.rendiciones === 1 ? 'ón' : 'ones'} prop{hoy.rendiciones === 1 ? 'ia' : 'ias'}</span>}
            {hoy.afks > 0        && <span style={{ color: 'var(--danger)'  }}>💤 {hoy.afks} AFK</span>}
            {hoy.campeon         && <span>· {hoy.campeon}</span>}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>

        {/* Barras semanales */}
        <div className="card">
          <p className="section-title">Esta semana</p>
          <div className="week-bars">
            {weekBars.map(({ dia, horas }) => {
              const pctBar = maxHoras > 0 ? (horas / maxHoras) * 100 : 0
              return (
                <div key={dia} className="week-bar-wrap">
                  <div className="week-bar" style={{
                    height:     `${Math.max(pctBar, 4)}%`,
                    background: horas > limite ? 'var(--danger)' : horas > 0 ? 'var(--success)' : 'var(--bg)',
                    border:     horas === 0 ? '1px solid var(--border)' : 'none',
                  }} />
                  <span className="week-bar-lbl">{dia}</span>
                </div>
              )
            })}
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
            Total: <strong style={{ color: 'var(--text)' }}>{fmt(semana.horas)}</strong>
            {objetivo.limite_semana > 0 && ` de ${fmt(objetivo.limite_semana)}`}
          </div>
          {/* Comparativa vs semana anterior */}
          {semana.anterior >= 0 && (() => {
            const diff = semana.horas - semana.anterior
            if (Math.abs(diff) < 0.08) return (
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 6 }}>
                → Igual que la semana pasada ({fmt(semana.anterior)})
              </div>
            )
            const mejor = diff < 0
            const color = mejor ? 'var(--success)' : diff > 1 ? 'var(--danger)' : 'var(--warning)'
            return (
              <div style={{ fontSize: 12, color, marginTop: 6, fontWeight: 500 }}>
                {mejor ? '↓' : '↑'} {fmt(Math.abs(diff))} {mejor ? 'menos' : 'más'} que la semana pasada
                <span style={{ color: 'var(--muted)', fontWeight: 400 }}> ({fmt(semana.anterior)})</span>
              </div>
            )
          })()}
        </div>

        {/* Últimas partidas */}
        <div className="card">
          <p className="section-title">Últimas partidas</p>
          {ultimas_partidas.length === 0 ? (
            <p style={{ color: 'var(--muted)', fontSize: 14 }}>No hay partidas registradas aún.</p>
          ) : (
            <div>
              {ultimas_partidas.map((p, i) => (
                <div key={i} style={{
                  display:        'flex',
                  justifyContent: 'space-between',
                  alignItems:     'center',
                  padding:        '9px 0',
                  borderBottom:   i < ultimas_partidas.length - 1 ? '1px solid var(--border)' : 'none',
                }}>
                  <div>
                    <span style={{ fontSize: 14, fontWeight: 500 }}>{p.campeon}</span>
                    <span style={{ fontSize: 12, color: 'var(--muted)', marginLeft: 8 }}>{p.modo}</span>
                    {p.rendicion_negativa && <span style={{ fontSize: 11, marginLeft: 6 }} title="Tu equipo rindió">🏳</span>}
                    {p.rendicion_positiva && <span style={{ fontSize: 11, marginLeft: 6 }} title="El rival rindió">🤝</span>}
                    {p.afk       && <span style={{ fontSize: 11, marginLeft: 4 }}>💤</span>}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 12, color: 'var(--muted)' }}>KDA {p.kda.toFixed(1)}</span>
                    <span className={`badge badge-${p.resultado === 'Victoria' ? 'v' : 'd'}`}>
                      {p.resultado}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Racha */}
      {racha > 0 && (
        <div className="streak-banner">
          <div className="streak-num">{racha}</div>
          <div className="streak-info">
            <h3>día{racha !== 1 ? 's' : ''} cumpliendo tu objetivo</h3>
            <p>
              {racha >= racha_maxima && racha > 1
                ? '¡Es tu récord personal! Sigue así.'
                : `Récord personal: ${racha_maxima} días`}
            </p>
          </div>
        </div>
      )}

      {/* Señales de comportamiento */}
      {behavior?.señales_comportamiento?.length > 0 && (
        <div className="card">
          <p className="section-title" style={{ marginBottom: 16 }}>Señales a tener en cuenta</p>
          {behavior.señales_comportamiento.map((s, i) => (
            <div key={i} className={`signal ${s.nivel}`}>
              <div className="signal-dot" />
              <p>{s.mensaje}</p>
            </div>
          ))}
        </div>
      )}

      {/* Modal de tilt */}
      {showTiltModal && tiltType && (() => {
        const c = TILT_CONTENT[tiltType]
        return (
          <div className="modal-overlay" onClick={dismissTilt}>
            <div className="modal-card tilt-modal" onClick={e => e.stopPropagation()}>
              <div className="tilt-modal-icon">{c.icon}</div>
              <h2>{c.title}</h2>
              <p>{c.body}</p>
              <p className="tilt-sub">
                Esto no es un juicio — es exactamente la razón por la que instalaste LolHelper.
              </p>
              <div className="tilt-actions">
                <button
                  className="btn btn-primary"
                  style={{ flex: 1 }}
                  onClick={dismissTilt}
                >
                  Tomar un descanso
                </button>
                <button
                  className="btn"
                  style={{ flex: 1, fontSize: 13 }}
                  onClick={dismissTilt}
                >
                  Seguir jugando de todas formas
                </button>
              </div>
            </div>
          </div>
        )
      })()}
    </div>
  )
}
