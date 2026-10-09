/**
 * API client — typed fetch wrappers for the Bob Intelligence backend.
 *
 * Placeholder for Milestone 2. Exports will be added as endpoints are
 * implemented.
 */

const BASE_URL = '/api'

export async function healthCheck(): Promise<{ status: string }> {
  const res = await fetch(`${BASE_URL}/health`)
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`)
  return res.json()
}
