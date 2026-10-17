/**
 * ApprovalPanel — tech lead approval and override controls.
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
import { CheckCircle2, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react'
import { Card, SectionHeading, Button, ErrorBanner, ModeBadge, ApprovalBadge } from './ui'
import { approveMode, overrideMode as overrideModeApi } from '../api/client'
import type { Recommendation, ExecutionMode } from '../api/types'

const VALID_MODES: ExecutionMode[] = ['bob_led', 'collaborative', 'human_led']

const MODE_LABELS: Record<ExecutionMode, string> = {
  bob_led: 'Bob-led',
  collaborative: 'Collaborative',
  human_led: 'Human-led',
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
    return (
      <Card>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ color: rec.mode_approval_status === 'approved' ? 'var(--color-green)' : 'var(--color-amber)' }}>
            {rec.mode_approval_status === 'approved'
              ? <CheckCircle2 size={18} />
              : <AlertTriangle size={18} />
            }
          </div>
          <div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <SectionHeading style={{ margin: 0 } as React.CSSProperties}>Decision Recorded</SectionHeading>
              <ApprovalBadge status={rec.mode_approval_status} />
              <ModeBadge mode={rec.mode} />
            </div>
            <p style={{ fontSize: '13px', color: 'var(--color-text-muted)', marginTop: '4px' }}>
              {rec.mode_approval_status === 'approved'
                ? `Approved by ${rec.mode_approved_by}`
                : `Overridden by ${rec.mode_approved_by}`
              }
              {rec.mode_approved_at && (
                <> on {new Date(rec.mode_approved_at).toLocaleString(undefined, {
                  year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
                })}</>
              )}
            </p>
            {rec.mode_override_reason && (
              <p style={{ fontSize: '13px', color: 'var(--color-text)', marginTop: '4px' }}>
                <strong>Override reason:</strong> {rec.mode_override_reason}
              </p>
            )}
          </div>
        </div>

        <p style={{ fontSize: '11px', color: 'var(--color-text-faint)', marginTop: '10px', fontStyle: 'italic' }}>
          Note: Identity is not authenticated. The approver name is recorded as entered.
        </p>
      </Card>
    )
  }

  // Pending — show decision controls
  return (
    <Card>
      <SectionHeading>Approve or Override Execution Mode</SectionHeading>

      <p style={{ fontSize: '13px', color: 'var(--color-text-muted)', marginBottom: '16px', lineHeight: 1.6 }}>
        The tech lead retains full control over the execution-mode decision.
        Approving records your identity against the current recommendation.
        Identity is not authenticated — do not treat approval as a security control.
      </p>

      {error && (
        <div style={{ marginBottom: '14px' }}>
          <ErrorBanner message={error} />
        </div>
      )}

      {submitted && (
        <div style={{ marginBottom: '14px', padding: '10px 12px', background: 'var(--color-green-bg)', border: '1px solid var(--color-green-border)', borderRadius: 'var(--radius)', fontSize: '13px', color: 'var(--color-green)' }}>
          Decision recorded successfully.
        </div>
      )}

      {/* Approve form */}
      <div style={{ marginBottom: '16px' }}>
        <p style={{ fontSize: '13px', fontWeight: 600, marginBottom: '8px' }}>
          Approve recommended mode: <ModeBadge mode={rec.mode} />
        </p>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '200px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
              Your name / ID (required)
            </label>
            <input
              type="text"
              value={approveBy}
              onChange={e => setApproveBy(e.target.value)}
              placeholder="e.g. alice.chen"
              aria-label="Approver identity"
              disabled={loading !== null}
              style={{
                width: '100%',
                padding: '7px 10px',
                borderRadius: 'var(--radius)',
                border: '1px solid var(--color-border)',
                fontSize: '13px',
              }}
            />
          </div>
          <Button
            variant="primary"
            onClick={handleApprove}
            disabled={!approveBy.trim() || loading !== null}
            loading={loading === 'approve'}
          >
            <CheckCircle2 size={14} />
            Approve Mode
          </Button>
        </div>
      </div>

      {/* Override toggle */}
      <button
        onClick={() => setShowOverride(v => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '5px',
          fontSize: '13px',
          color: 'var(--color-amber)',
          cursor: 'pointer',
          background: 'none',
          border: 'none',
          padding: '4px 0',
          fontWeight: 500,
        }}
      >
        {showOverride ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        Override recommendation
      </button>

      {/* Override form */}
      {showOverride && (
        <div style={{
          marginTop: '12px',
          padding: '14px',
          background: 'var(--color-amber-bg)',
          border: '1px solid var(--color-amber-border)',
          borderRadius: 'var(--radius)',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
        }}>
          <p style={{ fontSize: '13px', color: 'var(--color-text)', fontWeight: 600 }}>
            Override Recommendation
          </p>
          <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', lineHeight: 1.6 }}>
            Override when you disagree with the recommended mode.
            Both your identity and reason are required and will be permanently recorded.
          </p>

          <div>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
              Your name / ID (required)
            </label>
            <input
              type="text"
              value={overrideBy}
              onChange={e => setOverrideBy(e.target.value)}
              placeholder="e.g. alice.chen"
              aria-label="Override approver identity"
              disabled={loading !== null}
              style={{
                width: '100%',
                padding: '7px 10px',
                borderRadius: 'var(--radius)',
                border: '1px solid var(--color-border)',
                fontSize: '13px',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
              Override reason (required)
            </label>
            <textarea
              value={overrideReason}
              onChange={e => setOverrideReason(e.target.value)}
              placeholder="Explain why you are overriding the recommended mode…"
              aria-label="Override reason"
              disabled={loading !== null}
              rows={3}
              style={{
                width: '100%',
                padding: '7px 10px',
                borderRadius: 'var(--radius)',
                border: '1px solid var(--color-border)',
                fontSize: '13px',
                resize: 'vertical',
                fontFamily: 'inherit',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
              New execution mode (optional — leave blank to keep current)
            </label>
            <select
              value={selectedOverrideMode}
              onChange={e => setSelectedOverrideMode(e.target.value as ExecutionMode | '')}
              disabled={loading !== null}
              aria-label="Override mode selection"
              style={{
                padding: '7px 10px',
                borderRadius: 'var(--radius)',
                border: '1px solid var(--color-border)',
                fontSize: '13px',
                background: 'var(--color-surface)',
                width: '100%',
              }}
            >
              <option value="">Keep recommended mode ({rec.mode})</option>
              {VALID_MODES.map(m => (
                <option key={m} value={m}>{MODE_LABELS[m]}</option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="danger"
              onClick={handleOverride}
              disabled={!overrideBy.trim() || !overrideReason.trim() || loading !== null}
              loading={loading === 'override'}
            >
              <AlertTriangle size={14} />
              Record Override
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}
