import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { studentAPI, analyticsAPI, engagementAPI } from '../api/client.js'
import { Brain, Zap, TrendingUp, AlertTriangle, BookOpen, FlaskConical, BarChart3, Target, Clock } from 'lucide-react'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts'

export default function Home() {
  // ✅ FIXED HERE
  const user_id = localStorage.getItem('user_id')

  const [profile,   setProfile]   = useState(null)
  const [predict,   setPredict]   = useState(null)
  const [progress,  setProgress]  = useState(null)
  const [attention, setAttention] = useState(null)
  const [loading,   setLoading]   = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const [p, pred, prog, att] = await Promise.allSettled([
          studentAPI.getProfile(user_id),
          analyticsAPI.getPredict(user_id),
          analyticsAPI.getProgress(user_id),
          engagementAPI.getAttention(user_id),
        ])

        if (p.status    === 'fulfilled') setProfile(p.value.data)
        if (pred.status === 'fulfilled') setPredict(pred.value.data)
        if (prog.status === 'fulfilled') setProgress(prog.value.data)
        if (att.status  === 'fulfilled') setAttention(att.value.data)

      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }

    load()

    // Engagement tracking
    const log = (type) => engagementAPI.logEvent({ user_id: user_id, event_type: type })

    const onClick  = () => log('click')
    const onScroll = () => log('scroll')
    const onVis    = () => log(document.hidden ? 'blur' : 'focus')

    window.addEventListener('click', onClick)
    window.addEventListener('scroll', onScroll)
    document.addEventListener('visibilitychange', onVis)

    return () => {
      window.removeEventListener('click', onClick)
      window.removeEventListener('scroll', onScroll)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [user_id])

  if (loading) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'50vh' }}>
      <div className="spinner" style={{ width:36, height:36 }} />
    </div>
  )

  // (rest of your code unchanged)

  const mastery = profile?.mastery_scores || {}
  const masteryValues = Object.values(mastery)
  const avgMastery = masteryValues.length
    ? masteryValues.reduce((a, b) => a + b, 0) / masteryValues.length
    : 0

  const radarData = [
    { subject: 'Accuracy',   val: Math.round(avgMastery * 100) },
    { subject: 'Engagement', val: Math.round((profile?.engagement_score || 0.5) * 100) },
    { subject: 'Ability',    val: Math.round(((profile?.irt_ability || 0) + 3) / 6 * 100) },
    { subject: 'Cognitive',  val: Math.round((profile?.cognitive_level || 0.5) * 100) },
    { subject: 'Speed',      val: Math.round(Math.min((profile?.learning_speed || 1) / 2, 1) * 100) },
    { subject: 'Sessions',   val: Math.min(Math.round((profile?.total_sessions || 0) / 50 * 100), 100) },
  ]

  const abilityTrajectory = (progress?.ability_trajectory || []).slice(-15).map((p, i) => ({
    session: i + 1,
    ability: parseFloat(((p.ability || 0) * 33 + 50).toFixed(1)),
  }))

  const riskLevel = predict?.risk_level || 'low'
  const riskColor = riskLevel === 'high' ? 'var(--coral)' : riskLevel === 'medium' ? 'var(--amber)' : 'var(--green)'

  const statCards = [
    { icon: Brain,         color: 'var(--accent)',  label: 'IRT Ability',      value: ((profile?.irt_ability||0) >= 0 ? '+' : '') + (profile?.irt_ability||0).toFixed(2), sub: 'Latent ability (θ)' },
    { icon: Target,        color: 'var(--teal)',    label: 'Overall Mastery',  value: Math.round(avgMastery * 100) + '%',  sub: `${masteryValues.filter(v=>v>=0.8).length} topics mastered` },
    { icon: Zap,           color: 'var(--amber)',   label: 'Engagement',       value: Math.round((profile?.engagement_score||0.5)*100) + '%', sub: attention?.attention_level ? `${attention.attention_level} attention` : 'Tracking...' },
    { icon: TrendingUp,    color: 'var(--green)',   label: 'Predicted Score',  value: predict ? Math.round(predict.predicted_final_score*100)+'%' : '—', sub: 'Final exam forecast' },
    { icon: AlertTriangle, color: riskColor,        label: 'Dropout Risk',     value: predict ? Math.round(predict.dropout_risk*100)+'%' : '—', sub: riskLevel + ' risk level' },
    { icon: Clock,         color: 'var(--accent2)', label: 'Sessions',         value: profile?.total_sessions || 0, sub: 'Learning sessions' },
  ]

  return (
    <div className="fade-in">
      <div style={{ marginBottom:'2rem' }}>
        <h1 style={{ fontFamily:'var(--font-display)', fontSize:'2rem', fontWeight:800 }}>
          Your Learning Dashboard
        </h1>
        <p style={{ color:'var(--text2)', marginTop:'0.25rem' }}>
          AI-powered insights into your learning journey
        </p>
      </div>

      {/* Stat cards */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(190px,1fr))', gap:'1rem', marginBottom:'1.5rem' }}>
        {statCards.map(({ icon: Icon, color, label, value, sub }) => (
          <div key={label} className="card" style={{ padding:'1.25rem' }}>
            <div style={{ display:'flex', alignItems:'center', gap:'0.5rem', marginBottom:'0.75rem' }}>
              <div style={{ width:32, height:32, borderRadius:8, background:`${color}22`, display:'flex', alignItems:'center', justifyContent:'center' }}>
                <Icon size={16} color={color} />
              </div>
              <span style={{ fontSize:'0.8rem', color:'var(--text2)', fontWeight:500 }}>{label}</span>
            </div>
            <div style={{ fontSize:'1.6rem', fontWeight:700, fontFamily:'var(--font-display)', color }}>{value}</div>
            <div style={{ fontSize:'0.75rem', color:'var(--text3)', marginTop:'0.25rem' }}>{sub}</div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1.5rem', marginBottom:'1.5rem' }}>
        <div className="card">
          <h3 style={{ fontFamily:'var(--font-display)', fontWeight:700, marginBottom:'1rem' }}>Cognitive Profile</h3>
          <ResponsiveContainer width="100%" height={220}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis dataKey="subject" tick={{ fill:'var(--text2)', fontSize:11 }} />
              <Radar dataKey="val" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.2} strokeWidth={2} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
        <div className="card">
          <h3 style={{ fontFamily:'var(--font-display)', fontWeight:700, marginBottom:'1rem' }}>Ability Trajectory</h3>
          {abilityTrajectory.length > 1 ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={abilityTrajectory}>
                <XAxis dataKey="session" tick={{ fill:'var(--text3)', fontSize:11 }} />
                <YAxis domain={[0,100]} tick={{ fill:'var(--text3)', fontSize:11 }} />
                <Tooltip contentStyle={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:8, color:'var(--text)', fontSize:12 }} />
                <Line type="monotone" dataKey="ability" stroke="var(--teal)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height:220, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text3)', fontSize:'0.875rem', textAlign:'center' }}>
              Complete some assessments<br/>to see your ability trajectory
            </div>
          )}
        </div>
      </div>

      {/* Profile + Quick Actions */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1.5rem', marginBottom:'1.5rem' }}>
        <div className="card">
          <h3 style={{ fontFamily:'var(--font-display)', fontWeight:700, marginBottom:'1rem' }}>Learning Profile</h3>
          {[
            { label:'Learning Style',  value: profile?.learning_style || 'visual',  badge:'blue'  },
            { label:'Topics with gaps', value: profile?.knowledge_gaps?.length || 0, badge:'amber' },
            { label:'Strong topics',   value: profile?.strong_topics?.length || 0,   badge:'green' },
            { label:'Attention level', value: attention?.attention_level || 'tracking...', badge: attention?.attention_level==='high'?'green':'amber' },
          ].map(({ label, value, badge }) => (
            <div key={label} style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'0.75rem' }}>
              <span style={{ color:'var(--text2)', fontSize:'0.875rem' }}>{label}</span>
              <span className={`badge badge-${badge}`} style={{ textTransform:'capitalize' }}>{value}</span>
            </div>
          ))}
          {attention?.recommendation && (
            <div style={{ marginTop:'0.5rem', padding:'0.75rem', background:'var(--bg3)', borderRadius:8, fontSize:'0.8rem', color:'var(--text2)' }}>
              💡 {attention.recommendation}
            </div>
          )}
        </div>

        <div className="card">
          <h3 style={{ fontFamily:'var(--font-display)', fontWeight:700, marginBottom:'1rem' }}>Quick Actions</h3>
          <div style={{ display:'flex', flexDirection:'column', gap:'0.75rem' }}>
            {[
              { to:'/learn',     icon:BookOpen,     label:'Continue Learning',   sub:'AI-personalized path',       color:'var(--accent)' },
              { to:'/test',      icon:FlaskConical, label:'Take Adaptive Test',  sub:'IRT-calibrated assessment',  color:'var(--teal)'   },
              { to:'/analytics', icon:BarChart3,    label:'Full Analytics',      sub:'Heatmaps & predictions',     color:'var(--amber)'  },
            ].map(({ to, icon: Icon, label, sub, color }) => (
              <Link key={to} to={to} style={{ textDecoration:'none' }}>
                <div
                  style={{ display:'flex', alignItems:'center', gap:'1rem', padding:'0.875rem', borderRadius:10, background:'var(--bg3)', border:'1px solid var(--border)', transition:'var(--transition)', cursor:'pointer' }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor=color; e.currentTarget.style.background='var(--bg2)' }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor='var(--border)'; e.currentTarget.style.background='var(--bg3)' }}
                >
                  <div style={{ width:36, height:36, borderRadius:8, background:`${color}22`, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                    <Icon size={18} color={color} />
                  </div>
                  <div>
                    <div style={{ fontWeight:600, fontSize:'0.875rem' }}>{label}</div>
                    <div style={{ fontSize:'0.75rem', color:'var(--text2)' }}>{sub}</div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* Risk factors */}
      {predict?.risk_factors?.length > 0 && (
        <div className="card" style={{ borderColor: riskLevel==='high' ? 'rgba(255,107,107,0.3)' : 'var(--border)' }}>
          <h3 style={{ fontFamily:'var(--font-display)', fontWeight:700, marginBottom:'1rem' }}>
            <AlertTriangle size={16} style={{ marginRight:6, color:riskColor, verticalAlign:'middle' }} />
            Risk Analysis & Recommendations
          </h3>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1rem' }}>
            <div>
              <p style={{ fontSize:'0.8rem', color:'var(--text3)', marginBottom:'0.5rem', fontWeight:600, letterSpacing:'0.05em' }}>RISK FACTORS</p>
              {predict.risk_factors.map((f, i) => (
                <div key={i} style={{ display:'flex', alignItems:'center', gap:'0.5rem', marginBottom:'0.4rem' }}>
                  <div style={{ width:8, height:8, borderRadius:'50%', background: f.severity==='high'?'var(--coral)':f.severity==='medium'?'var(--amber)':'var(--text3)', flexShrink:0 }} />
                  <span style={{ fontSize:'0.8rem', color:'var(--text2)' }}>{f.factor}</span>
                </div>
              ))}
            </div>
            <div>
              <p style={{ fontSize:'0.8rem', color:'var(--text3)', marginBottom:'0.5rem', fontWeight:600, letterSpacing:'0.05em' }}>RECOMMENDATIONS</p>
              {(predict.recommendations || []).map((r, i) => (
                <div key={i} style={{ fontSize:'0.8rem', color:'var(--text2)', marginBottom:'0.4rem' }}>→ {r}</div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
