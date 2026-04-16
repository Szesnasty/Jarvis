import { spawnSync } from 'node:child_process';

const isWin = process.platform === 'win32';

// On Windows, npm.cmd is a batch file that requires a shell. We pass the full
// command as a single string so cmd.exe doesn't split paths with spaces and
// Node doesn't fire DEP0190 ("args + shell: true" deprecation).
function npmRunSync(args, opts = {}) {
  if (isWin) {
    return spawnSync(['npm.cmd', ...args].join(' '), { ...opts, shell: true });
  }
  return spawnSync('npm', args, opts);
}

const CYAN = '\x1b[36m';
const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const MAGENTA = '\x1b[35m';
const BOLD = '\x1b[1m';
const DIM = '\x1b[2m';
const RESET = '\x1b[0m';

const banner = `
${CYAN}     _                  _     ${RESET}
${CYAN}    | | __ _ _ ____   _(_)___ ${RESET}
${CYAN} _  | |/ _\` | '__\\ \\ / / / __|${RESET}
${CYAN}| |_| | (_| | |   \\ V /| \\__ \\${RESET}
${CYAN} \\___/ \\__,_|_|    \\_/ |_|___/${RESET}

${DIM}  YAn AI workspace that remembers what matters${RESET}
`;

const steps = [
  {
    label: 'Running system check',
    detail: 'verifying Node, npm, Python versions',
    args: ['run', 'preflight'],
  },
  {
    label: 'Waking up the backend',
    detail: 'creating Python venv + installing dependencies',
    args: ['run', 'install:backend'],
  },
  {
    label: 'Waking up the frontend',
    detail: 'installing Node dependencies',
    args: ['run', 'install:frontend'],
  },
  {
    label: 'Building the interface',
    detail: 'compiling the production Nuxt bundle',
    args: ['run', 'build'],
  },
];

function step(n, total, s) {
  console.log();
  console.log(`${MAGENTA}${BOLD}[${n}/${total}] ${s.label}${RESET}  ${DIM}${s.detail}${RESET}`);
  console.log(`${DIM}${'─'.repeat(60)}${RESET}`);
  const r = npmRunSync(s.args, { stdio: 'inherit' });
  if (r.error) {
    console.error(`\n${YELLOW}!${RESET} ${s.label} failed: ${r.error.message}`);
    process.exit(1);
  }
  if (r.status !== 0) {
    console.error(`\n${YELLOW}!${RESET} ${s.label} exited with code ${r.status}`);
    process.exit(r.status ?? 1);
  }
}

console.log(banner);
console.log(`${BOLD}Waking up Jarvis…${RESET}`);

const total = steps.length + 1;
steps.forEach((s, i) => step(i + 1, total, s));

const arcReactor = `
${CYAN}              .-"""""-.${RESET}
${CYAN}           .'${RESET}  ${BOLD}${CYAN}_____${RESET}  ${CYAN}'.${RESET}
${CYAN}          /${RESET}  ${CYAN}.'${RESET}     ${CYAN}'.${RESET}  ${CYAN}\\${RESET}
${CYAN}         |${RESET}  ${CYAN}/${RESET}   ${BOLD}${CYAN}◉${RESET}   ${CYAN}\\${RESET}  ${CYAN}|${RESET}
${CYAN}         |${RESET}  ${CYAN}\\${RESET}  ${BOLD}${CYAN}─┼─${RESET}  ${CYAN}/${RESET}  ${CYAN}|${RESET}
${CYAN}          \\${RESET}  ${CYAN}'._____.'${RESET}  ${CYAN}/${RESET}
${CYAN}           '.${RESET}         ${CYAN}.'${RESET}
${CYAN}             '-.....-'${RESET}
`;

console.log(arcReactor);
console.log(
  `${MAGENTA}${BOLD}[${total}/${total}] Starting servers${RESET}  ${DIM}backend :8000  •  frontend :3000${RESET}`,
);
console.log(`${DIM}${'─'.repeat(60)}${RESET}`);
console.log(
  `${GREEN}${BOLD}Jarvis is waking up.${RESET} ${DIM}Open ${RESET}${BOLD}http://localhost:3000${RESET}${DIM} once both servers are ready.${RESET}`,
);
console.log(`${DIM}Press Ctrl+C to put Jarvis back to sleep.${RESET}`);
console.log();

const serve = npmRunSync(['run', 'serve'], { stdio: 'inherit' });
process.exit(serve.status ?? 0);
