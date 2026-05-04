import { NavLink, useNavigate } from 'react-router-dom'
import { auth } from '../api'

const links = [
  { to: '/dashboard', label: 'Dashboard', icon: '▦' },
  { to: '/historial', label: 'Historial', icon: '◷' },
  { to: '/analisis',  label: 'Análisis',  icon: '◈' },
  { to: '/objetivo',  label: 'Objetivo',  icon: '◎' },
  { to: '/cuenta',    label: 'Cuenta',    icon: '◯' },
]

export default function Navbar() {
  const navigate = useNavigate()
  const user     = JSON.parse(localStorage.getItem('user') || '{}')

  async function logout() {
    try { await auth.logout() } catch {}
    localStorage.removeItem('user')
    navigate('/login')
  }

  return (
    <nav style={{
      background:    'var(--bg2)',
      borderRight:   '1px solid var(--border)',
      display:       'flex',
      flexDirection: 'column',
      padding:       '28px 0',
      height:        '100vh',
      position:      'sticky',
      top:           0,
    }}>
      {/* Logo */}
      <div style={{ padding: '0 24px 28px', borderBottom: '1px solid var(--border)' }}>
        <div style={{
          fontFamily:   'Syne, sans-serif',
          fontSize:     '18px',
          fontWeight:   '700',
          color:        'var(--accent)',
          marginBottom: '4px',
        }}>
          LolHelper
        </div>
        <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
          {user.game_name ? `${user.game_name}#${user.tag_line}` : ''}
        </div>
      </div>

      {/* Links */}
      <div style={{ flex: 1, padding: '16px 12px' }}>
        {links.map(({ to, label, icon }) => (
          <NavLink key={to} to={to} style={({ isActive }) => ({
            display:      'flex',
            alignItems:   'center',
            gap:          '10px',
            padding:      '10px 14px',
            borderRadius: 'var(--radius)',
            marginBottom: '4px',
            fontSize:     '14px',
            fontWeight:   isActive ? '500' : '400',
            color:        isActive ? 'var(--text)' : 'var(--muted)',
            background:   isActive ? 'var(--bg3)' : 'transparent',
            transition:   'all .15s',
          })}>
            <span style={{ fontSize: '16px' }}>{icon}</span>
            {label}
          </NavLink>
        ))}
      </div>

      {/* Logout */}
      <div style={{ padding: '16px 12px', borderTop: '1px solid var(--border)' }}>
        <button
          onClick={logout}
          style={{
            width:        '100%',
            padding:      '10px 14px',
            borderRadius: 'var(--radius)',
            background:   'transparent',
            border:       '1px solid var(--border)',
            color:        'var(--muted)',
            fontSize:     '14px',
            textAlign:    'left',
            display:      'flex',
            alignItems:   'center',
            gap:          '10px',
            cursor:       'pointer',
            transition:   'all .15s',
          }}
          onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--danger)'}
          onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
        >
          <span>↩</span> Cerrar sesión
        </button>
      </div>
    </nav>
  )
}
