import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { proAuth } from '../../api'

export default function ProRegistro() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    email: '', password: '', nombre: '', apellidos: '',
    numero_colegiado: '', especialidad: '',
    consentimiento_datos: false,
  })
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const upd = (k, v) => setForm(f => ({ ...f, [k]: v }))

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.consentimiento_datos) { setError('Debes aceptar el tratamiento de datos'); return }
    setLoading(true); setError('')
    try {
      await proAuth.registro(form)
      const me = await proAuth.me()
      localStorage.setItem('pro_user', JSON.stringify(me.data))
      navigate('/pro/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al registrarse')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={s.page}>
      <div style={s.box}>
        <div style={s.logo}>LolHelper <span style={s.badge}>Pro</span></div>
        <p style={s.sub}>Registro de profesional sanitario</p>

        {error && <div style={s.error}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div style={s.row}>
            <div style={s.group}>
              <label style={s.label}>Nombre</label>
              <input style={s.input} required value={form.nombre}
                onChange={e => upd('nombre', e.target.value)} />
            </div>
            <div style={s.group}>
              <label style={s.label}>Apellidos</label>
              <input style={s.input} required value={form.apellidos}
                onChange={e => upd('apellidos', e.target.value)} />
            </div>
          </div>

          <div style={s.group}>
            <label style={s.label}>Email profesional</label>
            <input style={s.input} type="email" required value={form.email}
              onChange={e => upd('email', e.target.value)} />
          </div>

          <div style={s.group}>
            <label style={s.label}>Contraseña</label>
            <input style={s.input} type="password" required minLength={8} value={form.password}
              onChange={e => upd('password', e.target.value)} />
          </div>

          <div style={s.row}>
            <div style={s.group}>
              <label style={s.label}>Nº de colegiado</label>
              <input style={s.input} required value={form.numero_colegiado}
                placeholder="Ej: 28-12345"
                onChange={e => upd('numero_colegiado', e.target.value)} />
            </div>
            <div style={s.group}>
              <label style={s.label}>Especialidad</label>
              <select style={s.input} value={form.especialidad}
                onChange={e => upd('especialidad', e.target.value)} required>
                <option value="">Seleccionar...</option>
                <option>Psicología clínica</option>
                <option>Psicoterapia</option>
                <option>Psiquiatría</option>
                <option>Trabajo social</option>
                <option>Coaching terapéutico</option>
                <option>Otra</option>
              </select>
            </div>
          </div>

          <div style={s.consent}>
            <label style={{ display: 'flex', gap: 10, alignItems: 'flex-start', cursor: 'pointer' }}>
              <input type="checkbox" checked={form.consentimiento_datos}
                onChange={e => upd('consentimiento_datos', e.target.checked)}
                style={{ marginTop: 3, accentColor: '#2563eb', flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: '#64748b', lineHeight: 1.6 }}>
                <strong style={{ color: '#1e293b' }}>Acepto el tratamiento de mis datos y los de mis pacientes</strong>
                {' '}conforme al RGPD. Declaro ser un profesional sanitario colegiado y me comprometo a obtener
                el consentimiento explícito de cada paciente antes de vincularlos a mi perfil.
              </span>
            </label>
          </div>

          <button style={{ ...s.btn, opacity: loading ? .7 : 1 }} disabled={loading}>
            {loading ? 'Registrando...' : 'Crear cuenta profesional'}
          </button>
        </form>

        <p style={s.switch}>
          ¿Ya tienes cuenta?{' '}
          <Link to="/pro/login" style={s.link}>Iniciar sesión</Link>
        </p>
      </div>
    </div>
  )
}

const s = {
  page:    { minHeight: '100vh', background: '#f0f4f8', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, fontFamily: "'DM Sans', sans-serif" },
  box:     { background: '#fff', borderRadius: 16, padding: '40px 36px', maxWidth: 580, width: '100%', boxShadow: '0 4px 24px rgba(0,0,0,0.08)' },
  logo:    { fontFamily: "'Syne', sans-serif", fontSize: 22, fontWeight: 700, color: '#2563eb', marginBottom: 6 },
  badge:   { background: '#dbeafe', color: '#1d4ed8', fontSize: 12, fontWeight: 700, padding: '2px 8px', borderRadius: 6, marginLeft: 6, verticalAlign: 'middle' },
  sub:     { fontSize: 14, color: '#64748b', marginBottom: 24 },
  row:     { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 },
  group:   { marginBottom: 16 },
  label:   { display: 'block', fontSize: 12, color: '#64748b', marginBottom: 6, fontWeight: 500 },
  input:   { width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 14, fontFamily: "'DM Sans', sans-serif", outline: 'none', boxSizing: 'border-box', color: '#1e293b' },
  consent: { background: '#f8fafc', borderRadius: 10, border: '1px solid #e2e8f0', padding: '14px 16px', marginBottom: 20, marginTop: 4 },
  btn:     { width: '100%', padding: '12px', borderRadius: 8, background: '#2563eb', border: 'none', color: '#fff', fontSize: 15, fontWeight: 600, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif" },
  error:   { background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#dc2626', marginBottom: 18 },
  switch:  { textAlign: 'center', fontSize: 13, color: '#94a3b8', marginTop: 20 },
  link:    { color: '#2563eb', textDecoration: 'none', fontWeight: 500 },
}
