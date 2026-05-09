import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authAPI } from '../api/client.js'
import toast from 'react-hot-toast'
import { Brain, Mail, Lock, User, Eye, EyeOff } from 'lucide-react'

export default function Login() {
  const [mode,    setMode]    = useState('login')
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const navigate = useNavigate()

  const [form, setForm] = useState({
    email: '', password: '', username: '', full_name: '', grade_level: 10,
  })

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setLoading(true)
    try {
      let res
      if (mode === 'login') {
        res = await authAPI.login(form.email, form.password)
      } else {
        res = await authAPI.register({
          email: form.email,
          password: form.password,
          username: form.username,
          full_name: form.full_name,
          grade_level: parseInt(form.grade_level),
        })
      }

      // ✅ FIX: Save token + user_id correctly
      localStorage.setItem('token', res.data.access_token)
      localStorage.setItem('user_id', res.data.user_id)

      toast.success(mode === 'login' ? 'Welcome back!' : 'Account created!')
      navigate('/')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center',
      background:'var(--bg)',
      backgroundImage:'radial-gradient(ellipse 80% 60% at 50% -20%, rgba(108,99,255,0.15), transparent)',
    }}>
      <div style={{ width:'100%', maxWidth: 420, padding:'0 1rem' }}>
        {/* Logo */}
        <div style={{ textAlign:'center', marginBottom:'2rem' }}>
          <div style={{
            width:56, height:56, borderRadius:16, margin:'0 auto 1rem',
            background:'linear-gradient(135deg, var(--accent), var(--teal))',
            display:'flex', alignItems:'center', justifyContent:'center',
          }}>
            <Brain size={28} color="#fff" />
          </div>
          <h1 style={{ fontFamily:'var(--font-display)', fontSize:'1.75rem', fontWeight:800 }}>
            AdaptLearn
          </h1>
          <p style={{ color:'var(--text2)', fontSize:'0.875rem', marginTop:'0.25rem' }}>
            AI-Powered Adaptive Learning System
          </p>
        </div>

        <div className="card" style={{ padding:'2rem' }}>
          {/* Mode toggle */}
          <div style={{ display:'flex', background:'var(--bg3)', borderRadius:10, padding:4, marginBottom:'1.5rem' }}>
            {['login','register'].map(m => (
              <button key={m} onClick={() => setMode(m)} style={{
                flex:1, padding:'0.5rem', border:'none', borderRadius:8,
                fontFamily:'var(--font)', fontSize:'0.875rem', fontWeight:500, cursor:'pointer',
                background: mode===m ? 'var(--bg2)' : 'transparent',
                color: mode===m ? 'var(--text)' : 'var(--text2)',
                transition:'var(--transition)',
              }}>
                {m === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>

          <form onSubmit={submit} style={{ display:'flex', flexDirection:'column', gap:'1rem' }}>
            {mode === 'register' && (
              <>
                <div>
                  <label>Full Name</label>
                  <div style={{ position:'relative', marginTop:4 }}>
                    <User size={15} style={{ position:'absolute', left:10, top:'50%', transform:'translateY(-50%)', color:'var(--text3)' }} />
                    <input style={{ paddingLeft:32 }} placeholder="Your name" value={form.full_name} onChange={set('full_name')} />
                  </div>
                </div>
                <div>
                  <label>Username</label>
                  <input placeholder="username" value={form.username} onChange={set('username')} required />
                </div>
              </>
            )}

            <div>
              <label>Email</label>
              <div style={{ position:'relative', marginTop:4 }}>
                <Mail size={15} style={{ position:'absolute', left:10, top:'50%', transform:'translateY(-50%)', color:'var(--text3)' }} />
                <input style={{ paddingLeft:32 }} type="email" placeholder="you@example.com" value={form.email} onChange={set('email')} required />
              </div>
            </div>

            <div>
              <label>Password</label>
              <div style={{ position:'relative', marginTop:4 }}>
                <Lock size={15} style={{ position:'absolute', left:10, top:'50%', transform:'translateY(-50%)', color:'var(--text3)' }} />
                <input 
                  style={{ paddingLeft:32, paddingRight:36 }} 
                  type={showPassword ? 'text' : 'password'} 
                  placeholder="••••••••" 
                  value={form.password} 
                  onChange={set('password')} 
                  required 
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position:'absolute', right:10, top:'50%', transform:'translateY(-50%)',
                    background:'none', border:'none', cursor:'pointer', color:'var(--text3)',
                    display:'flex', alignItems:'center'
                  }}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {mode === 'register' && (
              <div>
                <label>Grade Level</label>
                <select value={form.grade_level} onChange={set('grade_level')}>
                  {[6,7,8,9,10,11,12].map(g => <option key={g} value={g}>Grade {g}</option>)}
                  <option value={13}>Undergraduate</option>
                  <option value={14}>Graduate</option>
                </select>
              </div>
            )}

            <button className="btn btn-primary" type="submit" disabled={loading} style={{ width:'100%', justifyContent:'center', padding:'0.75rem', marginTop:'0.5rem' }}>
              {loading ? <span className="spinner" style={{ width:18, height:18 }} /> : (mode === 'login' ? 'Sign In' : 'Create Account')}
            </button>
          </form>

          <p style={{ textAlign:'center', fontSize:'0.75rem', color:'var(--text3)', marginTop:'1.25rem' }}>
            Demo: register any account to start exploring
          </p>
        </div>
      </div>
    </div>
  )
}