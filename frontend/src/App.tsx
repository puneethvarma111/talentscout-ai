import { useCallback, useEffect, useState } from 'react'
import { fetchHealth } from './api/client'
import { ChatPanel } from './components/ChatPanel'
import { ContextRail } from './components/ContextRail'
import { CopilotView } from './components/copilot/CopilotView'
import { Header, type View } from './components/Header'
import type { RailTab } from './constants/quickPrompts'
import type { SessionState } from './types/api'
import './styles/app.css'

const emptySession = (): SessionState => ({
  candidates: [],
  draft: null,
  checklist: [],
  policy_refs: [],
  management_brief: null,
  interview_pack: null,
})

function App() {
  const [sessionKey, setSessionKey] = useState(() => crypto.randomUUID())
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID())
  const [session, setSession] = useState<SessionState>(emptySession)
  const [useSupervisor, setUseSupervisor] = useState(true)
  const [activeTab, setActiveTab] = useState<RailTab>('shortlist')
  const [notice, setNotice] = useState('')
  const [view, setView] = useState<View>('copilot')
  const [health, setHealth] = useState<'connecting' | 'ok' | 'error'>('connecting')

  useEffect(() => {
    void fetchHealth()
      .then((r) => setHealth(r.ok ? 'ok' : 'error'))
      .catch(() => setHealth('error'))
  }, [])

  const mergeSession = useCallback((patch: Partial<SessionState>) => {
    setSession((prev) => ({ ...prev, ...patch }))
  }, [])

  const newChat = () => {
    setSessionKey(crypto.randomUUID())
    setSessionId(crypto.randomUUID())
    setSession(emptySession())
    setNotice('')
  }

  return (
    <div className="app-shell">
      <Header health={health} view={view} onViewChange={setView} onNewChat={newChat} />
      {view === 'copilot' ? (
        <main className="workspace single">
          <CopilotView key={sessionKey} />
        </main>
      ) : (
      <main className="workspace">
        <ChatPanel
          key={sessionKey}
          sessionId={sessionId}
          useSupervisor={useSupervisor}
          notice={notice}
          onSupervisorChange={setUseSupervisor}
          onSessionUpdate={mergeSession}
          onNotice={setNotice}
        />
        <ContextRail activeTab={activeTab} onTabChange={setActiveTab} session={session} />
      </main>
      )}
    </div>
  )
}

export default App
