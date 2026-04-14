# Step 18c — Model Selector UI + Per-Specialist Model Config

> **Goal**: Add a model selector to the chat interface and specialist configuration.
> Users pick which model to use per-conversation or per-specialist.
> Model preference persists in localStorage.

**Status**: ⬜ Not started
**Depends on**: Step 18a (provider keys in browser) + Step 18b (LiteLLM backend)

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| Model selector in chat | Dropdown near input bar — pick model for current conversation |
| Per-specialist model config | Specialist wizard step: assign default model |
| Model persistence | Last-used model saved to localStorage per provider |
| Model availability | Only show models for providers with configured keys |
| Cost indicator | Show relative cost (💰💰💰) per model in selector |

---

## File Structure

```
frontend/
  app/
    components/
      ModelSelector.vue         # NEW — dropdown with model list + cost indicators
    composables/
      useApiKeys.ts             # MODIFY — add model preference state
    pages/
      main.vue                  # MODIFY — add ModelSelector near input bar
      specialists.vue           # MODIFY — add model selection to wizard
backend/
  routers/
    chat.py                     # Already handles model from 18b — no changes
  services/
    specialist_service.py       # MODIFY — store default_model in specialist config
```

---

## Model Selector UI

```
┌────────────────────────────────────────────┐
│  Talk to Jarvis...            🤖 ▾  🎤 ⚔️ ➤ │
└────────────────────────────────────────────┘
                                 │
                                 ▼
                    ┌──────────────────────┐
                    │ 🤖 Anthropic         │
                    │   Claude Sonnet 4  ✓ │
                    │   Claude Haiku 4     │
                    │ ✨ OpenAI            │
                    │   GPT-4o             │
                    │   GPT-4o mini   💰   │
                    │   o3-mini            │
                    │ G  Google AI         │
                    │   Gemini 2.5 Flash   │
                    │   Gemini 2.5 Pro     │
                    └──────────────────────┘
```

### Behavior

- Shows only providers with configured keys (from `useApiKeys()`)
- Groups models by provider with provider icon + name as header
- Current model has ✓ checkmark
- Cheapest models get 💰 badge (optional)
- Click selects model → updates `activeModel` in `useApiKeys`
- Selected model sent in WS message `model` field (step 18b)
- Collapsed state shows current model icon (🤖/✨/G)

### Persistence

```typescript
// localStorage key
"jarvis_active_model" → "claude-sonnet-4-20250514"
"jarvis_active_provider" → "anthropic"
```

On load:
1. Read saved model + provider from localStorage
2. Verify that provider's key is still configured
3. If not → fall back to first configured provider's default model

---

## Per-Specialist Model Config

### Specialist JSON (`agents/{id}.json`)

Add optional `default_model` field:

```json
{
  "id": "health-guide",
  "name": "Health Guide",
  "role": "...",
  "default_model": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514"
  }
}
```

### Wizard Addition

In specialist creation/edit wizard, add a "Model" step (optional):

```
┌─────────────────────────────────────────┐
│  Default Model (optional)                │
│                                          │
│  When this specialist is active, use:    │
│  ┌──────────────────────────────────┐    │
│  │ 🤖 Claude Sonnet 4           ▾  │    │
│  └──────────────────────────────────┘    │
│                                          │
│  Leave empty to use conversation model.  │
└─────────────────────────────────────────┘
```

### Activation Flow

When specialist is activated:
1. If specialist has `default_model` → switch to that model (show toast "Switched to Claude Sonnet 4")
2. If user's configured keys don't include that provider → show warning, keep current model
3. If no `default_model` → keep whatever model user has selected

---

## Cost Indicators

Using LiteLLM's `model_cost` data (fetched once from backend or hardcoded):

| Model | Input $/1M | Output $/1M | Badge |
|-------|-----------|------------|-------|
| Claude Sonnet 4 | $3 | $15 | 💰💰 |
| Claude Haiku 4 | $0.80 | $4 | 💰 |
| GPT-4o | $2.50 | $10 | 💰💰 |
| GPT-4o mini | $0.15 | $0.60 | 💰 |
| o3-mini | $1.10 | $4.40 | 💰 |
| Gemini 2.5 Flash | $0.15 | $0.60 | 💰 |
| Gemini 2.5 Pro | $1.25 | $10 | 💰💰 |

Badges: 💰 = budget, 💰💰 = standard, 💰💰💰 = premium

---

## Acceptance Criteria

1. Model selector dropdown appears near chat input
2. Only models for configured providers are shown
3. Selecting a model persists to localStorage
4. WS messages include selected `model` field
5. Specialist wizard has optional model step
6. Activating specialist with `default_model` switches model
7. Missing provider key → graceful fallback
8. Model icons/grouping match provider cards in Settings

---

## Tests

### Frontend (Vitest)
- `ModelSelector` — renders only configured providers' models
- `ModelSelector` — selection persists to localStorage
- Specialist model config — saves/loads `default_model`
- Fallback — unconfigured provider model not selectable

### Backend (pytest)
- Specialist service — `default_model` field in JSON read/write
- No other backend changes needed (18b already handles `model` field)
