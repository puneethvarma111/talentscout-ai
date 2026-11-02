type HealthStatus = 'connecting' | 'ok' | 'error'
export type View = 'copilot' | 'recruiting'

interface HeaderProps {
  health: HealthStatus
  view: View
  onViewChange: (v: View) => void
  onNewChat: () => void
}

export function Header({ health, view, onViewChange, onNewChat }: HeaderProps) {
  const label =
    health === 'ok' ? 'AI connected' : health === 'error' ? 'AI offline (demo mode)' : 'Connecting…'

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark">T</div>
        <div>
          <strong>TalentScout HR</strong>
          <span>AI copilot for recruiting and people ops</span>
        </div>
      </div>
      <nav className="view-tabs" role="tablist" aria-label="Workspace">
        <button type="button" role="tab" aria-selected={view === 'copilot'} onClick={() => onViewChange('copilot')}>HR Copilot</button>
        <button type="button" role="tab" aria-selected={view === 'recruiting'} onClick={() => onViewChange('recruiting')}>Sourcing</button>
      </nav>
      <div className="top-actions">
        <span className={`status ${health === 'ok' ? 'ok' : health === 'error' ? 'error' : ''}`}>
          <i /> {label}
        </span>
        <button type="button" className="icon-button" onClick={onNewChat}>
          New chat
        </button>
      </div>
    </header>
  )
}
