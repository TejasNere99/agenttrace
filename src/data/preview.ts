export type RunStatus = 'Completed' | 'Failed' | 'Running'
export interface PreviewRun { id: string; task: string; agent: string; status: RunStatus; steps: number; duration: string; time: string; project: string }

// Design-only fixture data. Replace this module with API services in a later milestone.
export const previewRuns: PreviewRun[] = [
  { id: 'run_7f3a91c2', task: 'Summarize quarterly revenue', agent: 'Research Agent', status: 'Completed', steps: 12, duration: '8.4s', time: '2 min ago', project: 'Revenue Research' },
  { id: 'run_c5d82e10', task: 'Resolve dependency conflict', agent: 'Code Assistant', status: 'Failed', steps: 7, duration: '14.2s', time: '18 min ago', project: 'Code Assistant' },
  { id: 'run_91ae4d63', task: 'Compare product feedback', agent: 'Support Copilot', status: 'Completed', steps: 9, duration: '6.8s', time: '42 min ago', project: 'Support Copilot' },
  { id: 'run_4b71f0a8', task: 'Inspect failing test suite', agent: 'Code Assistant', status: 'Running', steps: 4, duration: '—', time: '1 hr ago', project: 'Code Assistant' },
]

export const trendData = [
  { day: 'Mon', runs: 32, duration: 7.1, success: 94 }, { day: 'Tue', runs: 46, duration: 8.4, success: 96 },
  { day: 'Wed', runs: 39, duration: 6.8, success: 91 }, { day: 'Thu', runs: 58, duration: 9.3, success: 97 },
  { day: 'Fri', runs: 48, duration: 7.7, success: 95 }, { day: 'Sat', runs: 66, duration: 8.1, success: 98 },
  { day: 'Sun', runs: 54, duration: 7.4, success: 96 },
]

export const projects = [
  { name: 'Code Assistant', description: 'Engineering agent for code review and debugging.', runs: 128, activity: '8 min ago', status: 'Active' },
  { name: 'Revenue Research', description: 'Research and synthesis across financial sources.', runs: 76, activity: '2 min ago', status: 'Active' },
  { name: 'Support Copilot', description: 'Customer support agent with retrieval tools.', runs: 44, activity: '42 min ago', status: 'Active' },
]

export const traceEvents = [
  { id: 'input', label: 'User Input', kind: 'Prompt', time: '10:42:01.120', duration: '0.1s', status: 'success', description: 'Inspect the latest quarterly revenue trends and summarize the key drivers.' },
  { id: 'planner', label: 'Planner', kind: 'Agent', time: '10:42:01.248', duration: '1.2s', status: 'success', description: 'Split task into data retrieval and trend analysis.' },
  { id: 'data', label: 'Data Agent', kind: 'Tool call', time: '10:42:02.504', duration: '3.8s', status: 'success', description: 'Queried quarterly revenue dataset and returned 14 records.' },
  { id: 'analysis', label: 'Analysis Agent', kind: 'Agent', time: '10:42:02.612', duration: '2.4s', status: 'success', description: 'Identified a 12% quarter-over-quarter increase, led by enterprise.' },
  { id: 'answer', label: 'Final Answer', kind: 'Output', time: '10:42:06.480', duration: '0.9s', status: 'success', description: 'Synthesized findings with source references for the user.' },
]
