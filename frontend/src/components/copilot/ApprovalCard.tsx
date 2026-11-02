import { useState } from 'react'
import { decideApproval } from '../../api/copilot'
import type { Approval } from '../../types/copilot'

export function ApprovalCard({ approval, sessionId }: { approval: Approval; sessionId: string }) {
  const [state, setState] = useState(approval)
  const [text, setText] = useState(approval.content)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const decide = async (d: 'approve' | 'reject') => {
    setBusy(true)
    setError('')
    try {
      setState(await decideApproval(sessionId, approval.id, d, text))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  const pending = state.status === 'pending'
  return (
    <section className={`approval ${state.status}`} aria-label={`${state.action} approval`}>
      <header>
        <span className="badge">{pending ? 'Needs your approval' : state.status === 'approved' ? 'Approved' : 'Rejected'}</span>
        <strong>{state.action} → {state.target}</strong>
      </header>
      {state.missing_fields && state.missing_fields.length > 0 && pending && (
        <p className="warn">Fill in before approving: {state.missing_fields.join(', ')}</p>
      )}
      <label className="sr-only" htmlFor={`ap-${approval.id}`}>Draft content</label>
      <textarea id={`ap-${approval.id}`} value={text} onChange={(e) => setText(e.target.value)} readOnly={!pending} rows={10} />
      {error && <p className="warn" role="alert">{error}</p>}
      {pending ? (
        <div className="approval-actions">
          <button type="button" className="ghost" disabled={busy} onClick={() => void decide('reject')}>Reject</button>
          <button type="button" className="ghost" onClick={() => void navigator.clipboard.writeText(text)}>Copy</button>
          <button type="button" className="primary" disabled={busy} onClick={() => void decide('approve')}>Approve draft</button>
        </div>
      ) : (
        <p className="approval-note">{state.note}</p>
      )}
    </section>
  )
}
