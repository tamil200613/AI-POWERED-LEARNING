import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Brain, BarChart3, BookOpen, FlaskConical, LogOut } from 'lucide-react'

const links = [
  { to: '/',          icon: Brain,        label: 'Dashboard' },
  { to: '/learn',     icon: BookOpen,     label: 'Learn'     },
  { to: '/test',      icon: FlaskConical, label: 'Test'      },
  { to: '/analytics', icon: BarChart3,    label: 'Analytics' },
]

export default function Navbar() {
  const { pathname } = useLocation()
  const navigate     = useNavigate()

  function logout() {
    localStorage.clear()
    navigate('/login')
  }

  return (
    <nav style={{
      background: 'var(--bg2)',
      borderBottom: '1px solid var(--border)',
      padding: '0 2rem',
      display: 'flex',
      alignItems: 'center',
      height: 60,
      gap: '2rem',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      {/* Logo */}
      <div style={{ display:'flex', alignItems:'center', gap:'0.5rem', marginRight:'1rem' }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: 'linear-gradient(135deg, var(--accent), var(--teal))',
          display:'flex', alignItems:'center', justifyContent:'center',
        }}>
          <Brain size={18} color="#fff" />
        </div>
        <span style={{ fontFamily:'var(--font-display)', fontWeight:700, fontSize:'1.1rem' }}>
          AdaptLearn
        </span>
      </div>

      {/* Nav links */}
      {links.map(({ to, icon: Icon, label }) => {
        const active = pathname === to
        return (
          <Link
            key={to} to={to}
            style={{
              display:'flex', alignItems:'center', gap:'0.4rem',
              padding:'0.4rem 0.75rem', borderRadius: 8,
              textDecoration:'none', fontSize:'0.875rem', fontWeight: 500,
              color: active ? 'var(--text)' : 'var(--text2)',
              background: active ? 'var(--bg3)' : 'transparent',
              border: active ? '1px solid var(--border)' : '1px solid transparent',
              transition:'var(--transition)',
            }}
          >
            <Icon size={16} />
            {label}
          </Link>
        )
      })}

      <div style={{ marginLeft:'auto' }}>
        <button className="btn btn-ghost" onClick={logout} style={{ gap:'0.4rem' }}>
          <LogOut size={15} />
          Logout
        </button>
      </div>
    </nav>
  )
}
