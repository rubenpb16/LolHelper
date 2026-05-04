import { useState } from 'react'
import { auth } from '../api'

export default function Cuenta() {
  const user = JSON.parse(localStorage.getItem('user') || '{}')

  const [pwForm,   setPwForm]   = useState({ password_actual: '', password_nueva: '', confirm: '' })
  const [pwMsg,    setPwMsg]    = useState({ type: '', text: '' })
  const [pwSaving, setPwSaving] = useState(false)

  async function handlePassword(e) {
    e.preventDefault()
    setPwMsg({ type: '', text: '' })
    if (pwForm.password_nueva.length < 8) {
      setPwMsg({ type: 'error', text: 'La contraseña debe tener al menos 8 caracteres' }); return
    }
    if (pwForm.password_nueva !== pwForm.confirm) {
      setPwMsg({ type: 'error', text: 'Las contraseñas nuevas no coinciden' }); return
    }
    setPwSaving(true)
    try {
      await auth.password({
        password_actual: pwForm.password_actual,
        password_nueva:  pwForm.password_nueva,
      })
      setPwMsg({ type: 'ok', text: 'Contraseña actualizada correctamente' })
      setPwForm({ password_actual: '', password_nueva: '', confirm: '' })
    } catch (err) {
      setPwMsg({ type: 'error', text: err.response?.data?.detail || 'Error al cambiar la contraseña' })
    } finally {
      setPwSaving(false)
    }
  }

  return (
    <div style={{ maxWidth: 560 }}>
      <h1 style={{ fontSize: 26, marginBottom: 6 }}>Cuenta</h1>
      <p style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 28 }}>
        Gestiona tu información de cuenta y seguridad.
      </p>

      {/* Información de la cuenta */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, marginBottom: 20 }}>Información</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={infoRow}>
            <span style={infoLabel}>Invocador</span>
            <span style={infoValue}>
              {user.game_name
                ? <><strong>{user.game_name}</strong><span style={{ color: 'var(--muted)' }}>#{user.tag_line}</span></>
                : <span style={{ color: 'var(--muted)' }}>—</span>}
            </span>
          </div>
          <div style={infoRow}>
            <span style={infoLabel}>Región</span>
            <span style={infoValue}>EUW</span>
          </div>
        </div>
      </div>

      {/* Cambiar contraseña */}
      <div className="card">
        <h2 style={{ fontSize: 16, marginBottom: 20 }}>Cambiar contraseña</h2>

        {pwMsg.text && (
          <div className={pwMsg.type === 'ok' ? 'success-banner' : 'error-banner'}>
            {pwMsg.text}
          </div>
        )}

        <form onSubmit={handlePassword}>
          <div className="input-group">
            <label>Contraseña actual</label>
            <input
              type="password" required placeholder="••••••••"
              value={pwForm.password_actual}
              onChange={e => setPwForm({ ...pwForm, password_actual: e.target.value })}
            />
          </div>
          <div className="input-group">
            <label>Nueva contraseña</label>
            <input
              type="password" required placeholder="Mínimo 8 caracteres"
              value={pwForm.password_nueva}
              onChange={e => setPwForm({ ...pwForm, password_nueva: e.target.value })}
            />
          </div>
          <div className="input-group">
            <label>Confirmar nueva contraseña</label>
            <input
              type="password" required placeholder="Repite la nueva contraseña"
              value={pwForm.confirm}
              onChange={e => setPwForm({ ...pwForm, confirm: e.target.value })}
            />
          </div>
          <button className="btn btn-full" disabled={pwSaving}>
            {pwSaving ? 'Cambiando...' : 'Cambiar contraseña'}
          </button>
        </form>
      </div>
    </div>
  )
}

const infoRow   = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--border)' }
const infoLabel = { fontSize: 13, color: 'var(--muted)' }
const infoValue = { fontSize: 14 }
