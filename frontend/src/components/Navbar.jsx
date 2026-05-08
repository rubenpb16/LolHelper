import { NavLink, useNavigate } from 'react-router-dom'
import { auth } from '../api'

const LOL_LINKS = [
  { to: '/dashboard', label: 'Dashboard', icon: '▦' },
  { to: '/historial', label: 'Historial', icon: '◷' },
  { to: '/analisis',  label: 'Análisis',  icon: '◈' },
]

const TFT_LINKS = [
  { to: '/tft/dashboard', label: 'Dashboard', icon: '▦' },
  { to: '/tft/historial', label: 'Historial',  icon: '◷' },
]

const BOTTOM_LINKS = [
  { to: '/objetivo', label: 'Objetivo', icon: '◎' },
  { to: '/cuenta',   label: 'Cuenta',   icon: '◯' },
]

const navStyle = (isActive, accentColor = 'var(--accent)') => ({
  display: 'flex', alignItems: 'center', gap: '10px',
  padding: '10px 14px', borderRadius: 'var(--radius)', marginBottom: '4px',
  fontSize: '14px', fontWeight: isActive ? '500' : '400',
  color: isActive ? 'var(--text)' : 'var(--muted)',
  background: isActive ? 'var(--bg3)' : 'transparent',
  transition: 'all .15s',
  textDecoration: 'none',
})

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
      <div style={{ flex: 1, padding: '16px 12px', overflowY: 'auto' }}>
        {/* LoL */}
        <div style={{ fontSize: 10, color: 'var(--muted)', letterSpacing: 1.5, textTransform: 'uppercase', fontWeight: 600, padding: '4px 14px 8px', marginTop: 4 }}>
          League of Legends
        </div>
        {LOL_LINKS.map(({ to, label, icon }) => (
          <NavLink key={to} to={to} style={({ isActive }) => navStyle(isActive)}>
            <span style={{ fontSize: '16px' }}>{icon}</span>{label}
          </NavLink>
        ))}

        {/* TFT */}
        <div style={{ fontSize: 10, color: '#c89b3c', letterSpacing: 1.5, textTransform: 'uppercase', fontWeight: 600, padding: '16px 14px 8px' }}>
          ♟ TFT
        </div>
        {TFT_LINKS.map(({ to, label, icon }) => (
          <NavLink key={to} to={to} style={({ isActive }) => navStyle(isActive, '#c89b3c')}>
            <span style={{ fontSize: '16px' }}>{icon}</span>{label}
          </NavLink>
        ))}

        {/* General */}
        <div style={{ height: 1, background: 'var(--border)', margin: '14px 0 10px' }} />
        {BOTTOM_LINKS.map(({ to, label, icon }) => (
          <NavLink key={to} to={to} style={({ isActive }) => navStyle(isActive)}>
            <span style={{ fontSize: '16px' }}>{icon}</span>{label}
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
