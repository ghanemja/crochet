// Route A: capture the live "Learn this stitch" scene frame by frame and encode
// assets/tutorials/<key>.{webm,mp4,jpg}.
//   python3 -m http.server 8765 &      (from the repo root)
//   node tools/capture_tutorials.mjs [keys...]
// Needs Playwright (Chromium) and ffmpeg on PATH.
import { createRequire } from "module";
import { mkdirSync, writeFileSync, rmSync, statSync } from "fs";
import { execFileSync } from "child_process";
import { join } from "path";
import { tmpdir } from "os";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const URL = process.env.URL || "http://localhost:8765/";
const FPS = 30, W = 1280, H = 800, BATCH = 15;
const KEYS = process.argv.slice(2).length ? process.argv.slice(2) : ["ch","sl","sc","hdc","dc","tr","inc","dec","mr"];
const OUT = "assets/tutorials";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
page.on("pageerror", e => console.error("pageerror:", e.message));
await page.goto(URL + "?capture=1", { waitUntil: "domcontentloaded", timeout: 120000 });
await page.waitForFunction(() => typeof YarnTex !== "undefined" && YarnTex.ready === true, null, { timeout: 60000 });
await page.evaluate(() => { try { pause(); } catch (e) {} });

for (const key of KEYS) {
  const dir = join(tmpdir(), "tut_" + key); rmSync(dir, { recursive: true, force: true }); mkdirSync(dir, { recursive: true });
  const total = await page.evaluate(([key, W, H]) => {
    Learn.noVideo = true; openLearn(key); setLearnPlaying(false); cancelAnimationFrame(Learn.raf);
    // denser strands than the interactive default
    window.learnMkMesh = function () { const m = yarnMesh(new THREE.LineCurve3(new THREE.Vector3(), new THREE.Vector3(0, 1, 0)), YR, false, 4, L3.yarnMat, { fibres: 9, radial: 14 });
      m.visible = false; L3.scene.add(m); L3.managed.push(m); return m; };
    buildLearnScene(key);
    L3.renderer.setPixelRatio(1); L3.renderer.setSize(W, H, false);
    L3.camera.aspect = W / H; L3.camera.updateProjectionMatrix();
    return learnTotal();
  }, [key, W, H]);
  const n = Math.round(total * FPS) + 1;
  console.log(`${key}: ${total}s, ${n} frames`); const t0 = Date.now();
  for (let i = 0; i < n; i += BATCH) {
    const shots = await page.evaluate(([i0, i1, FPS]) => {
      const out = [];
      for (let i = i0; i < i1; i++) { Learn.t = i / FPS; animateLearn3D(); L3.controls.update();
        L3.renderer.render(L3.scene, L3.camera); out.push(L3.renderer.domElement.toDataURL("image/png")); }
      return out;
    }, [i, Math.min(n, i + BATCH), FPS]);
    shots.forEach((d, k) => writeFileSync(join(dir, `f_${String(i + k).padStart(4, "0")}.png`), Buffer.from(d.split(",")[1], "base64")));
  }
  console.log(`  ${((Date.now() - t0) / n / 1000).toFixed(2)} s/frame`);
  encode(dir, key, n);
}
await browser.close();

export function encode(dir, key, n) {
  const inp = ["-y", "-loglevel", "error", "-framerate", String(FPS), "-i", join(dir, "f_%04d.png")];
  // two-pass VP9 aimed at ~1.35 MB whatever the length (fibre detail compresses poorly at fixed CRF)
  const kbps = Math.min(1500, Math.floor(1.35e6 * 8 / 1000 / (n / FPS)));
  const vp9 = ["-c:v", "libvpx-vp9", "-b:v", kbps + "k", "-row-mt", "1", "-pix_fmt", "yuv420p", "-passlogfile", join(dir, "vp9")];
  execFileSync("ffmpeg", [...inp, ...vp9, "-pass", "1", "-an", "-f", "null", "/dev/null"]);
  execFileSync("ffmpeg", [...inp, ...vp9, "-pass", "2", join(OUT, key + ".webm")]);
  console.log(`  webm ${kbps} kb/s: ${(statSync(join(OUT, key + ".webm")).size / 1e6).toFixed(2)} MB`);
  execFileSync("ffmpeg", [...inp, "-c:v", "libx264", "-crf", "23", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", join(OUT, key + ".mp4")]);
  const poster = Math.min(n - 1, Math.round(n * 0.8));
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", join(dir, `f_${String(poster).padStart(4, "0")}.png`), "-q:v", "4", join(OUT, key + ".jpg")]);
  console.log(`  mp4 ${(statSync(join(OUT, key + ".mp4")).size / 1e6).toFixed(2)} MB`);
}
