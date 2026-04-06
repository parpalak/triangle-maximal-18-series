#!/usr/bin/env node
//
// Reads gallery/*.lines.csv, generates docs/gallery/index.html
// with inline SVG images of each line configuration.
//
// Usage: node gallery/generate.js
//
// Reuses computational core from docs/viewer/js/ (parser, cells, matrix).

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
  // Replace window.App references with our App object
  const wrapped = code
    .replace(/const App = \(window\.App = window\.App \|\| \{\}\);/, "")
    .replace(/const App = window\.App;/g, "")
    .replace(/window\.__lvColorDebug/g, "null");
  // Execute with App in scope, stub document/window
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
loadModule("matrix.js");

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

  // Build base polygon (large rectangle around bbox)
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
// Upper bound: floor(n(n-2)/3)
// ---------------------------------------------------------------------------
function upperBound(n) {
  if (n % 2 === 0) return { value: Math.floor(n * (3 * n - 7) / 9), formula: "⌊n(3n−7)/9⌋" };
  if (n % 6 === 1) return { value: (n * (n - 2) - 2) / 3, formula: "(n(n−2)−2)/3" };
  /* n % 6 === 3 || n % 6 === 5 */ return { value: n * (n - 2) / 3, formula: "n(n−2)/3" };
}

// ---------------------------------------------------------------------------
// Choose color orientation (more black cells = invert)
// ---------------------------------------------------------------------------
function chooseInvertColor(cells) {
  let c0 = 0, c1 = 0;
  for (const c of cells) {
    if (c.external) continue;
    if (c.parity === 0) c0++;
    else c1++;
  }
  return c0 > c1;
}

function isBlack(cell, invertColor) {
  return invertColor ? (cell.parity === 0) : (cell.parity === 1);
}

// ---------------------------------------------------------------------------
// Generate SVG string for a line configuration
// ---------------------------------------------------------------------------
function generateSVG(lines, cells, bbox, svgSize, svgIndex) {
  const svgPrefix = `s${svgIndex}`;
  const invertColor = chooseInvertColor(cells);

  // Non-uniform squeeze into square
  const bw = bbox.maxX - bbox.minX;
  const bh = bbox.maxY - bbox.minY;
  const padding = 0.06;
  const scaleX = svgSize * (1 - 2 * padding) / bw;
  const scaleY = svgSize * (1 - 2 * padding) / bh;
  const cx = (bbox.minX + bbox.maxX) / 2;
  const cy = (bbox.minY + bbox.maxY) / 2;
  const tx = svgSize / 2 - cx * scaleX;
  const ty = svgSize / 2 + cy * scaleY;

  function wx(x) { return tx + x * scaleX; }
  function wy(y) { return ty - y * scaleY; }
  function pt(q) { return `${wx(q.x).toFixed(6)},${wy(q.y).toFixed(6)}`; }

  // Clip polygon in world coords
  const clipMargin = 0.02;
  const clipPoly = [
    { x: bbox.minX - bw * clipMargin, y: bbox.minY - bh * clipMargin },
    { x: bbox.maxX + bw * clipMargin, y: bbox.minY - bh * clipMargin },
    { x: bbox.maxX + bw * clipMargin, y: bbox.maxY + bh * clipMargin },
    { x: bbox.minX - bw * clipMargin, y: bbox.maxY + bh * clipMargin },
  ];

  // Check if an edge lies on one of the arrangement lines
  const lineEps = Math.max(bw, bh) * 1e-6;
  function isArrangementEdge(p1, p2) {
    for (const line of lines) {
      const d1 = Math.abs(p1.y - line.m * p1.x - line.b) / Math.sqrt(1 + line.m * line.m);
      const d2 = Math.abs(p2.y - line.m * p2.x - line.b) / Math.sqrt(1 + line.m * line.m);
      if (d1 < lineEps && d2 < lineEps) return true;
    }
    return false;
  }

  const parts = [];
  parts.push(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${svgSize} ${svgSize}">`);
  parts.push(`<rect width="${svgSize}" height="${svgSize}" fill="#ffffff"/>`);

  // Pass 1: external black cell outlines, clipped to cell interior.
  let clipId = 0;
  const defs = [];
  const extGroups = [];
  for (const c of cells) {
    if (!c.external) continue;
    if (!isBlack(c, invertColor)) continue;

    const clipped = App.clipPolygonByConvex(c.poly, clipPoly);
    if (clipped.length < 3) continue;

    const id = `${svgPrefix}c${clipId++}`;
    const points = clipped.map(q => pt(q)).join(" ");
    defs.push(`<clipPath id="${id}"><polygon points="${points}"/></clipPath>`);

    const edgeLines = [];
    for (let i = 0; i < clipped.length; i++) {
      const p1 = clipped[i];
      const p2 = clipped[(i + 1) % clipped.length];
      if (!isArrangementEdge(p1, p2)) continue;
      edgeLines.push(`<line x1="${wx(p1.x).toFixed(6)}" y1="${wy(p1.y).toFixed(6)}" x2="${wx(p2.x).toFixed(6)}" y2="${wy(p2.y).toFixed(6)}"/>`);
    }
    if (edgeLines.length > 0) {
      extGroups.push(`<g clip-path="url(#${id})">${edgeLines.join("")}</g>`);
    }
  }
  if (defs.length > 0) {
    parts.push(`<defs>${defs.join("")}</defs>`);
  }
  for (const g of extGroups) parts.push(g);

  // Pass 2: internal cells (skip white — background is already white)
  for (const c of cells) {
    if (c.external) continue;

    const black = isBlack(c, invertColor);
    if (!black) continue;

    const clipped = App.clipPolygonByConvex(c.poly, clipPoly);
    if (clipped.length < 3) continue;

    const sideCount = Number.isFinite(c.sideCount) ? c.sideCount : c.poly.length;
    const points = clipped.map(q => pt(q)).join(" ");
    parts.push(sideCount !== 3
      ? `<polygon points="${points}" fill="#f00"/>`
      : `<polygon points="${points}"/>`);
  }

  parts.push("</svg>");
  return parts.join("\n");
}

// ---------------------------------------------------------------------------
// Generate gallery HTML
// ---------------------------------------------------------------------------
function generateGalleryHTML(entries) {
  const items = entries.map(e => {
    const linesText = e.lines.map((l, i) => `${i}: y = ${l.m} * x + ${l.b}`).join("\n");
    const csvText = "m,b\\n" + e.lines.map(l => `${l.m},${l.b}`).join("\\n");

    return `
    <div class="entry">
      <div class="entry-header">
        <h2>${e.title}</h2>
        <p class="description">${e.description}</p>
      </div>
      <div class="entry-body">
        <div class="image" data-panzoom>${e.svg}</div>
        <div class="info">
          <p class="stats">${e.n} lines, ${e.triangles} triangles (upper bound <span class="upper-bound" title="${e.upperBound.formula}">${e.upperBound.value}</span>)</p>
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
<script>
(function(){
  document.querySelectorAll("[data-panzoom]").forEach(function(container){
    var svg = container.querySelector("svg");
    if(!svg) return;
    var vb = svg.getAttribute("viewBox").split(/\\s+/).map(Number);
    var ox = vb[0], oy = vb[1], ow = vb[2], oh = vb[3];
    var cx = ox, cy = oy, cw = ow, ch = oh;
    function set(){ svg.setAttribute("viewBox", cx+" "+cy+" "+cw+" "+ch); }
    // Map screen coords to viewBox fraction (accounts for preserveAspectRatio meet)
    function svgMap(rect, sx, sy){
      var sc = Math.min(rect.width/cw, rect.height/ch);
      var rw = cw*sc, rh = ch*sc;
      return { mx: (sx - (rect.width-rw)/2) / rw,
               my: (sy - (rect.height-rh)/2) / rh,
               s: 1/sc };
    }
    // Mouse drag
    var dragging = false, lastX, lastY;
    container.addEventListener("pointerdown", function(e){
      if(e.button !== 0) return;
      dragging = true; lastX = e.clientX; lastY = e.clientY;
      container.setPointerCapture(e.pointerId);
      e.preventDefault();
    });
    container.addEventListener("pointermove", function(e){
      if(!dragging) return;
      var rect = container.getBoundingClientRect();
      var m = svgMap(rect, 0, 0);
      cx -= (e.clientX - lastX) * m.s;
      cy -= (e.clientY - lastY) * m.s;
      lastX = e.clientX; lastY = e.clientY;
      set();
    });
    container.addEventListener("pointerup", function(){ dragging = false; });
    container.addEventListener("pointercancel", function(){ dragging = false; });
    // Wheel zoom
    container.addEventListener("wheel", function(e){
      if(!e.ctrlKey) return;
      e.preventDefault();
      var rect = container.getBoundingClientRect();
      var m = svgMap(rect, e.clientX - rect.left, e.clientY - rect.top);
      var factor = e.deltaY > 0 ? 1.15 : 1/1.15;
      var nw = cw * factor, nh = ch * factor;
      cx += (cw - nw) * m.mx;
      cy += (ch - nh) * m.my;
      cw = nw; ch = nh;
      set();
    }, {passive: false});
    // Double-click reset
    container.addEventListener("dblclick", function(){
      cx = ox; cy = oy; cw = ow; ch = oh; set();
    });
    // Touch pinch zoom — track fingers by identifier
    var pinchIds = [null, null];
    var pinchPts = [{x:0,y:0},{x:0,y:0}];
    var pinchActive = false;
    function pinchState(){ return {
      dist: Math.hypot(pinchPts[1].x-pinchPts[0].x, pinchPts[1].y-pinchPts[0].y),
      mid: {x:(pinchPts[0].x+pinchPts[1].x)/2, y:(pinchPts[0].y+pinchPts[1].y)/2}
    };}
    container.addEventListener("touchstart", function(e){
      for(var i=0;i<e.changedTouches.length;i++){
        var t = e.changedTouches[i];
        if(pinchIds[0]===null){ pinchIds[0]=t.identifier; pinchPts[0]={x:t.clientX,y:t.clientY}; }
        else if(pinchIds[1]===null){ pinchIds[1]=t.identifier; pinchPts[1]={x:t.clientX,y:t.clientY}; pinchActive=true; dragging=false; }
      }
    }, {passive: true});
    container.addEventListener("touchmove", function(e){
      if(!pinchActive) return;
      var prev = pinchState();
      for(var i=0;i<e.changedTouches.length;i++){
        var t = e.changedTouches[i];
        if(t.identifier===pinchIds[0]) pinchPts[0]={x:t.clientX,y:t.clientY};
        else if(t.identifier===pinchIds[1]) pinchPts[1]={x:t.clientX,y:t.clientY};
      }
      var cur = pinchState();
      if(prev.dist > 1){
        var rect = container.getBoundingClientRect();
        var m = svgMap(rect, cur.mid.x - rect.left, cur.mid.y - rect.top);
        var factor = prev.dist / cur.dist;
        var nw = cw * factor, nh = ch * factor;
        cx += (cw - nw) * m.mx;
        cy += (ch - nh) * m.my;
        cw = nw; ch = nh;
        cx -= (cur.mid.x - prev.mid.x) * m.s;
        cy -= (cur.mid.y - prev.mid.y) * m.s;
        set();
      }
    }, {passive: true});
    function pinchEnd(e){
      for(var i=0;i<e.changedTouches.length;i++){
        var id = e.changedTouches[i].identifier;
        if(id===pinchIds[0]) pinchIds[0]=null;
        if(id===pinchIds[1]) pinchIds[1]=null;
      }
      if(pinchIds[0]===null || pinchIds[1]===null) pinchActive=false;
      if(pinchIds[0]===null && pinchIds[1]===null) pinchIds=[null,null];
    }
    container.addEventListener("touchend", pinchEnd, {passive: true});
    container.addEventListener("touchcancel", pinchEnd, {passive: true});
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

  const SVG_SIZE = 600;

  const entries = [];
  for (let fi = 0; fi < files.length; fi++) {
    const file = files[fi];
    const filepath = path.join(galleryDir, file);
    const lines = parseLinesFile(filepath);
    const n = lines.length;
    const name = file.replace(".lines.csv", "");
    const meta = indexByFile[file] || {};
    const title = meta.title || `${n} lines`;
    const description = meta.description || "";

    console.log(`Processing ${file}: ${n} lines...`);

    const { cells, bbox } = computeCells(lines);  // intersections not needed here
    const triangles = countTriangles(cells);
    const ub = upperBound(n);
    const svg = generateSVG(lines, cells, bbox, SVG_SIZE, fi);

    entries.push({ name, file, n, lines, triangles, upperBound: ub, svg, title, description });
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
