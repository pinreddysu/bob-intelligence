import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Download,
  FileText,
  ChevronRight,
  Tag,
  Layers,
  Flame,
  ShieldAlert,
  Hash,
  Filter,
} from "lucide-react";
import { AppShell } from "../components/AppShell";
import {
  PriorityBadge,
  SourceBadge,
  Badge,
  Card,
  MetricCard,
  EmptyState,
  ErrorBanner,
  SampleDataBanner,
  StoryRowSkeleton,
  Button,
  WarningBanner,
} from "../components/ui";
import {
  listStories,
  importSampleStories,
  importJiraStory,
} from "../api/client";
import type { Story, StoryImportResponse } from "../api/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function hasSampleStory(stories: Story[]) {
  return stories.some((s) => s.source === "sample");
}

function hasRealStory(stories: Story[]) {
  return stories.some((s) => s.source !== "sample");
}

type FilterTab = "all" | "high_priority" | "blocked" | "jira" | "sample";

// ---------------------------------------------------------------------------
// Import panel
// ---------------------------------------------------------------------------

interface ImportPanelProps {
  onImported: (res: StoryImportResponse) => void;
  onCancel: () => void;
}

function ImportPanel({ onImported, onCancel }: ImportPanelProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jiraKey, setJiraKey] = useState("");
  const [importMode, setImportMode] = useState<"sample" | "jira">("sample");

  const handleImportSample = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await importSampleStories();
      onImported(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [onImported]);

  const handleImportJira = useCallback(async () => {
    if (!jiraKey.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await importJiraStory(jiraKey.trim());
      onImported(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [jiraKey, onImported]);

  return (
    <Card
      padding="lg"
      style={{
        marginBottom: "20px",
        border: "1px solid var(--color-accent-border)",
        boxShadow: "var(--shadow-md)",
        background: "var(--color-card-gradient)",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <h3
              style={{
                fontSize: "16px",
                fontWeight: 700,
                color: "var(--color-text)",
              }}
            >
              Import Stories to Queue
            </h3>
            <p
              style={{
                fontSize: "13px",
                color: "var(--color-text-muted)",
                marginTop: "2px",
              }}
            >
              Load backlog issues to analyze autonomy suitability and generate
              Bob execution plans.
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        </div>

        {/* Tab switch */}
        <div
          style={{
            display: "inline-flex",
            background: "var(--color-surface-subtle)",
            padding: "3px",
            borderRadius: "var(--radius)",
            border: "1px solid var(--color-border)",
            alignSelf: "flex-start",
            gap: "2px",
          }}
        >
          <button
            onClick={() => setImportMode("sample")}
            style={{
              padding: "6px 14px",
              borderRadius: "var(--radius-sm)",
              background:
                importMode === "sample"
                  ? "var(--color-surface)"
                  : "transparent",
              color:
                importMode === "sample"
                  ? "var(--color-accent)"
                  : "var(--color-text-muted)",
              fontWeight: 600,
              fontSize: "12.5px",
              cursor: "pointer",
              boxShadow: importMode === "sample" ? "var(--shadow-xs)" : "none",
              transition: "all 0.15s ease",
            }}
          >
            Built-in Sample Backlog
          </button>
          <button
            onClick={() => setImportMode("jira")}
            style={{
              padding: "6px 14px",
              borderRadius: "var(--radius-sm)",
              background:
                importMode === "jira" ? "var(--color-surface)" : "transparent",
              color:
                importMode === "jira"
                  ? "var(--color-accent)"
                  : "var(--color-text-muted)",
              fontWeight: 600,
              fontSize: "12.5px",
              cursor: "pointer",
              boxShadow: importMode === "jira" ? "var(--shadow-xs)" : "none",
              transition: "all 0.15s ease",
            }}
          >
            Live Jira Issue
          </button>
        </div>

        {importMode === "sample" ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "16px",
              padding: "16px",
              background: "var(--color-accent-bg)",
              border: "1px solid var(--color-accent-border)",
              borderRadius: "var(--radius)",
            }}
          >
            <div>
              <p
                style={{
                  fontSize: "13.5px",
                  fontWeight: 600,
                  color: "var(--color-text)",
                }}
              >
                Import Built-in Sample Dataset
              </p>
              <p
                style={{
                  fontSize: "12.5px",
                  color: "var(--color-text-muted)",
                  marginTop: "2px",
                }}
              >
                Loads 7 realistic PIE project stories with full acceptance
                criteria, blockers, and history. Duplicate imports are
                automatically skipped.
              </p>
            </div>
            <Button
              variant="primary"
              size="md"
              loading={loading}
              onClick={handleImportSample}
              icon={<Download size={14} />}
            >
              Import Sample Stories
            </Button>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <p style={{ fontSize: "13px", color: "var(--color-text-muted)" }}>
              Enter a Jira issue key (e.g. <code>PIE-42</code>) to fetch story
              details, acceptance criteria, and linked PRs directly from Jira
              Cloud:
            </p>
            <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <input
                type="text"
                value={jiraKey}
                onChange={(e) => setJiraKey(e.target.value)}
                placeholder="e.g. PIE-42"
                aria-label="Jira issue key"
                onKeyDown={(e) => e.key === "Enter" && handleImportJira()}
                className="input-base"
                style={{
                  flex: 1,
                  maxWidth: "320px",
                  fontFamily: "ui-monospace, monospace",
                  fontWeight: 600,
                }}
              />
              <Button
                variant="primary"
                size="md"
                loading={loading}
                disabled={!jiraKey.trim()}
                onClick={handleImportJira}
                icon={<Download size={14} />}
              >
                Fetch Story
              </Button>
            </div>
          </div>
        )}

        {error && <ErrorBanner message={error} />}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Story row
// ---------------------------------------------------------------------------

interface StoryRowProps {
  story: Story;
  onSelect: (story: Story) => void;
}

function StoryRow({ story, onSelect }: StoryRowProps) {
  const hasBlockers = story.blockers && story.blockers.length > 0;
  const isHighPriority =
    story.priority?.toLowerCase() === "highest" ||
    story.priority?.toLowerCase() === "critical" ||
    story.priority?.toLowerCase() === "high";

  return (
    <div
      onClick={() => onSelect(story)}
      style={{
        display: "flex",
        alignItems: "center",
        padding: "16px 20px",
        borderBottom: "1px solid var(--color-border-subtle)",
        gap: "16px",
        cursor: "pointer",
        transition: "all 0.15s ease",
        background: "var(--color-surface)",
        position: "relative",
      }}
      className="story-row-item"
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "var(--color-surface-hover)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "var(--color-surface)";
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          onSelect(story);
        }
      }}
      aria-label={`Open story ${story.jira_key ?? story.id}: ${story.title}`}
    >
      {/* Priority accent stripe */}
      <div
        style={{
          width: "3px",
          height: "36px",
          borderRadius: "9999px",
          background: isHighPriority
            ? "var(--color-red)"
            : hasBlockers
              ? "var(--color-amber)"
              : "var(--color-accent)",
          flexShrink: 0,
        }}
      />

      {/* Jira key pill */}
      <span
        style={{
          fontFamily: "JetBrains Mono, ui-monospace, monospace",
          fontSize: "12px",
          fontWeight: 700,
          color: "var(--color-text)",
          background: "var(--color-surface-subtle)",
          border: "1px solid var(--color-border)",
          borderRadius: "6px",
          padding: "4px 8px",
          letterSpacing: "-0.02em",
          flexShrink: 0,
          minWidth: "80px",
          textAlign: "center",
        }}
      >
        {story.jira_key ?? story.id.slice(0, 8)}
      </span>

      {/* Main info */}
      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: "flex",
          flexDirection: "column",
          gap: "4px",
        }}
      >
        <p
          style={{
            fontSize: "14px",
            fontWeight: 600,
            color: "var(--color-text)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            lineHeight: 1.3,
          }}
        >
          {story.title}
        </p>

        {/* Badges row */}
        <div
          style={{
            display: "flex",
            gap: "6px",
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          {story.status && (
            <Badge variant="gray" style={{ fontSize: "11px" }}>
              {story.status}
            </Badge>
          )}
          <SourceBadge source={story.source} />
          {hasBlockers && (
            <Badge variant="red" icon={<AlertTriangle size={11} />}>
              {story.blockers.length} blocker
              {story.blockers.length !== 1 ? "s" : ""}
            </Badge>
          )}
          {story.story_points !== null && story.story_points !== undefined && (
            <Badge
              variant="default"
              style={{ fontSize: "11px", color: "var(--color-text-muted)" }}
            >
              {story.story_points} pts
            </Badge>
          )}
          {story.labels && story.labels.length > 0 && (
            <span
              style={{
                display: "inline-flex",
                gap: "4px",
                alignItems: "center",
                color: "var(--color-text-faint)",
                fontSize: "11px",
                marginLeft: "4px",
              }}
            >
              <Tag size={10} />
              {(story.labels as string[]).slice(0, 2).join(", ")}
              {story.labels.length > 2 && ` +${story.labels.length - 2}`}
            </span>
          )}
        </div>
      </div>

      {/* Priority badge & evaluation arrow */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "14px",
          flexShrink: 0,
        }}
      >
        <PriorityBadge priority={story.priority} />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "4px",
            fontSize: "12px",
            fontWeight: 600,
            color: "var(--color-accent)",
            padding: "4px 8px",
            borderRadius: "6px",
            background: "var(--color-accent-bg)",
          }}
        >
          <span>Evaluate</span>
          <ChevronRight size={14} />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function StorySelector() {
  const navigate = useNavigate();
  const [stories, setStories] = useState<Story[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [showImport, setShowImport] = useState(false);
  const [importWarning, setImportWarning] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<FilterTab>("all");

  const fetchStories = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listStories();
      setStories(data.stories);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchStories();
  }, [fetchStories]);

  const handleImported = useCallback(
    (res: StoryImportResponse) => {
      setShowImport(false);
      if (res.source_warning) setImportWarning(res.source_warning);
      void fetchStories();
    },
    [fetchStories],
  );

  const handleSelect = useCallback(
    (story: Story) => {
      navigate(`/stories/${story.id}`);
    },
    [navigate],
  );

  // Metrics calculations
  const totalCount = stories.length;
  const highPriorityCount = useMemo(
    () =>
      stories.filter((s) => {
        const p = s.priority?.toLowerCase();
        return p === "highest" || p === "critical" || p === "high";
      }).length,
    [stories],
  );
  const blockedCount = useMemo(
    () => stories.filter((s) => s.blockers && s.blockers.length > 0).length,
    [stories],
  );
  const jiraCount = useMemo(
    () => stories.filter((s) => s.source === "jira").length,
    [stories],
  );
  const sampleCount = useMemo(
    () => stories.filter((s) => s.source === "sample").length,
    [stories],
  );

  const filtered = useMemo(() => {
    return stories.filter((s) => {
      // Tab filter
      if (activeTab === "high_priority") {
        const p = s.priority?.toLowerCase();
        if (p !== "highest" && p !== "critical" && p !== "high") return false;
      } else if (activeTab === "blocked") {
        if (!s.blockers || s.blockers.length === 0) return false;
      } else if (activeTab === "jira") {
        if (s.source !== "jira") return false;
      } else if (activeTab === "sample") {
        if (s.source !== "sample") return false;
      }

      // Search query filter
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        s.title.toLowerCase().includes(q) ||
        (s.jira_key && s.jira_key.toLowerCase().includes(q)) ||
        (s.status && s.status.toLowerCase().includes(q)) ||
        (s.labels && s.labels.some((l) => l.toLowerCase().includes(q)))
      );
    });
  }, [stories, search, activeTab]);

  const hasSample = hasSampleStory(stories);
  const hasReal = hasRealStory(stories);

  return (
    <AppShell
      title="Story Queue"
      subtitle={`${stories.length} candidate issues available for execution mode analysis`}
      searchValue={search}
      onSearchChange={setSearch}
      showSearch={stories.length > 0}
      onRefresh={fetchStories}
    >
      {/* Sample data alert */}
      {hasSample && !hasReal && (
        <div style={{ marginBottom: "16px" }}>
          <SampleDataBanner />
        </div>
      )}
      {hasSample && hasReal && (
        <div style={{ marginBottom: "16px" }}>
          <WarningBanner message="This queue contains a mix of live Jira stories and demo sample stories. Demo issues are marked with a 'Sample Data' tag." />
        </div>
      )}

      {/* Import warning banner */}
      {importWarning && (
        <div style={{ marginBottom: "16px" }}>
          <WarningBanner message={importWarning} />
        </div>
      )}

      {/* Executive Metric Cards Banner */}
      {!loading && !error && stories.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "14px",
            marginBottom: "20px",
          }}
        >
          <MetricCard
            title="Total Stories in Backlog"
            value={totalCount}
            subtext={`${sampleCount} sample / ${jiraCount} real Jira`}
            icon={<Layers size={18} />}
            accentColor="#2563EB"
          />
          <MetricCard
            title="High / Critical Priority"
            value={highPriorityCount}
            subtext="Require accelerated triage"
            icon={<Flame size={18} />}
            accentColor="#E11D48"
          />
          <MetricCard
            title="Blocked / At Risk"
            value={blockedCount}
            subtext="Contain active blockers"
            icon={<ShieldAlert size={18} />}
            accentColor="#D97706"
          />
          <MetricCard
            title="Dataset Composition"
            value={hasReal ? "Hybrid" : "PIE Sample"}
            subtext={
              hasReal ? "Connected to live Jira" : "Built-in reference data"
            }
            icon={<Hash size={18} />}
            accentColor="#7C3AED"
          />
        </div>
      )}

      {/* Import Drawer */}
      {showImport && (
        <ImportPanel
          onImported={handleImported}
          onCancel={() => setShowImport(false)}
        />
      )}

      {/* Toolbar & Filter Tabs */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "12px",
          marginBottom: "14px",
          flexWrap: "wrap",
        }}
      >
        {/* Filter Pills */}
        <div
          style={{
            display: "flex",
            gap: "6px",
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          <span
            style={{
              fontSize: "12px",
              fontWeight: 600,
              color: "var(--color-text-muted)",
              display: "flex",
              alignItems: "center",
              gap: "4px",
              marginRight: "4px",
            }}
          >
            <Filter size={12} />
            Filter:
          </span>
          <button
            onClick={() => setActiveTab("all")}
            style={{
              padding: "4px 10px",
              borderRadius: "9999px",
              fontSize: "12px",
              fontWeight: activeTab === "all" ? 700 : 500,
              background:
                activeTab === "all"
                  ? "var(--color-accent)"
                  : "var(--color-surface)",
              color:
                activeTab === "all" ? "#FFFFFF" : "var(--color-text-secondary)",
              border: `1px solid ${activeTab === "all" ? "var(--color-accent)" : "var(--color-border)"}`,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            All ({totalCount})
          </button>
          <button
            onClick={() => setActiveTab("high_priority")}
            style={{
              padding: "4px 10px",
              borderRadius: "9999px",
              fontSize: "12px",
              fontWeight: activeTab === "high_priority" ? 700 : 500,
              background:
                activeTab === "high_priority"
                  ? "var(--color-red)"
                  : "var(--color-surface)",
              color:
                activeTab === "high_priority"
                  ? "#FFFFFF"
                  : "var(--color-text-secondary)",
              border: `1px solid ${activeTab === "high_priority" ? "var(--color-red)" : "var(--color-border)"}`,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            High Priority ({highPriorityCount})
          </button>
          <button
            onClick={() => setActiveTab("blocked")}
            style={{
              padding: "4px 10px",
              borderRadius: "9999px",
              fontSize: "12px",
              fontWeight: activeTab === "blocked" ? 700 : 500,
              background:
                activeTab === "blocked"
                  ? "var(--color-amber)"
                  : "var(--color-surface)",
              color:
                activeTab === "blocked"
                  ? "#FFFFFF"
                  : "var(--color-text-secondary)",
              border: `1px solid ${activeTab === "blocked" ? "var(--color-amber)" : "var(--color-border)"}`,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            Has Blockers ({blockedCount})
          </button>
          {jiraCount > 0 && (
            <button
              onClick={() => setActiveTab("jira")}
              style={{
                padding: "4px 10px",
                borderRadius: "9999px",
                fontSize: "12px",
                fontWeight: activeTab === "jira" ? 700 : 500,
                background:
                  activeTab === "jira"
                    ? "var(--color-green)"
                    : "var(--color-surface)",
                color:
                  activeTab === "jira"
                    ? "#FFFFFF"
                    : "var(--color-text-secondary)",
                border: `1px solid ${activeTab === "jira" ? "var(--color-green)" : "var(--color-border)"}`,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              Jira ({jiraCount})
            </button>
          )}
          {sampleCount > 0 && (
            <button
              onClick={() => setActiveTab("sample")}
              style={{
                padding: "4px 10px",
                borderRadius: "9999px",
                fontSize: "12px",
                fontWeight: activeTab === "sample" ? 700 : 500,
                background:
                  activeTab === "sample" ? "#475569" : "var(--color-surface)",
                color:
                  activeTab === "sample"
                    ? "#FFFFFF"
                    : "var(--color-text-secondary)",
                border: `1px solid ${activeTab === "sample" ? "#475569" : "var(--color-border)"}`,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              Sample Data ({sampleCount})
            </button>
          )}
        </div>

        {/* Action Button */}
        <div>
          {!showImport && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setShowImport(true);
                setImportWarning(null);
              }}
              icon={<Download size={13} />}
            >
              Import Stories
            </Button>
          )}
        </div>
      </div>

      {/* Story List Card */}
      {loading ? (
        <Card padding="none">
          {[0, 1, 2, 3, 4].map((i) => (
            <StoryRowSkeleton key={i} />
          ))}
        </Card>
      ) : error ? (
        <ErrorBanner message={error} onRetry={fetchStories} />
      ) : filtered.length === 0 && stories.length === 0 ? (
        <Card padding="none">
          <EmptyState
            icon={<FileText size={32} />}
            title="Story queue is empty"
            description="Import sample PIE backlog tickets or fetch stories directly from Jira to begin generating Bob execution recommendations."
            action={
              <Button
                variant="primary"
                onClick={() => setShowImport(true)}
                icon={<Download size={14} />}
              >
                Import Stories
              </Button>
            }
          />
        </Card>
      ) : filtered.length === 0 ? (
        <Card padding="none">
          <EmptyState
            title="No matching stories found"
            description={
              search
                ? `No stories match "${search}" with current filter.`
                : "No stories found for the selected filter."
            }
            action={
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setSearch("");
                  setActiveTab("all");
                }}
              >
                Reset Filters
              </Button>
            }
          />
        </Card>
      ) : (
        <Card
          padding="none"
          style={{
            overflow: "hidden",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          {filtered.map((story) => (
            <StoryRow key={story.id} story={story} onSelect={handleSelect} />
          ))}
        </Card>
      )}

      {/* Footer stats */}
      {!loading && !error && filtered.length > 0 && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginTop: "12px",
            fontSize: "12px",
            color: "var(--color-text-faint)",
          }}
        >
          <span>
            Click any story to view autonomous execution recommendation and
            sign-off controls.
          </span>
          <span>
            Showing {filtered.length} of {stories.length} stories
          </span>
        </div>
      )}
    </AppShell>
  );
}
