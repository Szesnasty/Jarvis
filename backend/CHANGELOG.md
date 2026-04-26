# Changelog

## [0.15.0](https://github.com/Szesnasty/Jarvis/compare/backend-v0.14.1...backend-v0.15.0) (2026-04-26)


### ✨ Features

* SC review badges in NoteList + clearer BulkPromoteBanner ([494f12b](https://github.com/Szesnasty/Jarvis/commit/494f12bfc21685f19fa36c093431211f5b9219f6))


### 🐛 Bug Fixes

* **smart-connect:** clear done signal, visible progress, UX clarity ([649a288](https://github.com/Szesnasty/Jarvis/commit/649a288fecd9dc51820f5d57a912983eddb09471))

## [0.14.1](https://github.com/Szesnasty/Jarvis/compare/backend-v0.14.0...backend-v0.14.1) (2026-04-25)


### 🐛 Bug Fixes

* **smart-connect:** SQLite lock contention + 2-files badge + banner flicker ([83c4678](https://github.com/Szesnasty/Jarvis/commit/83c46785c83bb3e2e4403d53035bc5e2661a706f))

## [0.14.0](https://github.com/Szesnasty/Jarvis/compare/backend-v0.13.0...backend-v0.14.0) (2026-04-25)


### ✨ Features

* **retrieval:** step 28a — surface per-note retrieval trace in chat UI ([6e5c3b9](https://github.com/Szesnasty/Jarvis/commit/6e5c3b96ff7c16eec0323e43ffdde2f3a5314ffb))
* **step-28b/UX:** bulk-promote workflow for Smart Connect suggestions ([6e3603e](https://github.com/Szesnasty/Jarvis/commit/6e3603eeae5641286dbcb36b1dece1e5889e60ed))
* **step-28b:** auto-queue Smart Connect for split-document sections ([7cd535e](https://github.com/Szesnasty/Jarvis/commit/7cd535e8ce9b75331057642600a7fbc3ca153375))
* **step-28b:** memory sidebar document grouping ([aaa969f](https://github.com/Szesnasty/Jarvis/commit/aaa969f044542f940296ed4cc596bba33291440c))
* **step-28c:** eval baseline against reference PDFs ([ffb0276](https://github.com/Szesnasty/Jarvis/commit/ffb02766bc7da0520e3e35e9039228f71c6094b2))
* **step-28d:** section type classification for PDF section notes ([89842be](https://github.com/Szesnasty/Jarvis/commit/89842bee4043fd0bb09a9d5653baeef985baa01a))
* **step-28e:** client estimate specialist ([2fbdff2](https://github.com/Szesnasty/Jarvis/commit/2fbdff20363d969d8c728d0f3893a2c0a610aaab))


### 🐛 Bug Fixes

* **step-28b:** add document_type/parent/section_index to NoteMetadataResponse ([a6c503a](https://github.com/Szesnasty/Jarvis/commit/a6c503a4b6136fdaeccdf99951dc19054a25e01d))
* **step-28b:** idempotent _finalise eliminates Smart Connect git noise ([180fa99](https://github.com/Szesnasty/Jarvis/commit/180fa99a58df2a70a5a60b49a3d08af7d3ddadd4))
* **step-28b:** ingest split-document sections into graph at ingest time ([42e564b](https://github.com/Szesnasty/Jarvis/commit/42e564bceb3290867d23a3e64cdbd9cb7db48e32))


### ⚡ Performance

* cap NER text at 20k chars + fix memory limit=200 for folder view ([104f529](https://github.com/Szesnasty/Jarvis/commit/104f529f9daa9d2cf7a6ea1bcfaa7cce6aebac59))

## [0.13.0](https://github.com/Szesnasty/Jarvis/compare/backend-v0.12.1...backend-v0.13.0) (2026-04-25)


### ✨ Features

* **graph:** entity quality + similarity perf + graph UX polish ([4b424d5](https://github.com/Szesnasty/Jarvis/commit/4b424d5147cd021d701641cad5765da58d56c41e))
* **graph:** skip TOC wikilinks from index notes + prune singleton tags/concepts ([c5884f9](https://github.com/Szesnasty/Jarvis/commit/c5884f94bea72f28bfe6bc188da9536baabe67f2))
* **graph:** step 27b — scale entity caps with body length ([7d136a7](https://github.com/Szesnasty/Jarvis/commit/7d136a7ad7936520610cb0b6e5ba3bdc5362dc62))
* **graph:** step 27c - concept pass improvements for mixed PL/EN PDFs ([004b6ab](https://github.com/Szesnasty/Jarvis/commit/004b6ab9b20ad82f4ed47f1a59aebc183ba6f92c))
* **ingest:** auto rebuild graph after every file/url ingest ([43398f2](https://github.com/Szesnasty/Jarvis/commit/43398f2f69684bde315c1bf7d19314ce2054bf1b))
* **ingest:** step 27a — split large PDFs into per-section notes ([e53aa40](https://github.com/Szesnasty/Jarvis/commit/e53aa4097c710fd1e687c1c7840b748ba3634d84))
* **ingest:** step 27d — section split for txt/md/json/xml ([fd9e18d](https://github.com/Szesnasty/Jarvis/commit/fd9e18dbbe080cfb30d94271ca6cb76ae5d944c3))
* large-file ingest progress + SQLite stability + workspace reset ([b4e205a](https://github.com/Szesnasty/Jarvis/commit/b4e205ab727866a4e628ea030bd025995f20cbeb))


### 🐛 Bug Fixes

* **graph:** distinct colors for org/project/place/source/batch + 5s status polling ([d04a07d](https://github.com/Szesnasty/Jarvis/commit/d04a07d1063ac42f4a1dc13a45f0b8845c0b63e3))
* **hallucination:** raise person extraction threshold + add conversation-vs-knowledge rules to system prompt ([3217805](https://github.com/Szesnasty/Jarvis/commit/3217805e60c39d029b399b1b30e98cdeeadb7c3f))
* **ingest:** remove generic hub tags (imported/pdf/section) from section frontmatter — store as source_type field instead; fix reset:db to also clean .shm/.wal ([dbe2ca9](https://github.com/Szesnasty/Jarvis/commit/dbe2ca9344ccb90637888b790e607624a758f5a5))
* **ingest:** step 27a — drop blank-surround for strict numbered headings, filter TOC, dedup ([70ede83](https://github.com/Szesnasty/Jarvis/commit/70ede8301572cc1557562be965fbc8b4c2144074))
* offload connection_service sync I/O to threadpool (fixes /status pending during linking) ([a1fbf55](https://github.com/Szesnasty/Jarvis/commit/a1fbf550fed656c757f2055b5531a3b7e90939df))
* **security:** parse URL hostname for YouTube detection — fixes CodeQL incomplete substring sanitization ([3cf42f5](https://github.com/Szesnasty/Jarvis/commit/3cf42f583b7ee06adc693869763e99fc44ba8565))

## [0.12.1](https://github.com/Szesnasty/Jarvis/compare/backend-v0.12.0...backend-v0.12.1) (2026-04-25)


### 🐛 Bug Fixes

* **db:** apply busy_timeout to enrichment worker + backfill writers ([45a6d52](https://github.com/Szesnasty/Jarvis/commit/45a6d52f9efa147751331230e4efbffa67e453ad))

## [0.12.0](https://github.com/Szesnasty/Jarvis/compare/backend-v0.11.0...backend-v0.12.0) (2026-04-25)


### ✨ Features

* JSON ingest, monochromatic graph mode, CodeQL info-exposure fix ([6d93c0e](https://github.com/Szesnasty/Jarvis/commit/6d93c0e92f98fa39ee93c0c39347417d35a20391))
* **step-26a:** Smart Connect backfill, versioning & dry-run ([425e807](https://github.com/Szesnasty/Jarvis/commit/425e8071bd434e4cd674510dc24eec8230090c2c))
* **step-26b:** alias guardrails, weak_aliases, retrieval guard ([395452f](https://github.com/Szesnasty/Jarvis/commit/395452f4dd2d7d6c2f87d71baa4cb2890d5ddc79))
* **step-26c:** score breakdown, event log, stats, keep-all UI ([88c42f4](https://github.com/Szesnasty/Jarvis/commit/88c42f43025746e231118c33974908b102b68870))
* **step-26d:** controlled graph expansion in chat retrieval ([82581e9](https://github.com/Szesnasty/Jarvis/commit/82581e9b64a47a3b671f52667b46dead86771583))


### 🐛 Bug Fixes

* **specialists:** sanitize uploaded filenames instead of 422-rejecting ([b8d47e4](https://github.com/Szesnasty/Jarvis/commit/b8d47e46a13baec10642593b667e0da3c776fa9c))

## [0.11.0](https://github.com/Szesnasty/Jarvis/compare/backend-v0.10.0...backend-v0.11.0) (2026-04-24)


### ✨ Features

* **connect:** add alias matcher + NFKD slug fix — step 25 PR 3 ([7d4e888](https://github.com/Szesnasty/Jarvis/commit/7d4e888c947ac0a5423e31fde912d0d0c3b26a7b))
* **connection-service:** smart connect for per-note ingest-time linking ([75efbdb](https://github.com/Szesnasty/Jarvis/commit/75efbdb7ec30f8985f09aa1893f2986a10be9a9e))
* **connect:** semantic orphan repair + connections router — step 25 PR 4 ([c5bba8d](https://github.com/Szesnasty/Jarvis/commit/c5bba8de04bc79907070e6a14b81a6952f361361))
* **connect:** source/batch provenance + dismissals — step 25 PR 5 ([324a727](https://github.com/Szesnasty/Jarvis/commit/324a7276f2c83532a21a155bc9e9851b817285dd))
* **graph:** expand entity nodes to org/project/place — step 25 PR 2 ([759a6bc](https://github.com/Szesnasty/Jarvis/commit/759a6bc208ebcc9ebcda8a1db6993870ee0df4af))


### 🐛 Bug Fixes

* **security:** fix ReDoS in heading regex — replace (.+?)\s*$ with (.+) + rstrip() to eliminate polynomial backtracking (CodeQL high) ([a0f9cbb](https://github.com/Szesnasty/Jarvis/commit/a0f9cbbe1a1bbf74f0637fb9dd1619589d9c82e4))

## [0.10.0](https://github.com/Szesnasty/Jarvis/compare/backend-v0.9.1...backend-v0.10.0) (2026-04-24)


### ✨ Features

* **specialists:** add JARVIS-self for system prompt override + extension ([f5abe1a](https://github.com/Szesnasty/Jarvis/commit/f5abe1aeab58ffca4adc80067fe99cb93843d184))


### 📝 Documentation

* docs/features/jarvis-self-specialist.md + registry entry. ([f5abe1a](https://github.com/Szesnasty/Jarvis/commit/f5abe1aeab58ffca4adc80067fe99cb93843d184))

## [0.9.1](https://github.com/Szesnasty/Jarvis/compare/backend-v0.9.0...backend-v0.9.1) (2026-04-23)


### 🐛 Bug Fixes

* **ci:** repair broken test + patch python-dotenv CVE-2026-28684 ([04a2e1e](https://github.com/Szesnasty/Jarvis/commit/04a2e1e6905da1452b2e271473747e167ada1726))
* **deps:** remove python-dotenv override incompatible with litellm ([4de3760](https://github.com/Szesnasty/Jarvis/commit/4de3760ed5a7cfa18bad345f6d37a9b8a57c198e))
* **local-models:** sync active model to chat selector + snackbar for pull errors ([6774a37](https://github.com/Szesnasty/Jarvis/commit/6774a3723698110b077a39d3da1a08221962fe87))
* **security:** override litellm's vulnerable python-dotenv pin ([3efe07f](https://github.com/Szesnasty/Jarvis/commit/3efe07f9e3076a43b1b349f339e4977b8cf60ca1))

## [0.9.0](https://github.com/Szesnasty/Jarvis/compare/backend-v0.8.0...backend-v0.9.0) (2026-04-19)


### ✨ Features

* **jira:** improve MCP tool descriptions, sprint resolution and status mapping ([fb43915](https://github.com/Szesnasty/Jarvis/commit/fb439156fd8c222a5d671dc475bfc5b0cbde05c1))


### 🐛 Bug Fixes

* **tests:** stabilize CI by marking aspirational NER tests as xfail ([89d9ec0](https://github.com/Szesnasty/Jarvis/commit/89d9ec0584d17610030e5b9c2d30a91562ebfc5d))

## [0.8.0](https://github.com/Szesnasty/Jarvis/compare/backend-v0.7.0...backend-v0.8.0) (2026-04-18)


### ✨ Features

* add MCP server with 25 tools, stdio/SSE transports, cost-class budgets ([6e67612](https://github.com/Szesnasty/Jarvis/commit/6e6761202e6333c7a1d92ad113cd35edea34f3b6))
* **mcp:** frontend toggle + Settings panel + ready-to-paste client configs ([a604281](https://github.com/Szesnasty/Jarvis/commit/a6042810bc1f84076fea50ff1015a98afd25a351))


### 🐛 Bug Fixes

* **ci:** add missing mcp dependency and resync frontend lockfile ([569e462](https://github.com/Szesnasty/Jarvis/commit/569e462e414d87d91eea810759046961483c2ab1))
* **ci:** skip NER-dependent tests when spaCy models unavailable ([73ad82f](https://github.com/Szesnasty/Jarvis/commit/73ad82f70de94c941744a1fc32277748e1d189e8))


### ♻️ Refactoring

* **mcp:** migrate to local FastMCP CLI and remove SSE ([6b125f5](https://github.com/Szesnasty/Jarvis/commit/6b125f5bce93f12d04182001ca789abeac4ef638))

## [0.7.0](https://github.com/Szesnasty/Jarvis/compare/backend-v0.6.0...backend-v0.7.0) (2026-04-18)


### ✨ Features

* add privacy kill-switches & offline mode ([b7d5c24](https://github.com/Szesnasty/Jarvis/commit/b7d5c2425f6586846ecf56812a2d729b72ed045c))


### 🐛 Bug Fixes

* **tests:** update tests for privacy guard and sprint label injection ([33ed70a](https://github.com/Szesnasty/Jarvis/commit/33ed70a4b44b07ac2a871d48fa8ee3784f464214))

## [0.6.0](https://github.com/Szesnasty/Jarvis/compare/backend-v0.5.0...backend-v0.6.0) (2026-04-18)


### ✨ Features

* remove length limits on enrichment output ([4e7ebe9](https://github.com/Szesnasty/Jarvis/commit/4e7ebe980de216252bae1206fc8ae01d2d79a324))
* **specialists:** add system_prompt field and bake in Jira PM prompt ([db2a157](https://github.com/Szesnasty/Jarvis/commit/db2a157dc2a7ac9cb27d7364f1d0d13e126b6967))
* track tool usage metrics and add token savings tests ([8c83a69](https://github.com/Szesnasty/Jarvis/commit/8c83a69b3789c654c256aaa3d69c4b55d56f2426))


### 🐛 Bug Fixes

* always start enrichment workers on backend startup ([c792e47](https://github.com/Szesnasty/Jarvis/commit/c792e477b3069b9775de96a59219dbf2c4931acf))
* **specialists:** return list from GET /active so UI reflects activation ([c8c0e62](https://github.com/Szesnasty/Jarvis/commit/c8c0e62c406408295c6679d5518874c41f565488))
* truncate produces strings within Pydantic max_length ([9d45f71](https://github.com/Szesnasty/Jarvis/commit/9d45f71a07c8deb615ac29af186bb7ca99bcb9c7))


### ⚡ Performance

* **chat:** cap oversized tool_results and compact stale rounds ([46b3afa](https://github.com/Szesnasty/Jarvis/commit/46b3afa8556ea6dffa2362b221b62aad97c69df7))

## [0.5.0](https://github.com/Szesnasty/Jarvis/compare/backend-v0.4.1...backend-v0.5.0) (2026-04-17)


### ✨ Features

* **22e:** cross-source linking + Jira Strategist specialist ([07d2f23](https://github.com/Szesnasty/Jarvis/commit/07d2f2347e65a1fcaa6a47b5d456648fa0022672))
* **22f:** Jira-aware hybrid retrieval pipeline ([458d92a](https://github.com/Szesnasty/Jarvis/commit/458d92a9c40d4a7770b082f0fb91ccfc3d3befa1))
* **22g:** Jira Strategist specialist + tools + duel presets ([d882081](https://github.com/Szesnasty/Jarvis/commit/d8820815a55304bee402ff99b970b422acda4d53))
* add enrichment pipeline and soft graph edges ([93d5473](https://github.com/Szesnasty/Jarvis/commit/93d5473c4efd05aaaa7a276316fa40fd5baa1f82))
* **chunking:** multi-granularity strategy - 2.6x more vectors per Jira issue ([959ab97](https://github.com/Szesnasty/Jarvis/commit/959ab97a723ada124d897ceae09dd58af27b4dac))
* **enrichment:** add Cancel button to stop sharpen queue ([cf7e00d](https://github.com/Szesnasty/Jarvis/commit/cf7e00d6c1c714787785d155d611edbb3d4767dd))
* **enrichment:** one-click 'sharpen all' via local AI from Settings ([0a5f25d](https://github.com/Szesnasty/Jarvis/commit/0a5f25dfa53f2a1d03c1130ec81f327b5afede15))
* **ingest:** support large jira csv/xml imports ([08eb0c9](https://github.com/Szesnasty/Jarvis/commit/08eb0c9ac86de7c85a66bd3c8d9d024ab81c455e))
* Jira import UX, graph colors, and node preview improvements ([e55708e](https://github.com/Szesnasty/Jarvis/commit/e55708eeb8e96192005f4c07d854b80712b448bd))
* **jira:** add streaming XML and CSV ingest ([8392d9d](https://github.com/Szesnasty/Jarvis/commit/8392d9d435f6e6ca9f21f98c8b6df408aeaa7ba2))
* **retrieval:** denser chunking + local cross-encoder reranker ([4444d26](https://github.com/Szesnasty/Jarvis/commit/4444d26cc968fb542ac1a3862db792c386a805f5))
* **settings:** battery toggle for enrichment worker ([8006cbf](https://github.com/Szesnasty/Jarvis/commit/8006cbf4ea4bb88c2782124a5153551387925280))
* **settings:** selectable enrichment model and robust sharpen progress ([330fd12](https://github.com/Szesnasty/Jarvis/commit/330fd1269e745adc2ff5bb4de46f0d9aee962ef6))


### 🐛 Bug Fixes

* **22:** Jira issues indexed into notes table + chunk embeddings + PL vocab ([1cad68b](https://github.com/Szesnasty/Jarvis/commit/1cad68be95f1a6c779eccff149b64d69fd37417d))
* **enrichment:** unload Ollama model on cancel to stop GPU heat ([4bda714](https://github.com/Szesnasty/Jarvis/commit/4bda714892890e9cc16503e1af73f55b73c6fcf0))
* resolve CodeQL security warnings and failing tests ([8eb1b3f](https://github.com/Szesnasty/Jarvis/commit/8eb1b3fe3e4a9bfd04bd5e25735233701652a5e2))
* **security:** restrict CORS headers + add missing pytest-asyncio dep ([9ad05dc](https://github.com/Szesnasty/Jarvis/commit/9ad05dc825398c872da4c75c49208504902c89cd))
* **tests:** update upload size limit constant to 500 MB ([4237cfd](https://github.com/Szesnasty/Jarvis/commit/4237cfd136686e16e75dd4fdf3a3a49bc54adb05))

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
