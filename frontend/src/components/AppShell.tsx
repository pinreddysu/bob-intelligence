import React, { useState, useCallback, useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Brain,
  LayoutList,
  Menu,
  X,
  RefreshCw,
  AlertCircle,
  Loader2,
  Sparkles,
  GitBranch,
  BarChart3,
  Search,
  Activity,
  Sun,
  Moon,
} from "lucide-react";
import { healthCheck } from "../api/client";

// ---------------------------------------------------------------------------
// Connection status indicator
// ---------------------------------------------------------------------------

type ConnStatus = "idle" | "checking" | "ok" | "error";

function ConnectionIndicator({
  status,
  onCheck,
}: {
  status: ConnStatus;
  onCheck: () => void;
}) {
  if (status === "checking") {
    return (
      <button
        title="Checking backend connection…"
        onClick={onCheck}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          fontSize: "12.5px",
          fontWeight: 500,
          color: "var(--color-text-muted)",
          background: "var(--color-surface-subtle)",
          padding: "5px 10px",
          borderRadius: "var(--radius-full)",
          border: "1px solid var(--color-border)",
          cursor: "pointer",
        }}
      >
        <Loader2
          size={13}
          style={{
            animation: "spin 1s linear infinite",
            color: "var(--color-accent)",
          }}
        />
        <span>Connecting…</span>
      </button>
    );
  }
  if (status === "ok") {
    return (
      <button
        title="Backend connected — click to recheck"
        onClick={onCheck}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          fontSize: "12px",
          fontWeight: 600,
          color: "var(--color-green-text)",
          background: "var(--color-green-bg)",
          padding: "5px 10px",
          borderRadius: "var(--radius-full)",
          border: "1px solid var(--color-green-border)",
          cursor: "pointer",
        }}
      >
        <span className="pulse-dot pulse-dot-green" />
        <span>Connected</span>
      </button>
    );
  }
  if (status === "error") {
    return (
      <button
        title="Backend unreachable — click to retry"
        onClick={onCheck}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          fontSize: "12px",
          fontWeight: 600,
          color: "var(--color-red-text)",
          background: "var(--color-red-bg)",
          padding: "5px 10px",
          borderRadius: "var(--radius-full)",
          border: "1px solid var(--color-red-border)",
          cursor: "pointer",
        }}
      >
        <AlertCircle size={13} style={{ color: "var(--color-red)" }} />
        <span>Offline — Retry</span>
      </button>
    );
  }
  return (
    <button
      title="Check backend connection"
      onClick={onCheck}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "6px",
        fontSize: "12px",
        color: "var(--color-text-muted)",
        background: "var(--color-surface-subtle)",
        padding: "5px 10px",
        borderRadius: "var(--radius-full)",
        border: "1px solid var(--color-border)",
        cursor: "pointer",
      }}
    >
      <Activity size={13} />
      <span>Check Status</span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Nav item
// ---------------------------------------------------------------------------

interface NavItemProps {
  to: string;
  icon: React.ReactNode;
  label: string;
  end?: boolean;
  planned?: boolean;
  badge?: string;
  onClick?: () => void;
}

function NavItem({
  to,
  icon,
  label,
  end,
  planned,
  badge,
  onClick,
}: NavItemProps) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      style={({ isActive }) => ({
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "9px 12px",
        borderRadius: "var(--radius)",
        color: isActive
          ? "#FFFFFF"
          : planned
            ? "var(--color-sidebar-text-muted)"
            : "var(--color-sidebar-text)",
        background: isActive
          ? "linear-gradient(135deg, rgba(37, 99, 235, 0.9) 0%, rgba(79, 70, 229, 0.9) 100%)"
          : "transparent",
        fontSize: "13.5px",
        fontWeight: isActive ? 600 : 500,
        textDecoration: "none",
        transition: "all 0.15s ease",
        boxShadow: isActive ? "0 2px 8px rgba(37, 99, 235, 0.35)" : "none",
      })}
      className="sidebar-nav-item"
    >
      {({ isActive }) => (
        <>
          <span
            style={{
              color: isActive ? "#FFFFFF" : "var(--color-sidebar-text-muted)",
            }}
          >
            {icon}
          </span>
          <span style={{ flex: 1 }}>{label}</span>
          {badge && (
            <span
              style={{
                fontSize: "9.5px",
                fontWeight: 700,
                color: isActive ? "#FFFFFF" : planned ? "#FBBF24" : "#60A5FA",
                background: isActive
                  ? "rgba(255,255,255,0.2)"
                  : planned
                    ? "rgba(245, 158, 11, 0.15)"
                    : "rgba(37,99,235,0.15)",
                border:
                  planned && !isActive
                    ? "1px solid rgba(245, 158, 11, 0.3)"
                    : "none",
                borderRadius: "4px",
                padding: "2px 6px",
                letterSpacing: "0.04em",
              }}
            >
              {badge}
            </span>
          )}
        </>
      )}
    </NavLink>
  );
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

interface SidebarProps {
  open: boolean;
  onClose: () => void;
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
            position: "fixed",
            inset: 0,
            background: "rgba(15, 23, 42, 0.65)",
            backdropFilter: "blur(4px)",
            zIndex: 40,
          }}
        />
      )}
      <aside
        aria-label="Main navigation"
        style={{
          width: "var(--sidebar-width)",
          minHeight: "100vh",
          background: "var(--color-sidebar)",
          borderRight: "1px solid var(--color-sidebar-border)",
          display: "flex",
          flexDirection: "column",
          flexShrink: 0,
          position: "fixed",
          top: 0,
          left: open ? 0 : "calc(-1 * var(--sidebar-width))",
          bottom: 0,
          zIndex: 50,
          transition: "left 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
        className="app-sidebar"
      >
        {/* Brand */}
        <div
          style={{
            padding: "20px 18px 18px",
            borderBottom: "1px solid var(--color-sidebar-border)",
            display: "flex",
            alignItems: "center",
            gap: "12px",
            justifyContent: "space-between",
          }}
        >
          <div
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "10px",
              background: "linear-gradient(135deg, #2563EB 0%, #7C3AED 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 0 16px rgba(79, 70, 229, 0.4)",
              flexShrink: 0,
            }}
          >
            <Brain size={20} color="#FFFFFF" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <p
                style={{
                  color: "#F8FAFC",
                  fontWeight: 700,
                  fontSize: "14.5px",
                  letterSpacing: "-0.02em",
                  whiteSpace: "nowrap",
                }}
              >
                Bob Intelligence
              </p>
              <span
                style={{
                  fontSize: "9.5px",
                  fontWeight: 700,
                  background: "rgba(37, 99, 235, 0.25)",
                  color: "#60A5FA",
                  border: "1px solid rgba(96, 165, 250, 0.3)",
                  padding: "1px 5px",
                  borderRadius: "4px",
                }}
              >
                v1.0
              </span>
              {/* Mobile sidebar close button */}
              <button
                onClick={onClose}
                aria-label="Close navigation"
                className="close-sidebar-btn"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: "50%",
                  width: "20px",
                  height: "20px",
                  cursor: "pointer",
                  color: "#E2E8F0",
                  flexShrink: 0,
                }}
              >
                <X size={14} />
              </button>
            </div>
            <p
              style={{
                color: "var(--color-sidebar-text-muted)",
                fontSize: "11px",
                display: "flex",
                alignItems: "center",
                gap: "4px",
                marginTop: "1px",
              }}
            >
              <Sparkles size={10} style={{ color: "#F59E0B" }} />
              Autonomous Mission Control
            </p>
          </div>
        </div>

        {/* Navigation links */}
        <div
          style={{
            padding: "16px 10px",
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: "4px",
          }}
        >
          <p
            style={{
              color: "var(--color-sidebar-text-faint)",
              fontSize: "11px",
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              padding: "6px 12px 6px",
            }}
          >
            Autonomous Execution
          </p>
          <NavItem
            to="/"
            end
            icon={<LayoutList size={16} />}
            label="Story Queue"
            badge="LIVE"
            onClick={onClose}
          />

          {/* Future roadmap section */}
          <div
            style={{
              margin: "10px 8px 6px",
              borderTop: "1px solid rgba(255, 255, 255, 0.06)",
            }}
          />
          <p
            style={{
              color: "var(--color-sidebar-text-faint)",
              fontSize: "10.5px",
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              padding: "6px 12px 4px",
            }}
          >
            Future Features
          </p>
          <NavItem
            to="/sessions"
            icon={<GitBranch size={16} />}
            label="Bob Sessions"
            planned
            badge="FUTURE"
            onClick={onClose}
          />
          <NavItem
            to="/outcomes"
            icon={<BarChart3 size={16} />}
            label="Outcomes & Review"
            planned
            badge="FUTURE"
            onClick={onClose}
          />
        </div>

        {/* Sidebar Info Card */}
        <div style={{ padding: "14px 14px 16px" }}>
          <div
            style={{
              background: "rgba(255, 255, 255, 0.03)",
              border: "1px solid var(--color-sidebar-border)",
              borderRadius: "var(--radius)",
              padding: "12px 14px",
              display: "flex",
              flexDirection: "column",
              gap: "6px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <span
                style={{
                  fontSize: "10.5px",
                  color: "#60A5FA",
                  fontWeight: 700,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                }}
              >
                AUTONOMOUS AGENT
              </span>
              <span
                className="pulse-dot pulse-dot-green"
                title="IBM Bob Headless Runtime Online"
              />
            </div>
            <p
              style={{
                color: "#F8FAFC",
                fontSize: "13px",
                fontWeight: 700,
                letterSpacing: "-0.01em",
              }}
            >
              IBM Bob Agent
            </p>
            <p
              style={{
                color: "var(--color-sidebar-text-muted)",
                fontSize: "11px",
                lineHeight: 1.4,
              }}
            >
              Headless CLI &bull; TF-IDF Retrieval
            </p>
            <div
              style={{
                marginTop: "4px",
                paddingTop: "6px",
                borderTop: "1px solid rgba(255, 255, 255, 0.06)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                fontSize: "10px",
                color: "var(--color-sidebar-text-faint)",
              }}
            >
              <span>Guardrails: ACTIVE</span>
              <span style={{ color: "#10B981", fontWeight: 600 }}>ONLINE</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "12px 18px",
            borderTop: "1px solid var(--color-sidebar-border)",
            fontSize: "11px",
            color: "var(--color-sidebar-text-faint)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span>Bob Intelligence</span>
          <span style={{ color: "#10B981", fontWeight: 600 }}>Ready</span>
        </div>
      </aside>
    </>
  );
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

interface HeaderProps {
  title: string;
  subtitle?: string;
  onMenuClick: () => void;
  searchValue?: string;
  onSearchChange?: (v: string) => void;
  onRefresh?: () => void;
  showSearch?: boolean;
  connStatus: ConnStatus;
  onConnCheck: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
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
  theme,
  onToggleTheme,
}: HeaderProps) {
  return (
    <header
      style={{
        height: "var(--header-height)",
        background: "var(--color-header-bg)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid var(--color-border)",
        display: "flex",
        alignItems: "center",
        padding: "0 24px",
        gap: "16px",
        position: "sticky",
        top: 0,
        zIndex: 30,
      }}
    >
      {/* Mobile hamburger */}
      <button
        onClick={onMenuClick}
        aria-label="Open navigation"
        style={{
          display: "none",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--color-text-secondary)",
          padding: "6px",
          borderRadius: "var(--radius)",
          border: "1px solid var(--color-border)",
          background: "var(--color-surface)",
        }}
        className="menu-toggle"
      >
        <Menu size={18} />
      </button>

      {/* Title & breadcrumbs */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <h1
            style={{
              fontSize: "16px",
              fontWeight: 700,
              color: "var(--color-text)",
              letterSpacing: "-0.02em",
              lineHeight: 1.2,
            }}
          >
            {title}
          </h1>
        </div>
        {subtitle && (
          <p
            style={{
              fontSize: "12px",
              color: "var(--color-text-muted)",
              lineHeight: 1.3,
              marginTop: "1px",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {subtitle}
          </p>
        )}
      </div>

      {/* Search Bar */}
      {showSearch && onSearchChange !== undefined && (
        <div
          style={{
            position: "relative",
            display: "flex",
            alignItems: "center",
          }}
        >
          <Search
            size={14}
            style={{
              position: "absolute",
              left: "10px",
              color: "var(--color-text-faint)",
              pointerEvents: "none",
            }}
          />
          <input
            type="search"
            value={searchValue}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search stories, keys, status…"
            aria-label="Search stories"
            className="input-base"
            style={{
              paddingLeft: "32px",
              paddingRight: searchValue ? "28px" : "10px",
              height: "34px",
              width: "260px",
              fontSize: "12.5px",
              background: "var(--color-bg)",
            }}
          />
          {searchValue && (
            <button
              onClick={() => onSearchChange("")}
              aria-label="Clear search"
              style={{
                position: "absolute",
                right: "8px",
                color: "var(--color-text-faint)",
                padding: "2px",
              }}
            >
              <X size={12} />
            </button>
          )}
        </div>
      )}

      {/* Refresh */}
      {onRefresh && (
        <button
          onClick={onRefresh}
          title="Refresh stories"
          aria-label="Refresh stories"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--color-text-secondary)",
            padding: "7px",
            borderRadius: "var(--radius)",
            border: "1px solid var(--color-border)",
            background: "var(--color-surface)",
            cursor: "pointer",
          }}
        >
          <RefreshCw size={15} />
        </button>
      )}

      {/* Theme toggle */}
      <button
        onClick={onToggleTheme}
        title={
          theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
        }
        aria-label="Toggle theme"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--color-text-secondary)",
          padding: "7px",
          borderRadius: "var(--radius)",
          border: "1px solid var(--color-border)",
          background: "var(--color-surface)",
          cursor: "pointer",
          transition: "all 0.15s ease",
        }}
      >
        {theme === "dark" ? (
          <Sun size={15} style={{ color: "#F59E0B" }} />
        ) : (
          <Moon size={15} style={{ color: "#6366F1" }} />
        )}
      </button>

      {/* Connection status */}
      <ConnectionIndicator status={connStatus} onCheck={onConnCheck} />
    </header>
  );
}

// ---------------------------------------------------------------------------
// App shell
// ---------------------------------------------------------------------------

export interface AppShellProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  searchValue?: string;
  onSearchChange?: (v: string) => void;
  onRefresh?: () => void;
  showSearch?: boolean;
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
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [connStatus, setConnStatus] = useState<ConnStatus>("idle");
  const location = useLocation();

  // Theme management with localStorage persistence and system preference fallback
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    try {
      const saved = localStorage.getItem("bob-theme");
      if (saved === "light" || saved === "dark") return saved;
      if (
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches
      ) {
        return "dark";
      }
    } catch {
      // ignore
    }
    return "light";
  });

  useEffect(() => {
    try {
      document.documentElement.setAttribute("data-theme", theme);
      localStorage.setItem("bob-theme", theme);
    } catch {
      // ignore
    }
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  }, []);

  // Close sidebar on route change
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  const checkConn = useCallback(() => {
    setConnStatus("checking");
    healthCheck()
      .then(() => setConnStatus("ok"))
      .catch(() => setConnStatus("error"));
  }, []);

  // Check on mount
  useEffect(() => {
    checkConn();
  }, [checkConn]);

  return (
    <div
      style={{
        display: "flex",
        minHeight: "100vh",
        background: "var(--color-bg)",
      }}
    >
      <style>{`
        /* Desktop: always show sidebar inline */
        @media (min-width: 900px) {
          .app-sidebar {
            position: sticky !important;
            left: 0 !important;
            top: 0 !important;
            height: 100vh !important;
            align-self: flex-start;
          }
          .main-content {
            margin-left: 0 !important;
          }
          .menu-toggle { display: none !important; }
          .close-sidebar-btn { display: none !important;}
        }
        @media (max-width: 899px) {
          .menu-toggle { display: flex !important; }
        }
        .sidebar-nav-item:hover {
          background: rgba(255, 255, 255, 0.06) !important;
          color: #FFFFFF !important;
        }
      `}</style>

      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main content area */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
        }}
        className="main-content"
      >
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
          theme={theme}
          onToggleTheme={toggleTheme}
        />

        <main
          style={{
            flex: 1,
            padding: "24px 28px",
            maxWidth: "1400px",
            width: "100%",
            margin: "0 auto",
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
