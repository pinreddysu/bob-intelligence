/**
 * Centralized typed API client for the Bob Intelligence backend.
 *
 * Base URL is read from the VITE_API_BASE_URL environment variable.
 * In development, Vite proxies /api/* to http://localhost:8000 so the
 * variable may be omitted. In production, set it to the backend origin.
 *
 * Never embeds credentials or fabricates responses.
 */

import type {
  HealthResponse,
  StoryListResponse,
  StoryImportResponse,
  Story,
  Recommendation,
  ModeApproveRequest,
  ModeOverrideRequest,
  ResolvedTicketListResponse,
} from './types'

const BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

type HttpMethod = 'GET' | 'POST' | 'PATCH'

async function request<T>(
  method: HttpMethod,
  path: string,
  body?: unknown,
): Promise<T> {
  const url = `${BASE}/api${path}`
  const init: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body !== undefined) {
    init.body = JSON.stringify(body)
  }

  let res: Response
  try {
    res = await fetch(url, init)
  } catch (err) {
    throw new Error(`Network error — could not reach ${url}: ${String(err)}`)
  }

  let json: unknown
  const contentType = res.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    try {
      json = await res.json()
    } catch {
      throw new Error(`JSON parse error from ${url} (HTTP ${res.status})`)
    }
  } else {
    const text = await res.text()
    if (!res.ok) throw new Error(`HTTP ${res.status} from ${url}: ${text}`)
    return text as unknown as T
  }

  if (!res.ok) {
    // FastAPI validation errors have a `detail` array; other errors have a string.
    const detail = (json as { detail?: unknown })?.detail
    if (typeof detail === 'string') throw new Error(detail)
    if (Array.isArray(detail)) {
      const msgs = detail
        .map((e: { msg?: string; loc?: string[] }) =>
          [e.loc?.join('.'), e.msg].filter(Boolean).join(': '),
        )
        .join('; ')
      throw new Error(msgs || `HTTP ${res.status}`)
    }
    throw new Error(`HTTP ${res.status} from ${url}`)
  }

  return json as T
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export async function healthCheck(): Promise<HealthResponse> {
  return request<HealthResponse>('GET', '/health')
}

// ---------------------------------------------------------------------------
// Stories
// ---------------------------------------------------------------------------

export async function listStories(): Promise<StoryListResponse> {
  return request<StoryListResponse>('GET', '/stories')
}

export async function getStory(id: string): Promise<Story> {
  return request<Story>('GET', `/stories/${encodeURIComponent(id)}`)
}

export async function importSampleStories(): Promise<StoryImportResponse> {
  return request<StoryImportResponse>('POST', '/stories/import', {
    import_source: 'sample',
  })
}

export async function importJiraStory(
  jiraKey: string,
): Promise<StoryImportResponse> {
  return request<StoryImportResponse>('POST', '/stories/import', {
    import_source: 'jira',
    jira_key: jiraKey,
  })
}

// ---------------------------------------------------------------------------
// Recommendations
// ---------------------------------------------------------------------------

export async function createRecommendation(
  storyId: string,
): Promise<Recommendation> {
  return request<Recommendation>('POST', '/recommendations', {
    story_id: storyId,
  })
}

export async function getRecommendation(id: string): Promise<Recommendation> {
  return request<Recommendation>(
    'GET',
    `/recommendations/${encodeURIComponent(id)}`,
  )
}

export async function approveMode(
  recId: string,
  body: ModeApproveRequest,
): Promise<Recommendation> {
  return request<Recommendation>(
    'PATCH',
    `/recommendations/${encodeURIComponent(recId)}/mode-approve`,
    body,
  )
}

export async function overrideMode(
  recId: string,
  body: ModeOverrideRequest,
): Promise<Recommendation> {
  return request<Recommendation>(
    'PATCH',
    `/recommendations/${encodeURIComponent(recId)}/mode-override`,
    body,
  )
}

// ---------------------------------------------------------------------------
// Resolved tickets
// ---------------------------------------------------------------------------

export async function listResolvedTickets(): Promise<ResolvedTicketListResponse> {
  return request<ResolvedTicketListResponse>('GET', '/resolved-tickets')
}
