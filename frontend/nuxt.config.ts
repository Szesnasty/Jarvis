// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  ssr: false,
  devtools: { enabled: false },

  app: {
    head: {
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
        { rel: 'icon', type: 'image/x-icon', href: '/favicon.ico' },
        { rel: 'icon', type: 'image/png', sizes: '32x32', href: '/favicon-32x32.png' },
        { rel: 'icon', type: 'image/png', sizes: '192x192', href: '/favicon-192x192.png' },
        { rel: 'apple-touch-icon', sizes: '180x180', href: '/apple-touch-icon.png' },
      ],
    },
  },

  css: ['~/assets/css/main.css', '~/assets/css/settings.css'],
  runtimeConfig: {
    public: {
      backendWsUrl: 'ws://127.0.0.1:8000/api/chat/ws',
    },
  },
  nitro: {
    devProxy: {
      '/api': {
        target: 'http://127.0.0.1:8000/api',
        changeOrigin: true,
      },
    },
    routeRules: {
      '/api/**': { proxy: 'http://127.0.0.1:8000/api/**' },
    },
  },
  vite: {
    server: {
      hmr: {
        clientPort: 3000,
      },
    },
    ssr: {
      noExternal: ['force-graph', 'three'],
    },
  },
  typescript: {
    strict: true,
  },
})
