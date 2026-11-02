import type { AgentResult, Candidate, HealthResponse } from '../types/api'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, options)
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return response.json() as Promise<T>
}

export function fetchHealth(): Promise<HealthResponse> {
  return request('/api/health')
}

export function postAgent(body: {
  message: string
  session_id: string
  use_supervisor: boolean
}): Promise<AgentResult> {
  return request('/api/agent', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function fetchPipeline(): Promise<{ candidates: Candidate[] }> {
  return request('/api/pipeline')
}

export function patchPipelineStage(
  candidateKey: string,
  stage: string,
): Promise<{ candidates: Candidate[] }> {
  return request(`/api/pipeline/${encodeURIComponent(candidateKey)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ stage }),
  })
}

export async function transcribeAudio(blob: Blob): Promise<string> {
  const form = new FormData()
  form.append('audio', blob, 'request.webm')
  const result = await request<{ text: string }>('/api/transcribe', {
    method: 'POST',
    body: form,
  })
  return result.text
}
