import { useEffect, useState } from 'react'
import { tft } from '../api'

const TFT_GOLD = '#c89b3c'

function fmt(h) {
  const hh = Math.floor(h), m = Math.round((h - hh) * 60)
  if (hh === 0) return `${m}min`; if (m === 0) return `${hh}h`; return `${hh}h ${m}min`
}

function PlacementBadge({ placement }) {
  const colors = {
    1: { bg: '#ffd700', color: '#1a1a1a' },
    2: { bg: '#c0c0c0', color: '#1a1a1a' },
    3: { bg: '#cd7f32', color: '#fff' },
    4: { bg: 'rgba(52,211,153,.2)', color: '#34d399' },
  }
  const c = colors[placement] || { bg: 'rgba(248,113,113,.15)', color: '#f87171' }
  return (
    <span style={{ ...c, padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 700 }}>
      #{placement}
    </span>
  )
}

const dateInputStyle = {
  background: 'var(--bg3)', border: '1px solid var(--border2)',
  borderRadius: 'var(--radius)', padding: '6px 10px',
  color: 'var(--text)', fontSize: 13, colorScheme: 'dark',
}

export default function TftHistorial() {
  const today = new Date().toISOString().slice(0, 10)

  const [data,       setData]       = useState(null)
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState('')
  const [dias,       setDias]       = useState(30)
  const [customFrom, setCustomFrom] = useState('')
  const [customTo,   setCustomTo]   = useState('')
  const [useCustom,  setUseCustom]  = useState(false)
  const [offset,     setOffset]     = useState(0)
  const LIMIT = 50

  async function load(params) {
    setLoading(true); setError('')
    try {
      const r = await tft.historial({ ...params, limit: LIMIT, offset })
      setData(r.data)
    } catch { setError('No se pudo cargar el historial TFT') }
    finally { setLoading(false) }
  }

  useEffect(() => {
    if (useCustom && customFrom && customTo) load({ fecha_inicio: customFrom, fecha_fin: customTo })
    else load({ dias })
  }, [dias, useCustom, customFrom, customTo, offset])

  const customValid = customFrom && customTo && customFrom <= customTo

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 26, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ color: TFT_GOLD }}>♟</span> Historial TFT
          </h1>
          <div className="days-selector" style={{ marginBottom: 10 }}>
            {[7, 30, 60, 90].map(d => (
              <button key={d} className={!useCustom && dias === d ? 'active' : ''}
                onClick={() => { setUseCustom(false); setDias(d); setOffset(0) }}
                style={{ '--active-bg': TFT_GOLD }}>
                {d} días
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, color: 'var(--muted)' }}>Rango:</span>
            <input type="date" max={today} value={customFrom} style={dateInputStyle}
              onChange={e => { setCustomFrom(e.target.value); setUseCustom(false) }} />
            <span style={{ fontSize: 13, color: 'var(--muted)' }}>—</span>
            <input type="date" max={today} min={customFrom || undefined} value={customTo} style={dateInputStyle}
              onChange={e => { setCustomTo(e.target.value); setUseCustom(false) }} />
            {customValid && !useCustom && (
              <button className="btn btn-sm btn-primary" onClick={() => { setUseCustom(true); setOffset(0) }}>Aplicar</button>
            )}
            {useCustom && (
              <button className="btn btn-sm" onClick={() => { setCustomFrom(''); setCustomTo(''); setUseCustom(false) }}>× Limpiar</button>
            )}
          </div>
        </div>
      </div>

      {loading && <div className="loader"><div className="spinner" /> Cargando...</div>}
      {error   && <div className="error-banner">{error}</div>}

      {!loading && data && (
        <>
          {/* Resumen período */}
          {data.resumen && (
            <div className="stat-grid" style={{ marginBottom: 24 }}>
              {[
                { val: data.resumen.total_partidas,           lbl: 'Partidas',       color: 'var(--text)' },
                { val: `#${data.resumen.avg_placement}`,      lbl: 'Placement medio',color: data.resumen.avg_placement <= 4 ? 'var(--success)' : 'var(--warning)' },
                { val: `${data.resumen.top4_rate}%`,          lbl: 'Top4 rate',      color: data.resumen.top4_rate >= 50 ? 'var(--success)' : 'var(--warning)' },
                { val: fmt(data.resumen.horas_total),         lbl: 'Tiempo total',   color: TFT_GOLD },
                { val: data.resumen.primeros,                 lbl: '1er puesto',     color: '#ffd700' },
              ].map((st, i) => (
                <div className="stat-card" key={i}>
                  <div style={{ fontSize: 22, fontWeight: 700, color: st.color, fontFamily: "'Syne', sans-serif", lineHeight: 1, marginBottom: 6 }}>{st.val}</div>
                  <div className="lbl">{st.lbl}</div>
                </div>
              ))}
            </div>
          )}

          {/* Tabla */}
          {data.partidas.length === 0
            ? <div className="empty"><h3>Sin partidas en este período</h3></div>
            : (
              <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <table className="match-table">
                  <thead>
                    <tr>
                      {['Fecha', 'Modo', 'Puesto', 'Resultado', 'Duración', 'Parche'].map(h => (
                        <th key={h}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.partidas.map((p, i) => (
                      <tr key={i}>
                        <td>{p.fecha} <span style={{ color: 'var(--muted)', fontSize: 12 }}>{p.hora}</span></td>
                        <td style={{ color: 'var(--muted)' }}>{p.modo}</td>
                        <td><PlacementBadge placement={p.placement} /></td>
                        <td>
                          <span className={`badge badge-${p.top4 ? 'v' : 'd'}`}>
                            {p.top4 ? 'Top4' : 'Bot4'}
                          </span>
                        </td>
                        <td style={{ color: 'var(--muted)' }}>{fmt(p.duracion_min / 60)}</td>
                        <td style={{ color: 'var(--muted)', fontSize: 12 }}>{p.parche}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

          {/* Paginación */}
          {data.total > LIMIT && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 20 }}>
              <button className="btn btn-sm" disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - LIMIT))}>← Anterior</button>
              <span style={{ fontSize: 13, color: 'var(--muted)', padding: '7px 0' }}>
                {Math.floor(offset / LIMIT) + 1} / {Math.ceil(data.total / LIMIT)}
              </span>
              <button className="btn btn-sm" disabled={offset + LIMIT >= data.total}
                onClick={() => setOffset(offset + LIMIT)}>Siguiente →</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
