import React, { useState, useCallback, useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { clsx } from 'clsx'
import {
  Brain,
  LayoutList,
  ChevronRight,
  Menu,
  X,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Loader2,
} from 'lucide-react'
import { healthCheck } from '../api/client'

// ---------------------------------------------------------------------------
// Connection status indicator
// ---------------------------------------------------------------------------

type ConnStatus = 'idle' | 'checking' | 'ok' | 'error'

function ConnectionIndicator({
  status,
  onCheck,
}: {
  status: ConnStatus
  onCheck: () => void
}) {
  if (status === 'checking') {
    return (
      <button
        title="Checking backend connection…"
        onClick={onCheck}
        style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '12px', color: 'var(--color-text-muted)', background: 'none', border: 'none', cursor: 'pointer' }}
      >
        <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />
        Connecting
      </button>
    )
  }
  if (status === 'ok') {
    return (
      <button
        title="Backend connected — click to recheck"
        onClick={onCheck}
        style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '12px', color: 'var(--color-green)', background: 'none', border: 'none', cursor: 'pointer' }}
      >
        <CheckCircle2 size={13} />
        Connected
      </button>
    )
  }
  if (status === 'error') {
    return (
      <button
        title="Backend unreachable — click to retry"
        onClick={onCheck}
        style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '12px', color: 'var(--color-red)', background: 'none', border: 'none', cursor: 'pointer' }}
      >
        <AlertCircle size={13} />
        Offline
      </button>
    )
  }
  return (
    <button
      title="Check backend connection"
      onClick={onCheck}
      style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '12px', color: 'var(--color-text-muted)', background: 'none', border: 'none', cursor: 'pointer' }}
    >
      <AlertCircle size={13} />
      Unknown
    </button>
  )
}

// ---------------------------------------------------------------------------
// Nav item
// ---------------------------------------------------------------------------

interface NavItemProps {
  to: string
  icon: React.ReactNode
  label: string
  end?: boolean
  planned?: boolean
  onClick?: () => void
}

function NavItem({ to, icon, label, end, planned, onClick }: NavItemProps) {
  if (planned) {
    return (
      <div
        title="Not yet implemented"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: '8px 12px',
          borderRadius: 'var(--radius)',
          color: '#4B5563',
          cursor: 'not-allowed',
          fontSize: '13.5px',
          userSelect: 'none',
        }}
      >
        <span style={{ opacity: 0.5 }}>{icon}</span>
        <span style={{ opacity: 0.5 }}>{label}</span>
        <span style={{
          marginLeft: 'auto',
          fontSize: '10px',
          fontWeight: 600,
          color: '#374151',
          background: '#1F2937',
          borderRadius: '3px',
          padding: '1px 5px',
          letterSpacing: '0.04em',
        }}>
          PLANNED
        </span>
      </div>
    )
  }

  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      style={({ isActive }) => ({
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '8px 12px',
        borderRadius: 'var(--radius)',
        color: isActive ? '#fff' : 'var(--color-sidebar-text)',
        background: isActive ? 'var(--color-sidebar-active)' : 'transparent',
        fontSize: '13.5px',
        fontWeight: isActive ? 600 : 400,
        textDecoration: 'none',
        transition: 'background 0.1s, color 0.1s',
      })}
      className={({ isActive }) =>
        clsx(!isActive && 'hover:bg-[#1F2937]')
      }
    >
      {icon}
      {label}
    </NavLink>
  )
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

interface SidebarProps {
  open: boolean
  onClose: () => void
}

function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          aria-hidden
          onClick={onClose}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            zIndex: 40,
          }}
        />
      )}
      <nav
        aria-label="Main navigation"
        style={{
          width: 'var(--sidebar-width)',
          minHeight: '100vh',
          background: 'var(--color-sidebar)',
          display: 'flex',
          flexDirection: 'column',
          padding: '0',
          flexShrink: 0,
          position: 'fixed',
          top: 0,
          left: open ? 0 : 'calc(-1 * var(--sidebar-width))',
          bottom: 0,
          zIndex: 50,
          transition: 'left 0.2s ease',
        }}
        className="lg-sidebar"
      >
        {/* Brand */}
        <div
          style={{
            padding: '18px 16px 16px',
            borderBottom: '1px solid #1F2937',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <Brain size={22} color="#60A5FA" />
          <div>
            <p style={{ color: '#F9FAFB', fontWeight: 700, fontSize: '14px', lineHeight: 1.3 }}>
              Bob Intelligence
            </p>
            <p style={{ color: '#6B7280', fontSize: '11px' }}>Mission Control</p>
          </div>
        </div>

        {/* Navigation links */}
        <div style={{ padding: '12px 8px', flex: 1, display: 'flex', flexDirection: 'column', gap: '2px' }}>
          <p style={{ color: '#4B5563', fontSize: '11px', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', padding: '4px 12px 6px' }}>
            Execution Decisions
          </p>
          <NavItem
            to="/"
            end
            icon={<LayoutList size={16} />}
            label="Story Queue"
            onClick={onClose}
          />
          <NavItem
            to="#"
            icon={<ChevronRight size={16} />}
            label="Bob Sessions"
            planned
          />
          <NavItem
            to="#"
            icon={<ChevronRight size={16} />}
            label="Outcomes"
            planned
          />
        </div>

        {/* Footer */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid #1F2937', fontSize: '11px', color: '#4B5563' }}>
          Milestone 6 — Frontend
        </div>
      </nav>
    </>
  )
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

interface HeaderProps {
  title: string
  subtitle?: string
  onMenuClick: () => void
  searchValue?: string
  onSearchChange?: (v: string) => void
  onRefresh?: () => void
  showSearch?: boolean
  connStatus: ConnStatus
  onConnCheck: () => void
}

function Header({
  title,
  subtitle,
  onMenuClick,
  searchValue,
  onSearchChange,
  onRefresh,
  showSearch,
  connStatus,
  onConnCheck,
}: HeaderProps) {
  return (
    <header
      style={{
        height: 'var(--header-height)',
        background: 'var(--color-surface)',
        borderBottom: '1px solid var(--color-border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 20px',
        gap: '16px',
        position: 'sticky',
        top: 0,
        zIndex: 30,
      }}
    >
      {/* Mobile hamburger */}
      <button
        onClick={onMenuClick}
        aria-label="Open navigation"
        style={{ display: 'flex', alignItems: 'center', color: 'var(--color-text-muted)', padding: '4px' }}
        className="menu-toggle"
      >
        <Menu size={18} />
      </button>

      {/* Title */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <h1 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--color-text)', lineHeight: 1.2 }}>
          {title}
        </h1>
        {subtitle && (
          <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', lineHeight: 1.3 }}>
            {subtitle}
          </p>
        )}
      </div>

      {/* Search */}
      {showSearch && onSearchChange !== undefined && (
        <input
          type="search"
          value={searchValue}
          onChange={e => onSearchChange(e.target.value)}
          placeholder="Search stories…"
          aria-label="Search stories"
          style={{
            padding: '6px 10px',
            borderRadius: 'var(--radius)',
            border: '1px solid var(--color-border)',
            fontSize: '13px',
            width: '200px',
            background: 'var(--color-bg)',
            color: 'var(--color-text)',
          }}
        />
      )}

      {/* Refresh */}
      {onRefresh && (
        <button
          onClick={onRefresh}
          title="Refresh"
          aria-label="Refresh stories"
          style={{ display: 'flex', alignItems: 'center', color: 'var(--color-text-muted)', padding: '4px' }}
        >
          <RefreshCw size={16} />
        </button>
      )}

      {/* Connection status */}
      <ConnectionIndicator status={connStatus} onCheck={onConnCheck} />
    </header>
  )
}

// ---------------------------------------------------------------------------
// App shell
// ---------------------------------------------------------------------------

export interface AppShellProps {
  title: string
  subtitle?: string
  children: React.ReactNode
  searchValue?: string
  onSearchChange?: (v: string) => void
  onRefresh?: () => void
  showSearch?: boolean
}

export function AppShell({
  title,
  subtitle,
  children,
  searchValue,
  onSearchChange,
  onRefresh,
  showSearch,
}: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [connStatus, setConnStatus] = useState<ConnStatus>('idle')
  const location = useLocation()

  // Close sidebar on route change
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  const checkConn = useCallback(() => {
    setConnStatus('checking')
    healthCheck()
      .then(() => setConnStatus('ok'))
      .catch(() => setConnStatus('error'))
  }, [])

  // Check on mount
  useEffect(() => {
    checkConn()
  }, [checkConn])

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--color-bg)' }}>
      <style>{`
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        /* Desktop: always show sidebar inline */
        @media (min-width: 768px) {
          .lg-sidebar {
            position: sticky !important;
            left: 0 !important;
            top: 0 !important;
            height: 100vh !important;
            align-self: flex-start;
          }
          .menu-toggle { display: none !important; }
        }
        @media (max-width: 767px) {
          .lg-sidebar {
            position: fixed !important;
          }
        }
        .hover\\:bg-\\[\\#1F2937\\]:hover {
          background: #1F2937 !important;
        }
      `}</style>

      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Mobile sidebar close button */}
      {sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(false)}
          aria-label="Close navigation"
          style={{
            position: 'fixed',
            top: '14px',
            left: 'calc(var(--sidebar-width) - 36px)',
            zIndex: 60,
            background: '#374151',
            border: 'none',
            borderRadius: '50%',
            width: '28px',
            height: '28px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: '#D1D5DB',
          }}
        >
          <X size={14} />
        </button>
      )}

      {/* Main content area */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          marginLeft: 0,
        }}
        className="main-content"
      >
        <style>{`
          @media (min-width: 768px) {
            .main-content {
              margin-left: var(--sidebar-width) !important;
            }
          }
        `}</style>

        <Header
          title={title}
          subtitle={subtitle}
          onMenuClick={() => setSidebarOpen(true)}
          searchValue={searchValue}
          onSearchChange={onSearchChange}
          onRefresh={onRefresh}
          showSearch={showSearch}
          connStatus={connStatus}
          onConnCheck={checkConn}
        />

        <main style={{ flex: 1, padding: '20px' }}>
          {children}
        </main>
      </div>
    </div>
  )
}
