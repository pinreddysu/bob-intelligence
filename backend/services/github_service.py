"""
GitHub PR enrichment service — Milestone 4b / 4d.

Responsibilities:
  1. parse_pr_url(url) → (owner, repo, number) or None for invalid URLs.
  2. fetch_pr_evidence(url) → dict with PR metadata, files, patches, and CI
     check results.  Patches are bounded by _MAX_PATCH_CHARS per file and
     _MAX_PATCH_FILES total.  When GITHUB_TOKEN is absent the request is made
     unauthenticated (works for public repos; 60 req/hr rate limit applies).
     When the API call fails, returns partial evidence with source_warning
     populated and all unverifiable fields set to None.  Never invents evidence.
  3. fetch_file_content(owner, repo, path, ref) → (content_excerpt, warning)
     Returns up to _MAX_FILE_CONTENT_CHARS of decoded file content plus any
     warning.  Returns ("", warning) on any failure — never raises.

GITHUB_TOKEN usage:
  - When set: sent as Bearer token; raises rate limit to 5000 req/hr and
    enables access to private repositories.
  - When absent: requests are unauthenticated.  Public repositories are still
    fully accessible at 60 req/hr.  source_warning notes the lower rate limit.
    Private repositories return 404; source_warning advises setting GITHUB_TOKEN.

Patterns used to detect test files (fallback when LLM absent):
  test_*.py  *_test.py  *.spec.js  *.spec.ts  *.test.js  *.test.ts
  Any path containing /test/ or /tests/ as a directory component.

Revert heuristic (was_reverted field):
  True  — PR title contains "revert" (case-insensitive) AND a #N reference.
  False — title is present and does not match.
  None  — title is absent; signal unknown.

  This is a title pattern heuristic only. It does NOT establish that the PR
  was subsequently reverted, nor that the referenced PR is related to any
  historical ticket. Callers and the LLM must treat True as a risk signal,
  not as a confirmed outcome.

API errors handled:
  - Missing GITHUB_TOKEN → unauthenticated request; advisory source_warning added.
  - 401 / 403           → source_warning (auth error).
  - 404                 → source_warning (repo inaccessible or PR not found).
  - Other 4xx / 5xx     → source_warning (API error with status code).
  - Network / timeout   → source_warning (network error).

Design constraints:
  - merged=True does NOT imply AC were met.
  - Patches are transient context for the LLM; they are NOT persisted to DB.
  - Binary files are detected and skipped with a note in source_warning.
  - Rate-limit responses (403 with x-ratelimit-remaining: 0) are identified.
"""

from __future__ import annotations

import base64
import binascii
import os
import re
from typing import Any
from urllib.parse import quote

import httpx

# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

_PR_URL_RE = re.compile(
    r"https://github\.com/(?P<owner>[\w.\-]+)/(?P<repo>[\w.\-]+)/pull/(?P<number>\d+)/?$"
)

# Revert detection: title contains "revert" AND a PR-number reference like #42
_REVERT_RE = re.compile(r"\brevert\b", re.IGNORECASE)
_PR_REF_RE = re.compile(r"#\d+")

# Test-file patterns
_TEST_FILE_PATTERNS = re.compile(
    r"(^|/)tests?/"                   # any tests/ or test/ directory
    r"|test_[^/]+\.py$"               # test_foo.py
    r"|[^/]+_test\.py$"               # foo_test.py
    r"|[^/]+\.spec\.(js|ts|jsx|tsx)$" # foo.spec.js / ts
    r"|[^/]+\.test\.(js|ts|jsx|tsx)$" # foo.test.js / ts
    ,
    re.IGNORECASE,
)

# Patch / file content limits
_MAX_PATCH_FILES = 10          # maximum number of file patches to include
_MAX_PATCH_CHARS = 2000        # maximum patch characters per file
_MAX_FILE_CONTENT_CHARS = 3000 # maximum source file content chars to return


def parse_pr_url(url: str) -> tuple[str, str, int] | None:
    """
    Parse a GitHub PR URL into (owner, repo, pr_number).
    Returns None for any URL that does not match the expected pattern.
    """
    if not url or not isinstance(url, str):
        return None
    m = _PR_URL_RE.match(url.strip())
    if m is None:
        return None
    return m.group("owner"), m.group("repo"), int(m.group("number"))


def _is_test_file(path: str) -> bool:
    return bool(_TEST_FILE_PATTERNS.search(path))


def _detect_revert(title: str | None) -> bool | None:
    """
    Heuristic revert signal from PR title.
    True  — title contains "revert" + a #N reference.
    False — title is absent, empty, or does not match.
    None  — reserved for callers that explicitly signal unknown; not returned here.
    Treat True as a risk signal only, not definitive evidence.
    """
    if not title:
        return False
    return bool(_REVERT_RE.search(title) and _PR_REF_RE.search(title))


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

_GH_API = "https://api.github.com"
_TIMEOUT = 15.0  # seconds


def _gh_headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _partial_evidence(url: str, warning: str) -> dict[str, Any]:
    """Return a minimal evidence dict when full enrichment is not possible."""
    return {
        "url": url,
        "title": None,
        "state": None,
        "merged": None,
        "base_branch": None,
        "head_branch": None,
        "files_changed": [],
        "patches": [],
        # None = unavailable/failed; [] = fetched successfully, none configured
        "ci_checks": None,
        "ci_checks_available": False,
        "test_files_present": None,
        "was_reverted": None,
        "diff_summary": None,
        "code_analysis_notes": None,
        "source": "github_api",
        "source_warning": warning,
        "verified": False,
    }


def fetch_pr_evidence(url: str) -> dict[str, Any]:
    """
    Fetch PR metadata, file list (with patches), and CI check results from GitHub.

    Returns a dict suitable for use as PR evidence:
        url, title, state, merged, base_branch, head_branch,
        files_changed (list[str]), patches (list[dict] — transient, not persisted),
        test_files_present (bool|None), was_reverted (bool|None),
        ci_checks (list[dict]), diff_summary (None — populated by llm_service),
        code_analysis_notes (None — populated by llm_service),
        source, source_warning (str|None), verified (bool)

    patches is a list of dicts: {"filename": str, "patch": str}
    Each patch is bounded to _MAX_PATCH_CHARS characters.
    At most _MAX_PATCH_FILES patches are included.
    Binary files are skipped.
    patches is transient context for the LLM — it is NOT stored in PREvidence.

    On any failure the dict has verified=False and source_warning set.
    Never raises — all errors are captured as source_warning.
    """
    parsed = parse_pr_url(url)
    if parsed is None:
        return _partial_evidence(
            url,
            f"Invalid or unrecognised GitHub PR URL: {url!r}. "
            "Expected format: https://github.com/owner/repo/pull/N",
        )

    owner, repo, number = parsed
    token = os.getenv("GITHUB_TOKEN", "").strip()
    # _gh_headers() includes the token when present; omits it when absent.
    headers = _gh_headers()

    # ── PR metadata ──────────────────────────────────────────────────────────
    o, r = quote(owner, safe=""), quote(repo, safe="")
    pr_api_url = f"{_GH_API}/repos/{o}/{r}/pulls/{number}"
    try:
        pr_resp = httpx.get(pr_api_url, headers=headers, timeout=_TIMEOUT)
    except httpx.RequestError as exc:
        return _partial_evidence(url, f"Network error fetching PR metadata: {exc}")

    if pr_resp.status_code == 401:
        return _partial_evidence(url, "GitHub API returned 401 — GITHUB_TOKEN is invalid or expired.")
    if pr_resp.status_code == 403:
        if pr_resp.headers.get("x-ratelimit-remaining") == "0":
            return _partial_evidence(
                url,
                f"GitHub rate limit exhausted for {owner}/{repo}. "
                "Set GITHUB_TOKEN in .env to raise the limit to 5000 req/hr."
            )
        return _partial_evidence(url, f"GitHub API returned 403 — {owner}/{repo} is not accessible.")
    if pr_resp.status_code == 404:
        no_token_hint = (
            " Repository may be private — set GITHUB_TOKEN in .env to access private repos."
            if not token else ""
        )
        return _partial_evidence(
            url,
            f"GitHub PR not found: {owner}/{repo}/pull/{number} (404).{no_token_hint}"
        )
    if not pr_resp.is_success:
        return _partial_evidence(
            url, f"GitHub API returned HTTP {pr_resp.status_code} for {owner}/{repo}/pull/{number}."
        )
    try:
        pr_data_raw = pr_resp.json()
    except Exception:  # noqa: BLE001
        return _partial_evidence(url, "GitHub returned non-JSON for PR metadata.")
    if not isinstance(pr_data_raw, dict):
        return _partial_evidence(
            url,
            f"GitHub returned unexpected type for PR metadata: {type(pr_data_raw).__name__}.",
        )
    pr_data: dict[str, Any] = pr_data_raw

    # ── File list + patches (one page; files_changed always populated) ────────
    files_url = f"{_GH_API}/repos/{o}/{r}/pulls/{number}/files"
    file_paths: list[str] = []
    patches: list[dict[str, str]] = []
    files_warning: str | None = None
    try:
        files_resp = httpx.get(files_url, headers=headers, params={"per_page": 100}, timeout=_TIMEOUT)
        if files_resp.is_success:
            try:
                raw_files_raw = files_resp.json()
            except Exception:  # noqa: BLE001
                raw_files_raw = None
                files_warning = "GitHub returned non-JSON for PR file list."
            if raw_files_raw is None:
                raw_files: list[dict] = []
            elif not isinstance(raw_files_raw, list):
                files_warning = (
                    f"GitHub returned unexpected type for PR file list: "
                    f"{type(raw_files_raw).__name__}."
                )
                raw_files = []
            else:
                raw_files = raw_files_raw
            for f in raw_files:
                if not isinstance(f, dict):
                    continue
                fname = f.get("filename")
                if not isinstance(fname, str) or not fname:
                    continue
                file_paths.append(fname)
                # patch is absent for binary / oversized files — files_changed
                # still records the filename; patches only covers text diffs.
                raw_patch = f.get("patch")
                if isinstance(raw_patch, str) and raw_patch and len(patches) < _MAX_PATCH_FILES:
                    patches.append({"filename": fname, "patch": raw_patch[:_MAX_PATCH_CHARS]})
            # Warn when the PR has more files than one page covers
            total_changed = pr_data.get("changed_files")
            if isinstance(total_changed, int) and total_changed > len(raw_files):
                omitted = total_changed - len(raw_files)
                files_warning = (
                    f"PR reports {total_changed} changed files; only {len(raw_files)} "
                    f"returned in one page ({omitted} omitted). "
                    "Patch selection covers the first page only."
                )
        else:
            files_warning = (
                f"Could not fetch file list (HTTP {files_resp.status_code}); "
                "files_changed will be empty."
            )
    except httpx.RequestError as exc:
        files_warning = f"Network error fetching PR file list: {exc}"

    # ── CI checks — distinguish unavailable from "none configured" ────────────
    head_sha: str = ((pr_data.get("head") or {}).get("sha") or "").strip()
    ci_checks: list[dict] | None = None   # None = unavailable; [] = fetched, none found
    ci_checks_available = False
    ci_warning: str | None = None
    if head_sha:
        checks_url = f"{_GH_API}/repos/{o}/{r}/commits/{head_sha}/check-runs"
        try:
            ci_resp = httpx.get(checks_url, headers=headers, timeout=_TIMEOUT)
            if ci_resp.is_success:
                try:
                    ci_raw = ci_resp.json()
                except Exception:  # noqa: BLE001
                    ci_warning = "GitHub returned non-JSON for CI check-runs."
                    ci_raw = None
                if ci_raw is not None:
                    if not isinstance(ci_raw, dict):
                        ci_warning = (
                            f"GitHub returned unexpected type for CI check-runs: "
                            f"{type(ci_raw).__name__}."
                        )
                    else:
                        runs = ci_raw.get("check_runs", [])
                        if not isinstance(runs, list):
                            ci_warning = "Unexpected 'check_runs' value in CI response."
                        else:
                            ci_checks = [
                                {
                                    "name": run.get("name"),
                                    "status": run.get("status"),
                                    # conclusion="success" does NOT mean AC were met
                                    "conclusion": run.get("conclusion"),
                                }
                                for run in runs
                                if isinstance(run, dict)
                            ]
                            ci_checks_available = True
            else:
                ci_warning = (
                    f"Could not fetch CI checks (HTTP {ci_resp.status_code}); "
                    "ci_checks unavailable."
                )
        except httpx.RequestError as exc:
            ci_warning = f"Network error fetching CI checks: {exc}"
    else:
        ci_warning = "head SHA absent in PR metadata — CI checks not fetched."

    # ── Compose ──────────────────────────────────────────────────────────────
    title: str = (pr_data.get("title") or "").strip()
    merged: bool | None = (
        pr_data.get("merged") if "merged" in pr_data
        else pr_data.get("merged_at") is not None
    )
    base_branch: str | None = (pr_data.get("base") or {}).get("ref") or None
    head_branch: str | None = (pr_data.get("head") or {}).get("ref") or None
    state: str | None = pr_data.get("state") or None
    test_files_present: bool | None = (
        any(_is_test_file(p) for p in file_paths) if file_paths else None
    )
    # Pass title or None so _detect_revert returns None (unknown) for empty titles
    was_reverted = _detect_revert(title or None)

    all_warnings = [w for w in [files_warning, ci_warning] if w]
    source_warning = "; ".join(all_warnings) if all_warnings else None
    # verified=True when the file list was fetched successfully.
    # Public repos are accessible without a token; no penalty for missing token
    # when the API call succeeded.  Token absence is only surfaced on 404/403/rate-limit.
    verified = files_warning is None

    return {
        "url": url,
        "title": title or None,
        "state": state,
        "merged": merged,
        "base_branch": base_branch,
        "head_branch": head_branch,
        "files_changed": file_paths,
        "patches": patches,               # transient — NOT persisted to PREvidence
        "ci_checks": ci_checks,           # None = unavailable; [] = none configured
        "ci_checks_available": ci_checks_available,
        "test_files_present": test_files_present,
        "was_reverted": was_reverted,     # bool | None — heuristic only
        "diff_summary": None,             # populated by llm_service
        "code_analysis_notes": None,      # populated by llm_service
        "source": "github_api",
        "source_warning": source_warning,
        "verified": verified,
    }


# ---------------------------------------------------------------------------
# Current source file fetching
# ---------------------------------------------------------------------------

def fetch_file_content(
    owner: str,
    repo: str,
    path: str,
    ref: str,
) -> tuple[str, str | None]:
    """
    Fetch a single file's decoded UTF-8 content from the GitHub Contents API.

    Returns (content_excerpt, warning_or_None).
    - excerpt ≤ _MAX_FILE_CONTENT_CHARS characters.
    - Returns ("", warning) on every failure — never raises.
    - An empty return means content is UNAVAILABLE, not that the file is empty.

    ref is used exactly as supplied.  The caller must choose the correct
    revision; this function never substitutes a default silently.
    owner, repo, and path segments are URL-encoded before use.
    """
    # GITHUB_TOKEN is optional for public repos — unauthenticated requests are
    # permitted but subject to a lower rate limit (60 req/hour).
    headers = _gh_headers()
    o, r = quote(owner, safe=""), quote(repo, safe="")
    safe_path = "/".join(quote(seg, safe="") for seg in path.split("/"))
    contents_url = f"{_GH_API}/repos/{o}/{r}/contents/{safe_path}"

    try:
        resp = httpx.get(contents_url, headers=headers, params={"ref": ref}, timeout=_TIMEOUT)
    except httpx.RequestError as exc:
        return "", f"Network error fetching {path!r} at ref {ref!r}: {exc}"

    if resp.status_code == 401:
        return "", f"GitHub API returned 401 fetching {path!r} — token invalid or expired."
    if resp.status_code == 403:
        if resp.headers.get("x-ratelimit-remaining") == "0":
            return "", f"GitHub rate limit exhausted fetching {path!r}."
        return "", f"GitHub API returned 403 fetching {path!r} — access denied."
    if resp.status_code == 404:
        return (
            "",
            f"File not found: {path!r} at ref {ref!r} in {owner}/{repo} (404). "
            "Check the path and ref are correct.",
        )
    if not resp.is_success:
        return (
            "",
            f"GitHub API returned HTTP {resp.status_code} fetching {path!r} "
            f"at ref {ref!r} in {owner}/{repo}.",
        )

    try:
        data: Any = resp.json()
    except Exception:  # noqa: BLE001
        return "", f"GitHub returned non-JSON for {path!r} at ref {ref!r}."

    if isinstance(data, list):
        return "", f"Path {path!r} is a directory, not a file."
    if not isinstance(data, dict):
        return "", f"Unexpected response type for {path!r}: {type(data).__name__}."

    raw_content: str = data.get("content") or ""
    # Files too large: GitHub omits content and provides download_url instead
    if not raw_content and data.get("download_url"):
        size = data.get("size", "unknown")
        return (
            "",
            f"File {path!r} ({size} bytes) is too large for the Contents API at ref {ref!r}.",
        )

    encoding = data.get("encoding")
    if encoding != "base64" or not raw_content:
        return "", f"Unexpected encoding {encoding!r} for {path!r} — cannot decode."

    try:
        decoded = base64.b64decode(raw_content).decode("utf-8")
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        return "", f"File {path!r} at ref {ref!r} is binary or non-UTF-8 — skipping: {exc}"

    excerpt = decoded[:_MAX_FILE_CONTENT_CHARS]
    warning: str | None = (
        f"File {path!r} truncated to {_MAX_FILE_CONTENT_CHARS} chars "
        f"(full size: {len(decoded)} chars)."
        if len(decoded) > _MAX_FILE_CONTENT_CHARS else None
    )
    return excerpt, warning
