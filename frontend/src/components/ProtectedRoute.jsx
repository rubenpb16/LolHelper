import { Navigate } from 'react-router-dom'

export default function ProtectedRoute({ children }) {
  // El token viaja en una cookie httpOnly (no accesible desde JS).
  // Usamos el perfil en localStorage como indicador de sesión activa.
  // Si la cookie ha expirado, el primer API call devolverá 401 y el
  // interceptor de axios redirigirá al login automáticamente.
  const user = localStorage.getItem('user')
  if (!user) return <Navigate to="/login" replace />
  return children
}
