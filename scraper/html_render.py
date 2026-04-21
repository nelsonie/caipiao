"""把 site/ 下的 .md 转成同名 .html，带统一样式与顶部 frontmatter 摘要。"""
from __future__ import annotations
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
        return f"今日五大联赛 ({fm.get('total_matches', 0)} 场)"
    if fm.get("name"):
        return str(fm["name"])
    return fallback


def convert_md_file(md_path: Path, md_filename_hint: str | None = None) -> str:
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
{html_body}
</main>
<footer>数据源 500 彩票网 · 项目 <a href="https://github.com/nelsonie/caipiao">nelsonie/caipiao</a></footer>
</body>
</html>
"""


def render_html_for_dir(site_dir: Path) -> list[Path]:
    """递归把 site_dir 下所有 .md 编成同名 .html，返回生成的 html 路径列表"""
    out: list[Path] = []
    for md in sorted(site_dir.rglob("*.md")):
        html_path = md.with_suffix(".html")
        html = convert_md_file(md, md_filename_hint=md.name)
        html_path.write_text(html, encoding="utf-8")
        out.append(html_path)
    return out
