import { expect, mock, test } from 'claude-code/testing'

const PANE = {
  plugin: 'subagents',
  component: 'Pane',
  requestId: 'subagents',
  props: {
    title: 'Subagents',
    isFocused: false,
    bodyColumns: 50,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 30 },
    view: {},
  },
} as const

test('the pane follows a subagent from spawn to its last tool call to done', async ($, on) => {
  const clock = mock.clock(on)
  on('agent.spawn', (_, e) => ({ model: 'claude-test', agentId: `agent-${e.description.length}` }))
  on('tool.call', { tool: 'Read' }, () => ({ result: 'ok' }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('turn.complete', () => ({ text: '' }))

  await $.agent.spawn({
    tool_use_id: 'call-1',
    prompt: 'Find the failing test',
    description: 'Find the failing test',
    subagentType: 'swe:explorer',
    provider: { plugin: 'swe', tier: 'user' },
    parentModel: 'claude-test',
    background: false,
    fork: false,
  })
  await $.tool.call({ tool: 'Read', file_path: '/repo/src/sprite.ts', agentId: 'agent-21' })
  await clock.advance(65_000)

  const terminal = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await terminal.find({ type: 'Text', text: '1 running · 0 finished' })).toBeDefined()
  expect(await terminal.find({ type: 'Raster', key: 'sprite-agent-21' })).toBeDefined()
  expect(await terminal.find({ type: 'Text', text: /^swe:explorer \d+:\d\d$/ })).toBeDefined()
  expect(await terminal.find({ type: 'Text', text: 'Find the failing test' })).toBeDefined()
  expect(await terminal.find({ type: 'Text', text: '● Read sprite.ts' })).toBeDefined()
  await terminal.unmount()

  const desktop = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await desktop.find({ type: 'Text', text: '1 running · 0 finished' })).toBeDefined()
  const card = await desktop.find({ type: 'Svg' })
  expect(card?.props.alt).toBe('swe:explorer: Find the failing test, Read sprite.ts')
  expect(String(card?.props.source)).toContain('class="bob"')
  await desktop.unmount()

  await $.turn.complete({
    reason: 'answer',
    answer: 'Found it',
    durationMs: 65_000,
    isAborted: false,
    turnId: 'turn-1',
    agentId: 'agent-21',
  })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: '0 running · 1 finished' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'swe:explorer 1:05' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '✓ done · 1 tool call' })).toBeDefined()
  await ui.unmount()

  const done = await $.ui.mount({ ...PANE, surface: 'desktop' })
  const finished = await done.find({ type: 'Svg' })
  expect(finished?.props.alt).toBe('swe:explorer: Find the failing test, ✓ done · 1 tool call')
  expect(String(finished?.props.source)).not.toContain('class="bob"')
  await done.unmount()
})

test('running agents list above finished ones, newest first', async ($, on) => {
  mock.clock(on)
  on('agent.spawn', (_, e) => ({ model: 'claude-test', agentId: `agent-${e.subagentType}` }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('turn.complete', () => ({ text: '' }))
  const spawn = (subagentType: string, description: string) =>
    $.agent.spawn({
      tool_use_id: `call-${subagentType}`,
      prompt: description,
      description,
      subagentType,
      provider: { plugin: 'engine', tier: 'core' },
      parentModel: 'claude-test',
      background: true,
      fork: false,
    })

  await spawn('Plan', 'Plan the release')
  await spawn('Explore', 'Map the hooks')
  await spawn('swe:reviewer', 'Review the diff')
  await $.turn.complete({
    reason: 'answer', answer: '', durationMs: 1, isAborted: false, turnId: 'turn-2', agentId: 'agent-swe:reviewer',
  })

  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: '2 running · 1 finished' })).toBeDefined()
  const order = (await ui.findAll({ type: 'Text', text: /^(Plan|Explore|swe:reviewer) \d+:\d\d$/ })).map(t => t.text.split(' ')[0])
  expect(order).toEqual(['Explore', 'Plan', 'swe:reviewer'])
  await ui.unmount()
})

test('the pane says so when no subagent has run', async $ => {
  const terminal = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await terminal.find({ type: 'Text', text: 'No subagents yet.' })).toBeDefined()
  await terminal.unmount()
  const desktop = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await desktop.find({ type: 'Svg' }))?.props.alt).toBe('No subagents yet.')
  await desktop.unmount()
})
