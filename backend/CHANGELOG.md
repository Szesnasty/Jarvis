# Changelog

## [0.4.1](https://github.com/Szesnasty/Jarvis/compare/backend-v0.4.0...backend-v0.4.1) (2026-04-16)


### 🐛 Bug Fixes

* memory pipeline, entity extraction, chunk truncation ([cc2e91f](https://github.com/Szesnasty/Jarvis/commit/cc2e91fa9b3e21deeee00b4510bf0bd9f7db10f0))


### 🧪 Tests

* update tests to match changed timeout and system prompt behavior ([a002ba0](https://github.com/Szesnasty/Jarvis/commit/a002ba062ebf95d66c1877d5a48157d4ab49e713))

## [0.4.0](https://github.com/Szesnasty/Jarvis/compare/backend-v0.3.0...backend-v0.4.0) (2026-04-16)


### ✨ Features

* local model setup flow — UX polish, cancel download, OS copy, hardware scoring ([eb3c8ea](https://github.com/Szesnasty/Jarvis/commit/eb3c8ea2d30530fd2602968d8aca0769c2b2d65c))
* **local-models:** step 21a - Ollama backend service, hardware probe, model catalog & API ([8adecf2](https://github.com/Szesnasty/Jarvis/commit/8adecf20757f2e6d2d9548f1e6351fa546747b5b))
* **local-models:** step 21d - tool mode detection, health polling, slow response indicator ([ddda282](https://github.com/Szesnasty/Jarvis/commit/ddda2828a7a345b7fc1ad5c467df1ba6dd60ab11))


### 🐛 Bug Fixes

* clear active local model from config when it gets deleted ([aa88d34](https://github.com/Szesnasty/Jarvis/commit/aa88d34266c3e081642b8b3efae9eb569c212f8e))
* **security:** harden ollama base_url handling for CodeQL ([e608a17](https://github.com/Szesnasty/Jarvis/commit/e608a17117569087ccb5d629fc32a0fd60aeadd9))
* use httpx.request() for DELETE body — AsyncClient.delete() doesn't accept json= kwarg ([9d08f76](https://github.com/Szesnasty/Jarvis/commit/9d08f76010376165c2cd19604fb6ee0b0411cf88))

## [0.3.0](https://github.com/Szesnasty/Jarvis/compare/backend-v0.2.0...backend-v0.3.0) (2026-04-16)


### ✨ Features

* **step-20:** graph evidence UI, eval set & step-20 docs ([d14e170](https://github.com/Szesnasty/Jarvis/commit/d14e1703d711895aee24861a5885361869ca39bf))
* **step-20:** semantic search, embedding chunking & graph refactor ([5ecd451](https://github.com/Szesnasty/Jarvis/commit/5ecd4517d6b862d756d68bfd90f97551bf2a2fbd))
* **step-20:** spaCy NER with Polish lemmatization & fuzzy matching ([26ec964](https://github.com/Szesnasty/Jarvis/commit/26ec964a120a00958152799c70cdbbf5839f9df7))

## [0.2.0](https://github.com/Szesnasty/Jarvis/compare/backend-v0.1.0...backend-v0.2.0) (2026-04-15)


### ✨ Features

* conversations auto-save to memory + graph linking ([cb3ae93](https://github.com/Szesnasty/Jarvis/commit/cb3ae93e27ecee164d35d16b5a5a71df0798fde7))
* critical language matching rule in all system prompts ([0d1b433](https://github.com/Szesnasty/Jarvis/commit/0d1b433400095e4f98b4efd79795451efb5f974c))
* delete sessions & memory notes with confirmation dialog ([d3ddf88](https://github.com/Szesnasty/Jarvis/commit/d3ddf8859f71d1ff7545d9d3acde1ba0f991cea7))
* Duel Mode (Council Lite) — Steps 16a+16b ([9cb725e](https://github.com/Szesnasty/Jarvis/commit/9cb725e9aeb6afc5acd3748758f718bd550b7a15))
* implement URL ingest pipeline (step 11 + 11b) — YouTube + web articles ([979404d](https://github.com/Szesnasty/Jarvis/commit/979404d01d8591e5519b44ebd41ad55bd56a4697))
* interactive knowledge graph with entity extraction ([a4168bc](https://github.com/Szesnasty/Jarvis/commit/a4168bcf618d67f18e89a64f987737369f19e777))
* model badge on specialist cards + monochrome provider icons ([69d99bb](https://github.com/Szesnasty/Jarvis/commit/69d99bbaaab24c020f9344f11741c324e5b36609))
* phase 13 — semantic search & hybrid retrieval (steps 19a-19c) ([aa82a4c](https://github.com/Szesnasty/Jarvis/commit/aa82a4c75e5110c94947cd6db67e5f21b06802bc))
* provider icon + timestamp in chat bubbles ([9e534a2](https://github.com/Szesnasty/Jarvis/commit/9e534a20f3aae41d16bb866dcbc24444bcdd1fe8))
* session resume, auto-persist, and WebSocket reliability ([3553f13](https://github.com/Szesnasty/Jarvis/commit/3553f13d30fa7eebe553b0207b45048c5834f4fe))
* show model name per chat message ([cd3c315](https://github.com/Szesnasty/Jarvis/commit/cd3c3151b1794e699df54993b431f3303c21fdde))
* specialist knowledge files with upload and context injection ([4b5d691](https://github.com/Szesnasty/Jarvis/commit/4b5d6916269aae8a0514605945fc8ee29b79a61e))
* step-01 backend init ([e3b669c](https://github.com/Szesnasty/Jarvis/commit/e3b669cfa9583d1970e3e23096ad37dd2ad025b2))
* step-03 onboarding + workspace ([ccf08e1](https://github.com/Szesnasty/Jarvis/commit/ccf08e1fe8f913b0b207b9f98b3a717801d1650a))
* step-04 memory service + sqlite index ([a765043](https://github.com/Szesnasty/Jarvis/commit/a7650436fce9bb1cb5f30a64bdf08c131327b7e1))
* step-05 claude integration + streaming ([89a48df](https://github.com/Szesnasty/Jarvis/commit/89a48dfbe5c2cd1d0e46d9b041a57f0d2a48166c))
* step-07 planning tools + session persistence ([028472f](https://github.com/Szesnasty/Jarvis/commit/028472ff7ad3c0086692f91150238adc55df420e))
* step-08 knowledge graph ([37da338](https://github.com/Szesnasty/Jarvis/commit/37da338d4e859fa0a12fe16c7f96828eb69913c3))
* step-09 specialist system ([d1fb068](https://github.com/Szesnasty/Jarvis/commit/d1fb0682c3ecf518c3d5efc6ba1c4dda18c24938))
* step-10 polish + ingest + settings ([deb844f](https://github.com/Szesnasty/Jarvis/commit/deb844fa7b59daf9a86d0c437d87cefbaf3a9101))
* **step-18a:** multi-provider API keys frontend ([2ac7263](https://github.com/Szesnasty/Jarvis/commit/2ac726375ecacb9e755eb12bce7b28c23d5196a4))
* **step-18b+18c:** LiteLLM multi-provider backend + model selector UI ([b9ad9a8](https://github.com/Szesnasty/Jarvis/commit/b9ad9a8a30765d9469b19e1fd982c0b6ca4b9dad))
* **step-18d:** multi-provider onboarding + keyless workspace init ([6defa5c](https://github.com/Szesnasty/Jarvis/commit/6defa5c5abb297c4e6a3a358d2d2d142ec3abe5f))
* token budget management and UI improvements ([a0ee710](https://github.com/Szesnasty/Jarvis/commit/a0ee7100c8d8b10df1c480b3ff01ffc0df8dd8c8))
* web search, chat improvements & specialist enhancements ([1c189e5](https://github.com/Szesnasty/Jarvis/commit/1c189e5f5d0d96d0d9af909d4cbb6d99f990f4d5))
* WebSocket reliability + markdown rendering + orb nav animation ([7bf9059](https://github.com/Szesnasty/Jarvis/commit/7bf90590732278f6a6123a35c834a8d794402b71))


### 🐛 Bug Fixes

* misc backend improvements ([0d9dab2](https://github.com/Szesnasty/Jarvis/commit/0d9dab22680312eed00bdf10dacd348f56f3facd))
* remove deleted workspace_service functions from settings router ([312c97a](https://github.com/Szesnasty/Jarvis/commit/312c97ab4a70b44c5868f50dd83e756d7b804891))
* resolve 7 bugs — append_note return, token tracking, multi-tool loop, suggest specialist, smart enrich API, markdown rendering, session persistence ([4ddd3d0](https://github.com/Szesnasty/Jarvis/commit/4ddd3d04f3950ea6754b8ac5819fd3999def7993))
* save every conversation to memory + graph ([bc12f2f](https://github.com/Szesnasty/Jarvis/commit/bc12f2fd0fad7821a9a9084dc84895c89f0c9f78))
* security hardening across backend ([c6ff9d1](https://github.com/Szesnasty/Jarvis/commit/c6ff9d1543e584fb5a1140f720fef490ba5a4be0))
* strip non-API fields from messages before sending to Claude ([9431f72](https://github.com/Szesnasty/Jarvis/commit/9431f725f6a2469dda8fdbfa6d5b2369fe7cf2c9))


### 📝 Documentation

* add Tests + DoD to all steps, update coding guidelines with testing rules ([178d0ab](https://github.com/Szesnasty/Jarvis/commit/178d0ab97b76358954036f6cee86376a163243e5))


### ♻️ Refactoring

* simplify config loading and DRY frontend API composable ([cfa746f](https://github.com/Szesnasty/Jarvis/commit/cfa746fb8bf298a90581a5a7bbb5b5d8209781f6))


### 🤖 CI/CD

* add GitHub Actions pipeline, CodeQL, Release Please versioning ([0f6d047](https://github.com/Szesnasty/Jarvis/commit/0f6d047ef3321ea6c5c60e82ea7423e06174efbb))
