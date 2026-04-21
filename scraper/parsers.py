"""解析：XML 对阵列表 + jczq 首页（matchnum→gameid 映射）+ 析/亚/欧 三个单场页。"""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup


# -------- XML 对阵列表 --------

def parse_matches_xml(xml_text: str) -> list[dict]:
    """解析 pl_spf_2.xml, 返回全部 <m> 节点（含首条 <row> 的 SP 值）"""
    root = ET.fromstring(xml_text)
    out = []
    for m in root.findall("m"):
        row = m.find("row")
        rec = {
            "xml_id":    m.get("id"),
            "matchnum":  m.get("matchnum"),
            "date":      m.get("date"),
            "dayofweek": m.get("dayofweek"),
            "league":    m.get("league"),
            "home":      m.get("home"),
            "away":      m.get("away"),
            "spf_win":   row.get("win")  if row is not None else None,
            "spf_draw":  row.get("draw") if row is not None else None,
            "spf_lost":  row.get("lost") if row is not None else None,
            "spf_updated": row.get("updatetime") if row is not None else None,
        }
        out.append(rec)
    return out


# -------- jczq 首页 matchnum → gameid --------

def parse_match_index(html_text: str) -> dict[str, dict]:
    """
    从 /jczq/?playid=269&g=2 的 HTML 里抽 matchnum → {gameid, kickoff_cst, matchnum_label, ...}。

    每场 <tr> 上的关键 data-* 属性：
      - data-processname="2001"     ← XML 里的 matchnum
      - data-matchnum="周二001"      ← 人话版编号
      - data-id="2039240"           ← XML 里的 id
      - data-matchdate/time         ← 开赛时间
      - data-homeid / data-awayid   ← 球队 ID
    每行下还有 <a href="/fenxi/shuju-{gameid}.shtml">"析"</a>。
    """
    soup = BeautifulSoup(html_text, "lxml")
    mapping: dict[str, dict] = {}
    for tr in soup.find_all("tr", attrs={"data-processname": True}):
        processname = tr.get("data-processname")
        a = tr.find("a", href=re.compile(r"/fenxi/shuju-(\d+)\.shtml"))
        if not a:
            continue
        gid = re.search(r"/fenxi/shuju-(\d+)\.shtml", a["href"]).group(1)
        kickoff = None
        d, t = tr.get("data-matchdate"), tr.get("data-matchtime")
        if d and t:
            kickoff = f"{d} {t}"
        mapping[processname] = {
            "gameid":          gid,
            "kickoff_cst":     kickoff,
            "matchnum_label":  tr.get("data-matchnum"),
            "xml_id":          tr.get("data-id"),
            "home_team_id":    tr.get("data-homeid"),
            "away_team_id":    tr.get("data-awayid"),
        }
    return mapping


# -------- 析 / 亚 / 欧 三个单场页 --------

_PLAYER_RE = re.compile(r"^(?:(\d+))?\s*(.+?)\s*\(([^)]+)\)\s*$")


def _parse_player_cell(text: str) -> dict | None:
    """'19兹安·弗莱明(前锋)' → {number:'19', name:'兹安·弗莱明', position:'前锋'}"""
    text = text.strip()
    if not text:
        return None
    m = _PLAYER_RE.match(text)
    if m:
        return {"number": m.group(1), "name": m.group(2), "position": m.group(3)}
    return {"number": None, "name": text, "position": None}


def _section_by_h4(soup: BeautifulSoup, keyword: str) -> "BeautifulSoup | None":
    """找到 h4 文本包含 keyword 的那个 M_box 顶层容器"""
    for h4 in soup.select("div.M_title > h4"):
        if keyword in h4.get_text():
            # M_title 上溯到 M_box
            return h4.find_parent(class_="M_box")
    return None


def _parse_match_row(tr) -> dict:
    """
    交战历史 / 近期战绩 的行拆成 dict。
    典型列：赛事 | 日期 | 主-比分-客 | (半场) | 赛果 | (欧指) | (亚盘) | 盘路 | 大小 | 备注
    不强拆列数，统一按 header 对齐。
    """
    cells = [td.get_text(" ", strip=True) for td in tr.find_all("td", recursive=False)]
    return {"cells": cells}


def _th_clean_text(th) -> str:
    """去掉 th 里的 <select>/<option>/<em>/<i>/<input> 等噪音后再取文本"""
    clone = BeautifulSoup(str(th), "lxml").th
    if clone is None:
        return th.get_text(" ", strip=True)
    for tag in clone.find_all(["select", "option", "input", "i"]):
        tag.decompose()
    return clone.get_text(" ", strip=True)


def _parse_team_record_table(container) -> dict:
    """近期战绩：一侧（team_a 或 team_b）的表 + 底部 summary"""
    out: dict = {"team": None, "summary": None, "matches": []}
    name_el = container.select_one("strong.team_name")
    if name_el:
        out["team"] = name_el.get_text(strip=True)
    bottom = container.select_one(".bottom_info p")
    if bottom:
        out["summary"] = bottom.get_text(" ", strip=True)
    # matches
    table = container.select_one("table.pub_table")
    if table:
        rows = table.select("tr")
        if not rows:
            return out
        header = [_th_clean_text(th) for th in rows[0].find_all("th")]
        for tr in rows[1:]:
            # 跳过隐藏的"本场"提示行
            if "bmatch" in (tr.get("class") or []):
                continue
            tds = tr.find_all("td", recursive=False)
            if not tds:
                continue
            vals = [td.get_text(" ", strip=True) for td in tds]
            if header and len(header) == len(vals):
                out["matches"].append(dict(zip(header, vals)))
            else:
                out["matches"].append({"cells": vals})
    return out


def _parse_future_fixtures_side(container) -> list[dict]:
    out = []
    table = container.select_one("table.pub_table")
    if not table:
        return out
    rows = table.select("tr")
    if not rows:
        return out
    header = [th.get_text(" ", strip=True) for th in rows[0].find_all("th")]
    for tr in rows[1:]:
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue
        vals = [td.get_text(" ", strip=True) for td in tds]
        if header and len(header) == len(vals):
            out.append(dict(zip(header, vals)))
        else:
            out.append({"cells": vals})
    return out


def _parse_lineup_side(container) -> dict:
    """
    一侧的阵容块（container 是 team_a 或 team_b div）。
    返回 {formation, starters, subs, injured, suspended}
    """
    out = {"formation": None, "starters": [], "subs": [], "injured": [], "suspended": []}
    # "XX阵型: xxx" — team_name div
    name_div = container.select_one(".team_name")
    if name_div:
        txt = name_div.get_text(" ", strip=True).replace("\xa0", " ")
        if "阵型" in txt:
            # 示意文本："伯恩利阵型: 4-3-3"；"阵型:" 后可能为空
            part = txt.split("阵型", 1)[-1].lstrip(":：").strip()
            out["formation"] = part or None

    table = container.select_one("table.pub_table")
    if not table:
        return out

    # table 是混合的：第 1 段 首发/替补，第 2 段 伤病/停赛。
    # 根据 th 行切片。
    current_buckets: tuple[str, str] | None = None  # (left_bucket_name, right_bucket_name)
    bucket_map = {"首发": "starters", "替补": "subs", "伤病": "injured", "停赛": "suspended"}

    for tr in table.find_all("tr", recursive=False):
        ths = tr.find_all("th", recursive=False)
        if ths:
            labels = []
            for th in ths:
                raw = th.get_text(" ", strip=True).strip("- ").strip()
                labels.append(bucket_map.get(raw))
            # 只有当两侧都能映射到桶时才切换
            if len(labels) >= 2 and all(labels[:2]):
                current_buckets = (labels[0], labels[1])
            continue
        if not current_buckets:
            continue
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 2:
            continue
        for bucket, td in zip(current_buckets, tds[:2]):
            p = _parse_player_cell(td.get_text(" ", strip=True).replace("\xa0", " "))
            if p:
                out[bucket].append(p)
    return out


def parse_shuju(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    out: dict = {"title": None}

    if soup.title:
        out["title"] = soup.title.get_text(strip=True)

    # 双方摘要
    hist_header = soup.find("span", class_="his_info")
    if hist_header:
        out["h2h_summary"] = hist_header.get_text(" ", strip=True)

    # 球队排名（来自 M_sub_title 的 team_name span，过滤掉 "XX阵型:" 这类）
    ranks: list[str] = []
    for tn in soup.select("div.M_sub_title .team_name"):
        t = tn.get_text(" ", strip=True)
        if t and "阵型" not in t and t not in ranks:
            ranks.append(t)
    out["team_ranks"] = ranks

    # 交战历史 rows：h4 含"交战历史" 的 M_box 下面的 pub_table
    h2h_rows: list[dict] = []
    box = _section_by_h4(soup, "交战历史")
    if box:
        table = box.select_one(".M_content table.pub_table")
        if table:
            rows = table.select("tr")
            if rows:
                header = [_th_clean_text(th) for th in rows[0].find_all("th")]
                for tr in rows[1:]:
                    # 跳过本场 bmatch 的行
                    if "bmatch" in (tr.get("class") or []):
                        continue
                    tds = tr.find_all("td", recursive=False)
                    if not tds:
                        continue
                    vals = [td.get_text(" ", strip=True) for td in tds]
                    if header and len(header) == len(vals):
                        h2h_rows.append(dict(zip(header, vals)))
                    else:
                        h2h_rows.append({"cells": vals})
    out["h2h_rows"] = h2h_rows

    # 近期战绩
    recent = {"home": {}, "away": {}}
    box = _section_by_h4(soup, "近期战绩")
    if box:
        chart = box.select_one("div.odds_zj_tubiao")
        if chart:
            ta = chart.select_one("div.team_a")
            tb = chart.select_one("div.team_b")
            if ta: recent["home"] = _parse_team_record_table(ta)
            if tb: recent["away"] = _parse_team_record_table(tb)
    out["recent_form"] = recent

    # 未来赛事
    future = {"home": [], "away": []}
    box = _section_by_h4(soup, "未来赛事")
    if box:
        content = box.select_one("div.M_content")
        if content:
            ta = content.select_one("div.team_a")
            tb = content.select_one("div.team_b")
            if ta: future["home"] = _parse_future_fixtures_side(ta)
            if tb: future["away"] = _parse_future_fixtures_side(tb)
    out["future_fixtures"] = future

    # 预计阵容
    lineup = {"home": {}, "away": {}}
    box = _section_by_h4(soup, "预计阵容")
    if box:
        content = box.select_one("div.M_content")
        if content:
            ta = content.select_one("div.team_a")
            tb = content.select_one("div.team_b")
            if ta: lineup["home"] = _parse_lineup_side(ta)
            if tb: lineup["away"] = _parse_lineup_side(tb)
    out["lineup"] = lineup

    return out


def parse_yazhi(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for tr in soup.select('tr[xls="row"]'):
        a = tr.select_one("td.tb_plgs a")
        if not a:
            continue
        company = a.get("title") or a.get_text(strip=True)
        tables = tr.select("table.pl_table_data")
        def row_cells(t):
            return [td.get_text(strip=True) for td in t.select("td")] if t else []
        live = row_cells(tables[0]) if len(tables) > 0 else []
        init = row_cells(tables[1]) if len(tables) > 1 else []
        times = [t.get_text(strip=True) for t in tr.find_all("time")]
        rows.append({
            "cid": tr.get("id"),
            "company": company,
            "live": {
                "home_water": live[0] if len(live) > 0 else None,
                "handicap":   live[1] if len(live) > 1 else None,
                "away_water": live[2] if len(live) > 2 else None,
                "time":       times[0] if len(times) > 0 else None,
            },
            "init": {
                "home_water": init[0] if len(init) > 0 else None,
                "handicap":   init[1] if len(init) > 1 else None,
                "away_water": init[2] if len(init) > 2 else None,
                "time":       times[1] if len(times) > 1 else None,
            },
        })
    return rows


def parse_ouzhi(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for tr in soup.select('tr[xls="row"]'):
        plgs_td = tr.select_one("td.tb_plgs")
        if not plgs_td:
            continue
        a = plgs_td.find("a")
        company = plgs_td.get("title") or (a.get_text(strip=True) if a else None)

        # 页面 HTML 里 td 闭合不规范，直接按 tr 内的 pl_table_data 顺序取：
        # [0]=赔率, [1]=概率, [2]=返还率, [3]=凯利
        tables = tr.select("table.pl_table_data")

        def pair(table):
            if not table:
                return None
            trs = table.select("tr")
            if len(trs) < 2:
                return None
            return {
                "live": [x.get_text(strip=True) for x in trs[0].select("td")],
                "init": [x.get_text(strip=True) for x in trs[1].select("td")],
            }

        if len(tables) < 4:
            continue
        rows.append({
            "cid": tr.get("id"),
            "company": company,
            "time": tr.get("data-time"),
            "odds":  pair(tables[0]),
            "prob":  pair(tables[1]),
            "ret":   pair(tables[2]),
            "kelly": pair(tables[3]),
        })
    return rows
