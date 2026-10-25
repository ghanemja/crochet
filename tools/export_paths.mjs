// Route B step 1: dump the Learn scene's strand paths, hook pose and camera per
// frame (exportLearnPaths in index.html) to build/paths/<key>.json.
//   python3 -m http.server 8765 &   then   node tools/export_paths.mjs [keys...]
import { createRequire } from "module";
import { mkdirSync, writeFileSync } from "fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const URL = process.env.URL || "http://localhost:8765/";
const KEYS = process.argv.slice(2).length ? process.argv.slice(2) : ["ch","sl","sc","hdc","dc","tr","inc","dec","mr"];
mkdirSync("build/paths", { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
page.on("pageerror", e => console.error("pageerror:", e.message));
await page.goto(URL + "?export=" + Date.now(), { waitUntil: "domcontentloaded", timeout: 120000 });
await page.waitForFunction(() => typeof YarnTex !== "undefined" && YarnTex.ready === true, null, { timeout: 60000 });
await page.evaluate(() => { try { pause(); } catch (e) {} });
for (const key of KEYS) {
  const json = await page.evaluate(k => JSON.stringify(exportLearnPaths(k, 30)), key);
  writeFileSync(`build/paths/${key}.json`, json);
  console.log(key, (json.length / 1e6).toFixed(1) + " MB");
}
await browser.close();
