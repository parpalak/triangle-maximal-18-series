#!/usr/bin/env node
//
// Reads gallery/*.lines.csv, generates docs/gallery/index.html.
// SVG rendering happens client-side using the viewer's computational modules
// (parser.js, cells.js) loaded via <script> tags. The generated HTML contains
// only line coefficients as JSON — polygon geometry is computed in the browser.
//
// Usage: node gallery/generate.js

"use strict";

const fs = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// Minimal App shim — replaces window.App for Node.js
// ---------------------------------------------------------------------------
const App = {};
App.EPS = 1e-9;
App.state = {
  lines: [],
  intersections: [],
  bbox: null,
  cells: [],
  geoMatrix: [1, 0, 0, 1, 0, 0],
  flags: {
    checkerMode: true,
    coloredMode: false,
    highlightDefects: true,
    showOuter: false,
    showPoints: false,
    showLineNumbers: false,
  },
  _invertColor: false,
};

// Load viewer modules by evaluating them with our App shim
const viewerDir = path.join(__dirname, "..", "docs", "viewer", "js");
function loadModule(filename) {
  const code = fs.readFileSync(path.join(viewerDir, filename), "utf-8");
  const wrapped = code
    .replace(/const App = \(window\.App = window\.App \|\| \{\}\);/, "")
    .replace(/const App = window\.App;/g, "")
    .replace(/window\.__lvColorDebug/g, "null");
  const fn = new Function(
    "App",
    "document",
    "window",
    wrapped
      .replace(/^\(function\s*\(\)\s*\{/, "")
      .replace(/\}\)\(\);?\s*$/, "")
  );
  const stubEl = {
    clientWidth: 800,
    clientHeight: 600,
    getBoundingClientRect: () => ({ width: 800, height: 600 }),
  };
  const stubDocument = {
    getElementById: () => stubEl,
    createElementNS: () => ({ setAttribute() {}, appendChild() {} }),
    createElement: () => ({ appendChild() {} }),
  };
  fn(App, stubDocument, { App });
}

loadModule("state.js");
loadModule("parser.js");
loadModule("cells.js");

// ---------------------------------------------------------------------------
// Parse a .lines.csv file
// ---------------------------------------------------------------------------
function parseLinesFile(filepath) {
  const text = fs.readFileSync(filepath, "utf-8");
  return App.parseInput(text);
}

// ---------------------------------------------------------------------------
// Compute cell data for a set of lines
// ---------------------------------------------------------------------------
function computeCells(lines) {
  const intersections = App.computeIntersections(lines);
  const bbox = App.buildBBox(lines, intersections);
  const pad = Math.max(bbox.maxX - bbox.minX, bbox.maxY - bbox.minY) * 0.5;
  const basePoly = [
    { x: bbox.minX - pad, y: bbox.minY - pad },
    { x: bbox.maxX + pad, y: bbox.minY - pad },
    { x: bbox.maxX + pad, y: bbox.maxY + pad },
    { x: bbox.minX - pad, y: bbox.maxY + pad },
  ];
  const cells = App.buildCells(lines, basePoly);
  return { cells, intersections, bbox };
}

// ---------------------------------------------------------------------------
// Count triangles (internal only)
// ---------------------------------------------------------------------------
function countTriangles(cells) {
  let count = 0;
  for (const c of cells) {
    if (!c.external && c.sideCount === 3) count++;
  }
  return count;
}

// ---------------------------------------------------------------------------
// Upper bound
// ---------------------------------------------------------------------------
function upperBound(n) {
  if (n % 2 === 0) return { value: Math.floor(n * (3 * n - 7) / 9), formula: "\u230an(3n\u22127)/9\u230b" };
  if (n % 6 === 1) return { value: (n * (n - 2) - 2) / 3, formula: "(n(n\u22122)\u22122)/3" };
  return { value: n * (n - 2) / 3, formula: "n(n\u22122)/3" };
}

// ---------------------------------------------------------------------------
// Generate gallery HTML
// ---------------------------------------------------------------------------
function generateGalleryHTML(entries) {
  // Build JSON data — only line coefficients
  const galleryData = entries.map(e => ({
    lines: e.lines.map(l => [l.m, l.b]),
  }));

  const items = entries.map((e, i) => {
    const linesText = e.lines.map((l, j) => `${j}: y = ${l.m} * x + ${l.b}`).join("\n");
    const csvText = "m,b\\n" + e.lines.map(l => `${l.m},${l.b}`).join("\\n");

    return `
    <div class="entry">
      <div class="entry-header">
        <h2>${e.title}</h2>
        <p class="description">${e.description}</p>
      </div>
      <div class="entry-body">
        <div class="image" data-entry="${i}"></div>
        <div class="info">
          <p class="stats">${e.n} lines<br>${e.triangles} triangles (upper bound <span class="upper-bound" title="${e.upperBound.formula}">${e.upperBound.value}</span>)</p>
          <div class="equations">
            <pre class="coefficients">${linesText}</pre>
            <button class="copy-btn" onclick="navigator.clipboard.writeText('${csvText.replace(/'/g, "\\'")}')">Copy line coefficients m, b as CSV</button>
          </div>
          <details class="equations-mobile">
            <summary>Line equations</summary>
            <pre class="coefficients">${linesText}</pre>
            <button class="copy-btn" onclick="navigator.clipboard.writeText('${csvText.replace(/'/g, "\\'")}')">Copy line coefficients m, b as CSV</button>
          </details>
        </div>
      </div>
    </div>`;
  });

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Triangle-maximal straight-line arrangements</title>
  <style>
    :root { --ink: #1a1a1a; --muted: #888; --light: #f0f0f0; }
    * { box-sizing: border-box; }
    body {
      font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
      background: #f0f0f0; color: var(--ink);
      margin: 0; padding: 32px 40px;
    }
    h1 { font-size: 1.3em; font-weight: 600; margin: 0 0 4px; }
    .hint { color: var(--muted); font-size: 0.8em; margin: 0 0 32px; }
    .entry {
      margin-bottom: 48px;
    }
    .entry-header {
      margin-bottom: 12px;
    }
    .entry-header h2 { font-size: 1.05em; font-weight: 600; margin: 0 0 6px; }
    .description { font-size: 0.9em; color: var(--muted); margin: 0; line-height: 1.45; }
    .stats { font-size: 0.9em; margin: 0 0 12px; }
    .upper-bound { text-decoration: underline dotted; cursor: help; }
    .entry-body {
      display: grid;
      grid-template-columns: 1fr 280px;
      grid-template-rows: 600px;
      gap: 0;
    }
    .image {
      overflow: hidden; cursor: grab;
      touch-action: none; user-select: none; -webkit-user-select: none;
      height: 600px;
      display: flex; align-items: center; justify-content: center;
      background: #fff;
    }
    .image:active { cursor: grabbing; }
    .image svg { display: block; width: 100%; height: 100%; }
    .image svg polygon { fill: #000; }
    .image svg polygon.defect { fill: #f00; }
    .image svg line { stroke: #000; stroke-width: 1; vector-effect: non-scaling-stroke; }
    .info {
      padding: 0 0 0 24px;
      display: flex;
      flex-direction: column;
      min-height: 0;
      overflow: hidden;
    }
    .equations-heading { color: var(--muted); font-size: 0.85em; margin-bottom: 6px; flex-shrink: 0; }
    .equations-mobile { display: none; font-size: 0.85em; }
    .equations-mobile summary {
      cursor: pointer;
      color: var(--muted);
      font-size: 0.85em;
      margin-bottom: 6px;
    }
    .coefficients {
      background: #fff;
      border-radius: 6px;
      padding: 8px 10px;
      font-family: "IBM Plex Mono", monospace;
      font-size: 11px;
      line-height: 1.4;
      overflow-x: auto;
      overflow-y: auto;
      white-space: pre;
      margin: 0 0 8px;
      flex: 1;
      min-height: 0;
    }
    .equations {
      font-size: 0.85em;
      flex: 1; min-height: 0;
      display: flex; flex-direction: column;
    }
    .copy-btn {
      border: 1px solid #ccc;
      background: #fff;
      border-radius: 6px;
      padding: 4px 10px;
      font-size: 11px;
      cursor: pointer;
      flex-shrink: 0;
    }
    .copy-btn:hover { background: #f0f0f0; }
    footer { color: #888; font-size: 0.85em; }
    @media (max-width: 700px) {
      body { padding: 16px; }
      .entry-body { grid-template-columns: 1fr; }
      .info { padding: 12px 0 0; }
      .equations { display: none; }
      .equations-mobile { display: block; }
    }
  </style>
</head>
<body>
  <h1>Triangle-maximal straight-line arrangements</h1>
  <p class="hint">Drag to pan, Ctrl+scroll to zoom, double-click to reset.</p>
${items.join("\n")}
<script>var GALLERY_DATA = ${JSON.stringify(galleryData)};</script>
<script src="../viewer/js/state.js"></script>
<script src="../viewer/js/parser.js"></script>
<script src="../viewer/js/cells.js"></script>
<script>
(function(){
  var SVG_NS = "http://www.w3.org/2000/svg";
  var SVG_SIZE = 600;

  function buildCells(lines) {
    var intersections = App.computeIntersections(lines);
    var bbox = App.buildBBox(lines, intersections);
    var pad = Math.max(bbox.maxX - bbox.minX, bbox.maxY - bbox.minY) * 0.5;
    var basePoly = [
      { x: bbox.minX - pad, y: bbox.minY - pad },
      { x: bbox.maxX + pad, y: bbox.minY - pad },
      { x: bbox.maxX + pad, y: bbox.maxY + pad },
      { x: bbox.minX - pad, y: bbox.maxY + pad }
    ];
    return { cells: App.buildCells(lines, basePoly), bbox: bbox };
  }

  function chooseInvertColor(cells) {
    var c0 = 0, c1 = 0;
    for (var i = 0; i < cells.length; i++) {
      if (cells[i].external) continue;
      if (cells[i].parity === 0) c0++; else c1++;
    }
    return c0 > c1;
  }

  function isBlack(cell, inv) { return inv ? cell.parity === 0 : cell.parity === 1; }

  // Render one gallery entry into its container
  function renderEntry(entryData, container) {
    var lines = entryData.lines.map(function(mb) { return { m: mb[0], b: mb[1] }; });
    var result = buildCells(lines);
    var cells = result.cells, bbox = result.bbox;
    var invertColor = chooseInvertColor(cells);

    var bw = bbox.maxX - bbox.minX, bh = bbox.maxY - bbox.minY;
    var padding = 0.06;
    var scaleX = SVG_SIZE * (1 - 2 * padding) / bw;
    var scaleY = SVG_SIZE * (1 - 2 * padding) / bh;
    var cxWorld = (bbox.minX + bbox.maxX) / 2;
    var cyWorld = (bbox.minY + bbox.maxY) / 2;
    var txBase = SVG_SIZE / 2 - cxWorld * scaleX;
    var tyBase = SVG_SIZE / 2 + cyWorld * scaleY;
    function wx(x) { return txBase + x * scaleX; }
    function wy(y) { return tyBase - y * scaleY; }

    var clipMargin = 0.02;
    var clipPoly = [
      { x: bbox.minX - bw * clipMargin, y: bbox.minY - bh * clipMargin },
      { x: bbox.maxX + bw * clipMargin, y: bbox.minY - bh * clipMargin },
      { x: bbox.maxX + bw * clipMargin, y: bbox.maxY + bh * clipMargin },
      { x: bbox.minX - bw * clipMargin, y: bbox.maxY + bh * clipMargin }
    ];

    var lineEps = Math.max(bw, bh) * 1e-6;
    function isArrangementEdge(p1, p2) {
      for (var k = 0; k < lines.length; k++) {
        var ln = lines[k];
        var d1 = Math.abs(p1.y - ln.m * p1.x - ln.b) / Math.sqrt(1 + ln.m * ln.m);
        var d2 = Math.abs(p2.y - ln.m * p2.x - ln.b) / Math.sqrt(1 + ln.m * ln.m);
        if (d1 < lineEps && d2 < lineEps) return true;
      }
      return false;
    }

    // Create SVG
    var svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("viewBox", "0 0 " + SVG_SIZE + " " + SVG_SIZE);
    var bg = document.createElementNS(SVG_NS, "rect");
    bg.setAttribute("width", SVG_SIZE);
    bg.setAttribute("height", SVG_SIZE);
    bg.setAttribute("fill", "#ffffff");
    svg.appendChild(bg);

    // Collect elements with SVG-space coords for pan/zoom
    var pzItems = [];
    function storePolygon(el, worldPoly) {
      var coords = [];
      for (var j = 0; j < worldPoly.length; j++) {
        coords.push(wx(worldPoly[j].x), wy(worldPoly[j].y));
      }
      pzItems.push({ el: el, tag: "polygon", coords: coords });
    }
    function storeLine(el, p1, p2) {
      pzItems.push({ el: el, tag: "line", coords: [wx(p1.x), wy(p1.y), wx(p2.x), wy(p2.y)] });
    }

    // Pass 1: external black cell outlines
    var defs = document.createElementNS(SVG_NS, "defs");
    var hasDefs = false;
    var clipId = 0;
    for (var ci = 0; ci < cells.length; ci++) {
      var c = cells[ci];
      if (!c.external || !isBlack(c, invertColor)) continue;
      var clipped = App.clipPolygonByConvex(c.poly, clipPoly);
      if (clipped.length < 3) continue;

      var id = "g" + container.getAttribute("data-entry") + "c" + (clipId++);
      var cp = document.createElementNS(SVG_NS, "clipPath");
      cp.setAttribute("id", id);
      var cpPoly = document.createElementNS(SVG_NS, "polygon");
      cpPoly.setAttribute("points", clipped.map(function(q) { return wx(q.x).toFixed(6) + "," + wy(q.y).toFixed(6); }).join(" "));
      cp.appendChild(cpPoly);
      defs.appendChild(cp);
      storePolygon(cpPoly, clipped);
      hasDefs = true;

      var g = document.createElementNS(SVG_NS, "g");
      g.setAttribute("clip-path", "url(#" + id + ")");
      for (var ei = 0; ei < clipped.length; ei++) {
        var p1 = clipped[ei], p2 = clipped[(ei + 1) % clipped.length];
        if (!isArrangementEdge(p1, p2)) continue;
        var ln = document.createElementNS(SVG_NS, "line");
        ln.setAttribute("x1", wx(p1.x).toFixed(6));
        ln.setAttribute("y1", wy(p1.y).toFixed(6));
        ln.setAttribute("x2", wx(p2.x).toFixed(6));
        ln.setAttribute("y2", wy(p2.y).toFixed(6));
        g.appendChild(ln);
        storeLine(ln, p1, p2);
      }
      if (g.childNodes.length > 0) svg.appendChild(g);
    }
    if (hasDefs) svg.insertBefore(defs, svg.childNodes[1]);

    // Pass 2: internal black cells
    for (var ci2 = 0; ci2 < cells.length; ci2++) {
      var c2 = cells[ci2];
      if (c2.external || !isBlack(c2, invertColor)) continue;
      var clipped2 = App.clipPolygonByConvex(c2.poly, clipPoly);
      if (clipped2.length < 3) continue;
      var sideCount = Number.isFinite(c2.sideCount) ? c2.sideCount : c2.poly.length;
      var poly = document.createElementNS(SVG_NS, "polygon");
      poly.setAttribute("points", clipped2.map(function(q) { return wx(q.x).toFixed(6) + "," + wy(q.y).toFixed(6); }).join(" "));
      if (sideCount !== 3) poly.setAttribute("class", "defect");
      svg.appendChild(poly);
      storePolygon(poly, clipped2);
    }

    container.appendChild(svg);
    return pzItems;
  }

  // Pan/zoom setup
  function setupPanZoom(container, pzItems) {
    var svg = container.querySelector("svg");
    if (!svg) return;
    var svgW = SVG_SIZE, svgH = SVG_SIZE;
    var cx = 0, cy = 0, cw = svgW, ch = svgH;
    var ox = 0, oy = 0, ow = svgW, oh = svgH;

    function updateAll() {
      var sx = svgW / cw, sy = svgH / ch;
      for (var i = 0; i < pzItems.length; i++) {
        var it = pzItems[i];
        var co = it.coords;
        if (it.tag === "polygon") {
          var pts = "";
          for (var j = 0; j < co.length; j += 2) {
            if (j > 0) pts += " ";
            pts += ((co[j] - cx) * sx) + "," + ((co[j + 1] - cy) * sy);
          }
          it.el.setAttribute("points", pts);
        } else if (it.tag === "line") {
          it.el.setAttribute("x1", (co[0] - cx) * sx);
          it.el.setAttribute("y1", (co[1] - cy) * sy);
          it.el.setAttribute("x2", (co[2] - cx) * sx);
          it.el.setAttribute("y2", (co[3] - cy) * sy);
        }
      }
    }

    function svgMap(rect, sx2, sy2) {
      var sc = Math.min(rect.width / svgW, rect.height / svgH);
      var rw = svgW * sc, rh = svgH * sc;
      return {
        mx: (sx2 - (rect.width - rw) / 2) / rw,
        my: (sy2 - (rect.height - rh) / 2) / rh,
        s: cw / (svgW * sc)
      };
    }

    var dragging = false, lastX, lastY;
    container.addEventListener("pointerdown", function(e) {
      if (e.button !== 0) return;
      dragging = true; lastX = e.clientX; lastY = e.clientY;
      container.setPointerCapture(e.pointerId);
      e.preventDefault();
    });
    container.addEventListener("pointermove", function(e) {
      if (!dragging) return;
      var rect = container.getBoundingClientRect();
      var m = svgMap(rect, 0, 0);
      cx -= (e.clientX - lastX) * m.s;
      cy -= (e.clientY - lastY) * m.s;
      lastX = e.clientX; lastY = e.clientY;
      updateAll();
    });
    container.addEventListener("pointerup", function() { dragging = false; });
    container.addEventListener("pointercancel", function() { dragging = false; });

    container.addEventListener("wheel", function(e) {
      if (!e.ctrlKey) return;
      e.preventDefault();
      var rect = container.getBoundingClientRect();
      var m = svgMap(rect, e.clientX - rect.left, e.clientY - rect.top);
      var factor = e.deltaY > 0 ? 1.15 : 1 / 1.15;
      var nw = cw * factor, nh = ch * factor;
      cx += (cw - nw) * m.mx;
      cy += (ch - nh) * m.my;
      cw = nw; ch = nh;
      updateAll();
    }, { passive: false });

    container.addEventListener("dblclick", function() {
      cx = ox; cy = oy; cw = ow; ch = oh; updateAll();
    });

    var pinchIds = [null, null];
    var pinchPts = [{ x: 0, y: 0 }, { x: 0, y: 0 }];
    var pinchActive = false;
    function pinchState() {
      return {
        dist: Math.hypot(pinchPts[1].x - pinchPts[0].x, pinchPts[1].y - pinchPts[0].y),
        mid: { x: (pinchPts[0].x + pinchPts[1].x) / 2, y: (pinchPts[0].y + pinchPts[1].y) / 2 }
      };
    }
    container.addEventListener("touchstart", function(e) {
      for (var i = 0; i < e.changedTouches.length; i++) {
        var t = e.changedTouches[i];
        if (pinchIds[0] === null) { pinchIds[0] = t.identifier; pinchPts[0] = { x: t.clientX, y: t.clientY }; }
        else if (pinchIds[1] === null) { pinchIds[1] = t.identifier; pinchPts[1] = { x: t.clientX, y: t.clientY }; pinchActive = true; dragging = false; }
      }
    }, { passive: true });
    container.addEventListener("touchmove", function(e) {
      if (!pinchActive) return;
      var prev = pinchState();
      for (var i = 0; i < e.changedTouches.length; i++) {
        var t = e.changedTouches[i];
        if (t.identifier === pinchIds[0]) pinchPts[0] = { x: t.clientX, y: t.clientY };
        else if (t.identifier === pinchIds[1]) pinchPts[1] = { x: t.clientX, y: t.clientY };
      }
      var cur = pinchState();
      if (prev.dist > 1) {
        var rect = container.getBoundingClientRect();
        var m = svgMap(rect, cur.mid.x - rect.left, cur.mid.y - rect.top);
        var factor = prev.dist / cur.dist;
        var nw = cw * factor, nh = ch * factor;
        cx += (cw - nw) * m.mx;
        cy += (ch - nh) * m.my;
        cw = nw; ch = nh;
        cx -= (cur.mid.x - prev.mid.x) * m.s;
        cy -= (cur.mid.y - prev.mid.y) * m.s;
        updateAll();
      }
    }, { passive: true });
    function pinchEnd(e) {
      for (var i = 0; i < e.changedTouches.length; i++) {
        var id = e.changedTouches[i].identifier;
        if (id === pinchIds[0]) pinchIds[0] = null;
        if (id === pinchIds[1]) pinchIds[1] = null;
      }
      if (pinchIds[0] === null || pinchIds[1] === null) pinchActive = false;
      if (pinchIds[0] === null && pinchIds[1] === null) pinchIds = [null, null];
    }
    container.addEventListener("touchend", pinchEnd, { passive: true });
    container.addEventListener("touchcancel", pinchEnd, { passive: true });
  }

  // Render all entries
  GALLERY_DATA.forEach(function(entry, idx) {
    var container = document.querySelector('[data-entry="' + idx + '"]');
    if (!container) return;
    var pzItems = renderEntry(entry, container);
    setupPanZoom(container, pzItems);
  });
})();
</script>
<footer>Roman Parpalak and Denis Utkin, 2026</footer>
</body>
</html>`;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
function main() {
  const galleryDir = path.join(__dirname);
  const outDir = path.join(__dirname, "..", "docs", "gallery");

  // Load index
  const indexPath = path.join(galleryDir, "index.json");
  const index = JSON.parse(fs.readFileSync(indexPath, "utf-8"));
  const indexByFile = {};
  for (const entry of index) {
    indexByFile[entry.file] = entry;
  }

  // Find all *.lines.csv files, ordered by index.json
  const indexedFiles = index.map(e => e.file);
  const allFiles = fs.readdirSync(galleryDir).filter(f => f.endsWith(".lines.csv"));
  const extraFiles = allFiles.filter(f => !indexedFiles.includes(f)).sort();
  const files = [...indexedFiles.filter(f => allFiles.includes(f)), ...extraFiles];

  if (files.length === 0) {
    console.error("No *.lines.csv files found in gallery/");
    process.exit(1);
  }

  const entries = [];
  for (const file of files) {
    const filepath = path.join(galleryDir, file);
    const lines = parseLinesFile(filepath);
    const n = lines.length;
    const meta = indexByFile[file] || {};
    const title = meta.title || `${n} lines`;
    const description = meta.description || "";

    console.log(`Processing ${file}: ${n} lines...`);

    const { cells } = computeCells(lines);
    const triangles = countTriangles(cells);
    const ub = upperBound(n);

    entries.push({ n, lines, triangles, upperBound: ub, title, description });
    console.log(`  -> ${triangles} triangles (upper bound ${ub.value})`);
  }

  // Write output
  fs.mkdirSync(outDir, { recursive: true });
  const html = generateGalleryHTML(entries);
  const outPath = path.join(outDir, "index.html");
  fs.writeFileSync(outPath, html, "utf-8");
  console.log(`\nGallery written to ${outPath}`);
}

main();
