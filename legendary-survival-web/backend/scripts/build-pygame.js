'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

console.log('=== Building Pygame WebAssembly (Pygbag) ===');

const projectRoot = path.resolve(__dirname, '../../../');
const mainPy = path.join(projectRoot, 'main.py');
const audioSettingsPy = path.join(projectRoot, 'audio_settings.py');
const stageDir = path.join(projectRoot, 'build_pygame_stage');
const targetDir = path.resolve(__dirname, '../../frontend/pygame');

if (!fs.existsSync(mainPy)) {
  console.error('[ERROR] Could not find main.py at:', mainPy);
  process.exit(1);
}

// 1. Stage clean python files
console.log('1. Staging Python source files...');
if (fs.existsSync(stageDir)) {
  fs.rmSync(stageDir, { recursive: true, force: true });
}
fs.mkdirSync(stageDir, { recursive: true });
fs.copyFileSync(mainPy, path.join(stageDir, 'main.py'));
if (fs.existsSync(audioSettingsPy)) {
  fs.copyFileSync(audioSettingsPy, path.join(stageDir, 'audio_settings.py'));
}

// 2. Run pygbag --build
console.log('2. Running pygbag --build...');
const isWindows = process.platform === 'win32';
const pyCmd = isWindows ? 'python' : 'python3';

const res = spawnSync(pyCmd, ['-m', 'pygbag', '--build', '--app_name', 'pygame', '--ume_block', '0', stageDir], {
  stdio: 'inherit',
  shell: true,
});

if (res.status !== 0) {
  console.error('[ERROR] pygbag failed with exit code:', res.status);
  fs.rmSync(stageDir, { recursive: true, force: true });
  process.exit(res.status || 1);
}

// 3. Copy build/web to frontend/pygame
console.log('3. Copying WebAssembly artifacts to frontend/pygame...');
const webDir = path.join(stageDir, 'build', 'web');
if (!fs.existsSync(webDir)) {
  console.error('[ERROR] Expected build/web directory not found at:', webDir);
  fs.rmSync(stageDir, { recursive: true, force: true });
  process.exit(1);
}

fs.mkdirSync(targetDir, { recursive: true });
const files = fs.readdirSync(webDir);
for (const file of files) {
  const src = path.join(webDir, file);
  const dst = path.join(targetDir, file);
  if (fs.statSync(src).isFile()) {
    fs.copyFileSync(src, dst);
    console.log(`   ✓ Copied: ${file}`);
  }
}

// 4. Post-process index.html to ensure UME (User Media Engagement) block is completely bypassed
const targetIndexHtml = path.join(targetDir, 'index.html');
if (fs.existsSync(targetIndexHtml)) {
  console.log('4. Patching index.html for zero-click WebAssembly execution & auto audio unlock...');
  let html = fs.readFileSync(targetIndexHtml, 'utf8');

  // Bypass blocking while loop if ume_block is 0
  html = html.replace('if not platform.window.MM.UME:', 'if int(platform.window.config.ume_block) and not platform.window.MM.UME:');
  html = html.replace(/ume_block\s*:\s*1\s*,/g, 'ume_block : 0,');

  // Inject auto-unlock script if not already present
  if (!html.includes('function unlockMedia()')) {
    const unlockSnippet = `
function unlockMedia() {
    try {
        if (window.MM) window.MM.UME = true;
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (AudioContextClass) {
            if (!window._sharedAudioCtx) window._sharedAudioCtx = new AudioContextClass();
            if (window._sharedAudioCtx.state === 'suspended') window._sharedAudioCtx.resume();
        }
    } catch (_) {}
    const canvas = document.getElementById('canvas');
    if (canvas) { try { canvas.focus(); } catch (_) {} }
}
window.addEventListener('pointerdown', unlockMedia, { passive: true });
window.addEventListener('click', unlockMedia, { passive: true });
window.addEventListener('keydown', unlockMedia, { passive: true });
window.addEventListener('focus', unlockMedia, { passive: true });
window.addEventListener('message', (event) => {
    if (event.data && (event.data.type === 'FOCUS' || event.data.type === 'UNLOCK_MEDIA')) unlockMedia();
});
try { if (window.MM) window.MM.UME = true; unlockMedia(); } catch (_) {}
`;
    html = html.replace(/config\s*=\s*\{[\s\S]*?\}/, (match) => match + '\n' + unlockSnippet);
  }

  fs.writeFileSync(targetIndexHtml, html, 'utf8');
  console.log('   ✓ index.html successfully patched with auto-unlock and UME bypass.');
}

// 5. Cleanup
fs.rmSync(stageDir, { recursive: true, force: true });
console.log('=== Pygame WebAssembly Build Complete & Ready at /pygame/index.html ===');

