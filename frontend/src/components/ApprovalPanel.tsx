/**
 * ApprovalPanel — Tech Lead approval and override controls.
 *
 * Uses the exact API schemas from PATCH /api/recommendations/{id}/mode-approve
 * and PATCH /api/recommendations/{id}/mode-override.
 *
 * Design rules enforced:
 * - approved_by is required (min_length=1) — we do not imply it's authenticated.
 * - override_reason is required for override.
 * - mode is optional on override; must be one of the three valid values.
 * - Submission is disabled while a request is in progress.
 * - UI only updates after the server confirms success.
 * - API validation errors are displayed verbatim.
 */

import React, { useState, useCallback } from 'react'
import {
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  UserCheck,
  CornerDownRight,
  Sparkles,
} from 'lucide-react'
import { Card, SectionHeading, Button, ErrorBanner, ModeBadge, ApprovalBadge } from './ui'
import { approveMode, overrideMode as overrideModeApi } from '../api/client'
import type { Recommendation, ExecutionMode } from '../api/types'

const VALID_MODES: ExecutionMode[] = ['bob_led', 'collaborative', 'human_led']

const MODE_LABELS: Record<ExecutionMode, string> = {
  bob_led: 'Bob-led (Autonomous)',
  collaborative: 'Collaborative (Pairing)',
  human_led: 'Human-led (Manual)',
}

interface ApprovalPanelProps {
  rec: Recommendation
  onUpdate: (updated: Recommendation) => void
}

export function ApprovalPanel({ rec, onUpdate }: ApprovalPanelProps) {
  const [approveBy, setApproveBy] = useState('')
  const [overrideBy, setOverrideBy] = useState('')
  const [overrideReason, setOverrideReason] = useState('')
  const [selectedOverrideMode, setSelectedOverrideMode] = useState<ExecutionMode | ''>('')
  const [showOverride, setShowOverride] = useState(false)
  const [loading, setLoading] = useState<'approve' | 'override' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)

  const handleApprove = useCallback(async () => {
    if (!approveBy.trim()) return
    setLoading('approve')
    setError(null)
    try {
      const updated = await approveMode(rec.id, {
        approved_by: approveBy.trim(),
      })
      setSubmitted(true)
      onUpdate(updated)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(null)
    }
  }, [rec.id, approveBy, onUpdate])

  const handleOverride = useCallback(async () => {
    if (!overrideBy.trim() || !overrideReason.trim()) return
    setLoading('override')
    setError(null)
    try {
      const updated = await overrideModeApi(rec.id, {
        approved_by: overrideBy.trim(),
        override_reason: overrideReason.trim(),
        mode: selectedOverrideMode || undefined,
      })
      setSubmitted(true)
      onUpdate(updated)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(null)
    }
  }, [rec.id, overrideBy, overrideReason, selectedOverrideMode, onUpdate])

  // Already decided
  if (rec.mode_approval_status === 'approved' || rec.mode_approval_status === 'overridden') {
    const isApproved = rec.mode_approval_status === 'approved'

    return (
      <Card
        padding="md"
        style={{
          borderLeft: `4px solid ${isApproved ? 'var(--color-green)' : 'var(--color-amber)'}`,
          background: isApproved
            ? 'linear-gradient(180deg, var(--color-green-bg) 0%, var(--color-surface) 100%)'
            : 'linear-gradient(180deg, var(--color-amber-bg) 0%, var(--color-surface) 100%)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
          <div
            style={{
              width: '38px',
              height: '38px',
              borderRadius: '50%',
              background: isApproved ? 'var(--color-green-bg)' : 'var(--color-amber-bg)',
              color: isApproved ? 'var(--color-green)' : 'var(--color-amber)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              boxShadow: 'var(--shadow-xs)',
              border: `1px solid ${isApproved ? 'var(--color-green-border)' : 'var(--color-amber-border)'}`,
            }}
          >
            {isApproved ? <ShieldCheck size={20} /> : <AlertTriangle size={20} />}
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
              <span
                style={{
                  fontSize: '14.5px',
                  fontWeight: 700,
                  color: 'var(--color-text)',
                  letterSpacing: '-0.01em',
                }}
              >
                {isApproved ? 'Execution Mode Approved' : 'Execution Mode Overridden'}
              </span>
              <ApprovalBadge status={rec.mode_approval_status} />
              <ModeBadge mode={rec.mode} />
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '13px',
                color: 'var(--color-text-secondary)',
                marginTop: '6px',
              }}
            >
              <UserCheck size={14} style={{ color: 'var(--color-text-muted)' }} />
              <span>
                Signed by <strong>{rec.mode_approved_by}</strong>
                {rec.mode_approved_at && (
                  <>
                    {' '}
                    on{' '}
                    {new Date(rec.mode_approved_at).toLocaleString(undefined, {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </>
                )}
              </span>
            </div>

            {rec.mode_override_reason && (
              <div
                style={{
                  marginTop: '10px',
                  padding: '8px 12px',
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius)',
                  fontSize: '13px',
                  color: 'var(--color-text)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '8px',
                }}
              >
                <CornerDownRight size={14} style={{ color: 'var(--color-amber)', flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <strong style={{ color: 'var(--color-amber-text)' }}>Override Reason: </strong>
                  <span>{rec.mode_override_reason}</span>
                </div>
              </div>
            )}

            <p style={{ fontSize: '11px', color: 'var(--color-text-faint)', marginTop: '10px' }}>
              Sign-off identity is recorded as entered for audit trail.
            </p>
          </div>
        </div>
      </Card>
    )
  }

  // Pending — show decision controls
  return (
    <Card padding="lg">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <SectionHeading style={{ margin: 0 } as React.CSSProperties}>
          Tech Lead Sign-off Console
        </SectionHeading>
        <span
          style={{
            fontSize: '11.5px',
            color: 'var(--color-amber-text)',
            background: 'var(--color-amber-bg)',
            border: '1px solid var(--color-amber-border)',
            borderRadius: '9999px',
            padding: '2px 8px',
            fontWeight: 600,
          }}
        >
          Decision Required
        </span>
      </div>

      <p style={{ fontSize: '13px', color: 'var(--color-text-muted)', marginBottom: '16px', lineHeight: 1.6 }}>
        As Tech Lead, confirm whether Bob should execute this story autonomously, pair with human supervision, or hand off entirely. Enter your identifier to approve or record an override.
      </p>

      {error && (
        <div style={{ marginBottom: '14px' }}>
          <ErrorBanner message={error} />
        </div>
      )}

      {submitted && (
        <div
          style={{
            marginBottom: '14px',
            padding: '10px 14px',
            background: 'var(--color-green-bg)',
            border: '1px solid var(--color-green-border)',
            borderRadius: 'var(--radius)',
            fontSize: '13px',
            color: 'var(--color-green-text)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <CheckCircle2 size={16} />
          <span>Decision recorded successfully.</span>
        </div>
      )}

      {/* Approve form */}
      <div
        style={{
          background: 'var(--color-surface-subtle)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius)',
          padding: '14px 16px',
          marginBottom: '14px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
          <Sparkles size={14} style={{ color: 'var(--color-accent)' }} />
          <span style={{ fontSize: '13.5px', fontWeight: 600, color: 'var(--color-text)' }}>
            Approve Recommended Mode:
          </span>
          <ModeBadge mode={rec.mode} />
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '220px' }}>
            <input
              type="text"
              value={approveBy}
              onChange={e => setApproveBy(e.target.value)}
              placeholder="Your name or handle (e.g. alice.chen)"
              aria-label="Approver identity"
              disabled={loading !== null}
              className="input-base"
              style={{ width: '100%' }}
              onKeyDown={e => e.key === 'Enter' && handleApprove()}
            />
          </div>
          <Button
            variant="primary"
            onClick={handleApprove}
            disabled={!approveBy.trim() || loading !== null}
            loading={loading === 'approve'}
            icon={<CheckCircle2 size={14} />}
          >
            Approve Recommendation
          </Button>
        </div>
      </div>

      {/* Override toggle */}
      <button
        onClick={() => setShowOverride(v => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontSize: '13px',
          color: 'var(--color-amber-hover)',
          cursor: 'pointer',
          background: 'none',
          border: 'none',
          padding: '4px 0',
          fontWeight: 600,
        }}
      >
        {showOverride ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        <span>Disapprove or override recommended mode</span>
      </button>

      {/* Override form */}
      {showOverride && (
        <div
          style={{
            marginTop: '12px',
            padding: '16px',
            background: 'var(--color-amber-bg)',
            border: '1px solid var(--color-amber-border)',
            borderRadius: 'var(--radius)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          <div>
            <p style={{ fontSize: '13.5px', color: 'var(--color-text)', fontWeight: 700 }}>
              Override Execution Mode
            </p>
            <p style={{ fontSize: '12.5px', color: 'var(--color-amber-text)', lineHeight: 1.5, marginTop: '2px' }}>
              Override when you disagree with the recommended autonomy level. Your name and reason will be permanently recorded in the recommendation history.
            </p>
          </div>

          <div>
            <label
              style={{
                display: 'block',
                fontSize: '12px',
                fontWeight: 600,
                color: 'var(--color-text-secondary)',
                marginBottom: '4px',
              }}
            >
              Your Name / ID (required)
            </label>
            <input
              type="text"
              value={overrideBy}
              onChange={e => setOverrideBy(e.target.value)}
              placeholder="e.g. alice.chen"
              aria-label="Override approver identity"
              disabled={loading !== null}
              className="input-base"
              style={{ width: '100%', background: 'var(--color-input-bg)' }}
            />
          </div>

          <div>
            <label
              style={{
                display: 'block',
                fontSize: '12px',
                fontWeight: 600,
                color: 'var(--color-text-secondary)',
                marginBottom: '4px',
              }}
            >
              New Execution Mode (optional)
            </label>
            <select
              value={selectedOverrideMode}
              onChange={e => setSelectedOverrideMode(e.target.value as ExecutionMode | '')}
              disabled={loading !== null}
              aria-label="Override mode selection"
              className="input-base"
              style={{ width: '100%', background: 'var(--color-input-bg)' }}
            >
              <option value="">Keep current mode ({rec.mode ?? 'none'})</option>
              {VALID_MODES.map(m => (
                <option key={m} value={m}>
                  {MODE_LABELS[m]}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              style={{
                display: 'block',
                fontSize: '12px',
                fontWeight: 600,
                color: 'var(--color-text-secondary)',
                marginBottom: '4px',
              }}
            >
              Override Reason (required)
            </label>
            <textarea
              value={overrideReason}
              onChange={e => setOverrideReason(e.target.value)}
              placeholder="Explain why you are modifying the recommended mode (e.g. complex database migration requires senior human oversight)…"
              aria-label="Override reason"
              disabled={loading !== null}
              rows={3}
              className="input-base"
              style={{
                width: '100%',
                resize: 'vertical',
                fontFamily: 'inherit',
                background: 'var(--color-input-bg)',
              }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
            <Button
              variant="danger"
              onClick={handleOverride}
              disabled={!overrideBy.trim() || !overrideReason.trim() || loading !== null}
              loading={loading === 'override'}
              icon={<AlertTriangle size={14} />}
            >
              Record Override
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}
