import type { DuelConfig, DuelEvent, DuelPhase, DuelVerdict } from '~/types'

type WsSendFn = (data: Record<string, unknown>) => boolean

export function useDuel() {
  const isActive = useState<boolean>('duelActive', () => false)
  const topic = useState<string>('duelTopic', () => '')
  const events = useState<DuelEvent[]>('duelEvents', () => [])
  const phase = useState<DuelPhase>('duelPhase', () => 'idle')
  const verdict = useState<DuelVerdict | null>('duelVerdict', () => null)
  const showSetup = useState<boolean>('duelShowSetup', () => false)
  const specialists = useState<{ id: string; name: string; icon: string }[]>('duelSpecialists', () => [])
  const errorMsg = useState<string>('duelError', () => '')

  let _send: WsSendFn = () => false

  function bindSend(fn: WsSendFn): void {
    _send = fn
  }

  /** Current round text keyed by specialist name. */
  const currentTexts = useState<Record<string, string>>('duelCurrentTexts', () => ({}))

  function start(config: DuelConfig): void {
    isActive.value = true
    phase.value = 'round1'
    events.value = []
    verdict.value = null
    topic.value = config.topic
    currentTexts.value = {}
    errorMsg.value = ''
    showSetup.value = false

    // Attach API key, provider, model — same as regular chat messages
    const { activeProvider, activeKey, activeModel } = useApiKeys()
    const payload: Record<string, unknown> = { type: 'duel_start', ...config }
    payload.provider = activeProvider.value
    payload.model = activeModel.value
    if (activeKey.value) {
      payload.api_key = activeKey.value
    }
    _send(payload)
  }

  function handleWsEvent(raw: DuelEvent): void {
    events.value = [...events.value, raw]

    switch (raw.type) {
      case 'duel_setup':
        if (raw.specialists) specialists.value = raw.specialists
        break

      case 'duel_round_start':
        if (raw.round === 2) phase.value = 'round2'
        currentTexts.value = {}
        break

      case 'duel_specialist_delta':
        if (raw.specialist && raw.content) {
          const prev = currentTexts.value[raw.specialist] ?? ''
          currentTexts.value = { ...currentTexts.value, [raw.specialist]: prev + raw.content }
        }
        break

      case 'duel_specialist_done':
        // Text stays in currentTexts — it's the finished round text
        break

      case 'duel_judge_start':
        phase.value = 'judging'
        break

      case 'duel_judge_done':
        phase.value = 'verdict'
        verdict.value = {
          scores: raw.scores ?? {},
          winner: raw.winner ?? '',
          reasoning: raw.reasoning ?? '',
          recommendation: raw.recommendation ?? '',
          action_items: raw.action_items ?? [],
        }
        break

      case 'duel_done':
        phase.value = 'done'
        break

      case 'duel_error':
        phase.value = 'error'
        errorMsg.value = raw.content ?? 'Unknown duel error'
        break
    }
  }

  function cancel(): void {
    isActive.value = false
    phase.value = 'idle'
    events.value = []
    verdict.value = null
    currentTexts.value = {}
    errorMsg.value = ''
    showSetup.value = false
  }

  function openSetup(): void {
    showSetup.value = true
  }

  function closeSetup(): void {
    showSetup.value = false
  }

  /** Collect finished round texts for a given round number. */
  function getRoundTexts(roundNum: number): Record<string, string> {
    const texts: Record<string, string> = {}
    for (const ev of events.value) {
      if (ev.type === 'duel_specialist_delta' && ev.round === roundNum && ev.specialist) {
        texts[ev.specialist] = (texts[ev.specialist] ?? '') + (ev.content ?? '')
      }
    }
    return texts
  }

  return {
    isActive,
    topic,
    events,
    phase,
    verdict,
    showSetup,
    specialists,
    errorMsg,
    currentTexts,
    bindSend,
    start,
    handleWsEvent,
    cancel,
    openSetup,
    closeSetup,
    getRoundTexts,
  }
}
