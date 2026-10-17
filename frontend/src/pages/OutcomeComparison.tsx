import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { AppShell } from '../components/AppShell'
import { Card } from '../components/ui'

/**
 * Outcomes & Comparison — Milestone 5 (not yet implemented).
 * The backend endpoint POST /api/outcomes is gated with a 409.
 */
export default function OutcomeComparison() {
  const navigate = useNavigate()
  return (
    <AppShell title="Outcomes & Comparison" subtitle="Milestone 5 — not yet implemented">
      <button
        onClick={() => navigate('/')}
        style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: 'var(--color-text-muted)', marginBottom: '16px', cursor: 'pointer', background: 'none', border: 'none', padding: 0 }}
      >
        <ArrowLeft size={14} />
        Back to Story Queue
      </button>
      <Card>
        <p style={{ fontSize: '14px', fontWeight: 600, marginBottom: '8px' }}>Outcome Recording &amp; Comparison — Planned</p>
        <p style={{ fontSize: '13px', color: 'var(--color-text-muted)', lineHeight: 1.7 }}>
          This feature (Milestone 5) is not yet implemented in the backend. The
          <code style={{ fontFamily: 'ui-monospace, monospace', margin: '0 4px', fontSize: '12px' }}>POST /api/outcomes</code>
          endpoint is gated behind a 409 response until the story&rsquo;s recommendation is approved.
          Full implementation is deferred to a future milestone.
        </p>
      </Card>
    </AppShell>
  )
}
