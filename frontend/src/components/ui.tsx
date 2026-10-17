import React from 'react'
import { clsx } from 'clsx'
import type { ReactNode } from 'react'

// ---------------------------------------------------------------------------
// Badge
// ---------------------------------------------------------------------------

type BadgeVariant =
  | 'default'
  | 'blue'
  | 'amber'
  | 'red'
  | 'green'
  | 'purple'
  | 'gray'

const badgeStyles: Record<BadgeVariant, string> = {
  default:
    'bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0]',
  blue:
    'bg-[#EFF6FF] text-[#1D4ED8] border border-[#BFDBFE]',
  amber:
    'bg-[#FFFBEB] text-[#B45309] border border-[#FCD34D]',
  red:
    'bg-[#FEF2F2] text-[#DC2626] border border-[#FCA5A5]',
  green:
    'bg-[#F0FDF4] text-[#15803D] border border-[#86EFAC]',
  purple:
    'bg-[#F5F3FF] text-[#6D28D9] border border-[#C4B5FD]',
  gray:
    'bg-[#F9FAFB] text-[#6B7280] border border-[#E5E7EB]',
}

interface BadgeProps {
  children: ReactNode
  variant?: BadgeVariant
  className?: string
}

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
        badgeStyles[variant],
        className,
      )}
    >
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
  const variant: BadgeVariant =
    p === 'highest' || p === 'critical'
      ? 'red'
      : p === 'high'
      ? 'amber'
      : p === 'medium'
      ? 'blue'
      : 'gray'
  return <Badge variant={variant}>{priority}</Badge>
}

// ---------------------------------------------------------------------------
// Mode badge
// ---------------------------------------------------------------------------

export function ModeBadge({ mode }: { mode: string | null }) {
  if (!mode) return <Badge variant="gray">Unknown</Badge>
  if (mode === 'bob_led')
    return <Badge variant="blue">Bob-led</Badge>
  if (mode === 'collaborative')
    return <Badge variant="purple">Collaborative</Badge>
  if (mode === 'human_led')
    return <Badge variant="amber">Human-led</Badge>
  return <Badge variant="gray">{mode}</Badge>
}

// ---------------------------------------------------------------------------
// Approval status badge
// ---------------------------------------------------------------------------

export function ApprovalBadge({ status }: { status: string }) {
  if (status === 'approved')
    return <Badge variant="green">Approved</Badge>
  if (status === 'overridden')
    return <Badge variant="amber">Overridden</Badge>
  return <Badge variant="gray">Pending</Badge>
}

// ---------------------------------------------------------------------------
// Evidence confidence badge
// ---------------------------------------------------------------------------

export function ConfidenceBadge({ confidence }: { confidence: string }) {
  if (confidence === 'high') return <Badge variant="green">High confidence</Badge>
  if (confidence === 'medium') return <Badge variant="blue">Medium confidence</Badge>
  if (confidence === 'low') return <Badge variant="amber">Low confidence</Badge>
  return <Badge variant="gray">No evidence</Badge>
}

// ---------------------------------------------------------------------------
// Source badge
// ---------------------------------------------------------------------------

export function SourceBadge({ source }: { source: string }) {
  if (source === 'sample')
    return (
      <Badge variant="amber" className="font-semibold tracking-wide uppercase text-[10px]">
        Sample Data
      </Badge>
    )
  if (source === 'jira')
    return <Badge variant="green">Jira</Badge>
  return <Badge variant="gray">{source}</Badge>
}

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------

interface CardProps {
  children: ReactNode
  className?: string
  padding?: 'sm' | 'md' | 'lg' | 'none'
}

const paddingMap = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-5',
}

export function Card({ children, className, padding = 'md' }: CardProps) {
  return (
    <div
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-sm)',
      }}
      className={clsx(paddingMap[padding], className)}
    >
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section heading
// ---------------------------------------------------------------------------

export function SectionHeading({
  children,
  className,
  style: styleProp,
}: {
  children: ReactNode
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <h3
      className={clsx(className)}
      style={{
        fontSize: '12px',
        fontWeight: 600,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        color: 'var(--color-text-muted)',
        marginBottom: '8px',
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

export function Skeleton({ width, height = 16, className }: {
  width?: string | number
  height?: number
  className?: string
}) {
  return (
    <span
      className={clsx('inline-block rounded', className)}
      style={{
        width: width ?? '100%',
        height,
        background: 'linear-gradient(90deg, #E5E7EB 0%, #F3F4F6 50%, #E5E7EB 100%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.4s ease-in-out infinite',
        display: 'block',
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
        padding: '12px 16px',
        borderBottom: '1px solid var(--color-border-subtle)',
        display: 'flex',
        gap: '12px',
        alignItems: 'center',
      }}
    >
      <Skeleton width={56} height={14} />
      <Skeleton height={14} />
      <Skeleton width={64} height={14} className="ml-auto flex-none" />
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
        padding: '48px 24px',
        textAlign: 'center',
        gap: '12px',
        color: 'var(--color-text-muted)',
      }}
    >
      {icon && (
        <div style={{ opacity: 0.4, marginBottom: '4px' }}>{icon}</div>
      )}
      <p style={{ fontWeight: 600, color: 'var(--color-text)', fontSize: '15px' }}>{title}</p>
      {description && <p style={{ fontSize: '13px', maxWidth: '320px' }}>{description}</p>}
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
        padding: '10px 14px',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
        fontSize: '13px',
        color: 'var(--color-red)',
      }}
    >
      <span style={{ fontWeight: 600, flexShrink: 0 }}>Error:</span>
      <span style={{ flex: 1, color: 'var(--color-text)' }}>{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            flexShrink: 0,
            color: 'var(--color-red)',
            fontWeight: 600,
            textDecoration: 'underline',
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
        padding: '10px 14px',
        fontSize: '13px',
        color: 'var(--color-text)',
      }}
    >
      <span style={{ fontWeight: 600, color: 'var(--color-amber)' }}>Warning: </span>
      {message}
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
        background: 'var(--color-amber-bg)',
        border: '1px solid var(--color-amber-border)',
        borderRadius: 'var(--radius)',
        padding: '8px 12px',
        fontSize: '12px',
        fontWeight: 600,
        color: '#92400E',
        textAlign: 'center',
        letterSpacing: '0.04em',
      }}
    >
      [SAMPLE DATA] — These stories are from the built-in sample dataset, not a live Jira instance.
    </div>
  )
}

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ButtonSize = 'sm' | 'md'

interface ButtonProps {
  children: ReactNode
  onClick?: () => void
  variant?: ButtonVariant
  size?: ButtonSize
  disabled?: boolean
  loading?: boolean
  type?: 'button' | 'submit'
  className?: string
}

export function Button({
  children,
  onClick,
  variant = 'secondary',
  size = 'md',
  disabled,
  loading,
  type = 'button',
  className,
}: ButtonProps) {
  const base: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    borderRadius: 'var(--radius)',
    fontWeight: 500,
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    opacity: disabled || loading ? 0.6 : 1,
    transition: 'background 0.1s, border-color 0.1s',
    whiteSpace: 'nowrap',
    ...(size === 'sm'
      ? { padding: '4px 10px', fontSize: '12px' }
      : { padding: '7px 14px', fontSize: '14px' }),
  }

  const variantStyle: React.CSSProperties =
    variant === 'primary'
      ? {
          background: 'var(--color-accent)',
          color: '#fff',
          border: '1px solid var(--color-accent)',
        }
      : variant === 'danger'
      ? {
          background: 'var(--color-red)',
          color: '#fff',
          border: '1px solid var(--color-red)',
        }
      : variant === 'ghost'
      ? {
          background: 'transparent',
          color: 'var(--color-text)',
          border: '1px solid transparent',
        }
      : {
          background: 'var(--color-surface)',
          color: 'var(--color-text)',
          border: '1px solid var(--color-border)',
        }

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={className}
      style={{ ...base, ...variantStyle }}
    >
      {loading ? 'Loading…' : children}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Divider
// ---------------------------------------------------------------------------

export function Divider({ className, style: styleProp }: { className?: string; style?: React.CSSProperties }) {
  return (
    <hr
      className={className}
      style={{ border: 'none', borderTop: '1px solid var(--color-border)', ...styleProp }}
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
    <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', fontSize: '13px' }}>
      <span style={{ color: 'var(--color-text-muted)', flexShrink: 0, minWidth: '120px' }}>
        {label}
      </span>
      <span style={{ color: 'var(--color-text)' }}>{children}</span>
    </div>
  )
}
