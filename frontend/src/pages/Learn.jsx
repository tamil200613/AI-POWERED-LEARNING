import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { learningAPI, tutorAPI, studentAPI } from '../api/client.js'
import { Send, Bot, User, ChevronRight, Sparkles, RotateCcw, FlaskConical } from 'lucide-react'
import toast from 'react-hot-toast'

const MODES = [
  { key:'explain', label:'Explain' },
  { key:'solve', label:'Step-by-Step' },
  { key:'example', label:'Examples' },
  { key:'search', label:'AI Search' },
  { key:'quiz', label:'Quiz Me' },
]

export default function Learn() {
  const navigate = useNavigate()
  // ✅ FIXED HERE
  const user_id = localStorage.getItem('user_id')

  const [path, setPath] = useState(null)
  const [loading, setLoading] = useState(true)
  const [messages, setMessages] = useState([{
    role:'assistant',
      content:"Hi! I'm your AI tutor powered by Gemini 1.5 Flash with RAG. Select a topic from your personalized learning path, then ask me anything — I'll explain concepts, solve problems step-by-step, or generate practice examples!"
  }])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [topic, setTopic] = useState('general')
  const [topicName, setTopicName] = useState('General')
  const [mode, setMode] = useState('explain')
  const chatRef = useRef(null)

  useEffect(() => {
    learningAPI.getPath(user_id, 8)
      .then(r => setPath(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [user_id])

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight
  }, [messages])

  async function sendMessage(e) {
    e?.preventDefault()
    if (!input.trim() || sending) return

    const userMsg = { role:'user', content: input.trim() }
    setMessages(m => [...m, userMsg])
    setInput('')
    setSending(true)

    try {
      const res = await tutorAPI.chat({ messages:[...messages, userMsg], topic, mode })
      setMessages(m => [...m, { role:'assistant', content: res.data.response }])
    } catch(err) {
      toast.error('Check GOOGLE_API_KEY in your .env file')
      setMessages(m => [...m, { role:'assistant', content:'⚠️ API error — please add your GOOGLE_API_KEY to backend/.env and restart the server.' }])
    } finally {
      setSending(false)
    }
  }

  function pickTopic(rec) {
    setTopic(rec.topic_id)
    setTopicName(rec.name || rec.topic_id)
    setMessages([{
      role:'assistant',
      content:`Let's study **${rec.name}**! Your current mastery is ${Math.round((rec.current_mastery||0)*100)}%. The RL agent ranked this #${rec.rank} for you (Q=${rec.q_value?.toFixed(2)}). What would you like to do first?`
    }])
  }

  const recs = path?.rl_recommendations || []

  return (
    <div className="fade-in" style={{ display:'grid', gridTemplateColumns:'300px 1fr', gap:'1.5rem', height:'calc(100vh - 120px)' }}>

      {/* Learning Path Panel */}
      <div className="card" style={{ display:'flex', flexDirection:'column', overflow:'hidden', padding:'1rem' }}>
        <div style={{ display:'flex', alignItems:'center', gap:'0.5rem', marginBottom:'0.5rem' }}>
          <Sparkles size={15} color="var(--accent)" />
          <span style={{ fontFamily:'var(--font-display)', fontWeight:700, fontSize:'0.95rem' }}>AI Learning Path</span>
        </div>
        <p style={{ fontSize:'0.72rem', color:'var(--text3)', marginBottom:'1rem' }}>
          DQN RL recommendations · ε={path?.epsilon?.toFixed(3)||'...'}
        </p>

        {loading ? <div style={{display:'flex',justifyContent:'center',padding:'2rem'}}><div className="spinner"/></div>
        : recs.length === 0 ? <p style={{color:'var(--text3)',fontSize:'0.8rem'}}>Complete an assessment to get recommendations.</p>
        : (
          <div style={{ overflowY:'auto', flex:1, display:'flex', flexDirection:'column', gap:'0.5rem' }}>
            {recs.map((rec, i) => {
              const active = rec.topic_id === topic
              const pct    = Math.round((rec.current_mastery||0)*100)
              const col    = pct >= 80 ? 'var(--green)' : pct >= 40 ? 'var(--amber)' : 'var(--coral)'
              return (
                <div key={rec.topic_id} onClick={() => pickTopic(rec)} style={{
                  padding:'0.75rem', borderRadius:10, cursor:'pointer',
                  background: active ? 'rgba(108,99,255,0.12)' : 'var(--bg3)',
                  border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
                  transition:'var(--transition)',
                }}>
                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'0.35rem' }}>
                    <span style={{ fontSize:'0.82rem', fontWeight:600 }}>#{i+1} {rec.name||rec.topic_id}</span>
                    <ChevronRight size={13} color="var(--text3)" />
                  </div>
                  <div style={{ fontSize:'0.7rem', color:'var(--text3)', marginBottom:'0.4rem' }}>
                    {rec.subject} · Q={rec.q_value?.toFixed(2)}
                  </div>
                  <div className="mastery-bar">
                    <div className="mastery-fill" style={{ width:`${pct}%`, background:col }} />
                  </div>
                  <div style={{ fontSize:'0.68rem', color:col, marginTop:'0.2rem' }}>{pct}% mastery</div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* AI Tutor Chat */}
      <div className="card" style={{ display:'flex', flexDirection:'column', padding:0, overflow:'hidden' }}>
        {/* Header */}
        <div style={{ padding:'0.875rem 1.25rem', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap:'0.75rem', flexWrap:'wrap' }}>
          <div style={{ width:34,height:34,borderRadius:9,background:'linear-gradient(135deg,var(--accent),var(--teal))',display:'flex',alignItems:'center',justifyContent:'center' }}>
            <Bot size={18} color="#fff" />
          </div>
          <div>
            <div style={{ fontWeight:700, fontFamily:'var(--font-display)', fontSize:'0.95rem' }}>AI Tutor</div>
            <div style={{ fontSize:'0.7rem', color:'var(--text3)' }}>{topicName} · RAG + Gemini 1.5 Flash</div>
          </div>
          <div style={{ marginLeft:'auto', display:'flex', gap:'0.35rem', flexWrap:'wrap' }}>
            {MODES.map(m => (
              <button key={m.key} onClick={() => setMode(m.key)} style={{
                padding:'0.28rem 0.55rem', borderRadius:6, border:'none', cursor:'pointer',
                fontSize:'0.72rem', fontWeight:500, fontFamily:'var(--font)',
                background: mode===m.key ? 'var(--accent)' : 'var(--bg3)',
                color:      mode===m.key ? '#fff'          : 'var(--text2)',
                transition: 'var(--transition)',
              }}>{m.label}</button>
            ))}
            <button onClick={() => setMessages([{ role:'assistant', content:'Chat cleared! Pick a topic and ask away.' }])} title="Clear chat"
              style={{ padding:'0.28rem 0.55rem', borderRadius:6, border:'none', cursor:'pointer', background:'var(--bg3)', color:'var(--text2)', display:'flex', alignItems:'center' }}>
              <RotateCcw size={12} />
            </button>
            <button onClick={() => navigate('/test', { state: { initialTopicId: topic, initialTopicName: topicName } })} title="Take Topic Test"
              style={{ padding:'0.28rem 0.55rem', borderRadius:6, border:'none', cursor:'pointer', background:'var(--teal)', color:'#fff', display:'flex', alignItems:'center', gap:'0.3rem', fontWeight:600, fontSize:'0.72rem', marginLeft:'0.5rem' }}>
              <FlaskConical size={12} /> Test
            </button>
          </div>
        </div>

        {/* Messages */}
        <div ref={chatRef} style={{ flex:1, overflowY:'auto', padding:'1.25rem', display:'flex', flexDirection:'column', gap:'0.875rem' }}>
          {messages.map((msg, i) => (
            <div key={i} style={{ display:'flex', gap:'0.625rem', flexDirection:msg.role==='user'?'row-reverse':'row' }}>
              <div style={{ width:30,height:30,borderRadius:8,flexShrink:0,display:'flex',alignItems:'center',justifyContent:'center',
                background: msg.role==='user' ? 'rgba(108,99,255,0.2)' : 'linear-gradient(135deg,var(--accent),var(--teal))' }}>
                {msg.role==='user' ? <User size={14} color="var(--accent)" /> : <Bot size={14} color="#fff" />}
              </div>
              <div style={{ maxWidth:'78%', padding:'0.75rem 0.9rem', borderRadius:10,
                background: msg.role==='user' ? 'rgba(108,99,255,0.1)' : 'var(--bg3)',
                border:     msg.role==='user' ? '1px solid rgba(108,99,255,0.2)' : '1px solid var(--border)',
                fontSize:'0.85rem', lineHeight:1.75, whiteSpace:'pre-wrap' }}>
                {msg.content}
              </div>
            </div>
          ))}
          {sending && (
            <div style={{ display:'flex', gap:'0.625rem' }}>
              <div style={{ width:30,height:30,borderRadius:8,background:'linear-gradient(135deg,var(--accent),var(--teal))',display:'flex',alignItems:'center',justifyContent:'center' }}>
                <Bot size={14} color="#fff" />
              </div>
              <div style={{ padding:'0.75rem', borderRadius:10, background:'var(--bg3)', border:'1px solid var(--border)', display:'flex', gap:5, alignItems:'center' }}>
                {[0,1,2].map(j => <div key={j} style={{ width:5,height:5,borderRadius:'50%',background:'var(--text3)',animation:`bounce3 1.2s ${j*0.2}s infinite ease-in-out` }} />)}
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div style={{ padding:'0.875rem 1.25rem', borderTop:'1px solid var(--border)' }}>
          <form onSubmit={sendMessage} style={{ display:'flex', gap:'0.625rem' }}>
            <input value={input} onChange={e=>setInput(e.target.value)}
              placeholder={`Ask about ${topicName}... (${MODES.find(m=>m.key===mode)?.label} mode)`}
              disabled={sending} style={{ flex:1 }}
              onKeyDown={e => e.key==='Enter' && !e.shiftKey && sendMessage(e)} />
            <button type="submit" className="btn btn-primary" disabled={sending||!input.trim()} style={{ padding:'0.6rem 0.9rem' }}>
              <Send size={15} />
            </button>
          </form>
          <p style={{ fontSize:'0.68rem', color:'var(--text3)', marginTop:'0.4rem' }}>
            RAG retrieves relevant educational content · Powered by Gemini 1.5 Flash
          </p>
        </div>
      </div>

      <style>{`@keyframes bounce3{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-5px)}}`}</style>
    </div>
  )
}
