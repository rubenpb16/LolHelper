import { useEffect, useState } from 'react'
import { historial } from '../api'

const PAGE_SIZE      = 50
const DAYS_PAGE_SIZE = 7

function fmt(horas) {
  const h = Math.floor(horas)
  const m = Math.round((horas - h) * 60)
  if (h === 0) return `${m}min`
  if (m === 0) return `${h}h`
  return `${h}h ${m}min`
}

function toISOLocal(d) {
  return d.toISOString().slice(0, 10)
}

export default function Historial() {
  const today = toISOLocal(new Date())

  const [data,          setData]          = useState(null)
  const [dias,          setDias]          = useState(30)
  const [page,          setPage]          = useState(0)
  const [daysPage,      setDaysPage]      = useState(0)    // paginación días excedidos
  const [loading,       setLoading]       = useState(true)
  const [loadingFilter, setLoadingFilter] = useState(false)
  const [error,         setError]         = useState('')

  // Rango de fechas personalizado
  const [customFrom,  setCustomFrom]  = useState('')
  const [customTo,    setCustomTo]    = useState('')
  const [useCustom,   setUseCustom]   = useState(false)

  async function load(params) {
    if (!data) setLoading(true)
    else       setLoadingFilter(true)
    setError('')
    try {
      const res = await historial.get(params)
      setData(res.data)
    } catch {
      setError('No se pudieron cargar los datos. Inténtalo de nuevo.')
    } finally {
      setLoading(false)
      setLoadingFilter(false)
    }
  }

  useEffect(() => {
    if (useCustom) {
      load({ fecha_inicio: customFrom, fecha_fin: customTo, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
    } else {
      load({ dias, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
    }
  }, [dias, page, useCustom, customFrom, customTo])

  function handleDiasChange(d) {
    setUseCustom(false)
    setPage(0)
    setDaysPage(0)
    setDias(d)
  }

  function applyCustomRange() {
    if (!customFrom || !customTo || customFrom > customTo) return
    setUseCustom(true)
    setPage(0)
    setDaysPage(0)
  }

  function clearCustomRange() {
    setCustomFrom('')
    setCustomTo('')
    setUseCustom(false)
    setPage(0)
    setDaysPage(0)
  }

  const customRangeValid = customFrom && customTo && customFrom <= customTo

  const res        = data?.resumen || {}
  const total      = data?.total   ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)
  const wr         = res.total_partidas > 0
    ? Math.round(res.victorias / res.total_partidas * 100) : 0

  // Paginación client-side de días excedidos
  const diasExcedidos    = data?.dias_excedidos ?? []
  const totalDaysPages   = Math.ceil(diasExcedidos.length / DAYS_PAGE_SIZE)
  const diasExcedidosPag = diasExcedidos.slice(daysPage * DAYS_PAGE_SIZE, (daysPage + 1) * DAYS_PAGE_SIZE)

  if (loading) return <div className="loader"><div className="spinner" /> Cargando...</div>

  return (
    <div>
      {/* ── Cabecera + filtros ── */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
          <h1 style={{ fontSize: 26 }}>Historial</h1>
          {loadingFilter && <div className="spinner" style={{ width: 16, height: 16 }} />}
        </div>

        {/* Selector rápido de días */}
        <div className="days-selector" style={{ marginBottom: 12 }}>
          {[7, 14, 30, 60, 90].map(d => (
            <button key={d}
              className={!useCustom && dias === d ? 'active' : ''}
              onClick={() => handleDiasChange(d)}
              disabled={loadingFilter}
            >
              {d} días
            </button>
          ))}
        </div>

        {/* Selector de rango personalizado */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, color: 'var(--muted)' }}>O elige un rango:</span>
          <input
            type="date" max={today}
            value={customFrom}
            onChange={e => { setCustomFrom(e.target.value); setUseCustom(false) }}
            style={dateInputStyle}
          />
          <span style={{ fontSize: 13, color: 'var(--muted)' }}>—</span>
          <input
            type="date" max={today} min={customFrom || undefined}
            value={customTo}
            onChange={e => { setCustomTo(e.target.value); setUseCustom(false) }}
            style={dateInputStyle}
          />
          {customRangeValid && !useCustom && (
            <button
              className="btn btn-sm btn-primary"
              onClick={applyCustomRange}
              disabled={loadingFilter}
            >
              Aplicar
            </button>
          )}
          {useCustom && (
            <button className="btn btn-sm" onClick={clearCustomRange}>
              × Limpiar
            </button>
          )}
        </div>

        {useCustom && (
          <p style={{ fontSize: 12, color: 'var(--accent)', marginTop: 8 }}>
            Mostrando del {new Date(customFrom + 'T00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })} al {new Date(customTo + 'T00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}
          </p>
        )}
      </div>

      {error && <div className="error-banner" style={{ marginBottom: 24 }}>{error}</div>}

      {data && (
        <div style={{ opacity: loadingFilter ? 0.5 : 1, transition: 'opacity .2s' }}>
          {/* Resumen */}
          <div className="stat-grid" style={{ marginBottom: 24 }}>
            <div className="stat-card">
              <div className="val">{fmt(parseFloat(res.total_horas || 0))}</div>
              <div className="lbl">tiempo total</div>
            </div>
            <div className="stat-card">
              <div className="val">{total}</div>
              <div className="lbl">partidas</div>
            </div>
            <div className="stat-card">
              <div className={`val ${wr >= 50 ? 'val-ok' : 'val-danger'}`}>{wr}%</div>
              <div className="lbl">winrate</div>
            </div>
            <div className="stat-card">
              <div className="val val-accent">{parseFloat(res.kda_avg || 0).toFixed(2)}</div>
              <div className="lbl">KDA promedio</div>
            </div>
            <div className="stat-card">
              <div className="val val-warn">{res.dias_jugados || 0}</div>
              <div className="lbl">días jugados</div>
            </div>
            <div className="stat-card">
              <div className={`val ${res.rendiciones > 5 ? 'val-danger' : 'val-warn'}`}>
                {res.rendiciones || 0}
              </div>
              <div className="lbl">rendiciones propias 🏳</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>

            {/* Días que superaron el límite */}
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                <p className="section-title" style={{ marginBottom: 0 }}>
                  Días que superaste el límite
                </p>
                {diasExcedidos.length > 0 && (
                  <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                    {diasExcedidos.length} día{diasExcedidos.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>

              {diasExcedidos.length === 0 ? (
                <div className="empty" style={{ padding: 24 }}>
                  <p style={{ color: 'var(--success)' }}>¡Ninguno en este período!</p>
                </div>
              ) : (
                <>
                  {diasExcedidosPag.map((d, i) => (
                    <div key={i} style={{ padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{ fontSize: 14, fontWeight: 500 }}>
                          {new Date(d.fecha + 'T00:00').toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' })}
                        </span>
                        <span style={{ color: 'var(--danger)', fontSize: 14, fontWeight: 500 }}>
                          {fmt(parseFloat(d.horas))}
                        </span>
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--muted)', display: 'flex', gap: 12 }}>
                        <span>{d.partidas} partidas</span>
                        {d.rendiciones > 0 && <span>🏳 {d.rendiciones} rend.</span>}
                        {d.afks > 0        && <span>💤 {d.afks} AFK</span>}
                        {d.campeon         && <span>· {d.campeon}</span>}
                      </div>
                    </div>
                  ))}

                  {totalDaysPages > 1 && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
                      <button
                        className="btn btn-sm"
                        onClick={() => setDaysPage(p => p - 1)}
                        disabled={daysPage === 0}
                      >← Ant.</button>
                      <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                        {daysPage + 1}/{totalDaysPages}
                      </span>
                      <button
                        className="btn btn-sm"
                        onClick={() => setDaysPage(p => p + 1)}
                        disabled={daysPage >= totalDaysPages - 1}
                      >Sig. →</button>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Campeones más jugados */}
            <div className="card">
              <p className="section-title">Campeones más jugados</p>
              {data.por_campeon?.map((c, i) => {
                const wrC = Math.round(c.victorias / c.partidas * 100)
                return (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '10px 0', borderBottom: '1px solid var(--border)',
                  }}>
                    <div style={{
                      width: 32, height: 32, background: 'var(--bg3)',
                      borderRadius: 6, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', fontSize: 11, fontWeight: 700,
                      color: 'var(--accent)', flexShrink: 0,
                    }}>
                      {c.campeon?.slice(0, 2).toUpperCase()}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 2 }}>{c.campeon}</div>
                      <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                        {c.partidas} partidas · KDA {parseFloat(c.kda_avg).toFixed(1)} · {fmt(parseFloat(c.horas))}
                      </div>
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 500, color: wrC >= 50 ? 'var(--success)' : 'var(--danger)' }}>
                      {wrC}%
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Tabla de partidas */}
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <p className="section-title" style={{ marginBottom: 0 }}>Partidas ({total})</p>
              {totalPages > 1 && (
                <span style={{ fontSize: 13, color: 'var(--muted)' }}>
                  {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} de {total}
                </span>
              )}
            </div>

            {data.partidas?.length === 0 ? (
              <div className="empty">
                <h3>Sin partidas</h3>
                <p>No hay partidas registradas en el período seleccionado</p>
              </div>
            ) : (
              <>
                <div style={{ overflowX: 'auto' }}>
                  <table className="match-table">
                    <thead>
                      <tr>
                        <th>Fecha</th><th>Campeón</th><th>Modo</th><th>Resultado</th>
                        <th>KDA</th><th>Duración</th><th>CS/min</th><th>Notas</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.partidas.map((p, i) => (
                        <tr key={i}>
                          <td style={{ color: 'var(--muted)', fontSize: 13 }}>
                            {new Date(p.fecha + 'T00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}
                            {' '}<span style={{ opacity: .6 }}>{p.hora}</span>
                          </td>
                          <td style={{ fontWeight: 500 }}>{p.campeon}</td>
                          <td style={{ color: 'var(--muted)', fontSize: 13 }}>{p.modo}</td>
                          <td>
                            <span className={`badge badge-${p.resultado === 'Victoria' ? 'v' : 'd'}`}>
                              {p.resultado}
                            </span>
                          </td>
                          <td style={{ fontWeight: 500 }}>{p.kda.toFixed(2)}</td>
                          <td style={{ color: 'var(--muted)' }}>{fmt(p.duracion_min / 60)}</td>
                          <td style={{ color: 'var(--muted)' }}>{p.cs_min?.toFixed(1)}</td>
                          <td style={{ fontSize: 13 }}>
                            {p.rendicion_negativa && <span title="Tu equipo rindió">🏳</span>}
                            {p.rendicion_positiva && <span title="El rival rindió">🤝</span>}
                            {p.afk                && <span title="AFK">💤</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {totalPages > 1 && (
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, marginTop: 20 }}>
                    <button className="btn btn-sm" onClick={() => setPage(p => p - 1)} disabled={page === 0 || loadingFilter}>
                      ← Anterior
                    </button>
                    <span style={{ fontSize: 13, color: 'var(--muted)' }}>Página {page + 1} de {totalPages}</span>
                    <button className="btn btn-sm" onClick={() => setPage(p => p + 1)} disabled={page >= totalPages - 1 || loadingFilter}>
                      Siguiente →
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

const dateInputStyle = {
  background:   'var(--bg3)',
  border:       '1px solid var(--border2)',
  borderRadius: 'var(--radius)',
  padding:      '6px 10px',
  color:        'var(--text)',
  fontSize:     13,
  colorScheme:  'dark',
}
