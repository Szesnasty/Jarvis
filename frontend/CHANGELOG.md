# Changelog

## [0.16.1](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.16.0...frontend-v0.16.1) (2026-04-25)


### 🐛 Bug Fixes

* **smart-connect:** SQLite lock contention + 2-files badge + banner flicker ([83c4678](https://github.com/Szesnasty/Jarvis/commit/83c46785c83bb3e2e4403d53035bc5e2661a706f))

## [0.16.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.15.0...frontend-v0.16.0) (2026-04-25)


### ✨ Features

* **retrieval:** step 28a — surface per-note retrieval trace in chat UI ([6e5c3b9](https://github.com/Szesnasty/Jarvis/commit/6e5c3b96ff7c16eec0323e43ffdde2f3a5314ffb))
* **step-28a:** retrieval trace UI - add 3 frontend trace tests, mark 28a and step-28 Done ([c25205e](https://github.com/Szesnasty/Jarvis/commit/c25205e9f163f0f2ff7edd9916ae17bba3c54f56))
* **step-28b/UX:** bulk-promote workflow for Smart Connect suggestions ([6e3603e](https://github.com/Szesnasty/Jarvis/commit/6e3603eeae5641286dbcb36b1dece1e5889e60ed))
* **step-28b/UX:** move help affordance, surface section_connect in top bar ([f8308e4](https://github.com/Szesnasty/Jarvis/commit/f8308e4737d0766faafc841f6634cc030cec0e88))
* **step-28b/UX:** SmartConnectStatus badge replaces static help icon ([45405df](https://github.com/Szesnasty/Jarvis/commit/45405dfa4120a92ad61c22e34fc3cf4410b3aeba))
* **step-28b:** help icon nudging user to Smart Connect backfill ([2e100f5](https://github.com/Szesnasty/Jarvis/commit/2e100f5113a168ef35b26a7c5dee626acd224776))
* **step-28b:** memory sidebar document grouping ([aaa969f](https://github.com/Szesnasty/Jarvis/commit/aaa969f044542f940296ed4cc596bba33291440c))


### 🐛 Bug Fixes

* **step-28b/UX:** auto-expand parent doc on Review + tooltip on Smart Connect title ([1b6b186](https://github.com/Szesnasty/Jarvis/commit/1b6b18629f555ba84b8ed0226f96549d6209c91f))
* **step-28b:** toggle document expand/collapse on whole row click ([36a314e](https://github.com/Szesnasty/Jarvis/commit/36a314e3b56b43dce8bee037bab76d00a806f2f4))
* **tests/UX:** fix memory test sort order + SmartConnectStatus tooltip overflow ([afb21bc](https://github.com/Szesnasty/Jarvis/commit/afb21bcfb4915db08dac210eee766bd25253d75e))


### ⚡ Performance

* cap NER text at 20k chars + fix memory limit=200 for folder view ([104f529](https://github.com/Szesnasty/Jarvis/commit/104f529f9daa9d2cf7a6ea1bcfaa7cce6aebac59))

## [0.15.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.14.0...frontend-v0.15.0) (2026-04-25)


### ✨ Features

* **graph:** 'Bridges only' filter — hide entities connected to a single note ([8c85f35](https://github.com/Szesnasty/Jarvis/commit/8c85f3558b60cb9b8af53b40698f1753807dccbc))
* **graph:** auto-reload graph page when rebuild job completes ([31bec9e](https://github.com/Szesnasty/Jarvis/commit/31bec9e68854f1e9fff128f618f15a1af97e68c6))
* **graph:** entity quality + similarity perf + graph UX polish ([4b424d5](https://github.com/Szesnasty/Jarvis/commit/4b424d5147cd021d701641cad5765da58d56c41e))
* **ingest:** auto rebuild graph after every file/url ingest ([43398f2](https://github.com/Szesnasty/Jarvis/commit/43398f2f69684bde315c1bf7d19314ce2054bf1b))
* large-file ingest progress + SQLite stability + workspace reset ([b4e205a](https://github.com/Szesnasty/Jarvis/commit/b4e205ab727866a4e628ea030bd025995f20cbeb))


### 🐛 Bug Fixes

* **graph:** add immediate:true to rebuild watcher ([74bd995](https://github.com/Szesnasty/Jarvis/commit/74bd9951592152c81b03e26f0c5240f776120f7f))
* **graph:** distinct colors for org/project/place/source/batch + 5s status polling ([d04a07d](https://github.com/Szesnasty/Jarvis/commit/d04a07d1063ac42f4a1dc13a45f0b8845c0b63e3))
* **graph:** prevent node overlap — stronger collision (3 iter / 0.82 strength / +24 padding) + more repulsion ([6addb46](https://github.com/Szesnasty/Jarvis/commit/6addb466598864d4aedaa81da6f9a56751144104))
* **graph:** suppress hub nodes (&gt;50 edges) and folder areas by default ([ae74559](https://github.com/Szesnasty/Jarvis/commit/ae7455919ce9031e99609e447b182c77eabc15ed))
* **memory:** move orphan banner above note list, increase prominence ([327199c](https://github.com/Szesnasty/Jarvis/commit/327199c93aafc7e98f2067f9429cd5ec581b4614))

## [0.14.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.13.0...frontend-v0.14.0) (2026-04-25)


### ✨ Features

* **import:** multi-file selection in generic mode ([b184daa](https://github.com/Szesnasty/Jarvis/commit/b184daabbede86cdbebcc5a08337d9fe438b561a))

## [0.13.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.12.0...frontend-v0.13.0) (2026-04-25)


### ✨ Features

* JSON ingest, monochromatic graph mode, CodeQL info-exposure fix ([6d93c0e](https://github.com/Szesnasty/Jarvis/commit/6d93c0e92f98fa39ee93c0c39347417d35a20391))
* **step-26a:** Smart Connect backfill, versioning & dry-run ([425e807](https://github.com/Szesnasty/Jarvis/commit/425e8071bd434e4cd674510dc24eec8230090c2c))
* **step-26c:** score breakdown, event log, stats, keep-all UI ([88c42f4](https://github.com/Szesnasty/Jarvis/commit/88c42f43025746e231118c33974908b102b68870))
* **step-26d:** controlled graph expansion in chat retrieval ([82581e9](https://github.com/Szesnasty/Jarvis/commit/82581e9b64a47a3b671f52667b46dead86771583))


### 🐛 Bug Fixes

* **ui:** clarify Smart Connect backfill description — auto-run, no AI ([1632fca](https://github.com/Szesnasty/Jarvis/commit/1632fca17162d9c47d11d1ee8953c96987b89915))


### 🧪 Tests

* **frontend:** update ImportDialog accept attr to include .json ([ac0153f](https://github.com/Szesnasty/Jarvis/commit/ac0153f5713435fcb0975531984bb980e6e451ef))

## [0.12.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.11.0...frontend-v0.12.0) (2026-04-24)


### ✨ Features

* **connect:** smart connect review UI — step 25 PR 6 ([6894d53](https://github.com/Szesnasty/Jarvis/commit/6894d53338c50727756359c0e4eca03fa7d8c971))

## [0.11.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.10.1...frontend-v0.11.0) (2026-04-24)


### ✨ Features

* **specialists:** add JARVIS-self for system prompt override + extension ([f5abe1a](https://github.com/Szesnasty/Jarvis/commit/f5abe1aeab58ffca4adc80067fe99cb93843d184))


### 📝 Documentation

* docs/features/jarvis-self-specialist.md + registry entry. ([f5abe1a](https://github.com/Szesnasty/Jarvis/commit/f5abe1aeab58ffca4adc80067fe99cb93843d184))


### 🧪 Tests

* **jarvis-self:** cover uncheck-override edge case + 7 more frontend tests ([0d48958](https://github.com/Szesnasty/Jarvis/commit/0d48958e103cd9001f56225bdd9e18c375bcbbcb))

## [0.10.1](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.10.0...frontend-v0.10.1) (2026-04-23)


### 🐛 Bug Fixes

* **local-models:** sync active model to chat selector + snackbar for pull errors ([6774a37](https://github.com/Szesnasty/Jarvis/commit/6774a3723698110b077a39d3da1a08221962fe87))

## [0.10.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.9.0...frontend-v0.10.0) (2026-04-19)


### ✨ Features

* add Jarvis favicon (cyan orb) ([d802a8d](https://github.com/Szesnasty/Jarvis/commit/d802a8d7689f38acadcc6b1cd4cf06510d6a1f8d))

## [0.9.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.8.0...frontend-v0.9.0) (2026-04-19)


### ✨ Features

* **jira:** improve MCP tool descriptions, sprint resolution and status mapping ([fb43915](https://github.com/Szesnasty/Jarvis/commit/fb439156fd8c222a5d671dc475bfc5b0cbde05c1))


### 🐛 Bug Fixes

* **ci:** restore package-lock.json optional deps removed on macOS ([f10f93f](https://github.com/Szesnasty/Jarvis/commit/f10f93f0afd9ccf6f0555c4449e32c0a7b69e993))
* **graph+ci:** dampen drag jitter and prevent lock file regeneration ([b3ac657](https://github.com/Szesnasty/Jarvis/commit/b3ac657c688dc748dc0df6545f187ca6c1043b78))
* **graph:** improve force layout spacing, glow rendering and restore ambient particles ([d946f96](https://github.com/Szesnasty/Jarvis/commit/d946f96320214ef0ae5fb5e4aca60f2898317fd6))
* **graph:** increase node spacing for label readability ([d8f62aa](https://github.com/Szesnasty/Jarvis/commit/d8f62aabcbe7d6ead95b140ca60b9d65f39c5995))
* **graph:** reduce node jitter on hover by increasing physics damping ([89e4a9c](https://github.com/Szesnasty/Jarvis/commit/89e4a9c96050b12e6acb0a81c3d5a175dae2d5fa))

## [0.8.0](https://github.com/Szesnasty/Jarvis/compare/frontend-v0.7.0...frontend-v0.8.0) (2026-04-18)


### ✨ Features

* **mcp:** frontend toggle + Settings panel + ready-to-paste client configs ([a604281](https://github.com/Szesnasty/Jarvis/commit/a6042810bc1f84076fea50ff1015a98afd25a351))


### 🐛 Bug Fixes

* **ci:** add missing mcp dependency and resync frontend lockfile ([569e462](https://github.com/Szesnasty/Jarvis/commit/569e462e414d87d91eea810759046961483c2ab1))


### ♻️ Refactoring

* **frontend:** split settings page into subcomponents + composables ([bcdd3d4](https://github.com/Szesnasty/Jarvis/commit/bcdd3d4b462abc297cebd814b85efb9c54a4431a))
* **mcp:** migrate to local FastMCP CLI and remove SSE ([6b125f5](https://github.com/Szesnasty/Jarvis/commit/6b125f5bce93f12d04182001ca789abeac4ef638))

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
