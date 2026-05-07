import { useEffect, useState } from 'react'
import { useNavigate }          from 'react-router-dom'
import ProNavbar                from './ProNavbar'
import { proPacientes }         from '../../api'

const ESTADOS = {
  evaluacion:        { label: 'Evaluación',        color: '#f59e0b', bg: '#fffbeb' },
  tratamiento_activo:{ label: 'Tratamiento activo', color: '#2563eb', bg: '#eff6ff' },
  seguimiento:       { label: 'Seguimiento',         color: '#8b5cf6', bg: '#f5f3ff' },
  alta:              { label: 'Alta',                color: '#059669', bg: '#ecfdf5' },
}

function badge(estado) {
  const e = ESTADOS[estado] || { label: estado, color: '#64748b', bg: '#f1f5f9' }
  return (
    <span style={{
      background: e.bg, color: e.color, border: `1px solid ${e.color}44`,
      borderRadius: 6, padding: '3px 10px', fontSize: 12, fontWeight: 600,
    }}>{e.label}</span>
  )
}

export default function ProDashboard() {
  const navigate   = useNavigate()
  const proUser    = JSON.parse(localStorage.getItem('pro_user') || '{}')
  const [pacientes, setPacientes] = useState([])
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState('')
  const [filtro,    setFiltro]    = useState('todos')
  const [busqueda,  setBusqueda]  = useState('')
  const [linkCopiado, setLinkCopiado] = useState(false)

  useEffect(() => {
    proPacientes.lista()
      .then(r => setPacientes(r.data.pacientes))
      .catch(() => setError('No se pudieron cargar los pacientes'))
      .finally(() => setLoading(false))
  }, [])

  const invitacionUrl = `${window.location.origin}/invitacion/${proUser.link_token}`

  function copiarLink() {
    navigator.clipboard.writeText(invitacionUrl)
    setLinkCopiado(true)
    setTimeout(() => setLinkCopiado(false), 2500)
  }

  const filtrados = pacientes
    .filter(p => filtro === 'todos' || p.estado_tratamiento === filtro)
    .filter(p => !busqueda || `${p.riot_game_name} ${p.email}`.toLowerCase().includes(busqueda.toLowerCase()))

  const counts = pacientes.reduce((acc, p) => {
    acc[p.estado_tratamiento] = (acc[p.estado_tratamiento] || 0) + 1
    return acc
  }, {})

  if (loading) return (
    <div style={s.page}>
      <ProNavbar user={proUser} />
      <div style={s.center}>Cargando pacientes...</div>
    </div>
  )

  return (
    <div style={s.page}>
      <ProNavbar user={proUser} />

      <div style={s.content}>
        {/* Cabecera */}
        <div style={s.header}>
          <div>
            <h1 style={s.h1}>Mis pacientes</h1>
            <p style={s.sub}>{pacientes.length} paciente{pacientes.length !== 1 ? 's' : ''} en total</p>
          </div>

          {/* Link de invitación */}
          <div style={s.invBox}>
            <p style={s.invLabel}>Tu enlace de invitación</p>
            <div style={s.invRow}>
              <span style={s.invUrl}>{invitacionUrl}</span>
              <button style={{ ...s.invBtn, background: linkCopiado ? '#059669' : '#2563eb' }} onClick={copiarLink}>
                {linkCopiado ? '✓ Copiado' : 'Copiar'}
              </button>
            </div>
            <p style={s.invHint}>Envía este enlace a tus pacientes para vincularlos a tu cuenta</p>
          </div>
        </div>

        {error && <div style={s.error}>{error}</div>}

        {/* Stats rápidas */}
        <div style={s.statsGrid}>
          {Object.entries(ESTADOS).map(([k, e]) => (
            <div key={k} style={{ ...s.statCard, borderTopColor: e.color }}>
              <div style={{ fontSize: 24, fontWeight: 700, color: e.color }}>{counts[k] || 0}</div>
              <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>{e.label}</div>
            </div>
          ))}
        </div>

        {/* Filtros */}
        <div style={s.toolbar}>
          <div style={s.tabs}>
            {[['todos', 'Todos'], ...Object.entries(ESTADOS).map(([k, e]) => [k, e.label])].map(([k, l]) => (
              <button key={k}
                style={{ ...s.tab, ...(filtro === k ? s.tabActive : {}) }}
                onClick={() => setFiltro(k)}>
                {l}{k !== 'todos' && counts[k] ? ` (${counts[k]})` : ''}
              </button>
            ))}
          </div>
          <input style={s.search} placeholder="Buscar paciente..." value={busqueda}
            onChange={e => setBusqueda(e.target.value)} />
        </div>

        {/* Tabla de pacientes */}
        {filtrados.length === 0 ? (
          <div style={s.empty}>
            {pacientes.length === 0
              ? 'Aún no tienes pacientes. Comparte tu enlace de invitación para empezar.'
              : 'No hay pacientes que coincidan con los filtros.'}
          </div>
        ) : (
          <div style={s.tableWrap}>
            <table style={s.table}>
              <thead>
                <tr>
                  {['Paciente', 'Estado', 'Horas / semana', 'Última partida', 'Sincronizado', ''].map(h => (
                    <th key={h} style={s.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtrados.map(p => (
                  <tr key={p.id} style={s.tr}
                    onClick={() => navigate(`/pro/pacientes/${p.id}`)}
                  >
                    <td style={s.td}>
                      <div style={{ fontWeight: 600, color: '#1e293b' }}>{p.riot_game_name}<span style={{ color: '#94a3b8', fontWeight: 400 }}>#{p.riot_tag_line}</span></div>
                      <div style={{ fontSize: 12, color: '#94a3b8' }}>{p.email}</div>
                    </td>
                    <td style={s.td}>{badge(p.estado_tratamiento)}</td>
                    <td style={s.td}>
                      <span style={{ color: p.horas_semana > 14 ? '#dc2626' : p.horas_semana > 7 ? '#d97706' : '#059669', fontWeight: 600 }}>
                        {p.horas_semana.toFixed(1)}h
                      </span>
                    </td>
                    <td style={s.td}>
                      {p.ultima_partida
                        ? new Date(p.ultima_partida + 'T00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })
                        : <span style={{ color: '#94a3b8' }}>Sin datos</span>}
                    </td>
                    <td style={s.td}>
                      <span style={{ color: p.sincronizado ? '#059669' : '#f59e0b', fontSize: 12, fontWeight: 600 }}>
                        {p.sincronizado ? '● Activo' : '○ Pendiente'}
                      </span>
                    </td>
                    <td style={s.td}>
                      <button style={s.verBtn} onClick={e => { e.stopPropagation(); navigate(`/pro/pacientes/${p.id}`) }}>
                        Ver →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

const s = {
  page:       { minHeight: '100vh', background: '#f0f4f8', fontFamily: "'DM Sans', sans-serif" },
  content:    { maxWidth: 1100, margin: '0 auto', padding: '32px 24px' },
  header:     { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28, flexWrap: 'wrap', gap: 20 },
  h1:         { fontFamily: "'Syne', sans-serif", fontSize: 26, fontWeight: 700, color: '#1e293b', marginBottom: 4 },
  sub:        { fontSize: 14, color: '#64748b' },
  invBox:     { background: '#fff', borderRadius: 12, padding: '16px 20px', border: '1px solid #e2e8f0', maxWidth: 480 },
  invLabel:   { fontSize: 12, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: .6, marginBottom: 8 },
  invRow:     { display: 'flex', gap: 8, alignItems: 'center' },
  invUrl:     { flex: 1, fontSize: 12, color: '#2563eb', background: '#eff6ff', padding: '6px 10px', borderRadius: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  invBtn:     { padding: '6px 14px', borderRadius: 6, border: 'none', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif", flexShrink: 0, transition: 'background .2s' },
  invHint:    { fontSize: 11, color: '#94a3b8', marginTop: 6 },
  error:      { background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '12px 16px', fontSize: 14, color: '#dc2626', marginBottom: 20 },
  statsGrid:  { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 },
  statCard:   { background: '#fff', borderRadius: 10, padding: '16px 20px', border: '1px solid #e2e8f0', borderTop: '3px solid', textAlign: 'center' },
  toolbar:    { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, gap: 16, flexWrap: 'wrap' },
  tabs:       { display: 'flex', gap: 4 },
  tab:        { padding: '6px 14px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', color: '#64748b', fontSize: 13, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif" },
  tabActive:  { background: '#eff6ff', borderColor: '#2563eb', color: '#2563eb', fontWeight: 600 },
  search:     { padding: '8px 14px', borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 14, width: 220, fontFamily: "'DM Sans', sans-serif", outline: 'none' },
  empty:      { background: '#fff', borderRadius: 12, padding: 48, textAlign: 'center', color: '#64748b', fontSize: 15, border: '1px solid #e2e8f0' },
  tableWrap:  { background: '#fff', borderRadius: 12, border: '1px solid #e2e8f0', overflow: 'hidden' },
  table:      { width: '100%', borderCollapse: 'collapse' },
  th:         { padding: '12px 16px', fontSize: 11, color: '#94a3b8', textAlign: 'left', textTransform: 'uppercase', letterSpacing: .7, borderBottom: '1px solid #e2e8f0', fontWeight: 600 },
  tr:         { cursor: 'pointer', transition: 'background .12s' },
  td:         { padding: '14px 16px', fontSize: 14, borderBottom: '1px solid #f1f5f9', color: '#334155' },
  verBtn:     { padding: '6px 14px', borderRadius: 7, background: '#eff6ff', border: 'none', color: '#2563eb', fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif' "},
  center:     { display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300, color: '#64748b' },
}
