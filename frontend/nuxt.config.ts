// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  ssr: false,
  devtools: { enabled: false },
  css: ['~/assets/css/main.css'],
  routeRules: {
    '/api/**': { proxy: 'http://127.0.0.1:8000/api/**' },
  },
  typescript: {
    strict: true,
  },
})
