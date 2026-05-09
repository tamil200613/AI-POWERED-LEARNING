import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Navbar from './components/Navbar.jsx'
import Home from './pages/Home.jsx'
import Learn from './pages/Learn.jsx'
import Test from './pages/Test.jsx'
import Analytics from './pages/Analytics.jsx'
import Login from './pages/Login.jsx'

function PrivateRoute({ children }) {
  const token = localStorage.getItem('token')
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#181d2a',
            color: '#e8ecf4',
            border: '1px solid #232840',
            borderRadius: '12px',
            fontFamily: 'Inter, sans-serif',
            fontSize: '0.875rem',
          },
        }}
      />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={
          <PrivateRoute>
            <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
              <Navbar />
              <main style={{ flex: 1, padding: '2rem', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
                <Routes>
                  <Route path="/"          element={<Home />} />
                  <Route path="/learn"     element={<Learn />} />
                  <Route path="/test"      element={<Test />} />
                  <Route path="/analytics" element={<Analytics />} />
                </Routes>
              </main>
            </div>
          </PrivateRoute>
        } />
      </Routes>
    </BrowserRouter>
  )
}
