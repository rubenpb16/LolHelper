import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import Navbar        from './components/Navbar'
import Login         from './pages/Login'
import Dashboard     from './pages/Dashboard'
import Historial     from './pages/Historial'
import Objetivo      from './pages/Objetivo'
import Cuenta        from './pages/Cuenta'
import Analisis      from './pages/Analisis'
import Waitlist           from './pages/Waitlist'
import TftDashboard      from './pages/TftDashboard'
import TftHistorial      from './pages/TftHistorial'
import InvitacionPro      from './pages/InvitacionPro'
import ProLogin            from './pages/pro/ProLogin'
import ProRegistro         from './pages/pro/ProRegistro'
import ProDashboard        from './pages/pro/ProDashboard'
import ProPacienteDetalle  from './pages/pro/ProPacienteDetalle'
import ProProtectedRoute   from './components/ProProtectedRoute'

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
        {/* Rutas públicas */}
        <Route path="/unete"             element={<Waitlist />} />
        <Route path="/invitacion/:token" element={<InvitacionPro />} />

        {/* Portal profesional — estilo y auth completamente independientes */}
        <Route path="/pro/login"    element={<ProLogin />} />
        <Route path="/pro/registro" element={<ProRegistro />} />
        <Route path="/pro/dashboard" element={
          <ProProtectedRoute><ProDashboard /></ProProtectedRoute>
        }/>
        <Route path="/pro/pacientes/:pacienteId" element={
          <ProProtectedRoute><ProPacienteDetalle /></ProProtectedRoute>
        }/>

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
        <Route path="/tft/dashboard" element={
          <ProtectedRoute><Shell><TftDashboard /></Shell></ProtectedRoute>
        }/>
        <Route path="/tft/historial" element={
          <ProtectedRoute><Shell><TftHistorial /></Shell></ProtectedRoute>
        }/>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
