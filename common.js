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
const pts = (v,dp=1) => v==null ? "–" : (v>0?"+":"")+(v*100).toFixed(dp)+" pts";
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
function delta(v,title=""){ if(v==null) return '<span class="delta flat">–</span>';
  const c=v>=1?"up":v<=-1?"down":"flat"; return `<span class="delta ${c}" title="${esc(title)}">${v>0?"+":""}${v.toFixed(1)}</span>`; }
function flagsHTML(m){ return (m.flags||[]).map(f=>`<span class="flag f-${f.tone}">${esc(f.label)}</span>`).join(""); }
function trendBars(n){ return `<span class="trend" title="${n}/4">${[0,1,2,3].map(j=>`<i class="${j<n?"on":""}"></i>`).join("")}</span>`; }
function partName(k){ return {mom121_rel:"12-month momentum vs market (skipping last month)",rs6m:"6-month relative strength",rs3m:"3-month relative strength",
  trend:"Trend (moving averages)",sharpe:"1-year return per unit of risk (Sharpe)",mdd:"Shallow 1-year drawdown"}[k]||k; }

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
function lineChart(el,{t,series,h=240,fmt=v=>v.toFixed(2),baseline=null,area=0}){
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
  if(baseline!=null) g+=`<line x1="${L}" x2="${W-R}" y1="${Y(baseline)}" y2="${Y(baseline)}" stroke="var(--faint)" stroke-dasharray="3 3"/>`;
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

/* Relative rotation graph. items: [{key, label, rrg:[[x,y]...], quad}] */
function rrgChart(el,items,onOpen){
  const W=Math.max(300,el.clientWidth||520), H=Math.round(Math.min(W*0.85,520)), P=34;
  const all=items.flatMap(r=>r.rrg); if(!all.length){el.innerHTML='<p class="muted">Not enough history.</p>';return;}
  const ext=a=>Math.max(...a.map(v=>Math.abs(v-100)))*1.12||2;
  const ex=ext(all.map(p=>p[0])), ey=ext(all.map(p=>p[1]));
  const X=v=>P+(v-100+ex)/(2*ex)*(W-2*P), Y=v=>H-P-(v-100+ey)/(2*ey)*(H-2*P);
  const qcol={Leading:"var(--pos)",Weakening:"var(--warn)",Lagging:"var(--neg)",Improving:"var(--info)"};
  const cx=X(100), cy=Y(100);
  let s=`<rect x="${cx}" y="${P}" width="${W-P-cx}" height="${cy-P}" fill="var(--pos)" fill-opacity=".06"/>
    <rect x="${cx}" y="${cy}" width="${W-P-cx}" height="${H-P-cy}" fill="var(--warn)" fill-opacity=".06"/>
    <rect x="${P}" y="${cy}" width="${cx-P}" height="${H-P-cy}" fill="var(--neg)" fill-opacity=".06"/>
    <rect x="${P}" y="${P}" width="${cx-P}" height="${cy-P}" fill="var(--info)" fill-opacity=".06"/>
    <line x1="${P}" x2="${W-P}" y1="${cy}" y2="${cy}" stroke="var(--line)"/><line x1="${cx}" x2="${cx}" y1="${P}" y2="${H-P}" stroke="var(--line)"/>
    <text x="${W-P-6}" y="${P+16}" text-anchor="end" font-size="12" font-weight="600" fill="var(--pos)">LEADING</text>
    <text x="${W-P-6}" y="${H-P-8}" text-anchor="end" font-size="12" font-weight="600" fill="var(--warn)">WEAKENING</text>
    <text x="${P+6}" y="${H-P-8}" font-size="12" font-weight="600" fill="var(--neg)">LAGGING</text>
    <text x="${P+6}" y="${P+16}" font-size="12" font-weight="600" fill="var(--info)">IMPROVING</text>
    <text x="${W/2}" y="${H-8}" text-anchor="middle" font-size="11" fill="var(--muted)">Relative strength →</text>
    <text x="12" y="${H/2}" text-anchor="middle" font-size="11" fill="var(--muted)" transform="rotate(-90 12 ${H/2})">Relative momentum →</text>`;
  const labels=[];
  items.forEach(r=>{ const tl=r.rrg, c=qcol[r.quad]||"var(--muted)", last=tl[tl.length-1];
    s+=`<polyline points="${tl.map(p=>X(p[0]).toFixed(1)+","+Y(p[1]).toFixed(1)).join(" ")}" fill="none" stroke="${c}" stroke-opacity=".45" stroke-width="1.4"/>`;
    tl.slice(0,-1).forEach(p=>s+=`<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="1.8" fill="${c}" fill-opacity=".45"/>`);
    s+=`<circle cx="${X(last[0])}" cy="${Y(last[1])}" r="5" fill="${c}" stroke="var(--surface)" stroke-width="1.5" data-open="${esc(r.key)}" style="cursor:pointer"><title>${esc(r.title||r.label)}: ${esc(r.quad)}</title></circle>`;
    labels.push({x:X(last[0]),y:Y(last[1]),t:r.label.length>18?r.label.slice(0,17)+"…":r.label,key:r.key});
  });
  labels.sort((a,b)=>a.y-b.y); const placed=[];
  labels.forEach(l=>{ let y=l.y-8; while(placed.some(p=>Math.abs(p.y-y)<12&&Math.abs(p.x-l.x)<(l.t.length*6.5+10))) y+=12; placed.push({x:l.x,y});
    const right=l.x>W-130; s+=`<text x="${l.x+(right?-8:8)}" y="${y}" text-anchor="${right?"end":"start"}" font-size="11.5" fill="var(--ink)" data-open="${esc(l.key)}" style="cursor:pointer">${esc(l.t)}</text>`; });
  el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Relative rotation graph">${s}</svg>`;
  el.querySelectorAll("[data-open]").forEach(n=>n.addEventListener("click",()=>onOpen(n.dataset.open)));
}

/* ---------------------------------------------------------------- shared verdict + cards */
function verdict(m){
  // Built fresh from the latest data on every refresh; each clause only appears when the numbers support it.
  const s=m.score??50, over=m.rsi!=null&&m.rsi>=70, stretched=m.vs200!=null&&m.vs200>.15;
  const below200=m.vs200!=null&&m.vs200<0, gap=below200?` It is ${pct(-m.vs200,1,false)} below that line today.`:"";
  if(s>=60){
    const base = m.quad==="Weakening" ? "A leader that is losing relative momentum. Fine to hold; be selective with new money."
                                      : "Momentum, trend and relative strength all support an overweight.";
    if(!over&&!stretched) return base;
    const why=[over?`RSI ${m.rsi.toFixed(0)}`:"", stretched?`${pct(m.vs200,0,false)} above its 200-day average`:""].filter(Boolean).join(", ");
    return `${base} It is also stretched (${why}), so favour adding on pullbacks rather than chasing.`;
  }
  if(m.quad==="Improving"){
    if(s>=40) return "Turning up from a laggard position. A watch-list candidate.";
    return below200 ? `Early signs of a turn, but the trend is still weak. Wait for a close back above the 200-day average.${gap}`
                    : "Early signs of a turn and already back above its 200-day average, but the score is still low. Watch whether relative strength keeps improving before committing.";
  }
  if(s<40) return "Weak trend and relative performance. Underweight or avoid until it improves."+
                  (below200?` A close back above the 200-day average would be the first sign of repair.${gap}`:"");
  return "No strong edge either way. Market weight.";
}
function historyText(m){
  const bits=[["today",m.d1],["this week",m.d1w],["this month",m.d1m]].filter(([,v])=>v!=null)
    .map(([w,v])=>`${Math.abs(v)<1?"flat":(v>0?"up ":"down ")+Math.abs(v).toFixed(1)} ${w}`);
  return bits.length? "Score "+bits.join(", ")+"." : "";
}
function scoreHistoryCard(){ return `<div class="card chartbox"><div class="row"><span class="eyebrow">Score over the last 3 months</span>
  <span class="muted" style="font-size:12.5px" id="histtxt"></span></div><div id="hchart"></div>
  <p class="note">Each point re-scores every market as it stood that week, so moves reflect both its own prices and everyone else's.</p></div>`; }
function drawScoreHistory(m,cuts){
  $("#histtxt").textContent=historyText(m);
  lineChart($("#hchart"),{t:cuts,series:[{v:m.hist,color:scoreColor(m.score),name:"Score",w:2}],h:150,baseline:50,fmt:v=>v.toFixed(0)});
}
function holdingsCard(r,holdingsAt,what="the fund"){
  const h=r.holdings; if(!h||!h.length) return `<div class="card" style="padding:16px"><div class="eyebrow">Top 10 holdings</div><p class="muted" style="margin:6px 0 0">The fund provider hasn't published holdings for this fund.</p></div>`;
  const max=h[0].pct||1, tot=r.m.top10;
  const read = tot>=0.6?"Highly concentrated: a few companies drive most of the return."
             : tot>=0.35?"Moderately concentrated." : "Well spread: no single company dominates.";
  const asOf = holdingsAt? new Date(holdingsAt*1000).toLocaleDateString(undefined,{day:"numeric",month:"short"}) : "";
  return `<div class="card" style="padding:16px"><div class="row" style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:8px">
      <span class="eyebrow">Top 10 holdings</span><span class="muted" style="font-size:12.5px">${pct(tot,1,false)} of ${esc(what)} · ${esc(read)}</span></div>
    <div class="holds">${h.map((x,i)=>`<span class="hr">${i+1}</span>
      <span class="hn">${esc(x.name)} <a href="https://finance.yahoo.com/quote/${encodeURIComponent(x.sym)}" target="_blank" rel="noopener">${esc(x.sym)}</a></span>
      <span class="bar"><i style="width:${x.pct/max*100}%;background:var(--accent)"></i></span><span class="num">${pct(x.pct,1,false)}</span>`).join("")}</div>
    <p class="muted" style="font-size:12px;margin:10px 0 0">Weights as published by the fund provider${asOf?`, checked ${esc(asOf)}`:""}. Ticker links open Yahoo Finance.</p></div>`;
}
function factsCard(f,{ccy="USD",bf={},bn="its market",title="Fund facts",note="From Yahoo Finance, checked daily."}={}){
  const cmp=(v,bv,fmt,lowWord,highWord)=> v==null||bv==null? "" :
    `<small>${esc(bn)} ${fmt(bv)} · ${Math.abs(v/bv-1)<0.05?"in line":(v>bv?highWord:lowWord)}</small>`;
  const betaTxt = f.beta==null? "" : f.beta>1.15? "Swings more than the market" : f.beta<0.85? "Steadier than the market" : "Moves roughly with the market";
  const feeTxt = f.fee==null? "Not published" : `${bigMoney(f.fee*10000,"USD")} a year per $10,000 invested`;
  const local = f.aum!=null && ccy!=="USD" ? `<small>${bigMoney(f.aum,ccy)} in ${esc(ccy)}</small>` : "<small>Fund size</small>";
  return `<div class="card" style="padding:16px"><div class="eyebrow" style="margin-bottom:10px">${esc(title)}</div>
    <div class="facts">
      <div><span>Net assets</span><b>${bigMoney(f.aumUsd,"USD")}</b>${local}</div>
      <div><span>P/E ratio</span><b>${f.pe==null?"–":f.pe.toFixed(1)}</b>${cmp(f.pe,bf.pe,v=>v.toFixed(1),"cheaper than "+bn,"pricier than "+bn)||"<small>Price / trailing earnings</small>"}</div>
      <div><span>Dividend yield</span><b>${pct(f.yld,2,false)}</b>${cmp(f.yld,bf.yld,v=>pct(v,2,false),"lower income","higher income")||"<small>Last 12 months</small>"}</div>
      <div><span>Beta (5Y monthly)</span><b>${f.beta==null?"–":f.beta.toFixed(2)}</b><small>${esc(betaTxt)}</small></div>
      <div><span>Expense ratio</span><b>${pct(f.fee,2,false)}</b><small>${esc(feeTxt)}</small></div>
    </div>
    <p class="muted" style="font-size:12px;margin:10px 0 0">${esc(note)}</p></div>`;
}

/* ---------------------------------------------------------------- backtest */
function btStrength(bt){
  const t=bt.spreadT??0;
  return t>=2? {cls:"good",label:"Worked",word:"a statistically meaningful edge"}
       : t>=1? {cls:"weak",label:"Weak edge",word:"a positive but statistically weak edge that could be luck"}
       : t>-1? {cls:"none",label:"No edge",word:"no reliable edge"}
       :       {cls:"none",label:"Backfired",word:"an edge that worked the wrong way round"};
}
function btSummaryLine(bt,noun,vs="their market"){
  if(!bt) return "";
  const st=btStrength(bt);
  return `<p class="summary-line"><b>Backtest ${esc(monthYear(bt.from))}–${esc(monthYear(bt.to))}:</b> the top fifth of ${esc(noun)} by score did ${pts(bt.topAnn,1)} a year vs ${esc(vs)}, the bottom fifth ${pts(bt.botAnn,1)}. That is ${esc(st.word)}. <a href="#track">See the track record</a>.</p>`;
}
// "beat it by 1.6%", "trailed it by 3.5%", or "roughly matched it" when the gap rounds to nothing
const vsBench = (v,past=true) => Math.abs(v)<0.0015 ? (past?"roughly matched":"roughly match")
  : `${v>=0?(past?"beat":"beat"):(past?"trailed":"trail")}`;
const byPct = v => Math.abs(v)<0.0015 ? "" : ` by ${pct(Math.abs(v),1,false)}`;
function btAdvice(bt,noun){
  const t=bt.spreadT??0;
  if(t>=2) return "The score has been a useful guide on average, though it still misses in many months.";
  if(t>=1) return "Treat the score as a mild tilt that has helped on average, not as a reliable predictor for any single month.";
  return `For choosing ${noun}, the score has not added value in this test. Use it to describe trends and risk, and lean more on other evidence${noun==="countries"?" such as valuation, currency and the backdrop":""}.`;
}
function backtestSection(bt,{noun,benchWord}){
  if(!bt) return `<section id="track"><div class="sec-head"><div class="grow"><div class="eyebrow">Backtest</div><h2>Has the score worked?</h2>
    <p>Not enough history to test yet.</p></div></div></section>`;
  const st=btStrength(bt), years=((bt.to-bt.from)/31557600).toFixed(0);
  const b=bt.bands, order=["Strong overweight","Overweight","Neutral","Underweight","Avoid"];
  const vals=order.map(k=>b[k]&&b[k].ann), ordered=vals.every((v,i)=>i===0||v==null||vals[i-1]==null||vals[i-1]>=v-0.005);
  const text = `Over ${years} years (${monthYear(bt.from)} to ${monthYear(bt.to)}), the ${noun} ranked in the top fifth by score went on to ${vsBench(bt.topAnn,false)} ${benchWord}${byPct(bt.topAnn)} a year, while the bottom fifth ${vsBench(bt.botAnn)} it${byPct(bt.botAnn)}. `+
    `That gap of ${pts(bt.spreadAnn,1)} a year is ${st.word} (t = ${bt.spreadT==null?"–":bt.spreadT.toFixed(1)}; 2 or more would be convincing), and the top beat the bottom in ${pct(bt.hit,0,false)} of months. `+
    `${ordered?"The signal bands lined up in the right order, from Strong overweight down to Avoid.":"The signal bands did not line up neatly from Strong overweight down to Avoid."} ${btAdvice(bt,noun)}`;
  const kpi=(l,v,s,c="")=>`<div class="kpi"><span>${l}</span><b class="${c}">${v}</b><small>${s}</small></div>`;
  const comp=Object.entries(bt.components).map(([k,v])=>{ const t=v.t??0, e=t>=1.5?["eff-help","Helped"]:t<=-1.5?["eff-hurt","Hurt"]:["eff-none","No clear effect"];
    return `<tr><td>${esc(partName(k))}</td><td>${Math.round((engineWeights[k]||0)*100)}%</td><td class="${e[0]}">${e[1]}</td><td class="num">${v.t==null?"–":v.t.toFixed(1)}</td></tr>`; }).join("");
  return `<section id="track">
    <div class="sec-head"><div class="grow"><div class="eyebrow">Backtest · ${bt.months} months · ~${Math.round(bt.avgFunds)} ${esc(noun)} a month</div><h2>Has the score worked?</h2>
      <p>At the end of every month since ${esc(monthYear(bt.from))}, every one of the ${esc(noun)} was scored using only the data available that day, with exactly the same recipe as the live page. We then measured how each did over the following month against ${esc(benchWord)}.</p></div></div>
    <div class="bt-grid">
      <div class="card bt-verdict"><span class="badge ${st.cls}">${st.label}</span><div>${esc(text)}</div></div>
      <div class="kpis">
        ${kpi("Top fifth vs market",pts(bt.topAnn,1)+"/yr","Average yearly return over the next months, relative to "+esc(benchWord),cls(bt.topAnn))}
        ${kpi("Bottom fifth vs market",pts(bt.botAnn,1)+"/yr","The lowest-scored fifth over the same months",cls(bt.botAnn))}
        ${kpi("Gap, top minus bottom",pts(bt.spreadAnn,1)+"/yr",`Confidence t = ${bt.spreadT==null?"–":bt.spreadT.toFixed(1)} · worst month ${pts(bt.worstMonth.spread,1)} (${esc(monthYear(bt.worstMonth.t+86400))})`,cls(bt.spreadAnn))}
        ${kpi("Months top beat bottom",pct(bt.hit,0,false),"50% would be a coin toss")}
        ${kpi("Last 12 months",pts(bt.recentSpreadAnn,1)+"/yr",`Gap in the most recent year · top beat bottom in ${pct(bt.recentHit,0,false)} of months`,cls(bt.recentSpreadAnn))}
        ${kpi("Monthly turnover",pct(bt.turnover,0,false),"Share of the top fifth that changes each month (trading costs not included)")}
      </div>
      <div class="two">
        <div class="card chartbox"><div class="row"><span class="eyebrow">Growth of 100, relative to each market</span></div>
          <div class="row"><span class="key"><i style="background:var(--pos)"></i>Top fifth</span><span class="key"><i style="background:var(--faint)"></i>All ${esc(noun)}</span><span class="key"><i style="background:var(--neg)"></i>Bottom fifth</span></div>
          <div id="btchart"></div><p class="note">Rebalanced monthly. Above 100 = beat ${esc(benchWord)} since ${esc(monthYear(bt.from))}; no trading costs or taxes.</p></div>
        <div class="card panel"><div class="eyebrow" style="margin-bottom:8px">What each signal went on to do (per year, vs market)</div>
          <div class="bars">${barsSVG(order.map(k=>({label:k,v:b[k].ann,sub:`${b[k].n} cases`})),{fmt:v=>pts(v,1)})}</div>
          <p class="note">The average next-month return relative to ${esc(benchWord)}, annualised, for every time a market carried that signal.</p></div>
      </div>
      <div class="card panel"><div class="eyebrow" style="margin-bottom:6px">Which ingredients carried the signal</div>
        <div style="overflow-x:auto"><table class="comp"><thead><tr><th>Ingredient</th><th>Weight</th><th>Effect on next month</th><th>Confidence (t)</th></tr></thead><tbody>${comp}</tbody></table></div>
        <p class="note">The weights were set before this test and deliberately not re-tuned to it: fitting weights to the past makes a backtest look better without making the future any more predictable.</p></div>
      <div class="card panel"><div class="eyebrow" style="margin-bottom:6px">Read this test with care</div><ul class="caveats">
        <li>The ${esc(noun)} were chosen in 2026, so the test only includes ones that survived; that flatters any strategy slightly.</li>
        <li>Monthly rebalancing, no trading costs, spreads or taxes. With ${pct(bt.turnover,0,false)} monthly turnover, real-world costs would eat part of any gap.</li>
        <li>${bt.months} months is a short sample, and one strong year (such as 2020) can dominate the average.</li>
        <li>Longer horizons: the top-minus-bottom gap averaged ${pts(bt.fwd3,1)} over the next 3 months and ${pts(bt.fwd6,1)} over the next 6.</li>
        <li>Past results do not guarantee future ones, especially when a pattern becomes widely known.</li></ul></div>
    </div></section>`;
}
let engineWeights = {};
function drawBacktest(bt){
  if(!bt||!$("#btchart")) return;
  const c=bt.curves;
  lineChart($("#btchart"),{t:c.t,series:[{v:c.top.map(v=>v*100),color:"var(--pos)",name:"Top",w:2},{v:c.mid.map(v=>v*100),color:"var(--faint)",name:"All",w:1.4},{v:c.bot.map(v=>v*100),color:"var(--neg)",name:"Bottom",w:2}],h:230,baseline:100,fmt:v=>v.toFixed(0)});
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
function automatedNote(generated){ return `<p class="muted" style="margin:6px 0 0;font-size:12px">An automated, rule-based read of data from ${esc(new Date(generated*1000).toLocaleString([], {weekday:"short",hour:"2-digit",minute:"2-digit"}))}. It rewrites itself as prices change. <a href="#limits">Limitations</a></p>`; }

/* ---------------------------------------------------------------- live data loop */
function startLoop({url,onData,onError}){
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
      if(!L.data) $("#app").innerHTML=`<div class="loading err">Couldn't load prices: ${esc(e.message)}.<br>${STATIC?"Check your connection, then press Reload.":"Make sure <code>py server.py</code> is running, then press Refresh."}</div>`;
    }finally{ btn.disabled=false; btn.textContent=STATIC?"Reload":"Refresh now"; L.nextAt=Date.now()+REFRESH_MS; stamp(); }
  }
  function stamp(){
    if(!L.data) return;
    const mt=new Date(L.data.marketTime*1000), gen=new Date(L.data.generated*1000);
    const left=Math.max(0,L.nextAt-Date.now()), mm=Math.floor(left/60000), ss=String(Math.floor(left/1000)%60).padStart(2,"0");
    if(Date.now()-L.lastOk>REFRESH_MS*3) $("#dot").className="dot stale";
    if(STATIC){
      // GitHub's schedule can lag, so flag data older than an hour rather than pretending it's live
      const old=Date.now()-gen>60*60*1000; if(old) $("#dot").className="dot stale";
      $("#stamp").textContent=`${old?"Delayed":"Live"} · prices updated ${ago(gen.getTime())} (every ~15 min) · last trade ${mt.toLocaleString([], {weekday:"short",hour:"2-digit",minute:"2-digit"})}`;
      return;
    }
    $("#stamp").textContent=`Live · prices fetched ${gen.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})} · last trade ${mt.toLocaleString([], {weekday:"short",hour:"2-digit",minute:"2-digit"})} · next refresh ${mm}:${ss}`;
  }
  $("#refresh").onclick=()=>load(true);
  setInterval(()=>{ stamp(); if(L.nextAt && Date.now()>=L.nextAt) load(false); },1000);
  document.addEventListener("keydown",e=>{ if(e.key==="Escape") Drawer.close();
    if((e.key==="Enter"||e.key===" ")&&e.target.matches?.("[data-open][role=button]")){e.preventDefault();e.target.click();} });
  load(false);
  return L;
}
