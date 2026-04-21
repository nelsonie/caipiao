"""把解析好的 dict 渲染成 site/ 下的 MD + JSON 文件。"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
import yaml

from config import SITE_DIR, MATCHES_DIR


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fm(meta: dict) -> str:
    """YAML frontmatter，用 allow_unicode 保留中文字面量。"""
    body = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).rstrip()
    return f"---\n{body}\n---\n"


def _first_major_asia(yazhi: list[dict]) -> dict | None:
    """挑第一家有 live.handicap 的公司做 asia_main 摘要"""
    for r in yazhi:
        live = r.get("live") or {}
        if live.get("handicap"):
            return {
                "handicap":   live["handicap"],
                "home_water": live.get("home_water"),
                "away_water": live.get("away_water"),
                "company":    r.get("company"),
            }
    return None


def _first_major_euro(ouzhi: list[dict]) -> dict | None:
    for r in ouzhi:
        odds = (r.get("odds") or {}).get("live") or []
        if len(odds) >= 3:
            return {
                "win": odds[0], "draw": odds[1], "lost": odds[2],
                "company": r.get("company"),
            }
    return None


def render_match(gameid: str, match: dict, shuju: dict, yazhi: list[dict], ouzhi: list[dict]) -> tuple[str, str]:
    """返回 (md_text, json_text)"""
    fm_meta = {
        "gameid":       int(gameid),
        "matchnum":     match["matchnum"],
        "date":         match["date"],
        "league":       match["league"],
        "home":         match["home"],
        "away":         match["away"],
        "kickoff_cst":  match.get("kickoff_cst"),
        "spf": {
            "win":  match.get("spf_win"),
            "draw": match.get("spf_draw"),
            "lost": match.get("spf_lost"),
        },
        "asia_main": _first_major_asia(yazhi),
        "euro_main": _first_major_euro(ouzhi),
        "fetched_at_utc": _now_iso_utc(),
    }

    lines = [_fm(fm_meta)]
    lines.append(f"# {match['home']} vs {match['away']}\n")

    lines.append("## 交战 & 战绩\n")
    if shuju.get("h2h_summary"):
        lines.append(shuju["h2h_summary"] + "\n")
    if shuju.get("team_ranks"):
        lines.append("\n".join(f"- {r}" for r in shuju["team_ranks"][:2]) + "\n")
    if shuju.get("h2h_rows"):
        lines.append("\n近期交战：")
        for row in shuju["h2h_rows"][:6]:
            lines.append("- " + " | ".join(row))
        lines.append("")

    lines.append(f"\n## 亚盘（{len(yazhi)} 家）\n")
    lines.append("| 公司 | 即时主水 | 盘口 | 即时客水 | 即时时间 | 初始主水 | 初始盘口 | 初始客水 | 初始时间 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in yazhi:
        lv, it = r["live"], r["init"]
        lines.append(
            f"| {r['company']} "
            f"| {lv.get('home_water','')} | {lv.get('handicap','')} | {lv.get('away_water','')} | {lv.get('time','')} "
            f"| {it.get('home_water','')} | {it.get('handicap','')} | {it.get('away_water','')} | {it.get('time','')} |"
        )

    lines.append(f"\n## 欧赔（{len(ouzhi)} 家）\n")
    lines.append("| 公司 | 即时 胜/平/负 | 初始 胜/平/负 | 即时概率 | 即时返还 | 即时凯利 | 更新 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in ouzhi:
        def j(pair_key, which, sep="/"):
            p = (r.get(pair_key) or {}).get(which) or []
            return sep.join(p) if p else ""
        lines.append(
            f"| {r['company']} "
            f"| {j('odds','live')} | {j('odds','init')} "
            f"| {j('prob','live')} | {j('ret','live')} | {j('kelly','live')} "
            f"| {r.get('time','')} |"
        )

    md = "\n".join(lines) + "\n"

    full = {
        "frontmatter": fm_meta,
        "shuju": shuju,
        "yazhi": yazhi,
        "ouzhi": ouzhi,
    }
    return md, json.dumps(full, ensure_ascii=False, indent=2)


def render_index(matches_with_gameid: list[dict]) -> tuple[str, str]:
    """
    matches_with_gameid: 已经带 gameid 的场次列表，按 league 分组渲染。
    只包含"有 gameid"（即五大联赛且成功找到 gameid）的场次。
    """
    now = _now_iso_utc()
    by_league: dict[str, list[dict]] = {}
    for m in matches_with_gameid:
        by_league.setdefault(m["league"], []).append(m)

    fm = {
        "last_updated_utc": now,
        "total_matches": len(matches_with_gameid),
        "leagues_covered": sorted(by_league.keys()),
    }
    lines = [_fm(fm), "# 今日五大联赛对阵\n"]

    # 按联赛分组，每组按 matchnum 排序
    for league in sorted(by_league.keys()):
        items = sorted(by_league[league], key=lambda x: x["matchnum"])
        lines.append(f"\n## {league} ({len(items)})\n")
        lines.append("| 编号 | 日期 | 对阵 | 胜/平/负 | gameid |")
        lines.append("|---|---|---|---|---|")
        for m in items:
            spf = f"{m.get('spf_win','')}/{m.get('spf_draw','')}/{m.get('spf_lost','')}"
            lines.append(
                f"| {m['matchnum']} | {m['date']} {m.get('dayofweek','')} "
                f"| {m['home']} vs {m['away']} | {spf} "
                f"| [{m['gameid']}](matches/{m['gameid']}.md) |"
            )

    md = "\n".join(lines) + "\n"
    idx_json = {"last_updated_utc": now, "matches": matches_with_gameid}
    return md, json.dumps(idx_json, ensure_ascii=False, indent=2)


def render_meta(matches_with_gameid: list[dict]) -> str:
    meta = {
        "last_updated_utc": _now_iso_utc(),
        "total_matches": len(matches_with_gameid),
        "leagues_covered": sorted({m["league"] for m in matches_with_gameid}),
        "gameids": sorted([m["gameid"] for m in matches_with_gameid]),
    }
    return json.dumps(meta, ensure_ascii=False, indent=2)


def write_site(
    matches_with_gameid: list[dict],
    per_match_payloads: dict[str, tuple[str, str]],  # gameid -> (md, json)
    dry_run: bool = False,
) -> list[Path]:
    """
    写出所有 site/ 文件。
    旧的 matches/*.md/json 会被清空：避免滞留已下架的场次。
    返回写入的文件路径列表。
    """
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    MATCHES_DIR.mkdir(parents=True, exist_ok=True)

    # 清理旧的单场文件
    if not dry_run:
        for f in MATCHES_DIR.iterdir():
            if f.is_file() and f.suffix in {".md", ".json"}:
                f.unlink()

    written: list[Path] = []

    # 单场
    for gameid, (md, js) in per_match_payloads.items():
        p_md = MATCHES_DIR / f"{gameid}.md"
        p_js = MATCHES_DIR / f"{gameid}.json"
        if not dry_run:
            p_md.write_text(md, encoding="utf-8")
            p_js.write_text(js, encoding="utf-8")
        written += [p_md, p_js]

    # 索引
    idx_md, idx_json = render_index(matches_with_gameid)
    p_idx_md = SITE_DIR / "index.md"
    p_idx_js = SITE_DIR / "index.json"
    if not dry_run:
        p_idx_md.write_text(idx_md, encoding="utf-8")
        p_idx_js.write_text(idx_json, encoding="utf-8")
    written += [p_idx_md, p_idx_js]

    # meta
    p_meta = SITE_DIR / "_meta.json"
    if not dry_run:
        p_meta.write_text(render_meta(matches_with_gameid), encoding="utf-8")
    written.append(p_meta)

    return written
