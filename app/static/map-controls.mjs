// Display-only SVG controls. No requests, case mutations, or remote map provider.
const NS = 'http://www.w3.org/2000/svg';
export const MAX_ZOOM = 12;
const clamp = (n, low, high) => Math.min(high, Math.max(low, n));
export function parseViewBox(value) {
  const box = String(value).trim().split(/[\s,]+/).map(Number);
  if (box.length !== 4 || !box.every(Number.isFinite) || box[2] <= 0 || box[3] <= 0) throw Error('Invalid map extent.');
  return box;
}
export function boundView(base, view) {
  const width = clamp(view[2], base[2] / MAX_ZOOM, base[2]);
  const height = width * base[3] / base[2];
  // A little edge space allows island/coastal selections to be centered, but
  // never allows panning the entire map out of reach.
  return [clamp(view[0], base[0] - width * .1, base[0] + base[2] - width * .9),
    clamp(view[1], base[1] - height * .1, base[1] + base[3] - height * .9), width, height];
}
export function zoomView(base, view, factor, anchor = [.5, .5]) {
  const width = clamp(view[2] / factor, base[2] / MAX_ZOOM, base[2]), height = width * base[3] / base[2];
  return boundView(base, [view[0] + (view[2] - width) * anchor[0], view[1] + (view[3] - height) * anchor[1], width, height]);
}
export function panView(base, view, dx, dy) { return boundView(base, [view[0] + dx, view[1] + dy, view[2], view[3]]); }
export function fitView(base, box) {
  const width = clamp(Math.max(box.width, box.height * base[2] / base[3]) * 1.25, base[2] / MAX_ZOOM, base[2]);
  const height = width * base[3] / base[2];
  return boundView(base, [box.x + box.width / 2 - width / 2, box.y + box.height / 2 - height / 2, width, height]);
}
export function mapPreferences(value, labels = true) {
  const result = {status: true, timing: true, labels, legend: true};
  if (value && typeof value === 'object') for (const key of Object.keys(result)) {
    if (typeof value[key] === 'boolean') result[key] = value[key];
  }
  return result;
}

export function createMapControls({host, legend, id, label, defaultLabels = true, selectionName = 'selection'}) {
  const node = (tag, text, cls) => { const n = document.createElement(tag); if (text) n.textContent = text; if (cls) n.className = cls; return n; };
  const storageKey = 'civicrelay.map-controls.v1.' + id;
  let preferences = mapPreferences(null, defaultLabels);
  try { preferences = mapPreferences(JSON.parse(localStorage.getItem(storageKey)), defaultLabels); } catch { /* Storage is optional. */ }
  let svg = null, base = null, view = null, scope = null, selected = null, listeners = null;
  host.classList.add('interactive-map');
  host.setAttribute('role', 'region'); host.setAttribute('aria-label', label);
  const toolbar = node('div', null, 'map-toolbar'); toolbar.id = id + '-controls';
  toolbar.setAttribute('role', 'group'); toolbar.setAttribute('aria-label', label + ' controls');
  const navigation = node('div', null, 'map-navigation');
  const controls = [];
  function button(text, name, action, parent = navigation) {
    const b = node('button', text); b.type = 'button'; b.title = name; b.setAttribute('aria-label', name); b.setAttribute('aria-controls', host.id);
    b.onclick = action; parent.append(b); controls.push(b); return b;
  }
  const zoomIn = button('+', 'Zoom in', () => change(zoomView(base, view, 1.5)));
  const zoomOut = button('−', 'Zoom out', () => change(zoomView(base, view, 1 / 1.5)));
  const readout = node('output', '100%', 'map-zoom'); readout.setAttribute('aria-label', 'Map zoom'); navigation.append(readout);
  button('Fit map', 'Fit whole map', () => change([...base]));
  const fitSelection = button('Fit ' + selectionName, 'Fit selected ' + selectionName, () => {
    const path = selected?.querySelector('path'); if (path) change(fitView(base, path.getBBox()));
  });
  const pan = node('div', null, 'map-pan'); pan.setAttribute('role', 'group'); pan.setAttribute('aria-label', 'Pan map');
  for (const [text, name, x, y] of [['←', 'west', -1, 0], ['↑', 'north', 0, -1], ['↓', 'south', 0, 1], ['→', 'east', 1, 0]]) {
    button(text, 'Pan ' + name, () => change(panView(base, view, view[2] * .2 * x, view[3] * .2 * y)), pan);
  }
  const layers = node('details', null, 'map-layers'); layers.append(node('summary', 'Layers'));
  const choices = node('div', null, 'map-layer-choices');
  for (const [key, text] of [['status', 'Request status colors'], ['timing', 'Timing outlines'], ['labels', 'Place labels']]) {
    const wrap = node('label'), input = node('input'); input.type = 'checkbox'; input.checked = preferences[key]; input.dataset.layer = key;
    input.onchange = () => { preferences[key] = input.checked; applyLayers(); savePreferences(); };
    wrap.append(input, document.createTextNode(text)); choices.append(wrap);
  }
  layers.append(choices); toolbar.append(navigation, pan, layers); host.before(toolbar);
  const help = node('p', 'Drag to pan · Ctrl/⌘ + scroll to zoom · Keyboard: arrows pan, +/− zoom, 0/Home fits map.', 'map-controls-help');
  help.id = id + '-help'; host.after(help);
  const legendPanel = node('details', null, 'map-legend-panel'); legendPanel.id = id + '-legend-panel';
  const legendSummary = node('summary', 'Legend'); legendPanel.append(legendSummary); legend.before(legendPanel); legendPanel.append(legend);
  legendPanel.open = preferences.legend;
  // Persist before navigation/reload can cancel the native deferred toggle event.
  legendSummary.addEventListener('click', e => { e.preventDefault(); legendPanel.open = !legendPanel.open; preferences.legend = legendPanel.open; savePreferences(); });
  legendPanel.addEventListener('toggle', () => { preferences.legend = legendPanel.open; savePreferences(); });
  const statusLegend = node('div', null, 'map-status-legend');
  const neutralLegend = node('p', 'Status colors hidden — neutral shapes do not indicate request status.');
  const timingLegend = node('div', null, 'map-timing-legend');
  for (const [type, text] of [['overdue', 'Past timing date — verify evidence'], ['soon', 'Timing checkpoint due soon']]) {
    const entry = node('span'), swatch = node('i', null, 'map-outline-key ' + type); swatch.setAttribute('aria-hidden', 'true'); entry.append(swatch, document.createTextNode(text)); timingLegend.append(entry);
  }
  timingLegend.append(node('p', 'Planning signals, not a finding of a legal violation.'));
  const selectionLegend = node('span'), selectionKey = node('i', null, 'map-outline-key selected'); selectionKey.setAttribute('aria-hidden', 'true');
  selectionLegend.append(selectionKey, document.createTextNode('Dashed blue outline: selected or keyboard-focused place'));
  legend.replaceChildren(statusLegend, neutralLegend, timingLegend, selectionLegend);
  function savePreferences() {
    try { localStorage.setItem(storageKey, JSON.stringify(preferences)); } catch { /* Display works with storage disabled. */ }
  }
  function applyLayers() {
    for (const key of ['status', 'timing', 'labels']) host.dataset[key + 'Layer'] = preferences[key] ? 'on' : 'off';
    statusLegend.hidden = !preferences.status; neutralLegend.hidden = preferences.status; timingLegend.hidden = !preferences.timing;
  }
  function change(next) {
    if (!svg) return;
    view = next; svg.setAttribute('viewBox', view.map(n => Number(n.toFixed(5))).join(' '));
    const zoom = base[2] / view[2]; readout.textContent = Math.round(zoom * 100) + '%';
    zoomIn.disabled = zoom >= MAX_ZOOM - .00001; zoomOut.disabled = zoom <= 1.00001;
    // County labels keep a readable size as the map is enlarged.
    for (const text of svg.querySelectorAll('.county-label')) text.setAttribute('font-size', String(12 / Math.sqrt(zoom)));
  }
  function clear() {
    listeners?.abort(); listeners = null; svg = null; selected = null; host.classList.remove('is-panning');
    for (const b of controls) b.disabled = true;
  }
  function mount(nextSvg, {scope: nextScope, selected: nextSelected = null} = {}) {
    clear(); svg = nextSvg; selected = nextSelected;
    const nextBase = parseViewBox(svg.getAttribute('viewBox'));
    if (scope !== nextScope || !base || base.some((n, i) => n !== nextBase[i])) view = [...nextBase];
    base = nextBase; scope = nextScope;
    for (const b of controls) b.disabled = false;
    fitSelection.disabled = !selected;
    svg.setAttribute('tabindex', '0'); svg.setAttribute('aria-label', label + ' canvas'); svg.setAttribute('aria-describedby', help.id);
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    for (const group of svg.querySelectorAll('.state, .county-shape')) {
      const path = group.querySelector('path'), outline = path.cloneNode(); outline.setAttribute('class', 'map-selection'); outline.setAttribute('aria-hidden', 'true'); group.append(outline);
      if (group.classList.contains('county-shape')) {
        const bounds = path.getBBox(), text = document.createElementNS(NS, 'text');
        text.setAttribute('class', 'map-label county-label'); text.setAttribute('x', String(bounds.x + bounds.width / 2)); text.setAttribute('y', String(bounds.y + bounds.height / 2));
        text.setAttribute('text-anchor', 'middle'); text.setAttribute('dominant-baseline', 'middle'); text.setAttribute('aria-hidden', 'true');
        text.textContent = group.dataset.name; group.append(text);
      }
    }
    change(view); applyLayers();
    listeners = new AbortController(); const signal = listeners.signal;
    // Inverse SVG transform accounts for responsive sizes and letterboxing.
    const point = (x, y) => { const matrix = svg.getScreenCTM(); return matrix ? new DOMPoint(x, y).matrixTransform(matrix.inverse()) : null; };
    svg.addEventListener('wheel', e => {
      if (!e.ctrlKey && !e.metaKey) return; const p = point(e.clientX, e.clientY); if (!p) return;
      e.preventDefault(); const pixels = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 300 : 1);
      change(zoomView(base, view, Math.exp(clamp(-pixels * .002, -1, 1)), [(p.x - view[0]) / view[2], (p.y - view[1]) / view[3]]));
    }, {passive: false, signal});
    svg.addEventListener('keydown', e => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const directions = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]};
      if (directions[e.key]) { e.preventDefault(); const [x, y] = directions[e.key]; change(panView(base, view, x * view[2] * .15, y * view[3] * .15)); }
      else if (['+', '=', '-', '0', 'Home'].includes(e.key)) { e.preventDefault(); change(['0', 'Home'].includes(e.key) ? [...base] : zoomView(base, view, e.key === '-' ? 1 / 1.5 : 1.5)); }
    }, {signal});
    const pointers = new Map(); let gesture = null, moved = false, suppressUntil = 0;
    const center = () => { const ps = [...pointers.values()]; return {x: ps.reduce((n, p) => n + p.x, 0) / ps.length, y: ps.reduce((n, p) => n + p.y, 0) / ps.length,
      distance: ps.length > 1 ? Math.hypot(ps[0].x - ps[1].x, ps[0].y - ps[1].y) : 0}; };
    function rebaseGesture() {
      if (!pointers.size) { gesture = null; return; }
      const c = center(); gesture = {center: c, point: point(c.x, c.y), view: [...view], matrix: svg.getScreenCTM()?.inverse()};
    }
    svg.addEventListener('pointerdown', e => {
      if (e.button !== 0) return;
      if (!pointers.size) moved = false;
      pointers.set(e.pointerId, {x: e.clientX, y: e.clientY}); rebaseGesture();
      if (pointers.size > 1) moved = true;
    }, {signal});
    svg.addEventListener('pointermove', e => {
      if (!pointers.has(e.pointerId) || !gesture?.point || !gesture.matrix) return;
      pointers.set(e.pointerId, {x: e.clientX, y: e.clientY}); const c = center();
      if (!moved && Math.hypot(c.x - gesture.center.x, c.y - gesture.center.y) < 5) return;
      moved = true; e.preventDefault(); host.classList.add('is-panning');
      for (const pointerId of pointers.keys()) if (!svg.hasPointerCapture(pointerId)) svg.setPointerCapture(pointerId);
      const factor = gesture.center.distance > 0 && c.distance > 0 ? c.distance / gesture.center.distance : 1;
      const width = clamp(gesture.view[2] / factor, base[2] / MAX_ZOOM, base[2]), height = width * base[3] / base[2];
      const current = new DOMPoint(c.x, c.y).matrixTransform(gesture.matrix);
      change(boundView(base, [gesture.point.x - (current.x - gesture.view[0]) * width / gesture.view[2],
        gesture.point.y - (current.y - gesture.view[1]) * height / gesture.view[3], width, height]));
    }, {signal});
    const end = e => {
      if (!pointers.has(e.pointerId)) return;
      pointers.delete(e.pointerId); if (moved) suppressUntil = performance.now() + 350;
      if (svg.hasPointerCapture(e.pointerId)) svg.releasePointerCapture(e.pointerId);
      rebaseGesture(); if (!pointers.size) host.classList.remove('is-panning');
    };
    for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) svg.addEventListener(event, end, {signal});
    svg.addEventListener('pointerleave', e => { if (!svg.hasPointerCapture(e.pointerId)) end(e); }, {signal});
    svg.addEventListener('click', e => { if (performance.now() < suppressUntil) { e.preventDefault(); e.stopImmediatePropagation(); } }, {capture: true, signal});
  }
  clear(); applyLayers();
  return {mount, clear, setLegend: nodes => statusLegend.replaceChildren(...nodes),
    snapshot: () => ({scope, zoom: base && view ? Number((base[2] / view[2]).toFixed(3)) : 1,
      layers: {status: preferences.status, timing: preferences.timing, labels: preferences.labels}, legend_open: legendPanel.open})};
}
