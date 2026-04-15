# Jarvis

Personal memory, planning, and knowledge system.
Local Markdown memory + knowledge graph + Claude API.

Works on **macOS, Linux, and Windows** — one command, same on every OS.

## Requirements

If you use the direct npm flow, install these **before** running Jarvis.
If you use the bootstrap installers in Quick start, Node.js can be downloaded locally on demand.

### 1. Node.js 20+
Comes with `npm`. Check: `node --version`

> **Don't have Node.js?** Use a bootstrap installer below. It can download a local Node runtime after confirmation (no admin rights needed).

- macOS: `brew install node`
- Linux: [nodejs.org](https://nodejs.org/) or [nvm](https://github.com/nvm-sh/nvm)
- Windows: [nodejs.org installer](https://nodejs.org/) or [nvm-windows](https://github.com/coreybutler/nvm-windows)

### 2. Python 3.12 or 3.13
Check: `python3 --version` (macOS/Linux) or `py --version` / `python --version` (Windows).
**Python 3.14+ is not yet supported** — many ML packages lack prebuilt wheels for it.

> **Don't have Python?** The install script will offer to download a local copy automatically — no admin rights needed.

- macOS: `brew install python@3.12`
- Linux (Debian/Ubuntu): `sudo apt install python3.12 python3.12-venv`
- Windows: download **3.12.x** or **3.13.x** from [python.org](https://www.python.org/downloads/) — **tick "Add Python to PATH"** during install (the installer also adds the `py` launcher which the script will use automatically)

### 3. Anthropic API key
Get one at https://console.anthropic.com — you'll paste it into the app on first run.

## Quick start

After unzipping/cloning the repo, open a terminal in the project folder and run:

### Zero-prereq bootstrap (recommended for non-programmers)

- Windows (PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap\install.ps1
```

- macOS / Linux:

```bash
bash ./bootstrap/install.sh
```

Bootstrap scripts ask for confirmation before downloading local runtimes, then run the same `wake-up-jarvis` flow.

### npm flow (when Node.js is already installed)

```bash
npm run wake-up-jarvis
```

> Shorter aliases all do the same thing: `npm run wake`, `npm start`.
> If you happen to use Yarn instead of npm, `yarn wake-up-jarvis` / `yarn wake` / `yarn start` work too — but **you don't need Yarn**, npm ships with Node.js.

**That's it. One command, same on every OS.** It will:

1. **Run a preflight check** — verify Node 20+, npm 9+, and Python 3.12–3.13 are installed
2. **Wake up the backend** — find (or download) Python, create a venv, install backend deps
3. **Wake up the frontend** — install Node deps
4. **Build the interface** — compile the production Nuxt bundle
5. **Start both servers** in parallel:
   - **Backend** on http://localhost:8000
   - **Frontend** on http://localhost:3000

When you see both servers ready, open **http://localhost:3000** and paste your Anthropic API key on the onboarding screen.

Put Jarvis back to sleep with **`Ctrl+C`**.

> Run `npm run preflight` on its own to just check your system without installing anything.
> The first run takes a minute or two (install + build); subsequent runs are faster because deps are cached, but the frontend is rebuilt each time to guarantee you're running the latest code.

## Already installed? Just run it

If Jarvis is already installed and built and you only want to start the servers again (skipping install + build):

```bash
npm run serve
```

## Developer mode (HMR + auto-reload)

If you're editing the code and want hot module replacement and backend auto-reload:

```bash
npm run dev
```

Dev mode runs Vite's dev server for the frontend and uvicorn with `--reload` for the backend. Slower to start, hotter feedback loop.

## All commands

```bash
# Preflight
npm run preflight          # check Node / npm / Python versions, no side effects

# Install
npm run install:all        # backend (venv + pip) and frontend (npm)
npm run install:backend    # backend only
npm run install:frontend   # frontend only

# Production (optimized build)
npm run wake-up-jarvis     # preflight + install + build + serve (the full experience)
npm run wake               # alias for wake-up-jarvis
npm start                  # alias for wake-up-jarvis
npm run build              # nuxt build → frontend/.output
npm run serve              # serve backend (:8000) + frontend (:3000) in parallel
npm run serve:backend      # production backend only (uvicorn, no --reload)
npm run serve:frontend     # production frontend only (node .output/server/index.mjs)

# Development (HMR + auto-reload)
npm run dev                # dev backend + dev frontend in parallel
npm run dev:backend        # uvicorn --reload
npm run dev:frontend       # nuxt dev
```

## How it works (cross-platform, zero extra deps)

Jarvis uses small launcher scripts (in [`bootstrap/`](bootstrap/) and [`scripts/`](scripts/)) instead of shell-specific glue — no `concurrently`, no `cross-env`, no extra npm dependencies:

- [`bootstrap/install.ps1`](bootstrap/install.ps1) / [`bootstrap/install.sh`](bootstrap/install.sh) — optional bootstrap entrypoints that check Node.js and offer local runtime download before invoking `wake-up-jarvis`
- [`scripts/wake-up-jarvis.mjs`](scripts/wake-up-jarvis.mjs) — the immersive one-command entry point; runs preflight → install → build → serve in sequence with a themed banner and step-by-step status
- [`scripts/preflight.mjs`](scripts/preflight.mjs) — verifies Node, npm, and Python versions on your system before anything else runs
- [`scripts/install-backend.mjs`](scripts/install-backend.mjs) — prefers Python 3.12/3.13 probes first and can offer local Python download before creating the venv and installing requirements
- [`scripts/build-frontend.mjs`](scripts/build-frontend.mjs) — runs `nuxt build`
- [`scripts/serve-backend.mjs`](scripts/serve-backend.mjs) — runs uvicorn from the venv (`.venv/bin/python` on Unix, `.venv\Scripts\python.exe` on Windows)
- [`scripts/serve-frontend.mjs`](scripts/serve-frontend.mjs) — runs `node .output/server/index.mjs`
- [`scripts/serve.mjs`](scripts/serve.mjs) / [`scripts/dev.mjs`](scripts/dev.mjs) — run backend and frontend in parallel, forward `Ctrl+C` to both

Because everything goes through Node + `spawn`, there are no shell-isms (`&`, `wait`, backticks), no path-separator issues, and no assumptions about bash vs PowerShell vs cmd.

## Troubleshooting

### Any platform

- **"Node.js 20+ not found"** — run `bootstrap/install.ps1` (Windows) or `bootstrap/install.sh` (macOS/Linux) and accept local runtime download
- **"could not find Python 3.x on PATH"** — install Python and make sure `python3` (macOS/Linux) or `py` / `python` (Windows) runs in your terminal
- **Port 8000 or 3000 already in use** — another process is holding it; find and stop it (`lsof -i :8000` on macOS/Linux, `netstat -ano | findstr :8000` on Windows)
- **"backend venv is missing dependencies"** — a previous install was interrupted. Run `npm run install:backend` again (or delete `backend/.venv` and re-run `npm run wake-up-jarvis`)

### Windows-specific

- **Install looks stuck during "creating Python venv"** — this is almost always antivirus (Windows Defender, etc.) scanning every file pip writes. First install can take 30–90 seconds just for the venv, and another 2–5 minutes to download ~400 MB of ML wheels. **Do not press Ctrl+C** — give it time. If you did press Ctrl+C, the script will detect the broken venv on the next run and rebuild it cleanly.
- **If it's too slow**, add an exclusion in Windows Defender for the project folder (Settings → Virus & threat protection → Exclusions → Add a folder → select `backend\.venv` and `backend\.python-local`).
- **`.venv\Scripts\activate` : The term is not recognized** — you don't need to activate the venv manually. Just use `npm run wake-up-jarvis` (or `npm run serve` if already installed). If you really want to activate it in PowerShell, the command is `.\.venv\Scripts\Activate.ps1` — and PowerShell may require `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` first.
- **"cannot be loaded because running scripts is disabled on this system"** — PowerShell's default ExecutionPolicy blocks `.ps1` files. Either use the `powershell -ExecutionPolicy Bypass -File .\bootstrap\install.ps1` form from Quick start, or run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- **"`py` works but `python` doesn't"** — the `py` launcher is fine, the install script handles it automatically.
- **"could not remove backend/.venv"** — a previous Jarvis backend may still be running and holding files. Close any `python.exe` / `uvicorn` in Task Manager, then re-run.
- **Long-path errors** (`FileNotFoundError`, paths over 260 chars) — enable long paths: run PowerShell as Administrator and execute `New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force`, then reboot.

### macOS-specific

- **"xcrun: error: invalid active developer path"** — install the Command Line Tools: `xcode-select --install`. This is required for any package that builds from source.
- **`brew install python@3.14` installed, but it's too new** — many ML packages (fastembed, onnxruntime) don't yet ship wheels for 3.14. Install `python@3.12` or `python@3.13` instead, or let the install script download a local standalone Python.
- **Apple Silicon + old Python** — make sure your Python is arm64-native (`python3 -c "import platform; print(platform.machine())"` should print `arm64`). A Rosetta x86_64 Python will install slower and may pull in x86 wheels.

## Structure

- `backend/` — FastAPI + SQLite + Anthropic SDK
- `bootstrap/` — zero-prereq installers (download local Node runtime when needed)
- `frontend/` — Nuxt 3 + Vue 3 + TypeScript
- `scripts/` — cross-platform Node launchers used by npm scripts
- `docs/` — project documentation
- `CLAUDE.md` — full project plan
