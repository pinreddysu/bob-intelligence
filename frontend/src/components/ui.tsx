import React, { type ReactNode } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  Sparkles,
  User,
  Users,
  XCircle,
  Zap,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Badge
// ---------------------------------------------------------------------------

export type BadgeVariant =
  | 'default'
  | 'blue'
  | 'amber'
  | 'red'
  | 'green'
  | 'purple'
  | 'cyan'
  | 'gray'

const badgeColorMap: Record<BadgeVariant, { bg: string; text: string; border: string; dot: string }> = {
  default: { bg: 'var(--color-surface-subtle)', text: 'var(--color-text-secondary)', border: 'var(--color-border)', dot: 'var(--color-text-faint)' },
  blue: { bg: 'var(--color-accent-bg)', text: 'var(--color-accent)', border: 'var(--color-accent-border)', dot: 'var(--color-accent)' },
  amber: { bg: 'var(--color-amber-bg)', text: 'var(--color-amber-text)', border: 'var(--color-amber-border)', dot: 'var(--color-amber)' },
  red: { bg: 'var(--color-red-bg)', text: 'var(--color-red-text)', border: 'var(--color-red-border)', dot: 'var(--color-red)' },
  green: { bg: 'var(--color-green-bg)', text: 'var(--color-green-text)', border: 'var(--color-green-border)', dot: 'var(--color-green)' },
  purple: { bg: 'var(--color-purple-bg)', text: 'var(--color-purple-text)', border: 'var(--color-purple-border)', dot: 'var(--color-purple)' },
  cyan: { bg: 'var(--color-cyan-bg)', text: 'var(--color-cyan-text)', border: 'var(--color-cyan-border)', dot: 'var(--color-cyan)' },
  gray: { bg: 'var(--color-surface-subtle)', text: 'var(--color-text-muted)', border: 'var(--color-border)', dot: 'var(--color-text-faint)' },
}

export interface BadgeProps {
  children: ReactNode
  variant?: BadgeVariant
  className?: string
  style?: React.CSSProperties
  dot?: boolean
  icon?: ReactNode
}

export function Badge({
  children,
  variant = 'default',
  className = '',
  style: styleProp = {},
  dot = false,
  icon,
}: BadgeProps) {
  const c = badgeColorMap[variant] ?? badgeColorMap.default

  return (
    <span
      className={`badge badge-${variant} ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        padding: '3px 8px',
        borderRadius: '9999px',
        fontSize: '11.5px',
        fontWeight: 600,
        lineHeight: 1.3,
        letterSpacing: '0.01em',
        background: c.bg,
        color: c.text,
        border: `1px solid ${c.border}`,
        whiteSpace: 'nowrap',
        ...styleProp,
      }}
    >
      {dot && (
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: c.dot,
            flexShrink: 0,
          }}
        />
      )}
      {icon && <span style={{ display: 'inline-flex', alignItems: 'center' }}>{icon}</span>}
      {children}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Priority badge
// ---------------------------------------------------------------------------

export function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return <Badge variant="gray">—</Badge>
  const p = priority.toLowerCase()
  if (p === 'highest' || p === 'critical') {
    return (
      <Badge variant="red" dot icon={<AlertTriangle size={11} />}>
        {priority}
      </Badge>
    )
  }
  if (p === 'high') {
    return (
      <Badge variant="amber" dot>
        {priority}
      </Badge>
    )
  }
  if (p === 'medium') {
    return (
      <Badge variant="blue" dot>
        {priority}
      </Badge>
    )
  }
  return <Badge variant="gray">{priority}</Badge>
}

// ---------------------------------------------------------------------------
// Mode badge
// ---------------------------------------------------------------------------

export function ModeBadge({ mode }: { mode: string | null }) {
  if (!mode) return <Badge variant="gray">Unknown</Badge>
  if (mode === 'bob_led') {
    return (
      <Badge
        variant="blue"
        icon={<Zap size={12} style={{ color: '#2563EB' }} />}
        style={{ fontWeight: 700 }}
      >
        Bob-led
      </Badge>
    )
  }
  if (mode === 'collaborative') {
    return (
      <Badge
        variant="purple"
        icon={<Users size={12} style={{ color: '#7C3AED' }} />}
        style={{ fontWeight: 700 }}
      >
        Collaborative
      </Badge>
    )
  }
  if (mode === 'human_led') {
    return (
      <Badge
        variant="amber"
        icon={<User size={12} style={{ color: '#D97706' }} />}
        style={{ fontWeight: 700 }}
      >
        Human-led
      </Badge>
    )
  }
  return <Badge variant="gray">{mode}</Badge>
}

// ---------------------------------------------------------------------------
// Approval status badge
// ---------------------------------------------------------------------------

export function ApprovalBadge({ status }: { status: string }) {
  if (status === 'approved') {
    return (
      <Badge variant="green" icon={<CheckCircle2 size={12} />}>
        Approved
      </Badge>
    )
  }
  if (status === 'overridden') {
    return (
      <Badge variant="amber" icon={<AlertTriangle size={12} />}>
        Overridden
      </Badge>
    )
  }
  return (
    <Badge variant="gray" icon={<Clock size={12} />}>
      Pending
    </Badge>
  )
}

// ---------------------------------------------------------------------------
// Evidence confidence badge
// ---------------------------------------------------------------------------

export function ConfidenceBadge({ confidence }: { confidence: string }) {
  if (confidence === 'high') {
    return (
      <Badge variant="green" dot>
        High confidence
      </Badge>
    )
  }
  if (confidence === 'medium') {
    return (
      <Badge variant="blue" dot>
        Medium confidence
      </Badge>
    )
  }
  if (confidence === 'low') {
    return (
      <Badge variant="amber" dot>
        Low confidence
      </Badge>
    )
  }
  return <Badge variant="gray">No evidence</Badge>
}

// ---------------------------------------------------------------------------
// Source badge
// ---------------------------------------------------------------------------

export function SourceBadge({ source }: { source: string }) {
  if (source === 'sample') {
    return (
      <Badge
        variant="amber"
        style={{
          fontSize: '10px',
          fontWeight: 700,
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
          padding: '2px 7px',
        }}
      >
        Sample Data
      </Badge>
    )
  }
  if (source === 'jira') {
    return (
      <Badge
        variant="green"
        style={{
          fontSize: '10px',
          fontWeight: 700,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          padding: '2px 7px',
        }}
      >
        Jira
      </Badge>
    )
  }
  return <Badge variant="gray">{source}</Badge>
}

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------

interface CardProps {
  children: ReactNode
  className?: string
  padding?: 'sm' | 'md' | 'lg' | 'none'
  style?: React.CSSProperties
  onClick?: () => void
  hoverable?: boolean
}

const paddingMap: Record<'none' | 'sm' | 'md' | 'lg', string> = {
  none: '0px',
  sm: '12px 14px',
  md: '18px 20px',
  lg: '24px 28px',
}

export function Card({
  children,
  className = '',
  padding = 'md',
  style: styleProp = {},
  onClick,
  hoverable = false,
}: CardProps) {
  return (
    <div
      onClick={onClick}
      className={`card-base ${hoverable || onClick ? 'card-interactive' : ''} ${className}`}
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-sm)',
        padding: paddingMap[padding],
        position: 'relative',
        ...styleProp,
      }}
    >
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Metric Card
// ---------------------------------------------------------------------------

export interface MetricCardProps {
  title: string
  value: string | number
  subtext?: string
  icon?: ReactNode
  accentColor?: string
  badge?: ReactNode
}

export function MetricCard({
  title,
  value,
  subtext,
  icon,
  accentColor = 'var(--color-accent)',
  badge,
}: MetricCardProps) {
  return (
    <div
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        padding: '16px 18px',
        boxShadow: 'var(--shadow-xs)',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '3px',
          background: accentColor,
        }}
      />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span
          style={{
            fontSize: '12px',
            fontWeight: 600,
            color: 'var(--color-text-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {title}
        </span>
        {icon && (
          <div
            style={{
              color: accentColor,
              background: 'var(--color-surface-subtle)',
              borderRadius: '8px',
              padding: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {icon}
          </div>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '2px' }}>
        <span style={{ fontSize: '26px', fontWeight: 800, color: 'var(--color-text)', letterSpacing: '-0.02em', lineHeight: 1.1 }}>
          {value}
        </span>
        {badge}
      </div>
      {subtext && (
        <span style={{ fontSize: '12px', color: 'var(--color-text-faint)', lineHeight: 1.3 }}>
          {subtext}
        </span>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section heading
// ---------------------------------------------------------------------------

export function SectionHeading({
  children,
  className = '',
  style: styleProp,
}: {
  children: ReactNode
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <h3
      className={className}
      style={{
        fontSize: '11px',
        fontWeight: 700,
        letterSpacing: '0.07em',
        textTransform: 'uppercase',
        color: 'var(--color-text-muted)',
        marginBottom: '10px',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        ...styleProp,
      }}
    >
      {children}
    </h3>
  )
}

// ---------------------------------------------------------------------------
// Skeleton loader
// ---------------------------------------------------------------------------

export function Skeleton({
  width,
  height = 16,
  className = '',
  style: styleProp = {},
}: {
  width?: string | number
  height?: number | string
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <span
      className={className}
      style={{
        width: width ?? '100%',
        height,
        background: 'linear-gradient(90deg, var(--color-border) 0%, var(--color-surface-subtle) 50%, var(--color-border) 100%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s ease-in-out infinite',
        display: 'block',
        borderRadius: 'var(--radius-sm)',
        ...styleProp,
      }}
    />
  )
}

// ---------------------------------------------------------------------------
// Story queue row skeleton
// ---------------------------------------------------------------------------

export function StoryRowSkeleton() {
  return (
    <div
      style={{
        padding: '16px 20px',
        borderBottom: '1px solid var(--color-border-subtle)',
        display: 'flex',
        gap: '14px',
        alignItems: 'center',
      }}
    >
      <Skeleton width={70} height={18} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <Skeleton width="65%" height={16} />
        <div style={{ display: 'flex', gap: '8px' }}>
          <Skeleton width={50} height={14} />
          <Skeleton width={80} height={14} />
        </div>
      </div>
      <Skeleton width={80} height={20} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '56px 24px',
        textAlign: 'center',
        gap: '12px',
      }}
    >
      {icon && (
        <div
          style={{
            width: '56px',
            height: '56px',
            borderRadius: '50%',
            background: 'var(--color-accent-bg)',
            color: 'var(--color-accent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '4px',
            boxShadow: '0 0 0 8px var(--color-surface-subtle)',
          }}
        >
          {icon}
        </div>
      )}
      <p style={{ fontWeight: 700, color: 'var(--color-text)', fontSize: '16px', letterSpacing: '-0.01em' }}>
        {title}
      </p>
      {description && (
        <p style={{ fontSize: '13.5px', maxWidth: '380px', color: 'var(--color-text-muted)', lineHeight: 1.6 }}>
          {description}
        </p>
      )}
      {action && <div style={{ marginTop: '8px' }}>{action}</div>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Error banner
// ---------------------------------------------------------------------------

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string
  onRetry?: () => void
}) {
  return (
    <div
      role="alert"
      style={{
        background: 'var(--color-red-bg)',
        border: '1px solid var(--color-red-border)',
        borderRadius: 'var(--radius)',
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        fontSize: '13.5px',
        color: 'var(--color-red-text)',
        boxShadow: 'var(--shadow-xs)',
      }}
    >
      <XCircle size={18} style={{ color: 'var(--color-red)', flexShrink: 0, marginTop: '1px' }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <span style={{ fontWeight: 700, marginRight: '6px' }}>Error:</span>
        <span>{message}</span>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            flexShrink: 0,
            color: 'var(--color-red)',
            fontWeight: 700,
            textDecoration: 'underline',
            fontSize: '13px',
            cursor: 'pointer',
          }}
        >
          Retry
        </button>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Warning banner
// ---------------------------------------------------------------------------

export function WarningBanner({ message }: { message: string }) {
  return (
    <div
      style={{
        background: 'var(--color-amber-bg)',
        border: '1px solid var(--color-amber-border)',
        borderRadius: 'var(--radius)',
        padding: '12px 16px',
        fontSize: '13.5px',
        color: 'var(--color-amber-text)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        boxShadow: 'var(--shadow-xs)',
      }}
    >
      <AlertTriangle size={18} style={{ color: 'var(--color-amber)', flexShrink: 0, marginTop: '1px' }} />
      <div style={{ flex: 1 }}>
        <span style={{ fontWeight: 700, marginRight: '6px' }}>Warning:</span>
        {message}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sample data banner
// ---------------------------------------------------------------------------

export function SampleDataBanner() {
  return (
    <div
      role="status"
      style={{
        background: 'linear-gradient(90deg, #FFFBEB 0%, #FEF3C7 100%)',
        border: '1px solid var(--color-amber-border)',
        borderRadius: 'var(--radius)',
        padding: '10px 16px',
        fontSize: '12.5px',
        fontWeight: 600,
        color: '#92400E',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '8px',
        boxShadow: 'var(--shadow-xs)',
      }}
    >
      <Sparkles size={15} style={{ color: '#D97706' }} />
      <span>
        <strong>DEMO ENVIRONMENT</strong> — Displaying built-in PIE sample stories. Connect live Jira credentials to analyze real backlog stories.
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success'
export type ButtonSize = 'sm' | 'md' | 'lg'

export interface ButtonProps {
  children: ReactNode
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void
  variant?: ButtonVariant
  size?: ButtonSize
  disabled?: boolean
  loading?: boolean
  type?: 'button' | 'submit'
  className?: string
  style?: React.CSSProperties
  icon?: ReactNode
}

export function Button({
  children,
  onClick,
  variant = 'secondary',
  size = 'md',
  disabled,
  loading,
  type = 'button',
  className = '',
  style: styleProp = {},
  icon,
}: ButtonProps) {
  const sizeStyles: Record<ButtonSize, React.CSSProperties> = {
    sm: { padding: '5px 11px', fontSize: '12.5px', gap: '5px' },
    md: { padding: '8px 16px', fontSize: '13.5px', gap: '7px' },
    lg: { padding: '10px 20px', fontSize: '15px', gap: '8px' },
  }

  const variantClassMap: Record<ButtonVariant, string> = {
    primary: 'btn-primary-style',
    secondary: 'btn-secondary-style',
    ghost: 'btn-ghost-style',
    danger: 'btn-danger-style',
    success: 'badge-green',
  }

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`btn-base ${variantClassMap[variant]} ${className}`}
      style={{
        ...sizeStyles[size],
        ...styleProp,
      }}
    >
      {loading ? (
        <>
          <Loader2 size={size === 'sm' ? 12 : 14} style={{ animation: 'spin 1s linear infinite' }} />
          <span>Loading…</span>
        </>
      ) : (
        <>
          {icon}
          {children}
        </>
      )}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Divider
// ---------------------------------------------------------------------------

export function Divider({
  className = '',
  style: styleProp,
}: {
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <hr
      className={className}
      style={{
        border: 'none',
        borderTop: '1px solid var(--color-border)',
        margin: '12px 0',
        ...styleProp,
      }}
    />
  )
}

// ---------------------------------------------------------------------------
// Inline key-value pair
// ---------------------------------------------------------------------------

export function MetaRow({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div
      style={{
        display: 'flex',
        gap: '12px',
        alignItems: 'baseline',
        fontSize: '13px',
        padding: '3px 0',
      }}
    >
      <span
        style={{
          color: 'var(--color-text-muted)',
          flexShrink: 0,
          minWidth: '130px',
          fontWeight: 500,
        }}
      >
        {label}
      </span>
      <span style={{ color: 'var(--color-text)', flex: 1, minWidth: 0 }}>{children}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Progress Bar
// ---------------------------------------------------------------------------

export function ProgressBar({
  value,
  max = 100,
  color = 'var(--color-accent)',
  height = 6,
}: {
  value: number
  max?: number
  color?: string
  height?: number
}) {
  const percent = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <div
      style={{
        width: '100%',
        height: `${height}px`,
        background: 'var(--color-border)',
        borderRadius: '9999px',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          width: `${percent}%`,
          height: '100%',
          background: color,
          borderRadius: '9999px',
          transition: 'width 0.3s ease',
        }}
      />
    </div>
  )
}
