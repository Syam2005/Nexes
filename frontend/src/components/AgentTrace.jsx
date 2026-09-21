import { useEffect, useRef, useState } from 'react'

// FIX: keys must match exactly what backend broadcasts in LayerTrace
// backend uses: language_detector, ast_parser, security_scanner, reader_agent,
// modernizer_agent, diff_engine, chunk_validator, test_runner,
// risk_scorer, evaluation_engine, documenter_agent
const LAYER_LABELS = {
  language_detector:  { label: 'Language Detection',  color: '#6366f1' },
  ast_parser:         { label: 'AST Parsing',          color: '#8b5cf6' },
  security_scanner:   { label: 'Security Scan',        color: '#ef4444' },
  reader_agent:       { label: 'Reader Agent',          color: '#f59e0b' },
  modernizer_agent:   { label: 'Modernizer Agent',     color: '#f59e0b' },
  diff_engine:        { label: 'Diff Engine',           color: '#3b82f6' },
  chunk_validator:    { label: 'Chunk Validator',       color: '#3b82f6' },
  test_runner:        { label: 'Test Runner',           color: '#10b981' },
  risk_scorer:        { label: 'Risk Scorer',           color: '#f59e0b' },
  evaluation_engine:  { label: 'Evaluation Engine',    color: '#6366f1' },
  documenter_agent:   { label: 'Documenter Agent',     color: '#8b5cf6' },
  complete:           { label: 'Complete',              color: '#10b981' },
}

export default function AgentTrace({ analysisId }) {
  const [traces, setTraces] = useState([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    if (!analysisId) return

    const base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    // Replace http(s) with ws(s)
    const wsBase = base.replace(/^http/, 'ws')
    const wsUrl = `${wsBase}/ws/${analysisId}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        setTraces(prev => [...prev, { ...msg, ts: Date.now() }])
      } catch (_) {}
    }

    return () => {
      ws.close()
    }
  }, [analysisId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [traces])

  const statusDot = connected
    ? { background: '#10b981', boxShadow: '0 0 0 3px rgba(16,185,129,0.2)' }
    : { background: '#475569' }

  const getTraceLabel = (t) => {
    // Handle file_start, pipeline_complete, validation_failed, regression_blocked events
    if (t.type === 'file_start') return `Processing ${t.file || '...'}`
    if (t.type === 'pipeline_complete') return 'Pipeline complete'
    if (t.type === 'validation_failed') return `Validation failed: ${(t.issues || []).join(', ')}`
    if (t.type === 'regression_blocked') return t.message || 'Regression blocked'
    if (t.type === 'layer_start') return `Starting...`
    if (t.type === 'layer_end') return `Done (${t.duration_ms}ms)${t.status === 'error' ? ' ❌' : ' ✓'}`
    return t.message || t.type || ''
  }

  return (
    <div style={{
      background: '#0a0f1e', border: '1px solid #1e293b', borderRadius: 12,
      overflow: 'hidden', fontFamily: 'monospace',
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid #1e293b',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <div style={{
          width: 8, height: 8, borderRadius: '50%', transition: 'all 0.3s', ...statusDot,
        }} />
        <span style={{ color: '#94a3b8', fontSize: 12, fontWeight: 600, letterSpacing: '0.05em' }}>
          AGENT TRACE
        </span>
        <span style={{ color: '#334155', fontSize: 11, marginLeft: 'auto' }}>
          {traces.length} events
        </span>
      </div>

      {/* Trace log */}
      <div style={{ height: 280, overflowY: 'auto', padding: 12 }}>
        {traces.length === 0 ? (
          <div style={{ color: '#334155', fontSize: 12, padding: '8px 0' }}>
            {connected ? 'Waiting for pipeline events...' : 'Connecting...'}
          </div>
        ) : (
          traces.map((t, i) => {
            const meta = LAYER_LABELS[t.layer] || { label: t.layer || t.type, color: '#64748b' }
            return (
              <div key={i} style={{
                display: 'flex', gap: 10, marginBottom: 6, alignItems: 'flex-start',
              }}>
                <span style={{
                  fontSize: 10, color: '#334155', flexShrink: 0, paddingTop: 2,
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {new Date(t.ts).toLocaleTimeString('en', { hour12: false })}
                </span>
                <span style={{
                  fontSize: 10, fontWeight: 700, color: meta.color,
                  flexShrink: 0, paddingTop: 2, minWidth: 170,
                }}>
                  [{meta.label}]
                </span>
                <span style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.4 }}>
                  {getTraceLabel(t)}
                </span>
              </div>
            )
          })
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}