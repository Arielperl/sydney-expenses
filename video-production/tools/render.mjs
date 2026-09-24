#!/usr/bin/env node
// Captures tools/film.html frame-by-frame with headless Chrome (CDP over WebSocket)
// and encodes the frames with ffmpeg.
//
//   node tools/render.mjs --fmt 16x9 --cut main --out exports/main/x.mp4 [--audio a.wav] [--fps 24]
//   node tools/render.mjs --fmt 16x9 --cut main --stills 0.4,5,10 --stilldir assets/generated/storyboard --names F01,F02,F03
//
// Frames go to a temporary directory (outside the repo); only the encoded file is written to --out.
import { spawn, spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, v, i, a) => (v.startsWith('--') ? acc.concat([[v.slice(2), a[i + 1]?.startsWith('--') || a[i + 1] === undefined ? 'true' : a[i + 1]]]) : acc), []));
const fmt = args.fmt || '16x9';
const cut = args.cut || 'main';
const fps = Number(args.fps || 24);
const [W, H] = fmt === '9x16' ? [1080, 1920] : [1920, 1080];
const here = dirname(fileURLToPath(import.meta.url));
const film = pathToFileURL(join(here, 'film.html')).href + `?fmt=${fmt}&cut=${cut}&chip=${args.chip ?? '1'}`;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = 9300 + Math.floor(Math.random() * 500);
const tmpRoot = process.env.RENDER_TMP || tmpdir();
const prof = mkdtempSync(join(tmpRoot, 'sydney-chrome-'));
const frameDir = mkdtempSync(join(tmpRoot, 'sydney-frames-'));

const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, '--hide-scrollbars',
  '--allow-file-access-from-files', '--disable-gpu-vsync', '--force-color-profile=srgb', `--window-size=${W},${H}`, 'about:blank',
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));
async function json(path, method = 'GET') { for (let i = 0; i < 60; i++) { try { const r = await fetch(`http://127.0.0.1:${port}${path}`, { method }); if (r.ok) return r.json(); } catch {} await sleep(250); } throw new Error('Chrome did not start'); }

let ws, seq = 0; const pending = new Map();
function send(method, params = {}) { const id = ++seq; ws.send(JSON.stringify({ id, method, params })); return new Promise((res, rej) => pending.set(id, { res, rej })); }
async function evalJS(expression) { const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails)); return r.result.value; }

try {
  const target = await json('/json/new?about:blank', 'PUT');
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { const p = pending.get(d.id); pending.delete(d.id); d.error ? p.rej(new Error(d.error.message)) : p.res(d.result); } };
  await send('Page.enable'); await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: film });
  for (let i = 0; i < 240; i++) { if (await evalJS('window.__ready === true').catch(() => false)) break; await sleep(250); }
  const fontsOK = await evalJS('window.__fontsOK');
  const dur = await evalJS('window.__dur');
  console.log(`film ready: ${fmt} ${cut} ${dur}s, IBM Plex Sans Hebrew loaded: ${fontsOK}`);

  async function shoot(t, file, type = 'jpeg') {
    await evalJS(`window.renderFrame(${t}); new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`);
    const r = await send('Page.captureScreenshot', { format: type, quality: type === 'jpeg' ? 94 : undefined, clip: { x: 0, y: 0, width: W, height: H, scale: 1 }, captureBeyondViewport: false });
    writeFileSync(file, Buffer.from(r.data, 'base64'));
  }

  if (args.stills) {
    const times = args.stills.split(',').map(Number); const names = (args.names || '').split(',');
    const dir = resolve(args.stilldir || '.'); mkdirSync(dir, { recursive: true });
    for (let i = 0; i < times.length; i++) { const f = join(dir, `${names[i] || 'still-' + times[i]}.png`); await shoot(times[i], f, 'png'); console.log('still', f); }
  } else {
    // --mb N: N sub-frames per frame spread over a 180-degree shutter, averaged by ffmpeg (motion blur)
    const mb = Math.max(1, Number(args.mb || 1));
    const n = Math.round(dur * fps);
    const t0 = Date.now();
    for (let i = 0; i < n; i++) {
      for (let k = 0; k < mb; k++) {
        const t = i / fps + (mb > 1 ? (k / mb - 0.25) * (0.5 / fps) : 0) + 1e-4;
        await shoot(Math.max(0, t), join(frameDir, String(i * mb + k).padStart(6, '0') + '.jpg'));
      }
      if (i % 120 === 0) console.log(`frame ${i}/${n} (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
    }
    const out = resolve(args.out); mkdirSync(dirname(out), { recursive: true });
    const ff = ['-y', '-hide_banner', '-loglevel', 'error', '-framerate', String(fps * mb), '-i', join(frameDir, '%06d.jpg')];
    if (args.audio) ff.push('-i', resolve(args.audio));
    if (mb > 1) ff.push('-vf', `tmix=frames=${mb},select='eq(mod(n\\,${mb})\\,${mb - 1})',setpts=N/${fps}/TB`, '-r', String(fps));
    ff.push('-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
      '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-movflags', '+faststart');
    if (args.audio) ff.push('-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-shortest');
    ff.push(out);
    const r = spawnSync('ffmpeg', ff, { stdio: 'inherit' });
    if (r.status !== 0) throw new Error('ffmpeg failed');
    console.log('wrote', out);
  }
} finally {
  try { ws?.close(); } catch {}
  chrome.kill('SIGKILL');
  await sleep(300);
  rmSync(prof, { recursive: true, force: true });
  rmSync(frameDir, { recursive: true, force: true });
}
