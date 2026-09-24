// Shared assertions for the synthetic, isolated browser fixtures only.
import assert from 'node:assert/strict';

const view = async (page, selector) => (await page.locator(selector + ' svg').getAttribute('viewBox')).split(' ').map(Number);

export async function checkNationalMap(page) {
  const toolbar = page.locator('#national-map-controls'), svg = page.locator('#map svg');
  const original = await view(page, '#map');
  assert.equal(await toolbar.getByRole('button', {name:'Zoom out', exact:true}).isDisabled(), true);
  await toolbar.getByRole('button', {name:'Zoom in', exact:true}).click();
  assert.equal(await toolbar.locator('output').innerText(), '150%');
  const zoomed = await view(page, '#map'); assert.ok(zoomed[2] < original[2]);
  await toolbar.getByRole('button', {name:'Pan east', exact:true}).click();
  assert.ok((await view(page, '#map'))[0] > zoomed[0]);
  await svg.focus(); await page.keyboard.press('Home'); assert.deepEqual(await view(page, '#map'), original);
  await page.keyboard.press('+'); assert.equal(await toolbar.locator('output').innerText(), '150%');
  await page.keyboard.press('ArrowLeft'); assert.ok((await view(page, '#map'))[0] < zoomed[0]);
  await toolbar.getByRole('button', {name:'Fit whole map', exact:true}).click();
  await page.locator('#state-select').selectOption('DC');
  await toolbar.getByRole('button', {name:'Fit selected state', exact:true}).click();
  assert.equal(await toolbar.locator('output').innerText(), '1200%');
  assert.equal(await toolbar.getByRole('button', {name:'Zoom in', exact:true}).isDisabled(), true);
  await toolbar.getByRole('button', {name:'Fit whole map', exact:true}).click();
  await page.locator('#state-select').selectOption('MI');

  // Layer controls change presentation, not the underlying status or selection.
  const state = page.locator('#map [data-state="MI"]'), path = state.locator('path:not(.map-selection)');
  const status = await state.getAttribute('data-status'), fill = await path.evaluate(n => getComputedStyle(n).fill);
  await toolbar.locator('summary').click();
  await toolbar.getByLabel('Request status colors', {exact:true}).uncheck();
  assert.equal(await page.locator('#map').getAttribute('data-status-layer'), 'off');
  assert.notEqual(await path.evaluate(n => getComputedStyle(n).fill), fill);
  assert.equal(await state.getAttribute('data-status'), status);
  assert.equal(await state.getAttribute('aria-pressed'), 'true');
  assert.equal(await page.locator('#legend .map-status-legend').isVisible(), false);
  assert.match(await page.locator('#legend').innerText(), /Status colors hidden/);
  await toolbar.getByLabel('Timing outlines', {exact:true}).uncheck();
  assert.equal(await page.locator('#legend .map-timing-legend').isVisible(), false);
  await toolbar.getByLabel('Place labels', {exact:true}).uncheck();
  assert.equal(await state.locator('text').isVisible(), false);
  assert.equal(await state.locator('.map-selection').isVisible(), true);
  await page.locator('#national-map-legend-panel>summary').click();
  assert.equal(await page.locator('#legend').isVisible(), false);
  await page.reload(); await page.getByText('Private records workspace ready.', {exact:false}).waitFor();
  for (const layer of ['status','timing','labels']) assert.equal(await page.locator('#map').getAttribute('data-' + layer + '-layer'), 'off');
  assert.equal(await page.locator('#legend').isVisible(), false);
  await toolbar.locator('summary').click();
  for (const text of ['Request status colors','Timing outlines','Place labels']) await toolbar.getByLabel(text, {exact:true}).check();
  await toolbar.locator('summary').click(); await page.locator('#national-map-legend-panel>summary').click();

  // Dragging suppresses the resulting click; a normal click/keyboard choice works.
  await toolbar.getByRole('button', {name:'Zoom in', exact:true}).click();
  await svg.scrollIntoViewIfNeeded(); const rect = await svg.boundingBox();
  const before = await view(page, '#map'), selected = await page.locator('#state-select').inputValue();
  await page.mouse.move(rect.x + rect.width * .45, rect.y + rect.height * .55); await page.mouse.down();
  await page.mouse.move(rect.x + rect.width * .6, rect.y + rect.height * .65, {steps:10}); await page.mouse.up();
  assert.notDeepEqual(await view(page, '#map'), before); assert.equal(await page.locator('#state-select').inputValue(), selected);
  const afterDrag = await view(page, '#map');
  await page.mouse.wheel(0, -100);
  assert.deepEqual(await view(page, '#map'), afterDrag, 'ordinary scrolling must not zoom');
  await svg.scrollIntoViewIfNeeded(); const wheelRect = await svg.boundingBox();
  await page.mouse.move(wheelRect.x + wheelRect.width / 2, wheelRect.y + wheelRect.height / 2);
  await page.keyboard.down('Control'); await page.mouse.wheel(0, -100); await page.keyboard.up('Control');
  await page.waitForFunction(width => Number(document.querySelector('#map svg').getAttribute('viewBox').split(' ')[2]) < width, afterDrag[2]);
  await toolbar.getByRole('button', {name:'Fit whole map', exact:true}).click();
  await state.press('Enter'); assert.equal(await page.locator('#state-select').inputValue(), 'MI');
  assert.equal(await page.locator('#map [data-state="MI"]').evaluate(n => n === document.activeElement), true);
  await toolbar.getByRole('button', {name:'Fit selected state', exact:true}).click();
  assert.ok((await view(page, '#map'))[2] < original[2]);
  const fitted = await view(page, '#map'); await page.locator('#state-select').selectOption('WI');
  assert.deepEqual(await view(page, '#map'), fitted, 'selection redraw must preserve viewport');
  await page.locator('#state-select').selectOption('MI'); await toolbar.getByRole('button', {name:'Fit whole map', exact:true}).click();
}

export async function checkCountyMap(page) {
  const toolbar = page.locator('#county-map-controls');
  assert.equal(await toolbar.getByRole('button', {name:'Fit selected county', exact:true}).isDisabled(), true);
  await page.locator('#county-progress-rows').getByRole('button', {name:'Allegan County', exact:true}).click();
  await toolbar.getByRole('button', {name:'Fit selected county', exact:true}).click();
  const fitted = await view(page, '#county-progress-map'); assert.ok(fitted[2] < 200);
  await toolbar.locator('summary').click(); await toolbar.getByLabel('Place labels', {exact:true}).check();
  assert.equal(await page.locator('#county-progress-map .county-label').count(), 83);
  await toolbar.getByLabel('Request status colors', {exact:true}).uncheck();
  assert.equal(await page.locator('#county-progress-legend .map-status-legend').isVisible(), false);
  await page.locator('#county-progress-search').fill('Allegan');
  assert.deepEqual(await view(page, '#county-progress-map'), fitted);
  const refresh = page.waitForResponse(r => r.url().endsWith('/api/operation') && r.request().postDataJSON()?.tool === 'desk_list_counties');
  await page.getByRole('button', {name:'Refresh saved status', exact:true}).click(); await refresh;
  await page.waitForFunction(() => document.querySelector('#county-progress-panel').getAttribute('aria-busy') === 'false');
  assert.deepEqual(await view(page, '#county-progress-map'), fitted);
  assert.equal(await page.locator('#county-progress-map [data-county-id="county:26005"]').getAttribute('aria-pressed'), 'true');
  await page.locator('#county-progress-workflow').selectOption('records');
  await page.waitForFunction(() => document.querySelector('#county-progress-counts').textContent.includes('0 with requests'));
  assert.deepEqual(await view(page, '#county-progress-map'), fitted, 'same geography retains zoom across workflow switch');
  await page.locator('#county-progress-state').selectOption('WI');
  await page.waitForFunction(() => document.querySelectorAll('#county-progress-map .county-shape').length === 72);
  assert.equal(await toolbar.locator('output').innerText(), '100%', 'different geography resets zoom');
  await page.locator('#county-progress-state').selectOption('MI');
  await page.waitForFunction(() => document.querySelectorAll('#county-progress-map .county-shape').length === 83);
  await page.locator('#county-progress-workflow').selectOption('equipment');
  await page.waitForFunction(() => document.querySelector('#county-progress-counts').textContent.includes('6 with requests'));
  await toolbar.getByLabel('Request status colors', {exact:true}).check(); await toolbar.getByLabel('Place labels', {exact:true}).uncheck(); await toolbar.locator('summary').click();
}

export async function checkDirtyMapNavigation(page) {
  const note = page.locator('#case-note'), original = await note.inputValue(); await note.fill('Unsaved synthetic map-control regression');
  const revision = await page.locator('#case-workspace').innerText();
  for (const id of ['national-map','county-map']) {
    const controls = page.locator('#' + id + '-controls');
    await controls.getByRole('button', {name:'Zoom in', exact:true}).click();
    await controls.getByRole('button', {name:'Pan west', exact:true}).click();
    await controls.getByRole('button', {name:'Fit whole map', exact:true}).click();
    await controls.locator('summary').click(); await controls.getByLabel('Timing outlines', {exact:true}).uncheck(); await controls.getByLabel('Timing outlines', {exact:true}).check(); await controls.locator('summary').click();
    await page.locator('#' + id + '-legend-panel>summary').click(); await page.locator('#' + id + '-legend-panel>summary').click();
  }
  const refresh = page.waitForResponse(r => r.url().endsWith('/api/operation') && r.request().postDataJSON()?.tool === 'desk_list_counties');
  await page.getByRole('button', {name:'Refresh saved status', exact:true}).click(); await refresh;
  assert.equal(await note.inputValue(), 'Unsaved synthetic map-control regression');
  assert.equal(await page.locator('#case-workspace').innerText(), revision);
  await note.fill(original); // Discard only this test's unsaved input, never save it.
}

export async function checkTouchMap(browser, origin) {
  const context = await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true});
  const page = await context.newPage(), errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('**/*', route => route.request().url().startsWith(origin + '/') ? route.continue() : route.abort());
  try {
    await page.goto(origin); await page.getByText('Private records workspace ready.', {exact:false}).waitFor();
    await page.locator('#map svg').scrollIntoViewIfNeeded(); const rect = await page.locator('#map svg').boundingBox();
    const center = {x:rect.x + rect.width / 2,y:rect.y + rect.height / 2}, cdp = await context.newCDPSession(page);
    const touches = spread => [{id:0,x:center.x-spread,y:center.y},{id:1,x:center.x+spread,y:center.y}];
    await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:touches(25)});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:touches(55)});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    assert.ok((await view(page, '#map'))[2] < 870, 'pinch must zoom the map');
    assert.equal(await page.locator('#state-select').inputValue(),'MI', 'pinch must not select a new state');
    const controls=page.locator('#national-map-controls'); await controls.locator('summary').click();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true);
    await controls.getByRole('button',{name:'Fit whole map',exact:true}).tap();
    assert.deepEqual(await view(page, '#map'),[0,0,870,560]);
    assert.deepEqual(errors, []);
  } finally { await context.close(); }
}
