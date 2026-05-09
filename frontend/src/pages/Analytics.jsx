import { useEffect, useState } from 'react'
import { analyticsAPI } from '../api/client.js'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area, Cell } from 'recharts'
import { AlertTriangle, CheckCircle, TrendingUp, BookOpen } from 'lucide-react'

function MasteryCell({ topic, mastery }) {
  const pct   = Math.round(mastery * 100)
  const color = pct >= 80 ? '#22c55e' : pct >= 60 ? '#14d9c4' : pct >= 40 ? '#f59e0b' : '#ff6b6b'
  const bg    = pct >= 80 ? 'rgba(34,197,94,0.15)' : pct >= 60 ? 'rgba(20,217,196,0.12)' : pct >= 40 ? 'rgba(245,158,11,0.12)' : 'rgba(255,107,107,0.12)'
  return (
    <div title={`${topic}: ${pct}%`} style={{
      width: '100%', padding:'0.6rem 0.7rem', borderRadius:8,
      background: bg, border:`1px solid ${color}44`,
      cursor:'default',
    }}>
      <div style={{ fontSize:'0.72rem', fontWeight:600, color, marginBottom:'0.3rem', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
        {topic}
      </div>
      <div className="mastery-bar" style={{ height:5 }}>
        <div className="mastery-fill" style={{ width:`${pct}%`, background:color }} />
      </div>
      <div style={{ fontSize:'0.65rem', color, marginTop:'0.2rem' }}>{pct}%</div>
    </div>
  )
}

export default function Analytics() {
  const userId = localStorage.getItem('userId')
  const [heatmap,  setHeatmap]  = useState(null)
  const [predict,  setPredict]  = useState(null)
  const [progress, setProgress] = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [tab,      setTab]      = useState('heatmap')

  useEffect(() => {
    async function load() {
      try {
        const [h, p, pr] = await Promise.allSettled([
          analyticsAPI.getHeatmap(userId),
          analyticsAPI.getPredict(userId),
          analyticsAPI.getProgress(userId),
        ])
        if (h.status  === 'fulfilled') setHeatmap(h.value.data)
        if (p.status  === 'fulfilled') setPredict(p.value.data)
        if (pr.status === 'fulfilled') setProgress(pr.value.data)
      } catch(e) { console.error(e) }
      finally { setLoading(false) }
    }
    load()
  }, [userId])

  if (loading) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'50vh' }}>
      <div className="spinner" style={{ width:36, height:36 }} />
    </div>
  )

  const subjects = heatmap?.subjects || {}
  const summary  = heatmap?.summary  || {}

  // Progress chart data
  const progressData = (progress?.sessions || []).slice(-20).map((s, i) => ({
    session: i + 1,
    mastery:  Math.round((s.post_mastery || 0) * 100),
    gain:     Math.round((s.learning_gain || 0) * 100),
    duration: Math.round(s.duration_minutes || 0),
  }))

  const abilityData = (progress?.ability_trajectory || []).slice(-20).map((a, i) => ({
    session: i + 1,
    ability: parseFloat(((a.ability || 0) * 33 + 50).toFixed(1)),
    correct: a.correct ? 55 : 45,
  }))

  const riskColor = predict?.risk_level === 'high' ? 'var(--coral)' : predict?.risk_level === 'medium' ? 'var(--amber)' : 'var(--green)'

  const tabs = ['heatmap', 'progress', 'prediction']

  return (
    <div className="fade-in">
      <div style={{ marginBottom:'1.5rem' }}>
        <h1 style={{ fontFamily:'var(--font-display)', fontSize:'2rem', fontWeight:800 }}>Learning Analytics</h1>
        <p style={{ color:'var(--text2)', marginTop:'0.25rem' }}>Knowledge heatmaps, IRT trajectories & performance predictions</p>
      </div>

      {/* Summary row */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:'1rem', marginBottom:'1.5rem' }}>
        {[
          { icon:BookOpen,      color:'var(--accent)',  label:'Total Topics',    value: summary.total_topics   || 0 },
          { icon:CheckCircle,   color:'var(--green)',   label:'Mastered (≥80%)', value: summary.mastered       || 0 },
          { icon:TrendingUp,    color:'var(--teal)',    label:'In Progress',     value: summary.learning       || 0 },
          { icon:AlertTriangle, color:'var(--coral)',   label:'Knowledge Gaps',  value: summary.gap            || 0 },
        ].map(({ icon:Icon, color, label, value }) => (
          <div key={label} className="card" style={{ padding:'1rem', textAlign:'center' }}>
            <div style={{ width:32,height:32,borderRadius:8,background:`${color}22`,display:'flex',alignItems:'center',justifyContent:'center',margin:'0 auto 0.5rem' }}>
              <Icon size={16} color={color} />
            </div>
            <div style={{ fontSize:'1.75rem', fontWeight:700, fontFamily:'var(--font-display)', color }}>{value}</div>
            <div style={{ fontSize:'0.72rem', color:'var(--text3)', marginTop:'0.2rem' }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Tab Navigation */}
      <div style={{ display:'flex', gap:'0.4rem', marginBottom:'1.5rem', background:'var(--bg2)', padding:4, borderRadius:10, width:'fit-content', border:'1px solid var(--border)' }}>
        {tabs.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding:'0.45rem 1rem', borderRadius:8, border:'none', cursor:'pointer',
            fontFamily:'var(--font)', fontSize:'0.82rem', fontWeight:500,
            background: tab===t ? 'var(--bg3)' : 'transparent',
            color:      tab===t ? 'var(--text)' : 'var(--text2)',
            transition: 'var(--transition)', textTransform:'capitalize',
          }}>{t}</button>
        ))}
      </div>

      {/* Heatmap Tab */}
      {tab === 'heatmap' && (
        <div>
          {Object.entries(subjects).map(([subject, topics]) => (
            <div key={subject} className="card" style={{ marginBottom:'1rem' }}>
              <h3 style={{ fontFamily:'var(--font-display)', fontWeight:700, marginBottom:'1rem', textTransform:'capitalize' }}>
                {subject.replace(/_/g,' ')}
                <span style={{ fontSize:'0.8rem', fontWeight:400, color:'var(--text3)', marginLeft:'0.75rem' }}>
                  {topics.filter(t=>t.mastery>=0.8).length}/{topics.length} mastered
                </span>
              </h3>
              <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(140px,1fr))', gap:'0.5rem' }}>
                {topics.map(t => (
                  <MasteryCell key={t.topic_id} topic={t.name} mastery={t.mastery} />
                ))}
              </div>
            </div>
          ))}

          {/* Gap Subgraph */}
          {heatmap?.gap_subgraph?.nodes?.length > 0 && (
            <div className="card" style={{ borderColor:'rgba(255,107,107,0.25)' }}>
              <h3 style={{ fontFamily:'var(--font-display)', fontWeight:700, marginBottom:'1rem', color:'var(--coral)' }}>
                🔴 Knowledge Gap Network ({heatmap.gap_subgraph.nodes.length} topics)
              </h3>
              <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))', gap:'0.5rem' }}>
                {heatmap.gap_subgraph.nodes.map(n => (
                  <div key={n.id} style={{ padding:'0.75rem', borderRadius:8, background:'rgba(255,107,107,0.07)', border:'1px solid rgba(255,107,107,0.2)' }}>
                    <div style={{ fontSize:'0.8rem', fontWeight:600, marginBottom:'0.25rem' }}>{n.name}</div>
                    <div style={{ fontSize:'0.72rem', color:'var(--text3)' }}>Mastery: {Math.round((n.mastery||0)*100)}% · Difficulty: {n.difficulty}/5</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Progress Tab */}
      {tab === 'progress' && (
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1.5rem' }}>
          <div className="card">
            <h3 style={{ fontFamily:'var(--font-display)', fontWeight:700, marginBottom:'1rem' }}>Mastery Over Sessions</h3>
            {progressData.length > 1 ? (
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={progressData}>
                  <defs>
                    <linearGradient id="mGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="var(--teal)"   stopOpacity={0.3} />
                      <stop offset="95%" stopColor="var(--teal)"   stopOpacity={0}   />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="session" tick={{ fill:'var(--text3)', fontSize:11 }} />
                  <YAxis domain={[0,100]} tick={{ fill:'var(--text3)', fontSize:11 }} />
                  <Tooltip contentStyle={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:8, color:'var(--text)', fontSize:12 }} />
                  <Area type="monotone" dataKey="mastery" stroke="var(--teal)" fill="url(#mGrad)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height:250, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text3)', fontSize:'0.875rem' }}>
                Complete sessions to see mastery trend
              </div>
            )}
          </div>

          <div className="card">
            <h3 style={{ fontFamily:'var(--font-display)', fontWeight:700, marginBottom:'1rem' }}>IRT Ability Trajectory</h3>
            {abilityData.length > 1 ? (
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={abilityData}>
                  <defs>
                    <linearGradient id="aGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="var(--accent)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="var(--accent)" stopOpacity={0}   />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="session" tick={{ fill:'var(--text3)', fontSize:11 }} />
                  <YAxis domain={[0,100]} tick={{ fill:'var(--text3)', fontSize:11 }} />
                  <Tooltip contentStyle={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:8, color:'var(--text)', fontSize:12 }} />
                  <Area type="monotone" dataKey="ability" stroke="var(--accent)" fill="url(#aGrad)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height:250, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text3)', fontSize:'0.875rem' }}>
                Complete assessments to see ability trajectory
              </div>
            )}
          </div>

          <div className="card">
            <h3 style={{ fontFamily:'var(--font-display)', fontWeight:700, marginBottom:'1rem' }}>Learning Gain Per Session</h3>
            {progressData.length > 1 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={progressData}>
                  <XAxis dataKey="session" tick={{ fill:'var(--text3)', fontSize:11 }} />
                  <YAxis tick={{ fill:'var(--text3)', fontSize:11 }} />
                  <Tooltip contentStyle={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:8, color:'var(--text)', fontSize:12 }} />
                  <Bar dataKey="gain" radius={[4,4,0,0]}>
                    {progressData.map((d, i) => <Cell key={i} fill={d.gain > 0 ? 'var(--green)' : 'var(--coral)'} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height:220, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text3)', fontSize:'0.875rem' }}>
                No session data yet
              </div>
            )}
          </div>

          <div className="card">
            <h3 style={{ fontFamily:'var(--font-display)', fontWeight:700, marginBottom:'1rem' }}>Session Duration (minutes)</h3>
            {progressData.length > 1 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={progressData}>
                  <XAxis dataKey="session" tick={{ fill:'var(--text3)', fontSize:11 }} />
                  <YAxis tick={{ fill:'var(--text3)', fontSize:11 }} />
                  <Tooltip contentStyle={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:8, color:'var(--text)', fontSize:12 }} />
                  <Bar dataKey="duration" fill="var(--accent)" radius={[4,4,0,0]} fillOpacity={0.8} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height:220, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text3)', fontSize:'0.875rem' }}>
                No session data yet
              </div>
            )}
          </div>
        </div>
      )}

      {/* Prediction Tab */}
      {tab === 'prediction' && predict && (
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1.5rem' }}>
          <div className="card" style={{ borderColor: predict.risk_level==='high'?'rgba(255,107,107,0.3)':predict.risk_level==='medium'?'rgba(245,158,11,0.3)':'rgba(34,197,94,0.3)' }}>
            <h3 style={{ fontFamily:'var(--font-display)', fontWeight:700, marginBottom:'1.5rem' }}>Performance Prediction</h3>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1rem', marginBottom:'1.5rem' }}>
              {[
                { label:'Predicted Final Score', value: Math.round(predict.predicted_final_score*100)+'%', color:'var(--teal)',  sub:'Ensemble XGBoost+LSTM' },
                { label:'Dropout Risk',          value: Math.round(predict.dropout_risk*100)+'%',          color: riskColor,    sub: predict.risk_level+' risk level' },
                { label:'XGBoost Prediction',    value: Math.round(predict.xgb_prediction*100)+'%',        color:'var(--accent)',sub:'Gradient boosting'    },
                { label:'LSTM Prediction',       value: Math.round(predict.lstm_prediction*100)+'%',       color:'var(--amber)', sub:'Temporal trajectory'  },
              ].map(({ label, value, color, sub }) => (
                <div key={label} style={{ background:'var(--bg3)', borderRadius:10, padding:'1rem', border:'1px solid var(--border)' }}>
                  <div style={{ fontSize:'1.5rem', fontWeight:700, fontFamily:'var(--font-display)', color }}>{value}</div>
                  <div style={{ fontSize:'0.78rem', fontWeight:600, marginTop:'0.25rem' }}>{label}</div>
                  <div style={{ fontSize:'0.7rem', color:'var(--text3)' }}>{sub}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h3 style={{ fontFamily:'var(--font-display)', fontWeight:700, marginBottom:'1rem' }}>XAI — Risk Analysis</h3>
            {predict.risk_factors?.length > 0 ? (
              <>
                <p style={{ fontSize:'0.8rem', color:'var(--text3)', marginBottom:'1rem', fontWeight:600, letterSpacing:'0.04em' }}>TOP RISK FACTORS</p>
                {predict.risk_factors.map((f, i) => (
                  <div key={i} style={{ display:'flex', alignItems:'center', gap:'0.75rem', marginBottom:'0.75rem' }}>
                    <div style={{ width:10,height:10,borderRadius:'50%',flexShrink:0,background:f.severity==='high'?'var(--coral)':f.severity==='medium'?'var(--amber)':'var(--text3)' }} />
                    <div style={{ flex:1 }}>
                      <div style={{ fontSize:'0.82rem', fontWeight:600 }}>{f.factor}</div>
                    </div>
                    <span className={`badge badge-${f.severity==='high'?'red':f.severity==='medium'?'amber':'blue'}`} style={{ fontSize:'0.7rem' }}>
                      {f.severity}
                    </span>
                  </div>
                ))}
                <div style={{ marginTop:'1.25rem', paddingTop:'1rem', borderTop:'1px solid var(--border)' }}>
                  <p style={{ fontSize:'0.8rem', color:'var(--text3)', marginBottom:'0.75rem', fontWeight:600, letterSpacing:'0.04em' }}>RECOMMENDATIONS</p>
                  {(predict.recommendations||[]).map((r, i) => (
                    <div key={i} style={{ fontSize:'0.8rem', color:'var(--text2)', marginBottom:'0.5rem', display:'flex', gap:'0.5rem' }}>
                      <span style={{ color:'var(--teal)', flexShrink:0 }}>→</span> {r}
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div style={{ display:'flex', alignItems:'center', gap:'0.75rem', padding:'1rem', background:'rgba(34,197,94,0.08)', borderRadius:10, border:'1px solid rgba(34,197,94,0.2)' }}>
                <CheckCircle size={24} color="var(--green)" />
                <div>
                  <div style={{ fontWeight:600, color:'var(--green)' }}>No significant risk factors</div>
                  <div style={{ fontSize:'0.8rem', color:'var(--text2)', marginTop:'0.2rem' }}>Keep up your current learning pace!</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'prediction' && !predict && (
        <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:200, color:'var(--text3)' }}>
          No prediction data available — complete some sessions first
        </div>
      )}
    </div>
  )
}
