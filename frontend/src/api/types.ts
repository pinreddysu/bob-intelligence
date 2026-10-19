/**
 * TypeScript types derived from the Bob Intelligence Pydantic schemas.
 * Keep in sync with backend/schemas.py.
 */

// ---------------------------------------------------------------------------
// Story
// ---------------------------------------------------------------------------

export interface Story {
  id: string
  jira_key: string | null
  title: string
  description: string | null
  acceptance_criteria: string | null
  story_points: number | null
  labels: string[]
  priority: string | null
  status: string | null
  assignee: string | null
  blockers: string[]
  linked_prs: string[]
  source: string
  created_at: string
}

export interface StoryListResponse {
  stories: Story[]
  total: number
}

export interface StoryImportResponse {
  stories: Story[]
  source_status: 'jira' | 'sample_import' | 'credentials_missing' | 'jira_error'
  source_warning: string | null
  skipped_duplicates: number
}

// ---------------------------------------------------------------------------
// Recommendation
// ---------------------------------------------------------------------------

export type ExecutionMode = 'bob_led' | 'collaborative' | 'human_led'
export type ApprovalStatus = 'pending' | 'approved' | 'overridden'
export type EvidenceConfidence = 'high' | 'medium' | 'low' | 'none'

export interface EvidenceItem {
  source: string
  description: string
  verified: boolean
}

export interface RiskItem {
  description: string
  severity: 'low' | 'medium' | 'high'
}

export interface CounterEvidenceItem {
  description: string
}

export interface SimilarTicketItem {
  jira_key: string
  title: string
  similarity_score: number
  resolution: string | null
  mode_used: string | null
  ac_met: boolean | null
}

export interface SupportingPRItem {
  url: string
  merged: boolean | null
  files_changed: string[]
  title: string | null
  state: string | null
  test_files_present: boolean | null
  was_reverted: boolean | null
  ci_checks: unknown[]
  diff_summary: string | null
  source_warning: string | null
  verified: boolean
}

export interface ReadinessCheckResult {
  name: string
  status: 'pass' | 'warn' | 'fail'
  can_auto_resolve: boolean
  details: string
  missing_items: string[]
}

export interface RetrievabilityNote {
  item: string
  auto: boolean
  reason: string
}

export interface TicketReadiness {
  overall_status: 'ready' | 'ready_with_gaps' | 'not_ready' | 'not_assessed'
  summary: string
  sufficiency_verdict: string | null
  llm_recommended_mode: string | null
  llm_confidence: string | null
  blocking_gaps: string[]
  evidence_relevance: string | null
  evidence_relevance_reason: string | null
  needed_context: string[]
  retrievability_notes: RetrievabilityNote[]
  auto_resolvable_gaps: number
  human_required_gaps: number
  checks: ReadinessCheckResult[]
}

export interface Recommendation {
  id: string
  story_id: string

  // Priority
  priority_rank: number | null
  priority_rationale: string | null
  priority_evidence: EvidenceItem[]

  // Mode
  mode: ExecutionMode | null
  mode_rationale: string | null
  mode_evidence: EvidenceItem[]
  mode_risks: RiskItem[]
  mode_counterevidence: CounterEvidenceItem[]

  // Mode approval
  mode_approval_status: ApprovalStatus
  mode_approved_by: string | null
  mode_approved_at: string | null
  mode_override_reason: string | null

  // Developer match (deferred – always null/empty)
  suggested_developer: string | null
  dev_match_rationale: string | null
  dev_match_evidence: unknown[]
  dev_match_risks: unknown[]
  is_stretch_assignment: boolean
  stretch_support_plan: string | null
  dev_match_approval_status: string
  dev_match_approved_by: string | null
  dev_match_approved_at: string | null
  dev_match_override_reason: string | null

  // Historical evidence (M4a/M4b)
  similar_tickets: SimilarTicketItem[]
  supporting_prs: SupportingPRItem[]
  evidence_confidence: EvidenceConfidence
  code_analysis_notes: string | null

  // PR warnings
  pr_evidence_warnings: string[]

  // Readiness (M4c)
  ticket_readiness: TicketReadiness | null

  // Shared
  uncertainty_note: string | null
  status: 'pending' | 'superseded'
  created_at: string
}

// ---------------------------------------------------------------------------
// Request bodies
// ---------------------------------------------------------------------------

export interface ModeApproveRequest {
  approved_by: string
}

export interface ModeOverrideRequest {
  approved_by: string
  override_reason: string
  mode?: ExecutionMode
}

// ---------------------------------------------------------------------------
// Resolved tickets (M4a)
// ---------------------------------------------------------------------------

export interface ResolvedTicket {
  id: string
  jira_key: string
  title: string
  description: string | null
  resolution: string | null
  labels: string[]
  linked_prs: string[]
  files_changed: string[]
  mode_used: string | null
  ac_met: boolean | null
  was_reverted: boolean
  source: string
  created_at: string
}

export interface ResolvedTicketListResponse {
  tickets: ResolvedTicket[]
  total: number
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string
}

// ---------------------------------------------------------------------------
// API error shape
// ---------------------------------------------------------------------------

export interface ApiError {
  detail: string | { msg: string; type: string }[]
}
