#!/usr/bin/env bash
# scripts/smoke_test.sh
#
# Milestone 4a smoke test — exercises the full Milestone 3 + 4a flow:
#   1. Health check
#   2. Sample story import
#   3. Sample resolved-ticket import (M4a)
#   4. GET /api/resolved-tickets (M4a)
#   5. Priority + execution-mode recommendation (now includes M4a fields)
#   6. Assert similar_tickets, supporting_prs, evidence_confidence in response
#   7. Jira resolved-ticket import with no credentials → credentials_missing
#   8. Recommendation uncertainty_note for story with no resolved-ticket overlap
#   9. Execution-mode approval gate (PATCH .../mode-approve)
#  10. Override failure path (missing override_reason → assert 422)
#  11. Bob-session gate (409 when pending, 501 after approval)
#  12. Outcomes gate (409 when pending, 501 after approval)
#  13. GET recommendation persists with M4a fields
#
# Runs without Jira credentials.
#
# Usage:
#   cd bob-intelligence
#   bash scripts/smoke_test.sh
#
# Requires: curl, python3, a running backend on $BASE_URL (default http://localhost:8000)

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
PASS=0
FAIL=0

echo "=== Bob Intelligence — Milestone 4a smoke test ==="
echo "Target: $BASE_URL"
echo ""

# ── helpers ───────────────────────────────────────────────────────────────────

check() {
  local label="$1"
  local condition="$2"
  if eval "$condition"; then
    echo "  ✓ $label"
    PASS=$((PASS + 1))
  else
    echo "  ✗ FAILED: $label"
    FAIL=$((FAIL + 1))
  fi
}

# ── 1. Health check ───────────────────────────────────────────────────────────
echo "--- 1. GET /api/health"
HEALTH=$(curl -sf "$BASE_URL/api/health")
echo "  Response: $HEALTH"
check "health returns ok" 'echo "$HEALTH" | grep -q "\"status\":\"ok\""'
echo ""

# ── 2. Sample story import ────────────────────────────────────────────────────
echo "--- 2. POST /api/stories/import (source=sample)"
IMPORT_RESP=$(curl -sf -X POST "$BASE_URL/api/stories/import" \
  -H "Content-Type: application/json" \
  -d '{"import_source":"sample"}')

SOURCE_STATUS=$(echo "$IMPORT_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['source_status'])")
SOURCE_WARNING=$(echo "$IMPORT_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('source_warning') or '')")
STORY_NEW=$(echo "$IMPORT_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['stories']))")
STORY_SKIPPED=$(echo "$IMPORT_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('skipped_duplicates',0))")
STORY_TOTAL=$((STORY_NEW + STORY_SKIPPED))

echo "  source_status: $SOURCE_STATUS"
echo "  source_warning: $SOURCE_WARNING"
echo "  stories new: $STORY_NEW  skipped: $STORY_SKIPPED  total accounted: $STORY_TOTAL"

check "source_status is sample_import" '[ "$SOURCE_STATUS" = "sample_import" ]'
check "source_warning is non-empty" '[ -n "$SOURCE_WARNING" ]'
check "at least one story present (new+skipped)" '[ "$STORY_TOTAL" -ge 1 ]'

# Grab PIE-2 (login endpoint) — has domain overlap with sample resolved tickets.
# Fall back to any story if PIE-2 is not present.
STORY_ID=$(curl -sf "$BASE_URL/api/stories" | python3 -c "
import sys, json
d = json.load(sys.stdin)
stories = d.get('stories', [])
# Prefer PIE-2 (login endpoint) for similarity coverage
pie2 = next((s for s in stories if s.get('jira_key') == 'PIE-2'), None)
print((pie2 or stories[0])['id'] if stories else '')
")
echo "  Using story_id: $STORY_ID"
echo ""

# ── 3. Sample resolved-ticket import (M4a) ───────────────────────────────────
echo "--- 3. POST /api/resolved-tickets/import (source=sample)"
RT_IMPORT=$(curl -sf -X POST "$BASE_URL/api/resolved-tickets/import" \
  -H "Content-Type: application/json" \
  -d '{"source":"sample"}')

RT_SOURCE_STATUS=$(echo "$RT_IMPORT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['source_status'])")
RT_SKIPPED_FIRST=$(echo "$RT_IMPORT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['skipped_duplicates'])")
RT_NEW_FIRST=$(echo "$RT_IMPORT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['tickets']))")
# Count = newly inserted + already-present (skipped on first call due to lifespan seed)
RT_COUNT=$((RT_NEW_FIRST + RT_SKIPPED_FIRST))
echo "  source_status: $RT_SOURCE_STATUS"
echo "  tickets new: $RT_NEW_FIRST  skipped: $RT_SKIPPED_FIRST  total accounted: $RT_COUNT"

check "resolved-tickets source_status is sample_import" '[ "$RT_SOURCE_STATUS" = "sample_import" ]'
check "sample resolved tickets present (new+skipped >= 1)" '[ "$RT_COUNT" -ge 1 ]'

# Idempotency: second import must skip all (everything already in DB)
RT_IMPORT2=$(curl -sf -X POST "$BASE_URL/api/resolved-tickets/import" \
  -H "Content-Type: application/json" \
  -d '{"source":"sample"}')
RT_SKIPPED=$(echo "$RT_IMPORT2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['skipped_duplicates'])")
RT_NEW=$(echo "$RT_IMPORT2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['tickets']))")
echo "  second import: new=$RT_NEW skipped=$RT_SKIPPED"
check "second resolved-ticket import skips all duplicates" '[ "$RT_NEW" = "0" ] && [ "$RT_SKIPPED" -ge 1 ]'
echo ""

# ── 4. GET /api/resolved-tickets (M4a) ───────────────────────────────────────
echo "--- 4. GET /api/resolved-tickets"
RT_LIST=$(curl -sf "$BASE_URL/api/resolved-tickets")
RT_TOTAL=$(echo "$RT_LIST" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['total'])")
echo "  total: $RT_TOTAL"
check "resolved-tickets list has total ≥1" '[ "$RT_TOTAL" -ge 1 ]'
echo ""

# ── 5. Jira resolved-ticket import with no credentials (M4a) ─────────────────
echo "--- 5. POST /api/resolved-tickets/import (source=jira, no credentials)"
RT_JIRA=$(curl -sf -X POST "$BASE_URL/api/resolved-tickets/import" \
  -H "Content-Type: application/json" \
  -d '{"source":"jira"}')
RT_JIRA_STATUS=$(echo "$RT_JIRA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['source_status'])")
echo "  source_status: $RT_JIRA_STATUS"
check "jira resolved-ticket import returns credentials_missing" '[ "$RT_JIRA_STATUS" = "credentials_missing" ]'
echo ""

# ── 6. Generate recommendation ────────────────────────────────────────────────
echo "--- 6. POST /api/recommendations (now includes M4a fields)"
REC_RESP=$(curl -sf -X POST "$BASE_URL/api/recommendations" \
  -H "Content-Type: application/json" \
  -d "{\"story_id\":\"$STORY_ID\"}")

REC_ID=$(echo "$REC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['id'])")
MODE=$(echo "$REC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['mode'])")
MODE_STATUS=$(echo "$REC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['mode_approval_status'])")
PRIORITY_RANK=$(echo "$REC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['priority_rank'])")
UNCERTAINTY=$(echo "$REC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('uncertainty_note') or '')")
MODE_EVIDENCE_COUNT=$(echo "$REC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['mode_evidence']))")
DEV_MATCH=$(echo "$REC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('suggested_developer'))")
SIMILAR_COUNT=$(echo "$REC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('similar_tickets', [])))")
EVIDENCE_CONF=$(echo "$REC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('evidence_confidence','none'))")
SUPPORTING_PRS_COUNT=$(echo "$REC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('supporting_prs', [])))")
CODE_NOTES=$(echo "$REC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('code_analysis_notes'))")

echo "  rec_id: $REC_ID"
echo "  mode: $MODE"
echo "  mode_approval_status: $MODE_STATUS"
echo "  priority_rank: $PRIORITY_RANK"
echo "  uncertainty_note: $UNCERTAINTY"
echo "  mode_evidence items: $MODE_EVIDENCE_COUNT"
echo "  suggested_developer (should be None): $DEV_MATCH"
echo "  similar_tickets count: $SIMILAR_COUNT"
echo "  evidence_confidence: $EVIDENCE_CONF"
echo "  supporting_prs count: $SUPPORTING_PRS_COUNT"
echo "  code_analysis_notes (should be None in M4a): $CODE_NOTES"

check "recommendation has valid mode" '[ "$MODE" = "bob_led" ] || [ "$MODE" = "collaborative" ] || [ "$MODE" = "human_led" ]'
check "mode_approval_status is pending" '[ "$MODE_STATUS" = "pending" ]'
check "priority_rank is set" '[ -n "$PRIORITY_RANK" ] && [ "$PRIORITY_RANK" != "None" ]'
check "mode_evidence is non-empty" '[ "$MODE_EVIDENCE_COUNT" -gt 0 ]'
check "suggested_developer is None (DEFERRED)" '[ "$DEV_MATCH" = "None" ]'
check "similar_tickets is present (list)" 'echo "$REC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d[\"similar_tickets\"], list)"'
check "similar_tickets non-empty (sample tickets imported)" '[ "$SIMILAR_COUNT" -ge 1 ]'
check "evidence_confidence is valid value" '[ "$EVIDENCE_CONF" = "high" ] || [ "$EVIDENCE_CONF" = "medium" ] || [ "$EVIDENCE_CONF" = "low" ] || [ "$EVIDENCE_CONF" = "none" ]'
check "evidence_confidence is not none (sample tickets imported)" '[ "$EVIDENCE_CONF" != "none" ]'
check "supporting_prs is present (list)" 'echo "$REC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d[\"supporting_prs\"], list)"'
check "code_analysis_notes is null in M4a" '[ "$CODE_NOTES" = "None" ]'
echo ""

# ── 7. Override failure path (missing override_reason → 422) ─────────────────
echo "--- 7. PATCH .../mode-override with missing override_reason (expect 422)"
OVERRIDE_NO_REASON_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X PATCH "$BASE_URL/api/recommendations/$REC_ID/mode-override" \
  -H "Content-Type: application/json" \
  -d '{"approved_by":"lead@example.com"}')
echo "  HTTP status (expect 422): $OVERRIDE_NO_REASON_STATUS"
check "missing override_reason returns 422" '[ "$OVERRIDE_NO_REASON_STATUS" = "422" ]'

echo "--- 4b. PATCH .../mode-override with empty override_reason (expect 422)"
OVERRIDE_EMPTY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X PATCH "$BASE_URL/api/recommendations/$REC_ID/mode-override" \
  -H "Content-Type: application/json" \
  -d '{"approved_by":"lead@example.com","override_reason":""}')
echo "  HTTP status (expect 422): $OVERRIDE_EMPTY_STATUS"
check "empty override_reason returns 422" '[ "$OVERRIDE_EMPTY_STATUS" = "422" ]'
echo ""

# ── 5. Bob-session gate — 409 while pending ────────────────────────────────────
echo "--- 5. POST /api/bob-sessions while mode_approval_status=pending (expect 409)"
BOB_PENDING_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$BASE_URL/api/bob-sessions" \
  -H "Content-Type: application/json" \
  -d "{\"story_id\":\"$STORY_ID\",\"summary\":\"test\",\"files_changed\":[]}")
echo "  HTTP status (expect 409): $BOB_PENDING_STATUS"
check "bob-session rejected when pending" '[ "$BOB_PENDING_STATUS" = "409" ]'
echo ""

# ── 6. Outcomes gate — 409 while pending ──────────────────────────────────────
echo "--- 6. POST /api/outcomes while mode_approval_status=pending (expect 409)"
OUTCOME_PENDING_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$BASE_URL/api/outcomes" \
  -H "Content-Type: application/json" \
  -d "{\"story_id\":\"$STORY_ID\",\"test_result\":\"pass\"}")
echo "  HTTP status (expect 409): $OUTCOME_PENDING_STATUS"
check "outcomes rejected when pending" '[ "$OUTCOME_PENDING_STATUS" = "409" ]'
echo ""

# ── 10. Tech lead approves execution mode ────────────────────────────────────
echo "--- 10. PATCH .../mode-approve (tech lead approval)"
APPROVE_RESP=$(curl -sf -X PATCH "$BASE_URL/api/recommendations/$REC_ID/mode-approve" \
  -H "Content-Type: application/json" \
  -d '{"approved_by":"lead@smoke-test.example"}')

APPROVED_STATUS=$(echo "$APPROVE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['mode_approval_status'])")
APPROVED_BY=$(echo "$APPROVE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('mode_approved_by') or '')")
APPROVED_AT=$(echo "$APPROVE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('mode_approved_at') or '')")

echo "  mode_approval_status: $APPROVED_STATUS"
echo "  mode_approved_by: $APPROVED_BY"
echo "  mode_approved_at: $APPROVED_AT"

check "mode_approval_status is approved" '[ "$APPROVED_STATUS" = "approved" ]'
check "mode_approved_by is recorded" '[ -n "$APPROVED_BY" ] && [ "$APPROVED_BY" != "None" ]'
check "mode_approved_at timestamp is recorded" '[ -n "$APPROVED_AT" ] && [ "$APPROVED_AT" != "None" ]'
echo ""

# ── 11. Bob-session gate passes after approval (expect 501) ──────────────────
echo "--- 11. POST /api/bob-sessions after approval (expect 501, not 409)"
BOB_AFTER_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$BASE_URL/api/bob-sessions" \
  -H "Content-Type: application/json" \
  -d "{\"story_id\":\"$STORY_ID\",\"summary\":\"test\",\"files_changed\":[]}")
echo "  HTTP status (expect 501): $BOB_AFTER_STATUS"
check "bob-session gate passes after approval (501 not 409)" '[ "$BOB_AFTER_STATUS" = "501" ]'
echo ""

# ── 12. Outcomes gate passes after approval (expect 501) ─────────────────────
echo "--- 12. POST /api/outcomes after approval (expect 501, not 409)"
OUTCOME_AFTER_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$BASE_URL/api/outcomes" \
  -H "Content-Type: application/json" \
  -d "{\"story_id\":\"$STORY_ID\",\"test_result\":\"pass\"}")
echo "  HTTP status (expect 501): $OUTCOME_AFTER_STATUS"
check "outcomes gate passes after approval (501 not 409)" '[ "$OUTCOME_AFTER_STATUS" = "501" ]'
echo ""

# ── 13. GET recommendation persists with M4a fields ──────────────────────────
echo "--- 13. GET /api/recommendations/$REC_ID (persistence + M4a fields)"
GET_RESP=$(curl -sf "$BASE_URL/api/recommendations/$REC_ID")
GET_STATUS=$(echo "$GET_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['mode_approval_status'])")
GET_CONF=$(echo "$GET_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('evidence_confidence','none'))")
GET_SIM_COUNT=$(echo "$GET_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('similar_tickets', [])))")
echo "  mode_approval_status persisted: $GET_STATUS"
echo "  evidence_confidence persisted: $GET_CONF"
echo "  similar_tickets persisted count: $GET_SIM_COUNT"
check "recommendation persists in DB" '[ "$GET_STATUS" = "approved" ]'
check "evidence_confidence persists" '[ "$GET_CONF" != "" ]'
check "similar_tickets persists" '[ "$GET_SIM_COUNT" -ge 1 ]'
echo ""

# ── Summary ───────────────────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL))
echo "============================================"
echo " Results: $PASS/$TOTAL checks passed"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
  echo "SMOKE TEST FAILED ($FAIL check(s) failed)"
  exit 1
else
  echo "=== Milestone 4a smoke test PASSED ==="
  exit 0
fi
