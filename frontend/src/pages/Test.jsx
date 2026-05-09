import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { assessmentAPI } from '../api/client.js'
import { FlaskConical, CheckCircle, XCircle, ChevronRight, BarChart2, RefreshCw } from 'lucide-react'
import toast from 'react-hot-toast'

const TOPICS = [
  { id:'math_derivatives', name:'Derivatives' },
  { id:'cs_oop',           name:'OOP' },
  { id:'phys_kinematics',  name:'Kinematics' },
  { id:'math_statistics',  name:'Statistics' },
  { id:'cs_algorithms',    name:'Algorithms' },
  { id:'cs_data_structures',name:'Data Structures'},
]

const QTYPES = ['mcq','descriptive','coding']

export default function Test() {
  const location = useLocation()
  
  const initialTopicFromState = location.state?.initialTopicId 
    ? { id: location.state.initialTopicId, name: location.state.initialTopicName || location.state.initialTopicId }
    : null;

  const availableTopics = [...TOPICS];
  if (initialTopicFromState && !availableTopics.find(t => t.id === initialTopicFromState.id)) {
    availableTopics.unshift(initialTopicFromState);
  }

  const [phase,       setPhase]       = useState('setup')   // setup | testing | done
  const [topic,       setTopic]       = useState(initialTopicFromState || TOPICS[0])
  const [qType,       setQType]       = useState('mcq')
  const [session,     setSession]     = useState(null)
  const [current,     setCurrent]     = useState(null)
  const [answer,      setAnswer]      = useState('')
  const [responses,   setResponses]   = useState([])
  const [submitting,  setSubmitting]  = useState(false)
  const [lastResult,  setLastResult]  = useState(null)
  const [history,     setHistory]     = useState([])
  const [finalStats,  setFinalStats]  = useState(null)

  async function startTest() {
    setSubmitting(true)
    try {
      const res = await assessmentAPI.startAdaptive({ topic_id: topic.id, max_items: 10 })
      setSession(res.data)
      setCurrent(res.data)
      setResponses([])
      setHistory([])
      setLastResult(null)
      setPhase('testing')
    } catch(e) {
      console.error(e)
      toast.error(e.response?.data?.detail || 'Failed to start test')
    } finally { setSubmitting(false) }
  }

  async function submitAnswer() {
    if (!answer.trim() || submitting) return
    setSubmitting(true)
    try {
      const irt = current.irt_params || current.question?.irt_params || { a:1, b:0, c:0.25 }
      const payload = {
        question_id:      current.question_id || 'q1',
        topic_id:         topic.id,
        student_answer:   answer,
        correct_answer:   current.question?.correct_answer || '',
        irt_a:            irt.a,
        irt_b:            irt.b,
        irt_c:            irt.c,
        current_responses: responses,
      }
      const res = await assessmentAPI.submitAnswer(payload)
      const data = res.data

      setLastResult(data)
      setHistory(h => [...h, {
        q:       current.question?.question || 'Question',
        answer,
        correct: data.is_correct,
        score:   data.score,
        feedback:data.feedback,
        ability: data.ability_after,
      }])

      // Add response to IRT history
      setResponses(r => [...r, { a: irt.a, b: irt.b, c: irt.c, response: data.is_correct ? 1 : 0, question_id: current.question_id }])
      setAnswer('')

      if (data.test_complete || !data.next_question) {
        setFinalStats({
          finalAbility:  data.ability_after,
          se:            data.standard_error,
          mastery:       data.mastery_score,
          itemsAnswered: data.items_answered,
          stopReason:    data.stop_reason,
        })
        setPhase('done')
      } else {
        setCurrent(data.next_question)
        setLastResult(null) // clear for next question after brief show
      }
    } catch(e) {
      toast.error('Submission failed')
    } finally { setSubmitting(false) }
  }

  function reset() {
    setPhase('setup')
    setSession(null)
    setCurrent(null)
    setAnswer('')
    setResponses([])
    setHistory([])
    setLastResult(null)
    setFinalStats(null)
  }

  // ── Setup Phase ──
  if (phase === 'setup') return (
    <div className="fade-in" style={{ maxWidth:640, margin:'0 auto' }}>
      <h1 style={{ fontFamily:'var(--font-display)', fontSize:'2rem', fontWeight:800, marginBottom:'0.5rem' }}>
        Adaptive Assessment
      </h1>
      <p style={{ color:'var(--text2)', marginBottom:'2rem' }}>
        IRT 3-Parameter Logistic model · Questions calibrated to your ability in real-time
      </p>

      <div className="card" style={{ marginBottom:'1.5rem' }}>
        <h3 style={{ fontWeight:700, marginBottom:'1rem' }}>Select Topic</h3>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:'0.5rem' }}>
          {availableTopics.map(t => (
            <div key={t.id} onClick={() => setTopic(t)} style={{
              padding:'0.75rem', borderRadius:10, cursor:'pointer', textAlign:'center',
              background: topic.id===t.id ? 'rgba(108,99,255,0.15)' : 'var(--bg3)',
              border:     topic.id===t.id ? '1px solid var(--accent)' : '1px solid var(--border)',
              fontSize:'0.8rem', fontWeight:600, transition:'var(--transition)',
            }}>
              {t.name}
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginBottom:'1.5rem' }}>
        <h3 style={{ fontWeight:700, marginBottom:'1rem' }}>Question Type</h3>
        <div style={{ display:'flex', gap:'0.5rem' }}>
          {QTYPES.map(q => (
            <button key={q} onClick={() => setQType(q)} style={{
              padding:'0.5rem 1rem', borderRadius:8, border:'none', cursor:'pointer',
              fontFamily:'var(--font)', fontSize:'0.8rem', fontWeight:500,
              background: qType===q ? 'var(--teal)' : 'var(--bg3)',
              color:      qType===q ? 'var(--bg)'   : 'var(--text2)',
              transition: 'var(--transition)', textTransform:'capitalize',
            }}>{q}</button>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginBottom:'1.5rem', background:'rgba(108,99,255,0.05)', borderColor:'rgba(108,99,255,0.2)' }}>
        <h4 style={{ fontWeight:600, marginBottom:'0.5rem', color:'var(--accent2)' }}>How It Works</h4>
        <ul style={{ fontSize:'0.8rem', color:'var(--text2)', lineHeight:2, paddingLeft:'1rem' }}>
          <li>Each question is selected using Maximum Information criterion (Fisher Information)</li>
          <li>Ability θ updated after each response using EAP/MLE estimation</li>
          <li>Test stops when SE &lt; 0.3 or after 10 questions</li>
          <li>AI generates questions tailored to your estimated ability level</li>
        </ul>
      </div>

      <button className="btn btn-primary" onClick={startTest} disabled={submitting} style={{ width:'100%', justifyContent:'center', padding:'0.875rem', fontSize:'1rem' }}>
        {submitting ? <span className="spinner" /> : <><FlaskConical size={18} /> Start Adaptive Test</>}
      </button>
    </div>
  )

  // ── Done Phase ──
  if (phase === 'done') return (
    <div className="fade-in" style={{ maxWidth:700, margin:'0 auto' }}>
      <div className="card" style={{ textAlign:'center', padding:'2.5rem', marginBottom:'1.5rem', background:'rgba(20,217,196,0.05)', borderColor:'rgba(20,217,196,0.2)' }}>
        <BarChart2 size={48} color="var(--teal)" style={{ marginBottom:'1rem' }} />
        <h2 style={{ fontFamily:'var(--font-display)', fontWeight:800, fontSize:'1.75rem', marginBottom:'0.5rem' }}>Test Complete!</h2>
        <p style={{ color:'var(--text2)', marginBottom:'2rem' }}>{finalStats?.stopReason?.replace(/_/g,' ')}</p>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:'1rem' }}>
          {[
            { label:'Final Ability (θ)', value: finalStats?.finalAbility?.toFixed(3), color:'var(--accent)' },
            { label:'Std Error',         value: finalStats?.se?.toFixed(3),           color:'var(--amber)'  },
            { label:'Mastery Score',     value: Math.round((finalStats?.mastery||0)*100)+'%', color:'var(--teal)' },
            { label:'Items Answered',    value: finalStats?.itemsAnswered,             color:'var(--green)'  },
          ].map(({ label, value, color }) => (
            <div key={label} style={{ background:'var(--bg3)', borderRadius:10, padding:'1rem', border:'1px solid var(--border)' }}>
              <div style={{ fontSize:'1.6rem', fontWeight:700, fontFamily:'var(--font-display)', color }}>{value}</div>
              <div style={{ fontSize:'0.7rem', color:'var(--text3)', marginTop:'0.25rem' }}>{label}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginBottom:'1.5rem' }}>
        <h3 style={{ fontWeight:700, marginBottom:'1rem' }}>Question Review</h3>
        {history.map((h, i) => (
          <div key={i} style={{ display:'flex', gap:'0.75rem', padding:'0.75rem 0', borderBottom: i<history.length-1?'1px solid var(--border)':'none' }}>
            <div style={{ width:24,height:24,borderRadius:'50%',display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0,background: h.correct?'rgba(34,197,94,0.15)':'rgba(255,107,107,0.15)' }}>
              {h.correct ? <CheckCircle size={14} color="var(--green)" /> : <XCircle size={14} color="var(--coral)" />}
            </div>
            <div style={{ flex:1 }}>
              <div style={{ fontSize:'0.8rem', fontWeight:600, marginBottom:'0.25rem' }}>Q{i+1}: {h.q?.slice(0,80)}{h.q?.length>80?'…':''}</div>
              <div style={{ fontSize:'0.75rem', color:'var(--text2)' }}>Your answer: {h.answer?.slice(0,60)}</div>
              {h.feedback && <div style={{ fontSize:'0.72rem', color:'var(--text3)', marginTop:'0.2rem' }}>{h.feedback}</div>}
            </div>
            <div style={{ fontSize:'0.75rem', color:'var(--text3)', flexShrink:0 }}>θ={h.ability?.toFixed(2)}</div>
          </div>
        ))}
      </div>

      <button className="btn btn-primary" onClick={reset} style={{ width:'100%', justifyContent:'center', padding:'0.875rem' }}>
        <RefreshCw size={16} /> Take Another Test
      </button>
    </div>
  )

  // ── Testing Phase ──
  const q = current?.question || {}
  const irt = current?.irt_params || {}
  const itemsAnswered = responses.length
  const progressPct   = Math.round(itemsAnswered / 10 * 100)

  return (
    <div className="fade-in" style={{ maxWidth:700, margin:'0 auto' }}>
      {/* Progress */}
      <div className="card" style={{ padding:'1rem', marginBottom:'1rem' }}>
        <div style={{ display:'flex', justifyContent:'space-between', fontSize:'0.8rem', color:'var(--text2)', marginBottom:'0.5rem' }}>
          <span>Question {itemsAnswered + 1} of ~10</span>
          <span>Topic: {topic.name} · b={irt.b?.toFixed(2)} · a={irt.a?.toFixed(2)}</span>
        </div>
        <div className="mastery-bar" style={{ height:8 }}>
          <div className="mastery-fill" style={{ width:`${progressPct}%`, background:'linear-gradient(90deg,var(--accent),var(--teal))' }} />
        </div>
      </div>

      {/* Question */}
      <div className="card" style={{ marginBottom:'1rem' }}>
        <div style={{ display:'flex', gap:'0.5rem', marginBottom:'1rem' }}>
          <span className="badge badge-blue" style={{ textTransform:'capitalize' }}>{q.type || qType}</span>
          <span className="badge" style={{ background:'rgba(245,158,11,0.15)', color:'var(--amber)' }}>
            Difficulty: {q.difficulty ? Math.round(q.difficulty*100)+'%' : '—'}
          </span>
          <span className="badge" style={{ background:'rgba(108,99,255,0.12)', color:'var(--accent2)' }}>
            IRT b={irt.b?.toFixed(2)||'—'}
          </span>
        </div>

        <p style={{ fontSize:'0.95rem', lineHeight:1.8, marginBottom:'1.25rem' }}>
          {q.question || 'Loading question...'}
        </p>

        {/* MCQ options */}
        {q.options && (
          <div style={{ display:'flex', flexDirection:'column', gap:'0.5rem', marginBottom:'1rem' }}>
            {q.options.map((opt, i) => (
              <div key={i} onClick={() => setAnswer(opt)} style={{
                padding:'0.75rem 1rem', borderRadius:8, cursor:'pointer',
                background: answer===opt ? 'rgba(108,99,255,0.15)' : 'var(--bg3)',
                border:     answer===opt ? '1px solid var(--accent)' : '1px solid var(--border)',
                fontSize:'0.875rem', transition:'var(--transition)',
              }}>
                {opt}
              </div>
            ))}
          </div>
        )}

        {/* Open-ended */}
        {!q.options && (
          <textarea value={answer} onChange={e=>setAnswer(e.target.value)}
            placeholder="Type your answer here..." rows={4}
            style={{ resize:'vertical', fontFamily:'var(--font-mono)', fontSize:'0.85rem' }} />
        )}
      </div>

      {/* Last result feedback */}
      {lastResult && (
        <div className="card" style={{ marginBottom:'1rem', borderColor: lastResult.is_correct?'rgba(34,197,94,0.3)':'rgba(255,107,107,0.3)', background: lastResult.is_correct?'rgba(34,197,94,0.05)':'rgba(255,107,107,0.05)' }}>
          <div style={{ display:'flex', alignItems:'center', gap:'0.5rem' }}>
            {lastResult.is_correct
              ? <CheckCircle size={18} color="var(--green)" />
              : <XCircle    size={18} color="var(--coral)" />}
            <span style={{ fontWeight:600, color: lastResult.is_correct?'var(--green)':'var(--coral)' }}>
              {lastResult.is_correct ? 'Correct!' : 'Incorrect'}
            </span>
            <span style={{ fontSize:'0.8rem', color:'var(--text3)', marginLeft:'auto' }}>
              θ: {lastResult.ability_before?.toFixed(2)} → {lastResult.ability_after?.toFixed(2)}
            </span>
          </div>
          {lastResult.feedback && <p style={{ fontSize:'0.8rem', color:'var(--text2)', marginTop:'0.5rem' }}>{lastResult.feedback}</p>}
        </div>
      )}

      <button className="btn btn-primary" onClick={submitAnswer} disabled={!answer.trim()||submitting} style={{ width:'100%', justifyContent:'center', padding:'0.875rem', fontSize:'0.95rem' }}>
        {submitting ? <span className="spinner" /> : <>Submit Answer <ChevronRight size={16} /></>}
      </button>
    </div>
  )
}
