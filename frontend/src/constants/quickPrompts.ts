export const QUICK_PROMPTS = [
  { label: 'Source candidates', prompt: 'Source candidates for a frontend engineer with React and TypeScript' },
  { label: 'Draft a job description', prompt: 'Draft a job description for a software engineer' },
  { label: 'Onboarding checklist', prompt: 'Create an onboarding checklist for a new engineer' },
  { label: 'Ask HR policy', prompt: 'What is our leave policy?' },
  {
    label: 'Pipeline for managers',
    prompt: 'Summarize our hiring pipeline for leadership and flag next actions',
  },
  {
    label: 'Interview pack',
    prompt: 'Prepare interview questions for a backend engineer focusing on Python and system design',
  },
  {
    label: 'Compare top 3',
    prompt: 'Compare our top three candidates with pros and gaps from public evidence',
  },
] as const

export type RailTab = 'shortlist' | 'pipeline' | 'work'
