import { expect, mock, test } from 'claude-code/testing'

const PANE = {
  plugin: 'activity',
  component: 'Pane',
  requestId: 'activity',
  props: {
    title: 'Activity',
    isFocused: false,
    bodyColumns: 60,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 20 },
    view: {},
  },
} as const

test('the pane lists finished, failed and denied calls', async ($, on) => {
  const clock = mock.clock(on)
  on('tool.call', { tool: 'Bash' }, async (_, e) => {
    if (e.command === 'false') return { isError: true, result: 'Exit code 1', text: 'Exit code 1' }
    await clock.sleep(1500)
    return { result: { stdout: 'a\n', stderr: '', interrupted: false } }
  })
  on('tool.call', { tool: 'Read' }, () => ({ deny: 'not here' }))

  const slow = $.tool.call({ tool: 'Bash', command: 'ls  -la' })
  await clock.settle()
  const midway = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await midway.find({ type: 'Text', text: '1 calls · 1 running · 0 failed' })).toBeDefined()
  await midway.unmount()
  await clock.advance(1500)
  await slow
  await $.tool.call({ tool: 'Bash', command: 'false' })
  await $.tool.call({ tool: 'Read', file_path: '/etc/shadow' })

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect(await ui.find({ type: 'Text', text: '3 calls · 0 running · 2 failed' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /✓ +1\.5s Bash ls -la/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /✗ .*Bash false/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /⊘ .*Read \/etc\/shadow/ })).toBeDefined()
    await ui.unmount()
  }
})

test('the pane says so when nothing has run', async $ => {
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: 'No tool calls yet.' })).toBeDefined()
  await ui.unmount()
})

test('the pane draws every kept call, taller than its window, for the engine to scroll', async ($, on) => {
  mock.clock(on)
  on('tool.call', { tool: 'Bash' }, () => ({ result: { stdout: '', stderr: '', interrupted: false } }))
  for (let n = 1; n <= 30; n++) await $.tool.call({ tool: 'Bash', command: `echo ${n}` })

  const ui = await $.ui.mount({
    ...PANE,
    surface: 'terminal',
    props: { ...PANE.props, scroll: { offset: 0, bodyRows: 5 } },
  })
  expect(await ui.find({ type: 'Text', text: /Bash echo 1$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /Bash echo 30$/ })).toBeDefined()
  await ui.unmount()
})
