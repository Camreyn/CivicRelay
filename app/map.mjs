// Functional geography only: group the project's county polygons by state.
// Display uses a simple equirectangular view with separate AK/HI insets, not new boundaries.
// Modified for standalone refresh: data is supplied explicitly by the maintainer.
export function buildMap(data,states) {
const groups = new Map(states.map(x=>[x.code,{...x, paths:[], bounds:[Infinity,Infinity,-Infinity,-Infinity]}]));
function project(lon, lat, code) {
  if (code === 'AK') return [65 + ((lon>0?lon-360:lon)+190)*4, 438+(73-lat)*4.5];
  if (code === 'HI') return [325+(lon+179)*6, 458+(29-lat)*7];
  return [54+(lon+125)*11.5, 46+(50-lat)*13];
}
for (const feature of data.features) {
  const group = groups.get(String(feature.properties.STATE));
  if (!group || !feature.geometry) continue;
  const polygons = feature.geometry.type === 'Polygon' ? [feature.geometry.coordinates] : feature.geometry.coordinates;
  for (const polygon of polygons) {
    const parts=[];
    for (const ring of polygon) {
      const coords=ring.map(([lon,lat])=>project(lon,lat,group.code));
      for(const [x,y] of coords) {group.bounds[0]=Math.min(group.bounds[0],x);group.bounds[1]=Math.min(group.bounds[1],y);group.bounds[2]=Math.max(group.bounds[2],x);group.bounds[3]=Math.max(group.bounds[3],y);}
      parts.push(coords.map(([x,y],i)=>`${i?'L':'M'}${x.toFixed(1)},${y.toFixed(1)}`).join('')+'Z');
    }
    group.paths.push(parts.join(''));
  }
}
const callouts = ['VT','NH','MA','RI','CT','NJ','DE','MD','DC'];
const labelOverrides={HI:[465,541],FL:[560,336],MI:[518,134]};
const output = [...groups.values()].map(({code,name,paths,bounds})=>({code,name,path:paths.join(''),
  x: labelOverrides[code]?.[0] ?? (callouts.includes(code)?790:(bounds[0]+bounds[2])/2),
  y: labelOverrides[code]?.[1] ?? (callouts.includes(code)?65+callouts.indexOf(code)*31:(bounds[1]+bounds[3])/2),
  callout:callouts.includes(code), anchor:[(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2],
}));
if(output.length!==51 || output.some(x=>!x.path || !Number.isFinite(x.x))) throw Error('State geometry is incomplete');
return {source:'public/data/national-counties.geojson',states:output};
}
