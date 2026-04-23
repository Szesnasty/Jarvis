export type SnackbarAction = {
  label: string
  href?: string
  onClick?: () => void
}

export type SnackbarItem = {
  id: number
  message: string
  type: 'error' | 'warning' | 'info' | 'success'
  action?: SnackbarAction
  /** ms until auto-dismiss; 0 = persistent until manually closed */
  duration: number
}

let _nextId = 1

export function useSnackbar() {
  const items = useState<SnackbarItem[]>('snackbar-items', () => [])
  function show(
    message: string,
    options: {
      type?: SnackbarItem['type']
      action?: SnackbarAction
      duration?: number
    } = {},
  ): number {
    const id = _nextId++
    const item: SnackbarItem = {
      id,
      message,
      type: options.type ?? 'info',
      action: options.action,
      duration: options.duration ?? 5000,
    }
    items.value = [...items.value, item]
    if (item.duration > 0) {
      setTimeout(() => dismiss(id), item.duration)
    }
    return id
  }

  function dismiss(id: number): void {
    items.value = items.value.filter(i => i.id !== id)
  }

  function error(message: string, action?: SnackbarAction, duration = 0): number {
    return show(message, { type: 'error', action, duration })
  }

  function warning(message: string, action?: SnackbarAction, duration = 5000): number {
    return show(message, { type: 'warning', action, duration })
  }

  function success(message: string, duration = 3000): number {
    return show(message, { type: 'success', duration })
  }

  return { items, show, dismiss, error, warning, success }
}
