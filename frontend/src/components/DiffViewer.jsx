import ReactDiffViewer from 'react-diff-viewer-continued'

const RISK = {
  LOW:    { bg: 'rgba(16,185,129,0.12)',  color: 'var(--green)', border: 'var(--green-border)' },
  MEDIUM: { bg: 'rgba(245,158,11,0.12)', color: 'var(--amber)', border: 'rgba(245,158,11,0.3)' },
  HIGH:   { bg: 'rgba(239,68,68,0.12)',  color: 'var(--red)',   border: 'var(--red-border)' },
}

export default function DiffViewer({ change, index, onAccept, onSkip }) {
  const risk = RISK[change.risk_level] || RISK.MEDIUM
  const isSkipped  = change.status === 'skipped'
  const isAccepted = change.status === 'accepted'
  const isFailed   = change.status === 'validation_failed'

  // Detect dark mode from data-theme
  const isDark = document.documentElement.getAttribute('data-theme') !== 'light'

  return (
    <div style={{
      border: `1px solid ${risk.border}`,
      borderRadius: 10,
      overflow: 'hidden',
      marginBottom: 20,
      opacity: isSkipped ? 0.5 : 1,
      transition: 'opacity 0.2s',
      background: 'var(--bg-surface)',
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px',
        background: 'var(--bg-surface)',
        display: 'flex', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
          <span style={{ color: 'var(--text-faint)', fontSize: 11 }}>#{index + 1}</span>
          <span style={{ color: 'var(--text-primary)', fontSize: 13, fontWeight: 600 }}>
            {change.file_path}
          </span>
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
            L{change.line_start}–{change.line_end}
          </span>
        </div>

        <div style={{
          padding: '3px 10px', borderRadius: 6,
          background: risk.bg, color: risk.color,
          fontSize: 11, fontWeight: 700,
          border: `1px solid ${risk.border}`,
          letterSpacing: '0.05em',
        }}>
          {change.risk_level}
        </div>

        {isFailed && (
          <div style={{
            padding: '3px 10px', borderRadius: 6,
            background: 'var(--red-bg)', color: 'var(--red)',
            fontSize: 11, fontWeight: 700,
            border: '1px solid var(--red-border)',
          }}>
            AUTO-FIX FAILED
          </div>
        )}
      </div>

      {/* Description */}
      <div style={{
        padding: '8px 16px',
        background: 'var(--bg-elevated)',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
          <strong style={{ color: 'var(--text-muted)' }}>Issue:</strong> {change.description}
        </div>
        {change.risk_reason && (
          <div style={{ color: 'var(--text-faint)', fontSize: 11, marginTop: 4 }}>
            <strong>Risk:</strong> {change.risk_reason}
          </div>
        )}
        {change.confidence != null && (
          <div style={{ color: 'var(--text-faintest)', fontSize: 11, marginTop: 2 }}>
            Confidence: {Math.round(change.confidence * 100)}%
          </div>
        )}
        {isFailed && (
          <div style={{ color: 'var(--amber)', fontSize: 11, marginTop: 4 }}>
            ⚠ The LLM could not produce a verbatim match for this fix. Review manually.
          </div>
        )}
      </div>

      {/* Diff — only show when there's actual code to diff */}
      {change.old_code || change.new_code ? (
        <div style={{ fontSize: 12 }}>
          <ReactDiffViewer
            oldValue={change.old_code || ''}
            newValue={change.new_code || ''}
            splitView={false}
            useDarkTheme={isDark}
            hideLineNumbers={false}
            showDiffOnly={false}
            styles={{
              variables: {
                dark: {
                  diffViewerBackground: '#0d1526',
                  diffViewerColor: '#e2e8f0',
                  addedBackground: 'rgba(16,185,129,0.08)',
                  addedColor: '#e2e8f0',
                  removedBackground: 'rgba(239,68,68,0.08)',
                  removedColor: '#e2e8f0',
                  wordAddedBackground: 'rgba(16,185,129,0.25)',
                  wordRemovedBackground: 'rgba(239,68,68,0.25)',
                  gutterBackground: '#0a0f1e',
                  gutterColor: '#334155',
                },
                light: {
                  diffViewerBackground: '#f8fafc',
                  diffViewerColor: '#1e293b',
                  addedBackground: 'rgba(5,150,105,0.08)',
                  addedColor: '#1e293b',
                  removedBackground: 'rgba(220,38,38,0.08)',
                  removedColor: '#1e293b',
                  wordAddedBackground: 'rgba(5,150,105,0.2)',
                  wordRemovedBackground: 'rgba(220,38,38,0.2)',
                  gutterBackground: '#f1f5f9',
                  gutterColor: '#94a3b8',
                },
              },
            }}
          />
        </div>
      ) : (
        <div style={{ padding: '12px 16px', color: 'var(--text-faint)', fontSize: 12 }}>
          No diff available — manual fix required.
        </div>
      )}

      {/* Actions */}
      {!isSkipped && !isAccepted && !isFailed && onAccept && onSkip && (
        <div style={{
          padding: '10px 16px',
          background: 'var(--bg-surface)',
          borderTop: '1px solid var(--border)',
          display: 'flex', gap: 8,
        }}>
          <button onClick={() => onAccept(change.id)} style={{
            padding: '6px 16px', borderRadius: 6,
            border: '1px solid var(--green)', background: 'var(--green-bg)',
            color: 'var(--green)', fontSize: 12, fontWeight: 600, cursor: 'pointer',
          }}>✓ Accept</button>
          <button onClick={() => onSkip(change.id)} style={{
            padding: '6px 16px', borderRadius: 6,
            border: '1px solid var(--border)', background: 'transparent',
            color: 'var(--text-faint)', fontSize: 12, cursor: 'pointer',
          }}>✕ Skip</button>
        </div>
      )}

      {(isAccepted || isSkipped) && (
        <div style={{
          padding: '8px 16px',
          background: 'var(--bg-surface)',
          borderTop: '1px solid var(--border)',
          color: isAccepted ? 'var(--green)' : 'var(--text-faint)',
          fontSize: 12, fontWeight: 600,
        }}>
          {isAccepted ? '✓ Accepted' : '✕ Skipped'}
        </div>
      )}
    </div>
  )
}