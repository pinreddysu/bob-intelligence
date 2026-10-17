import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Zap,
  Users,
  User,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  ExternalLink,
  GitPullRequest,
  History,
  ShieldAlert,
  HelpCircle,
  Info,
} from 'lucide-react'
import { AppShell } from '../components/AppShell'
import {
  Badge,
  ModeBadge,
  ApprovalBadge,
  ConfidenceBadge,
  SourceBadge,
  PriorityBadge,
  Card,
  SectionHeading,
  Skeleton,
  ErrorBanner,
  WarningBanner,
  Button,
  MetaRow,
  Divider,
} from '../components/ui'
import { ApprovalPanel } from '../components/ApprovalPanel'
import {
  getStory,
  createRecommendation,
  getRecommendation,
} from '../api/client'
import type { Story, Recommendation, EvidenceItem, RiskItem } from '../api/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function modeLabel(mode: string | null): string {
  if (mode === 'bob_led') return 'Bob-led'
  if (mode === 'collaborative') return 'Collaborative'
  if (mode === 'human_led') return 'Human-led'
  return mode ?? 'Unknown'
}

function modeDescription(mode: string | null): string {
  if (mode === 'bob_led')
    return 'Bob performs the implementation. The tech lead reviews output and verifies acceptance criteria before merging.'
  if (mode === 'collaborative')
    return 'Bob assists with implementation while a human provides active oversight and makes key decisions.'
  if (mode === 'human_led')
    return 'A human should lead this work. Evidence is insufficient, risk is too high, or Bob should not operate autonomously here.'
  return 'Execution mode not determined.'
}

function modeIcon(mode: string | null, size = 22) {
  if (mode === 'bob_led') return <Zap size={size} />
  if (mode === 'collaborative') return <Users size={size} />
  if (mode === 'human_led') return <User size={size} />
  return <HelpCircle size={size} />
}

function modeColor(mode: string | null): { bg: string; border: string; text: string; icon: string } {
  if (mode === 'bob_led')
    return { bg: '#EFF6FF', border: '#BFDBFE', text: '#1E40AF', icon: '#2563EB' }
  if (mode === 'collaborative')
    return { bg: '#F5F3FF', border: '#C4B5FD', text: '#5B21B6', icon: '#7C3AED' }
  if (mode === 'human_led')
    return { bg: '#FFFBEB', border: '#FCD34D', text: '#92400E', icon: '#D97706' }
  return { bg: '#F9FAFB', border: '#E5E7EB', text: '#374151', icon: '#6B7280' }
}

// ---------------------------------------------------------------------------
// Story context panel
// ---------------------------------------------------------------------------

function StoryContext({ story }: { story: Story }) {
  return (
    <Card>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontFamily: 'ui-monospace, monospace', fontSize: '13px', color: 'var(--color-text-muted)', fontWeight: 600 }}>
            {story.jira_key ?? story.id.slice(0, 8)}
          </span>
          <SourceBadge source={story.source} />
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          <PriorityBadge priority={story.priority} />
          {story.status && <Badge variant="gray">{story.status}</Badge>}
        </div>
      </div>

      <h2 style={{ fontSize: '17px', fontWeight: 700, marginBottom: '12px', lineHeight: 1.4 }}>
        {story.title}
      </h2>

      {story.description && (
        <div style={{ marginBottom: '14px' }}>
          <SectionHeading>Description</SectionHeading>
          <p style={{ fontSize: '13px', color: 'var(--color-text)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
            {story.description}
          </p>
        </div>
      )}

      {story.acceptance_criteria && (
        <div style={{ marginBottom: '14px' }}>
          <SectionHeading>Acceptance Criteria</SectionHeading>
          <p style={{ fontSize: '13px', color: 'var(--color-text)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
            {story.acceptance_criteria}
          </p>
        </div>
      )}

      {!story.description && !story.acceptance_criteria && (
        <p style={{ fontSize: '13px', color: 'var(--color-text-faint)', fontStyle: 'italic' }}>
          No description or acceptance criteria available from Jira.
        </p>
      )}

      <Divider style={{ margin: '12px 0' } as React.CSSProperties} />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {story.assignee && <MetaRow label="Assignee">{story.assignee}</MetaRow>}
        {story.story_points !== null && story.story_points !== undefined && (
          <MetaRow label="Story points">{story.story_points} (display only)</MetaRow>
        )}
        {story.labels && story.labels.length > 0 && (
          <MetaRow label="Labels">
            <span style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
              {(story.labels as string[]).map(l => (
                <Badge key={l} variant="gray">{l}</Badge>
              ))}
            </span>
          </MetaRow>
        )}
        {story.blockers && story.blockers.length > 0 && (
          <MetaRow label="Blockers">
            <span style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {(story.blockers as string[]).map((b, i) => (
                <span key={i} style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--color-red)', fontSize: '13px' }}>
                  <AlertTriangle size={12} />
                  {b}
                </span>
              ))}
            </span>
          </MetaRow>
        )}
        {story.linked_prs && story.linked_prs.length > 0 && (
          <MetaRow label="Linked PRs">
            <span style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {(story.linked_prs as string[]).map((pr, i) => (
                <a
                  key={i}
                  href={pr}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  <GitPullRequest size={12} />
                  {pr}
                  <ExternalLink size={10} style={{ opacity: 0.5 }} />
                </a>
              ))}
            </span>
          </MetaRow>
        )}
        <MetaRow label="Created">{formatDate(story.created_at)}</MetaRow>
      </div>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Mode hero
// ---------------------------------------------------------------------------

function ModeHero({ rec }: { rec: Recommendation }) {
  const colors = modeColor(rec.mode)

  return (
    <div
      style={{
        background: colors.bg,
        border: `2px solid ${colors.border}`,
        borderRadius: 'var(--radius-lg)',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{ color: colors.icon, flexShrink: 0 }}>
          {modeIcon(rec.mode, 28)}
        </div>
        <div>
          <p style={{ fontSize: '12px', color: colors.text, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', opacity: 0.7 }}>
            Recommended Execution Mode
          </p>
          <p style={{ fontSize: '22px', fontWeight: 800, color: colors.text, lineHeight: 1.2 }}>
            {modeLabel(rec.mode)}
          </p>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-end' }}>
          <ApprovalBadge status={rec.mode_approval_status} />
          <ConfidenceBadge confidence={rec.evidence_confidence} />
        </div>
      </div>

      <p style={{ fontSize: '13.5px', color: colors.text, opacity: 0.85, lineHeight: 1.6 }}>
        {modeDescription(rec.mode)}
      </p>

      {rec.mode_rationale && (
        <div style={{
          background: 'rgba(255,255,255,0.7)',
          borderRadius: 'var(--radius)',
          padding: '10px 12px',
          fontSize: '13px',
          color: 'var(--color-text)',
          lineHeight: 1.7,
        }}>
          <strong>Rationale: </strong>{rec.mode_rationale}
        </div>
      )}

      {rec.mode_approval_status === 'approved' && (
        <div style={{ display: 'flex', gap: '8px', fontSize: '12px', color: 'var(--color-green)', alignItems: 'center' }}>
          <CheckCircle2 size={13} />
          <span>Approved by <strong>{rec.mode_approved_by}</strong> on {formatDate(rec.mode_approved_at)}</span>
        </div>
      )}
      {rec.mode_approval_status === 'overridden' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px', color: 'var(--color-amber)' }}>
          <span style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <AlertTriangle size={13} />
            Overridden by <strong>{rec.mode_approved_by}</strong> on {formatDate(rec.mode_approved_at)}
          </span>
          {rec.mode_override_reason && (
            <span style={{ paddingLeft: '19px', color: 'var(--color-text-muted)' }}>
              Reason: {rec.mode_override_reason}
            </span>
          )}
        </div>
      )}

      {rec.uncertainty_note && (
        <div style={{
          background: 'rgba(255,255,255,0.6)',
          border: '1px solid rgba(0,0,0,0.08)',
          borderRadius: 'var(--radius)',
          padding: '8px 10px',
          fontSize: '12px',
          color: 'var(--color-text-muted)',
          display: 'flex',
          gap: '6px',
          alignItems: 'flex-start',
        }}>
          <Info size={12} style={{ flexShrink: 0, marginTop: '1px' }} />
          {rec.uncertainty_note}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Evidence list
// ---------------------------------------------------------------------------

function EvidenceList({ items }: { items: EvidenceItem[] }) {
  if (!items || items.length === 0) {
    return <p style={{ fontSize: '13px', color: 'var(--color-text-faint)', fontStyle: 'italic' }}>No evidence recorded.</p>
  }
  return (
    <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {items.map((item, i) => (
        <li key={i} style={{
          display: 'flex',
          gap: '8px',
          alignItems: 'flex-start',
          padding: '8px 10px',
          background: item.verified ? 'var(--color-green-bg)' : 'var(--color-bg)',
          border: `1px solid ${item.verified ? 'var(--color-green-border)' : 'var(--color-border)'}`,
          borderRadius: 'var(--radius)',
          fontSize: '13px',
        }}>
          <span style={{ flexShrink: 0, marginTop: '1px', color: item.verified ? 'var(--color-green)' : 'var(--color-text-faint)' }}>
            {item.verified ? <CheckCircle2 size={13} /> : <Clock size={13} />}
          </span>
          <span style={{ flex: 1 }}>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', fontWeight: 600, marginRight: '6px' }}>
              [{item.source}]
            </span>
            {item.description}
          </span>
          {!item.verified && (
            <Badge variant="amber" className="flex-none">unverified</Badge>
          )}
        </li>
      ))}
    </ul>
  )
}

// ---------------------------------------------------------------------------
// Risk list
// ---------------------------------------------------------------------------

function RiskList({ items }: { items: RiskItem[] }) {
  if (!items || items.length === 0) {
    return <p style={{ fontSize: '13px', color: 'var(--color-text-faint)', fontStyle: 'italic' }}>No risks identified.</p>
  }
  const severityIcon = (s: string) => {
    if (s === 'high') return <XCircle size={13} style={{ color: 'var(--color-red)' }} />
    if (s === 'medium') return <AlertTriangle size={13} style={{ color: 'var(--color-amber)' }} />
    return <Info size={13} style={{ color: 'var(--color-text-muted)' }} />
  }
  const severityBg = (s: string) => {
    if (s === 'high') return { bg: 'var(--color-red-bg)', border: 'var(--color-red-border)' }
    if (s === 'medium') return { bg: 'var(--color-amber-bg)', border: 'var(--color-amber-border)' }
    return { bg: 'var(--color-bg)', border: 'var(--color-border)' }
  }
  return (
    <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {items.map((item, i) => {
        const c = severityBg(item.severity)
        return (
          <li key={i} style={{
            display: 'flex',
            gap: '8px',
            alignItems: 'flex-start',
            padding: '8px 10px',
            background: c.bg,
            border: `1px solid ${c.border}`,
            borderRadius: 'var(--radius)',
            fontSize: '13px',
          }}>
            <span style={{ flexShrink: 0, marginTop: '1px' }}>{severityIcon(item.severity)}</span>
            <span style={{ flex: 1 }}>{item.description}</span>
            <Badge variant={item.severity === 'high' ? 'red' : item.severity === 'medium' ? 'amber' : 'gray'}>
              {item.severity}
            </Badge>
          </li>
        )
      })}
    </ul>
  )
}

// ---------------------------------------------------------------------------
// Readiness panel
// ---------------------------------------------------------------------------

function ReadinessPanel({ rec }: { rec: Recommendation }) {
  const r = rec.ticket_readiness

  if (!r) {
    return (
      <Card>
        <SectionHeading>Ticket Readiness</SectionHeading>
        <p style={{ fontSize: '13px', color: 'var(--color-text-faint)', fontStyle: 'italic' }}>
          Readiness assessment not available — no data was returned by the backend for this recommendation.
        </p>
      </Card>
    )
  }

  const statusColor = {
    ready: 'var(--color-green)',
    ready_with_gaps: 'var(--color-amber)',
    not_ready: 'var(--color-red)',
    not_assessed: 'var(--color-text-muted)',
  }[r.overall_status] ?? 'var(--color-text-muted)'

  const statusIcon = {
    ready: <CheckCircle2 size={14} />,
    ready_with_gaps: <AlertTriangle size={14} />,
    not_ready: <XCircle size={14} />,
    not_assessed: <Clock size={14} />,
  }[r.overall_status] ?? <Clock size={14} />

  return (
    <Card>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
        <SectionHeading style={{ margin: 0 } as React.CSSProperties}>Ticket Readiness</SectionHeading>
        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '13px', color: statusColor, fontWeight: 600 }}>
          {statusIcon}
          {r.overall_status.replace(/_/g, ' ')}
        </span>
        {r.llm_confidence && (
          <Badge variant={r.llm_confidence === 'high' ? 'green' : r.llm_confidence === 'medium' ? 'blue' : 'amber'}>
            {r.llm_confidence} confidence
          </Badge>
        )}
      </div>

      {r.summary && (
        <p style={{ fontSize: '13.5px', lineHeight: 1.7, marginBottom: '12px' }}>{r.summary}</p>
      )}

      {r.blocking_gaps && r.blocking_gaps.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <SectionHeading>Blocking Gaps</SectionHeading>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {(r.blocking_gaps as string[]).map((g, i) => (
              <li key={i} style={{
                display: 'flex', gap: '6px', alignItems: 'flex-start',
                fontSize: '13px', color: 'var(--color-red)',
                padding: '6px 8px',
                background: 'var(--color-red-bg)',
                border: '1px solid var(--color-red-border)',
                borderRadius: 'var(--radius-sm)',
              }}>
                <XCircle size={12} style={{ flexShrink: 0, marginTop: '2px' }} />
                {g}
              </li>
            ))}
          </ul>
        </div>
      )}

      {r.needed_context && r.needed_context.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <SectionHeading>Missing Context</SectionHeading>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {(r.needed_context as string[]).map((c, i) => (
              <li key={i} style={{ fontSize: '13px', color: 'var(--color-text)', padding: '5px 8px', background: 'var(--color-amber-bg)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-amber-border)' }}>
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(r.auto_resolvable_gaps > 0 || r.human_required_gaps > 0) && (
        <div style={{ display: 'flex', gap: '12px', fontSize: '13px' }}>
          {r.auto_resolvable_gaps > 0 && (
            <span style={{ color: 'var(--color-green)' }}>
              <CheckCircle2 size={12} style={{ display: 'inline', marginRight: '4px' }} />
              {r.auto_resolvable_gaps} auto-resolvable
            </span>
          )}
          {r.human_required_gaps > 0 && (
            <span style={{ color: 'var(--color-amber)' }}>
              <User size={12} style={{ display: 'inline', marginRight: '4px' }} />
              {r.human_required_gaps} require human input
            </span>
          )}
        </div>
      )}
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Evidence tabs
// ---------------------------------------------------------------------------

type EvidenceTab = 'historical' | 'prs' | 'risks' | 'uncertainty'

function EvidenceInspector({ rec }: { rec: Recommendation }) {
  const [tab, setTab] = useState<EvidenceTab>('historical')

  const tabs: { id: EvidenceTab; label: string; icon: React.ReactNode; count?: number }[] = [
    {
      id: 'historical',
      label: 'Historical Tickets',
      icon: <History size={13} />,
      count: rec.similar_tickets?.length,
    },
    {
      id: 'prs',
      label: 'Pull Requests',
      icon: <GitPullRequest size={13} />,
      count: rec.supporting_prs?.length,
    },
    {
      id: 'risks',
      label: 'Risks',
      icon: <ShieldAlert size={13} />,
      count: rec.mode_risks?.length,
    },
    {
      id: 'uncertainty',
      label: 'Uncertainty',
      icon: <HelpCircle size={13} />,
    },
  ]

  return (
    <Card padding="none">
      {/* Tab bar */}
      <div
        role="tablist"
        style={{
          display: 'flex',
          borderBottom: '1px solid var(--color-border)',
          overflowX: 'auto',
        }}
      >
        {tabs.map(t => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              padding: '10px 14px',
              fontSize: '13px',
              fontWeight: tab === t.id ? 600 : 400,
              color: tab === t.id ? 'var(--color-accent)' : 'var(--color-text-muted)',
              borderBottom: tab === t.id ? '2px solid var(--color-accent)' : '2px solid transparent',
              background: 'none',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              marginBottom: '-1px',
            }}
          >
            {t.icon}
            {t.label}
            {t.count !== undefined && t.count > 0 && (
              <span style={{
                background: tab === t.id ? 'var(--color-accent)' : 'var(--color-border)',
                color: tab === t.id ? '#fff' : 'var(--color-text-muted)',
                borderRadius: '10px',
                padding: '0 6px',
                fontSize: '11px',
                fontWeight: 600,
                minWidth: '18px',
                textAlign: 'center',
              }}>
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab panels */}
      <div style={{ padding: '16px' }} role="tabpanel">
        {tab === 'historical' && (
          <HistoricalTicketsPanel rec={rec} />
        )}
        {tab === 'prs' && (
          <PRsPanel rec={rec} />
        )}
        {tab === 'risks' && (
          <RisksPanel rec={rec} />
        )}
        {tab === 'uncertainty' && (
          <UncertaintyPanel rec={rec} />
        )}
      </div>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Historical tickets panel
// ---------------------------------------------------------------------------

function HistoricalTicketsPanel({ rec }: { rec: Recommendation }) {
  if (!rec.similar_tickets || rec.similar_tickets.length === 0) {
    return (
      <p style={{ fontSize: '13px', color: 'var(--color-text-faint)', fontStyle: 'italic' }}>
        No similar resolved tickets found. The recommendation is based solely on story structure signals.
      </p>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
        Similarity scores are TF-IDF cosine similarity based on story text — not semantic understanding.
        A high score indicates vocabulary overlap, not verified functional equivalence.
      </p>
      {rec.similar_tickets.map((t, i) => (
        <div key={i} style={{
          padding: '10px 12px',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius)',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{ fontFamily: 'ui-monospace, monospace', fontSize: '12px', fontWeight: 700, color: 'var(--color-text-muted)' }}>
              {t.jira_key}
            </span>
            <span style={{ fontSize: '13px', fontWeight: 500, flex: 1 }}>{t.title}</span>
          </div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
            <Badge variant="blue">
              {(t.similarity_score * 100).toFixed(0)}% similar
            </Badge>
            {t.mode_used && <ModeBadgeSmall mode={t.mode_used} />}
            {t.ac_met === true && <Badge variant="green">AC met</Badge>}
            {t.ac_met === false && <Badge variant="red">AC not met</Badge>}
            {t.ac_met === null && <Badge variant="gray">AC unknown</Badge>}
            {t.resolution && (
              <Badge variant="gray">{t.resolution}</Badge>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function ModeBadgeSmall({ mode }: { mode: string }) {
  return <ModeBadge mode={mode} />
}

// ---------------------------------------------------------------------------
// PRs panel
// ---------------------------------------------------------------------------

function PRsPanel({ rec }: { rec: Recommendation }) {
  if (!rec.supporting_prs || rec.supporting_prs.length === 0) {
    return (
      <p style={{ fontSize: '13px', color: 'var(--color-text-faint)', fontStyle: 'italic' }}>
        No related pull-request evidence available.
      </p>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {rec.pr_evidence_warnings && rec.pr_evidence_warnings.length > 0 && (
        <div style={{ marginBottom: '4px' }}>
          {rec.pr_evidence_warnings.map((w, i) => (
            <WarningBanner key={i} message={w} />
          ))}
        </div>
      )}
      <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
        A merged PR does not imply acceptance criteria were met. Test file detection is a heuristic, not a verified test run.
      </p>
      {rec.supporting_prs.map((pr, i) => (
        <div key={i} style={{
          padding: '10px 12px',
          border: `1px solid ${pr.source_warning ? 'var(--color-amber-border)' : 'var(--color-border)'}`,
          background: pr.source_warning ? 'var(--color-amber-bg)' : 'var(--color-surface)',
          borderRadius: 'var(--radius)',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
            <GitPullRequest size={14} style={{ color: 'var(--color-text-muted)', marginTop: '2px', flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              {pr.title ? (
                <p style={{ fontSize: '13px', fontWeight: 500 }}>{pr.title}</p>
              ) : null}
              <a
                href={pr.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: '12px', color: 'var(--color-accent)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}
              >
                {pr.url}
                <ExternalLink size={10} style={{ display: 'inline', marginLeft: '4px', opacity: 0.5 }} />
              </a>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {pr.merged === true && <Badge variant="green">Merged</Badge>}
            {pr.merged === false && <Badge variant="red">Not merged</Badge>}
            {pr.merged === null && <Badge variant="gray">Merge unknown</Badge>}
            {pr.state && <Badge variant="gray">{pr.state}</Badge>}
            {pr.test_files_present === true && (
              <Badge variant="blue">Test files detected (heuristic)</Badge>
            )}
            {pr.was_reverted === true && (
              <Badge variant="red">Revert signal detected</Badge>
            )}
            {!pr.verified && (
              <Badge variant="amber">Unverified</Badge>
            )}
          </div>
          {pr.diff_summary && (
            <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', lineHeight: 1.6 }}>
              <strong>LLM summary:</strong> {pr.diff_summary}
            </p>
          )}
          {pr.files_changed && pr.files_changed.length > 0 && (
            <details>
              <summary style={{ fontSize: '12px', cursor: 'pointer', color: 'var(--color-text-muted)' }}>
                {pr.files_changed.length} file{pr.files_changed.length !== 1 ? 's' : ''} changed
              </summary>
              <ul style={{ marginTop: '4px', paddingLeft: '16px', fontSize: '12px', color: 'var(--color-text-muted)', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                {(pr.files_changed as string[]).map((f, j) => <li key={j}>{f}</li>)}
              </ul>
            </details>
          )}
          {pr.source_warning && (
            <p style={{ fontSize: '11px', color: 'var(--color-amber)', fontStyle: 'italic' }}>
              Warning: {pr.source_warning}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Risks panel
// ---------------------------------------------------------------------------

function RisksPanel({ rec }: { rec: Recommendation }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <SectionHeading>Risks</SectionHeading>
        <RiskList items={rec.mode_risks} />
      </div>
      {rec.mode_counterevidence && rec.mode_counterevidence.length > 0 && (
        <div>
          <SectionHeading>Counterevidence</SectionHeading>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '5px' }}>
            {rec.mode_counterevidence.map((item, i) => (
              <li key={i} style={{
                padding: '7px 10px',
                background: 'var(--color-amber-bg)',
                border: '1px solid var(--color-amber-border)',
                borderRadius: 'var(--radius)',
                fontSize: '13px',
              }}>
                {item.description}
              </li>
            ))}
          </ul>
        </div>
      )}
      {rec.code_analysis_notes && (
        <div>
          <SectionHeading>Code Analysis Notes</SectionHeading>
          <p style={{ fontSize: '13px', lineHeight: 1.7, color: 'var(--color-text)' }}>
            {rec.code_analysis_notes}
          </p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Uncertainty panel
// ---------------------------------------------------------------------------

function UncertaintyPanel({ rec }: { rec: Recommendation }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {rec.uncertainty_note ? (
        <div style={{
          padding: '10px 12px',
          background: 'var(--color-amber-bg)',
          border: '1px solid var(--color-amber-border)',
          borderRadius: 'var(--radius)',
          fontSize: '13px',
          lineHeight: 1.7,
        }}>
          <p style={{ fontWeight: 600, marginBottom: '4px', color: 'var(--color-amber)' }}>Uncertainty Note</p>
          {rec.uncertainty_note}
        </div>
      ) : (
        <p style={{ fontSize: '13px', color: 'var(--color-text-faint)', fontStyle: 'italic' }}>No uncertainty note recorded for this recommendation.</p>
      )}
      <div>
        <SectionHeading>Priority Evidence</SectionHeading>
        <EvidenceList items={rec.priority_evidence as EvidenceItem[]} />
      </div>
      <div>
        <SectionHeading>Mode Evidence</SectionHeading>
        <EvidenceList items={rec.mode_evidence as EvidenceItem[]} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function RecommendationView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [story, setStory] = useState<Story | null>(null)
  const [rec, setRec] = useState<Recommendation | null>(null)
  const [storyLoading, setStoryLoading] = useState(true)
  const [recLoading, setRecLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [storyError, setStoryError] = useState<string | null>(null)
  const [recError, setRecError] = useState<string | null>(null)
  const [genError, setGenError] = useState<string | null>(null)

  // Load story
  useEffect(() => {
    if (!id) return
    setStoryLoading(true)
    setStoryError(null)
    getStory(id)
      .then(s => setStory(s))
      .catch(e => setStoryError(String(e)))
      .finally(() => setStoryLoading(false))
  }, [id])

  // Attempt to find existing recommendation by generating (POST is idempotent in terms of
  // superseding — we probe the backend here). Actually we just show Generate button.

  const handleGenerate = useCallback(async () => {
    if (!id) return
    setGenerating(true)
    setGenError(null)
    try {
      const result = await createRecommendation(id)
      setRec(result)
    } catch (e) {
      setGenError(String(e))
    } finally {
      setGenerating(false)
    }
  }, [id])

  const handleRefreshRec = useCallback(async () => {
    if (!rec) return
    setRecLoading(true)
    setRecError(null)
    try {
      const result = await getRecommendation(rec.id)
      setRec(result)
    } catch (e) {
      setRecError(String(e))
    } finally {
      setRecLoading(false)
    }
  }, [rec])

  const handleApprovalUpdate = useCallback((updated: Recommendation) => {
    setRec(updated)
  }, [])

  const subtitle = story ? `${story.jira_key ?? story.id.slice(0, 8)} — ${story.title}` : ''

  return (
    <AppShell title="Story Detail" subtitle={subtitle}>
      {/* Back button */}
      <button
        onClick={() => navigate('/')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontSize: '13px',
          color: 'var(--color-text-muted)',
          marginBottom: '16px',
          cursor: 'pointer',
          background: 'none',
          border: 'none',
          padding: 0,
        }}
      >
        <ArrowLeft size={14} />
        Back to Story Queue
      </button>

      {storyLoading ? (
        <Card>
          <Skeleton height={20} width="40%" className="mb-3" />
          <Skeleton height={14} className="mb-2" />
          <Skeleton height={14} className="mb-2" />
          <Skeleton height={14} width="60%" />
        </Card>
      ) : storyError ? (
        <ErrorBanner message={storyError} />
      ) : story ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Story context */}
          <StoryContext story={story} />

          {/* Recommendation section */}
          {!rec && !generating && !genError && (
            <Card>
              <div style={{ textAlign: 'center', padding: '20px 0' }}>
                <p style={{ color: 'var(--color-text-muted)', marginBottom: '14px', fontSize: '14px' }}>
                  No recommendation generated yet for this story.
                </p>
                <Button variant="primary" onClick={handleGenerate}>
                  <Zap size={14} />
                  Generate Recommendation
                </Button>
              </div>
            </Card>
          )}

          {generating && (
            <Card>
              <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--color-text-muted)', fontSize: '14px' }}>
                Generating recommendation…
              </div>
            </Card>
          )}

          {genError && (
            <ErrorBanner message={genError} onRetry={handleGenerate} />
          )}

          {rec && (
            <>
              {/* Status banner for superseded */}
              {rec.status === 'superseded' && (
                <WarningBanner message="This recommendation has been superseded by a newer recommendation for this story." />
              )}

              {/* Mode hero */}
              <ModeHero rec={rec} />

              {/* Priority info */}
              {(rec.priority_rank !== null || rec.priority_rationale) && (
                <Card>
                  <SectionHeading>Priority Ranking</SectionHeading>
                  <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                    {rec.priority_rank !== null && (
                      <div style={{ textAlign: 'center', background: 'var(--color-accent-bg)', border: '1px solid #BFDBFE', borderRadius: 'var(--radius)', padding: '8px 16px' }}>
                        <p style={{ fontSize: '22px', fontWeight: 800, color: 'var(--color-accent)' }}>#{rec.priority_rank}</p>
                        <p style={{ fontSize: '11px', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Priority rank</p>
                      </div>
                    )}
                    {rec.priority_rationale && (
                      <p style={{ fontSize: '13px', color: 'var(--color-text)', lineHeight: 1.7, flex: 1 }}>
                        {rec.priority_rationale}
                      </p>
                    )}
                  </div>
                </Card>
              )}

              {/* Readiness */}
              <ReadinessPanel rec={rec} />

              {/* Evidence inspector */}
              <EvidenceInspector rec={rec} />

              {/* Approval controls */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <SectionHeading style={{ margin: 0 } as React.CSSProperties}>Decision Control</SectionHeading>
                {recLoading ? (
                  <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>Refreshing…</span>
                ) : (
                  <button
                    onClick={handleRefreshRec}
                    style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: 'var(--color-text-muted)', cursor: 'pointer', background: 'none', border: 'none' }}
                  >
                    <RefreshCw size={12} />
                    Refresh
                  </button>
                )}
              </div>
              {recError && <ErrorBanner message={recError} onRetry={handleRefreshRec} />}
              <ApprovalPanel rec={rec} onUpdate={handleApprovalUpdate} />

              {/* Regenerate */}
              <div style={{ textAlign: 'right' }}>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleGenerate}
                  loading={generating}
                >
                  <RefreshCw size={12} />
                  Regenerate Recommendation
                </Button>
                <p style={{ fontSize: '11px', color: 'var(--color-text-faint)', marginTop: '4px' }}>
                  Regenerating will supersede the current recommendation.
                  {rec.mode_approval_status !== 'pending' && ' The current approval status will not be transferred.'}
                </p>
              </div>
            </>
          )}
        </div>
      ) : null}
    </AppShell>
  )
}
