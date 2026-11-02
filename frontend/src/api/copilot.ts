import type { Approval, CopilotConfig, CopilotEvent, Persona, UploadedDoc } from '../types/copilot'

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = ((await res.json()) as { detail?: string }).detail ?? detail
    } catch {
      /* not json */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const fetchCopilotConfig = (): Promise<CopilotConfig> => fetch('/api/copilot/config').then((r) => json<CopilotConfig>(r))

export async function streamCopilot(
  body: { message: string; session_id: string; persona: Persona },
  onEvent: (e: CopilotEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/copilot/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok || !res.body) await json(res)
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const raw = buffer.slice(0, idx).trim()
      buffer = buffer.slice(idx + 2)
      if (raw.startsWith('data:')) onEvent(JSON.parse(raw.slice(5)) as CopilotEvent)
    }
  }
}

export function uploadDoc(sessionId: string, file: File): Promise<UploadedDoc> {
  const form = new FormData()
  form.append('session_id', sessionId)
  form.append('file', file)
  return fetch('/api/copilot/upload', { method: 'POST', body: form }).then((r) => json<UploadedDoc>(r))
}

export const removeDoc = (sessionId: string, id: string) =>
  fetch(`/api/copilot/upload/${id}?session_id=${encodeURIComponent(sessionId)}`, { method: 'DELETE' })

export function decideApproval(sessionId: string, id: string, decision: 'approve' | 'reject', content?: string): Promise<Approval> {
  return fetch(`/api/copilot/approvals/${id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, decision, content }),
  }).then((r) => json<Approval>(r))
}
