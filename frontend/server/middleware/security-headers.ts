import { randomBytes } from 'node:crypto'

/**
 * Security headers middleware — sets CSP and hardening headers on all responses.
 *
 * CSP strategy:
 * - PRODUCTION: nonce-based script-src. A fresh random nonce is generated per
 *   request and injected into inline <script> tags by the csp-nonce plugin.
 * - DEV: 'unsafe-inline' (Vite HMR needs it; nonce won't help because HMR
 *   injects scripts dynamically).
 * - Styles always need 'unsafe-inline' (Vue scoped styles inject at runtime).
 */
export default defineEventHandler((event) => {
  const config = useRuntimeConfig()

  // Backend origin — used for both HTTP (connect-src) and WS
  const wsUrl: string = (config.public.backendWsUrl as string) || 'ws://127.0.0.1:8000/api/chat/ws'
  // Extract the WS origin (e.g. ws://127.0.0.1:8000)
  const wsOrigin = wsUrl.replace(/\/api\/.*$/, '')
  // HTTP equivalent for API proxy
  const httpOrigin = wsOrigin.replace(/^ws/, 'http')

  const isDev = process.env.NODE_ENV !== 'production'

  // Dev-mode: allow Vite HMR websockets
  const devWsSources = isDev
    ? ' ws://localhost:3000 ws://localhost:24678 ws://127.0.0.1:3000 ws://127.0.0.1:24678'
    : ''

  const connectSrc = `'self' ${httpOrigin} ${wsOrigin}${devWsSources}`

  // Production: per-request nonce for inline scripts (Nuxt SPA bootstrap).
  // Dev: 'unsafe-inline' because Vite HMR injects scripts dynamically.
  let scriptSrc: string
  if (isDev) {
    scriptSrc = "script-src 'self' 'unsafe-inline'"
  } else {
    const nonce = randomBytes(16).toString('base64')
    event.context.cspNonce = nonce
    scriptSrc = `script-src 'self' 'nonce-${nonce}'`
  }

  const csp = [
    "default-src 'self'",
    scriptSrc,
    // style 'unsafe-inline' is required: Vue injects scoped <style> at runtime
    "style-src 'self' 'unsafe-inline'",
    "font-src 'self' data:",
    "img-src 'self' data: blob:",
    `connect-src ${connectSrc}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join('; ')

  setHeaders(event, {
    'Content-Security-Policy': csp,
    'X-Frame-Options': 'DENY',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(self), geolocation=(), payment=()',
  })
})
