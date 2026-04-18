import { ref } from 'vue'

// Module-level singleton — every settings subcomponent calls this to publish
// short-lived status messages to the page-level banner.
const message = ref('')

export function useSettingsStatus() {
  function set(msg: string) {
    message.value = msg
  }
  function clear() {
    message.value = ''
  }
  return { message, set, clear }
}
