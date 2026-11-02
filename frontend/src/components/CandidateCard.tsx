import type { Candidate, PipelineStage } from '../types/api'

const STAGES: PipelineStage[] = ['Sourced', 'Shortlisted', 'Outreach ready']

interface CandidateCardProps {
  candidate: Candidate
  showStageSelect?: boolean
  onStageChange?: (stage: PipelineStage) => void
}

export function CandidateCard({ candidate, showStageSelect, onStageChange }: CandidateCardProps) {
  const name = candidate.name || candidate.username || candidate.title || 'Public profile'
  const url = candidate.profile_url || candidate.url
  const skills = (candidate.matched_skills || []).slice(0, 4)

  return (
    <article className="candidate-card">
      <div className="candidate-head">
        <span className="candidate-name">{name}</span>
        <span className="score">{candidate.match_score ?? 0}%</span>
      </div>
      {!showStageSelect && (
        <p>{candidate.bio || candidate.snippet || 'No public summary available.'}</p>
      )}
      {!showStageSelect && (
        <div>
          {skills.length
            ? skills.map((skill) => (
                <span key={skill} className="tag">
                  {skill}
                </span>
              ))
            : (
              <span className="tag">Evidence pending</span>
              )}
        </div>
      )}
      {!showStageSelect && url && (
        <a href={url} target="_blank" rel="noopener noreferrer">
          Open source profile ↗
        </a>
      )}
      {showStageSelect && candidate.candidate_key && onStageChange && (
        <select
          className="stage-select"
          value={candidate.pipeline_stage ?? 'Sourced'}
          onChange={(e) => onStageChange(e.target.value as PipelineStage)}
        >
          {STAGES.map((stage) => (
            <option key={stage} value={stage}>
              {stage}
            </option>
          ))}
        </select>
      )}
    </article>
  )
}
