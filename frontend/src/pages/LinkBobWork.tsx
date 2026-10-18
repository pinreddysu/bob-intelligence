import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Cpu, CheckCircle2, Lock, Clock } from 'lucide-react'
import { AppShell } from '../components/AppShell'
import { Card, SectionHeading, Badge, Button } from '../components/ui'

/**
 * Bob Sessions — Future Feature Preview.
 * Autonomous execution session linking.
 */
export default function LinkBobWork() {
  const navigate = useNavigate()

  return (
    <AppShell
      title="Bob Autonomous Sessions"
      subtitle="Future Feature Roadmap — Autonomous session linking and execution orchestration"
    >
      <button
        onClick={() => navigate('/')}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          fontSize: '13px',
          fontWeight: 600,
          color: 'var(--color-text-muted)',
          marginBottom: '18px',
          cursor: 'pointer',
          background: 'none',
          border: 'none',
          padding: 0,
        }}
      >
        <ArrowLeft size={15} />
        <span>Back to Story Queue</span>
      </button>

      {/* Future Feature Notification Banner */}
      <div
        style={{
          padding: '12px 16px',
          background: 'var(--color-amber-bg)',
          border: '1px solid var(--color-amber-border)',
          borderRadius: 'var(--radius)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          marginBottom: '16px',
          fontSize: '13px',
          color: 'var(--color-amber-text)',
        }}
      >
        <Clock size={16} style={{ color: 'var(--color-amber)', flexShrink: 0 }} />
        <span>
          <strong>Future Feature Roadmap</strong> — Autonomous Bob session linking is planned for an upcoming release. The preview below outlines the execution pipeline and integration architecture.
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <Card
          padding="lg"
          style={{
            background: 'var(--color-card-gradient)',
            border: '1px solid var(--color-accent-border)',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', marginBottom: '16px' }}>
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '12px',
                background: 'var(--color-accent-bg)',
                color: 'var(--color-accent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <Cpu size={22} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--color-text)' }}>
                  Autonomous Agent Session Linking
                </h3>
                <Badge variant="amber" icon={<Clock size={11} />}>
                  Future Feature &bull; Planned
                </Badge>
                <Badge variant="default" icon={<Lock size={10} />}>
                  Gated API
                </Badge>
              </div>
              <p style={{ fontSize: '13.5px', color: 'var(--color-text-muted)', marginTop: '4px', lineHeight: 1.6 }}>
                Orchestrates autonomous coding agents upon tech lead approval. Bridges Jira issues with live Bob execution environments, git branches, and PR creation.
              </p>
            </div>
          </div>

          <div
            style={{
              padding: '14px 16px',
              background: 'var(--color-surface-subtle)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius)',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
            }}
          >
            <SectionHeading style={{ margin: 0 } as React.CSSProperties}>
              Prerequisite &amp; Gating Rule
            </SectionHeading>
            <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
              The backend endpoint{' '}
              <code
                style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  padding: '2px 6px',
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: '4px',
                  fontSize: '12px',
                }}
              >
                POST /api/bob-sessions
              </code>{' '}
              returns <strong style={{ color: 'var(--color-amber-text)' }}>HTTP 409 Conflict</strong> until the story&rsquo;s recommendation is explicitly approved by a Tech Lead.
            </p>
          </div>

          <div style={{ marginTop: '20px' }}>
            <SectionHeading>Upcoming Architecture Workflow</SectionHeading>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px',
                marginTop: '10px',
              }}
            >
              {[
                { title: '1. Sign-off Gating', desc: 'Verify approved execution mode and approver identity.' },
                { title: '2. Branch Provisioning', desc: 'Fork isolated feature branch with ticket context.' },
                { title: '3. Bob Autonomous Run', desc: 'Agent generates code, runs tests, and verifies AC.' },
                { title: '4. PR Submission', desc: 'Open Pull Request with full traceability back to Jira.' },
              ].map((step, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '12px 14px',
                    borderRadius: 'var(--radius)',
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    boxShadow: 'var(--shadow-xs)',
                  }}
                >
                  <p style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-accent)' }}>
                    {step.title}
                  </p>
                  <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '4px', lineHeight: 1.4 }}>
                    {step.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="primary"
              size="md"
              onClick={() => navigate('/')}
              icon={<CheckCircle2 size={14} />}
            >
              Review Approved Stories in Queue
            </Button>
          </div>
        </Card>
      </div>
    </AppShell>
  )
}
