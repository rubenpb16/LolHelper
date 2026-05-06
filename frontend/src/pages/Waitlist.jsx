import { useState, useRef } from 'react'
import { waitlist } from '../api'

// Splash arts del CDN oficial de Riot (Data Dragon — uso permitido en fan apps)
const HERO_BG   = 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Jinx_0.jpg'
const CHAMPS_ROW = ['Ahri', 'Thresh', 'Yasuo']

const FEATURES = [
  {
    icon: '⏱',
    title: 'Controla tu tiempo',
    desc: 'Establece límites diarios y semanales. Recibe alertas por email cuando te acerques a tu límite — en el momento exacto en que importa.',
  },
  {
    icon: '🧠',
    title: 'Detecta el tilt antes de que ocurra',
    desc: 'LolHelper identifica rachas negativas y rendiciones seguidas y te recuerda que un descanso ahora vale más que la siguiente partida.',
  },
  {
    icon: '📊',
    title: 'Analiza tus patrones reales',
    desc: 'Descubre a qué horas rindes mejor, cómo el cansancio afecta tu LP y qué campeones juegas mejor cuando estás fresco.',
  },
]

const inputSt = {
  width: '100%',
  background: 'rgba(255,255,255,0.05)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: 10,
  padding: '12px 16px',
  color: '#e8eaf0',
  fontSize: 15,
  fontFamily: "'DM Sans', sans-serif",
  outline: 'none',
  boxSizing: 'border-box',
  transition: 'border-color .15s',
}

export default function Waitlist() {
  const formRef = useRef(null)

  const [form, setForm] = useState({
    riot_game_name:       '',
    riot_tag_line:        '',
    email:                '',
    consentimiento_datos:  false,
    consentimiento_emails: false,
  })
  const [submitting, setSubmitting] = useState(false)
  const [submitted,  setSubmitted]  = useState(false)
  const [error,      setError]      = useState('')

  function scrollToForm() {
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.consentimiento_datos) {
      setError('Debes aceptar el tratamiento de datos para continuar.')
      return
    }
    if (!form.riot_game_name.trim() || !form.riot_tag_line.trim()) {
      setError('Completa tu nombre de invocador y TAG.')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      await waitlist.register({
        ...form,
        riot_tag_line: form.riot_tag_line.replace('#', '').trim(),
      })
      setSubmitted(true)
    } catch (err) {
      setError(err.response?.data?.detail || 'Algo salió mal. Inténtalo de nuevo.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ background: '#0a0b0f', minHeight: '100vh', color: '#e8eaf0', fontFamily: "'DM Sans', sans-serif", overflowX: 'hidden' }}>

      {/* ── BARRA SUPERIOR ──────────────────────────────────── */}
      <header style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
        padding: '0 40px',
        height: 60,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'rgba(10,11,15,0.85)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        <span style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: 18, color: '#7c6af7', letterSpacing: -0.5 }}>
          LolHelper
        </span>
        <button onClick={scrollToForm} style={{
          padding: '8px 20px', borderRadius: 8,
          background: '#7c6af7', border: 'none',
          color: '#fff', fontSize: 13, fontWeight: 600,
          fontFamily: "'DM Sans', sans-serif", cursor: 'pointer',
          transition: 'background .15s',
        }}
        onMouseEnter={e => e.currentTarget.style.background = '#5b50c9'}
        onMouseLeave={e => e.currentTarget.style.background = '#7c6af7'}
        >
          Quiero acceso →
        </button>
      </header>

      {/* ── HERO ────────────────────────────────────────────── */}
      <section style={{
        minHeight: '100vh', paddingTop: 60,
        display: 'flex', alignItems: 'center',
        position: 'relative', overflow: 'hidden',
      }}>
        {/* Splash art de fondo */}
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: `url(${HERO_BG})`,
          backgroundSize: 'cover', backgroundPosition: '65% center',
          opacity: 0.18,
        }} />
        {/* Gradiente izquierda opaca, derecha semitransparente */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(100deg, #0a0b0f 48%, rgba(10,11,15,0.55) 72%, rgba(124,106,247,0.08) 100%)',
        }} />
        {/* Halo morado izquierda */}
        <div style={{
          position: 'absolute',
          width: 700, height: 700, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(124,106,247,0.11) 0%, transparent 68%)',
          top: '50%', left: '-8%', transform: 'translateY(-50%)',
          pointerEvents: 'none',
        }} />
        {/* Halo dorado arriba derecha */}
        <div style={{
          position: 'absolute',
          width: 500, height: 500, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(200,155,60,0.07) 0%, transparent 68%)',
          top: '-10%', right: '5%',
          pointerEvents: 'none',
        }} />

        <div style={{ position: 'relative', zIndex: 1, maxWidth: 1100, margin: '0 auto', padding: '80px 40px', width: '100%' }}>
          <div style={{ maxWidth: 620 }}>

            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              background: 'rgba(124,106,247,0.12)', border: '1px solid rgba(124,106,247,0.3)',
              borderRadius: 20, padding: '6px 16px', marginBottom: 32,
              fontSize: 13, color: '#a89ff7', fontWeight: 500,
            }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#7c6af7', display: 'inline-block', boxShadow: '0 0 8px #7c6af7' }} />
              Beta cerrada · Acceso anticipado
            </div>

            <h1 style={{
              fontFamily: "'Syne', sans-serif",
              fontSize: 'clamp(40px, 5.5vw, 68px)',
              fontWeight: 700, lineHeight: 1.08, marginBottom: 26,
              background: 'linear-gradient(135deg, #e8eaf0 30%, #7c6af7 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
            }}>
              Juega más consciente.<br />Rinde más.
            </h1>

            <p style={{ fontSize: 18, color: '#9ca3af', lineHeight: 1.75, marginBottom: 14, maxWidth: 520 }}>
              LolHelper rastrea tu tiempo de juego, detecta cuándo el{' '}
              <em style={{ color: '#c89b3c', fontStyle: 'normal', fontWeight: 600 }}>tilt</em>{' '}
              te está costando LP y te ayuda a construir hábitos que sí funcionan — dentro y fuera de la Grieta.
            </p>
            <p style={{ fontSize: 15, color: '#4b5563', lineHeight: 1.7, marginBottom: 44 }}>
              Estamos en fase de pruebas. Apúntate, importamos tu historial y te avisamos cuando la app esté lista para ti.
            </p>

            <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center' }}>
              <button onClick={scrollToForm} style={{
                padding: '15px 32px', borderRadius: 10,
                background: '#7c6af7', border: 'none',
                color: '#fff', fontSize: 16, fontWeight: 600,
                fontFamily: "'DM Sans', sans-serif", cursor: 'pointer',
                boxShadow: '0 0 28px rgba(124,106,247,0.4)',
                transition: 'all .15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = '#5b50c9'; e.currentTarget.style.boxShadow = '0 0 36px rgba(124,106,247,0.55)' }}
              onMouseLeave={e => { e.currentTarget.style.background = '#7c6af7'; e.currentTarget.style.boxShadow = '0 0 28px rgba(124,106,247,0.4)' }}
              >
                Quiero acceso anticipado →
              </button>
              <span style={{ fontSize: 13, color: '#4b5563' }}>Sin coste · Sin compromiso</span>
            </div>

          </div>
        </div>

        {/* Indicador scroll */}
        <div style={{
          position: 'absolute', bottom: 28, left: '50%', transform: 'translateX(-50%)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
          color: '#374151', fontSize: 12, animation: 'wlBounce 2.2s ease-in-out infinite',
        }}>
          <span>Ver más</span>
          <span style={{ fontSize: 16 }}>↓</span>
        </div>
      </section>

      {/* ── FEATURES ────────────────────────────────────────── */}
      <section style={{ padding: '100px 40px 80px', maxWidth: 1100, margin: '0 auto' }}>

        <p style={{ textAlign: 'center', fontSize: 11, color: '#7c6af7', letterSpacing: 3, textTransform: 'uppercase', marginBottom: 14, fontWeight: 700 }}>
          ¿Qué es LolHelper?
        </p>
        <h2 style={{
          fontFamily: "'Syne', sans-serif",
          fontSize: 'clamp(26px, 3.5vw, 40px)', fontWeight: 700,
          textAlign: 'center', marginBottom: 14,
        }}>
          La herramienta que tu main no tiene
        </h2>
        <p style={{ textAlign: 'center', color: '#6b7280', fontSize: 16, maxWidth: 560, margin: '0 auto 60px', lineHeight: 1.7 }}>
          No es un tracker de stats al uso. LolHelper analiza <strong style={{ color: '#e8eaf0' }}>cuándo</strong>, <strong style={{ color: '#e8eaf0' }}>cuánto</strong> y <strong style={{ color: '#e8eaf0' }}>cómo</strong> juegas — y te ayuda a tomar mejores decisiones sobre tu tiempo.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
          {FEATURES.map((f, i) => (
            <div key={i}
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)',
                borderRadius: 16, padding: '28px 24px',
                transition: 'border-color .2s, background .2s, transform .2s',
                cursor: 'default',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = 'rgba(124,106,247,0.35)'
                e.currentTarget.style.background  = 'rgba(124,106,247,0.05)'
                e.currentTarget.style.transform   = 'translateY(-3px)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'
                e.currentTarget.style.background  = 'rgba(255,255,255,0.03)'
                e.currentTarget.style.transform   = 'translateY(0)'
              }}
            >
              <div style={{ fontSize: 34, marginBottom: 16 }}>{f.icon}</div>
              <h3 style={{ fontFamily: "'Syne', sans-serif", fontSize: 17, marginBottom: 12, fontWeight: 600 }}>{f.title}</h3>
              <p style={{ color: '#6b7280', fontSize: 14, lineHeight: 1.75 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CAMPEONES DECORATIVOS ────────────────────────────── */}
      <section style={{ padding: '0 40px 80px', maxWidth: 1100, margin: '0 auto' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          {CHAMPS_ROW.map(champ => (
            <div key={champ} style={{
              height: 200, borderRadius: 16, overflow: 'hidden',
              position: 'relative', border: '1px solid rgba(255,255,255,0.06)',
            }}>
              <div style={{
                position: 'absolute', inset: 0,
                backgroundImage: `url(https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${champ}_0.jpg)`,
                backgroundSize: 'cover', backgroundPosition: 'center 15%',
                opacity: 0.3,
                transition: 'opacity .3s',
              }} className={`champ-bg-${champ}`} />
              <div style={{
                position: 'absolute', inset: 0,
                background: 'linear-gradient(to bottom, rgba(10,11,15,0.1) 30%, rgba(10,11,15,0.85) 100%)',
              }} />
              <div style={{
                position: 'absolute', bottom: 16, left: 20,
                fontFamily: "'Syne', sans-serif", fontSize: 15, fontWeight: 600,
                color: 'rgba(232,234,240,0.7)',
              }}>
                {champ}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── FORM ────────────────────────────────────────────── */}
      <section ref={formRef} style={{ padding: '60px 40px 120px', maxWidth: 540, margin: '0 auto' }}>

        <p style={{ textAlign: 'center', fontSize: 11, color: '#7c6af7', letterSpacing: 3, textTransform: 'uppercase', marginBottom: 14, fontWeight: 700 }}>
          Acceso anticipado
        </p>
        <h2 style={{
          fontFamily: "'Syne', sans-serif",
          fontSize: 'clamp(24px, 3vw, 34px)', fontWeight: 700,
          textAlign: 'center', marginBottom: 10,
        }}>
          Sé de los primeros
        </h2>
        <p style={{ textAlign: 'center', color: '#6b7280', fontSize: 15, lineHeight: 1.7, marginBottom: 36, maxWidth: 440, marginLeft: 'auto', marginRight: 'auto' }}>
          Apúntate con tu cuenta de Riot. Importaremos tu historial de partidas y te avisaremos en cuanto la app esté lista.
        </p>

        <div style={{
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 20, padding: '36px 32px',
          boxShadow: '0 0 60px rgba(124,106,247,0.06)',
        }}>
          {submitted ? (
            /* ── ÉXITO ── */
            <div style={{ textAlign: 'center', padding: '16px 0' }}>
              <div style={{ fontSize: 52, marginBottom: 20 }}>🎮</div>
              <h3 style={{ fontFamily: "'Syne', sans-serif", fontSize: 22, marginBottom: 14 }}>¡Ya estás dentro!</h3>
              <p style={{ color: '#9ca3af', fontSize: 15, lineHeight: 1.75 }}>
                Muchas gracias por tu contribución.<br />
                Pronto recibirás más noticias sobre la aplicación.
              </p>
              <div style={{
                marginTop: 28, padding: '14px 20px',
                background: 'rgba(124,106,247,0.1)', borderRadius: 10,
                border: '1px solid rgba(124,106,247,0.2)',
                fontSize: 13, color: '#a89ff7', lineHeight: 1.6,
              }}>
                Estamos importando tu historial de partidas en segundo plano.
                Te avisaremos cuando todo esté listo.
              </div>
            </div>
          ) : (
            /* ── FORMULARIO ── */
            <form onSubmit={handleSubmit} noValidate>

              {/* Cuenta de Riot */}
              <div style={{ marginBottom: 20 }}>
                <label style={{ display: 'block', fontSize: 11, color: '#6b7280', textTransform: 'uppercase', letterSpacing: .9, marginBottom: 8, fontWeight: 600 }}>
                  Cuenta de Riot
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10, alignItems: 'start' }}>
                  <input
                    required
                    placeholder="NombreInvocador"
                    value={form.riot_game_name}
                    onChange={e => setForm({ ...form, riot_game_name: e.target.value })}
                    style={inputSt}
                    onFocus={e => e.target.style.borderColor = 'rgba(124,106,247,0.6)'}
                    onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
                  />
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ color: '#4b5563', fontWeight: 700, fontSize: 16 }}>#</span>
                    <input
                      required
                      placeholder="EUW"
                      value={form.riot_tag_line}
                      onChange={e => setForm({ ...form, riot_tag_line: e.target.value.replace('#', '') })}
                      style={{ ...inputSt, width: 88 }}
                      maxLength={10}
                      onFocus={e => e.target.style.borderColor = 'rgba(124,106,247,0.6)'}
                      onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
                    />
                  </div>
                </div>
                <p style={{ marginTop: 6, fontSize: 12, color: '#374151' }}>
                  Ej: zRamBoXx #EUW — tal como aparece en el cliente
                </p>
              </div>

              {/* Email */}
              <div style={{ marginBottom: 26 }}>
                <label style={{ display: 'block', fontSize: 11, color: '#6b7280', textTransform: 'uppercase', letterSpacing: .9, marginBottom: 8, fontWeight: 600 }}>
                  Correo electrónico
                </label>
                <input
                  required
                  type="email"
                  placeholder="tu@email.com"
                  value={form.email}
                  onChange={e => setForm({ ...form, email: e.target.value })}
                  style={inputSt}
                  onFocus={e => e.target.style.borderColor = 'rgba(124,106,247,0.6)'}
                  onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
                />
              </div>

              {/* Consentimiento RGPD */}
              <div style={{
                background: 'rgba(255,255,255,0.025)',
                border: '1px solid rgba(255,255,255,0.07)',
                borderRadius: 12, padding: '18px 16px', marginBottom: 22,
              }}>
                <p style={{ fontSize: 11, color: '#374151', textTransform: 'uppercase', letterSpacing: .7, fontWeight: 700, marginBottom: 16 }}>
                  Privacidad y consentimiento
                </p>

                {/* Obligatorio */}
                <label style={{ display: 'flex', gap: 11, alignItems: 'flex-start', marginBottom: 14, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    required
                    checked={form.consentimiento_datos}
                    onChange={e => setForm({ ...form, consentimiento_datos: e.target.checked })}
                    style={{ marginTop: 3, accentColor: '#7c6af7', width: 15, height: 15, flexShrink: 0, cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: 13, color: '#9ca3af', lineHeight: 1.6 }}>
                    <strong style={{ color: '#e8eaf0' }}>Acepto el tratamiento de mis datos</strong>{' '}
                    <span style={{ color: '#f87171', fontSize: 11 }}>(obligatorio)</span>
                    {'. '}LolHelper accederá a tu historial de partidas públicas de Riot Games para analizar tus patrones de juego.
                    No vendemos ni compartimos tus datos. Puedes solicitar su eliminación en cualquier momento.
                  </span>
                </label>

                {/* Opcional */}
                <label style={{ display: 'flex', gap: 11, alignItems: 'flex-start', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={form.consentimiento_emails}
                    onChange={e => setForm({ ...form, consentimiento_emails: e.target.checked })}
                    style={{ marginTop: 3, accentColor: '#7c6af7', width: 15, height: 15, flexShrink: 0, cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: 13, color: '#9ca3af', lineHeight: 1.6 }}>
                    <strong style={{ color: '#e8eaf0' }}>Quiero recibir novedades</strong>{' '}
                    <span style={{ color: '#4b5563', fontSize: 11 }}>(opcional)</span>
                    {'. '}Acepto recibir emails sobre el lanzamiento de LolHelper y actualizaciones de la app.
                  </span>
                </label>
              </div>

              {error && (
                <div style={{
                  background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.25)',
                  borderRadius: 8, padding: '12px 16px', fontSize: 14, color: '#f87171',
                  marginBottom: 18, lineHeight: 1.5,
                }}>
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={submitting}
                style={{
                  width: '100%', padding: '15px', borderRadius: 10,
                  background: submitting ? '#374151' : '#7c6af7',
                  border: 'none', color: '#fff', fontSize: 16, fontWeight: 600,
                  fontFamily: "'DM Sans', sans-serif",
                  cursor: submitting ? 'not-allowed' : 'pointer',
                  transition: 'background .15s',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  boxShadow: submitting ? 'none' : '0 0 24px rgba(124,106,247,0.3)',
                }}
                onMouseEnter={e => { if (!submitting) e.currentTarget.style.background = '#5b50c9' }}
                onMouseLeave={e => { if (!submitting) e.currentTarget.style.background = '#7c6af7' }}
              >
                {submitting ? (
                  <>
                    <div style={{ width: 16, height: 16, border: '2px solid rgba(255,255,255,0.25)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin .7s linear infinite' }} />
                    Registrando...
                  </>
                ) : 'Quiero acceso anticipado →'}
              </button>

            </form>
          )}
        </div>

        <p style={{ textAlign: 'center', fontSize: 12, color: '#374151', marginTop: 20, lineHeight: 1.6 }}>
          Tus datos se almacenan de forma segura y sólo se usarán para el análisis descrito.<br />
          Puedes solicitar la eliminación en cualquier momento escribiéndonos.
        </p>
      </section>

      {/* ── FOOTER ──────────────────────────────────────────── */}
      <footer style={{
        borderTop: '1px solid rgba(255,255,255,0.05)',
        padding: '24px 40px',
        textAlign: 'center',
        fontSize: 12, color: '#374151', lineHeight: 1.7,
      }}>
        <p>LolHelper no está afiliado con Riot Games. League of Legends es marca registrada de Riot Games, Inc.</p>
        <p>Los datos de partidas se obtienen mediante la API oficial de Riot Games conforme a sus{' '}
          <a href="https://developer.riotgames.com/policies/general" target="_blank" rel="noopener noreferrer"
            style={{ color: '#4b5563', textDecoration: 'underline' }}>
            términos de uso
          </a>.
        </p>
      </footer>

      {/* Keyframes globales inline para la landing */}
      <style>{`
        @keyframes wlBounce {
          0%, 100% { transform: translateX(-50%) translateY(0); opacity: .5; }
          50%       { transform: translateX(-50%) translateY(8px); opacity: 1; }
        }
      `}</style>
    </div>
  )
}
