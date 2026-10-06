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
    expect(await ui.find({ type: 'Text', text: /^✓ +1\.5s ❯ Bash $/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', text: '▸ ls -la' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^✗ .* ❯ Bash $/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', text: '▸ false' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^⊘ .* ▤ Read $/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', text: '▸ /etc/shadow' })).toBeDefined()
    await ui.unmount()
  }
})

test('pressing a call shows its full input and why it failed, and pressing again hides them', async ($, on) => {
  mock.clock(on)
  on('tool.call', { tool: 'Bash' }, () => ({ isError: true, result: 'Exit code 2', text: 'grep: no such file' }))
  await $.tool.call({ tool: 'Bash', command: 'grep -rn  needle\n  missing/', description: 'Search for the needle' })

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    const call = await ui.find({ type: 'Button', text: '▸ grep -rn needle missing/' })
    expect(call).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^command / })).toBeUndefined()

    await ui.press({ key: call?.key ?? '' })
    expect(await ui.find({ type: 'Button', text: '▾ grep -rn needle missing/' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'command grep -rn  needle\n  missing/' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'description Search for the needle' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: '✗ grep: no such file' })).toBeDefined()

    await ui.press({ key: call?.key ?? '' })
    expect(await ui.find({ type: 'Text', text: /^command / })).toBeUndefined()
    await ui.unmount()
  }
})

test('a call whose input holds escape sequences still draws, its control characters made visible', async ($, on) => {
  mock.clock(on)
  on('tool.call', { tool: 'Bash' }, () => ({ result: { stdout: '', stderr: '', interrupted: false } }))
  await $.tool.call({ tool: 'Bash', command: 'echo \x1b]0;title\x07 hi\r\nnext' })

  const desktop = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await desktop.find({ type: 'Button', text: '▸ echo ␛]0;title␇ hi next' })).toBeDefined()
  await desktop.unmount()

  const terminal = await $.ui.mount({ ...PANE, surface: 'terminal' })
  const call = await terminal.find({ type: 'Button', text: '▸ echo ␛]0;title␇ hi next' })
  expect(call).toBeDefined()
  await terminal.press({ key: call?.key ?? '' })
  expect(await terminal.find({ type: 'Text', text: 'command echo ␛]0;title␇ hi␍\nnext' })).toBeDefined()
  await terminal.unmount()
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
  expect(await ui.find({ type: 'Button', text: /^▸ echo 1$/ })).toBeDefined()
  expect(await ui.find({ type: 'Button', text: /^▸ echo 30$/ })).toBeDefined()
  await ui.unmount()
})
