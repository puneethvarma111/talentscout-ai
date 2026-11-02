export type Persona = 'employee' | 'manager' | 'hr'

export interface CopilotConfig {
  provider: string
  model: string
  mock: boolean
  data_source: string
  personas: Record<Persona, { user_id: string; label: string }>
}

export interface Step {
  id: string
  status: 'running' | 'done' | 'error'
  tool: string
  label: string
  args?: Record<string, unknown>
  summary?: string
  ms?: number
}

export type Cell = string | number | boolean | null | undefined

export interface Artifact {
  kind: 'table' | 'checklist' | 'scorecard'
  title: string
  columns: string[]
  rows: Record<string, Cell>[]
  score?: number
  recommendation?: string
  notes?: string[]
}

export interface Approval {
  id: string
  action: string
  target: string
  status: 'pending' | 'approved' | 'rejected'
  content: string
  missing_fields?: string[]
  note?: string
}

export interface CopilotMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  status: 'streaming' | 'done' | 'error'
  steps: Step[]
  artifacts: Artifact[]
  approvals: Approval[]
  notice?: string
}

export interface UploadedDoc {
  id: string
  name: string
  kind: string
  chars: number
}

export type CopilotEvent =
  | { type: 'meta'; provider: string; model: string }
  | ({ type: 'step' } & Step)
  | { type: 'token'; text: string }
  | { type: 'reset_text' }
  | { type: 'artifact'; artifact: Artifact }
  | { type: 'approval'; approval: Approval }
  | { type: 'notice'; text: string }
  | { type: 'done'; text: string }
  | { type: 'error'; text: string }
