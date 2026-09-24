import assert from 'node:assert/strict';
import test from 'node:test';
import {MAX_ZOOM, parseViewBox, boundView, zoomView, panView, fitView, mapPreferences} from './static/map-controls.mjs';
const base = [0, 0, 900, 600];

test('map extents accept whitespace/commas and reject malformed or empty extents', () => {
  assert.deepEqual(parseViewBox(' 0, 0 900 600 '), base);
  for (const value of ['', '0 0 0 50', '0 0 -10 10', '0 0 NaN 60', '0 0 Infinity 600', '0 0 900 600 1']) assert.throws(() => parseViewBox(value));
});
test('zoom preserves aspect ratio and anchor, with bounded minimum/maximum', () => {
  assert.deepEqual(zoomView(base, base, 2, [.25, .75]), [112.5, 225, 450, 300]);
  assert.deepEqual(zoomView(base, base, .1), base);
  const maximum = zoomView(base, base, 1e9);
  assert.equal(maximum[2], base[2] / MAX_ZOOM);
  assert.equal(maximum[2] / maximum[3], base[2] / base[3]);
  assert.deepEqual(zoomView(base, maximum, 2), maximum);
});
test('panning never strands the map offscreen, including offset source extents', () => {
  const view = zoomView(base, base, 2);
  assert.deepEqual(panView(base, view, 10, -20), [235, 130, 450, 300]);
  assert.deepEqual(panView(base, view, -1e6, -1e6), [-45, -30, 450, 300]);
  assert.deepEqual(panView(base, view, 1e6, 1e6), [495, 330, 450, 300]);
  assert.deepEqual(boundView([100, 100, 900, 600], [-1e6, -1e6, 900, 600]), [10, 40, 900, 600]);
});
test('fit selection includes padding and handles tiny or disconnected shapes', () => {
  assert.deepEqual(fitView(base, {x:300, y:200, width:100, height:80}), [275, 190, 150, 100]);
  assert.equal(fitView(base, {x:450, y:300, width:0, height:0})[2], 75);
  assert.deepEqual(fitView(base, {x:0, y:0, width:900, height:600}), base);
});
test('persist only known boolean display preferences with safe defaults', () => {
  assert.deepEqual(mapPreferences(null, false), {status:true, timing:true, labels:false, legend:true});
  assert.deepEqual(mapPreferences({status:false, timing:'false', labels:true, legend:false, arbitrary:'ignored'}, false), {status:false, timing:true, labels:true, legend:false});
});
