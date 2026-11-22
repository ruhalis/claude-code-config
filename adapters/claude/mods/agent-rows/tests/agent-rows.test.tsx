import { expect, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On, RenderPropsOf } from 'claude-code'

type Row = RenderPropsOf['AgentRow']

const ROW: Row = {
  id: 'a1',
  description: 'Run the test suite',
  type: 'verifier',
  status: 'running',
  kind: 'local_agent',
  taskStatus: 'running',
  label: 'Run the test suite',
  startTime: 0,
  cwd: '/',
  model: 'claude-sonnet-5-5-20260901',
  effort: 'medium',
  tokenCount: 12345,
  tokenSamples: [],
  hasRow: true,
  rowIds: ['a1'],
  columns: 120,
  isHidden: false,
}

// SGR styles off, so a test reads the words.
const plain = (text: string | undefined) =>
  (text ?? '').replace(/\u001b\[[0-9;]*m/g, '')

// Stands for the engine's own row, beneath the mod, and answers a function that
// mounts one row and gives the body the mod passed down to it.
const rows = (on: On) => {
  let body: string | undefined
  on('ui.render', { component: 'AgentRow' }, ($, e) => {
    const { Text } = $.ui.resolve(e)
    body = e.props.body

    return <Text>row</Text>
  })

  return async ($: Engine, props: Row) => {
    body = undefined
    const ui = await $.ui.mount({
      plugin: 'agent-rows',
      surface: 'terminal',
      component: 'AgentRow',
      requestId: props.id,
      props,
    })
    await ui.unmount()

    return body
  }
}

test('a row reads type, model, effort, task and tokens', async ($, on) => {
  const bodyOf = rows(on)
  const body = await bodyOf($, ROW)

  expect(plain(body)).toBe('verifier sonnet 5.5 medium · Run the test suite · 12k')
  // The type is bold, the effort coloured by its level (medium: cyan).
  expect(body).toContain('\u001b[1mverifier\u001b[0m')
  expect(body).toContain('\u001b[36mmedium\u001b[0m')
})

test('a body the settings already drew is replaced', async ($, on) => {
  const bodyOf = rows(on)
  const body = await bodyOf($, { ...ROW, body: 'from subagentStatusLine' })

  expect(plain(body)).toBe('verifier sonnet 5.5 medium · Run the test suite · 12k')
})

test('no effort set reads as the session effort', async ($, on) => {
  const bodyOf = rows(on)
  const { effort: _, ...row } = ROW
  const body = await bodyOf($, row)

  expect(plain(body)).toBe(
    'verifier sonnet 5.5 session effort · Run the test suite · 12k',
  )
})

test('a numeric effort is drawn as written', async ($, on) => {
  const bodyOf = rows(on)
  const body = await bodyOf($, { ...ROW, effort: 8000 })

  expect(plain(body)).toContain('sonnet 5.5 8000 · ')
})

test('xhigh is magenta, high yellow', async ($, on) => {
  const bodyOf = rows(on)
  expect(await bodyOf($, { ...ROW, effort: 'xhigh' })).toContain(
    '\u001b[35mxhigh\u001b[0m',
  )
  expect(await bodyOf($, { ...ROW, id: 'a2', effort: 'high' })).toContain(
    '\u001b[33mhigh\u001b[0m',
  )
})

test('no model yet reads model?, an alias stays as it is', async ($, on) => {
  const bodyOf = rows(on)
  const { model: _, ...row } = ROW

  expect(plain(await bodyOf($, row))).toContain('verifier model? medium')
  expect(
    plain(await bodyOf($, { ...ROW, id: 'a2', model: 'opus' })),
  ).toContain('verifier opus medium')
  expect(
    plain(await bodyOf($, { ...ROW, id: 'a3', model: 'claude-fable-5-2' })),
  ).toContain('verifier fable 5.2 medium')
})

test('a progress summary of several lines stays one row', async ($, on) => {
  const bodyOf = rows(on)
  const body = await bodyOf($, {
    ...ROW,
    label: 'Reading files\n\n  then \u001b[31mrunning\u001b[0m\tthe build\u0007',
  })

  expect(body).not.toContain('\n')
  expect(plain(body)).toBe(
    'verifier sonnet 5.5 medium · Reading files then running the build · 12k',
  )
})

test('a long task is cut so the token count stays in the row', async ($, on) => {
  const bodyOf = rows(on)
  const label = 'x'.repeat(200)
  const wide = plain(await bodyOf($, { ...ROW, label }))
  const { columns: _, ...unmeasured } = { ...ROW, id: 'a2', label }
  const narrow = plain(await bodyOf($, unmeasured))

  // 120 columns leave more than the cap of 60.
  expect(wide).toBe(`verifier sonnet 5.5 medium · ${'x'.repeat(59)}… · 12k`)
  // Unmeasured rows are taken as 80 columns: the whole body fits them.
  expect(narrow.endsWith('… · 12k')).toBe(true)
  expect(Array.from(narrow).length).toBe(80)
})

test('token counts shorten as they grow', async ($, on) => {
  const bodyOf = rows(on)
  expect(plain(await bodyOf($, { ...ROW, tokenCount: 0 }))).toMatch(/ · 0$/)
  expect(
    plain(await bodyOf($, { ...ROW, id: 'a2', tokenCount: 1250 })),
  ).toMatch(/ · 1\.2k$/)
  expect(
    plain(await bodyOf($, { ...ROW, id: 'a3', tokenCount: 187600 })),
  ).toMatch(/ · 188k$/)
})

test('a teammate is named by its name', async ($, on) => {
  const bodyOf = rows(on)
  const body = await bodyOf($, {
    ...ROW,
    type: 'teammate',
    name: 'reviewer',
    kind: 'in_process_teammate',
  })

  expect(plain(body)).toMatch(/^reviewer sonnet 5\.5 medium · /)
})
