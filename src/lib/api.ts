const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL

/** API root for the next integration milestone; preview fixtures remain the active data source. */
export const API_BASE_URL = (configuredBaseUrl || 'http://localhost:8000/api').replace(/\/$/, '')

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { error?: { message?: string } } | null
    throw new Error(body?.error?.message ?? `AgentTrace API returned ${response.status}`)
  }
  return response.status === 204 ? undefined as T : await response.json() as T
}
