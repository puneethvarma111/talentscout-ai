import type { Persona } from '../types/copilot'

export interface UseCase {
  id: string
  icon: string
  title: string
  blurb: string
  prompt: string
  personas: Persona[]
  needsUpload?: string
}

export const USE_CASES: UseCase[] = [
  { id: 'leave', icon: '🗓', title: 'Leave balance', blurb: 'Balances, pending and upcoming leave', prompt: 'How many leave days do I have left?', personas: ['employee', 'manager', 'hr'] },
  { id: 'policy', icon: '📘', title: 'Policy Q&A', blurb: 'Answers from your handbook, with citations', prompt: 'What is the work from home policy?', personas: ['employee', 'manager', 'hr'], needsUpload: 'Upload your HR handbook (PDF) for company-specific answers' },
  { id: 'attendance', icon: '⏱', title: 'Attendance check', blurb: 'Late marks, LOP and WFH for 30 days', prompt: 'Show my team attendance for the last 30 days and flag issues', personas: ['manager', 'hr'] },
  { id: 'availability', icon: '👥', title: "Who's out", blurb: 'Plan sprints and releases around leave', prompt: 'Who is out on leave in the next 30 days?', personas: ['manager', 'hr'] },
  { id: 'retention', icon: '📈', title: 'Retention signals', blurb: 'Burnout and attrition early warnings', prompt: 'Which team members show attrition or burnout risk, and why?', personas: ['manager', 'hr'] },
  { id: 'screen', icon: '📄', title: 'Screen a resume', blurb: 'Explainable fit score against a JD', prompt: 'Screen the uploaded resume against the job description', personas: ['manager', 'hr'], needsUpload: 'Attach a resume and a JD (.pdf / .txt)' },
  { id: 'interview', icon: '💬', title: 'Interview pack', blurb: 'Structured questions per role', prompt: 'Prepare interview questions for a backend engineer focusing on Java and system design', personas: ['manager', 'hr'] },
  { id: 'onboarding', icon: '✅', title: 'Onboarding plan', blurb: 'Day-0 to day-30 checklist with owners', prompt: 'Create an onboarding plan for a new QA engineer', personas: ['manager', 'hr'] },
  { id: 'offer', icon: '✉️', title: 'Offer letter', blurb: 'Draft for approval — never auto-sent', prompt: 'Draft an offer letter to Kiran Kumar as a Backend Engineer at 18 LPA, joining 2026-12-01 in Hyderabad', personas: ['hr'] },
]
