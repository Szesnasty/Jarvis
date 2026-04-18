# Changelog

## [0.7.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.6.0...frontend-v0.7.0) (2026-04-18)


### ✨ Features

* add privacy kill-switches & offline mode ([b7d5c24](https://github.com/Szesnasty/Jarvis/commit/b7d5c2425f6586846ecf56812a2d729b72ed045c))


### 🐛 Bug Fixes

* **ci:** restore package-lock.json, remove from .gitignore, drop bun.lock ([0d236cc](https://github.com/Szesnasty/Jarvis/commit/0d236ccc0660f5fec40215e7468dac1b1fb3243e))

## [0.6.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.5.0...frontend-v0.6.0) (2026-04-18)


### ✨ Features

* **graph:** cluster Jira issues by sprint with hover focus and dynamic type filters ([daeb16a](https://github.com/Szesnasty/Jarvis/commit/daeb16ae4bbdfd78ec6852f72a21f65457b27746))
* **graph:** highlight edges connected to focused node ([cd5536c](https://github.com/Szesnasty/Jarvis/commit/cd5536ca1fbdaa9dc3f0c985f46ad85cd158b5be))
* **specialists:** add system_prompt field and bake in Jira PM prompt ([db2a157](https://github.com/Szesnasty/Jarvis/commit/db2a157dc2a7ac9cb27d7364f1d0d13e126b6967))
* track tool usage metrics and add token savings tests ([8c83a69](https://github.com/Szesnasty/Jarvis/commit/8c83a69b3789c654c256aaa3d69c4b55d56f2426))


### 🐛 Bug Fixes

* **ci:** include cross-platform binaries in lockfile (linux + darwin) ([1150604](https://github.com/Szesnasty/Jarvis/commit/115060443cb99a255eeeab4b7e10cbe8ddf5f4a7))
* **ci:** regenerate package-lock.json to sync with package.json ([dcbbdd1](https://github.com/Szesnasty/Jarvis/commit/dcbbdd16a5a9aa4d55082372b555545c98ca45e8))
* sharpen progress bar counts skipped/failed items as done ([fc99fd6](https://github.com/Szesnasty/Jarvis/commit/fc99fd6854083529ec9ff9effce37a8ba22bef05))

## [0.5.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.4.1...frontend-v0.5.0) (2026-04-17)


### ✨ Features

* **enrichment:** add Cancel button to stop sharpen queue ([cf7e00d](https://github.com/Szesnasty/Jarvis/commit/cf7e00d6c1c714787785d155d611edbb3d4767dd))
* **enrichment:** one-click 'sharpen all' via local AI from Settings ([0a5f25d](https://github.com/Szesnasty/Jarvis/commit/0a5f25dfa53f2a1d03c1130ec81f327b5afede15))
* **ingest:** support large jira csv/xml imports ([08eb0c9](https://github.com/Szesnasty/Jarvis/commit/08eb0c9ac86de7c85a66bd3c8d9d024ab81c455e))
* Jira import UX, graph colors, and node preview improvements ([e55708e](https://github.com/Szesnasty/Jarvis/commit/e55708eeb8e96192005f4c07d854b80712b448bd))
* **settings:** battery toggle for enrichment worker ([8006cbf](https://github.com/Szesnasty/Jarvis/commit/8006cbf4ea4bb88c2782124a5153551387925280))
* **settings:** progress bar for local AI sharpening ([9cb9650](https://github.com/Szesnasty/Jarvis/commit/9cb9650a13e1fd438826a30dcbc17bbad5d55920))
* **settings:** selectable enrichment model and robust sharpen progress ([330fd12](https://github.com/Szesnasty/Jarvis/commit/330fd1269e745adc2ff5bb4de46f0d9aee962ef6))


### 🐛 Bug Fixes

* **settings:** persist sharpen progress across navigation ([9dcb37d](https://github.com/Szesnasty/Jarvis/commit/9dcb37d127af02bccae6e566850d961a4b8e0965))
* **settings:** prevent NaN in sharpen progress state restore ([234f0e2](https://github.com/Szesnasty/Jarvis/commit/234f0e2985b8da8401f5fdf066e778bb08f37410))
* **tests:** update frontend accept attribute assertions for csv/xml ([122aa3f](https://github.com/Szesnasty/Jarvis/commit/122aa3f3d6f3c631306c417913b2abbfe23d5f04))

## [0.4.1](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.4.0...frontend-v0.4.1) (2026-04-16)


### 🐛 Bug Fixes

* memory pipeline, entity extraction, chunk truncation ([cc2e91f](https://github.com/Szesnasty/Jarvis/commit/cc2e91fa9b3e21deeee00b4510bf0bd9f7db10f0))

## [0.4.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.3.0...frontend-v0.4.0) (2026-04-16)


### ✨ Features

* cancel download button on LocalModelCard — works in settings and onboarding ([55cd9e7](https://github.com/Szesnasty/Jarvis/commit/55cd9e72053077331f9146470bfa50450773e7c0))
* local model setup flow — UX polish, cancel download, OS copy, hardware scoring ([eb3c8ea](https://github.com/Szesnasty/Jarvis/commit/eb3c8ea2d30530fd2602968d8aca0769c2b2d65c))
* **local-models:** step 21b - Settings UI, model cards, pull progress, ModelSelector integration ([faeddae](https://github.com/Szesnasty/Jarvis/commit/faeddaef2182c4ae1246c97dcf04f16966c8e634))
* **local-models:** step 21c - two-path onboarding (Cloud vs Local), keyless workspace ([7ecfcb0](https://github.com/Szesnasty/Jarvis/commit/7ecfcb086f4df96c8b93a2f17ce2c29492672fc5))
* **local-models:** step 21d - tool mode detection, health polling, slow response indicator ([ddda282](https://github.com/Szesnasty/Jarvis/commit/ddda2828a7a345b7fc1ad5c467df1ba6dd60ab11))
* **onboarding:** redesign local setup as 3-step wizard with OS-aware install ([00d1c19](https://github.com/Szesnasty/Jarvis/commit/00d1c192727f52137373413cf626e7c69f70a718))
* show recommended hardware per model card + best picks in hw summary card ([7b05512](https://github.com/Szesnasty/Jarvis/commit/7b0551220c3abf62e23a397518d3f191e4397c75))


### 🐛 Bug Fixes

* add missing imports in useLocalSetupFlow (useLocalModels, ModelRecommendation type) ([8a7b6c6](https://github.com/Szesnasty/Jarvis/commit/8a7b6c6888826194198d9a340ef6bc396e466b42))
* show all model info in compact mode; label recommended RAM explicitly ([54f3ebc](https://github.com/Szesnasty/Jarvis/commit/54f3ebcdbf39373ed5341003fdd0cc7b77635735))
* strip ollama_chat/ prefix in ModelSelector trigger label ([e526992](https://github.com/Szesnasty/Jarvis/commit/e5269927d2ed74025e0e8bb96e6a2fbb4b909685))
* sync model selection to useApiKeys + fix onboarding navigation ([db73ec0](https://github.com/Szesnasty/Jarvis/commit/db73ec06ede1ce7f17c477909577a0eb0d28e6e4))

## [0.3.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.2.1...frontend-v0.3.0) (2026-04-16)


### ✨ Features

* **step-20:** graph evidence UI, eval set & step-20 docs ([d14e170](https://github.com/Szesnasty/Jarvis/commit/d14e1703d711895aee24861a5885361869ca39bf))

## [0.2.1](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.2.0...frontend-v0.2.1) (2026-04-15)


### 🐛 Bug Fixes

* remove top-level await in index.vue to fix blank page on first load ([49db6bd](https://github.com/Szesnasty/Jarvis/commit/49db6bd49363c257f4d1c129ecced6422033601f))
* remove top-level await in index.vue to fix blank page on first load ([fb83bdf](https://github.com/Szesnasty/Jarvis/commit/fb83bdff35a5ed5b528209b8ccef2a6d76bf4ff4))

## [0.2.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.1.0...frontend-v0.2.0) (2026-04-15)


### ✨ Features

* add and setup codument ([c0c2cca](https://github.com/Szesnasty/Jarvis/commit/c0c2cca4740d3efc7354fef654dc067e3364e553))
* add user-friendly tooltips for specialist tools step ([fb200d7](https://github.com/Szesnasty/Jarvis/commit/fb200d732fdfe773b8d2c486f7b96a182aeb32e6))
* auto-rebuild knowledge graph on view enter ([f298aea](https://github.com/Szesnasty/Jarvis/commit/f298aeae38b311bf634fd3376c38c37aed146d8c))
* CSP + security headers middleware ([5e1891e](https://github.com/Szesnasty/Jarvis/commit/5e1891e518b53b3f58df5116086c8e9a1bd5574c))
* delete sessions & memory notes with confirmation dialog ([d3ddf88](https://github.com/Szesnasty/Jarvis/commit/d3ddf8859f71d1ff7545d9d3acde1ba0f991cea7))
* Duel Mode (Council Lite) — Steps 16a+16b ([9cb725e](https://github.com/Szesnasty/Jarvis/commit/9cb725e9aeb6afc5acd3748758f718bd550b7a15))
* implement URL ingest pipeline (step 11 + 11b) — YouTube + web articles ([979404d](https://github.com/Szesnasty/Jarvis/commit/979404d01d8591e5519b44ebd41ad55bd56a4697))
* interactive knowledge graph with entity extraction ([a4168bc](https://github.com/Szesnasty/Jarvis/commit/a4168bcf618d67f18e89a64f987737369f19e777))
* model badge on specialist cards + monochrome provider icons ([69d99bb](https://github.com/Szesnasty/Jarvis/commit/69d99bbaaab24c020f9344f11741c324e5b36609))
* phase 13 — semantic search & hybrid retrieval (steps 19a-19c) ([aa82a4c](https://github.com/Szesnasty/Jarvis/commit/aa82a4c75e5110c94947cd6db67e5f21b06802bc))
* provider icon + timestamp in chat bubbles ([9e534a2](https://github.com/Szesnasty/Jarvis/commit/9e534a20f3aae41d16bb866dcbc24444bcdd1fe8))
* session resume, auto-persist, and WebSocket reliability ([3553f13](https://github.com/Szesnasty/Jarvis/commit/3553f13d30fa7eebe553b0207b45048c5834f4fe))
* show current model in Duel Mode setup panel ([8078de6](https://github.com/Szesnasty/Jarvis/commit/8078de6b7a9e77415e5d7f4a60b303f648b4ac0f))
* show model name per chat message ([cd3c315](https://github.com/Szesnasty/Jarvis/commit/cd3c3151b1794e699df54993b431f3303c21fdde))
* specialist knowledge files with upload and context injection ([4b5d691](https://github.com/Szesnasty/Jarvis/commit/4b5d6916269aae8a0514605945fc8ee29b79a61e))
* specialist model picker in wizard step 4 + duel panel z-index fix ([55c693a](https://github.com/Szesnasty/Jarvis/commit/55c693a1d98d5f1b27f4e008b80b9b4cb8311542))
* step-02 frontend init (nuxt) ([d4218bf](https://github.com/Szesnasty/Jarvis/commit/d4218bf90f2538ad2c8e3ab47b455df0f0845ca0))
* step-03 onboarding + workspace ([ccf08e1](https://github.com/Szesnasty/Jarvis/commit/ccf08e1fe8f913b0b207b9f98b3a717801d1650a))
* step-04 memory service + sqlite index ([a765043](https://github.com/Szesnasty/Jarvis/commit/a7650436fce9bb1cb5f30a64bdf08c131327b7e1))
* step-05 claude integration + streaming ([89a48df](https://github.com/Szesnasty/Jarvis/commit/89a48dfbe5c2cd1d0e46d9b041a57f0d2a48166c))
* step-06 voice input/output ([39518c5](https://github.com/Szesnasty/Jarvis/commit/39518c5d2232ac5520e9b5ffec2e7503f5725cbb))
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

* duel verdict scroll — match ChatPanel flex pattern with max-width ([a87023c](https://github.com/Szesnasty/Jarvis/commit/a87023c6835dc9f464ab2b43f51b0befcc8e3333))
* **frontend/tests:** mock GraphCanvas to prevent force-graph JSDOM errors ([2360b3b](https://github.com/Szesnasty/Jarvis/commit/2360b3be24d6cd9b90828344cc214acb9d222d02))
* **frontend:** fix remaining 3 test failures ([2ea395e](https://github.com/Szesnasty/Jarvis/commit/2ea395eee00f979dedea226a12876932a7b84272))
* **frontend:** pin crossws ^0.4.5 as explicit dependency ([61da467](https://github.com/Szesnasty/Jarvis/commit/61da467a6dd74f11fbafe8242175c99872679f3d))
* **frontend:** update crossws to 0.4.5 to fix npm ci lock file mismatch ([79e0f2b](https://github.com/Szesnasty/Jarvis/commit/79e0f2bdebc841e1292400908fd0aac02eaaf4e9))
* living graph particles + model selection persistence ([ce2dd02](https://github.com/Szesnasty/Jarvis/commit/ce2dd027616928255fdfb98fe443f36935436e74))
* production build — API proxy + nonce CSP + defensive guards ([05037fe](https://github.com/Szesnasty/Jarvis/commit/05037feef42eab1eec2d42b00fe17ef5764dc46d))
* remove deleted workspace_service functions from settings router ([312c97a](https://github.com/Szesnasty/Jarvis/commit/312c97ab4a70b44c5868f50dd83e756d7b804891))
* replace emoji icons with official SVG logos, widen settings ([23b6383](https://github.com/Szesnasty/Jarvis/commit/23b6383aed71811d57d8513af0b32f7d4f9e0a43))
* resolve 7 bugs — append_note return, token tracking, multi-tool loop, suggest specialist, smart enrich API, markdown rendering, session persistence ([4ddd3d0](https://github.com/Szesnasty/Jarvis/commit/4ddd3d04f3950ea6754b8ac5819fd3999def7993))


### 📝 Documentation

* add screenshots, LICENSE (Apache 2.0), SECURITY, CODE_OF_CONDUCT, CONTRIBUTING ([ba2464e](https://github.com/Szesnasty/Jarvis/commit/ba2464ed676a35a4fe51192c5f947be90b02147c))


### ♻️ Refactoring

* simplify config loading and DRY frontend API composable ([cfa746f](https://github.com/Szesnasty/Jarvis/commit/cfa746fb8bf298a90581a5a7bbb5b5d8209781f6))


### 🤖 CI/CD

* add GitHub Actions pipeline, CodeQL, Release Please versioning ([0f6d047](https://github.com/Szesnasty/Jarvis/commit/0f6d047ef3321ea6c5c60e82ea7423e06174efbb))
