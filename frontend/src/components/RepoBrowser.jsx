import { useState, useEffect } from 'react'
import api from '../utils/api'
import toast from 'react-hot-toast'

function FileNode({ file, selected, onToggle }) {
  const isSelected = selected.has(file.path)
  return (
    <div
      onClick={() => onToggle(file.path)}
      style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '5px 10px', cursor: 'pointer', borderRadius: 6,
        background: isSelected ? 'var(--brand-bg)' : 'transparent',
        transition: 'background 0.1s',
      }}
      onMouseEnter={e => {
        if (!isSelected) e.currentTarget.style.background = 'var(--bg-hover)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = isSelected ? 'var(--brand-bg)' : 'transparent'
      }}
    >
      <input
        type="checkbox"
        checked={isSelected}
        onChange={() => onToggle(file.path)}
        onClick={e => e.stopPropagation()}
        style={{ width: 13, height: 13, accentColor: 'var(--brand)', flexShrink: 0 }}
      />
      <span style={{ fontSize: 12 }}>📄</span>
      <span style={{
        color: isSelected ? 'var(--brand-muted)' : 'var(--text-secondary)',
        fontSize: 12, flex: 1,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {file.path}
      </span>
      {file.size != null && (
        <span style={{ color: 'var(--text-faintest)', fontSize: 10, flexShrink: 0 }}>
          {(file.size / 1024).toFixed(1)}KB
        </span>
      )}
    </div>
  )
}

export default function RepoBrowser({ repo, connectionId, onAnalyse }) {
  const [tree, setTree]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(new Set())

  useEffect(() => {
    if (!repo || !connectionId) return
    setLoading(true)
    const [owner, repoName] = repo.split('/')
    api.get(`/github/repos/${owner}/${repoName}/tree?connection_id=${connectionId}`)
      .then(r => setTree(r.data.files || []))
      .catch(() => toast.error('Failed to load repo tree'))
      .finally(() => setLoading(false))
  }, [repo, connectionId])

  const toggle = (path) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  const selectAll = () => {
    setSelected(new Set((tree || []).map(f => f.path)))
  }

  if (loading) return (
    <div style={{ color: 'var(--text-faint)', fontSize: 13, padding: 16 }}>
      Loading file tree...
    </div>
  )
  if (!tree) return null

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 10, overflow: 'hidden',
    }}>
      <div style={{
        padding: '10px 12px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: 12, fontWeight: 600 }}>FILES</span>
        <span style={{ color: 'var(--text-faint)', fontSize: 11 }}>{selected.size} selected</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <button
            onClick={selectAll}
            style={{
              padding: '4px 10px', borderRadius: 5,
              border: '1px solid var(--border-muted)',
              background: 'transparent', color: 'var(--text-faint)',
              fontSize: 11, cursor: 'pointer',
            }}
          >Select all</button>
          <button
            disabled={selected.size === 0}
            onClick={() => onAnalyse([...selected])}
            style={{
              padding: '4px 12px', borderRadius: 5,
              border: `1px solid ${selected.size > 0 ? 'var(--brand)' : 'var(--border)'}`,
              background: selected.size > 0 ? 'var(--brand-bg)' : 'transparent',
              color: selected.size > 0 ? 'var(--brand-muted)' : 'var(--text-faintest)',
              fontSize: 11, cursor: selected.size > 0 ? 'pointer' : 'default',
              fontWeight: 600,
            }}
          >
            Analyse {selected.size > 0 ? `(${selected.size})` : ''}
          </button>
        </div>
      </div>

      <div style={{ maxHeight: 360, overflowY: 'auto', padding: 6 }}>
        {tree.map(file => (
          <FileNode key={file.path} file={file} selected={selected} onToggle={toggle} />
        ))}
        {tree.length === 0 && (
          <div style={{ color: 'var(--text-faint)', fontSize: 12, padding: '12px 10px' }}>
            No supported code files found.
          </div>
        )}
      </div>
    </div>
  )
}