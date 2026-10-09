#!/usr/bin/env bash
# scripts/smoke_test.sh
#
# Milestone 1 smoke test — verifies the backend health endpoint only.
# Full end-to-end flow (story import → recommendation → Bob session →
# outcome → comparison) will be added in Milestone 7.
#
# Usage:
#   cd bob-intelligence
#   bash scripts/smoke_test.sh
#
# Requirements: curl, a running backend (uvicorn backend.main:app --port 8000)

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "=== Bob Intelligence smoke test ==="
echo "Target: $BASE_URL"
echo ""

# ── Health check ──────────────────────────────────────────────────────────────
echo "--- GET /api/health"
HEALTH=$(curl -sf "$BASE_URL/api/health")
echo "Response: $HEALTH"

if echo "$HEALTH" | grep -q '"status":"ok"'; then
  echo "✓ Health check passed"
else
  echo "✗ Health check FAILED — expected {\"status\":\"ok\"}, got: $HEALTH"
  exit 1
fi

echo ""
echo "=== Milestone 1 smoke test PASSED ==="
echo "Milestones 2-7 will extend this script with the full workflow."
