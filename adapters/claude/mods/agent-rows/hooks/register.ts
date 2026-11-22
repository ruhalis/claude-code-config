// agent-rows: the body of each agent's row in the at-a-glance agent list (in
// the terminal, the list under the prompt while agents run). Replaces the
// engine's "name · description · tokens" with
//   <agent type> <model> <effort> · <what it is doing> · <tokens>
// so the type, the resolved model and the configured effort are visible at a
// glance. It took over from the `subagentStatusLine` setting and its jq script
// when Claude Code deprecated that setting in favour of mods.
//
// Loaded through CLAUDE_CODE_PLUGIN_DIRS in settings.json's env, from the
// ~/.claude/mods/agent-rows link install.sh makes.
import type { Register, RenderPropsOf } from 'claude-code'

type Row = RenderPropsOf['AgentRow']

const ESC = '\u001b['
const sgr = (code: string, text: string) => `${ESC}${code}m${text}${ESC}0m`
const dim = (text: string) => sgr('2', text)
const bold = (text: string) => sgr('1', text)

// Columns assumed where the surface has not measured the row.
const DEFAULT_COLUMNS = 80
const LABEL_MAX = 60
const LABEL_MIN = 12

// claude-opus-5-5[-20260901] -> "opus 5.5"; an alias (opus, inherit) stays.
const shortModel = (model: string): string => {
  const m = /claude-([a-z]+)(?:-(\d+)-(\d+))?/.exec(model)
  if (m === null) {
    return model
  }
  const [, family, major, minor] = m

  return major === undefined ? `${family}` : `${family} ${major}.${minor}`
}

const effortText = (effort: Row['effort']): string => {
  // Absent: the agent's definition and the Agent call set none, so it runs at
  // the session's level.
  if (effort === undefined) {
    return dim('session effort')
  }
  const level = String(effort)
  if (level === 'max' || level === 'xhigh') {
    return sgr('35', level) // magenta
  }
  if (level === 'high') {
    return sgr('33', level) // yellow
  }

  return sgr('36', level) // cyan
}

const tokens = (count: number): string => {
  if (count < 1000) {
    return String(count)
  }
  if (count < 10000) {
    return `${Math.floor(count / 100) / 10}k`
  }

  return `${Math.round(count / 1000)}k`
}

// The label is a model's progress summary, line breaks and all, and a line
// break in the body makes the row taller: fold it to one plain line.
const oneLine = (text: string): string =>
  text
    .replace(/\u001b\[[0-9;?]*[ -\/]*[@-~]/g, '')
    .replace(/[\u0000-\u001f\u007f-\u009f]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

const clip = (text: string, max: number): string => {
  const chars = Array.from(text)

  return chars.length > max ? `${chars.slice(0, max - 1).join('')}…` : text
}

const rowBody = (row: Row): string => {
  const who = row.type === 'teammate' ? (row.name ?? row.type) : row.type
  const model = row.model === undefined ? 'model?' : shortModel(row.model)
  const effortPlain = row.effort === undefined ? 'session effort' : String(row.effort)
  const used = tokens(row.tokenCount)

  // Fit the label to what the head and the token count leave, so the count is
  // not the part the row's edge cuts off.
  const fixed = `${who} ${model} ${effortPlain} ·  · ${used}`.length
  const room = (row.columns ?? DEFAULT_COLUMNS) - fixed
  const label = clip(
    oneLine(row.label === '' ? row.description : row.label),
    Math.max(LABEL_MIN, Math.min(LABEL_MAX, room)),
  )

  return `${bold(who)} ${model} ${effortText(row.effort)} · ${dim(label)} · ${dim(used)}`
}

export const register: Register = on => {
  // `body` arrives already set while a subagentStatusLine setting still draws
  // the row; this hook's text replaces it either way.
  on('ui.render', { component: 'AgentRow' }, ($, e, next) =>
    next({ ...e, props: { ...e.props, body: rowBody(e.props) } }),
  )
}
