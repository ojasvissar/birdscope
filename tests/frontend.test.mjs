import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {esc,csv,seasonFor,selectProduct,color} from '../dist/lib.js';
const data=JSON.parse(fs.readFileSync('dist/data/analysis.json','utf8'));
test('winter season crosses the calendar boundary',()=>{
 assert.equal(seasonFor('2023-01-04',data.metadata.season_dates),'nonbreeding');
 assert.equal(seasonFor('2023-12-27',data.metadata.season_dates),'nonbreeding');
 assert.equal(seasonFor('2023-06-21',data.metadata.season_dates),'breeding');
});
test('custom exports reflect all selected filters',()=>{
 const rows=selectProduct(data,'north','weekly','breeding');
 assert.ok(rows.length>0&&rows.length<52);
 assert.ok(rows.every(r=>r.region==='north'&&seasonFor(r.date,data.metadata.season_dates)==='breeding'));
 assert.equal(selectProduct(data,'all','trends').length,1);
 assert.equal(selectProduct(data,'every','weekly').length,208);
});
test('CSV preserves quoted commas and newlines',()=>{
 assert.equal(csv([{name:'a,"b',value:'one\ntwo'}]),'"name","value"\r\n"a,""b","one\ntwo"\r\n');
});
test('dynamic strings are escaped and missing color differs from zero',()=>{
 assert.equal(esc('<img onerror="x">'),'&lt;img onerror=&quot;x&quot;&gt;');
 assert.notEqual(color(null,1),color(0,1));
});
test('all required static and download artifacts exist',()=>{
 for(const f of ['index.html','styles.css','app.js','data/analysis.json','data/basemap.geojson','data/regions.geojson','data/status.geojson','data/trends.geojson','downloads/conservation-brief.html','downloads/provenance.json','downloads/model-evaluation.json','downloads/weekly-regions.csv','downloads/regional-trends.csv'])assert.ok(fs.statSync('dist/'+f).size>0,f);
});
