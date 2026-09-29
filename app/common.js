"use strict";
// Shared by the Sectors page (index.html) and the Countries page (world.html).
// build_static.py flips this to true for the GitHub Pages copy, which reads data files
// that GitHub Actions regenerates every ~15 minutes instead of calling the local server.
const STATIC = false;
const REFRESH_MS = 5*60*1000;

/* ---------------------------------------------------------------- basics */
const makeStore = ns => ({get(k,d){try{const v=localStorage.getItem(ns+k);return v==null?d:JSON.parse(v)}catch(e){return d}},
                          set(k,v){try{localStorage.setItem(ns+k,JSON.stringify(v))}catch(e){}}});
const $ = s => document.querySelector(s);
const esc = s => String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pct = (v,dp=1,sign=true) => v==null||isNaN(v) ? "–" : (sign&&v>0?"+":"")+(v*100).toFixed(dp)+"%";
const cls = v => v==null?"":v>0?"pos":v<0?"neg":"";
function money(v,ccy){ if(v==null) return "–"; const dp = v>=1000?0:v>=100?2:v>=1?2:4;
  return v.toLocaleString(undefined,{minimumFractionDigits:dp,maximumFractionDigits:dp})+(ccy?` ${ccy}`:""); }
const CCY_SIGN={USD:"$",EUR:"€",JPY:"¥",CAD:"C$",GBP:"£"};
function bigMoney(v,ccy){ if(v==null) return "–"; const s=CCY_SIGN[ccy]??(ccy+" "), a=Math.abs(v);
  return s+(a>=1e12?(v/1e12).toFixed(2)+"T":a>=1e9?(v/1e9).toFixed(1)+"B":a>=1e6?(v/1e6).toFixed(0)+"M":Math.round(v).toLocaleString()); }
function heat(v,cap){ if(v==null) return "";
  const a = Math.min(1,Math.abs(v)/cap)*42; if(a<3) return "";
  return `background:color-mix(in oklab,var(${v>0?"--pos":"--neg"}) ${a.toFixed(0)}%,transparent)`; }
function scoreColor(s){ return s>=60?"var(--pos)":s>=40?"var(--faint)":"var(--neg)"; }
function sigClass(sig){ return {"Strong overweight":"s-so","Overweight":"s-ow","Neutral":"s-ne","Underweight":"s-uw","Avoid":"s-av"}[sig]||"s-ne"; }
function ago(ms){ const s=Math.round((Date.now()-ms)/1000); if(s<60) return "just now"; const m=Math.round(s/60); return m<60?`${m} min ago`:`${Math.round(m/60)} h ago`; }
const monthYear = ts => new Date(ts*1000).toLocaleDateString(undefined,{month:"short",year:"numeric",timeZone:"UTC"});

/* ---------------------------------------------------------------- plain-language vocabulary
   One set of words everywhere: sizes are shown without a sign and the direction is a word
   ("6.9% ahead", "3.5% behind"), and every comparison names what it is compared with. */
const near0 = v => Math.abs(v) < 0.0015;
function aheadBehind(v,dp=1){ return v==null? "–" : near0(v)? "about level" : `${pct(Math.abs(v),dp,false)} ${v>0?"ahead":"behind"}`; }
// the word that follows a value from aheadBehind(): "ahead OF x", "behind x", "about level WITH x"
const relPrep = v => v==null||near0(v)? "with " : v>0? "of " : "";
function betterWorse(v,dp=1){ return v==null? "–" : near0(v)? "about the same" : `${pct(Math.abs(v),dp,false)} ${v>0?"better":"worse"}`; }
function upDown(v,dp=1){ return v==null? "–" : near0(v)? "flat" : `${v>0?"up":"down"} ${pct(Math.abs(v),dp,false)}`; }
// what a yearly % difference means on $10,000
const per10k = (v,sign="$") => sign+(Math.round(Math.abs(v)*1000)*10).toLocaleString();
// The rotation quadrant compares the last ~2 months with its own recent norm, so the words say "lately".
const QUAD_PLAIN = {Leading:"ahead lately and pulling away", Weakening:"ahead lately but its edge is fading", Lagging:"behind lately and slipping", Improving:"behind lately but improving"};
function quadSentence(q,bench){ return {
  Leading:`over the last couple of months it has been doing better than ${bench}, and that edge is still growing.`,
  Weakening:`over the last couple of months it has been doing better than ${bench}, but that edge has started to fade. Leaders often cool off from here.`,
  Improving:`over the last couple of months it has been doing worse than ${bench}, but it has started to improve. An early turnaround candidate.`,
  Lagging:`over the last couple of months it has been doing worse than ${bench}, and it is slipping further.`}[q]||""; }
const SIGNAL_HELP = {
  "Strong overweight":"Score 80 or more: the data strongly favours holding more of this than its usual share.",
  "Overweight":"Score 60–79: the data favours holding more of this than its usual share.",
  "Neutral":"Score 40–59: no clear signal either way; a normal amount.",
  "Underweight":"Score 20–39: the data suggests holding less of this than its usual share.",
  "Avoid":"Score under 20: among the weakest; the data suggests holding little or none."};
function sigPill(sig,text=sig){ return `<span class="pill ${sigClass(sig)}" title="${esc(SIGNAL_HELP[sig]||"")}">${esc(text??"–")}</span>`; }
// trend checks passed (0-4), not trend strength
const TREND_WORD = ["downtrend","mostly down","mixed trend","mostly up","clear uptrend"];
const CCY_NAME = {USD:"US dollar",CAD:"Canadian dollar",MXN:"Mexican peso",BRL:"Brazilian real",ARS:"Argentine peso",CLP:"Chilean peso",
  GBP:"pound",EUR:"euro",CHF:"Swiss franc",SEK:"Swedish krona",NOK:"Norwegian krone",DKK:"Danish krone",PLN:"Polish zloty",TRY:"Turkish lira",
  JPY:"yen",CNY:"Chinese yuan",HKD:"Hong Kong dollar",INR:"Indian rupee",KRW:"Korean won",TWD:"Taiwan dollar",AUD:"Australian dollar",
  NZD:"New Zealand dollar",SGD:"Singapore dollar",IDR:"Indonesian rupiah",MYR:"Malaysian ringgit",THB:"Thai baht",PHP:"Philippine peso",
  VND:"Vietnamese dong",ILS:"Israeli shekel",SAR:"Saudi riyal",ZAR:"South African rand"};
const ccyName = c => CCY_NAME[c]||c;
// plural forms for sentences like "in yen" / "in Swedish kronor" (most just add an s)
const CCY_PLURAL = {JPY:"yen",KRW:"Korean won",CNY:"Chinese yuan",VND:"Vietnamese dong",THB:"Thai baht",SEK:"Swedish kronor",NOK:"Norwegian kroner",
  DKK:"Danish kroner",BRL:"Brazilian reais",TRY:"Turkish lira",IDR:"Indonesian rupiah",MYR:"Malaysian ringgit",ZAR:"South African rand",GBP:"pounds"};
const ccyPlural = c => CCY_PLURAL[c]||(CCY_NAME[c]?CCY_NAME[c]+"s":c);
// how reliable a backtest result is (from a t-statistic): one scale used everywhere
function confLabel(t){ return t==null? "–" : t>=2? "High" : t>=1? "Low" : "None"; }
const tval = t => Math.abs(t)<0.05?"0.0":t.toFixed(1);
const confText = t => t==null? "–" : `${confLabel(t)} (t = ${tval(t)})`;
const sgn = v => v==null? "–" : (Math.round(v)>0?"+":"")+Math.round(v);
function delta(v,title=""){ if(v==null) return '<span class="delta flat">–</span>';
  const c=v>=1?"up":v<=-1?"down":"flat"; return `<span class="delta ${c}" title="${esc(title)}">${sgn(v)}</span>`; }
const scoreChangeTip = m => `Score change (0–100 scale): since the previous close ${sgn(m.d1)} · this week ${sgn(m.d1w)} · over 4 weeks ${sgn(m.d1m)}`;
function flagsHTML(m){ return (m.flags||[]).map(f=>`<span class="flag f-${f.tone}" title="${esc(f.tip||"")}">${esc(f.label)}</span>`).join(""); }
function trendBars(n){ return `<span class="trend" title="${n} of 4 uptrend checks pass">${[0,1,2,3].map(j=>`<i class="${j<n?"on":""}"></i>`).join("")}</span>`; }
function partName(k,vs="the whole market"){ return {
  mom121_rel:`Past year vs ${vs} (leaving out the latest month)`, rs6m:`Last 6 months vs ${vs}`, rs3m:`Last 3 months vs ${vs}`,
  trend:"Price trend (vs its 50- and 200-day averages)", sharpe:"Past-year gain above cash, for the ups and downs (Sharpe)",
  mdd:"Biggest drop in the past year (smaller ranks higher)"}[k]||k; }
function partTip(k,vs="the whole market"){ return {
  mom121_rel:`Its return from 12 months ago to 1 month ago, compared with ${vs} over the same time. The latest month is left out because very short-term moves often reverse.`,
  rs6m:`How much better or worse it did than ${vs} over the last 6 months.`,
  rs3m:`How much better or worse it did than ${vs} over the last 3 months.`,
  trend:"Four checks (price above its 50-day and its 200-day average, the 50-day above the 200-day, the 200-day rising over the last month), plus how far the price is above or below its 200-day average.",
  sharpe:"Sharpe ratio: the past year's return minus today's US cash rate (3-month Treasury bill), divided by how much the price swung over the year. Higher = more reward for the risk taken.",
  mdd:"Its largest fall from a high point to a later low in the past 12 months, ranked across all of them: the shallower the fall, the higher the rank."}[k]||""; }

/* ---------------------------------------------------------------- svg helpers */
function sparkSVG(vals,{w=96,h=24,color}={}){
  const v = vals.filter(x=>x!=null); if(v.length<2) return "";
  const mn=Math.min(...v), mx=Math.max(...v), r=mx-mn||1;
  const P = v.map((y,i)=>[i/(v.length-1)*(w-3)+1.5, h-2-(y-mn)/r*(h-4)]);
  const d = P.map((p,i)=>(i?"L":"M")+p[0].toFixed(1)+" "+p[1].toFixed(1)).join("");
  const c = color || (v[v.length-1]>=v[0]?"var(--pos)":"var(--neg)");
  const last = P[P.length-1];
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
    <path d="${d}L${last[0]} ${h}L1.5 ${h}Z" fill="${c}" fill-opacity=".10"/>
    <path d="${d}" fill="none" stroke="${c}" stroke-width="1.4" vector-effect="non-scaling-stroke"/>
    <circle cx="${last[0]}" cy="${last[1]}" r="1.8" fill="${c}"/></svg>`;
}
function niceTicks(mn,mx,n=5){ const span=mx-mn||1, step0=span/n, mag=10**Math.floor(Math.log10(step0));
  const step=[1,2,2.5,5,10].map(s=>s*mag).find(s=>span/s<=n)||mag*10; const out=[];
  for(let v=Math.ceil(mn/step)*step; v<=mx+1e-9; v+=step) out.push(+v.toFixed(10)); return out; }

/* Line chart with hover crosshair. series: [{v:[], color, w, dash, name}] */
function lineChart(el,{t,series,h=240,fmt=v=>v.toFixed(2),baseline=null,baselineLabel="",area=0}){
  if(!el) return;
  const W = Math.max(280, el.clientWidth||600), H=h, L=8, R=58, T=10, B=24;
  const all = series.flatMap(s=>s.v).filter(v=>v!=null); if(baseline!=null) all.push(baseline);
  let mn=Math.min(...all), mx=Math.max(...all); const pad=(mx-mn)*.06||1; mn-=pad; mx+=pad;
  const X = i => L + i/(t.length-1)*(W-L-R), Y = v => T + (1-(v-mn)/(mx-mn))*(H-T-B);
  const ticks = niceTicks(mn,mx,4);
  let g = ticks.map(v=>`<line x1="${L}" x2="${W-R}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)" stroke-width="1"/>
    <text x="${W-R+6}" y="${Y(v)+4}" font-size="11" fill="var(--muted)" font-family="var(--mono)">${fmt(v)}</text>`).join("");
  const span = (t[t.length-1]-t[0])/86400, years = span>800, short = span<150;
  const seen=new Set(); let xl="";
  t.forEach((ts,i)=>{ const d=new Date(ts*1000); const key = years? d.getFullYear() : short? d.getFullYear()+"-"+d.getMonth()+"-"+(d.getDate()<15) : d.getFullYear()+"-"+d.getMonth();
    if(!seen.has(key)){ seen.add(key); if(i<2) return;
      if(years && span>2500 && d.getFullYear()%2) return;
      if(!years && !short && d.getMonth()%2) return;
      if(short && d.getDate()>=15) return;
      const lab = years? d.getFullYear() : d.toLocaleString(undefined,{month:"short"});
      xl+=`<text x="${X(i)}" y="${H-6}" font-size="11" fill="var(--muted)" text-anchor="middle">${lab}</text>`; }});
  if(baseline!=null) g+=`<line x1="${L}" x2="${W-R}" y1="${Y(baseline)}" y2="${Y(baseline)}" stroke="var(--faint)" stroke-dasharray="3 3"/>`+
    (baselineLabel?`<text x="${L+4}" y="${Y(baseline)-5}" font-size="11" fill="var(--muted)">${esc(baselineLabel)}</text>`:"");
  const paths = series.map((s,si)=>{ let d="",on=false;
    s.v.forEach((v,i)=>{ if(v==null){on=false;return;} d+=(on?"L":"M")+X(i).toFixed(1)+" "+Y(v).toFixed(1); on=true; });
    const fill = (si===0&&area) ? `<path d="${d}L${X(s.v.length-1)} ${H-B}L${X(s.v.findIndex(v=>v!=null))} ${H-B}Z" fill="${s.color}" fill-opacity=".08"/>` : "";
    return fill+`<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${s.w||1.6}" ${s.dash?`stroke-dasharray="${s.dash}"`:""} stroke-linejoin="round"/>`; }).join("");
  const s0=series[0].v, li=s0.length-1;
  const end = s0[li]==null? "" : `<circle cx="${X(li)}" cy="${Y(s0[li])}" r="3.5" fill="${series[0].color}"/>
    <rect x="${W-R+2}" y="${Y(s0[li])-9}" width="${R-4}" height="18" rx="4" fill="${series[0].color}"/>
    <text x="${W-R+6}" y="${Y(s0[li])+4}" font-size="11" fill="var(--surface)" font-family="var(--mono)">${fmt(s0[li])}</text>`;
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img">${g}${xl}${paths}${end}
    <line class="xh" x1="0" x2="0" y1="${T}" y2="${H-B}" stroke="var(--muted)" stroke-width="1" visibility="hidden"/>
    <rect x="${L}" y="${T}" width="${W-L-R}" height="${H-T-B}" fill="transparent"/></svg>`;
  const svg=el.querySelector("svg"), xh=svg.querySelector(".xh"), tip=$("#tip");
  svg.addEventListener("mousemove",e=>{ const r=svg.getBoundingClientRect(); const x=(e.clientX-r.left)*(W/r.width);
    const i=Math.max(0,Math.min(li,Math.round((x-L)/(W-L-R)*li))); xh.setAttribute("x1",X(i)); xh.setAttribute("x2",X(i)); xh.setAttribute("visibility","visible");
    const d=new Date(t[i]*1000).toLocaleDateString(undefined,{day:"numeric",month:"short",year:"numeric"});
    tip.innerHTML = esc(d)+"  "+series.map(s=>s.v[i]==null?"":`<span style="color:${s.color==="var(--ink)"?"inherit":s.color}">${esc(s.name)} ${esc(fmt(s.v[i]))}</span>`).join("  ");
    showTip(e); });
  svg.addEventListener("mouseleave",()=>{xh.setAttribute("visibility","hidden");$("#tip").hidden=true;});
}
function showTip(e){ const tip=$("#tip"); tip.hidden=false;
  tip.style.left=Math.min(e.clientX+14,innerWidth-tip.offsetWidth-8)+"px"; tip.style.top=(e.clientY-34)+"px"; }

/* Diverging horizontal bars: items [{label, v, sub}] */
function barsSVG(items,{fmt=v=>pct(v,1)}={}){
  const W=560, rowH=30, L=150, R=70, H=items.length*rowH+8;
  const mx=Math.max(0.001,...items.map(x=>Math.abs(x.v??0))), zero=L+(W-L-R)/2, scale=(W-L-R)/2/mx;
  const rows=items.map((x,i)=>{ const y=4+i*rowH, v=x.v??0, w=Math.abs(v)*scale, x0=v>=0?zero:zero-w;
    return `<text x="0" y="${y+18}" font-size="12.5" fill="var(--ink)">${esc(x.label)}</text>
      ${x.sub?`<text x="${L-8}" y="${y+18}" font-size="11" fill="var(--faint)" text-anchor="end">${esc(x.sub)}</text>`:""}
      <rect x="${x0}" y="${y+6}" width="${Math.max(1,w)}" height="16" rx="3" fill="${v>=0?"var(--pos)":"var(--neg)"}" fill-opacity=".85"/>
      <text x="${v>=0?x0+w+6:x0-6}" y="${y+18}" font-size="12" font-family="var(--mono)" fill="var(--ink)" text-anchor="${v>=0?"start":"end"}">${esc(x.v==null?"–":fmt(x.v))}</text>`; }).join("");
  return `<svg viewBox="0 0 ${W} ${H}" role="img"><line x1="${zero}" x2="${zero}" y1="0" y2="${H}" stroke="var(--line)"/>${rows}</svg>`;
}

/* Relative rotation graph. items: [{key, label, title, rrg:[[x,y]...], quad}]; vs = short name of what they're compared with */
function rrgChart(el,items,onOpen,{vs="the market"}={}){
  const W=Math.max(300,el.clientWidth||520), H=Math.round(Math.min(W*0.85,520)), P=34;
  const all=items.flatMap(r=>r.rrg); if(!all.length){el.innerHTML='<p class="muted">Not enough history.</p>';return;}
  const ext=a=>Math.max(...a.map(v=>Math.abs(v-100)))*1.12||2;
  const ex=ext(all.map(p=>p[0])), ey=ext(all.map(p=>p[1]));
  const X=v=>P+(v-100+ex)/(2*ex)*(W-2*P), Y=v=>H-P-(v-100+ey)/(2*ey)*(H-2*P);
  const qcol={Leading:"var(--pos)",Weakening:"var(--warn)",Lagging:"var(--neg)",Improving:"var(--info)"};
  const cx=X(100), cy=Y(100);
  const corner=(x,y,anchor,colour,name,sub,below)=>`<text x="${x}" y="${y}" text-anchor="${anchor}" font-size="12" font-weight="600" fill="${colour}">${name}</text>
    <text x="${x}" y="${below?y+13:y-14}" text-anchor="${anchor}" font-size="10.5" fill="${colour}" fill-opacity=".85">${sub}</text>`;
  let s=`<rect x="${cx}" y="${P}" width="${W-P-cx}" height="${cy-P}" fill="var(--pos)" fill-opacity=".06"/>
    <rect x="${cx}" y="${cy}" width="${W-P-cx}" height="${H-P-cy}" fill="var(--warn)" fill-opacity=".06"/>
    <rect x="${P}" y="${cy}" width="${cx-P}" height="${H-P-cy}" fill="var(--neg)" fill-opacity=".06"/>
    <rect x="${P}" y="${P}" width="${cx-P}" height="${cy-P}" fill="var(--info)" fill-opacity=".06"/>
    <line x1="${P}" x2="${W-P}" y1="${cy}" y2="${cy}" stroke="var(--line)"/><line x1="${cx}" x2="${cx}" y1="${P}" y2="${H-P}" stroke="var(--line)"/>
    ${corner(W-P-6,P+16,"end","var(--pos)","LEADING","ahead, pulling away",true)}
    ${corner(W-P-6,H-P-8,"end","var(--warn)","WEAKENING","ahead, losing ground",false)}
    ${corner(P+6,H-P-8,"start","var(--neg)","LAGGING","behind, slipping",false)}
    ${corner(P+6,P+16,"start","var(--info)","IMPROVING","behind, catching up",true)}
    <text x="${W/2}" y="${H-8}" text-anchor="middle" font-size="11" fill="var(--muted)">Doing better than ${esc(vs)} →</text>
    <text x="12" y="${H/2}" text-anchor="middle" font-size="11" fill="var(--muted)" transform="rotate(-90 12 ${H/2})">Gaining ground →</text>`;
  const labels=[];
  items.forEach(r=>{ const tl=r.rrg, c=qcol[r.quad]||"var(--muted)", last=tl[tl.length-1];
    s+=`<polyline points="${tl.map(p=>X(p[0]).toFixed(1)+","+Y(p[1]).toFixed(1)).join(" ")}" fill="none" stroke="${c}" stroke-opacity=".45" stroke-width="1.4"/>`;
    tl.slice(0,-1).forEach(p=>s+=`<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="1.8" fill="${c}" fill-opacity=".45"/>`);
    s+=`<circle cx="${X(last[0])}" cy="${Y(last[1])}" r="5" fill="${c}" stroke="var(--surface)" stroke-width="1.5" data-open="${esc(r.key)}" style="cursor:pointer"><title>${esc(r.title||r.label)}: ${esc(r.quad)}, ${esc(QUAD_PLAIN[r.quad]||"")} vs ${esc(vs)}</title></circle>`;
    labels.push({x:X(last[0]),y:Y(last[1]),t:r.label.length>18?r.label.slice(0,17)+"…":r.label,key:r.key});
  });
  labels.sort((a,b)=>a.y-b.y); const placed=[];
  labels.forEach(l=>{ let y=l.y-8; while(placed.some(p=>Math.abs(p.y-y)<12&&Math.abs(p.x-l.x)<(l.t.length*6.5+10))) y+=12; placed.push({x:l.x,y});
    const right=l.x>W-130; s+=`<text x="${l.x+(right?-8:8)}" y="${y}" text-anchor="${right?"end":"start"}" font-size="11.5" fill="var(--ink)" data-open="${esc(l.key)}" style="cursor:pointer">${esc(l.t)}</text>`; });
  el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Rotation map">${s}</svg>`;
  el.querySelectorAll("[data-open]").forEach(n=>n.addEventListener("click",()=>onOpen(n.dataset.open)));
}

/* ---------------------------------------------------------------- shared verdict + cards */
function verdict(m,bench="its region's whole market"){
  // Built fresh from the latest data on every refresh; each clause only appears when the numbers support it.
  const s=m.score??50, over=m.rsi!=null&&m.rsi>=70, stretched=m.vs200!=null&&m.vs200>.15;
  const below200=m.vs200!=null&&m.vs200<0, gap=below200?` It is ${pct(-m.vs200,1,false)} below that line today.`:"";
  if(s>=60){
    const base = m.quad==="Weakening" ? `A high score, but over the last couple of months its edge over ${bench} has started to fade. Fine to keep; be choosy about adding more.`
      : `A high score: it ranks well on performance against ${bench}, price trend and risk. The data supports holding more of it than usual.`;
    if(!over&&!stretched) return base;
    const why=[over?`RSI ${m.rsi.toFixed(0)}, where 70 or more means a sharp run-up`:"", stretched?`price ${pct(m.vs200,0,false)} above its 200-day average`:""].filter(Boolean).join("; ");
    return `${base} It has also risen very fast (${why}), so consider buying after a dip rather than right now.`;
  }
  if(m.quad==="Improving"){
    if(s>=40) return `It has been doing worse than ${bench}, but over the last couple of months it has started to improve. Worth watching.`;
    return below200 ? `Starting to improve against ${bench} lately, but its own price trend is still weak. Wait until it ends a day above its 200-day (about 10-month) average price.${gap}`
                    : `Starting to improve against ${bench} lately and already back above its 200-day average price, but the score is still low. Watch whether the improvement lasts before committing.`;
  }
  if(s<40) return `A low score: it ranks poorly on performance against ${bench}, price trend and risk. The data suggests holding less of it than usual, or none, until that changes.`+
                  (below200?` The first sign of recovery would be a day ending above its 200-day (about 10-month) average price.${gap}`:"");
  return "No clear signal either way. A normal-sized holding is reasonable.";
}
function historyText(m,prefix=true){
  const bits=[["since the previous close",m.d1],["this week",m.d1w],["over 4 weeks",m.d1m]].filter(([,v])=>v!=null)
    .map(([w,v])=>`${Math.abs(v)<1?"little changed":(v>0?"up ":"down ")+Math.round(Math.abs(v))} ${w}`);
  return bits.length? (prefix?"Score ":"")+bits.join(", ")+"." : "";
}
function scoreHistoryCard(noun="funds"){ return `<div class="card chartbox"><div class="row"><span class="eyebrow">Score over the last 3 months</span>
  <span class="muted" style="font-size:12.5px" id="histtxt"></span></div><div id="hchart"></div>
  <p class="note">Each point is the score as it stood that week. Scores rank ${esc(noun)} against each other, so this one can move when others move, even if its own price doesn't. Dashed line = 50, the middle.</p></div>`; }
function drawScoreHistory(m,cuts){
  $("#histtxt").textContent=historyText(m)+" (out of 100)";
  lineChart($("#hchart"),{t:cuts,series:[{v:m.hist,color:scoreColor(m.score),name:"Score",w:2}],h:150,baseline:50,fmt:v=>v.toFixed(0)});
}
function holdingsCard(r,holdingsAt,what="the fund"){
  const h=r.holdings; if(!h||!h.length) return `<div class="card" style="padding:16px"><div class="eyebrow">Top 10 holdings</div><p class="muted" style="margin:6px 0 0">The fund provider hasn't published holdings for this fund.</p></div>`;
  const max=h[0].pct||1, tot=r.m.top10;
  const read = tot>=0.6?"Highly concentrated: a few companies drive most of the return."
             : tot>=0.35?"Fairly concentrated: a handful of companies have a big effect." : "Well spread: no single company dominates.";
  const asOf = holdingsAt? new Date(holdingsAt*1000).toLocaleDateString(undefined,{day:"numeric",month:"short"}) : "";
  return `<div class="card" style="padding:16px"><div class="row" style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:8px">
      <span class="eyebrow">Top 10 holdings</span><span class="muted" style="font-size:12.5px">Together ${pct(tot,1,false)} of ${esc(what)} · ${esc(read)}</span></div>
    <div class="holds">${h.map((x,i)=>`<span class="hr">${i+1}</span>
      <span class="hn">${esc(x.name)} <a href="https://finance.yahoo.com/quote/${encodeURIComponent(x.sym)}" target="_blank" rel="noopener">${esc(x.sym)}</a></span>
      <span class="bar"><i style="width:${x.pct/max*100}%;background:var(--accent)"></i></span><span class="num">${pct(x.pct,1,false)}</span>`).join("")}</div>
    <p class="muted" style="font-size:12px;margin:10px 0 0">Each company's share of the fund, as published by the fund provider${asOf?` (checked ${esc(asOf)})`:""}. Click a code to see the company on Yahoo Finance.</p></div>`;
}
/* bn = plain label for the comparison, e.g. "Whole US market (S&P 500)" or "World stocks" */
function factsCard(f,{ccy="USD",bf={},bn="",title="Fund facts",note="From Yahoo Finance, checked daily."}={}){
  const cheaper=(v,bv)=>{ const d=v/bv-1; return Math.abs(d)<0.05?"about the same":`${Math.round(Math.abs(d)*100)}% ${d>0?"pricier":"cheaper"}`; };
  const pays=(v,bv)=>{ const d=v/bv-1; return Math.abs(d)<0.05?"about the same":d>0?"pays more":"pays less"; };
  const beta = f.beta==null? "" : f.beta>1.15||f.beta<0.85? `Has tended to move about ${f.beta.toFixed(1)}× as much as its reference market` : "Has tended to move roughly in step with its reference market";
  const sign = CCY_SIGN[ccy]||"$";
  return `<div class="card" style="padding:16px"><div class="eyebrow" style="margin-bottom:10px">${esc(title)}</div>
    <div class="facts">
      <div><span>Fund size</span><b>${bigMoney(f.aumUsd,"USD")}</b><small>${f.aum!=null&&ccy!=="USD"?`${bigMoney(f.aum,ccy)} in the fund's own currency`:"Money invested in the fund"}</small></div>
      <div title="Share price divided by the last 12 months' profit per share, across the companies held. Lower = cheaper."><span>Price vs profits (P/E)</span><b>${f.pe==null?"–":f.pe.toFixed(1)}</b>
        <small>${f.pe!=null&&bf.pe?`${esc(bn)}: ${bf.pe.toFixed(1)} · ${cheaper(f.pe,bf.pe)}`:"Share price ÷ last year's profits"}</small></div>
      <div title="Cash dividends paid over the last 12 months, as a % of today's price."><span>Dividend yield</span><b>${pct(f.yld,2,false)}</b>
        <small>${f.yld!=null&&bf.yld?`${esc(bn)}: ${pct(bf.yld,2,false)} · ${pays(f.yld,bf.yld)}`:"Dividends over the last 12 months"}</small></div>
      <div title="Yahoo's beta figure (shown there as 'Beta (5Y Monthly)'): how much the fund has tended to move when its reference market moves. 1 = in step; above 1 = bigger moves. Not the same as how bumpy it is overall."><span>Market sensitivity (beta)</span><b>${f.beta==null?"–":f.beta.toFixed(2)}</b><small>${esc(beta)}</small></div>
      <div><span>Yearly fee</span><b>${pct(f.fee,2,false)}</b><small>${f.fee==null?"Not published":`${sign}${Math.round(f.fee*10000).toLocaleString()} a year per ${sign}10,000 invested`}</small></div>
    </div>
    <p class="muted" style="font-size:12px;margin:10px 0 0">${esc(note)}</p></div>`;
}

/* ---------------------------------------------------------------- backtest ("track record") */
function btStrength(bt){
  const t=bt.spreadT??0;
  // bands describe how RELIABLE the result is (month-to-month consistency), not how big the gap is
  return t>=2? {cls:"good",label:"Probably helped",word:"an advantage that is unlikely to be pure luck"}
       : t>=1? {cls:"weak",label:"Possibly helped",word:"a possible advantage, but the results swung so much from month to month that it could still be luck"}
       : t>-1? {cls:"none",label:"Didn't help",word:"no reliable advantage"}
       :       {cls:"none",label:"Backfired",word:"a result pointing the wrong way, with lower scores doing better"};
}
function btAdvice(bt,noun){
  const t=bt.spreadT??0;
  if(t>=2) return "The score has been a useful guide on average, but it is still wrong in many months.";
  if(t>=1) return "Use the score as a gentle nudge, not a forecast: it has helped on average but is often wrong in any given month.";
  return `For picking ${noun}, the score did not help in this test. Use it to describe trends and risk, and lean more on other evidence${noun==="countries"?" such as valuation, currency and today's conditions":""}.`;
}
// "beat X by 1.6% a year on average" / "trailed X by 3.5% a year on average" / "roughly matched X"
// base=true gives the form used after "went on to" ("trail", "roughly match")
function beatTrail(v,what,base=false){ return near0(v)? `roughly ${base?"match":"matched"} ${what}` : `${v>0?"beat":base?"trail":"trailed"} ${what} by ${pct(Math.abs(v),1,false)} a year on average`; }
const extra10k = v => `about ${per10k(v)} a year ${v>0?"more":"less"} than just holding it, per $10,000`;
function btSummaryLine(bt,{noun,vs}){
  if(!bt) return "";
  return `<p class="summary-line"><b>Tested on the past (${esc(monthYear(bt.from))}–${esc(monthYear(bt.to))}):</b> each month, the 20% of ${esc(noun)} with the highest scores went on to ${esc(beatTrail(bt.topAnn,vs,true))}; the lowest-scored 20% ${esc(beatTrail(bt.botAnn,"it"))}. That is ${esc(btStrength(bt).word)}. <a href="#track">See the full test</a>.</p>`;
}
/* noun: what is scored ("funds"/"countries"); one: singular; vs: long comparison; vsShort: for tight labels;
   vsList: optional sentence listing each region's comparison */
function backtestSection(bt,{noun,one,vs,vsShort,vsList=""}){
  if(!bt) return `<section id="track"><div class="sec-head"><div class="grow"><div class="eyebrow">Testing the score on the past</div><h2>Has the score worked?</h2>
    <p>There isn't enough price history yet to check how the score would have done.</p></div></div></section>`;
  const st=btStrength(bt), years=Math.round((bt.to-bt.from)/31557600), group=Math.max(1,Math.round(bt.avgFunds/5));
  const b=bt.bands, order=["Strong overweight","Overweight","Neutral","Underweight","Avoid"];
  const vals=order.map(k=>b[k]&&b[k].ann), ordered=vals.every((v,i)=>i===0||v==null||vals[i-1]==null||vals[i-1]>=v-0.005);
  const won=Math.round(bt.hit*bt.months), wonRecent=Math.round(bt.recentHit*12);
  // are the top group's winning months bigger than its losing months? (checked from the data, not assumed)
  const sp=(bt.spreadByMonth||[]).map(x=>x[1]), wins=sp.filter(v=>v>0), losses=sp.filter(v=>v<0);
  const avgWin=wins.length?wins.reduce((a,v)=>a+v,0)/wins.length:0, avgLoss=losses.length?-losses.reduce((a,v)=>a+v,0)/losses.length:0;
  const size = avgWin>avgLoss*1.1? ", and its good months were bigger than its bad ones" : avgLoss>avgWin*1.1? ", but its bad months were bigger than its good ones" : "";
  const gapSentence = near0(bt.spreadAnn)? "So the top and bottom groups ended up roughly level."
    : bt.spreadAnn>0? `So the top group did about ${pct(bt.spreadAnn,1,false)} a year better than the bottom group, on average.`
    : `In fact the bottom group did about ${pct(-bt.spreadAnn,1,false)} a year better than the top group, on average.`;
  const text = `Each month we re-sorted the ${noun} into five equal groups by score (about ${group} in each). Over ${years} years (${monthYear(bt.from)} to ${monthYear(bt.to)}), `+
    `the top-scored group went on to ${beatTrail(bt.topAnn,vs,true)}${near0(bt.topAnn)?"":` (${extra10k(bt.topAnn)})`}, `+
    `while the lowest-scored group ${beatTrail(bt.botAnn,"it")}. ${gapSentence} `+
    `That is ${st.word}: our reliability check (a t-statistic, which compares the average gap with how much it wobbled month to month) came out at ${bt.spreadT==null?"–":tval(bt.spreadT)}, and 2 or more would be convincing. `+
    `The top group beat the bottom group in ${won} of ${bt.months} months${size}. `+
    `${ordered?"Higher ratings were generally followed by better results, from Strong overweight at the top to Avoid at the bottom.":"The ratings did not line up: a higher rating was not reliably followed by a better result."} ${btAdvice(bt,noun)}`;
  const kpi=(l,v,s,c="",tip="")=>`<div class="kpi" title="${esc(tip)}"><span>${l}</span><b class="${c}">${v}</b><small>${s}</small></div>`;
  const effect=t=>t==null?["eff-none","–"]:t>=2?["eff-help","Helped (reliable)"]:t>=1?["eff-help","Possibly helped"]:t<=-2?["eff-hurt","Hurt (reliable)"]:t<=-1?["eff-hurt","Possibly hurt"]:["eff-none","No clear effect"];
  const comp=Object.entries(bt.components).map(([k,v])=>{ const e=effect(v.t);
    return `<tr><td title="${esc(partTip(k,vsShort))}">${esc(partName(k,vsShort))}</td><td>${Math.round((engineWeights[k]||0)*100)}%</td><td class="${e[0]}">${e[1]}</td><td>${confText(v.t)}</td></tr>`; }).join("");
  const c=bt.curves, end=k=>Math.round(c[k][c[k].length-1]*100);
  const worst=bt.worstMonth, strongHit=b["Strong overweight"]&&b["Strong overweight"].hit;
  return `<section id="track">
    <div class="sec-head"><div class="grow"><div class="eyebrow" title="Often called a 'backtest': replaying the past to see how the score's picks would have done">Testing the score on the past · ${bt.months} months (about ${years} years) · about ${Math.round(bt.avgFunds)} ${esc(noun)} each month</div><h2>Has the score worked?</h2>
      <p>We replayed the past. At the end of every month since ${esc(monthYear(bt.from))}, we scored every one of the ${esc(noun)} using only the prices known at the time, with the same recipe as today. Then we checked whether each did better or worse over the next month than ${esc(vs)}${vsList?`: ${esc(vsList)}`:""}. This is a simulation, not a record of real trades.</p></div></div>
    <div class="bt-grid">
      <div class="card bt-verdict"><span class="badge ${st.cls}">${st.label}</span><div>${esc(text)}</div></div>
      <div class="kpis">
        ${kpi("Top-scored 20%, per year",aheadBehind(bt.topAnn),`${relPrep(bt.topAnn)}${esc(vsShort)}, on average${near0(bt.topAnn)?"":` · ${extra10k(bt.topAnn)}`}`,cls(bt.topAnn),"Average monthly result × 12, compared with the market it was measured against")}
        ${kpi("Lowest-scored 20%, per year",aheadBehind(bt.botAnn),`${relPrep(bt.botAnn)}${esc(vsShort)}, on average${near0(bt.botAnn)?"":` · ${extra10k(bt.botAnn)}`}`,cls(bt.botAnn),"Average monthly result × 12, compared with the market it was measured against")}
        ${kpi("Top group vs lowest group, per year",betterWorse(bt.spreadAnn),`on average. Reliability: ${confText(bt.spreadT)}; 2 or more means unlikely to be luck.`,cls(bt.spreadAnn),"The reliability check is a t-statistic: how big the average gap is compared with its month-to-month wobble.")}
        ${kpi("Months the top group beat the lowest group",`${won} of ${bt.months}`,"A coin toss would win about half the months.")}
        ${kpi("Last 12 months, top vs lowest group",betterWorse(bt.recentSpreadAnn),`in total. The top group beat the lowest group in ${wonRecent} of 12 months. One year is too short to judge.`,cls(bt.recentSpreadAnn))}
        ${kpi("Swapped each month",pct(bt.turnover,0,false),`of the top group changes each month (about ${Math.round(bt.turnover*group)} of ${group}). Real trading costs would eat into any gain; they aren't included.`)}
      </div>
      ${strictChecks(bt,vsShort)}
      <div class="two">
        <div class="card chartbox"><div class="row"><span class="eyebrow">Top vs lowest group, relative to the market (100 = level with it)</span></div>
          <div class="row"><span class="key"><i style="background:var(--pos)"></i>Top-scored 20%</span><span class="key"><i style="background:var(--faint)"></i>All ${esc(noun)} (average)</span><span class="key"><i style="background:var(--neg)"></i>Lowest-scored 20%</span></div>
          <div id="btchart"></div><p class="note">These lines track performance compared with ${esc(vs)}, not the value of an investment (which also rose and fell with the market). Each group's monthly result against the market is compounded, starting from 100. By ${esc(monthYear(bt.to))} the top group was at ${end("top")} (${aheadBehind(end("top")/100-1,0)} ${relPrep(end("top")/100-1)}the market over the whole period), the lowest group at ${end("bot")}, and the average of all ${esc(noun)} at ${end("mid")}${end("mid")<100?", so the typical one lagged the market over this period":""}. Groups re-picked every month; no trading costs or taxes.</p></div>
        <div class="card panel"><div class="eyebrow" style="margin-bottom:8px">How each rating did next (per year, vs ${esc(vsShort)})</div>
          <div class="bars">${barsSVG(order.map(k=>({label:k,v:b[k].ann,sub:`${b[k].n.toLocaleString()} cases`})),{fmt:v=>Math.abs(v)<0.0005?"0.0%":pct(v,1)})}</div>
          <p class="note">Every time a ${esc(one)} had that rating, we measured how it did over the next month compared with ${esc(vs)}, then scaled the average up to a yearly rate (monthly average × 12). + = ahead, − = behind.${strongHit!=null?` Even "Strong overweight" ${esc(noun)} were ahead in only ${pct(strongHit,0,false)} of those cases.`:""}</p></div>
      </div>
      <div class="card panel"><div class="eyebrow" style="margin-bottom:6px">Which parts of the score helped?</div>
        <div style="overflow-x:auto"><table class="comp"><thead><tr><th>Part of the score</th><th>Share of score</th><th>Effect on the next month</th><th title="A t-statistic: how sure we can be the effect isn't luck">Reliability</th></tr></thead><tbody>${comp}</tbody></table></div>
        <p class="note">Reliability (t): under 1 = no sign of an effect, 1–2 = weak, 2 or more = convincing. We fixed these shares before running the test and did not adjust them to fit the results: tuning them to the past would make this test look better without making the score any better at predicting the future.</p></div>
      <div class="card panel"><div class="eyebrow" style="margin-bottom:6px">Read this test with care</div><ul class="caveats">
        <li>We picked these ${esc(noun)} in 2026, with hindsight: any that closed along the way are missing, and popular themes were chosen knowing they survived. That can make the results look different from what someone would really have experienced.</li>
        <li>The test swaps holdings every month for free: no trading fees, no gap between buying and selling prices, and no tax. With ${pct(bt.turnover,0,false)} of the top group changing each month, real costs would eat into any gain.</li>
        <li>${bt.months} months (about ${years} years) is not long for a test like this, and one unusual year (such as 2020) can sway the average.</li>
        <li>Worst single month (${esc(monthYear(worst.t+86400))}): the top group did ${pct(Math.abs(worst.spread),1,false)} ${worst.spread<0?"worse":"better"} than the lowest group.</li>
        <li>Holding longer: over the following 3 months the top group ${near0(bt.fwd3)?"roughly matched":bt.fwd3>0?"beat":"trailed"} the lowest group${near0(bt.fwd3)?"":` by ${pct(Math.abs(bt.fwd3),1,false)}`} on average, and over the following 6 months it ${near0(bt.fwd6)?"roughly matched it":`${bt.fwd6>0?"beat":"trailed"} it by ${pct(Math.abs(bt.fwd6),1,false)}`} on average (totals, not yearly rates).</li>
        <li>Past results do not guarantee future ones, especially once many investors start following the same pattern.</li></ul></div>
    </div></section>`;
}
function strictChecks(bt,vsShort){
  const hs=(bt.halves||[]).filter(Boolean); if(!hs.length) return "";
  const row=(label,h,from,to)=>`<tr><td>${label}<br><small class="muted">${esc(monthYear(from))} – ${esc(monthYear(to))}</small></td>
    <td class="${cls(h.topAnn)}">${aheadBehind(h.topAnn)}</td><td class="${cls(h.botAnn)}">${aheadBehind(h.botAnn)}</td>
    <td class="${cls(h.spreadAnn)}">${betterWorse(h.spreadAnn)}</td><td>${confText(h.spreadT)}</td><td>${Math.round(h.hit*h.months)} of ${h.months}</td></tr>`;
  const both = hs.length===2 && hs.every(h=>h.spreadAnn>0), weaker = hs.length===2 && hs[1].spreadAnn < hs[0].spreadAnn/2;
  return `<div class="card panel"><div class="eyebrow" style="margin-bottom:6px">Stricter checks</div>
    <div style="overflow-x:auto"><table class="comp"><thead><tr><th>Period</th><th>Top-scored 20%, per year</th><th>Lowest-scored 20%, per year</th><th>Top vs lowest</th><th>Reliability</th><th>Months top won</th></tr></thead><tbody>
      ${hs[0]?row("First half",hs[0],hs[0].from,hs[0].to+86400):""}${hs[1]?row("Second half",hs[1],hs[1].from,hs[1].to+86400):""}
      ${row("Whole period",bt,bt.from,bt.to)}</tbody></table></div>
    <p class="note">${both?`The top group did better than the lowest group in both halves${weaker?", but the gap shrank a lot in the more recent half":""}.`:"The result did not hold up in both halves, which is a warning sign that it may be luck."}
      After estimated trading costs (${pct(bt.costPerTrade,2,false)} per trade, about ${pct(bt.costAnn,1,false)} a year at this level of swapping), the top-scored group was ${aheadBehind(bt.topNetAnn)} ${relPrep(bt.topNetAnn)}${esc(vsShort)} a year on average.
      Any future change to the score's recipe has to beat the current one on the first half and then again on the second half, which it never saw, before it is adopted.</p></div>`;
}
let engineWeights = {};
function drawBacktest(bt){
  if(!bt||!$("#btchart")) return;
  const c=bt.curves;
  lineChart($("#btchart"),{t:c.t,series:[{v:c.top.map(v=>v*100),color:"var(--pos)",name:"Top 20%",w:2},{v:c.mid.map(v=>v*100),color:"var(--faint)",name:"All (average)",w:1.4},{v:c.bot.map(v=>v*100),color:"var(--neg)",name:"Lowest 20%",w:2}],
    h:230,baseline:100,baselineLabel:"100 = level with the market",fmt:v=>v.toFixed(0)});
}

/* ---------------------------------------------------------------- practice portfolios (live test) */
const CUR = {gbp:{sign:"£",word:"pounds"}, usd:{sign:"$",word:"US dollars"}};
const moneyIn = (v,cur) => v==null? "–" : CUR[cur].sign+Math.round(v).toLocaleString();
const lastVal = a => { for(let i=(a||[]).length-1;i>=0;i--) if(a[i]!=null) return a[i]; return null; };
/* nameOf(key) -> display name; mkt: short name for "the picks' own markets" (null when that's just world stocks) */
function paperSection(p,{noun,nameOf,mkt,cur="gbp"}){
  if(!p) return `<section id="paper"><div class="sec-head"><div class="grow"><div class="eyebrow">Live test</div><h2>Practice portfolios</h2>
    <p>The practice portfolios start with the first daily snapshot. Check back tomorrow.</p></div></div></section>`;
  const L=p[cur], v=g=>lastVal(L[g]), start=10000, days=p.t.length, chg=g=>v(g)==null?null:v(g)/start-1;
  const kpi=(l,g,sub)=>`<div class="kpi"><span>${l}</span><b class="${cls(chg(g))}">${moneyIn(v(g),cur)}</b><small>${esc(upDown(chg(g)))} since ${esc(p.started)}${sub?` · ${sub}`:""}</small></div>`;
  const list=(rows,title)=>`<div class="card panel"><div class="eyebrow" style="margin-bottom:4px">${title}</div>
    ${rows.map(h=>`<div class="idea" data-open="${esc(h.key)}" role="button" tabindex="0"><span class="nm">${esc(nameOf(h.key))}</span><span class="sc ${cls(h.sinceGbp)}">${pct(h.sinceGbp,1)}</span></div>`).join("")}
    <p class="note">Change in pounds since the latest monthly picks (${esc(p.rebalances[p.rebalances.length-1].date)}).</p></div>`;
  return `<section id="paper">
    <div class="sec-head"><div class="grow"><div class="eyebrow">Live test · started ${esc(p.started)} · day ${days}</div><h2>Practice portfolios</h2>
      <p>A test on past data can be tuned until it looks good; this can't. At the start of each month we save the 20% of ${esc(noun)} with the highest scores and the 20% with the lowest, then track what ${CUR[cur].sign}10,000 in each would do. No real money is involved; trading costs (${pct(p.costPerTrade,2,false)} per trade) are included. Next picks: ${esc(p.nextRebalance)}.</p></div>
      <span class="seg" role="group" aria-label="Portfolio currency" style="margin-left:0"><button type="button" data-pcur="gbp" aria-pressed="${cur==="gbp"}">£</button><button type="button" data-pcur="usd" aria-pressed="${cur==="usd"}">$</button></span></div>
    <div class="bt-grid">
      <div class="kpis">
        ${kpi("Top-scored portfolio","top")}
        ${kpi("Lowest-scored portfolio","bottom","for comparison")}
        ${mkt?kpi("Same money in the picks' own markets","mkt",esc(mkt)):""}
        ${kpi("World stocks (MSCI ACWI)","world","a simple benchmark")}
      </div>
      <div class="card chartbox"><div class="row"><span class="eyebrow">Value of ${CUR[cur].sign}10,000 since ${esc(p.started)} (in ${CUR[cur].word})</span></div>
        <div class="row"><span class="key"><i style="background:var(--pos)"></i>Top-scored</span><span class="key"><i style="background:var(--neg)"></i>Lowest-scored</span>${mkt?`<span class="key"><i style="background:var(--accent)"></i>Picks' own markets</span>`:""}<span class="key"><i style="background:var(--faint)"></i>World stocks</span></div>
        <div id="paperchart"></div>
        <p class="note">Early days: a few weeks tells you almost nothing, because short-term moves are mostly noise. Judge it after 6–12 months.</p></div>
      <div class="two">${list(p.holdings,`Top-scored holdings (${p.holdings.length})`)}${list(p.bottomHoldings||[],`Lowest-scored holdings (${(p.bottomHoldings||[]).length})`)}</div>
      <details class="card panel"><summary class="eyebrow" style="cursor:pointer">Every monthly pick so far (${p.rebalances.length})</summary>
        ${p.rebalances.slice().reverse().map(r=>`<p style="font-size:13.5px;margin:10px 0 0"><b>${esc(r.date)}</b><br><span class="pos">Top:</span> ${esc(r.top.map(nameOf).join(", "))}<br><span class="neg">Lowest:</span> ${esc(r.bottom.map(nameOf).join(", "))}</p>`).join("")}</details>
    </div></section>`;
}
function drawPaper(p,cur,mkt){
  const el=$("#paperchart"); if(!p||!el) return;
  if(p.t.length<2){ el.innerHTML='<p class="muted" style="margin:8px 0">The chart appears once there are a couple of days of history.</p>'; return; }
  const L=p[cur], s=[{v:L.top,color:"var(--pos)",name:"Top",w:2},{v:L.bottom,color:"var(--neg)",name:"Lowest",w:2}];
  if(mkt) s.push({v:L.mkt,color:"var(--accent)",name:"Markets",w:1.4});
  s.push({v:L.world,color:"var(--faint)",name:"World",w:1.4});
  lineChart(el,{t:p.t,series:s,h:220,baseline:10000,fmt:v=>moneyIn(v,cur)});
}
/* Signal changes recorded from the daily snapshots */
function changesSection(ch,{nameOf,noun}){
  const list=(ch&&ch.changes||[]).slice().reverse().slice(0,40);
  const byDate={}; list.forEach(c=>(byDate[c.date]=byDate[c.date]||[]).push(c));
  return `<section id="changes"><div class="sec-head"><div class="grow"><div class="eyebrow">Signal changes</div><h2>What changed recently</h2>
    <p>Recorded from a snapshot of every score taken each weekday after the US market closes${ch&&ch.since?`, starting ${esc(ch.since)}`:""}. Today's entries are live and can still change before the close.</p></div></div>
    <div class="card panel">${list.length?Object.entries(byDate).map(([d,cs])=>`<div style="margin-bottom:10px"><div class="eyebrow" style="margin-bottom:2px">${esc(d)}${cs[0].live?" · live":""}</div>
      ${cs.map(c=>`<div class="idea" data-open="${esc(c.key)}" role="button" tabindex="0"><span class="nm">${esc(nameOf(c.key))}</span><span class="sc">${sigPill(c.from)} → ${sigPill(c.to)}</span></div>`).join("")}</div>`).join("")
      :`<p class="muted" style="margin:0">No signal changes recorded yet. The record started ${esc(ch&&ch.since||"today")}; changes to any of the ${esc(noun)} will appear here as they happen.</p>`}</div></section>`;
}
function signalHistoryCard(ch,key){
  const mine=(ch&&ch.changes||[]).filter(c=>c.key===key).slice().reverse();
  return `<div class="card" style="padding:16px"><div class="eyebrow" style="margin-bottom:6px">Signal history</div>
    ${mine.length?mine.map(c=>`<div style="display:flex;gap:10px;align-items:center;padding:4px 0;font-size:13.5px"><span class="num" style="min-width:86px">${esc(c.date)}${c.live?" (live)":""}</span>${sigPill(c.from)} → ${sigPill(c.to)}</div>`).join("")
      :`<p class="muted" style="margin:0;font-size:13.5px">No change recorded since daily snapshots began${ch&&ch.since?` on ${esc(ch.since)}`:""}.</p>`}</div>`;
}

/* ---------------------------------------------------------------- detail drawer */
const Drawer = {
  open(label,html,onClose){
    this.close(true);
    const scrim=document.createElement("div"); scrim.className="scrim"; scrim.id="scrim"; scrim.onclick=()=>this.close();
    const d=document.createElement("aside"); d.className="drawer"; d.id="drawer"; d.setAttribute("role","dialog"); d.setAttribute("aria-label",label);
    d.innerHTML=html; document.body.append(scrim,d); document.body.style.overflow="hidden";
    this.onClose=onClose;
    d.querySelector("#closeD")?.addEventListener("click",()=>this.close()); d.querySelector("#closeD")?.focus();
    d.querySelectorAll("a[href^='#']").forEach(a=>a.addEventListener("click",()=>this.close()));
    return d;
  },
  close(silent){ $("#scrim")?.remove(); $("#drawer")?.remove(); const t=$("#tip"); if(t) t.hidden=true; document.body.style.overflow="";
    if(!silent&&this.onClose) this.onClose(); },
};
function automatedNote(generated){ return `<p class="muted" style="margin:6px 0 0;font-size:12px">Written automatically by fixed rules from prices as of ${esc(new Date(generated*1000).toLocaleString([], {weekday:"short",hour:"2-digit",minute:"2-digit"}))}, and updated as prices change. Not advice; see the <a href="#limits">limitations</a>.</p>`; }

/* ---------------------------------------------------------------- live data loop */
function startLoop({url,onData}){
  const L={lastOk:0,nextAt:0,data:null};
  async function load(force){
    const btn=$("#refresh"); btn.disabled=true; btn.textContent="Refreshing…";
    try{
      const res=await fetch(STATIC ? `api/${url}.json?t=${Date.now()}` : `/api/${url}${force?"?force=1":""}`,{cache:"no-store"});
      if(!res.ok) throw new Error("Server replied "+res.status);
      const data=await res.json(); if(data.error) throw new Error(data.error);
      engineWeights=data.weights||{};
      L.data=data; L.lastOk=Date.now(); onData(data);
      $("#dot").className="dot";
    }catch(e){
      $("#dot").className="dot err";
      if(!L.data) $("#app").innerHTML=`<div class="loading err">Couldn't load prices: ${esc(e.message)}.<br>${STATIC?"Check your connection, then press Reload.":"Make sure <code>py app/server.py</code> is running, then press Refresh."}</div>`;
    }finally{ btn.disabled=false; btn.textContent=STATIC?"Reload":"Refresh now"; L.nextAt=Date.now()+REFRESH_MS; stamp(); }
  }
  function stamp(){
    if(!L.data) return;
    const mt=new Date(L.data.marketTime*1000), gen=new Date(L.data.generated*1000);
    const left=Math.max(0,L.nextAt-Date.now()), mm=Math.floor(left/60000), ss=Math.floor(left/1000)%60;
    if(Date.now()-L.lastOk>REFRESH_MS*3) $("#dot").className="dot stale";
    const last=mt.toLocaleString([], {weekday:"short",hour:"2-digit",minute:"2-digit"});
    if(STATIC){
      // GitHub's schedule can lag, so flag data older than an hour rather than pretending it's live
      const old=Date.now()-gen>60*60*1000; if(old) $("#dot").className="dot stale";
      $("#stamp").textContent=`${old?"Delayed":"Live"} · prices updated ${ago(gen.getTime())} (every ~15 min) · last trade ${last}`;
      return;
    }
    $("#stamp").textContent=`Live · prices checked ${gen.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})} · last trade ${last} · next check in ${mm?mm+" min":ss+" s"}`;
  }
  $("#refresh").onclick=()=>load(true);
  setInterval(()=>{ stamp(); if(L.nextAt && Date.now()>=L.nextAt) load(false); },1000);
  document.addEventListener("keydown",e=>{ if(e.key==="Escape") Drawer.close();
    if((e.key==="Enter"||e.key===" ")&&e.target.matches?.("[data-open][role=button]")){e.preventDefault();e.target.click();} });
  load(false);
  return L;
}
