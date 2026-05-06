import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import Navbar        from './components/Navbar'
import Login         from './pages/Login'
import Dashboard     from './pages/Dashboard'
import Historial     from './pages/Historial'
import Objetivo      from './pages/Objetivo'
import Cuenta        from './pages/Cuenta'
import Analisis      from './pages/Analisis'
import Waitlist      from './pages/Waitlist'

function Shell({ children }) {
  return (
    <div className="app-shell">
      <Navbar />
      <main className="main-content">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Landing pública — completamente aislada del resto de la app */}
        <Route path="/unete" element={<Waitlist />} />
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={
          <ProtectedRoute><Shell><Dashboard /></Shell></ProtectedRoute>
        }/>
        <Route path="/historial" element={
          <ProtectedRoute><Shell><Historial /></Shell></ProtectedRoute>
        }/>
        <Route path="/objetivo" element={
          <ProtectedRoute><Shell><Objetivo /></Shell></ProtectedRoute>
        }/>
        <Route path="/cuenta" element={
          <ProtectedRoute><Shell><Cuenta /></Shell></ProtectedRoute>
        }/>
        <Route path="/analisis" element={
          <ProtectedRoute><Shell><Analisis /></Shell></ProtectedRoute>
        }/>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
