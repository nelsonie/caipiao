"""入口：抓当日五大联赛全部场次的 析/亚/欧，渲染 site/"""
from __future__ import annotations
import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# 允许直接 `python fetch.py` 运行
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    JCZQ_INDEX_URL,
    XML_SPF_URL,
    DETAIL_URLS,
    CONCURRENCY,
)
from net import get_text, get_detail
from parsers import (
    parse_matches_xml,
    parse_match_index,
    parse_shuju,
    parse_yazhi,
    parse_ouzhi,
)
from render import render_match, write_site

log = logging.getLogger("fetch")


def fetch_one_match(gameid: str) -> tuple[dict, list[dict], list[dict]]:
    """抓析/亚/欧三页，返回 (shuju, yazhi, ouzhi)"""
    s_html = get_detail(DETAIL_URLS["shuju"].format(gameid=gameid))
    y_html = get_detail(DETAIL_URLS["yazhi"].format(gameid=gameid))
    o_html = get_detail(DETAIL_URLS["ouzhi"].format(gameid=gameid))
    return parse_shuju(s_html), parse_yazhi(y_html), parse_ouzhi(o_html)


def main(dry_run: bool) -> int:
    # 1. 抓 XML 对阵列表（全部联赛）
    log.info("fetching XML match list")
    xml = get_text(XML_SPF_URL)
    all_matches = parse_matches_xml(xml)
    log.info("XML total %d matches", len(all_matches))

    if not all_matches:
        log.warning("no matches today; writing empty index")
        write_site([], {}, dry_run=dry_run)
        return 0

    # 2. 抓 jczq HTML 拿 matchnum → {gameid, kickoff_cst, ...}
    log.info("fetching jczq HTML for match index")
    html = get_text(JCZQ_INDEX_URL)
    index_map = parse_match_index(html)
    log.info("match index map: %d entries", len(index_map))

    # 3. Join
    enriched = []
    missing = []
    for m in all_matches:
        meta = index_map.get(m["matchnum"])
        if meta:
            enriched.append({**m, **meta})
        else:
            missing.append(m["matchnum"])
    if missing:
        log.warning("no gameid found for matchnum(s): %s", missing)

    # 4. 并发抓三页 + 解析
    log.info("fetching %d matches (concurrency=%d)", len(enriched), CONCURRENCY)
    per_match_payloads: dict[str, tuple[str, str]] = {}

    def work(match: dict):
        gid = match["gameid"]
        shuju, yazhi, ouzhi = fetch_one_match(gid)
        md, js = render_match(gid, match, shuju, yazhi, ouzhi)
        return gid, md, js, len(yazhi), len(ouzhi)

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futures = {ex.submit(work, m): m for m in enriched}
        for fut in as_completed(futures):
            m = futures[fut]
            try:
                gid, md, js, ny, no = fut.result()
                per_match_payloads[gid] = (md, js)
                log.info("done gameid=%s (%s vs %s): %d yazhi, %d ouzhi",
                         gid, m["home"], m["away"], ny, no)
            except Exception as e:
                log.exception("failed gameid=%s (%s vs %s): %s",
                              m.get("gameid"), m.get("home"), m.get("away"), e)

    # 5. 渲染
    successful = [m for m in enriched if m["gameid"] in per_match_payloads]
    log.info("writing %d match payloads to site/ (dry_run=%s)", len(successful), dry_run)
    files = write_site(successful, per_match_payloads, dry_run=dry_run)
    for f in files:
        log.info("  %s%s", "[dry] " if dry_run else "", f.relative_to(f.parents[1]))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="不实际写文件")
    args = ap.parse_args()
    sys.exit(main(dry_run=args.dry_run))
