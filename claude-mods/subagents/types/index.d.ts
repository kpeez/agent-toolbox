export type AgentStatus = 'running' | 'done' | 'stopped' | 'failed'

export type AgentRun = {
  /** The subagent's loop id, or the Agent call's id when the engine gave none. */
  id: string
  agentId?: string
  parentAgentId?: string
  /** The agent definition it runs as: `Explore`, `swe:reviewer`, `fork`. */
  type: string
  /** The address `Agent({ name })` gave it, when it has one. */
  name?: string
  /** The Agent call's few-word description of the task. */
  description: string
  status: AgentStatus
  /** The latest tool call it made, as `Read register.tsx`. */
  activity: string
  toolCalls: number
  startedAt: number
  endedAt?: number
}

declare module 'claude-code' {
  interface PluginState {
    subagents: {
      agents: AgentRun[]
      now: number
      isAutoOpened: boolean
    }
  }
}
