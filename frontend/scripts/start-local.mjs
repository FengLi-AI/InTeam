import { cp, access } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const standalone = path.join(root, '.next', 'standalone');
try { await access(path.join(standalone, 'server.js')); }
catch { console.error('请先执行 npm run build。'); process.exit(1); }
const copyOptions = { recursive: true, force: true, filter: (source) => !path.basename(source).startsWith('._') };
await cp(path.join(root, 'public'), path.join(standalone, 'public'), copyOptions);
await cp(path.join(root, '.next', 'static'), path.join(standalone, '.next', 'static'), copyOptions);
const child = spawn(process.execPath, [path.join(standalone, 'server.js')], {
  cwd: standalone, stdio: 'inherit', env: { ...process.env, HOSTNAME: '127.0.0.1', PORT: process.env.PORT || '3000' },
});
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
child.on('exit', (code) => process.exit(code ?? 0));
