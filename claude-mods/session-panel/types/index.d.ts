/** How one tool call ended, or that it has not. */
export type CallStatus = 'running' | 'ok' | 'error' | 'denied'

/** A shell command's status: a call status, or moved to the background. */
export type ShellStatus = CallStatus | 'background'

export type AgentStatus = 'running' | 'done' | 'stopped' | 'failed'

export type Tab = 'overview' | 'subagents' | 'shell' | 'files'

/** Every tool call, kept small: what the timeline and the counts read. */
export type CallMark = {
  id: string
  tool: string
  /** The subagent loop that made the call; absent on the main loop. */
  agentId?: string
  status: CallStatus
  startedAt: number
  endedAt?: number
}

export type ShellRun = {
  id: string
  command: string
  /** The call's few-word description of what the command does. */
  description: string
  agentId?: string
  status: ShellStatus
  startedAt: number
  endedAt?: number
  /** The tail of each stream, cleaned of escape sequences. */
  stdout: string
  stderr: string
  /** Why it ended as it did: a deny, an interrupt, a timeout. */
  note?: string
}

/** One tool call in a subagent's trace. */
export type TraceStep = {
  id: string
  tool: string
  summary: string
  status: CallStatus
  at: number
}

export type AgentRun = {
  /** The subagent's loop id, or the Agent call's id when the engine gave none. */
  id: string
  agentId?: string
  parentAgentId?: string
  /** The agent definition it runs as: `Explore`, `swe:reviewer`, `fork`. */
  type: string
  name?: string
  description: string
  prompt: string
  model?: string
  isBackground: boolean
  status: AgentStatus
  startedAt: number
  endedAt?: number
  toolCalls: number
  /** The latest tool calls, oldest first. */
  trace: TraceStep[]
  answer?: string
  tokensIn: number
  tokensOut: number
}

export type FileTouch = {
  path: string
  reads: number
  edits: number
  lastAt: number
}

export type Usage = { tokensIn: number; tokensOut: number; turns: number }

declare module 'claude-code' {
  interface PluginState {
    'session-panel': {
      calls: CallMark[]
      shell: ShellRun[]
      agents: AgentRun[]
      files: FileTouch[]
      usage: Usage
      tab: Tab
      /** Ids of the rows shown open. */
      expanded: string[]
      /** Ids of the shell runs and agents whose details ride the next prompt. */
      asked: string[]
      /** When the person last sent a prompt: the band shows agents since. */
      turnFrom: number
      now: number
    }
  }
}
