// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  ssr: false,
  devtools: { enabled: false },
  css: ['~/assets/css/main.css'],
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
