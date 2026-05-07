import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { proAuth } from '../../api'

export default function ProLogin() {
  const navigate = useNavigate()
  const [form,    setForm]    = useState({ username: '', password: '' })
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      const res = await proAuth.login({ username: form.username, password: form.password })
      if (res.data.rol !== 'profesional') {
        setError('Esta cuenta no es de profesional. Usa el acceso de pacientes.')
        return
      }
      // Obtener perfil completo (incluye link_token y datos del profesional)
      const me = await proAuth.me()
      localStorage.setItem('pro_user', JSON.stringify({ ...res.data, ...me.data }))
      navigate('/pro/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Email o contraseña incorrectos')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={s.page}>
      <div style={s.box}>
        <div style={s.logo}>LolHelper <span style={s.badge}>Pro</span></div>
        <p style={s.sub}>Panel para profesionales sanitarios</p>

        {error && <div style={s.error}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div style={s.group}>
            <label style={s.label}>Correo electrónico</label>
            <input style={s.input} type="email" required autoFocus
              value={form.username}
              onChange={e => setForm({ ...form, username: e.target.value })}
            />
          </div>
          <div style={s.group}>
            <label style={s.label}>Contraseña</label>
            <input style={s.input} type="password" required
              value={form.password}
              onChange={e => setForm({ ...form, password: e.target.value })}
            />
          </div>
          <button style={{ ...s.btn, opacity: loading ? .7 : 1 }} disabled={loading}>
            {loading ? 'Accediendo...' : 'Acceder al panel'}
          </button>
        </form>

        <p style={s.switch}>
          ¿No tienes cuenta?{' '}
          <Link to="/pro/registro" style={s.link}>Regístrate como profesional</Link>
        </p>
      </div>
    </div>
  )
}

const s = {
  page:  { minHeight: '100vh', background: '#f0f4f8', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, fontFamily: "'DM Sans', sans-serif" },
  box:   { background: '#fff', borderRadius: 16, padding: '44px 40px', maxWidth: 420, width: '100%', boxShadow: '0 4px 24px rgba(0,0,0,0.08)' },
  logo:  { fontFamily: "'Syne', sans-serif", fontSize: 22, fontWeight: 700, color: '#2563eb', marginBottom: 6 },
  badge: { background: '#dbeafe', color: '#1d4ed8', fontSize: 12, fontWeight: 700, padding: '2px 8px', borderRadius: 6, marginLeft: 6, verticalAlign: 'middle' },
  sub:   { fontSize: 14, color: '#64748b', marginBottom: 28 },
  group: { marginBottom: 18 },
  label: { display: 'block', fontSize: 12, color: '#64748b', marginBottom: 6, fontWeight: 500 },
  input: { width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 15, fontFamily: "'DM Sans', sans-serif", outline: 'none', boxSizing: 'border-box', color: '#1e293b' },
  btn:   { width: '100%', padding: '12px', borderRadius: 8, background: '#2563eb', border: 'none', color: '#fff', fontSize: 15, fontWeight: 600, cursor: 'pointer', marginTop: 8, fontFamily: "'DM Sans', sans-serif" },
  error: { background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#dc2626', marginBottom: 18 },
  switch:{ textAlign: 'center', fontSize: 13, color: '#94a3b8', marginTop: 20 },
  link:  { color: '#2563eb', textDecoration: 'none', fontWeight: 500 },
}
