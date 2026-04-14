/**
 * Security headers middleware — sets CSP and hardening headers on all responses.
 *
 * CSP is assembled dynamically to allow:
 * - Self-origin for scripts, styles, images, fonts
 * - Backend API (HTTP + WS) for chat and data
 * - WebSocket connections (ws:// in dev, wss:// in prod)
 * - data: / blob: URIs for inline assets (SVG icons, canvas blobs)
 * - 'unsafe-inline' for styles (Vue scoped styles inject at runtime)
 * - Dev-mode HMR websockets
 */
export default defineEventHandler((event) => {
  const config = useRuntimeConfig()

  // Backend origin — used for both HTTP (connect-src) and WS
  const wsUrl: string = (config.public.backendWsUrl as string) || 'ws://127.0.0.1:8000/api/chat/ws'
  // Extract the WS origin (e.g. ws://127.0.0.1:8000)
  const wsOrigin = wsUrl.replace(/\/api\/.*$/, '')
  // HTTP equivalent for API proxy
  const httpOrigin = wsOrigin.replace(/^ws/, 'http')

  // Dev-mode: allow Vite HMR websockets
  const isDev = process.env.NODE_ENV !== 'production'
  const devSources = isDev
    ? ' ws://localhost:3000 ws://localhost:24678 ws://127.0.0.1:3000 ws://127.0.0.1:24678'
    : ''

  const connectSrc = `'self' ${httpOrigin} ${wsOrigin}${devSources}`

  const csp = [
    "default-src 'self'",
    // unsafe-inline required: Vue injects scoped styles at runtime
    "script-src 'self' 'unsafe-inline'",
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
