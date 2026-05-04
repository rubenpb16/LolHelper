import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { auth } from '../api'

export default function Login() {
  const navigate        = useNavigate()
  const [mode, setMode] = useState('login')
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)

  const [loginForm, setLoginForm] = useState({ email: '', password: '' })

  const [regForm, setRegForm] = useState({
    email:               '',
    password:            '',
    confirm:             '',
    riot_game_name:      '',
    riot_tag_line:       'EUW',
    limite_horas_dia:    2,
    limite_horas_semana: 10,
    alerta_porcentaje:   80,
    consentimiento_datos:  false,
    consentimiento_emails: false,
  })

  async function handleLogin(e) {
    e.preventDefault()
    if (loginForm.password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres'); return
    }
    setError(''); setLoading(true)
    try {
      const res = await auth.login({
        username: loginForm.email,
        password: loginForm.password,
      })
      localStorage.setItem('user', JSON.stringify({
        game_name: res.data.game_name,
        tag_line:  res.data.tag_line,
      }))
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Email o contraseña incorrectos')
    } finally {
      setLoading(false)
    }
  }

  async function handleRegister(e) {
    e.preventDefault()
    setError('')
    if (regForm.password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres'); return
    }
    if (regForm.password !== regForm.confirm) {
      setError('Las contraseñas no coinciden'); return
    }
    if (regForm.riot_tag_line.length > 10) {
      setError('El TAG no puede tener más de 10 caracteres'); return
    }
    if (!regForm.consentimiento_datos) {
      setError('Debes aceptar la política de privacidad para continuar')
      return
    }
    if (!regForm.consentimiento_emails) {
      setError('Debes aceptar recibir emails de alerta para usar la app')
      return
    }
    setLoading(true)
    try {
      const res = await auth.register({
        email:               regForm.email,
        password:            regForm.password,
        riot_game_name:      regForm.riot_game_name,
        riot_tag_line:       regForm.riot_tag_line,
        limite_horas_dia:    regForm.limite_horas_dia,
        limite_horas_semana: regForm.limite_horas_semana,
        alerta_porcentaje:   regForm.alerta_porcentaje,
        consentimiento_datos:  regForm.consentimiento_datos,
        consentimiento_emails: regForm.consentimiento_emails,
      })
      localStorage.setItem('user', JSON.stringify({
        game_name: res.data.game_name,
        tag_line:  res.data.tag_line,
      }))
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al crear la cuenta')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-box">
        <div className="auth-logo">LolHelper</div>
        <div className="auth-sub">
          {mode === 'login'
            ? 'Accede a tu panel de seguimiento'
            : 'Crea tu cuenta y empieza a tomar el control'}
        </div>

        {error && <div className="error-banner">{error}</div>}

        {mode === 'login' ? (
          <form onSubmit={handleLogin}>
            <div className="input-group">
              <label>Email</label>
              <input
                type="email" required
                placeholder="tu@email.com"
                value={loginForm.email}
                onChange={e => setLoginForm({ ...loginForm, email: e.target.value })}
              />
            </div>
            <div className="input-group">
              <label>Contraseña</label>
              <input
                type="password" required
                placeholder="Mínimo 8 caracteres"
                value={loginForm.password}
                onChange={e => setLoginForm({ ...loginForm, password: e.target.value })}
              />
            </div>
            <button className="btn btn-primary btn-full" disabled={loading}>
              {loading ? 'Entrando...' : 'Entrar'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegister}>
            <div className="input-group">
              <label>Email</label>
              <input type="email" required placeholder="tu@email.com"
                value={regForm.email}
                onChange={e => setRegForm({ ...regForm, email: e.target.value })}
              />
            </div>
            <div className="input-group">
              <label>Contraseña</label>
              <input type="password" required placeholder="Mínimo 8 caracteres"
                value={regForm.password}
                onChange={e => setRegForm({ ...regForm, password: e.target.value })}
              />
            </div>
            <div className="input-group">
              <label>Confirmar contraseña</label>
              <input type="password" required placeholder="Repite la contraseña"
                value={regForm.confirm}
                onChange={e => setRegForm({ ...regForm, confirm: e.target.value })}
              />
            </div>
            <div className="input-row">
              <div className="input-group">
                <label>Nombre de invocador</label>
                <input required placeholder="zRamBoXx"
                  value={regForm.riot_game_name}
                  onChange={e => setRegForm({ ...regForm, riot_game_name: e.target.value })}
                />
              </div>
              <div className="input-group">
                <label>TAG (máx. 10)</label>
                <input required placeholder="EUW" maxLength={10}
                  value={regForm.riot_tag_line}
                  onChange={e => setRegForm({ ...regForm, riot_tag_line: e.target.value })}
                />
              </div>
            </div>
            <div className="input-row">
              <div className="input-group">
                <label>Límite diario (horas)</label>
                <input type="number" min="0.5" max="24" step="0.5"
                  value={regForm.limite_horas_dia}
                  onChange={e => setRegForm({ ...regForm, limite_horas_dia: parseFloat(e.target.value) })}
                />
              </div>
              <div className="input-group">
                <label>Límite semanal (horas)</label>
                <input type="number" min="1" max="168" step="0.5"
                  value={regForm.limite_horas_semana}
                  onChange={e => setRegForm({ ...regForm, limite_horas_semana: parseFloat(e.target.value) })}
                />
              </div>
            </div>
            <div className="input-group">
              <label>Avisarme cuando lleve el % del límite diario</label>
              <select
                value={regForm.alerta_porcentaje}
                onChange={e => setRegForm({ ...regForm, alerta_porcentaje: parseInt(e.target.value) })}
              >
                {[50, 60, 70, 75, 80, 90, 100].map(v =>
                  <option key={v} value={v}>{v}%</option>
                )}
              </select>
            </div>

            <div className="divider" />

            <div className="check-item">
              <input type="checkbox" id="c1"
                checked={regForm.consentimiento_datos}
                onChange={e => setRegForm({ ...regForm, consentimiento_datos: e.target.checked })}
              />
              <label htmlFor="c1">
                He leído y acepto la <strong>Política de Privacidad</strong> y los{' '}
                <strong>Términos de uso</strong>. Entiendo que mis datos de juego
                serán tratados para el seguimiento de mi tiempo de juego.
              </label>
            </div>
            <div className="check-item">
              <input type="checkbox" id="c2"
                checked={regForm.consentimiento_emails}
                onChange={e => setRegForm({ ...regForm, consentimiento_emails: e.target.checked })}
              />
              <label htmlFor="c2">
                Acepto recibir <strong>emails de alerta</strong> sobre mi tiempo
                de juego cuando supere los límites que yo mismo configure.
              </label>
            </div>

            <button className="btn btn-primary btn-full" style={{ marginTop: '8px' }} disabled={loading}>
              {loading ? 'Creando cuenta...' : 'Crear mi cuenta'}
            </button>
          </form>
        )}

        <div className="auth-switch">
          {mode === 'login' ? (
            <>¿Aún no tienes cuenta?
              <button onClick={() => { setMode('register'); setError('') }}>Regístrate</button>
            </>
          ) : (
            <>¿Ya tienes cuenta?
              <button onClick={() => { setMode('login'); setError('') }}>Inicia sesión</button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
