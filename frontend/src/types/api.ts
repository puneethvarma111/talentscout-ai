export type PipelineStage = 'Sourced' | 'Shortlisted' | 'Outreach ready'

export interface Candidate {
  name?: string
  username?: string
  title?: string
  bio?: string
  snippet?: string
  url?: string
  profile_url?: string
  match_score?: number
  matched_skills?: string[]
  candidate_key?: string
  pipeline_stage?: PipelineStage
}

export interface DraftArtifact {
  type?: string
  content?: string
}

export interface ChecklistItem {
  task: string
  owner: string
}

export interface PolicyRef {
  id: string
  title: string
  answer: string
}

export interface AgentResult {
  reply?: string
  candidates?: Candidate[]
  steps?: string[]
  draft?: DraftArtifact | null
  checklist?: ChecklistItem[]
  policy_refs?: PolicyRef[]
  management_brief?: unknown
  interview_pack?: unknown
  session_id?: string
}

export interface SessionState {
  candidates: Candidate[]
  draft: DraftArtifact | null
  checklist: ChecklistItem[]
  policy_refs: PolicyRef[]
  management_brief: unknown
  interview_pack: unknown
}

export interface HealthResponse {
  ok: boolean
  ollama_model?: string
  error?: string
}
