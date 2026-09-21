import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'

const COLORS = ['#6366f1', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#f97316']

export default function LanguageChart({ data }) {
  if (!data || Object.keys(data).length === 0) return null

  const chartData = Object.entries(data).map(([name, value]) => ({ name, value }))
  const isDark = document.documentElement.getAttribute('data-theme') !== 'light'
  const tooltipBg = isDark ? '#0f172a' : '#ffffff'
  const tooltipBorder = isDark ? '#1e293b' : '#e2e8f0'
  const tooltipColor = isDark ? '#e2e8f0' : '#0f172a'
  const legendColor = isDark ? '#94a3b8' : '#475569'

  return (
    <div style={{
      background: 'var(--bg-surface)',
      borderRadius: 10,
      border: '1px solid var(--border)',
      padding: 16,
    }}>
      <div style={{
        color: 'var(--text-secondary)', fontSize: 12, fontWeight: 600,
        marginBottom: 12, letterSpacing: '0.05em',
      }}>
        LANGUAGE BREAKDOWN
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%" cy="50%"
            innerRadius={55} outerRadius={80}
            paddingAngle={3} dataKey="value"
          >
            {chartData.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: tooltipBg, border: `1px solid ${tooltipBorder}`,
              borderRadius: 8, color: tooltipColor, fontSize: 12,
            }}
            formatter={(v) => [`${v}%`, '']}
          />
          <Legend
            formatter={(v) => (
              <span style={{ color: legendColor, fontSize: 11 }}>{v}</span>
            )}
            iconSize={8}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}