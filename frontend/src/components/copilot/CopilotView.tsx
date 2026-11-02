import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchCopilotConfig, removeDoc, streamCopilot, uploadDoc } from '../../api/copilot'
import { USE_CASES } from '../../constants/useCases'
import type { CopilotConfig, CopilotEvent, CopilotMessage, Persona, UploadedDoc } from '../../types/copilot'
import { ApprovalCard } from './ApprovalCard'
import { ArtifactCard } from './ArtifactCard'
import { Markdown } from './Markdown'
import { StepTimeline } from './StepTimeline'
import '../../styles/copilot.css'

const uid = () => crypto.randomUUID()
const PERSONAS: { id: Persona; label: string }[] = [
  { id: 'employee', label: 'Employee' },
  { id: 'manager', label: 'Manager' },
  { id: 'hr', label: 'HR' },
]

export function CopilotView() {
  const [sessionId] = useState(uid)
  const [config, setConfig] = useState<CopilotConfig | null>(null)
  const [configError, setConfigError] = useState('')
  const [persona, setPersona] = useState<Persona>('manager')
  const [messages, setMessages] = useState<CopilotMessage[]>([])
  const [input, setInput] = useState('')
  const [docs, setDocs] = useState<UploadedDoc[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [busy, setBusy] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    fetchCopilotConfig().then(setConfig).catch((e: Error) => setConfigError(e.message || 'API unreachable'))
  }, [])

  useEffect(() => () => abortRef.current?.abort(), [])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const patchLast = (fn: (m: CopilotMessage) => CopilotMessage) =>
    setMessages((prev) => prev.map((m, i) => (i === prev.length - 1 ? fn(m) : m)))

  const onEvent = useCallback((e: CopilotEvent) => {
    patchLast((m) => {
      switch (e.type) {
        case 'token':
          return { ...m, text: m.text + e.text }
        case 'reset_text':
          return { ...m, text: '' }
        case 'step': {
          const exists = m.steps.some((s) => s.id === e.id)
          const step = { id: e.id, status: e.status, tool: e.tool, label: e.label, args: e.args, summary: e.summary, ms: e.ms }
          return { ...m, steps: exists ? m.steps.map((s) => (s.id === e.id ? step : s)) : [...m.steps, step] }
        }
        case 'artifact':
          return { ...m, artifacts: [...m.artifacts, e.artifact] }
        case 'approval':
          return { ...m, approvals: [...m.approvals, e.approval] }
        case 'notice':
          return { ...m, notice: e.text }
        case 'done':
          return { ...m, text: e.text || m.text, status: 'done' }
        case 'error':
          return { ...m, text: m.text || e.text, status: 'error' }
        default:
          return m
      }
    })
  }, [])

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim()
      if (!text || busy) return
      setInput('')
      setBusy(true)
      setMessages((prev) => [
        ...prev,
        { id: uid(), role: 'user', text, status: 'done', steps: [], artifacts: [], approvals: [] },
        { id: uid(), role: 'assistant', text: '', status: 'streaming', steps: [], artifacts: [], approvals: [] },
      ])
      const ctrl = new AbortController()
      abortRef.current = ctrl
      try {
        await streamCopilot({ message: text, session_id: sessionId, persona }, onEvent, ctrl.signal)
        patchLast((m) => (m.status === 'streaming' ? { ...m, status: 'done' } : m))
      } catch (err) {
        const aborted = (err as Error).name === 'AbortError'
        patchLast((m) => ({ ...m, status: aborted ? 'done' : 'error', text: m.text || (aborted ? 'Stopped.' : `I couldn't reach the HR Copilot API. ${(err as Error).message}`) }))
      } finally {
        setBusy(false)
        inputRef.current?.focus()
      }
    },
    [busy, onEvent, persona, sessionId],
  )

  const onFiles = async (files: FileList | null) => {
    if (!files?.length) return
    setUploading(true)
    setUploadError('')
    for (const f of Array.from(files)) {
      try {
        const d = await uploadDoc(sessionId, f)
        setDocs((prev) => [...prev, d])
      } catch (e) {
        setUploadError(`${f.name}: ${(e as Error).message}`)
      }
    }
    setUploading(false)
    if (fileRef.current) fileRef.current.value = ''
  }

  const cases = USE_CASES.filter((u) => u.personas.includes(persona))
  const lastFailed = messages.length > 1 && messages[messages.length - 1].status === 'error'

  return (
    <section className="copilot panel" aria-label="HR Copilot">
      <div className="cp-head">
        <div>
          <span className="eyebrow">HR Copilot</span>
          <h1>Ask about people, leave, policies and hiring</h1>
        </div>
        <div className="persona" role="radiogroup" aria-label="Act as">
          {PERSONAS.map((p) => (
            <button key={p.id} type="button" role="radio" aria-checked={persona === p.id} className={persona === p.id ? 'on' : ''} onClick={() => setPersona(p.id)} disabled={busy}>
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {configError ? (
        <div className="banner error" role="alert">Can't reach the API ({configError}). Start it with <code>uv run uvicorn app.main:app --reload</code>.</div>
      ) : config?.mock ? (
        <div className="banner">Offline demo mode — answers come from rules and demo data, no AI model. Start Ollama or set <code>LLM_PROVIDER</code> for full AI.</div>
      ) : null}

      <div className="cp-body" ref={listRef} aria-live="polite" aria-busy={busy}>
        {messages.length === 0 ? (
          <div className="cp-empty">
            <p className="cp-who">
              Signed in as <strong>{config?.personas[persona]?.label ?? persona}</strong>
              {config && <> · {config.mock ? 'offline mode' : `${config.provider} · ${config.model}`} · {config.data_source} data</>}
            </p>
            <div className="case-grid">
              {cases.map((u) => (
                <button key={u.id} type="button" className="case" onClick={() => { setInput(u.prompt); inputRef.current?.focus() }}>
                  <span className="case-icon" aria-hidden>{u.icon}</span>
                  <strong>{u.title}</strong>
                  <span>{u.blurb}</span>
                  {u.needsUpload && <em>{u.needsUpload}</em>}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) =>
            m.role === 'user' ? (
              <div key={m.id} className="msg user"><div className="bubble">{m.text}</div></div>
            ) : (
              <div key={m.id} className={`msg bot ${m.status}`}>
                <div className="avatar" aria-hidden>S</div>
                <div className="bot-col">
                  <StepTimeline steps={m.steps} streaming={m.status === 'streaming'} />
                  {m.notice && <div className="banner small">{m.notice}</div>}
                  {m.artifacts.map((a, i) => <ArtifactCard key={i} artifact={a} />)}
                  {m.approvals.map((a) => <ApprovalCard key={a.id} approval={a} sessionId={sessionId} />)}
                  {m.text ? (
                    <div className={`answer ${m.status === 'error' ? 'err' : ''}`}><Markdown text={m.text} />{m.status === 'streaming' && <span className="caret" aria-hidden />}</div>
                  ) : m.status === 'streaming' && !m.steps.length ? (
                    <div className="typing" aria-label="Thinking"><i /><i /><i /></div>
                  ) : null}
                </div>
              </div>
            ),
          )
        )}
        {lastFailed && (
          <button type="button" className="ghost retry" onClick={() => void send(messages[messages.length - 2].text)}>Retry last question</button>
        )}
      </div>

      <div className="cp-foot">
        {(docs.length > 0 || uploading || uploadError) && (
          <div className="chips">
            {docs.map((d) => (
              <span key={d.id} className="chip">
                📎 {d.name} <small>{d.kind}</small>
                <button type="button" aria-label={`Remove ${d.name}`} onClick={() => { void removeDoc(sessionId, d.id); setDocs(docs.filter((x) => x.id !== d.id)) }}>×</button>
              </span>
            ))}
            {uploading && <span className="chip muted">Uploading…</span>}
            {uploadError && <span className="chip errc" role="alert">{uploadError}</span>}
          </div>
        )}
        {messages.length > 0 && !busy && (
          <div className="followups">
            {cases.slice(0, 4).map((u) => <button key={u.id} type="button" onClick={() => void send(u.prompt)}>{u.title}</button>)}
          </div>
        )}
        <form className="cp-composer" onSubmit={(e) => { e.preventDefault(); void send(input) }}>
          <input ref={fileRef} type="file" accept=".pdf,.txt,.md,.csv" multiple hidden onChange={(e) => void onFiles(e.target.files)} />
          <button type="button" className="icon" aria-label="Attach resume, JD or policy file" title="Attach .pdf / .txt" onClick={() => fileRef.current?.click()}>＋</button>
          <label htmlFor="cp-input" className="sr-only">Message</label>
          <textarea
            id="cp-input"
            ref={inputRef}
            rows={1}
            value={input}
            placeholder={persona === 'employee' ? 'e.g. How many casual leaves do I have?' : 'e.g. Who is on leave next week?'}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(input) } }}
          />
          {busy ? (
            <button type="button" className="send stop" aria-label="Stop" onClick={() => abortRef.current?.abort()}>■</button>
          ) : (
            <button type="submit" className="send" aria-label="Send" disabled={!input.trim()}>↑</button>
          )}
        </form>
        <small className="disclaimer">Uses tools on HRMS data you're allowed to see. Drafts need human approval and are never sent automatically.</small>
      </div>
    </section>
  )
}
