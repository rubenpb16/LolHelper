import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { proInvitacion } from '../api'

export default function InvitacionPro() {
  const { token } = useParams()

  const [pro,       setPro]       = useState(null)
  const [loadError, setLoadError] = useState('')
  const [form,      setForm]      = useState({
    nombre: '', apellidos: '',
    riot_game_name: '', riot_tag_line: '', email: '',
    consentimiento_datos: false, consentimiento_emails: false,
  })
  const [submitting, setSubmitting] = useState(false)
  const [submitted,  setSubmitted]  = useState(false)
  const [error,      setError]      = useState('')

  useEffect(() => {
    proInvitacion.info(token)
      .then(r => setPro(r.data))
      .catch(() => setLoadError('Este enlace de invitación no es válido o ha expirado.'))
  }, [token])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.consentimiento_datos) { setError('Debes aceptar el tratamiento de datos'); return }
    setSubmitting(true); setError('')
    try {
      await proInvitacion.aceptar(token, {
        ...form,
        riot_tag_line: form.riot_tag_line.replace('#', '').trim(),
      })
      setSubmitted(true)
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al procesar la solicitud')
    } finally {
      setSubmitting(false)
    }
  }

  if (loadError) return (
    <div style={s.page}>
      <div style={s.box}>
        <div style={s.logo}>LolHelper</div>
        <div style={s.alertError}>{loadError}</div>
      </div>
    </div>
  )

  if (!pro) return (
    <div style={s.page}>
      <div style={s.box}>
        <div style={s.logo}>LolHelper</div>
        <p style={{ color: '#64748b', textAlign: 'center' }}>Cargando...</p>
      </div>
    </div>
  )

  if (submitted) return (
    <div style={s.page}>
      <div style={s.box}>
        <div style={s.logo}>LolHelper</div>
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <div style={{ fontSize: 52, marginBottom: 16 }}>✅</div>
          <h2 style={s.h2}>¡Vinculación completada!</h2>
          <p style={{ color: '#64748b', fontSize: 15, lineHeight: 1.7, marginTop: 10 }}>
            Tus datos han sido registrados correctamente.
            <strong style={{ color: '#1e293b' }}> {pro.nombre} {pro.apellidos}</strong> ya puede
            ver tu historial de partidas para ayudarte en el seguimiento.
          </p>
          <div style={s.infoBox}>
            <p style={{ fontSize: 14, color: '#1d4ed8', fontWeight: 500, marginBottom: 6 }}>
              ¿Quieres acceder a tu propio panel de seguimiento?
            </p>
            <p style={{ fontSize: 13, color: '#64748b', lineHeight: 1.6, marginBottom: 12 }}>
              Puedes crear tu cuenta en la app con el mismo email que has introducido
              y ver tus propias estadísticas, límites y progreso.
            </p>
            <a
              href={`${window.location.origin}/login`}
              style={{ display: 'inline-block', padding: '9px 20px', borderRadius: 8, background: '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, textDecoration: 'none' }}
            >
              Crear mi cuenta →
            </a>
          </div>
        </div>
      </div>
    </div>
  )

  return (
    <div style={s.page}>
      <div style={s.box}>
        <div style={s.logo}>LolHelper</div>

        {/* Info del profesional */}
        <div style={s.proCard}>
          <div style={s.avatar}>{pro.nombre.charAt(0)}</div>
          <div>
            <p style={s.proNombre}>{pro.nombre} {pro.apellidos}</p>
            <p style={s.proEspecialidad}>{pro.especialidad}</p>
          </div>
        </div>

        <p style={s.desc}>
          Este profesional te ha invitado a compartir tu historial de partidas de League of Legends
          con fines terapéuticos. Rellena tus datos para completar la vinculación.
        </p>

        {error && <div style={s.alertError}>{error}</div>}

        <form onSubmit={handleSubmit}>
          {/* Nombre real */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 18 }}>
            <div>
              <label style={s.label}>Nombre</label>
              <input style={s.input} required placeholder="Rubén"
                value={form.nombre}
                onChange={e => setForm({ ...form, nombre: e.target.value })} />
            </div>
            <div>
              <label style={s.label}>Apellidos</label>
              <input style={s.input} required placeholder="García López"
                value={form.apellidos}
                onChange={e => setForm({ ...form, apellidos: e.target.value })} />
            </div>
          </div>

          {/* Cuenta Riot */}
          <div style={s.group}>
            <label style={s.label}>Tu cuenta de Riot</label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10 }}>
              <input style={s.input} required placeholder="NombreInvocador"
                value={form.riot_game_name}
                onChange={e => setForm({ ...form, riot_game_name: e.target.value })} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: '#94a3b8', fontWeight: 700 }}>#</span>
                <input style={{ ...s.input, width: 90 }} required placeholder="EUW"
                  maxLength={10}
                  value={form.riot_tag_line}
                  onChange={e => setForm({ ...form, riot_tag_line: e.target.value.replace('#','') })} />
              </div>
            </div>
            <p style={s.hint}>Ej: zRamBoXx #EUW — tal como aparece en el cliente</p>
          </div>

          {/* Email */}
          <div style={s.group}>
            <label style={s.label}>Tu email</label>
            <input style={s.input} type="email" required placeholder="tu@email.com"
              value={form.email}
              onChange={e => setForm({ ...form, email: e.target.value })} />
            <p style={s.hint}>Solo para identificarte en el sistema. No recibirás publicidad.</p>
          </div>

          {/* RGPD */}
          <div style={s.consentBox}>
            <p style={s.consentTitle}>Consentimiento y privacidad</p>

            <label style={s.checkLabel}>
              <input type="checkbox" required
                checked={form.consentimiento_datos}
                onChange={e => setForm({ ...form, consentimiento_datos: e.target.checked })}
                style={{ accentColor: '#2563eb', marginTop: 2, flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: '#475569', lineHeight: 1.6 }}>
                <strong style={{ color: '#1e293b' }}>Acepto que LolHelper acceda a mi historial de partidas</strong>
                {' '}(obligatorio) y que estos datos sean compartidos con{' '}
                <strong style={{ color: '#1e293b' }}>{pro.nombre} {pro.apellidos}</strong> exclusivamente
                con fines terapéuticos, conforme al RGPD. Entiendo que el profesional no puede revelar
                estos datos a terceros y que puedo solicitar la baja contactando con LolHelper.
              </span>
            </label>

            <label style={{ ...s.checkLabel, marginBottom: 0, marginTop: 12 }}>
              <input type="checkbox"
                checked={form.consentimiento_emails}
                onChange={e => setForm({ ...form, consentimiento_emails: e.target.checked })}
                style={{ accentColor: '#2563eb', marginTop: 2, flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: '#475569', lineHeight: 1.6 }}>
                <strong style={{ color: '#1e293b' }}>Quiero recibir alertas y resúmenes</strong>{' '}
                (opcional) — emails sobre mi progreso y cuando me acerque a mis límites de juego.
              </span>
            </label>
          </div>

          <button style={{ ...s.btn, opacity: submitting ? .7 : 1 }} disabled={submitting}>
            {submitting ? 'Procesando...' : 'Confirmar vinculación →'}
          </button>
        </form>

        <p style={{ textAlign: 'center', fontSize: 11, color: '#94a3b8', marginTop: 18, lineHeight: 1.6 }}>
          LolHelper no está afiliado con Riot Games. Tus datos se almacenan de forma segura
          y solo se comparten con el profesional que te ha enviado este enlace.
        </p>
      </div>
    </div>
  )
}

const s = {
  page:         { minHeight: '100vh', background: '#f0f4f8', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, fontFamily: "'DM Sans', sans-serif" },
  box:          { background: '#fff', borderRadius: 16, padding: '40px 36px', maxWidth: 520, width: '100%', boxShadow: '0 4px 24px rgba(0,0,0,0.08)' },
  logo:         { fontFamily: "'Syne', sans-serif", fontSize: 20, fontWeight: 700, color: '#2563eb', marginBottom: 20, textAlign: 'center' },
  proCard:      { display: 'flex', alignItems: 'center', gap: 14, background: '#eff6ff', borderRadius: 10, padding: '14px 16px', marginBottom: 20, border: '1px solid #bfdbfe' },
  avatar:       { width: 44, height: 44, borderRadius: '50%', background: '#2563eb', color: '#fff', fontFamily: "'Syne', sans-serif", fontSize: 18, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  proNombre:    { fontSize: 15, fontWeight: 700, color: '#1e293b', marginBottom: 2 },
  proEspecialidad:{ fontSize: 13, color: '#2563eb' },
  desc:         { fontSize: 14, color: '#64748b', lineHeight: 1.7, marginBottom: 24 },
  h2:           { fontFamily: "'Syne', sans-serif", fontSize: 22, fontWeight: 700, color: '#1e293b' },
  group:        { marginBottom: 18 },
  label:        { display: 'block', fontSize: 12, color: '#64748b', marginBottom: 6, fontWeight: 600 },
  input:        { width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 14, fontFamily: "'DM Sans', sans-serif", outline: 'none', boxSizing: 'border-box', color: '#1e293b' },
  hint:         { fontSize: 12, color: '#94a3b8', marginTop: 5 },
  consentBox:   { background: '#f8fafc', borderRadius: 10, border: '1px solid #e2e8f0', padding: '16px', marginBottom: 20 },
  consentTitle: { fontSize: 11, color: '#64748b', fontWeight: 700, textTransform: 'uppercase', letterSpacing: .6, marginBottom: 14 },
  checkLabel:   { display: 'flex', gap: 10, alignItems: 'flex-start', cursor: 'pointer', marginBottom: 4 },
  btn:          { width: '100%', padding: '13px', borderRadius: 8, background: '#2563eb', border: 'none', color: '#fff', fontSize: 15, fontWeight: 600, cursor: 'pointer', fontFamily: "'DM Sans', sans-serif" },
  alertError:   { background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '12px 16px', fontSize: 14, color: '#dc2626', marginBottom: 18 },
  infoBox:      { background: '#eff6ff', borderRadius: 10, border: '1px solid #bfdbfe', padding: '14px 16px', marginTop: 20, textAlign: 'left' },
}
