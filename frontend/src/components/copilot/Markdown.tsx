import type { ReactNode } from 'react'

/** Tiny, safe markdown subset: **bold**, _italic_, `code`, [citations], bullets, > quotes. No HTML injection. */
function inline(text: string, key: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+§\d+\]|(?<![\w])_[^_]+_(?![\w])|\*[^*\s][^*]*\*)/g)
  return parts.map((p, i) => {
    const k = `${key}-${i}`
    if (p.startsWith('**') && p.endsWith('**')) return <strong key={k}>{p.slice(2, -2)}</strong>
    if (p.startsWith('`') && p.endsWith('`')) return <code key={k}>{p.slice(1, -1)}</code>
    if (/^\[[^\]]+§\d+\]$/.test(p)) return <span key={k} className="cite" title="Source">{p.slice(1, -1)}</span>
    if ((p.startsWith('_') && p.endsWith('_')) || (p.startsWith('*') && p.endsWith('*') && p.length > 2)) return <em key={k}>{p.slice(1, -1)}</em>
    return p
  })
}

export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  let list: ReactNode[] = []
  const flush = (i: number) => {
    if (list.length) blocks.push(<ul key={`ul-${i}`}>{list}</ul>)
    list = []
  }
  text.split('\n').forEach((line, i) => {
    const t = line.trim()
    const bullet = /^([-*•]|\d+\.)\s+(.*)/.exec(t)
    if (bullet) {
      list.push(<li key={i}>{inline(bullet[2], `li${i}`)}</li>)
      return
    }
    flush(i)
    if (!t) return
    if (t.startsWith('>')) blocks.push(<blockquote key={i}>{inline(t.replace(/^>\s?/, ''), `q${i}`)}</blockquote>)
    else if (/^#{1,4}\s/.test(t)) blocks.push(<p key={i} className="md-h">{inline(t.replace(/^#+\s/, ''), `h${i}`)}</p>)
    else blocks.push(<p key={i}>{inline(t, `p${i}`)}</p>)
  })
  flush(-1)
  return <div className="md">{blocks}</div>
}
