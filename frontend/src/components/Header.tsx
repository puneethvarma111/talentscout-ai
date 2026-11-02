type HealthStatus = 'connecting' | 'ok' | 'error'

interface HeaderProps {
  health: HealthStatus
  onNewChat: () => void
}

export function Header({ health, onNewChat }: HeaderProps) {
  const label =
    health === 'ok' ? 'AI connected' : health === 'error' ? 'AI unavailable' : 'Connecting…'

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark">T</div>
        <div>
          <strong>TalentScout HR</strong>
          <span>AI copilot for recruiting and people ops</span>
        </div>
      </div>
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
