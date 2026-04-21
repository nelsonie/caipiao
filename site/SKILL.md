---
name: caipiao-500-big5
description: 500 彩票网竞彩足球五大联赛（英超/西甲/德甲/意甲/法甲）当日对阵、亚盘、欧赔、数据分析快照。回答赛前盘口/赔率/交战历史类问题。
data_source: trade.500.com / odds.500.com
update_frequency: 约每小时一次，精确时间戳见 _meta.json 与每个场次 frontmatter 的 fetched_at_utc
site_root: https://caipiao.niexingxing.com
---

# 使用指南

这是一份给 AI Agent 读的数据集说明。以下所有路径都以 `site_root` 为根。

## 1. 判断数据时效

先 GET `_meta.json`：

```json
{
  "last_updated_utc": "2026-04-21T07:30:00Z",
  "total_matches": 10,
  "leagues_covered": ["英格兰超级联赛", "西班牙甲级联赛", ...],
  "gameids": ["1373121", ...]
}
```

如果 `last_updated_utc` 超过 2 小时前，数据可能已过期，回答时应明确告知用户。

## 2. 发现今日全部场次

GET `index.md`（人话式）或 `index.json`（结构化）。

`index.json` 结构：
```json
{
  "last_updated_utc": "...",
  "matches": [
    {
      "xml_id": "2039243", "matchnum": "周三004", "date": "2026-04-22",
      "dayofweek": "星期三", "league": "西班牙甲级联赛",
      "home": "马洛卡", "away": "巴伦西亚",
      "spf_win": "5.12", "spf_draw": "3.80", "spf_lost": "1.49",
      "spf_updated": "2026-04-21 13:27", "gameid": "1373121"
    },
    ...
  ]
}
```

## 3. 获取单场详情

用 `gameid` 拼路径：

- `matches/{gameid}.md` — Markdown：frontmatter 带核心字段，body 是三份数据的 pipe table
- `matches/{gameid}.json` — 同数据 JSON 版，原始更完整

### frontmatter 字段（YAML）
```yaml
gameid: 1373121
matchnum: 周二001
date: 2026-04-21
league: 英格兰超级联赛
home: 伯恩利
away: 曼彻斯特城
kickoff_cst: null            # 预留，当前版本可能为空
spf: {win: 2.52, draw: 4.08, lost: 2.05}   # 500 网竞彩 SP
asia_main:                    # 第一家主流亚盘的即时数据（仅摘要）
  handicap: 半球
  home_water: "0.830↓"
  away_water: "0.780↑"
  company: 威**尔
euro_main:                    # 第一家欧赔公司的即时数据（仅摘要）
  win: "1.83"
  draw: "3.15"
  lost: "3.76"
  company: 竞*官*
fetched_at_utc: 2026-04-21T07:30:00Z
```

### body 三个小节
- `## 交战 & 战绩` — 来自析页：双方近 N 次交战的战绩描述，双方联赛排名，最近 6 场对阵比分
- `## 亚盘（N 家）` — pipe table：每家公司一行，含即时/初始的主水、盘口、客水、时间
- `## 欧赔（N 家）` — pipe table：每家公司一行，含即时/初始胜平负赔率、概率、返还率、凯利指数

## 4. 典型触发场景

用户问：
- "今天英超谁打谁？" → 1) 读 `index.json` 2) 按 `league == "英格兰超级联赛"` 过滤 3) 列出 home/away + spf
- "皇马这场亚盘？" → 1) 读 `index.json`，按 `home == "皇家马德里"` 或 `away == "皇家马德里"` 找到 gameid 2) 读 `matches/{gameid}.md` 的亚盘表
- "凯利指数最高的公司？" → 读 `matches/{gameid}.json`，从 `ouzhi[].kelly.live` 排序

## 5. 回答时的免责与时效

- 数据来源必须注明"500 彩票网"
- 必须包含 `last_updated_utc` 作为时效说明
- 赔率可能已变化，回答时告知用户以实际购彩平台为准
- 不做投注建议
