// Route A: capture the live "Learn this stitch" scene to video.
//   python3 -m http.server 8765 &   (from the repo root)
//   node tools/capture_tutorials.mjs [keys...]      (default: all stitches)
// Writes assets/tutorials/<key>.webm, .mp4 and .jpg (poster at 80%).
// Needs playwright (NODE_PATH=/opt/node-tools/node_modules in the cloud container) and ffmpeg.
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync, statSync } from "node:fs";
import { join } from "node:path";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");   // resolved via NODE_PATH or a local install

const URL = process.env.URL || "http://localhost:8765/";
const FPS = 24, W = 960, H = 600;   // SwiftShader renders ~3 s/frame at this size; the modal shows ~600 CSS px
const KEYS = process.argv.slice(2).length ? process.argv.slice(2) : ["ch", "sl", "sc", "hdc", "dc", "tr", "inc", "dec", "mr"];
const OUT = "assets/tutorials";
const TMP = process.env.TMP_DIR || "/tmp/tutorial_frames";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
page.on("console", m => { if (m.type() === "error") console.log("[page]", m.text()); });
await page.goto(URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => typeof YarnTex !== "undefined" && YarnTex.ready === true, null, { timeout: 120000 });

for (const key of KEYS) {
  const dir = join(TMP, key); rmSync(dir, { recursive: true, force: true }); mkdirSync(dir, { recursive: true });
  const total = await page.evaluate(({ key, W, H }) => {
    if (typeof pause === "function") try { pause(); } catch (e) {}
    TUTORIAL_KEYS.clear();   // capture the live scene, not the videos it produces
    // more fibres and rounder tubes than the live view can afford
    learnMkMesh = function () {
      const m = yarnMesh(new THREE.LineCurve3(new THREE.Vector3(), new THREE.Vector3(0, 1, 0)), YR, false, 4, L3.yarnMat, { fibres: 9, radial: 14 });
      m.visible = false; L3.scene.add(m); L3.managed.push(m); return m;
    };
    openLearn(key); setLearnPlaying(false); cancelAnimationFrame(Learn.raf);
    L3.renderer.setPixelRatio(1); L3.renderer.setSize(W, H, false);
    L3.camera.aspect = W / H; L3.camera.updateProjectionMatrix();
    L3.controls.update();
    return learnTotal();
  }, { key, W, H });
  const n = Math.ceil((total + 1.0) * FPS);   // short hold on the finished stitch
  const t0 = Date.now();
  for (let i = 0; i < n; i += 15) {
    const batch = await page.evaluate(({ i, n, FPS }) => {
      const out = [];
      for (let j = i; j < Math.min(n, i + 15); j++) {
        Learn.t = j / FPS; animateLearn3D(); L3.renderer.render(L3.scene, L3.camera);
        out.push(L3.renderer.domElement.toDataURL("image/png"));
      }
      return out;
    }, { i, n, FPS });
    batch.forEach((d, k) => writeFileSync(join(dir, `f_${String(i + k).padStart(4, "0")}.png`), Buffer.from(d.split(",")[1], "base64")));
    process.stdout.write(`\r${key}: ${Math.min(n, i + 15)}/${n} frames (${((Date.now() - t0) / 1000).toFixed(0)} s)`);
  }
  process.stdout.write("\n");
  const inp = ["-y", "-loglevel", "error", "-framerate", String(FPS), "-i", join(dir, "f_%04d.png")];
  execFileSync("ffmpeg", [...inp, "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "36", "-row-mt", "1", "-pix_fmt", "yuv420p", "-an", join(OUT, `${key}.webm`)]);
  execFileSync("ffmpeg", [...inp, "-c:v", "libx264", "-crf", "24", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", join(OUT, `${key}.mp4`)]);
  const poster = String(Math.round(total * 0.8 * FPS)).padStart(4, "0");
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", join(dir, `f_${poster}.png`), "-q:v", "4", join(OUT, `${key}.jpg`)]);
  const kb = f => (statSync(join(OUT, f)).size / 1024).toFixed(0) + " KB";
  console.log(`${key}: webm ${kb(key + ".webm")}, mp4 ${kb(key + ".mp4")}, jpg ${kb(key + ".jpg")}`);
}
await browser.close();
