import { useState } from 'react'
import type { Artifact, Cell } from '../../types/copilot'

const label = (c: string) => c.replace(/_/g, ' ')

function cell(v: Cell, col: string) {
  if (typeof v === 'boolean') return <span className={`pill ${v ? 'good' : 'bad'}`}>{v ? 'Met' : 'Gap'}</span>
  if (col === 'signal' || col === 'status') return <span className={`pill ${String(v).toLowerCase()}`}>{String(v)}</span>
  return v === null || v === undefined || v === '' ? '—' : String(v)
}

function toCsv(a: Artifact) {
  const esc = (v: Cell) => `"${String(v ?? '').replace(/"/g, '""')}"`
  return [a.columns.join(','), ...a.rows.map((r) => a.columns.map((c) => esc(r[c])).join(','))].join('\n')
}

export function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const [done, setDone] = useState<Record<number, boolean>>({})
  const download = () => {
    const url = URL.createObjectURL(new Blob([toCsv(artifact)], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `${artifact.title.replace(/[^\w]+/g, '_')}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <section className="artifact" aria-label={artifact.title}>
      <header>
        <strong>{artifact.title}</strong>
        <button type="button" className="ghost" onClick={download}>Export CSV</button>
      </header>
      {artifact.kind === 'scorecard' && (
        <div className="scorecard">
          <div className="score-ring" style={{ ['--p' as string]: artifact.score ?? 0 }} role="img" aria-label={`Score ${artifact.score} of 100`}>
            <span>{artifact.score}</span>
          </div>
          <div>
            <div className="rec">{artifact.recommendation}</div>
            <small>Keyword evidence from the resume. Verify in interview.</small>
          </div>
        </div>
      )}
      {artifact.rows.length === 0 ? (
        <p className="empty-row">No records in this range.</p>
      ) : artifact.kind === 'checklist' ? (
        <ul className="checklist">
          {artifact.rows.map((r, i) => (
            <li key={i}>
              <label>
                <input type="checkbox" checked={!!done[i]} onChange={(e) => setDone({ ...done, [i]: e.target.checked })} />
                <span className={done[i] ? 'struck' : ''}>{String(r.task)}</span>
              </label>
              <span className="meta">{String(r.owner)} · {String(r.due)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>{artifact.columns.map((c) => <th key={c} scope="col">{label(c)}</th>)}</tr>
            </thead>
            <tbody>
              {artifact.rows.map((r, i) => (
                <tr key={i}>{artifact.columns.map((c) => <td key={c}>{cell(r[c], c)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {artifact.notes && artifact.notes.length > 0 && (
        <div className="notes">
          <strong>Suggested interview probes</strong>
          <ul>{artifact.notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </div>
      )}
    </section>
  )
}
