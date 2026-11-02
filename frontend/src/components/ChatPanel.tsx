import { useCallback, useEffect, useRef, useState } from 'react'
import { postAgent, transcribeAudio } from '../api/client'
import { QUICK_PROMPTS } from '../constants/quickPrompts'
import type { AgentResult, SessionState } from '../types/api'

export interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
}

interface ChatPanelProps {
  sessionId: string
  useSupervisor: boolean
  notice: string
  onSupervisorChange: (value: boolean) => void
  onSessionUpdate: (patch: Partial<SessionState> & Pick<AgentResult, 'steps'>) => void
  onNotice: (text: string) => void
}

export function ChatPanel({
  sessionId,
  useSupervisor,
  notice,
  onSupervisorChange,
  onSessionUpdate,
  onNotice,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [activity, setActivity] = useState('')
  const [recording, setRecording] = useState(false)
  const chatRef = useRef<HTMLDivElement>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight })
  }, [messages, activity])

  const applyResult = useCallback(
    (result: AgentResult) => {
      onSessionUpdate({
        candidates: result.candidates ?? [],
        draft: result.draft ?? null,
        checklist: result.checklist ?? [],
        policy_refs: result.policy_refs ?? [],
        management_brief: result.management_brief ?? null,
        interview_pack: result.interview_pack ?? null,
        steps: result.steps,
      })
      const steps = result.steps || []
      setActivity(steps.length ? `Completed: ${steps.join(' · ')}` : '')
      if (result.reply) {
        setMessages((prev) => [...prev, { role: 'assistant', text: result.reply! }])
        speechSynthesis.cancel()
        speechSynthesis.speak(new SpeechSynthesisUtterance(result.reply))
      }
    },
    [onSessionUpdate],
  )

  const sendAgent = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || sending) return
      setMessages((prev) => [...prev, { role: 'user', text: trimmed }])
      setMessage('')
      setSending(true)
      setActivity('TalentScout HR is working…')
      onNotice('')
      try {
        const result = await postAgent({
          message: trimmed,
          session_id: sessionId,
          use_supervisor: useSupervisor,
        })
        applyResult(result)
      } catch {
        onNotice('The assistant could not complete that request. Check that Ollama is running, then try again.')
        setActivity('')
      } finally {
        setSending(false)
      }
    },
    [applyResult, onNotice, sending, sessionId, useSupervisor],
  )

  const toggleMic = useCallback(async () => {
    if (recording && recorderRef.current) {
      recorderRef.current.stop()
      setRecording(false)
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const recorder = new MediaRecorder(stream)
      recorderRef.current = recorder
      chunksRef.current = []
      recorder.ondataavailable = (event) => chunksRef.current.push(event.data)
      recorder.onstop = async () => {
        const formBlob = new Blob(chunksRef.current, { type: recorder.mimeType })
        stream.getTracks().forEach((track) => track.stop())
        streamRef.current = null
        try {
          const text = await transcribeAudio(formBlob)
          if (text) void sendAgent(text)
        } catch {
          onNotice('Voice transcription failed. You can type your request instead.')
        }
      }
      recorder.start()
      setRecording(true)
    } catch {
      onNotice('Microphone permission is unavailable. You can type your request instead.')
    }
  }, [onNotice, recording, sendAgent])

  return (
    <section className="conversation panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">HR assistant</span>
          <h1>What can I help you with?</h1>
        </div>
        <span className="privacy">Local-first workspace</span>
      </div>

      {notice ? <div className="notice">{notice}</div> : null}

      <div ref={chatRef} className="chat" aria-live="polite">
        {messages.length === 0 && (
          <div className="welcome">
            <div className="welcome-icon">✦</div>
            <h2>One place for your hiring work.</h2>
            <p>
              Ask me to source candidates, draft a job description, prepare onboarding, or look up an HR
              policy.
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role === 'user' ? 'user' : 'assistant'}`}>
            <div className="message-label">{msg.role === 'user' ? 'You' : 'TalentScout HR'}</div>
            <div className="bubble">{msg.text}</div>
          </div>
        ))}
      </div>

      {activity && <div className="activity">{activity}</div>}

      <div className="composer-wrap">
        <div className="quick-actions">
          {QUICK_PROMPTS.map(({ label, prompt }) => (
            <button
              key={label}
              type="button"
              onClick={() => {
                setMessage(prompt)
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="supervisor-toggle">
          <input
            type="checkbox"
            checked={useSupervisor}
            onChange={(e) => onSupervisorChange(e.target.checked)}
          />
          Multi-agent supervisor (LangGraph)
        </label>
        <div className="composer">
          <textarea
            rows={1}
            placeholder="Ask your HR assistant anything…"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void sendAgent(message)
              }
            }}
          />
          <button
            type="button"
            id="mic"
            className="icon-button"
            title="Record a voice request"
            onClick={() => void toggleMic()}
          >
            {recording ? '■' : '●'}
          </button>
          <button
            type="button"
            className="send"
            disabled={sending}
            onClick={() => void sendAgent(message)}
          >
            ↑
          </button>
        </div>
        <small>AI drafts are for review. Public candidate evidence must be verified before decisions.</small>
      </div>
    </section>
  )
}
