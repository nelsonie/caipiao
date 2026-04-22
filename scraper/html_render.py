"""把 site/ 下的 .md 转成同名 .html，带统一样式与顶部 frontmatter 摘要。"""
from __future__ import annotations
import json
import re
from pathlib import Path
import yaml
import markdown as md_lib

_MD_LINK_RE = re.compile(r'href="([^"]+)\.md([#"])')


_CSS = """
:root { color-scheme: light dark; --fg:#222; --bg:#fff; --muted:#666; --border:#ddd; --accent:#2684ff; --code-bg:#f4f4f6; }
@media (prefers-color-scheme: dark) {
  :root { --fg:#e8e8ea; --bg:#1a1a1c; --muted:#999; --border:#333; --accent:#5aa3ff; --code-bg:#222; }
}
* { box-sizing: border-box; }
body {
  font: 15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB",sans-serif;
  color: var(--fg); background: var(--bg); margin: 0;
}
main { max-width: 1100px; margin: 0 auto; padding: 1.5rem 1.2rem 4rem; }
nav  { max-width: 1100px; margin: 0 auto; padding: 1rem 1.2rem; border-bottom: 1px solid var(--border);
       display: flex; gap: 1.2rem; font-size: .92rem; }
nav a { color: var(--accent); text-decoration: none; }
nav a:hover { text-decoration: underline; }
h1 { font-size: 1.6rem; margin: 1.2rem 0 1rem; border-bottom: 2px solid var(--border); padding-bottom: .5rem; }
h2 { font-size: 1.2rem; margin: 1.6rem 0 .6rem; color: var(--fg); }
h3 { font-size: 1.05rem; margin: 1.1rem 0 .4rem; color: var(--muted); }
p  { margin: .55rem 0; }
a  { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
code { background: var(--code-bg); padding: 1px 5px; border-radius: 4px; font-size: .88em;
       font-family: ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
pre { background: var(--code-bg); padding: .8rem 1rem; border-radius: 6px; overflow-x: auto; }
hr { border: 0; border-top: 1px solid var(--border); margin: 1.5rem 0; }
ul, ol { padding-left: 1.4rem; }
li { margin: .15rem 0; }

.table-wrap { overflow-x: auto; margin: .6rem 0 1rem; border: 1px solid var(--border); border-radius: 6px; }
table { width: 100%; border-collapse: collapse; font-size: .88rem; }
th, td { text-align: left; padding: .45rem .7rem; border-bottom: 1px solid var(--border); white-space: nowrap; }
th { background: var(--code-bg); font-weight: 600; color: var(--muted); }
tr:last-child td { border-bottom: 0; }

.fm-box { border: 1px solid var(--border); border-radius: 8px; padding: .8rem 1rem;
          margin: 0 0 1.2rem; background: var(--code-bg); font-size: .9rem; }
.fm-box .fm-row { display: flex; gap: .6rem; padding: .2rem 0; }
.fm-box .fm-k { width: 140px; color: var(--muted); flex-shrink: 0; }
.fm-box .fm-v { flex: 1; font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .88rem; word-break: break-all; }

footer { max-width: 1100px; margin: 3rem auto 2rem; padding: 0 1.2rem; color: var(--muted); font-size: .8rem;
         border-top: 1px solid var(--border); padding-top: 1rem; }

button { font: inherit; padding: .5rem 1rem; border: 1px solid var(--border);
         border-radius: 6px; background: var(--accent); color: #fff; cursor: pointer; }
button:hover { opacity: .88; }
button:disabled { opacity: .5; cursor: default; }

.quick { margin: 1rem 0 2rem; padding: 1rem 1.2rem; border: 1px solid var(--border);
         border-radius: 8px; background: var(--code-bg); }
.quick h2 { margin: 0 0 .6rem; font-size: 1rem; color: var(--muted); font-weight: 600; }
.quick ul { list-style: none; padding: 0; margin: 0 0 1rem; }
.quick li { padding: .35rem 0; border-bottom: 1px dashed var(--border);
            display: flex; gap: .8rem; align-items: baseline; flex-wrap: wrap; }
.quick li:last-child { border-bottom: 0; }
.quick .meta { color: var(--muted); font-size: .82rem; font-variant-numeric: tabular-nums;
               min-width: 11rem; flex-shrink: 0; }
.quick .teams { flex: 1; }
.quick .url { margin-left: auto; font-family: ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
              font-size: .8rem; color: var(--muted); white-space: nowrap;
              overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.quick .url:hover { color: var(--accent); }
@media (max-width: 700px) {
  .quick .url { margin-left: 0; flex-basis: 100%; }
}
.quick .hint { font-size: .78rem; color: var(--muted); margin-top: .6rem; }
"""


def _split_frontmatter(md_text: str) -> tuple[dict | None, str]:
    if not md_text.startswith("---\n"):
        return None, md_text
    end = md_text.find("\n---\n", 4)
    if end < 0:
        return None, md_text
    try:
        fm = yaml.safe_load(md_text[4:end])
    except Exception:
        return None, md_text
    return fm, md_text[end + 5 :]


def _render_fm_box(fm: dict | None) -> str:
    if not fm:
        return ""
    def _fmt(v):
        if isinstance(v, dict):
            return " · ".join(f"<b>{k}</b>:{v2}" for k, v2 in v.items() if v2 is not None)
        if isinstance(v, list):
            return "、".join(str(x) for x in v)
        return str(v)
    rows = "".join(
        f'<div class="fm-row"><div class="fm-k">{k}</div><div class="fm-v">{_fmt(v)}</div></div>'
        for k, v in fm.items()
    )
    return f'<div class="fm-box">{rows}</div>'


def _title_from_fm(fm: dict | None, fallback: str) -> str:
    if not fm:
        return fallback
    if fm.get("home") and fm.get("away"):
        return f"{fm['home']} vs {fm['away']}"
    if "total_matches" in fm:
        return f"今日全部对阵 ({fm.get('total_matches', 0)} 场)"
    if fm.get("name"):
        return str(fm["name"])
    return fallback


def _render_index_quick_block(site_dir: Path) -> str:
    """
    首页最上方的"快查 + 一键复制"区块。
    数据源：site/index.json。纯字符串，不引入外部 JS。
    """
    idx_json = site_dir / "index.json"
    if not idx_json.exists():
        return ""
    try:
        data = json.loads(idx_json.read_text(encoding="utf-8"))
    except Exception:
        return ""
    matches = data.get("matches") or []
    if not matches:
        return ""

    # 按 (date, matchnum) 排序，与 index.md 的分组视角互补
    matches = sorted(matches, key=lambda m: (m.get("date") or "", m.get("matchnum") or ""))

    def _esc(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    li_html = []
    js_items = []
    for m in matches:
        gid = m.get("gameid")
        if not gid:
            continue
        date = m.get("date") or ""
        league = m.get("league") or ""
        home = m.get("home") or ""
        away = m.get("away") or ""
        meta = f"{date} · {league}"
        teams = f"{home} vs {away}"
        url_rel = f"/matches/{gid}.html"
        # URL 的文案里放 {ORIGIN} 占位符；页面加载时 JS 会替换成 location.origin
        li_html.append(
            f'<li>'
            f'<span class="meta">{_esc(meta)}</span>'
            f'<span class="teams">{_esc(teams)}</span>'
            f'<a class="url" href="{_esc(url_rel)}">{{ORIGIN}}{_esc(url_rel)}</a>'
            f'</li>'
        )
        js_items.append({
            "line": f"{date} {league} {home} vs {away} {{ORIGIN}}{url_rel}"
        })

    ul = "\n".join(li_html)
    payload_json = json.dumps(js_items, ensure_ascii=False)

    return f"""
<section class="quick">
  <h2>快查（{len(li_html)} 场 · 按日期升序）</h2>
  <ul>
    {ul}
  </ul>
  <button id="copy-all" type="button">复制全部对阵及链接</button>
  <p class="hint">点按钮会把每场一行，格式：<code>日期 联赛 主队 vs 客队 URL</code>，复制到剪贴板。</p>
  <script>
    (function () {{
      var ITEMS = {payload_json};
      var origin = location.origin;
      // 页面加载时把 li 里的 {{ORIGIN}} 占位符都换成真实域名
      document.querySelectorAll('.quick .url').forEach(function (a) {{
        if (a.textContent.indexOf('{{ORIGIN}}') === 0) {{
          a.textContent = origin + a.textContent.slice('{{ORIGIN}}'.length);
        }}
      }});
      var btn = document.getElementById('copy-all');
      btn.addEventListener('click', function () {{
        var text = ITEMS.map(function (it) {{ return it.line.replace('{{ORIGIN}}', origin); }}).join('\\n');
        var done = function () {{
          var prev = btn.textContent;
          btn.textContent = '已复制 ' + ITEMS.length + ' 条 ✓';
          btn.disabled = true;
          setTimeout(function () {{ btn.textContent = prev; btn.disabled = false; }}, 2000);
        }};
        if (navigator.clipboard && window.isSecureContext) {{
          navigator.clipboard.writeText(text).then(done, function (err) {{
            alert('复制失败：' + err);
          }});
        }} else {{
          var ta = document.createElement('textarea');
          ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
          document.body.appendChild(ta); ta.select();
          try {{ document.execCommand('copy'); done(); }} catch (e) {{ alert('复制失败'); }}
          document.body.removeChild(ta);
        }}
      }});
    }})();
  </script>
</section>
"""


def convert_md_file(md_path: Path, md_filename_hint: str | None = None,
                    extras_top: str = "") -> str:
    """读 md 文件，转成完整 HTML 字符串"""
    md_text = md_path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(md_text)

    html_body = md_lib.markdown(
        body,
        extensions=["tables", "fenced_code", "sane_lists"],
        output_format="html5",
    )
    # md 链接 → html 链接
    html_body = _MD_LINK_RE.sub(r'href="\1.html\2', html_body)
    # 给所有 table 裹一层 overflow 滚动容器
    html_body = re.sub(r"<table>", '<div class="table-wrap"><table>', html_body)
    html_body = re.sub(r"</table>", "</table></div>", html_body)

    title = _title_from_fm(fm, md_path.stem)
    md_name = md_filename_hint or md_path.name

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · caipiao</title>
<meta name="robots" content="noindex,nofollow">
<link rel="alternate" type="text/markdown" href="{md_name}">
<style>{_CSS}</style>
</head>
<body>
<nav>
  <a href="/">首页</a>
  <a href="/SKILL.html">SKILL（AI 指南）</a>
  <a href="{md_name}">查看原始 Markdown</a>
  <a href="/_meta.json">_meta.json</a>
</nav>
<main>
<h1>{title}</h1>
{_render_fm_box(fm)}
{extras_top}
{html_body}
</main>
<footer>数据源 500 彩票网 · 项目 <a href="https://github.com/nelsonie/caipiao">nelsonie/caipiao</a></footer>
</body>
</html>
"""


def render_html_for_dir(site_dir: Path) -> list[Path]:
    """递归把 site_dir 下所有 .md 编成同名 .html，返回生成的 html 路径列表"""
    out: list[Path] = []
    quick_block = _render_index_quick_block(site_dir)
    for md in sorted(site_dir.rglob("*.md")):
        html_path = md.with_suffix(".html")
        extras = quick_block if (md.parent == site_dir and md.name == "index.md") else ""
        html = convert_md_file(md, md_filename_hint=md.name, extras_top=extras)
        html_path.write_text(html, encoding="utf-8")
        out.append(html_path)
    return out
