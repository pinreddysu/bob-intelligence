import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  Download,
  FileText,
  ChevronRight,
  Tag,
} from 'lucide-react'
import { AppShell } from '../components/AppShell'
import {
  PriorityBadge,
  SourceBadge,
  Badge,
  Card,
  EmptyState,
  ErrorBanner,
  SampleDataBanner,
  StoryRowSkeleton,
  Button,
  WarningBanner,
} from '../components/ui'
import { listStories, importSampleStories, importJiraStory } from '../api/client'
import type { Story, StoryImportResponse } from '../api/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function hasSampleStory(stories: Story[]) {
  return stories.some(s => s.source === 'sample')
}

function hasRealStory(stories: Story[]) {
  return stories.some(s => s.source !== 'sample')
}

// ---------------------------------------------------------------------------
// Import panel
// ---------------------------------------------------------------------------

interface ImportPanelProps {
  onImported: (res: StoryImportResponse) => void
}

function ImportPanel({ onImported }: ImportPanelProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [jiraKey, setJiraKey] = useState('')
  const [importMode, setImportMode] = useState<'sample' | 'jira'>('sample')

  const handleImportSample = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await importSampleStories()
      onImported(res)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [onImported])

  const handleImportJira = useCallback(async () => {
    if (!jiraKey.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await importJiraStory(jiraKey.trim())
      onImported(res)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [jiraKey, onImported])

  return (
    <Card className="mb-4" padding="md">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <p style={{ fontWeight: 600, fontSize: '14px' }}>Import Stories</p>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setImportMode('sample')}
            style={{
              padding: '5px 12px',
              borderRadius: 'var(--radius)',
              border: `1px solid ${importMode === 'sample' ? 'var(--color-accent)' : 'var(--color-border)'}`,
              background: importMode === 'sample' ? 'var(--color-accent-bg)' : 'transparent',
              color: importMode === 'sample' ? 'var(--color-accent)' : 'var(--color-text-muted)',
              fontWeight: 500,
              fontSize: '13px',
              cursor: 'pointer',
            }}
          >
            Sample data
          </button>
          <button
            onClick={() => setImportMode('jira')}
            style={{
              padding: '5px 12px',
              borderRadius: 'var(--radius)',
              border: `1px solid ${importMode === 'jira' ? 'var(--color-accent)' : 'var(--color-border)'}`,
              background: importMode === 'jira' ? 'var(--color-accent-bg)' : 'transparent',
              color: importMode === 'jira' ? 'var(--color-accent)' : 'var(--color-text-muted)',
              fontWeight: 500,
              fontSize: '13px',
              cursor: 'pointer',
            }}
          >
            Jira story
          </button>
        </div>

        {importMode === 'sample' ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <p style={{ fontSize: '13px', color: 'var(--color-text-muted)', flex: 1 }}>
              Import built-in PIE sample stories (idempotent — duplicates are skipped).
            </p>
            <Button
              variant="primary"
              size="sm"
              loading={loading}
              onClick={handleImportSample}
            >
              <Download size={13} />
              Import
            </Button>
          </div>
        ) : (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <input
              type="text"
              value={jiraKey}
              onChange={e => setJiraKey(e.target.value)}
              placeholder="e.g. PIE-42"
              aria-label="Jira issue key"
              onKeyDown={e => e.key === 'Enter' && handleImportJira()}
              style={{
                padding: '6px 10px',
                borderRadius: 'var(--radius)',
                border: '1px solid var(--color-border)',
                fontSize: '13px',
                flex: 1,
              }}
            />
            <Button
              variant="primary"
              size="sm"
              loading={loading}
              disabled={!jiraKey.trim()}
              onClick={handleImportJira}
            >
              Fetch
            </Button>
          </div>
        )}

        {error && <ErrorBanner message={error} />}
      </div>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Story row
// ---------------------------------------------------------------------------

interface StoryRowProps {
  story: Story
  onSelect: (story: Story) => void
}

function StoryRow({ story, onSelect }: StoryRowProps) {
  const hasBlockers = story.blockers && story.blockers.length > 0

  return (
    <button
      onClick={() => onSelect(story)}
      style={{
        display: 'grid',
        gridTemplateColumns: '90px 1fr auto',
        alignItems: 'center',
        gap: '12px',
        padding: '12px 16px',
        borderBottom: '1px solid var(--color-border-subtle)',
        width: '100%',
        textAlign: 'left',
        background: 'transparent',
        cursor: 'pointer',
        transition: 'background 0.1s',
      }}
      onMouseEnter={e =>
        (e.currentTarget.style.background = 'var(--color-border-subtle)')
      }
      onMouseLeave={e =>
        (e.currentTarget.style.background = 'transparent')
      }
      aria-label={`Open story ${story.jira_key ?? story.id}: ${story.title}`}
    >
      {/* Key */}
      <span
        style={{
          fontFamily: 'ui-monospace, monospace',
          fontSize: '12px',
          color: 'var(--color-text-muted)',
          fontWeight: 600,
        }}
      >
        {story.jira_key ?? story.id.slice(0, 8)}
      </span>

      {/* Title + meta */}
      <div style={{ minWidth: 0 }}>
        <p
          style={{
            fontSize: '13.5px',
            fontWeight: 500,
            color: 'var(--color-text)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {story.title}
        </p>
        <div style={{ display: 'flex', gap: '6px', marginTop: '4px', flexWrap: 'wrap', alignItems: 'center' }}>
          {story.status && (
            <Badge variant="gray">{story.status}</Badge>
          )}
          <SourceBadge source={story.source} />
          {hasBlockers && (
            <Badge variant="red">
              <AlertTriangle size={10} style={{ marginRight: '3px' }} />
              {story.blockers.length} blocker{story.blockers.length !== 1 ? 's' : ''}
            </Badge>
          )}
          {story.labels && story.labels.length > 0 && (
            <span style={{ display: 'flex', gap: '4px', alignItems: 'center', color: 'var(--color-text-faint)', fontSize: '11px' }}>
              <Tag size={10} />
              {(story.labels as string[]).slice(0, 3).join(', ')}
              {story.labels.length > 3 && ` +${story.labels.length - 3}`}
            </span>
          )}
        </div>
      </div>

      {/* Priority + chevron */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
        <PriorityBadge priority={story.priority} />
        <ChevronRight size={14} style={{ color: 'var(--color-text-faint)' }} />
      </div>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function StorySelector() {
  const navigate = useNavigate()
  const [stories, setStories] = useState<Story[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [importWarning, setImportWarning] = useState<string | null>(null)

  const fetchStories = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listStories()
      setStories(data.stories)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchStories()
  }, [fetchStories])

  const handleImported = useCallback(
    (res: StoryImportResponse) => {
      setShowImport(false)
      if (res.source_warning) setImportWarning(res.source_warning)
      void fetchStories()
    },
    [fetchStories],
  )

  const handleSelect = useCallback(
    (story: Story) => {
      navigate(`/stories/${story.id}`)
    },
    [navigate],
  )

  const filtered = useMemo(() => {
    if (!search.trim()) return stories
    const q = search.toLowerCase()
    return stories.filter(
      s =>
        s.title.toLowerCase().includes(q) ||
        (s.jira_key && s.jira_key.toLowerCase().includes(q)) ||
        (s.status && s.status.toLowerCase().includes(q)),
    )
  }, [stories, search])

  const hasSample = hasSampleStory(stories)
  const hasReal = hasRealStory(stories)
  const subtitle =
    stories.length === 0
      ? 'No stories imported yet'
      : `${stories.length} stor${stories.length !== 1 ? 'ies' : 'y'} — select one to generate a recommendation`

  return (
    <AppShell
      title="Story Queue"
      subtitle={subtitle}
      searchValue={search}
      onSearchChange={setSearch}
      showSearch={stories.length > 0}
      onRefresh={fetchStories}
    >
      {/* Sample data notice */}
      {hasSample && !hasReal && (
        <div style={{ marginBottom: '12px' }}>
          <SampleDataBanner />
        </div>
      )}
      {hasSample && hasReal && (
        <div style={{ marginBottom: '12px' }}>
          <WarningBanner message="This queue contains a mix of real Jira stories and sample data. Sample stories are labeled clearly." />
        </div>
      )}

      {/* Import warning */}
      {importWarning && (
        <div style={{ marginBottom: '12px' }}>
          <WarningBanner message={importWarning} />
        </div>
      )}

      {/* Import panel */}
      {showImport && (
        <ImportPanel onImported={handleImported} />
      )}

      {/* Actions row */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '12px', gap: '8px' }}>
        {!showImport && (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => { setShowImport(true); setImportWarning(null) }}
          >
            <Download size={13} />
            Import
          </Button>
        )}
        {showImport && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowImport(false)}
          >
            Cancel
          </Button>
        )}
      </div>

      {/* Story list */}
      {loading ? (
        <Card padding="none">
          {[0, 1, 2, 3].map(i => (
            <StoryRowSkeleton key={i} />
          ))}
        </Card>
      ) : error ? (
        <ErrorBanner message={error} onRetry={fetchStories} />
      ) : filtered.length === 0 && stories.length === 0 ? (
        <Card padding="none">
          <EmptyState
            icon={<FileText size={32} />}
            title="No stories imported"
            description="Import sample stories or fetch a Jira story to get started."
            action={
              <Button
                variant="primary"
                onClick={() => setShowImport(true)}
              >
                <Download size={14} />
                Import Stories
              </Button>
            }
          />
        </Card>
      ) : filtered.length === 0 ? (
        <Card padding="none">
          <EmptyState
            title="No stories match your search"
            description={`No stories found for "${search}".`}
          />
        </Card>
      ) : (
        <Card padding="none">
          {filtered.map(story => (
            <StoryRow key={story.id} story={story} onSelect={handleSelect} />
          ))}
        </Card>
      )}

      {/* Story count footer */}
      {!loading && !error && filtered.length > 0 && (
        <p style={{ marginTop: '10px', fontSize: '12px', color: 'var(--color-text-faint)', textAlign: 'right' }}>
          {filtered.length} of {stories.length} stories
        </p>
      )}
    </AppShell>
  )
}
