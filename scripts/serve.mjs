import { spawn } from 'node:child_process';

const isWin = process.platform === 'win32';

// On Windows, npm.cmd is a batch file that requires a shell. We pass the full
// command as a single string so cmd.exe doesn't split paths with spaces and
// Node doesn't fire DEP0190 ("args + shell: true" deprecation).
function spawnNpm(args, opts = {}) {
  if (isWin) {
    return spawn(['npm.cmd', ...args].join(' '), { ...opts, shell: true });
  }
  return spawn('npm', args, opts);
}

const procs = [
  { name: 'backend', color: '\x1b[36m', child: null },
  { name: 'frontend', color: '\x1b[35m', child: null },
];
const reset = '\x1b[0m';

procs[0].child = spawnNpm(['run', 'serve:backend'], { stdio: 'inherit' });
procs[1].child = spawnNpm(['run', 'serve:frontend'], { stdio: 'inherit' });

let shuttingDown = false;
function shutdown() {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const p of procs) {
    if (p.child && p.child.exitCode === null) {
      try {
        p.child.kill(isWin ? undefined : 'SIGINT');
      } catch {}
    }
  }
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

let exited = 0;
for (const p of procs) {
  p.child.on('exit', (code) => {
    console.log(`${p.color}[${p.name}]${reset} exited with code ${code}`);
    exited++;
    shutdown();
    if (exited === procs.length) process.exit(code ?? 0);
  });
  p.child.on('error', (err) => {
    console.error(`${p.color}[${p.name}]${reset} failed to start: ${err.message}`);
    shutdown();
    process.exit(1);
  });
}
