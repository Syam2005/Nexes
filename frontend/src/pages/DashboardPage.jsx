import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'
import api from '../utils/api'
import toast from 'react-hot-toast'
import RepoBrowser from '../components/RepoBrowser'

const TABS = ['file', 'url', 'repo']

export default function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const fileRef = useRef(null)

  const [tab, setTab] = useState('file')
  const [files, setFiles] = useState([])
  const [repoUrl, setRepoUrl] = useState('')
  const [selectedConn, setSelectedConn] = useState(null)
  const [selectedRepo, setSelectedRepo] = useState('')
  const [loading, setLoading] = useState(false)
  const [recentAnalyses, setRecentAnalyses] = useState([])

  // FIX: useEffect for data fetching, not useState
  useEffect(() => {
    api.get('/history?limit=3')
      .then(r => setRecentAnalyses(r.data?.analyses || r.data || []))
      .catch(() => {})
  }, [])

  const handleFileChange = (e) => {
    const f = Array.from(e.target.files || [])
    setFiles(f)
    if (f.length) toast.success(`${f.length} file${f.length > 1 ? 's' : ''} selected`)
  }

  const analyseFiles = async () => {
    if (!files.length) return toast.error('Select at least one file')
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', files[0])
      const r = await api.post('/analyze/file', fd)
      navigate(`/analysis/${r.data.analysis_id}`)
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  const analyseUrl = async () => {
    if (!repoUrl.trim()) return toast.error('Enter a GitHub URL')
    setLoading(true)
    try {
      // FIX: /analyze/url expects Form data fields, not JSON
      const fd = new FormData()
      fd.append('repo_url', repoUrl.trim())
      const r = await api.post('/analyze/url', fd)
      navigate(`/analysis/${r.data.analysis_id}`)
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  const analyseRepoPaths = async (paths) => {
    if (!paths.length) return
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('repo_url', selectedRepo)
      fd.append('file_paths', paths.join(','))
      if (selectedConn) fd.append('connection_id', selectedConn)
      const r = await api.post('/analyze/url', fd)
      navigate(`/analysis/${r.data.analysis_id}`)
    } catch (e) {
      const msg = e.response?.data?.detail
      toast.error(typeof msg === 'string' ? msg : 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  const connections = user?.github_connections || []

  return (
    <div style={{ padding: '28px 32px', maxWidth: 920, margin: '0 auto' }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ color: '#e2e8f0', fontSize: 22, fontWeight: 700, margin: 0 }}>
          Analyse Code
        </h1>
        <p style={{ color: '#475569', fontSize: 13, margin: '6px 0 0' }}>
          Upload files, paste a GitHub URL, or browse your connected repos.
        </p>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex', gap: 2, marginBottom: 20, background: '#0a0f1e',
        borderRadius: 10, padding: 4, border: '1px solid #1e293b', width: 'fit-content',
      }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '7px 18px', borderRadius: 7, border: 'none', cursor: 'pointer',
            fontSize: 13, fontWeight: 500,
            background: tab === t ? '#1e293b' : 'transparent',
            color: tab === t ? '#e2e8f0' : '#475569',
            transition: 'all 0.15s',
          }}>
            {t === 'file' ? '📁 File Upload' : t === 'url' ? '🔗 GitHub URL' : '🗂️ My Repos'}
          </button>
        ))}
      </div>

      <div style={{
        background: '#0a0f1e', border: '1px solid #1e293b', borderRadius: 12,
        padding: 24, marginBottom: 24,
      }}>

        {tab === 'file' && (
          <div>
            <input
              type="file" ref={fileRef} multiple
              accept=".py,.js,.ts,.jsx,.tsx,.java,.go,.rs,.rb,.c,.cpp,.h,.cs,.php,.kt,.swift,.scala,.r,.sh,.sql"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />
            <div
              onClick={() => fileRef.current?.click()}
              style={{
                border: '2px dashed #1e293b', borderRadius: 10, padding: '40px 20px',
                textAlign: 'center', cursor: 'pointer', transition: 'border-color 0.15s',
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = '#6366f1'}
              onMouseLeave={e => e.currentTarget.style.borderColor = '#1e293b'}
            >
              <div style={{ fontSize: 32, marginBottom: 10 }}>📄</div>
              <div style={{ color: '#94a3b8', fontSize: 14, fontWeight: 500 }}>
                {files.length > 0 ? `${files.length} file(s) selected` : 'Click to upload code files'}
              </div>
              <div style={{ color: '#475569', fontSize: 12, marginTop: 4 }}>
                Python, JavaScript, TypeScript, Java, Go, Rust, Ruby, C, C++, C#, PHP, Kotlin, Swift, Scala, R, SQL, Bash
              </div>
              {files.length > 0 && (
                <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center' }}>
                  {files.map(f => (
                    <span key={f.name} style={{
                      background: '#1e293b', color: '#94a3b8',
                      padding: '3px 10px', borderRadius: 5, fontSize: 11,
                    }}>
                      {f.name}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <button
              onClick={analyseFiles}
              disabled={loading || files.length === 0}
              style={{
                marginTop: 16, width: '100%', padding: '12px 20px', borderRadius: 10,
                background: files.length > 0 ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : '#1e293b',
                color: files.length > 0 ? '#fff' : '#475569',
                border: 'none', fontSize: 14, fontWeight: 600,
                cursor: files.length > 0 && !loading ? 'pointer' : 'default',
              }}
            >
              {loading ? 'Analysing...' : `Analyse ${files.length > 0 ? `${files.length} file(s)` : 'files'}`}
            </button>
          </div>
        )}

        {tab === 'url' && (
          <div>
            <label style={{
              color: '#64748b', fontSize: 12, fontWeight: 600,
              letterSpacing: '0.05em', display: 'block', marginBottom: 8,
            }}>
              GITHUB URL
            </label>
            <input
              value={repoUrl}
              onChange={e => setRepoUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              style={{
                width: '100%', padding: '11px 14px', borderRadius: 8,
                background: '#0f172a', border: '1px solid #1e293b', color: '#e2e8f0',
                fontSize: 13, outline: 'none', boxSizing: 'border-box',
              }}
              onFocus={e => e.target.style.borderColor = '#6366f1'}
              onBlur={e => e.target.style.borderColor = '#1e293b'}
              onKeyDown={e => e.key === 'Enter' && analyseUrl()}
            />
            <p style={{ color: '#334155', fontSize: 11, marginTop: 6 }}>
              Supports public repos and private repos from your connected GitHub accounts.
            </p>
            <button
              onClick={analyseUrl}
              disabled={loading || !repoUrl.trim()}
              style={{
                marginTop: 12, width: '100%', padding: '12px 20px', borderRadius: 10,
                background: repoUrl.trim() ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : '#1e293b',
                color: repoUrl.trim() ? '#fff' : '#475569',
                border: 'none', fontSize: 14, fontWeight: 600,
                cursor: repoUrl.trim() && !loading ? 'pointer' : 'default',
              }}
            >
              {loading ? 'Analysing...' : 'Analyse Repository'}
            </button>
          </div>
        )}

        {tab === 'repo' && (
          <div>
            {connections.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '30px 0' }}>
                <div style={{ fontSize: 28, marginBottom: 10 }}>🔗</div>
                <div style={{ color: '#64748b', fontSize: 14 }}>No GitHub accounts connected.</div>
                <a href="/profile" style={{ color: '#818cf8', fontSize: 13, marginTop: 8, display: 'inline-block' }}>
                  Connect GitHub in Profile →
                </a>
              </div>
            ) : (
              <div>
                <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
                  {connections.map(c => (
                    <button
                      key={c.id}
                      onClick={() => { setSelectedConn(c.id); setSelectedRepo('') }}
                      style={{
                        padding: '7px 14px', borderRadius: 8,
                        border: `1px solid ${selectedConn === c.id ? '#6366f1' : '#1e293b'}`,
                        background: selectedConn === c.id ? 'rgba(99,102,241,0.12)' : 'transparent',
                        color: selectedConn === c.id ? '#818cf8' : '#64748b',
                        fontSize: 12, cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: 6,
                      }}
                    >
                      {c.avatar_url && (
                        <img src={c.avatar_url} alt="" style={{ width: 16, height: 16, borderRadius: '50%' }} />
                      )}
                      {c.github_username}
                    </button>
                  ))}
                </div>
                {selectedConn && (
                  <div>
                    <RepoSelector connId={selectedConn} onSelectRepo={setSelectedRepo} />
                    {selectedRepo && (
                      <div style={{ marginTop: 14 }}>
                        <RepoBrowser repo={selectedRepo} connectionId={selectedConn} onAnalyse={analyseRepoPaths} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Recent analyses */}
      {recentAnalyses.length > 0 && (
        <div>
          <h2 style={{ color: '#94a3b8', fontSize: 12, fontWeight: 600, marginBottom: 12, letterSpacing: '0.05em' }}>
            RECENT ANALYSES
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {recentAnalyses.map(a => (
              <div
                key={a.id}
                onClick={() => navigate(`/analysis/${a.id}`)}
                style={{
                  background: '#0a0f1e', border: '1px solid #1e293b', borderRadius: 10,
                  padding: '12px 16px', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 12,
                  transition: 'border-color 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = '#334155'}
                onMouseLeave={e => e.currentTarget.style.borderColor = '#1e293b'}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#e2e8f0', fontSize: 13, fontWeight: 500 }}>{a.source_name}</div>
                  <div style={{ color: '#475569', fontSize: 11, marginTop: 2 }}>
                    {a.language} · {a.total_issues} issues · {new Date(a.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div style={{
                  padding: '3px 10px', borderRadius: 5, fontSize: 11, fontWeight: 700,
                  background: a.status === 'complete'
                    ? 'rgba(16,185,129,0.1)' : a.status === 'running'
                    ? 'rgba(99,102,241,0.1)' : 'rgba(71,85,105,0.1)',
                  color: a.status === 'complete' ? '#10b981' : a.status === 'running' ? '#818cf8' : '#64748b',
                }}>{a.status}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function RepoSelector({ connId, onSelectRepo }) {
  const [repos, setRepos] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState('')

  // FIX: useEffect for data fetching
  useEffect(() => {
    setLoading(true)
    api.get(`/github/repos?connection_id=${connId}`)
      .then(r => setRepos(Array.isArray(r.data) ? r.data : (r.data?.repos || [])))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [connId])

  const filtered = repos.filter(r =>
    r.full_name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div>
      <input
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Search repositories..."
        style={{
          width: '100%', padding: '9px 12px', borderRadius: 8,
          background: '#0f172a', border: '1px solid #1e293b', color: '#e2e8f0',
          fontSize: 12, outline: 'none', marginBottom: 8, boxSizing: 'border-box',
        }}
      />
      {loading ? (
        <div style={{ color: '#475569', fontSize: 12 }}>Loading repos...</div>
      ) : (
        <div style={{ maxHeight: 200, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {filtered.slice(0, 30).map(r => (
            <button
              key={r.full_name}
              onClick={() => { setSelected(r.full_name); onSelectRepo(r.full_name) }}
              style={{
                padding: '8px 12px', borderRadius: 7,
                border: `1px solid ${selected === r.full_name ? '#6366f1' : '#1e293b'}`,
                background: selected === r.full_name ? 'rgba(99,102,241,0.1)' : 'transparent',
                color: selected === r.full_name ? '#818cf8' : '#64748b',
                fontSize: 12, cursor: 'pointer', textAlign: 'left',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}
            >
              <span>{r.full_name}</span>
              {r.language && <span style={{ color: '#334155', fontSize: 10 }}>{r.language}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}