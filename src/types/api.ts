export type RunStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled'
export type TraceEventStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped'
export type TraceEventType =
  | 'task_start' | 'planning' | 'llm_call' | 'tool_call' | 'tool_result'
  | 'code_execution' | 'validation' | 'error' | 'recovery' | 'task_complete'

export type DemoScenario =
  | 'successful_execution'
  | 'tool_failure'
  | 'wrong_tool_selection'
  | 'repeated_tool_calls'
  | 'error_with_recovery'
  | 'unrecovered_failure'

export interface AgentRun {
  id: string
  project_id: string
  task: string
  agent_name: string
  status: RunStatus
  started_at: string | null
  ended_at: string | null
  duration_ms: number | null
  event_count: number
  synthetic: boolean
  scenario: DemoScenario | null
  failure_reason: string | null
  metadata: Record<string, unknown>
  created_at: string
}

export interface TraceEvent {
  id: string
  event_id: string
  run_id: string
  parent_event_id: string | null
  sequence_number: number
  event_type: TraceEventType
  name: string
  status: TraceEventStatus
  inputs: unknown
  outputs: unknown
  error: Record<string, unknown> | string | null
  timestamp: string
  duration_ms: number | null
  metadata: Record<string, unknown>
}

export interface DemoRunRequest {
  project_id: string
  scenario: DemoScenario
}

export interface DemoRunResponse {
  run_id: string
  project_id: string
  task: string
  scenario: DemoScenario
  status: Extract<RunStatus, 'success' | 'failed'>
  event_count: number
  duration_ms: number
  duration_kind: 'wall_clock'
  synthetic: true
  started_at: string
  ended_at: string
}

export interface RunSummary {
  run_id: string
  status: RunStatus
  event_count: number
  successful_event_count: number
  failed_event_count: number
  tool_call_count: number
  error_count: number
  recovery_count: number
  duration_ms: number | null
  synthetic: boolean
  scenario: DemoScenario | null
}
