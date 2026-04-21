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

def parse_shuju(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    out: dict = {}

    title = soup.title.get_text(strip=True) if soup.title else None
    out["title"] = title

    # 双方交战历史摘要："双方近<6>次交战，..."
    hist_header = soup.find("span", class_="his_info")
    if hist_header:
        out["h2h_summary"] = hist_header.get_text(" ", strip=True)

    # 球队排名（含 [K1联赛3] 这种标签）
    ranks: list[str] = []
    for tn in soup.select(".team_name"):
        t = tn.get_text(" ", strip=True)
        if t and t not in ranks:
            ranks.append(t)
    out["team_ranks"] = ranks

    # 交战历史 rows：表头带"比分"的表
    h2h_rows: list[list[str]] = []
    for h4 in soup.find_all("h4"):
        if "交战历史" in h4.get_text():
            table = h4.find_next("table")
            if table:
                for tr in table.select("tbody tr")[:10]:
                    cells = [td.get_text(" ", strip=True) for td in tr.select("td")]
                    if cells:
                        h2h_rows.append(cells)
            break
    out["h2h_rows"] = h2h_rows

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
