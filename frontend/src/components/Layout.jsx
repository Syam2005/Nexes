import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'

const NAV = [
  { to: '/dashboard', icon: '◈', label: 'Dashboard' },
  { to: '/history',   icon: '⊙', label: 'History' },
  { to: '/profile',   icon: '◎', label: 'Profile' },
  { to: '/settings',  icon: '⊗', label: 'Settings' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)

  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg-base)', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside
        className="nx-sidebar"
        style={{
          width: collapsed ? 64 : 220,
          minWidth: collapsed ? 64 : 220,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Logo */}
        <div style={{ padding: '20px 16px 16px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8, flexShrink: 0,
              background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 14, fontWeight: 700, color: '#fff',
            }}>N</div>
            {!collapsed && (
              <span style={{ color: 'var(--text-primary)', fontWeight: 700, fontSize: 16, letterSpacing: '-0.5px' }}>
                NEXUS
              </span>
            )}
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '12px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {NAV.map(({ to, icon, label }) => (
            <NavLink key={to} to={to} style={({ isActive }) => ({
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '9px 10px', borderRadius: 8,
              color: isActive ? 'var(--brand-muted)' : 'var(--text-faint)',
              background: isActive ? 'var(--brand-bg)' : 'transparent',
              textDecoration: 'none', fontSize: 13, fontWeight: 500,
              transition: 'all 0.15s',
              whiteSpace: 'nowrap',
            })}>
              <span style={{ fontSize: 16, flexShrink: 0 }}>{icon}</span>
              {!collapsed && label}
            </NavLink>
          ))}
        </nav>

        {/* User / Collapse */}
        <div style={{
          padding: '8px 8px 16px',
          borderTop: '1px solid var(--border)',
          display: 'flex', flexDirection: 'column', gap: 4,
        }}>
          {user && !collapsed && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px' }}>
              {user.photo_url
                ? <img src={user.photo_url} alt="" style={{ width: 28, height: 28, borderRadius: '50%' }} />
                : <div style={{
                    width: 28, height: 28, borderRadius: '50%',
                    background: '#312e81',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: '#818cf8', fontSize: 12, fontWeight: 700,
                  }}>
                    {user.name?.[0]?.toUpperCase()}
                  </div>
              }
              <div style={{ overflow: 'hidden' }}>
                <div style={{
                  color: 'var(--text-primary)', fontSize: 12, fontWeight: 600,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>{user.name}</div>
                <div style={{ color: 'var(--text-faint)', fontSize: 11 }}>
                  {user.email?.split('@')[0]}
                </div>
              </div>
            </div>
          )}

          <button
            onClick={() => setCollapsed(c => !c)}
            style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px',
              borderRadius: 8, background: 'transparent', border: 'none',
              cursor: 'pointer', color: 'var(--text-faint)', fontSize: 13,
            }}
          >
            <span style={{ flexShrink: 0 }}>{collapsed ? '▶' : '◀'}</span>
            {!collapsed && 'Collapse'}
          </button>

          <button
            onClick={handleLogout}
            style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px',
              borderRadius: 8, background: 'transparent', border: 'none',
              cursor: 'pointer', color: 'var(--red)', fontSize: 13,
            }}
          >
            <span style={{ flexShrink: 0 }}>⏻</span>
            {!collapsed && 'Sign out'}
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="nx-main" style={{ flex: 1, overflow: 'auto' }}>
        <Outlet />
      </main>
    </div>
  )
}