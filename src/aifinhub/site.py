"""Static site generator for GitHub Pages.

A single self-contained index.html that fetches papers.json at runtime and
renders a searchable, filterable list. No build step, no framework.
"""

from __future__ import annotations

from pathlib import Path

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="A curated, searchable collection of research at the intersection of artificial intelligence and finance — part of the FAME project (Paris Dauphine – PSL x HEC Montreal).">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://fame-ai.org/hub/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="FAME">
<meta property="og:title" content="{title}">
<meta property="og:description" content="A curated, searchable collection of AI-and-finance research — part of the FAME project.">
<meta property="og:url" content="https://fame-ai.org/hub/">
<meta property="og:image" content="https://fame-ai.org/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<style>
  :root {{ --bg:#0a0e1c; --bg2:#0e1533; --fg:#e9ebf6; --muted:#98a1c4;
           --accent:#5b9dff; --g1:#56a8ff; --g2:#b984ff; --card:#141b32;
           --line:#283152; --shadow:0 2px 10px rgba(0,0,0,.35); }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; color:var(--fg); background:var(--bg);
          font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
          -webkit-font-smoothing:antialiased; }}
  a {{ color:var(--accent); }}
  .grad {{ background:linear-gradient(90deg,var(--g1),var(--g2));
           -webkit-background-clip:text; background-clip:text; color:transparent; }}
  .nav {{ position:sticky; top:0; z-index:50; background:rgba(10,14,28,.72);
          backdrop-filter:saturate(180%) blur(12px); box-shadow:0 1px 0 rgba(255,255,255,.04); }}
  .navwrap {{ max-width:1100px; margin:0 auto; padding:0 24px; height:62px;
              display:flex; align-items:center; justify-content:space-between; }}
  .brand {{ font-weight:800; font-size:22px; letter-spacing:1px; text-decoration:none; }}
  .nav .links a {{ color:var(--fg); font-size:14.5px; font-weight:500;
                   margin-left:24px; text-decoration:none; }}
  .nav .links a:hover {{ color:var(--accent); }}
  header {{ max-width:1100px; margin:0 auto; padding:34px 24px 6px; }}
  h1 {{ margin:0 0 6px; font-size:30px; font-weight:800; letter-spacing:-.3px; }}
  .sub {{ color:var(--muted); margin:0; font-size:16px; }}
  .controls {{ max-width:1100px; margin:18px auto; padding:0 24px;
               display:flex; gap:8px; flex-wrap:nowrap; align-items:center; }}
  input,select {{ background:var(--card); color:var(--fg); border:1px solid var(--line);
                  border-radius:9px; padding:9px 11px; font-size:14px; }}
  input::placeholder {{ color:#7c849f; }}
  input:focus,select:focus {{ outline:none; border-color:var(--accent);
                  box-shadow:0 0 0 3px rgba(91,157,255,.22); }}
  option {{ background:#141b32; }}
  input {{ flex:1; min-width:120px; }}
  select {{ flex:0 0 auto; cursor:pointer; }}
  main {{ max-width:1100px; margin:0 auto; padding:0 24px 60px; }}
  @media (max-width:760px) {{ .controls {{ flex-wrap:wrap; }} .nav .links a {{ margin-left:14px; }} }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px;
           padding:20px 22px; margin:14px 0; box-shadow:var(--shadow); transition:.15s; }}
  .card:hover {{ box-shadow:0 8px 22px rgba(16,24,40,.07); }}
  .card.feat {{ border-color:#caa23a; background:#181a2c; }}
  .card h2 {{ margin:0 0 6px; font-size:18px; }}
  .card h2 a {{ color:var(--fg); text-decoration:none; }}
  .card h2 a:hover {{ color:var(--accent); }}
  .meta {{ color:var(--muted); font-size:13px; margin-bottom:8px; }}
  .badge {{ display:inline-block; background:#1e2742; color:#aab4d4;
            border-radius:6px; padding:1px 8px; font-size:12px; margin-right:6px; }}
  .badge.feat {{ background:#3a3015; color:#f6c453; }}
  .badge.theme {{ background:#12301f; color:#5fd39a; cursor:pointer; }}
  .badge.fame {{ background:#2c1b40; color:#cf9bff; font-weight:600; }}
  .abs {{ color:#c2c8da; font-size:14px; white-space:pre-line;
          display:-webkit-box; -webkit-line-clamp:4; -webkit-box-orient:vertical;
          overflow:hidden; }}
  .abs.open {{ display:block; -webkit-line-clamp:unset; }}
  .more {{ background:none; border:none; color:var(--accent); cursor:pointer;
           font-size:13px; padding:4px 0; }}
  .more:hover {{ text-decoration:underline; }}
  footer {{ text-align:center; color:var(--muted); padding:30px; font-size:13px; }}
</style>
</head>
<body>
<nav class="nav">
  <div class="navwrap">
    <a class="brand grad" href="/">FAME</a>
    <div class="links">
      <a href="/">Project</a>
      <a href="/#research">Research</a>
      <a href="/#team">Team</a>
    </div>
  </div>
</nav>
<header>
  <h1>{title}</h1>
  <p class="sub">{subtitle}</p>
</header>
<div class="controls">
  <input id="q" placeholder="Search title, author, abstract…">
  <select id="theme"><option value="">All themes</option></select>
  <select id="src"><option value="">All sources</option></select>
  <select id="yfrom"><option value="">From</option></select>
  <select id="yto"><option value="">To</option></select>
  <select id="sort">
    <option value="date">Newest first</option>
    <option value="fame">Most FAME-relevant</option>
  </select>
</div>
<main id="list"></main>
<footer>
  <span id="count"></span> · Curated by {curator}
</footer>
<script>
let PAPERS=[];
const FAME={fame_threshold};
const el=id=>document.getElementById(id);
function esc(s){{return (s||'').replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));}}
function card(p){{
  const feat=p.featured?' feat':'';
  const badge=p.featured?'<span class="badge feat">★ featured</span>':'';
  const cats=(p.categories||[]).slice(0,4).map(c=>`<span class="badge">${{esc(c)}}</span>`).join('');
  const themes=(p.themes||[]).map(t=>`<span class="badge theme" onclick="pickTheme('${{esc(t)}}')">${{esc(t)}}</span>`).join('');
  const fame=(p.fame_score>=FAME)?`<span class="badge fame" title="Similarity to the FAME project summary">FAME · ${{p.fame_score}}%</span>`:'';
  const authors=(p.authors||[]).slice(0,8).join(', ');
  const abs=esc(p.abstract||'');
  const long=(p.abstract||'').length>320;
  const more=long?`<button class="more" onclick="toggleAbs(this)">Show more ▾</button>`:'';
  return `<div class="card${{feat}}">
    <h2><a href="${{esc(p.url)}}" target="_blank" rel="noopener">${{esc(p.title)}}</a></h2>
    <div class="meta">${{badge}}${{esc(authors)}} · <b>${{esc(p.venue||p.source)}}</b> · ${{esc((p.published||'').slice(0,7))}}</div>
    <div class="meta">${{fame}}${{themes}}${{cats}}</div>
    <div class="abs">${{abs}}</div>${{more}}
  </div>`;
}}
function pickTheme(t){{ el('theme').value=t; render(); window.scrollTo(0,0); }}
function toggleAbs(btn){{
  const open=btn.previousElementSibling.classList.toggle('open');
  btn.textContent=open?'Show less ▴':'Show more ▾';
}}
function render(){{
  const q=el('q').value.toLowerCase(), src=el('src').value,
        theme=el('theme').value, sort=el('sort').value,
        yfrom=el('yfrom').value, yto=el('yto').value;
  let rows=PAPERS.filter(p=>{{
    if(src && p.source!==src) return false;
    if(theme && !(p.themes||[]).includes(theme)) return false;
    const y=(p.published||'').slice(0,4);
    if(yfrom && (!y || y<yfrom)) return false;
    if(yto && (!y || y>yto)) return false;
    if(!q) return true;
    return (p.title+' '+(p.authors||[]).join(' ')+' '+p.abstract).toLowerCase().includes(q);
  }});
  rows.sort((a,b)=> sort==='fame'
    ? ((b.fame_score||0)-(a.fame_score||0))||(b.published||'').localeCompare(a.published||'')
    : (b.published||'').localeCompare(a.published||''));
  el('list').innerHTML=rows.map(card).join('')||'<p class="sub">No matches.</p>';
  el('count').textContent=rows.length+' papers';
}}
fetch('papers.json?v={version}').then(r=>r.json()).then(d=>{{
  PAPERS=d.papers||[];
  const srcs=[...new Set(PAPERS.map(p=>p.source))].sort();
  el('src').innerHTML+='<option>'+srcs.join('</option><option>')+'</option>';
  const themes=[...new Set(PAPERS.flatMap(p=>p.themes||[]))].sort();
  if(themes.length) el('theme').innerHTML+='<option>'+themes.join('</option><option>')+'</option>';
  const years=[...new Set(PAPERS.map(p=>(p.published||'').slice(0,4)).filter(Boolean))].sort().reverse();
  const yopts=years.map(y=>'<option>'+y+'</option>').join('');
  el('yfrom').innerHTML+=yopts; el('yto').innerHTML+=yopts;
  ['q','src','theme','yfrom','yto','sort'].forEach(id=>el(id).addEventListener('input',render));
  render();
}});
</script>
</body>
</html>
"""


def render_index(cfg: dict, docs_dir: Path, version: str = "1") -> None:
    from .fame import FAME_THRESHOLD
    hub = cfg["hub"]
    html = INDEX_HTML.format(
        title=hub["title"], subtitle=hub["subtitle"], curator=hub["curator"],
        fame_threshold=FAME_THRESHOLD, version=version,
    )
    (docs_dir / "index.html").write_text(html)
