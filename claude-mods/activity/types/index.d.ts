export type CallStatus = 'running' | 'ok' | 'error' | 'denied'

export type CallField = { key: string; value: string }

export type Call = {
  id: string
  tool: string
  summary: string
  /** The call's input fields, each value cut to a readable length. */
  fields: CallField[]
  /** Why it failed or was denied, cut short. */
  reason?: string
  isSubagent: boolean
  startedAt: number
  durationMs?: number
  status: CallStatus
}

declare module 'claude-code' {
  interface PluginState {
    activity: { calls: Call[]; expanded: string[] }
  }
}
