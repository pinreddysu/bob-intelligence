import React, { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
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
  Sparkles,
  FileCheck,
  CheckSquare,
  ShieldCheck,
  Award,
} from "lucide-react";
import { AppShell } from "../components/AppShell";
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
  ProgressBar,
} from "../components/ui";
import { ApprovalPanel } from "../components/ApprovalPanel";
import {
  getStory,
  createRecommendation,
  getRecommendation,
  getRecommendationForStory,
} from "../api/client";
import type {
  Story,
  Recommendation,
  EvidenceItem,
  RiskItem,
} from "../api/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function modeLabel(mode: string | null): string {
  if (mode === "bob_led") return "Bob-led (Autonomous)";
  if (mode === "collaborative") return "Collaborative (Pairing)";
  if (mode === "human_led") return "Human-led (Manual)";
  return mode ?? "Unknown";
}

function modeDescription(mode: string | null): string {
  if (mode === "bob_led")
    return "Bob performs end-to-end implementation autonomously. The tech lead conducts a final review and verifies acceptance criteria before merging.";
  if (mode === "collaborative")
    return "Bob executes boilerplate and test scaffolding while an engineer guides architectural decisions, key logic, and complex edge cases.";
  if (mode === "human_led")
    return "An engineer should take lead on this issue. Autonomous evidence is insufficient, or high risk/low confidence requires manual ownership.";
  return "Execution mode not determined.";
}

function modeIcon(mode: string | null, size = 26) {
  if (mode === "bob_led") return <Zap size={size} />;
  if (mode === "collaborative") return <Users size={size} />;
  if (mode === "human_led") return <User size={size} />;
  return <HelpCircle size={size} />;
}

function modeColor(mode: string | null): {
  bg: string;
  border: string;
  text: string;
  iconBg: string;
  iconColor: string;
} {
  if (mode === "bob_led")
    return {
      bg: "var(--mode-bob-bg)",
      border: "var(--mode-bob-border)",
      text: "var(--mode-bob-text)",
      iconBg: "#2563EB",
      iconColor: "#FFFFFF",
    };
  if (mode === "collaborative")
    return {
      bg: "var(--mode-collab-bg)",
      border: "var(--mode-collab-border)",
      text: "var(--mode-collab-text)",
      iconBg: "#7C3AED",
      iconColor: "#FFFFFF",
    };
  if (mode === "human_led")
    return {
      bg: "var(--mode-human-bg)",
      border: "var(--mode-human-border)",
      text: "var(--mode-human-text)",
      iconBg: "#D97706",
      iconColor: "#FFFFFF",
    };
  return {
    bg: "var(--color-surface-subtle)",
    border: "var(--color-border)",
    text: "var(--color-text)",
    iconBg: "#64748B",
    iconColor: "#FFFFFF",
  };
}

// ---------------------------------------------------------------------------
// Story context panel
// ---------------------------------------------------------------------------

function StoryContext({ story }: { story: Story }) {
  // Format acceptance criteria lines into checklist items if multiline
  const acLines = story.acceptance_criteria
    ? story.acceptance_criteria
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)
    : [];

  return (
    <Card padding="lg">
      {/* Header bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "14px",
          flexWrap: "wrap",
          gap: "8px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              fontFamily: "JetBrains Mono, ui-monospace, monospace",
              fontSize: "13px",
              fontWeight: 700,
              color: "var(--color-text)",
              background: "var(--color-surface-subtle)",
              border: "1px solid var(--color-border)",
              borderRadius: "6px",
              padding: "3px 8px",
            }}
          >
            {story.jira_key ?? story.id.slice(0, 8)}
          </span>
          <SourceBadge source={story.source} />
        </div>
        <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          <PriorityBadge priority={story.priority} />
          {story.status && <Badge variant="gray">{story.status}</Badge>}
        </div>
      </div>

      <h2
        style={{
          fontSize: "18px",
          fontWeight: 700,
          marginBottom: "14px",
          lineHeight: 1.4,
          color: "var(--color-text)",
          letterSpacing: "-0.02em",
        }}
      >
        {story.title}
      </h2>

      {story.description && (
        <div style={{ marginBottom: "16px" }}>
          <SectionHeading>Description</SectionHeading>
          <div
            style={{
              fontSize: "13.5px",
              color: "var(--color-text-secondary)",
              lineHeight: 1.7,
              whiteSpace: "pre-wrap",
              background: "var(--color-surface-subtle)",
              border: "1px solid var(--color-border-subtle)",
              borderRadius: "var(--radius)",
              padding: "12px 14px",
            }}
          >
            {story.description}
          </div>
        </div>
      )}

      {story.acceptance_criteria && (
        <div style={{ marginBottom: "16px" }}>
          <SectionHeading>
            <CheckSquare size={13} style={{ color: "var(--color-accent)" }} />
            Acceptance Criteria
          </SectionHeading>
          {acLines.length > 1 ? (
            <div
              style={{ display: "flex", flexDirection: "column", gap: "6px" }}
            >
              {acLines.map((line, idx) => (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "8px",
                    fontSize: "13px",
                    color: "var(--color-text)",
                    lineHeight: 1.5,
                    padding: "6px 10px",
                    background: "var(--color-surface-subtle)",
                    border: "1px solid var(--color-border-subtle)",
                    borderRadius: "var(--radius-sm)",
                  }}
                >
                  <FileCheck
                    size={14}
                    style={{
                      color: "var(--color-green)",
                      flexShrink: 0,
                      marginTop: "2px",
                    }}
                  />
                  <span>{line.replace(/^[-*•]\s*/, "")}</span>
                </div>
              ))}
            </div>
          ) : (
            <p
              style={{
                fontSize: "13.5px",
                color: "var(--color-text)",
                lineHeight: 1.7,
                whiteSpace: "pre-wrap",
                background: "var(--color-surface-subtle)",
                borderRadius: "var(--radius)",
                padding: "12px 14px",
              }}
            >
              {story.acceptance_criteria}
            </p>
          )}
        </div>
      )}

      {!story.description && !story.acceptance_criteria && (
        <p
          style={{
            fontSize: "13px",
            color: "var(--color-text-faint)",
            fontStyle: "italic",
            marginBottom: "12px",
          }}
        >
          No description or acceptance criteria found in Jira payload.
        </p>
      )}

      <Divider style={{ margin: "14px 0" }} />

      {/* Metadata breakdown */}
      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        {story.assignee && <MetaRow label="Assignee">{story.assignee}</MetaRow>}
        {story.story_points !== null && story.story_points !== undefined && (
          <MetaRow label="Story points">
            <span style={{ fontWeight: 600 }}>{story.story_points} points</span>
          </MetaRow>
        )}
        {story.labels && story.labels.length > 0 && (
          <MetaRow label="Labels">
            <span style={{ display: "flex", gap: "5px", flexWrap: "wrap" }}>
              {(story.labels as string[]).map((l) => (
                <Badge key={l} variant="gray">
                  {l}
                </Badge>
              ))}
            </span>
          </MetaRow>
        )}
        {story.blockers && story.blockers.length > 0 && (
          <MetaRow label="Blockers">
            <span
              style={{ display: "flex", flexDirection: "column", gap: "4px" }}
            >
              {(story.blockers as string[]).map((b, i) => (
                <span
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    color: "var(--color-red-text)",
                    fontSize: "12.5px",
                    fontWeight: 600,
                  }}
                >
                  <AlertTriangle
                    size={13}
                    style={{ color: "var(--color-red)" }}
                  />
                  {b}
                </span>
              ))}
            </span>
          </MetaRow>
        )}
        {story.linked_prs && story.linked_prs.length > 0 && (
          <MetaRow label="Linked PRs">
            <span
              style={{ display: "flex", flexDirection: "column", gap: "4px" }}
            >
              {(story.linked_prs as string[]).map((pr, i) => (
                <a
                  key={i}
                  href={pr}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    fontSize: "12.5px",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                    color: "var(--color-accent)",
                  }}
                >
                  <GitPullRequest size={13} />
                  <span>{pr}</span>
                  <ExternalLink size={11} style={{ opacity: 0.6 }} />
                </a>
              ))}
            </span>
          </MetaRow>
        )}
        <MetaRow label="Imported">{formatDate(story.created_at)}</MetaRow>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Mode hero
// ---------------------------------------------------------------------------

function ModeHero({ rec }: { rec: Recommendation }) {
  const colors = modeColor(rec.mode);

  return (
    <div
      style={{
        background: colors.bg,
        border: `2px solid ${colors.border}`,
        borderRadius: "var(--radius-xl)",
        padding: "24px",
        display: "flex",
        flexDirection: "column",
        gap: "14px",
        boxShadow: "var(--shadow-md)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "16px",
          flexWrap: "wrap",
        }}
      >
        <div
          style={{
            width: "52px",
            height: "52px",
            borderRadius: "14px",
            background: colors.iconBg,
            color: colors.iconColor,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            boxShadow: "0 4px 14px rgba(0,0,0,0.15)",
          }}
        >
          {modeIcon(rec.mode, 28)}
        </div>
        <div style={{ flex: 1, minWidth: "200px" }}>
          <p
            style={{
              fontSize: "11px",
              color: colors.text,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              opacity: 0.75,
              display: "flex",
              alignItems: "center",
              gap: "5px",
            }}
          >
            <Sparkles size={12} />
            Recommended Execution Mode
          </p>
          <p
            style={{
              fontSize: "24px",
              fontWeight: 800,
              color: colors.text,
              lineHeight: 1.2,
              letterSpacing: "-0.02em",
              marginTop: "2px",
            }}
          >
            {modeLabel(rec.mode)}
          </p>
        </div>
        <div
          style={{
            marginLeft: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "6px",
            alignItems: "flex-end",
          }}
        >
          <ApprovalBadge status={rec.mode_approval_status} />
          <ConfidenceBadge confidence={rec.evidence_confidence} />
        </div>
      </div>

      <p
        style={{
          fontSize: "14px",
          color: colors.text,
          opacity: 0.9,
          lineHeight: 1.6,
          fontWeight: 500,
        }}
      >
        {modeDescription(rec.mode)}
      </p>

      {rec.mode_rationale && (
        <div
          style={{
            background: "var(--color-surface)",
            borderRadius: "var(--radius)",
            border: "1px solid var(--color-border)",
            padding: "12px 16px",
            fontSize: "13.5px",
            color: "var(--color-text)",
            lineHeight: 1.65,
            boxShadow: "var(--shadow-xs)",
          }}
        >
          <strong style={{ color: colors.text }}>AI Model Rationale: </strong>
          <span>{rec.mode_rationale}</span>
        </div>
      )}

      {rec.mode_approval_status === "approved" && (
        <div
          style={{
            display: "flex",
            gap: "8px",
            fontSize: "12.5px",
            color: "var(--color-green-text)",
            alignItems: "center",
            background: "var(--color-green-bg)",
            border: "1px solid var(--color-green-border)",
            padding: "8px 12px",
            borderRadius: "var(--radius)",
          }}
        >
          <CheckCircle2 size={15} style={{ color: "var(--color-green)" }} />
          <span>
            Mode approved by <strong>{rec.mode_approved_by}</strong> on{" "}
            {formatDate(rec.mode_approved_at)}
          </span>
        </div>
      )}

      {rec.mode_approval_status === "overridden" && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "4px",
            fontSize: "12.5px",
            color: "var(--color-amber-text)",
            background: "var(--color-amber-bg)",
            border: "1px solid var(--color-amber-border)",
            padding: "8px 12px",
            borderRadius: "var(--radius)",
          }}
        >
          <span style={{ display: "flex", gap: "6px", alignItems: "center" }}>
            <AlertTriangle size={15} style={{ color: "var(--color-amber)" }} />
            Overridden by <strong>{rec.mode_approved_by}</strong> on{" "}
            {formatDate(rec.mode_approved_at)}
          </span>
          {rec.mode_override_reason && (
            <span
              style={{
                paddingLeft: "21px",
                color: "var(--color-text-secondary)",
              }}
            >
              Reason: {rec.mode_override_reason}
            </span>
          )}
        </div>
      )}

      {rec.uncertainty_note && (
        <div
          style={{
            background: "var(--color-surface-subtle)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius)",
            padding: "10px 14px",
            fontSize: "12.5px",
            color: "var(--color-text-muted)",
            display: "flex",
            gap: "8px",
            alignItems: "flex-start",
          }}
        >
          <Info
            size={14}
            style={{
              flexShrink: 0,
              marginTop: "2px",
              color: "var(--color-accent)",
            }}
          />
          <span>{rec.uncertainty_note}</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Evidence list
// ---------------------------------------------------------------------------

function EvidenceList({ items }: { items: EvidenceItem[] }) {
  if (!items || items.length === 0) {
    return (
      <p
        style={{
          fontSize: "13px",
          color: "var(--color-text-faint)",
          fontStyle: "italic",
        }}
      >
        No evidence recorded.
      </p>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      {items.map((item, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            gap: "10px",
            alignItems: "flex-start",
            padding: "10px 12px",
            background: item.verified
              ? "var(--color-green-bg)"
              : "var(--color-surface-subtle)",
            border: `1px solid ${item.verified ? "var(--color-green-border)" : "var(--color-border)"}`,
            borderRadius: "var(--radius)",
            fontSize: "13px",
          }}
        >
          <span
            style={{
              flexShrink: 0,
              marginTop: "1px",
              color: item.verified
                ? "var(--color-green)"
                : "var(--color-text-faint)",
            }}
          >
            {item.verified ? <CheckCircle2 size={15} /> : <Clock size={15} />}
          </span>
          <span style={{ flex: 1, minWidth: 0, lineHeight: 1.5 }}>
            <span
              style={{
                color: "var(--color-text-muted)",
                fontSize: "11px",
                fontWeight: 700,
                marginRight: "6px",
                textTransform: "uppercase",
              }}
            >
              [{item.source}]
            </span>
            {item.description}
          </span>
          {!item.verified && (
            <Badge variant="amber" style={{ flexShrink: 0 }}>
              unverified
            </Badge>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Risk list
// ---------------------------------------------------------------------------

function RiskList({ items }: { items: RiskItem[] }) {
  if (!items || items.length === 0) {
    return (
      <p
        style={{
          fontSize: "13px",
          color: "var(--color-text-faint)",
          fontStyle: "italic",
        }}
      >
        No risks identified.
      </p>
    );
  }

  const severityIcon = (s: string) => {
    if (s === "high")
      return <XCircle size={15} style={{ color: "var(--color-red)" }} />;
    if (s === "medium")
      return (
        <AlertTriangle size={15} style={{ color: "var(--color-amber)" }} />
      );
    return <Info size={15} style={{ color: "var(--color-text-muted)" }} />;
  };

  const severityBg = (s: string) => {
    if (s === "high")
      return { bg: "var(--color-red-bg)", border: "var(--color-red-border)" };
    if (s === "medium")
      return {
        bg: "var(--color-amber-bg)",
        border: "var(--color-amber-border)",
      };
    return { bg: "var(--color-surface-subtle)", border: "var(--color-border)" };
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      {items.map((item, i) => {
        const c = severityBg(item.severity);
        return (
          <div
            key={i}
            style={{
              display: "flex",
              gap: "10px",
              alignItems: "flex-start",
              padding: "10px 14px",
              background: c.bg,
              border: `1px solid ${c.border}`,
              borderRadius: "var(--radius)",
              fontSize: "13px",
            }}
          >
            <span style={{ flexShrink: 0, marginTop: "1px" }}>
              {severityIcon(item.severity)}
            </span>
            <span
              style={{ flex: 1, color: "var(--color-text)", lineHeight: 1.5 }}
            >
              {item.description}
            </span>
            <Badge
              variant={
                item.severity === "high"
                  ? "red"
                  : item.severity === "medium"
                    ? "amber"
                    : "gray"
              }
              style={{ flexShrink: 0, textTransform: "capitalize" }}
            >
              {item.severity} severity
            </Badge>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Readiness panel
// ---------------------------------------------------------------------------

function ReadinessPanel({ rec }: { rec: Recommendation }) {
  const r = rec.ticket_readiness;

  if (!r) {
    return (
      <Card padding="md">
        <SectionHeading>Ticket Readiness Scorecard</SectionHeading>
        <p
          style={{
            fontSize: "13px",
            color: "var(--color-text-faint)",
            fontStyle: "italic",
          }}
        >
          Readiness assessment not available — no data was returned by the
          backend for this recommendation.
        </p>
      </Card>
    );
  }

  const statusColor =
    {
      ready: "var(--color-green)",
      ready_with_gaps: "var(--color-amber)",
      not_ready: "var(--color-red)",
      not_assessed: "var(--color-text-muted)",
    }[r.overall_status] ?? "var(--color-text-muted)";

  const statusIcon = {
    ready: <CheckCircle2 size={16} />,
    ready_with_gaps: <AlertTriangle size={16} />,
    not_ready: <XCircle size={16} />,
    not_assessed: <Clock size={16} />,
  }[r.overall_status] ?? <Clock size={16} />;

  return (
    <Card padding="lg">
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "14px",
          flexWrap: "wrap",
          gap: "8px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <SectionHeading style={{ margin: 0 } as React.CSSProperties}>
            <ShieldCheck size={14} style={{ color: "var(--color-accent)" }} />
            Ticket Readiness Scorecard
          </SectionHeading>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "5px",
              fontSize: "13px",
              color: statusColor,
              fontWeight: 700,
              textTransform: "capitalize",
            }}
          >
            {statusIcon}
            {r.overall_status.replace(/_/g, " ")}
          </span>
        </div>

        {r.llm_confidence && (
          <Badge
            variant={
              r.llm_confidence === "high"
                ? "green"
                : r.llm_confidence === "medium"
                  ? "blue"
                  : "amber"
            }
          >
            {r.llm_confidence} confidence
          </Badge>
        )}
      </div>

      {r.summary && (
        <p
          style={{
            fontSize: "13.5px",
            lineHeight: 1.65,
            color: "var(--color-text-secondary)",
            marginBottom: "14px",
          }}
        >
          {r.summary}
        </p>
      )}

      {/* Auto vs Human Gap KPI bar */}
      {(r.auto_resolvable_gaps > 0 || r.human_required_gaps > 0) && (
        <div
          style={{
            display: "flex",
            gap: "12px",
            marginBottom: "14px",
            padding: "10px 14px",
            background: "var(--color-surface-subtle)",
            borderRadius: "var(--radius)",
            border: "1px solid var(--color-border)",
            flexWrap: "wrap",
          }}
        >
          {r.auto_resolvable_gaps > 0 && (
            <span
              style={{
                fontSize: "12.5px",
                color: "var(--color-green-text)",
                fontWeight: 600,
              }}
            >
              <CheckCircle2
                size={13}
                style={{ display: "inline", marginRight: "5px" }}
              />
              {r.auto_resolvable_gaps} gap
              {r.auto_resolvable_gaps !== 1 ? "s" : ""} auto-resolvable by Bob
            </span>
          )}
          {r.human_required_gaps > 0 && (
            <span
              style={{
                fontSize: "12.5px",
                color: "var(--color-amber-text)",
                fontWeight: 600,
              }}
            >
              <User
                size={13}
                style={{ display: "inline", marginRight: "5px" }}
              />
              {r.human_required_gaps} gap
              {r.human_required_gaps !== 1 ? "s" : ""} require human
              clarification
            </span>
          )}
        </div>
      )}

      {/* Detailed Readiness Checks list if available */}
      {r.checks && r.checks.length > 0 && (
        <div style={{ marginBottom: "14px" }}>
          <SectionHeading>
            Automated Readiness Checks ({r.checks.length})
          </SectionHeading>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {r.checks.map((chk, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  borderRadius: "var(--radius)",
                  background: "var(--color-surface-subtle)",
                  border: "1px solid var(--color-border)",
                  fontSize: "13px",
                }}
              >
                <div
                  style={{ display: "flex", alignItems: "center", gap: "8px" }}
                >
                  {chk.status === "pass" && (
                    <CheckCircle2
                      size={14}
                      style={{ color: "var(--color-green)" }}
                    />
                  )}
                  {chk.status === "warn" && (
                    <AlertTriangle
                      size={14}
                      style={{ color: "var(--color-amber)" }}
                    />
                  )}
                  {chk.status === "fail" && (
                    <XCircle size={14} style={{ color: "var(--color-red)" }} />
                  )}
                  <span style={{ fontWeight: 600, color: "var(--color-text)" }}>
                    {chk.name}
                  </span>
                  {chk.details && (
                    <span
                      style={{
                        fontSize: "12px",
                        color: "var(--color-text-muted)",
                      }}
                    >
                      — {chk.details}
                    </span>
                  )}
                </div>
                <div
                  style={{ display: "flex", gap: "6px", alignItems: "center" }}
                >
                  {chk.can_auto_resolve && (
                    <Badge variant="blue" style={{ fontSize: "10.5px" }}>
                      Auto-resolvable
                    </Badge>
                  )}
                  <Badge
                    variant={
                      chk.status === "pass"
                        ? "green"
                        : chk.status === "warn"
                          ? "amber"
                          : "red"
                    }
                    style={{ textTransform: "uppercase", fontSize: "10.5px" }}
                  >
                    {chk.status}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Blocking Gaps */}
      {r.blocking_gaps && r.blocking_gaps.length > 0 && (
        <div style={{ marginBottom: "14px" }}>
          <SectionHeading>
            Blocking Gaps ({r.blocking_gaps.length})
          </SectionHeading>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {(r.blocking_gaps as string[]).map((g, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  gap: "8px",
                  alignItems: "flex-start",
                  fontSize: "13px",
                  color: "var(--color-red-text)",
                  padding: "8px 12px",
                  background: "var(--color-red-bg)",
                  border: "1px solid var(--color-red-border)",
                  borderRadius: "var(--radius)",
                }}
              >
                <XCircle
                  size={14}
                  style={{
                    flexShrink: 0,
                    marginTop: "2px",
                    color: "var(--color-red)",
                  }}
                />
                <span>{g}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Needed Context */}
      {r.needed_context && r.needed_context.length > 0 && (
        <div>
          <SectionHeading>Missing Context Needed Before Start</SectionHeading>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {(r.needed_context as string[]).map((c, i) => (
              <div
                key={i}
                style={{
                  fontSize: "13px",
                  color: "var(--color-amber-text)",
                  padding: "8px 12px",
                  background: "var(--color-amber-bg)",
                  borderRadius: "var(--radius)",
                  border: "1px solid var(--color-amber-border)",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "8px",
                }}
              >
                <Info
                  size={14}
                  style={{
                    color: "var(--color-amber)",
                    flexShrink: 0,
                    marginTop: "2px",
                  }}
                />
                <span>{c}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Evidence tabs
// ---------------------------------------------------------------------------

type EvidenceTab = "historical" | "prs" | "risks" | "uncertainty";

function EvidenceInspector({ rec }: { rec: Recommendation }) {
  const [tab, setTab] = useState<EvidenceTab>("historical");

  const tabs: {
    id: EvidenceTab;
    label: string;
    icon: React.ReactNode;
    count?: number;
  }[] = [
    {
      id: "historical",
      label: "Similar Tickets",
      icon: <History size={14} />,
      count: rec.similar_tickets?.length,
    },
    {
      id: "prs",
      label: "Pull Requests",
      icon: <GitPullRequest size={14} />,
      count: rec.supporting_prs?.length,
    },
    {
      id: "risks",
      label: "Risks & Counterevidence",
      icon: <ShieldAlert size={14} />,
      count: rec.mode_risks?.length,
    },
    {
      id: "uncertainty",
      label: "Signals & Evidence",
      icon: <HelpCircle size={14} />,
    },
  ];

  return (
    <Card padding="none">
      {/* Tab bar */}
      <div
        role="tablist"
        style={{
          display: "flex",
          borderBottom: "1px solid var(--color-border)",
          background: "var(--color-surface-subtle)",
          padding: "4px 8px 0",
          overflowX: "auto",
          borderTopLeftRadius: "var(--radius-lg)",
          borderTopRightRadius: "var(--radius-lg)",
        }}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "10px 16px",
              fontSize: "13px",
              fontWeight: tab === t.id ? 700 : 500,
              color:
                tab === t.id
                  ? "var(--color-accent)"
                  : "var(--color-text-muted)",
              borderBottom:
                tab === t.id
                  ? "2px solid var(--color-accent)"
                  : "2px solid transparent",
              background: tab === t.id ? "var(--color-surface)" : "transparent",
              borderTopLeftRadius: "6px",
              borderTopRightRadius: "6px",
              cursor: "pointer",
              whiteSpace: "nowrap",
              marginBottom: "-1px",
              transition: "all 0.15s ease",
            }}
          >
            {t.icon}
            <span>{t.label}</span>
            {t.count !== undefined && t.count > 0 && (
              <span
                style={{
                  background:
                    tab === t.id
                      ? "var(--color-accent-bg)"
                      : "var(--color-border)",
                  color:
                    tab === t.id
                      ? "var(--color-accent)"
                      : "var(--color-text-muted)",
                  borderRadius: "9999px",
                  padding: "1px 7px",
                  fontSize: "11px",
                  fontWeight: 700,
                }}
              >
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab panels */}
      <div style={{ padding: "20px" }} role="tabpanel">
        {tab === "historical" && <HistoricalTicketsPanel rec={rec} />}
        {tab === "prs" && <PRsPanel rec={rec} />}
        {tab === "risks" && <RisksPanel rec={rec} />}
        {tab === "uncertainty" && <UncertaintyPanel rec={rec} />}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Historical tickets panel
// ---------------------------------------------------------------------------

function HistoricalTicketsPanel({ rec }: { rec: Recommendation }) {
  if (!rec.similar_tickets || rec.similar_tickets.length === 0) {
    return (
      <p
        style={{
          fontSize: "13px",
          color: "var(--color-text-faint)",
          fontStyle: "italic",
        }}
      >
        No similar resolved tickets found in the vector/TF-IDF database.
      </p>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      <p style={{ fontSize: "12.5px", color: "var(--color-text-muted)" }}>
        Similarity scores are calculated via TF-IDF cosine similarity based on
        issue text and labels.
      </p>
      {rec.similar_tickets.map((t, i) => (
        <div
          key={i}
          style={{
            padding: "12px 14px",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius)",
            background: "var(--color-surface)",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
            boxShadow: "var(--shadow-xs)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              flexWrap: "wrap",
            }}
          >
            <span
              style={{
                fontFamily: "JetBrains Mono, ui-monospace, monospace",
                fontSize: "12px",
                fontWeight: 700,
                color: "var(--color-text)",
                background: "var(--color-surface-subtle)",
                padding: "2px 6px",
                borderRadius: "4px",
                border: "1px solid var(--color-border)",
              }}
            >
              {t.jira_key}
            </span>
            <span
              style={{
                fontSize: "13.5px",
                fontWeight: 600,
                flex: 1,
                color: "var(--color-text)",
              }}
            >
              {t.title}
            </span>
            <Badge variant="blue" style={{ fontWeight: 700 }}>
              {(t.similarity_score * 100).toFixed(0)}% match
            </Badge>
          </div>

          {/* Similarity progress bar */}
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{ flex: 1 }}>
              <ProgressBar
                value={t.similarity_score * 100}
                height={5}
                color="#2563EB"
              />
            </div>
          </div>

          <div
            style={{
              display: "flex",
              gap: "6px",
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            {t.mode_used && <ModeBadge mode={t.mode_used} />}
            {t.ac_met === true && (
              <Badge variant="green">AC Met in Production</Badge>
            )}
            {t.ac_met === false && <Badge variant="red">AC Not Met</Badge>}
            {t.ac_met === null && <Badge variant="gray">AC Unknown</Badge>}
            {t.resolution && <Badge variant="gray">{t.resolution}</Badge>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// PRs panel
// ---------------------------------------------------------------------------

function PRsPanel({ rec }: { rec: Recommendation }) {
  if (!rec.supporting_prs || rec.supporting_prs.length === 0) {
    return (
      <p
        style={{
          fontSize: "13px",
          color: "var(--color-text-faint)",
          fontStyle: "italic",
        }}
      >
        No pull request evidence linked to this issue or similar resolved
        stories.
      </p>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      {rec.pr_evidence_warnings && rec.pr_evidence_warnings.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          {rec.pr_evidence_warnings.map((w, i) => (
            <WarningBanner key={i} message={w} />
          ))}
        </div>
      )}
      <p style={{ fontSize: "12.5px", color: "var(--color-text-muted)" }}>
        PR telemetry includes merge state, test coverage detection, and revert
        heuristics.
      </p>
      {rec.supporting_prs.map((pr, i) => (
        <div
          key={i}
          style={{
            padding: "12px 14px",
            border: `1px solid ${pr.source_warning ? "var(--color-amber-border)" : "var(--color-border)"}`,
            background: pr.source_warning
              ? "var(--color-amber-bg)"
              : "var(--color-surface)",
            borderRadius: "var(--radius)",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
            boxShadow: "var(--shadow-xs)",
          }}
        >
          <div
            style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}
          >
            <div
              style={{
                padding: "6px",
                borderRadius: "6px",
                background: "var(--color-surface-subtle)",
                color: "var(--color-accent)",
                marginTop: "1px",
              }}
            >
              <GitPullRequest size={15} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              {pr.title && (
                <p
                  style={{
                    fontSize: "13.5px",
                    fontWeight: 600,
                    color: "var(--color-text)",
                  }}
                >
                  {pr.title}
                </p>
              )}
              <a
                href={pr.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  fontSize: "12.5px",
                  color: "var(--color-accent)",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                  marginTop: "2px",
                }}
              >
                <span>{pr.url}</span>
                <ExternalLink size={11} style={{ opacity: 0.6 }} />
              </a>
            </div>
          </div>

          <div
            style={{
              display: "flex",
              gap: "6px",
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            {pr.merged === true && <Badge variant="green">Merged</Badge>}
            {pr.merged === false && <Badge variant="red">Not merged</Badge>}
            {pr.merged === null && <Badge variant="gray">Merge unknown</Badge>}
            {pr.state && <Badge variant="gray">{pr.state}</Badge>}
            {pr.test_files_present === true && (
              <Badge variant="blue">Test files detected</Badge>
            )}
            {pr.was_reverted === true && (
              <Badge variant="red">Revert detected</Badge>
            )}
            {!pr.verified && <Badge variant="amber">Unverified source</Badge>}
          </div>

          {pr.diff_summary && (
            <div
              style={{
                fontSize: "12.5px",
                color: "var(--color-text-secondary)",
                lineHeight: 1.6,
                background: "var(--color-surface-subtle)",
                padding: "8px 12px",
                borderRadius: "6px",
              }}
            >
              <strong>Diff Summary:</strong> {pr.diff_summary}
            </div>
          )}

          {pr.files_changed && pr.files_changed.length > 0 && (
            <details style={{ fontSize: "12px" }}>
              <summary
                style={{
                  cursor: "pointer",
                  color: "var(--color-accent)",
                  fontWeight: 600,
                }}
              >
                {pr.files_changed.length} file
                {pr.files_changed.length !== 1 ? "s" : ""} modified
              </summary>
              <ul
                style={{
                  marginTop: "6px",
                  paddingLeft: "18px",
                  fontSize: "12px",
                  color: "var(--color-text-muted)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "2px",
                  fontFamily: "ui-monospace, monospace",
                  overflow: "hidden",
                  minWidth: 0,
                }}
              >
                {(pr.files_changed as string[]).map((f, j) => (
                  <li
                    key={j}
                    style={{ wordBreak: "break-all", overflowWrap: "anywhere" }}
                  >
                    {f}
                  </li>
                ))}
              </ul>
            </details>
          )}

          {pr.source_warning && (
            <p
              style={{
                fontSize: "11.5px",
                color: "var(--color-amber-text)",
                fontStyle: "italic",
              }}
            >
              Warning: {pr.source_warning}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Risks panel
// ---------------------------------------------------------------------------

function RisksPanel({ rec }: { rec: Recommendation }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
      <div>
        <SectionHeading>Identified Execution Risks</SectionHeading>
        <RiskList items={rec.mode_risks} />
      </div>

      {rec.mode_counterevidence && rec.mode_counterevidence.length > 0 && (
        <div>
          <SectionHeading>Counterevidence Signals</SectionHeading>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {rec.mode_counterevidence.map((item, i) => (
              <div
                key={i}
                style={{
                  padding: "9px 12px",
                  background: "var(--color-amber-bg)",
                  border: "1px solid var(--color-amber-border)",
                  borderRadius: "var(--radius)",
                  fontSize: "13px",
                  color: "var(--color-amber-text)",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "8px",
                }}
              >
                <AlertTriangle
                  size={14}
                  style={{
                    color: "var(--color-amber)",
                    flexShrink: 0,
                    marginTop: "2px",
                  }}
                />
                <span>{item.description}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {rec.code_analysis_notes && (
        <div>
          <SectionHeading>Codebase Analysis Notes</SectionHeading>
          <div
            style={{
              fontSize: "13.5px",
              lineHeight: 1.7,
              color: "var(--color-text)",
              background: "var(--color-surface-subtle)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius)",
              padding: "12px 14px",
            }}
          >
            {rec.code_analysis_notes}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Uncertainty panel
// ---------------------------------------------------------------------------

function UncertaintyPanel({ rec }: { rec: Recommendation }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
      {rec.uncertainty_note ? (
        <div
          style={{
            padding: "12px 14px",
            background: "var(--color-amber-bg)",
            border: "1px solid var(--color-amber-border)",
            borderRadius: "var(--radius)",
            fontSize: "13px",
            lineHeight: 1.6,
          }}
        >
          <p
            style={{
              fontWeight: 700,
              marginBottom: "4px",
              color: "var(--color-amber-text)",
            }}
          >
            Uncertainty Assessment
          </p>
          <p style={{ color: "var(--color-text)" }}>{rec.uncertainty_note}</p>
        </div>
      ) : (
        <p
          style={{
            fontSize: "13px",
            color: "var(--color-text-faint)",
            fontStyle: "italic",
          }}
        >
          No uncertainty note recorded for this recommendation.
        </p>
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
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function RecommendationView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [story, setStory] = useState<Story | null>(null);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [storyLoading, setStoryLoading] = useState(true);
  const [recLoading, setRecLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [storyError, setStoryError] = useState<string | null>(null);
  const [recError, setRecError] = useState<string | null>(null);
  const [genError, setGenError] = useState<string | null>(null);

  // Load story
  useEffect(() => {
    if (!id) return;
    setStoryLoading(true);
    setStoryError(null);
    getStory(id)
      .then((s) => setStory(s))
      .catch((e) => setStoryError(String(e)))
      .finally(() => setStoryLoading(false));
  }, [id]);

  // Load existing recommendation for this story on mount (if any)
  useEffect(() => {
    if (!story) return;
    getRecommendationForStory(story.id)
      .then((existing) => setRec(existing))
      .catch(() => {
        /* no recommendation yet — generate banner will show */
      });
  }, [story?.id]);

  const handleGenerate = useCallback(async () => {
    if (!id) return;
    setGenerating(true);
    setGenError(null);
    try {
      const result = await createRecommendation(id);
      setRec(result);
    } catch (e) {
      setGenError(String(e));
    } finally {
      setGenerating(false);
    }
  }, [id]);

  const handleRefreshRec = useCallback(async () => {
    if (!rec) return;
    setRecLoading(true);
    setRecError(null);
    try {
      const result = await getRecommendation(rec.id);
      setRec(result);
    } catch (e) {
      setRecError(String(e));
    } finally {
      setRecLoading(false);
    }
  }, [rec]);

  const handleApprovalUpdate = useCallback((updated: Recommendation) => {
    setRec(updated);
  }, []);

  const subtitle = story
    ? `${story.jira_key ?? story.id.slice(0, 8)} — ${story.title}`
    : "";

  return (
    <AppShell title="Story Analysis & Recommendation" subtitle={subtitle}>
      {/* Back button */}
      <button
        onClick={() => navigate("/")}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          fontSize: "13px",
          fontWeight: 600,
          color: "var(--color-text-muted)",
          marginBottom: "18px",
          cursor: "pointer",
          background: "none",
          border: "none",
          padding: 0,
        }}
      >
        <ArrowLeft size={15} />
        <span>Back to Story Queue</span>
      </button>

      {storyLoading ? (
        <Card padding="lg">
          <Skeleton height={24} width="40%" style={{ marginBottom: "14px" }} />
          <Skeleton height={16} style={{ marginBottom: "8px" }} />
          <Skeleton height={16} style={{ marginBottom: "8px" }} />
          <Skeleton height={16} width="60%" />
        </Card>
      ) : storyError ? (
        <ErrorBanner message={storyError} />
      ) : story ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Story context */}
          <StoryContext story={story} />

          {/* Un-generated state banner */}
          {!rec && !generating && !genError && (
            <Card
              padding="lg"
              style={{
                textAlign: "center",
                padding: "40px 24px",
                background: "var(--color-card-gradient)",
                border: "1px solid var(--color-accent-border)",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              <div
                style={{
                  width: "52px",
                  height: "52px",
                  borderRadius: "50%",
                  background: "var(--color-accent-bg)",
                  color: "var(--color-accent)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 14px",
                }}
              >
                <Zap size={26} />
              </div>
              <h3
                style={{
                  fontSize: "18px",
                  fontWeight: 700,
                  color: "var(--color-text)",
                  marginBottom: "6px",
                }}
              >
                Generate Bob Execution Recommendation
              </h3>
              <p
                style={{
                  color: "var(--color-text-muted)",
                  fontSize: "13.5px",
                  maxWidth: "520px",
                  margin: "0 auto 20px",
                  lineHeight: 1.6,
                }}
              >
                Run multi-signal autonomous triage. Bob analyzes acceptance
                criteria completeness, historical resolved ticket patterns, PR
                telemetry, and potential codebase risks.
              </p>
              <Button
                variant="primary"
                size="lg"
                onClick={handleGenerate}
                icon={<Zap size={16} />}
              >
                Generate Recommendation
              </Button>
            </Card>
          )}

          {/* Generating loading card */}
          {generating && (
            <Card
              padding="lg"
              style={{
                textAlign: "center",
                padding: "40px 24px",
                background: "var(--color-surface)",
                border: "1px solid var(--color-accent-border)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "12px",
                }}
              >
                <RefreshCw
                  size={28}
                  style={{
                    color: "var(--color-accent)",
                    animation: "spin 1.2s linear infinite",
                  }}
                />
                <p
                  style={{
                    fontWeight: 700,
                    fontSize: "16px",
                    color: "var(--color-text)",
                  }}
                >
                  Synthesizing Autonomous Recommendation…
                </p>
                <p
                  style={{
                    fontSize: "13px",
                    color: "var(--color-text-muted)",
                    maxWidth: "420px",
                    lineHeight: 1.5,
                  }}
                >
                  Invoking IBM Bob Autonomous Agent and cross-referencing TF-IDF
                  embeddings against historical Jira issues and GitHub pull
                  requests.
                </p>
              </div>
            </Card>
          )}

          {genError && (
            <ErrorBanner message={genError} onRetry={handleGenerate} />
          )}

          {/* Active Recommendation Content */}
          {rec && !generating && (
            <>
              {rec.status === "superseded" && (
                <WarningBanner message="This recommendation has been superseded by a newer version for this story." />
              )}

              {/* Mode Hero Banner */}
              <ModeHero rec={rec} />

              {/* Priority Ranking Card */}
              {(rec.priority_rank !== null || rec.priority_rationale) && (
                <Card padding="md">
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "10px",
                    }}
                  >
                    <Award size={16} style={{ color: "var(--color-accent)" }} />
                    <SectionHeading
                      style={{ margin: 0 } as React.CSSProperties}
                    >
                      Backlog Priority Ranking
                    </SectionHeading>
                  </div>

                  <div
                    style={{
                      display: "flex",
                      gap: "16px",
                      alignItems: "center",
                      flexWrap: "wrap",
                    }}
                  >
                    {rec.priority_rank !== null && (
                      <div
                        style={{
                          textAlign: "center",
                          background: "var(--color-accent-bg)",
                          border: "1px solid var(--color-accent-border)",
                          borderRadius: "var(--radius)",
                          padding: "10px 18px",
                          minWidth: "110px",
                        }}
                      >
                        <p
                          style={{
                            fontSize: "28px",
                            fontWeight: 800,
                            color: "var(--color-accent)",
                            lineHeight: 1,
                          }}
                        >
                          #{rec.priority_rank}
                        </p>
                        <p
                          style={{
                            fontSize: "10.5px",
                            color: "var(--color-text-muted)",
                            textTransform: "uppercase",
                            letterSpacing: "0.06em",
                            fontWeight: 700,
                            marginTop: "4px",
                          }}
                        >
                          Rank in Queue
                        </p>
                      </div>
                    )}
                    {rec.priority_rationale && (
                      <p
                        style={{
                          fontSize: "13.5px",
                          color: "var(--color-text-secondary)",
                          lineHeight: 1.6,
                          flex: 1,
                        }}
                      >
                        {rec.priority_rationale}
                      </p>
                    )}
                  </div>
                </Card>
              )}

              {/* Ticket Readiness Scorecard */}
              <ReadinessPanel rec={rec} />

              {/* Evidence Inspector Tabs */}
              <EvidenceInspector rec={rec} />

              {/* Approval Controls */}
              <div style={{ marginTop: "4px" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "8px",
                  }}
                >
                  <SectionHeading style={{ margin: 0 } as React.CSSProperties}>
                    Executive Sign-off &amp; Approval
                  </SectionHeading>
                  {recLoading ? (
                    <span
                      style={{
                        fontSize: "12px",
                        color: "var(--color-text-muted)",
                      }}
                    >
                      Refreshing…
                    </span>
                  ) : (
                    <button
                      onClick={handleRefreshRec}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "5px",
                        fontSize: "12px",
                        color: "var(--color-text-muted)",
                        cursor: "pointer",
                        background: "none",
                        border: "none",
                        padding: "2px 6px",
                      }}
                    >
                      <RefreshCw size={12} />
                      <span>Refresh Recommendation</span>
                    </button>
                  )}
                </div>
                {recError && (
                  <ErrorBanner message={recError} onRetry={handleRefreshRec} />
                )}
                <ApprovalPanel rec={rec} onUpdate={handleApprovalUpdate} />
              </div>

              {/* Regenerate Recommendation */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-end",
                  marginTop: "10px",
                  gap: "4px",
                }}
              >
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleGenerate}
                  loading={generating}
                  icon={<RefreshCw size={13} />}
                >
                  Regenerate Recommendation
                </Button>
                <p
                  style={{ fontSize: "11px", color: "var(--color-text-faint)" }}
                >
                  Regenerating creates a fresh assessment and supersedes the
                  current version.
                  {rec.mode_approval_status !== "pending" &&
                    " Approval status will reset to pending."}
                </p>
              </div>
            </>
          )}
        </div>
      ) : null}
    </AppShell>
  );
}
