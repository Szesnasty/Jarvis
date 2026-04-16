/**
 * Official SVG icons for AI providers (from Simple Icons where available).
 * Each returns a complete <svg> string, sized via the icon container.
 */

export const PROVIDER_ICONS: Record<string, string> = {
  // Official Anthropic logo from Simple Icons
  anthropic: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M17.3041 3.541h-3.6718l6.696 16.918H24Zm-10.6082 0L0 20.459h3.7442l1.3693-3.5527h7.0052l1.3693 3.5528h3.7442L10.5363 3.5409Zm-.3712 10.2232 2.2914-5.9456 2.2914 5.9456Z"/>
  </svg>`,

  // Official OpenAI hex-knot logo
  openai: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.998 5.998 0 0 0-3.998 2.9 6.042 6.042 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073ZM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494ZM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646ZM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872v.024Zm16.597 3.855-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667Zm2.01-3.023-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66v.018ZM8.318 12.861l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.392.68l.006 6.72Zm1.097-2.365L12 8.893l2.585 1.5v2.998L12 14.893l-2.585-1.5v-2.897Z"/>
  </svg>`,

  // Official Google Gemini sparkle logo from Simple Icons
  google: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M11.04 19.32Q12 21.51 12 24q0-2.49.93-4.68.96-2.19 2.58-3.81t3.81-2.55Q21.51 12 24 12q-2.49 0-4.68-.93a12.3 12.3 0 0 1-3.81-2.58 12.3 12.3 0 0 1-2.58-3.81Q12 2.49 12 0q0 2.49-.96 4.68-.93 2.19-2.55 3.81a12.3 12.3 0 0 1-3.81 2.58Q2.49 12 0 12q2.49 0 4.68.96 2.19.93 3.81 2.55t2.55 3.81"/>
  </svg>`,

  // Ollama — llama silhouette / local device icon
  ollama: `<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M9 2a5 5 0 0 0-5 5v3.17A3.001 3.001 0 0 0 2 13v4a3 3 0 0 0 3 3h1v1a1 1 0 1 0 2 0v-1h8v1a1 1 0 1 0 2 0v-1h1a3 3 0 0 0 3-3v-4a3.001 3.001 0 0 0-2-2.83V7a5 5 0 0 0-5-5H9Zm5 2a3 3 0 0 1 3 3v3H7V7a3 3 0 0 1 3-3h4Zm-4.5 8a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Zm5 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Z"/>
  </svg>`,
}

/** Eye-open SVG icon for show/hide password toggle */
export const ICON_EYE_OPEN = `<svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" width="18" height="18">
  <path d="M10 4.5C5.833 4.5 2.275 7.1 1 10.5c1.275 3.4 4.833 6 9 6s7.725-2.6 9-6c-1.275-3.4-4.833-6-9-6Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="10" cy="10.5" r="2.5" stroke="currentColor" stroke-width="1.5"/>
</svg>`

/** Eye-closed SVG icon for show/hide password toggle */
export const ICON_EYE_CLOSED = `<svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" width="18" height="18">
  <path d="M2.5 2.5l15 15M8.352 8.352a2.5 2.5 0 0 0 3.296 3.296" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M5.75 5.818C3.45 7.182 1.95 9.318 1 10.5c1.275 3.4 4.833 6 9 6 1.65 0 3.175-.4 4.5-1.075m2.35-1.7c.9-.95 1.6-2.025 2.15-3.225-1.275-3.4-4.833-6-9-6-.7 0-1.375.075-2.025.2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`

/** Lock/shield icon for security badges */
export const ICON_LOCK = `<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" width="14" height="14">
  <rect x="3" y="7" width="10" height="7" rx="1.5" stroke="currentColor" stroke-width="1.3"/>
  <path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
</svg>`

/** Info icon */
export const ICON_INFO = `<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" width="14" height="14">
  <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.3"/>
  <path d="M8 7v4.5M8 5.25v.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
</svg>`
