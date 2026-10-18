import { useNavigate } from 'react-router-dom'
import { ArrowLeft, BarChart3, Lock, CheckCircle2, Clock } from 'lucide-react'
import { AppShell } from '../components/AppShell'
import { Card, SectionHeading, Badge, Button } from '../components/ui'

/**
 * Outcomes & Comparison — Future Feature Preview.
 * Post-merge verification and telemetry benchmarks.
 */
export default function OutcomeComparison() {
  const navigate = useNavigate()

  return (
    <AppShell
      title="Outcomes & Telemetry Comparison"
      subtitle="Future Feature Roadmap — Post-merge verification and autonomous efficiency benchmarks"
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
          <strong>Future Feature Roadmap</strong> — Outcome tracking and autonomous vs human telemetry comparison is planned for an upcoming release. The preview below outlines the telemetry benchmarks and feedback loop.
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <Card
          padding="lg"
          style={{
            background: 'var(--color-card-gradient)',
            border: '1px solid var(--color-purple-border)',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', marginBottom: '16px' }}>
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '12px',
                background: 'var(--color-purple-bg)',
                color: 'var(--color-purple)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <BarChart3 size={22} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--color-text)' }}>
                  Outcome Recording &amp; Benchmark Evaluation
                </h3>
                <Badge variant="amber" icon={<Clock size={11} />}>
                  Future Feature &bull; Planned
                </Badge>
                <Badge variant="default" icon={<Lock size={10} />}>
                  Gated API
                </Badge>
              </div>
              <p style={{ fontSize: '13.5px', color: 'var(--color-text-muted)', marginTop: '4px', lineHeight: 1.6 }}>
                Records production outcomes, acceptance criteria verification results, code review cycles, and time-to-merge metrics to continuously improve recommendation accuracy.
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
                POST /api/outcomes
              </code>{' '}
              is gated behind an HTTP 409 response until a story&rsquo;s recommendation is approved and the execution session completes.
            </p>
          </div>

          <div style={{ marginTop: '20px' }}>
            <SectionHeading>Upcoming Telemetry Roadmap</SectionHeading>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px',
                marginTop: '10px',
              }}
            >
              {[
                { title: 'AC Verification', desc: 'Automated test suite evaluation and AC pass/fail rate.' },
                { title: 'Code Review Diffs', desc: 'Number of review iterations and human interventions.' },
                { title: 'Cycle Time', desc: 'Duration from sign-off to merged production Pull Request.' },
                { title: 'Model Feedback Loop', desc: 'Feed verified outcomes back into TF-IDF vector corpus.' },
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
                  <p style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-purple)' }}>
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
              Return to Story Queue
            </Button>
          </div>
        </Card>
      </div>
    </AppShell>
  )
}
