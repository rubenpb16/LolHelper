import { useEffect, useState } from 'react'
import { objetivo as objApi } from '../api'

export default function Objetivo() {
  const [form,      setForm]      = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [loadError, setLoadError] = useState('')
  const [saving,    setSaving]    = useState(false)
  const [msg,       setMsg]       = useState({ type: '', text: '' })

  useEffect(() => {
    objApi.get()
      .then(r => setForm({
        limite_horas_dia:    parseFloat(r.data.limite_horas_dia),
        limite_horas_semana: parseFloat(r.data.limite_horas_semana),
        alerta_porcentaje:   r.data.alerta_al_porcentaje,
        resumen_nocturno:    r.data.resumen_nocturno,
        hora_resumen:        r.data.hora_resumen?.slice(0, 5) || '23:00',
      }))
      .catch(() => setLoadError('No se pudo cargar el objetivo. Recarga la página.'))
      .finally(() => setLoading(false))
  }, [])

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true); setMsg({ type: '', text: '' })
    try {
      await objApi.update({
        limite_horas_dia:    form.limite_horas_dia,
        limite_horas_semana: form.limite_horas_semana,
        alerta_porcentaje:   form.alerta_porcentaje,
        resumen_nocturno:    form.resumen_nocturno,
        hora_resumen:        form.hora_resumen,
      })
      setMsg({ type: 'ok', text: '¡Objetivo actualizado correctamente!' })
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Error al guardar' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="loader"><div className="spinner" /> Cargando...</div>

  if (loadError) return (
    <div style={{ maxWidth: 560 }}>
      <h1 style={{ fontSize: 26, marginBottom: 20 }}>Tu objetivo</h1>
      <div className="error-banner">{loadError}</div>
    </div>
  )

  return (
    <div style={{ maxWidth: 560 }}>
      <h1 style={{ fontSize: 26, marginBottom: 6 }}>Tu objetivo</h1>
      <p style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 28 }}>
        Puedes cambiar estos valores cuando quieras. Los cambios se aplican de inmediato.
      </p>

      <div className="card">
        <h2 style={{ fontSize: 16, marginBottom: 20 }}>Límites de tiempo</h2>

        {msg.text && (
          <div className={msg.type === 'ok' ? 'success-banner' : 'error-banner'}>
            {msg.text}
          </div>
        )}

        <form onSubmit={handleSave}>
          <div className="input-row">
            <div className="input-group">
              <label>Límite diario (horas)</label>
              <input
                type="number" min="0.5" max="24" step="0.5"
                value={form.limite_horas_dia}
                onChange={e => setForm({ ...form, limite_horas_dia: parseFloat(e.target.value) })}
              />
              <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
                = {Math.floor(form.limite_horas_dia)}h {Math.round((form.limite_horas_dia % 1) * 60)}min al día
              </p>
            </div>
            <div className="input-group">
              <label>Límite semanal (horas)</label>
              <input
                type="number" min="1" max="168" step="0.5"
                value={form.limite_horas_semana}
                onChange={e => setForm({ ...form, limite_horas_semana: parseFloat(e.target.value) })}
              />
              <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
                = {Math.round(form.limite_horas_semana / 7 * 10) / 10}h de media al día
              </p>
            </div>
          </div>

          <div className="input-group">
            <label>Avisarme cuando lleve el % del límite diario</label>
            <select
              value={form.alerta_porcentaje}
              onChange={e => setForm({ ...form, alerta_porcentaje: parseInt(e.target.value) })}
            >
              {[50, 60, 70, 75, 80, 90, 100].map(v =>
                <option key={v} value={v}>{v}% — cuando lleve {fmt(form.limite_horas_dia * v / 100)}</option>
              )}
            </select>
          </div>

          <div className="divider" />

          <p style={{ fontSize: 13, fontWeight: 500, marginBottom: 14 }}>Resumen nocturno</p>

          <div className="toggle-wrap" style={{ marginBottom: 14 }}>
            <div
              className={`toggle ${form.resumen_nocturno ? 'on' : ''}`}
              onClick={() => setForm({ ...form, resumen_nocturno: !form.resumen_nocturno })}
            />
            <span className="toggle-label">
              {form.resumen_nocturno ? 'Activo — recibirás un resumen cada noche' : 'Desactivado'}
            </span>
          </div>

          {form.resumen_nocturno && (
            <div className="input-group">
              <label>Hora del resumen nocturno</label>
              <input
                type="time"
                value={form.hora_resumen}
                onChange={e => setForm({ ...form, hora_resumen: e.target.value })}
                style={{ width: 'auto' }}
              />
            </div>
          )}

          <button className="btn btn-primary btn-full" style={{ marginTop: 8 }} disabled={saving}>
            {saving ? 'Guardando...' : 'Guardar cambios'}
          </button>
        </form>
      </div>
    </div>
  )
}

function fmt(horas) {
  const h = Math.floor(horas)
  const m = Math.round((horas - h) * 60)
  if (h === 0) return `${m}min`
  if (m === 0) return `${h}h`
  return `${h}h ${m}min`
}
