import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../utils/api'
import toast from 'react-hot-toast'
import AgentTrace from '../components/AgentTrace'
import DiffViewer from '../components/DiffViewer'
import QualityMetrics from '../components/QualityMetrics'
import SecurityReport from '../components/SecurityReport'
import LanguageChart from '../components/LanguageChart'

export default function AnalysisPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [analysis, setAnalysis] = useState(null)
  const [changes, setChanges] = useState([])
  const [loading, setLoading] = useState(true)
  const [committing, setCommitting] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [tab, setTab] = useState('changes')

  const load = useCallback(async () => {
    try {
      const res = await api.get(`/analysis/${id}`)
      setAnalysis(res.data)
      setChanges(res.data.changes || [])
    } catch {
      toast.error('Failed to load analysis')
    } finally {
      setLoading(false)
    }
  }, [id])

  // FIX: single polling effect — only poll while running, stop when complete/failed
  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!analysis) return
    if (analysis.status !== 'running' && analysis.status !== 'pending') return
    const t = setInterval(load, 2500)
    return () => clearInterval(t)
  }, [analysis?.status, load])

  const handleAccept = async (changeId) => {
    try {
      await api.post(`/changes/${changeId}/approve`)
      setChanges(prev => prev.map(c => c.id === changeId ? { ...c, status: 'accepted' } : c))
      toast.success('Change accepted')
    } catch {
      toast.error('Failed to accept change')
    }
  }

  const handleSkip = async (changeId) => {
    try {
      await api.post(`/changes/${changeId}/skip`)
      setChanges(prev => prev.map(c => c.id === changeId ? { ...c, status: 'skipped' } : c))
      toast('Change skipped', { icon: '·' })
    } catch {
      toast.error('Failed to skip change')
    }
  }

  const acceptAllLow = async () => {
    const low = changes.filter(c => c.risk_level === 'LOW' && c.status === 'pending')
    if (!low.length) return
    await Promise.all(low.map(c => api.post(`/changes/${c.id}/approve`)))
    setChanges(prev => prev.map(c =>
      c.risk_level === 'LOW' && c.status === 'pending' ? { ...c, status: 'accepted' } : c
    ))
    toast.success(`${low.length} LOW risk changes accepted`)
  }

  const handleCommit = async () => {
    setCommitting(true)
    try {
      const accepted = changes.filter(c => c.status === 'accepted').map(c => c.id)
      if (!accepted.length) return toast.error('Accept at least one change first')
      await api.post(`/analysis/${id}/commit`, { change_ids: accepted })
      toast.success('Changes committed to GitHub!')
      load()
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Commit failed')
    } finally {
      setCommitting(false)
    }
  }

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const res = await api.get(`/analysis/${id}/download`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `nexus-modernized-${id.slice(0, 8)}.txt`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Download failed — make sure you have accepted changes')
    } finally {
      setDownloading(false)
    }
  }

  const handleReportDownload = async () => {
    try {
      const res = await api.get(`/analysis/${id}/report`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `nexus-report-${id.slice(0, 8)}.md`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Report download failed')
    }
  }

  if (loading) return (
    <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ color: '#475569', fontSize: 14 }}>Loading analysis...</div>
    </div>
  )

  if (!analysis) return (
    <div style={{ padding: 32, color: '#ef4444' }}>Analysis not found</div>
  )

  const pendingCount = changes.filter(c => c.status === 'pending').length
  const acceptedCount = changes.filter(c => c.status === 'accepted').length
  const lowPendingCount = changes.filter(c => c.risk_level === 'LOW' && c.status === 'pending').length
  const hasGitHub = !!analysis.github_repo
  const secFindings = analysis.full_report?.report?.security_section
    ? (analysis.full_report?.security_findings || [])
    : []

  // Build test detail for display
  const testResult = analysis.full_report?.files?.[0]?.test_result || null

  const tabs = [
    { key: 'changes', label: `Changes (${changes.length})` },
    { key: 'security', label: `Security (${analysis.security_issues || 0})` },
    { key: 'tests', label: `Tests${analysis.tests_passed != null ? (analysis.tests_passed ? ' ✓' : ' ✗') : ''}` },
    { key: 'report', label: 'Report' },
    analysis.language_breakdown && { key: 'languages', label: 'Languages' },
  ].filter(Boolean)

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1080, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
        <button
          onClick={() => navigate('/dashboard')}
          style={{ color: '#475569', background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, padding: 0 }}
        >← Back</button>
        <div style={{ flex: 1 }}>
          <h1 style={{ color: '#e2e8f0', fontSize: 18, fontWeight: 700, margin: 0 }}>
            {analysis.source_name}
          </h1>
          <div style={{ color: '#475569', fontSize: 12, marginTop: 4, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {analysis.language && <span>{analysis.language}{analysis.era ? ` · ${analysis.era}` : ''}</span>}
            <span>{analysis.total_issues} issues</span>
            <span>{changes.length} proposed changes</span>
            {analysis.total_files > 1 && <span>{analysis.total_files} files</span>}
          </div>
        </div>

        <div style={{
          padding: '5px 12px', borderRadius: 7, fontSize: 12, fontWeight: 700,
          background: analysis.status === 'complete'
            ? 'rgba(16,185,129,0.1)' : analysis.status === 'running'
            ? 'rgba(99,102,241,0.1)' : 'rgba(239,68,68,0.1)',
          color: analysis.status === 'complete'
            ? '#10b981' : analysis.status === 'running'
            ? '#818cf8' : '#ef4444',
          border: `1px solid ${analysis.status === 'complete'
            ? 'rgba(16,185,129,0.2)' : analysis.status === 'running'
            ? 'rgba(99,102,241,0.2)' : 'rgba(239,68,68,0.2)'}`,
        }}>
          {analysis.status === 'running' && '⟳ '}{analysis.status.toUpperCase()}
        </div>
      </div>

      {/* Live agent trace */}
      {(analysis.status === 'running' || analysis.status === 'pending') && (
        <div style={{ marginBottom: 20 }}>
          <AgentTrace analysisId={id} />
        </div>
      )}

      {/* Metrics */}
      {analysis.status === 'complete' && (
        <div style={{ marginBottom: 20 }}>
          <QualityMetrics analysis={analysis} />
        </div>
      )}

      {/* Action bar */}
      {analysis.status === 'complete' && changes.length > 0 && (
        <div style={{
          background: '#0a0f1e', border: '1px solid #1e293b', borderRadius: 10,
          padding: '12px 16px', marginBottom: 20,
          display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
        }}>
          <span style={{ color: '#64748b', fontSize: 12 }}>
            {acceptedCount} accepted · {pendingCount} pending
          </span>

          {lowPendingCount > 0 && (
            <button onClick={acceptAllLow} style={{
              padding: '6px 14px', borderRadius: 7, border: '1px solid rgba(16,185,129,0.3)',
              background: 'rgba(16,185,129,0.08)', color: '#10b981',
              fontSize: 12, cursor: 'pointer', fontWeight: 500,
            }}>
              Accept all LOW ({lowPendingCount})
            </button>
          )}

          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <button
              onClick={handleReportDownload}
              style={{
                padding: '8px 14px', borderRadius: 8, border: '1px solid #334155',
                background: 'transparent', color: '#94a3b8',
                fontSize: 13, cursor: 'pointer',
              }}
            >📄 Report</button>

            {hasGitHub ? (
              <button
                onClick={handleCommit}
                disabled={committing || acceptedCount === 0}
                style={{
                  padding: '8px 18px', borderRadius: 8, border: 'none',
                  background: acceptedCount > 0 ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : '#1e293b',
                  color: acceptedCount > 0 ? '#fff' : '#475569',
                  fontSize: 13, fontWeight: 600, cursor: acceptedCount > 0 ? 'pointer' : 'default',
                }}
              >
                {committing ? 'Committing...' : `Commit${acceptedCount > 0 ? ` (${acceptedCount})` : ''}`}
              </button>
            ) : (
              <button
                onClick={handleDownload}
                disabled={downloading || acceptedCount === 0}
                style={{
                  padding: '8px 18px', borderRadius: 8, border: '1px solid #6366f1',
                  background: acceptedCount > 0 ? 'rgba(99,102,241,0.12)' : 'transparent',
                  color: acceptedCount > 0 ? '#818cf8' : '#475569',
                  fontSize: 13, fontWeight: 600, cursor: acceptedCount > 0 ? 'pointer' : 'default',
                }}
              >
                {downloading ? 'Downloading...' : `↓ Download${acceptedCount > 0 ? ` (${acceptedCount})` : ''}`}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div style={{
        display: 'flex', gap: 2, marginBottom: 16, background: '#0a0f1e',
        borderRadius: 8, padding: 3, border: '1px solid #1e293b', width: 'fit-content',
      }}>
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} style={{
            padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12,
            background: tab === t.key ? '#1e293b' : 'transparent',
            color: tab === t.key ? '#e2e8f0' : '#475569',
          }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'changes' && (
        <div>
          {changes.length === 0 ? (
            <div style={{ color: '#475569', fontSize: 14, padding: '20px 0' }}>
              {analysis.status === 'running' ? 'Waiting for modernizer...' : 'No changes proposed.'}
            </div>
          ) : (
            changes.map((c, i) => (
              <DiffViewer key={c.id} change={c} index={i} onAccept={handleAccept} onSkip={handleSkip} />
            ))
          )}
        </div>
      )}

      {tab === 'security' && <SecurityReport findings={secFindings} />}

      {/* FIX: Tests tab — show what tests ran and whether they passed */}
      {tab === 'tests' && (
        <div style={{ background: '#0a0f1e', border: '1px solid #1e293b', borderRadius: 10, padding: 20 }}>
          <div style={{ color: '#94a3b8', fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', marginBottom: 16 }}>
            TEST RESULTS
          </div>
          {analysis.tests_passed == null ? (
            <div style={{ color: '#475569', fontSize: 13 }}>No test data available.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* Overall result */}
              <div style={{
                padding: '12px 16px', borderRadius: 8,
                background: analysis.tests_passed ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
                border: `1px solid ${analysis.tests_passed ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
                display: 'flex', alignItems: 'center', gap: 10,
              }}>
                <span style={{ fontSize: 18 }}>{analysis.tests_passed ? '✅' : '❌'}</span>
                <div>
                  <div style={{
                    color: analysis.tests_passed ? '#10b981' : '#ef4444',
                    fontWeight: 600, fontSize: 14,
                  }}>
                    {analysis.tests_passed ? 'All tests passed after modernization' : 'Regression detected — changes were blocked'}
                  </div>
                  <div style={{ color: '#475569', fontSize: 12, marginTop: 2 }}>
                    {analysis.test_count != null ? `${analysis.test_count} tests passed` : 'No test count available'}
                  </div>
                </div>
              </div>

              {/* Explanation for users */}
              <div style={{
                padding: '12px 16px', borderRadius: 8, background: '#0f172a',
                border: '1px solid #1e293b',
              }}>
                <div style={{ color: '#64748b', fontSize: 11, fontWeight: 600, marginBottom: 6 }}>
                  HOW TEST SAFETY WORKS
                </div>
                <div style={{ color: '#94a3b8', fontSize: 12, lineHeight: 1.7 }}>
                  NEXUS runs your existing test suite on both the <strong style={{ color: '#e2e8f0' }}>original</strong> and <strong style={{ color: '#e2e8f0' }}>modernized</strong> code.
                  If the modernized version causes more test failures than the original, all changes are automatically blocked — nothing is committed.
                  {analysis.tests_passed === false && (
                    <span style={{ color: '#ef4444', display: 'block', marginTop: 8, fontWeight: 500 }}>
                      ⚠ A regression was detected. The proposed changes were not saved. Fix the failing tests and re-analyse.
                    </span>
                  )}
                  {analysis.tests_passed === true && (
                    <span style={{ color: '#10b981', display: 'block', marginTop: 8 }}>
                      ✓ Modernized code produces no more failures than the original.
                    </span>
                  )}
                </div>
              </div>

              {/* Framework info if available */}
              {testResult?.framework_detected && (
                <div style={{ color: '#475569', fontSize: 12 }}>
                  Framework detected: <span style={{ color: '#818cf8' }}>{testResult.framework_detected}</span>
                  {testResult.auto_generated_tests && (
                    <span style={{ marginLeft: 8, color: '#f59e0b' }}>
                      · No tests found — characterization tests were auto-generated. Review before committing.
                    </span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {tab === 'report' && (
        <div style={{ background: '#0a0f1e', border: '1px solid #1e293b', borderRadius: 10, padding: 20 }}>
          {analysis.report_markdown ? (
            <pre style={{ color: '#94a3b8', fontSize: 12, whiteSpace: 'pre-wrap', lineHeight: 1.7, margin: 0 }}>
              {analysis.report_markdown}
            </pre>
          ) : (
            <div style={{ color: '#475569', fontSize: 13 }}>
              {analysis.status === 'running' ? 'Report will be generated when analysis completes...' : 'No report available.'}
            </div>
          )}
        </div>
      )}

      {tab === 'languages' && (
        <LanguageChart data={analysis.language_breakdown} />
      )}
    </div>
  )
}