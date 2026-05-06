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
  get: () => api.get('/dashboard'),
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

export const sync = {
  me: () => api.post('/sync/me'),
}

export default api
