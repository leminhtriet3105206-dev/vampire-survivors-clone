'use strict';

// `npm run check` - syntax-checks every backend and frontend JS file without running it.
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const roots = [path.resolve(__dirname, '../src'), path.resolve(__dirname, '../../frontend/js')];

function collect(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) collect(full, out);
    else if (entry.name.endsWith('.js')) out.push(full);
  }
  return out;
}

let failed = 0;
for (const file of roots.flatMap((r) => collect(r))) {
  try {
    const args = file.includes(`${path.sep}frontend${path.sep}`)
      ? ['--input-type=module', '--check']
      : ['--check', file];
    if (args[0] === '--input-type=module') {
      execFileSync(process.execPath, args, { input: fs.readFileSync(file), stdio: ['pipe', 'pipe', 'pipe'] });
    } else {
      execFileSync(process.execPath, args, { stdio: 'pipe' });
    }
    console.log(`ok   ${path.relative(process.cwd(), file)}`);
  } catch (err) {
    failed += 1;
    console.error(`FAIL ${path.relative(process.cwd(), file)}\n${err.stderr?.toString() || err.message}`);
  }
}
process.exit(failed ? 1 : 0);

