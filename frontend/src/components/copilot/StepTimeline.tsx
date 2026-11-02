import { useState } from 'react'
import type { Step } from '../../types/copilot'

export function StepTimeline({ steps, streaming }: { steps: Step[]; streaming: boolean }) {
  const [open, setOpen] = useState(false)
  if (!steps.length) return null
  const running = steps.some((s) => s.status === 'running')
  return (
    <div className="steps">
      <button type="button" className="steps-toggle" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <span className={`dot ${running ? 'pulse' : steps.some((s) => s.status === 'error') ? 'err' : 'ok'}`} aria-hidden />
        {running ? steps[steps.length - 1].label + '…' : `Used ${steps.length} tool${steps.length > 1 ? 's' : ''}`}
        <span className="chev" aria-hidden>{open ? '▾' : '▸'}</span>
      </button>
      {(open || (running && streaming)) && (
        <ol className="step-list">
          {steps.map((s) => (
            <li key={s.id} className={s.status}>
              <span className="step-icon" aria-label={s.status}>{s.status === 'running' ? '◌' : s.status === 'done' ? '✓' : '!'}</span>
              <div>
                <strong>{s.label}</strong>
                {s.summary && <span className="step-sum"> — {s.summary}</span>}
                {s.args && Object.keys(s.args).length > 0 && <code className="step-args">{s.tool}({JSON.stringify(s.args)})</code>}
              </div>
              {s.ms !== undefined && <span className="step-ms">{s.ms} ms</span>}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
