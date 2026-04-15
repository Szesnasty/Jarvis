import { spawnSync } from 'node:child_process';

const isWin = process.platform === 'win32';

console.log('[build-frontend] running nuxt build');
// On Windows, npm.cmd needs a shell. Pass as single string to avoid DEP0190.
const r = isWin
  ? spawnSync('npm.cmd --prefix frontend run build', { stdio: 'inherit', shell: true })
  : spawnSync('npm', ['--prefix', 'frontend', 'run', 'build'], { stdio: 'inherit' });
if (r.error) {
  console.error(`[build-frontend] failed: ${r.error.message}`);
  process.exit(1);
}
process.exit(r.status ?? 0);
