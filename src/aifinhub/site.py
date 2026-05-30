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
<style>
  :root {{ --bg:#0f1115; --card:#1a1d24; --fg:#e7e9ee; --muted:#9aa3b2;
           --accent:#5b9dff; --feat:#f6c453; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",
          Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--fg); }}
  header {{ padding:32px 20px 16px; max-width:980px; margin:0 auto; }}
  h1 {{ margin:0 0 4px; font-size:28px; }}
  .sub {{ color:var(--muted); margin:0; }}
  .controls {{ max-width:980px; margin:16px auto; padding:0 20px;
               display:flex; gap:10px; flex-wrap:wrap; }}
  input,select {{ background:var(--card); color:var(--fg); border:1px solid #2a2e38;
                  border-radius:8px; padding:10px 12px; font-size:15px; }}
  input {{ flex:1; min-width:220px; }}
  main {{ max-width:980px; margin:0 auto; padding:0 20px 60px; }}
  .card {{ background:var(--card); border:1px solid #242833; border-radius:12px;
           padding:18px 20px; margin:12px 0; }}
  .card.feat {{ border-color:var(--feat); }}
  .card h2 {{ margin:0 0 6px; font-size:18px; }}
  .card h2 a {{ color:var(--fg); text-decoration:none; }}
  .card h2 a:hover {{ color:var(--accent); }}
  .meta {{ color:var(--muted); font-size:13px; margin-bottom:8px; }}
  .badge {{ display:inline-block; background:#222631; color:var(--accent);
            border-radius:6px; padding:1px 8px; font-size:12px; margin-right:6px; }}
  .badge.feat {{ background:#3a3015; color:var(--feat); }}
  .badge.theme {{ background:#15301f; color:#5fd39a; cursor:pointer; }}
  .abs {{ color:#c7ccd6; font-size:14px; white-space:pre-line;
          display:-webkit-box; -webkit-line-clamp:4; -webkit-box-orient:vertical;
          overflow:hidden; }}
  .abs.open {{ display:block; -webkit-line-clamp:unset; }}
  .more {{ background:none; border:none; color:var(--accent); cursor:pointer;
           font-size:13px; padding:4px 0; }}
  .more:hover {{ text-decoration:underline; }}
  .links a {{ color:var(--accent); text-decoration:none; margin-right:14px;
              font-size:14px; }}
  footer {{ text-align:center; color:var(--muted); padding:30px; font-size:13px; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <p class="sub">{subtitle}</p>
</header>
<div class="controls">
  <input id="q" placeholder="Search title, author, abstract…">
  <select id="theme"><option value="">All themes</option></select>
  <select id="src"><option value="">All sources</option></select>
  <select id="sort">
    <option value="date">Newest first</option>
    <option value="featured">Featured first</option>
  </select>
</div>
<main id="list"></main>
<footer>
  <span id="count"></span> · Curated by {curator} ·
  <a href="papers.json" style="color:var(--muted)">data</a>
</footer>
<script>
let PAPERS=[];
const el=id=>document.getElementById(id);
function esc(s){{return (s||'').replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));}}
function card(p){{
  const feat=p.featured?' feat':'';
  const badge=p.featured?'<span class="badge feat">★ featured</span>':'';
  const cats=(p.categories||[]).slice(0,4).map(c=>`<span class="badge">${{esc(c)}}</span>`).join('');
  const themes=(p.themes||[]).map(t=>`<span class="badge theme" onclick="pickTheme('${{esc(t)}}')">${{esc(t)}}</span>`).join('');
  const authors=(p.authors||[]).slice(0,8).join(', ');
  const pdf=p.pdf_url?`<div class="links"><a href="${{esc(p.pdf_url)}}" target="_blank" rel="noopener">PDF</a></div>`:'';
  const abs=esc(p.abstract||'');
  const long=(p.abstract||'').length>320;
  const more=long?`<button class="more" onclick="toggleAbs(this)">Show more ▾</button>`:'';
  return `<div class="card${{feat}}">
    <h2><a href="${{esc(p.url)}}" target="_blank" rel="noopener">${{esc(p.title)}}</a></h2>
    <div class="meta">${{badge}}${{esc(authors)}} · <b>${{esc(p.venue||p.source)}}</b> · ${{esc(p.published||'')}}</div>
    <div class="meta">${{themes}}${{cats}}</div>
    <div class="abs">${{abs}}</div>${{more}}
    ${{pdf}}
  </div>`;
}}
function pickTheme(t){{ el('theme').value=t; render(); window.scrollTo(0,0); }}
function toggleAbs(btn){{
  const open=btn.previousElementSibling.classList.toggle('open');
  btn.textContent=open?'Show less ▴':'Show more ▾';
}}
function render(){{
  const q=el('q').value.toLowerCase(), src=el('src').value,
        theme=el('theme').value, sort=el('sort').value;
  let rows=PAPERS.filter(p=>{{
    if(src && p.source!==src) return false;
    if(theme && !(p.themes||[]).includes(theme)) return false;
    if(!q) return true;
    return (p.title+' '+(p.authors||[]).join(' ')+' '+p.abstract).toLowerCase().includes(q);
  }});
  rows.sort((a,b)=> sort==='featured'
    ? (b.featured-a.featured)||(b.published||'').localeCompare(a.published||'')
    : (b.published||'').localeCompare(a.published||''));
  el('list').innerHTML=rows.map(card).join('')||'<p class="sub">No matches.</p>';
  el('count').textContent=rows.length+' papers';
}}
fetch('papers.json').then(r=>r.json()).then(d=>{{
  PAPERS=d.papers||[];
  const srcs=[...new Set(PAPERS.map(p=>p.source))].sort();
  el('src').innerHTML+='<option>'+srcs.join('</option><option>')+'</option>';
  const themes=[...new Set(PAPERS.flatMap(p=>p.themes||[]))].sort();
  if(themes.length) el('theme').innerHTML+='<option>'+themes.join('</option><option>')+'</option>';
  ['q','src','theme','sort'].forEach(id=>el(id).addEventListener('input',render));
  render();
}});
</script>
</body>
</html>
"""


def render_index(cfg: dict, docs_dir: Path) -> None:
    hub = cfg["hub"]
    html = INDEX_HTML.format(
        title=hub["title"], subtitle=hub["subtitle"], curator=hub["curator"]
    )
    (docs_dir / "index.html").write_text(html)
