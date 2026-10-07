import { expect, mock, test } from 'claude-code/testing'

import { dancerCells } from '../hooks/dancer'
import { agentColor } from '../hooks/svg'

const PANE = {
  plugin: 'session-panel',
  component: 'Pane',
  requestId: 'session-panel',
  props: {
    title: 'Session',
    isFocused: false,
    bodyColumns: 80,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 40 },
    view: {},
  },
} as const

// Any C0 or C1 control character but newline and tab: the engine refuses a
// drawing that holds one.
const CONTROL = /[^\P{Cc}\n\t]/u

function strings(node: unknown, out: string[] = []): string[] {
  if (typeof node === 'string') out.push(node)
  else if (Array.isArray(node)) node.forEach(n => strings(n, out))
  else if (node && typeof node === 'object') Object.values(node).forEach(v => strings(v, out))
  return out
}

type Mount = { findAll: (q: { type: string }) => Promise<{ props: Record<string, unknown> }[]> }

// The query matches by type, key and text only, so props are matched here.
async function findByProp(ui: Mount, type: string, prop: string, pattern: RegExp) {
  return (await ui.findAll({ type })).find(el => pattern.test(String(el.props[prop])))
}

for (const surface of ['terminal', 'desktop'] as const) {
  test(`a failing shell command shows its cleaned output on ${surface}`, async ($, on) => {
    mock.clock(on)
    on('ui.open', () => ({ value: { isPlaced: true } }))
    on('tool.call', { tool: 'Bash' }, () => ({
      isError: true,
      result: 'Exit code 1',
      text: 'Exit code 1\n\x1b[31m✗ shell tab keeps escapes out\x1b[0m\r\n',
    }))

    await $.tool.call({ tool: 'Bash', tool_use_id: 'sh-1', command: 'bun test', description: 'Run the tests' })

    const ui = await $.ui.mount({ ...PANE, surface })
    await ui.press({ key: 'tab-shell' })
    expect(await ui.find({ type: 'Text', text: /1 failed/ })).toBeDefined()
    await ui.press({ key: 'shb-sh-1' })
    const output = await findByProp(ui, 'Code', 'source', /✗ shell tab keeps escapes out/)
    expect(output).toBeDefined()
    expect(String(output?.props.source)).not.toMatch(CONTROL)
    expect(String(output?.props.source)).not.toContain('[31m')
    await ui.unmount()
  })

  test(`a subagent's trace and answer reach its details on ${surface}`, async ($, on) => {
    const clock = mock.clock(on)
    on('ui.open', () => ({ value: { isPlaced: true } }))
    on('agent.spawn', () => ({ model: 'claude-test', agentId: 'agent-1' }))
    on('tool.call', { tool: 'Read' }, () => ({ result: 'ok' }))
    on('turn.complete', () => ({ text: '' }))

    await $.agent.spawn({
      tool_use_id: 'call-1', prompt: 'Find the **failing** test', description: 'Find the failing test',
      subagentType: 'swe:explorer', provider: { plugin: 'swe', tier: 'user' }, parentModel: 'claude-test',
      background: false, fork: false,
    })
    // A subagent's call carries its loop id, an envelope key the typed input leaves out.
    await $.tool.call({ tool: 'Read', tool_use_id: 'r-1', file_path: '/repo/src/sprite.ts', agentId: 'agent-1' } as Parameters<typeof $.tool.call>[0])
    await clock.advance(65_000)
    await $.turn.complete({
      reason: 'answer', answer: 'It is `sprite.test.ts`.', durationMs: 65_000, isAborted: false, turnId: 't-1',
      agentId: 'agent-1', usage: { model: 'claude-test', input_tokens: 1000, output_tokens: 200, cache_read_input_tokens: 500, cache_creation_input_tokens: 0 },
    })

    const ui = await $.ui.mount({ ...PANE, surface })
    await ui.press({ key: 'tab-subagents' })
    expect(await ui.find({ type: 'Text', text: /0 running/ })).toBeDefined()
    await ui.press({ key: 'more-agent-1' })
    expect(await ui.find({ type: 'Text', text: /Read sprite\.ts/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: ' · 1 tool call' })).toBeDefined()
    expect(await ui.find({ type: 'Markdown', text: 'It is `sprite.test.ts`.' })).toBeDefined()
    if (surface === 'desktop') {
      const card = await findByProp(ui, 'Svg', 'alt', /^swe:explorer: Find the failing test/)
      expect(card).toBeDefined()
      expect(String(card?.props.source)).toContain('1.5k in · 200 out')
      expect(String(card?.props.source)).not.toContain('tool call')
    }
    await ui.unmount()
  })

  test(`every tab of the demo draws without control characters on ${surface}`, async ($, on) => {
    mock.clock(on)
    on('ui.open', () => ({ value: { isPlaced: true } }))
    await $.command.run({
      command: 'panel', args: 'demo', origin: { kind: 'composer' },
      presentation: { isFullscreen: false, columns: 120 },
    })

    const ui = await $.ui.mount({ ...PANE, surface })
    for (const tab of ['overview', 'subagents', 'shell', 'files']) {
      await ui.press({ key: `tab-${tab}` })
      const drawn = await ui.drawn()
      for (const s of strings(drawn)) expect(s).not.toMatch(CONTROL)
    }
    await ui.press({ key: 'tab-shell' })
    await ui.press({ key: 'shb-demo-sh-test' })
    expect(await findByProp(ui, 'Code', 'source', /✗ the shell tab keeps escape sequences out/)).toBeDefined()
    await ui.unmount()
  })

  if (surface === 'desktop') {
    test('pressing an agent on the timeline opens its details', async ($, on) => {
      mock.clock(on)
      on('ui.open', () => ({ value: { isPlaced: true } }))
      await $.command.run({
        command: 'panel', args: 'demo', origin: { kind: 'composer' },
        presentation: { isFullscreen: false, columns: 120 },
      })

      const ui = await $.ui.mount({ ...PANE, surface })
      await ui.press({ key: 'lane-demo-review' })
      const details = await ui.find({ type: 'Button', key: 'more-demo-review' })
      expect(details?.props.label).toBe('▾ Hide details')
      expect(await ui.find({ type: 'Text', text: 'Prompt' })).toBeDefined()
      await ui.unmount()
    })
  }

  test(`an asked shell command rides the next prompt once on ${surface}`, async ($, on) => {
    mock.clock(on)
    on('ui.open', () => ({ value: { isPlaced: true } }))
    on('tool.call', { tool: 'Bash' }, () => ({ isError: true, result: 'Exit code 1', text: 'Exit code 1\nboom: missing fixture' }))
    const sent: (readonly string[] | undefined)[] = []
    on('prompt.submit', (_, e) => {
      sent.push(e.context)
      return { text: e.text, context: e.context }
    })

    await $.tool.call({ tool: 'Bash', tool_use_id: 'sh-1', command: 'bun test', description: 'Run the tests' })
    const ui = await $.ui.mount({ ...PANE, surface })
    await ui.press({ key: 'tab-shell' })
    await ui.press({ key: 'ask-sh-1' })
    expect((await ui.find({ type: 'Button', key: 'ask-sh-1' }))?.props.label).toBe('✓ asked')

    const submit = (text: string) => $.prompt.submit({ text, wait: false, origin: { kind: 'composer' } })
    await submit('why did this fail?')
    await submit('and now?')
    expect(sent[0]?.join('\n')).toContain('bun test')
    expect(sent[0]?.join('\n')).toContain('boom: missing fixture')
    expect(sent[1]).toBeUndefined()
    expect((await ui.find({ type: 'Button', key: 'ask-sh-1' }))?.props.label).toBe('ask')
    await ui.unmount()
  })

  test(`the band above the prompt follows this turn's subagents on ${surface}`, async ($, on) => {
    const clock = mock.clock(on)
    on('ui.open', () => ({ value: { isPlaced: true } }))
    on('agent.spawn', () => ({ model: 'claude-test', agentId: 'agent-1' }))
    on('turn.complete', () => ({ text: '' }))
    on('prompt.submit', (_, e) => ({ text: e.text }))
    // The engine's own band beneath: empty.
    on('ui.render', { component: 'AbovePrompt' }, ($, e) => $.ui.resolve(e).Box({}))
    const BAND = {
      plugin: 'session-panel', component: 'AbovePrompt', surface,
      props: { hasSurvey: false, isWorking: true, maxRows: 10, bodyColumns: 80, scroll: { offset: 0, bodyRows: 9 }, view: {} },
    } as const
    const submit = (text: string) => $.prompt.submit({ text, wait: false, origin: { kind: 'composer' } })

    await submit('map the code')
    await $.agent.spawn({
      tool_use_id: 'call-1', prompt: 'Map it', description: 'Map the code', subagentType: 'Explore',
      provider: { plugin: 'core', tier: 'core' }, parentModel: 'claude-test', background: false, fork: false,
    })
    await clock.advance(5_000)

    const band = await $.ui.mount(BAND)
    expect(await band.find({ type: 'Text', text: /1 running/ })).toBeDefined()
    // A Clawd dances for the running agent.
    const dancer = surface === 'terminal'
      ? await band.find({ type: 'Raster', key: 'dancer-agent-1' })
      : await band.find({ type: 'Svg', key: undefined })
    expect(dancer).toBeDefined()
    if (surface === 'desktop') expect(dancer?.props.alt).toBe('A Clawd dancing')
    // The row's marker draws in the color the panel's card and lane use.
    const marker = (await band.findAll({ type: 'Text' })).find(t => /^[◐◓◑◒] $/.test(t.text))
    expect(marker?.props.color).toBe(agentColor('Explore'))
    if (surface === 'desktop') {
      const pane = await $.ui.mount({ ...PANE, surface })
      await pane.press({ key: 'tab-subagents' })
      const card = (await pane.findAll({ type: 'Svg' })).find(el => String(el.props.alt).startsWith('Explore:'))
      expect(String(card?.props.source)).toContain(`fill="${agentColor('Explore')}"`)
      await pane.unmount()
    }
    await band.press({ key: 'band-agent-agent-1' })
    const pane = await $.ui.mount({ ...PANE, surface })
    expect((await pane.find({ type: 'Button', key: 'more-agent-1' }))?.props.label).toBe('▾ Hide details')
    await pane.unmount()

    await $.turn.complete({ reason: 'answer', answer: 'Done', durationMs: 5_000, isAborted: false, turnId: 't-1', agentId: 'agent-1' })
    expect(await band.find({ type: 'Text', text: 'subagents · 1 done' })).toBeDefined()
    expect(await band.find({ type: surface === 'terminal' ? 'Raster' : 'Svg' })).toBeUndefined()
    await submit('thanks')
    expect(await band.find({ type: 'Text', text: /subagents ·/ })).toBeUndefined()
    await band.unmount()
  })
}

test('a dancer moves from beat to beat and wears its agent color', () => {
  const words = (b64: string) => new Uint32Array(Uint8Array.from(atob(b64), c => c.charCodeAt(0)).buffer)
  const frames = [0, 1, 2, 3].map(beat => dancerCells('#2a9d8f', beat))
  expect(new Set(frames).size).toBe(4)
  expect(dancerCells('#2a9d8f', 4)).toBe(frames[0])
  for (const frame of frames) expect([...words(frame)]).toContain(0x2a9d8f)
})
