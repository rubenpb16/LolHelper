import { Navigate } from 'react-router-dom'

export default function ProProtectedRoute({ children }) {
  const raw  = localStorage.getItem('pro_user')
  const user = raw ? JSON.parse(raw) : null
  if (!user || user.rol !== 'profesional') {
    return <Navigate to="/pro/login" replace />
  }
  return children
}
