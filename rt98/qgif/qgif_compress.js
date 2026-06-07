// qgif_compress.js - run EPOMAKER/RDMCTMZT's qgif WASM compressor under Node.
//
// Usage:  node qgif_compress.js <framesDir> <fps> <outPath>
//   framesDir : directory containing input_0.png, input_1.png, ... (target-sized,
//               width & height divisible by 4 - e.g. 240x136)
//   fps       : playback frames-per-second (integer >= 1)
//   outPath   : where to write the resulting .qgif binary
//
// This loads the vendor's qgif.js (Emscripten module) + qgif.wasm and calls the
// exported `compress_video_wasm(inputPattern, output, 0, fps)` exactly as the
// official RT98 web tool's compress worker does. We do not reimplement the codec.
const fs = require('fs');
const path = require('path');
const createModule = require('./qgif.js');

const [, , framesDir, fpsArg, outPath] = process.argv;
if (!framesDir || !outPath) {
  console.error('usage: node qgif_compress.js <framesDir> <fps> <outPath>');
  process.exit(2);
}

(async () => {
  const mod = await createModule({
    locateFile: (p) => (p.endsWith('.wasm') ? path.join(__dirname, 'qgif.wasm') : p),
  });
  if (!mod.FS || !mod.cwrap) throw new Error('qgif module not ready (no FS/cwrap)');

  const files = fs.readdirSync(framesDir)
    .filter((f) => /^input_\d+\.png$/.test(f))
    .sort((a, b) => parseInt(a.match(/\d+/)[0], 10) - parseInt(b.match(/\d+/)[0], 10));
  if (files.length === 0) throw new Error('no input_*.png frames in ' + framesDir);

  files.forEach((f, i) => {
    mod.FS.writeFile('/input_' + i + '.png', new Uint8Array(fs.readFileSync(path.join(framesDir, f))));
  });

  const compress = mod.cwrap('compress_video_wasm', 'number', ['string', 'string', 'number', 'number']);
  const fps = Math.max(1, Math.floor(Number(fpsArg) || 10));

  let out = null;
  for (const [inPat, outName] of [['input_X.png', 'output.qgif'], ['/input_X.png', '/output.qgif']]) {
    try {
      compress(inPat, outName, 0, fps);
      const data = mod.FS.readFile('/' + outName.replace(/^\/+/, ''));
      if (data && data.length) { out = data; break; }
    } catch (e) { /* try next path form */ }
  }
  if (!out) throw new Error('compress_video_wasm produced no output');

  fs.writeFileSync(outPath, Buffer.from(out.buffer, out.byteOffset, out.byteLength));
  console.error(`qgif: ${files.length} frames @ ${fps}fps -> ${out.length} bytes -> ${outPath}`);
})().catch((e) => { console.error('ERR', e && e.message ? e.message : e); process.exit(1); });
