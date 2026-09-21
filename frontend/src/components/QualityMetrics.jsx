export default function QualityMetrics({ analysis }) {
  if (!analysis) return null

  const {
    complexity_before, complexity_after,
    estimated_hours_saved, confidence_score,
    minimality_score, tests_passed, test_count,
    total_issues, security_issues,
  } = analysis

  const cards = [
    complexity_before != null && {
      label: 'Complexity',
      before: typeof complexity_before === 'number' ? complexity_before.toFixed(1) : complexity_before,
      after: complexity_after != null
        ? (typeof complexity_after === 'number' ? complexity_after.toFixed(1) : complexity_after)
        : null,
      improved: complexity_after != null && complexity_after < complexity_before,
    },
    estimated_hours_saved != null && {
      label: 'Time Saved',
      value: `~${typeof estimated_hours_saved === 'number' ? estimated_hours_saved.toFixed(1) : estimated_hours_saved}h`,
      sub: 'manual effort avoided',
      color: 'var(--green)',
    },
    confidence_score != null && {
      label: 'Confidence',
      // confidence_score is already 0-100 — do NOT multiply by 100
      value: `${Math.round(Number(confidence_score))}%`,
      sub: 'modernization accuracy',
      color: 'var(--brand)',
    },
    minimality_score != null && {
      label: 'Minimality',
      // minimality_score is already 0-100 — do NOT multiply by 100
      value: `${Math.round(Number(minimality_score))}%`,
      sub: 'file unchanged',
      color: '#8b5cf6',
    },
    tests_passed != null && {
      label: 'Tests',
      value: tests_passed ? 'PASS' : 'FAIL',
      sub: test_count != null ? `${test_count} passed` : 'regression check',
      color: tests_passed ? 'var(--green)' : 'var(--red)',
    },
    {
      label: 'Issues Found',
      value: total_issues || 0,
      sub: `${security_issues || 0} security`,
      color: (security_issues || 0) > 0 ? 'var(--red)' : 'var(--text-faint)',
    },
  ].filter(Boolean)

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
      gap: 10,
    }}>
      {cards.map((card, i) => (
        <div key={i} className="nx-metric-card">
          <div style={{
            color: 'var(--text-faint)', fontSize: 10,
            fontWeight: 600, letterSpacing: '0.05em', marginBottom: 6,
          }}>
            {card.label.toUpperCase()}
          </div>

          {card.before != null ? (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 18, fontWeight: 700 }}>
                  {card.before}
                </span>
                <span style={{ color: 'var(--text-faintest)', fontSize: 12 }}>→</span>
                {card.after != null ? (
                  <span style={{
                    fontSize: 18, fontWeight: 700,
                    color: card.improved ? 'var(--green)' : 'var(--red)',
                  }}>{card.after}</span>
                ) : (
                  <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>—</span>
                )}
              </div>
              {card.after != null && (
                <div style={{ color: 'var(--text-faintest)', fontSize: 10, marginTop: 2 }}>
                  {card.improved ? '↓ improved' : '— unchanged'}
                </div>
              )}
            </div>
          ) : (
            <div>
              <div style={{ color: card.color || 'var(--text-primary)', fontSize: 22, fontWeight: 700 }}>
                {card.value}
              </div>
              {card.sub && (
                <div style={{ color: 'var(--text-faint)', fontSize: 10, marginTop: 2 }}>
                  {card.sub}
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}