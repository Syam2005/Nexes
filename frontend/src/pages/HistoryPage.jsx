import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../utils/api'
import toast from 'react-hot-toast'

const RISK_COLORS = {
  LOW:    { color: '#10b981', bg: 'rgba(16,185,129,0.1)' },
  MEDIUM: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)' },
  HIGH:   { color: '#ef4444', bg: 'rgba(239,68,68,0.1)' },
}

export default function HistoryPage() {
  const navigate = useNavigate()
  const [analyses, setAnalyses] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterLang, setFilterLang] = useState('')
  const [filterRisk, setFilterRisk] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [search, setSearch] = useState('')

  useEffect(() => {
    api.get('/history?limit=50')
      .then(r => setAnalyses(Array.isArray(r.data) ? r.data : (r.data?.analyses || [])))
      .catch(() => toast.error('Failed to load history'))
      .finally(() => setLoading(false))
  }, [])

  const languages = [...new Set(analyses.map(a => a.language).filter(Boolean))]

  const filtered = analyses.filter(a => {
    if (filterLang && a.language !== filterLang) return false
    if (filterRisk && a.overall_risk !== filterRisk) return false
    if (filterStatus && a.status !== filterStatus) return false
    if (search && !a.source_name?.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const downloadReport = async (e, analysisId) => {
    e.stopPropagation()
    try {
      const res = await api.get(`/analysis/${analysisId}/report`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `nexus-report-${analysisId.slice(0, 8)}.md`
      anchor.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Report download failed')
    }
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 960, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ color: '#e2e8f0', fontSize: 22, fontWeight: 700, margin: 0 }}>History</h1>
        <p style={{ color: '#475569', fontSize: 13, margin: '6px 0 0' }}>All past analyses. Click any to re-open.</p>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by name..."
          style={{
            padding: '8px 12px', borderRadius: 8, background: '#0a0f1e',
            border: '1px solid #1e293b', color: '#e2e8f0', fontSize: 12,
            outline: 'none', flex: 1, minWidth: 160,
          }}
        />
        {languages.length > 0 && (
          <select value={filterLang} onChange={e => setFilterLang(e.target.value)} style={{
            padding: '8px 10px', borderRadius: 8, background: '#0a0f1e',
            border: '1px solid #1e293b', color: filterLang ? '#e2e8f0' : '#475569',
            fontSize: 12, outline: 'none',
          }}>
            <option value="">All languages</option>
            {languages.map(l => <option key={l} value={l}>{l}</option>)}
          </select>
        )}
        <select value={filterRisk} onChange={e => setFilterRisk(e.target.value)} style={{
          padding: '8px 10px', borderRadius: 8, background: '#0a0f1e',
          border: '1px solid #1e293b', color: filterRisk ? '#e2e8f0' : '#475569',
          fontSize: 12, outline: 'none',
        }}>
          <option value="">All risk</option>
          <option value="LOW">LOW</option>
          <option value="MEDIUM">MEDIUM</option>
          <option value="HIGH">HIGH</option>
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} style={{
          padding: '8px 10px', borderRadius: 8, background: '#0a0f1e',
          border: '1px solid #1e293b', color: filterStatus ? '#e2e8f0' : '#475569',
          fontSize: 12, outline: 'none',
        }}>
          <option value="">All status</option>
          <option value="complete">Complete</option>
          <option value="running">Running</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      <div style={{ color: '#334155', fontSize: 11, marginBottom: 10 }}>
        {filtered.length} of {analyses.length} analyses
      </div>

      {loading ? (
        <div style={{ color: '#475569', fontSize: 13, padding: '20px 0' }}>Loading...</div>
      ) : filtered.length === 0 ? (
        <div style={{
          background: '#0a0f1e', border: '1px solid #1e293b', borderRadius: 10,
          padding: '40px 20px', textAlign: 'center', color: '#475569', fontSize: 14,
        }}>
          No analyses found. Start one from the Dashboard.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {filtered.map(a => {
            const risk = RISK_COLORS[a.overall_risk]
            return (
              <div
                key={a.id}
                onClick={() => navigate(`/analysis/${a.id}`)}
                style={{
                  background: '#0a0f1e', border: '1px solid #1e293b', borderRadius: 10,
                  padding: '14px 16px', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
                  transition: 'border-color 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = '#334155'}
                onMouseLeave={e => e.currentTarget.style.borderColor = '#1e293b'}
              >
                <div style={{ flex: 1, minWidth: 200 }}>
                  <div style={{ color: '#e2e8f0', fontSize: 13, fontWeight: 500, marginBottom: 3 }}>
                    {a.source_name}
                  </div>
                  <div style={{ color: '#475569', fontSize: 11, display: 'flex', gap: 10 }}>
                    {a.language && <span>{a.language}{a.era ? ` (${a.era})` : ''}</span>}
                    <span>{a.total_issues || 0} issues</span>
                    {a.estimated_hours_saved != null && (
                      <span style={{ color: '#10b981' }}>~{Number(a.estimated_hours_saved).toFixed(1)}h saved</span>
                    )}
                  </div>
                </div>

                {risk && (
                  <span style={{
                    ...risk, padding: '3px 10px', borderRadius: 5,
                    fontSize: 10, fontWeight: 700,
                  }}>{a.overall_risk}</span>
                )}

                <span style={{
                  padding: '3px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600,
                  background: a.status === 'complete'
                    ? 'rgba(16,185,129,0.1)' : a.status === 'running'
                    ? 'rgba(99,102,241,0.1)' : 'rgba(71,85,105,0.1)',
                  color: a.status === 'complete' ? '#10b981' : a.status === 'running' ? '#818cf8' : '#64748b',
                }}>{a.status}</span>

                {/* FIX: single date span (was duplicated) */}
                <span style={{ color: '#334155', fontSize: 11 }}>
                  {new Date(a.created_at).toLocaleDateString('en', {
                    month: 'short', day: 'numeric', year: 'numeric',
                  })}
                </span>

                <button
                  onClick={(e) => downloadReport(e, a.id)}
                  style={{
                    padding: '4px 10px', borderRadius: 5,
                    border: '1px solid #334155',
                    background: 'transparent', color: '#64748b',
                    fontSize: 11, cursor: 'pointer', flexShrink: 0,
                  }}
                >📄 Report</button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}