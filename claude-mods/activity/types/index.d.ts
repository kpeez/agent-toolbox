export type CallStatus = 'running' | 'ok' | 'error' | 'denied'

export type Call = {
  id: string
  tool: string
  summary: string
  isSubagent: boolean
  startedAt: number
  durationMs?: number
  status: CallStatus
}

declare module 'claude-code' {
  interface PluginState {
    activity: { calls: Call[] }
  }
}
