// Render summary/summary_<date>.html (from render_summary.py) to a 1080x1350 PNG.
// Usage: node scripts/summary_png.js summary/summary_20261127.html [out.png]
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const src = path.resolve(process.argv[2]);
  const out = process.argv[3] || src.replace(/\.html$/, '.png');
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: 1 });
  await p.goto('file://' + src);
  await p.waitForTimeout(300);
  await p.screenshot({ path: out });
  await b.close();
  console.log(out);
})();
