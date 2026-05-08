import axios from 'axios'

// En Railway se inyecta VITE_API_URL en el build; en local cae al fallback.
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: BASE,
  withCredentials: true,  // envía la cookie httpOnly automáticamente
})

// Si el servidor devuelve 401, limpiar datos locales y redirigir al login
api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export const auth = {
  register: d  => api.post('/auth/register', d),
  login:    d  => api.post('/auth/login',
                   new URLSearchParams(d),
                   { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }),
  me:       ()  => api.get('/auth/me'),
  password: d  => api.put('/auth/password', d),
  logout:   ()  => api.post('/auth/logout'),
}

export const dashboard = {
  get:  ()                    => api.get('/dashboard'),
  mes:  (year, month)         => api.get(`/dashboard/mes?year=${year}&month=${month}`),
  dia:  (fecha)               => api.get(`/dashboard/dia?fecha=${fecha}`),
}

export const historial = {
  get: ({ dias = 30, limit = 50, offset = 0, fecha_inicio, fecha_fin } = {}) => {
    const qs = new URLSearchParams({ limit, offset })
    if (fecha_inicio && fecha_fin) {
      qs.set('fecha_inicio', fecha_inicio)
      qs.set('fecha_fin',    fecha_fin)
    } else {
      qs.set('dias', dias)
    }
    return api.get(`/historial?${qs}`)
  },
}

export const objetivo = {
  get:    ()  => api.get('/objetivo'),
  update: d   => api.put('/objetivo', d),
}

export const stats = {
  comportamiento: (dias = 30) => api.get(`/stats/comportamiento?dias=${dias}`),
  analisis: ({ dias = 30, fecha_inicio, fecha_fin } = {}) => {
    const qs = new URLSearchParams()
    if (fecha_inicio && fecha_fin) {
      qs.set('fecha_inicio', fecha_inicio)
      qs.set('fecha_fin_p',  fecha_fin)
    } else {
      qs.set('dias', dias)
    }
    return api.get(`/stats/analisis?${qs}`)
  },
  rankHistoria: (dias = 60) => api.get(`/stats/rank-historia?dias=${dias}`),
}

export const waitlist = {
  register: (data) => api.post('/waitlist', data),
}

// ── B2B: Profesionales ────────────────────────────────────────

export const proAuth = {
  registro: (data) => api.post('/pro/registro', data),
  login: (data) => api.post('/auth/login',
    new URLSearchParams(data),
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  ),
  me:     () => api.get('/pro/me'),
  logout: () => api.post('/auth/logout'),
}

export const proInvitacion = {
  info:    (token)        => api.get(`/invitacion/${token}`),
  aceptar: (token, data)  => api.post(`/invitacion/${token}/aceptar`, data),
}

export const proPacientes = {
  lista:          ()                              => api.get('/pro/pacientes'),
  dashboard:      (id)                            => api.get(`/pro/pacientes/${id}/dashboard`),
  historial:      (id, params = {})               => {
    const qs = new URLSearchParams()
    if (params.fecha_inicio && params.fecha_fin) {
      qs.set('fecha_inicio', params.fecha_inicio)
      qs.set('fecha_fin',    params.fecha_fin)
    } else {
      qs.set('dias', params.dias ?? 30)
    }
    qs.set('limit',  params.limit  ?? 50)
    qs.set('offset', params.offset ?? 0)
    return api.get(`/pro/pacientes/${id}/historial?${qs}`)
  },
  analisis:       (id, params = {})               => {
    const qs = new URLSearchParams()
    if (params.fecha_inicio && params.fecha_fin) {
      qs.set('fecha_inicio', params.fecha_inicio)
      qs.set('fecha_fin_p',  params.fecha_fin)
    } else {
      qs.set('dias', params.dias ?? 30)
    }
    return api.get(`/pro/pacientes/${id}/analisis?${qs}`)
  },
  rankHistoria:   (id, dias = 60)                 => api.get(`/pro/pacientes/${id}/rank-historia?dias=${dias}`),
  mes:            (id, year, month)               => api.get(`/pro/pacientes/${id}/mes?year=${year}&month=${month}`),
  dia:            (id, fecha)                     => api.get(`/pro/pacientes/${id}/dia?fecha=${fecha}`),
  notas:          (id)                            => api.get(`/pro/pacientes/${id}/notas`),
  resumenConsulta:(id, dias = 7)                  => api.get(`/pro/pacientes/${id}/resumen-consulta?dias=${dias}`),
  comparativa:    (id, diasActual = 30, diasAnt = 30) => api.get(`/pro/pacientes/${id}/comparativa?dias_actual=${diasActual}&dias_anterior=${diasAnt}`),
  crearNota:      (id, contenido, categoria = 'observacion') => api.post(`/pro/pacientes/${id}/notas`, { contenido, categoria }),
  editarNota:     (id, notaId, contenido, categoria = 'observacion') => api.put(`/pro/pacientes/${id}/notas/${notaId}`, { contenido, categoria }),
  borrarNota:     (id, notaId)                    => api.delete(`/pro/pacientes/${id}/notas/${notaId}`),
  actualizarEstado: (id, estado)                  => api.patch(`/pro/pacientes/${id}/estado`, { estado }),
}

export const sync = {
  me: () => api.post('/sync/me'),
}

export default api
