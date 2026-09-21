const SEV = {
  HIGH:   { bg: 'var(--red-bg)',   color: 'var(--red)',   border: 'var(--red-border)' },
  MEDIUM: { bg: 'var(--amber-bg)', color: 'var(--amber)', border: 'rgba(245,158,11,0.3)' },
  LOW:    { bg: 'var(--brand-bg)', color: 'var(--brand-muted)', border: 'var(--brand-border)' },
}

export default function SecurityReport({ findings }) {
  if (!findings || findings.length === 0) {
    return (
      <div style={{
        background: 'var(--green-bg)',
        border: '1px solid var(--green-border)',
        borderRadius: 10, padding: '14px 16px',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{ color: 'var(--green)', fontSize: 16 }}>✓</span>
        <span style={{ color: 'var(--green)', fontSize: 13 }}>No security issues found</span>
      </div>
    )
  }

  const high = findings.filter(f => f.severity === 'HIGH').length
  const med  = findings.filter(f => f.severity === 'MEDIUM').length

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 10, overflow: 'hidden',
    }}>
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{ color: 'var(--red)', fontSize: 14 }}>⚠</span>
        <span style={{ color: 'var(--text-secondary)', fontSize: 12, fontWeight: 600 }}>
          SECURITY FINDINGS
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          {high > 0 && (
            <span style={{
              ...SEV.HIGH, padding: '2px 8px', borderRadius: 4,
              fontSize: 11, fontWeight: 700, border: `1px solid ${SEV.HIGH.border}`,
            }}>{high} HIGH</span>
          )}
          {med > 0 && (
            <span style={{
              ...SEV.MEDIUM, padding: '2px 8px', borderRadius: 4,
              fontSize: 11, fontWeight: 700, border: `1px solid ${SEV.MEDIUM.border}`,
            }}>{med} MED</span>
          )}
        </div>
      </div>

      {findings.map((f, i) => {
        const sev = SEV[f.severity] || SEV.LOW
        return (
          <div key={i} style={{
            padding: '12px 16px',
            borderBottom: i < findings.length - 1 ? '1px solid var(--border)' : 'none',
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <span style={{
                ...sev, padding: '2px 8px', borderRadius: 4, fontSize: 10,
                fontWeight: 700, flexShrink: 0, marginTop: 1,
                border: `1px solid ${sev.border}`,
              }}>{f.severity}</span>
              <div>
                <div style={{ color: 'var(--text-primary)', fontSize: 13, fontWeight: 500 }}>
                  {f.message || f.issue}
                </div>
                {(f.file_path || f.line) && (
                  <div style={{ color: 'var(--text-faint)', fontSize: 11, marginTop: 3 }}>
                    {f.file_path}{f.line ? `:${f.line}` : ''}
                    {f.test_id && <span style={{ marginLeft: 6, color: 'var(--text-faintest)' }}>[{f.test_id}]</span>}
                  </div>
                )}
                {f.fix_suggestion && (
                  <div style={{ color: 'var(--brand)', fontSize: 11, marginTop: 3 }}>
                    Suggestion: {f.fix_suggestion}
                  </div>
                )}
              </div>
            </div>
          </div>
        )
      })}

      {high > 0 && (
        <div style={{
          padding: '10px 16px',
          background: 'var(--red-bg)',
          borderTop: '1px solid var(--red-border)',
          color: 'var(--red)', fontSize: 11,
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <span>⚠</span>
          HIGH severity issues block PR merge. Fix manually before committing.
        </div>
      )}
    </div>
  )
}