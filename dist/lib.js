export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const fmt = (v, n=2) => v == null || !Number.isFinite(Number(v)) ? 'No data' : Number(v).toLocaleString('en-US',{maximumFractionDigits:n,minimumFractionDigits:n});
export const signed = (v,n=2) => v == null ? 'No data' : `${v>0?'+':''}${fmt(v,n)}`;
export function seasonFor(date, seasons) {
  const md = date.slice(5);
  return seasons.find(s => {const a=s.start_date.slice(5),b=s.end_date.slice(5); return a<=b ? md>=a&&md<=b : md>=a||md<=b;})?.season || 'unclassified';
}
export function csv(rows) {
  if(!rows.length) return '';
  const keys=Object.keys(rows[0]);
  const q=v=>`"${String(v??'').replace(/"/g,'""')}"`;
  return [keys.map(q).join(','),...rows.map(r=>keys.map(k=>q(r[k])).join(','))].join('\r\n')+'\r\n';
}
export function selectProduct(data, region, product, season='all') {
  if(product==='trends') return data.regional_trends.filter(r=>region==='every'||r.region===region);
  return data.weekly_summary.filter(r=>(region==='every'||r.region===region)&&
    (season==='all'||seasonFor(r.date,data.metadata.season_dates)===season));
}
export function color(v, max, diverging=false) {
  if(v==null||!Number.isFinite(v)) return '#d5dde0';
  if(diverging) {
    const t=Math.min(Math.abs(v)/max,1), a=[237,241,237], b=v<0?[184,72,49]:[0,119,119];
    return `rgb(${a.map((x,i)=>Math.round(x+(b[i]-x)*t)).join(',')})`;
  }
  const t=Math.sqrt(Math.max(0,Math.min(v/max,1)));
  const stops=[[231,244,211],[120,197,152],[33,142,119],[0,74,68]];
  const at=Math.min(Math.floor(t*3),2), f=t*3-at;
  return `rgb(${stops[at].map((x,i)=>Math.round(x+(stops[at+1][i]-x)*f)).join(',')})`;
}
