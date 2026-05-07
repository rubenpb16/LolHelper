import { Link, useNavigate, useLocation } from 'react-router-dom'
import { proAuth } from '../../api'

const LINKS = [
  { to: '/pro/dashboard', label: 'Pacientes' },
]

export default function ProNavbar({ user }) {
  const navigate  = useNavigate()
  const { pathname } = useLocation()

  async function handleLogout() {
    try { await proAuth.logout() } catch {}
    localStorage.removeItem('pro_user')
    navigate('/pro/login')
  }

  return (
    <nav style={s.nav}>
      <div style={s.left}>
        <span style={s.logo}>LolHelper <span style={s.badge}>Pro</span></span>
        <div style={s.links}>
          {LINKS.map(l => (
            <Link key={l.to} to={l.to} style={{
              ...s.link,
              ...(pathname.startsWith(l.to) ? s.linkActive : {}),
            }}>
              {l.label}
            </Link>
          ))}
        </div>
      </div>
      <div style={s.right}>
        {user && (
          <span style={s.name}>
            {user.nombre} {user.apellidos}
          </span>
        )}
        <button style={s.logout} onClick={handleLogout}>Cerrar sesión</button>
      </div>
    </nav>
  )
}

const s = {
  nav:       { background: '#fff', borderBottom: '1px solid #e2e8f0', padding: '0 32px', height: 60, display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontFamily: "'DM Sans', sans-serif", position: 'sticky', top: 0, zIndex: 50 },
  left:      { display: 'flex', alignItems: 'center', gap: 32 },
  logo:      { fontFamily: "'Syne', sans-serif", fontSize: 18, fontWeight: 700, color: '#2563eb' },
  badge:     { background: '#dbeafe', color: '#1d4ed8', fontSize: 11, fontWeight: 700, padding: '2px 7px', borderRadius: 5, marginLeft: 5, verticalAlign: 'middle' },
  links:     { display: 'flex', gap: 4 },
  link:      { padding: '6px 14px', borderRadius: 8, fontSize: 14, color: '#64748b', fontWeight: 500, textDecoration: 'none', transition: 'all .15s' },
  linkActive:{ background: '#eff6ff', color: '#2563eb' },
  right:     { display: 'flex', alignItems: 'center', gap: 16 },
  name:      { fontSize: 13, color: '#64748b' },
  logout:    { padding: '7px 14px', borderRadius: 8, background: 'transparent', border: '1px solid #e2e8f0', color: '#64748b', fontSize: 13, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif" },
}
