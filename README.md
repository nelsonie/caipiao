# caipiao · 500 五大联赛数据站（AI Agent 可读）

每小时从 trade.500.com / odds.500.com 抓取当日售卖中的五大联赛（英超/西甲/德甲/意甲/法甲）对阵、亚盘、欧赔、数据分析，生成 Markdown + JSON 快照，部署到 Cloudflare Pages 供 AI Agent 消费。

## 布局

- `scraper/` — Python 抓取 + 解析 + 渲染
- `site/` — Cloudflare Pages 根目录（Build command 留空，Output dir = `site`）
  - `SKILL.md` — AI Agent 使用指南，访问入口
  - `index.md` / `index.json` — 今日全部场次索引
  - `_meta.json` — 最后更新时间
  - `matches/{gameid}.md` / `matches/{gameid}.json` — 单场详情

## 跑起来（本地）

```bash
cd scraper
python3 -m venv ../.venv
../.venv/bin/pip install -r requirements.txt
../.venv/bin/python fetch.py               # 完整抓取+写入 site/
../.venv/bin/python fetch.py --dry-run     # 只打印不写盘
```

## 跑起来（服务器 cron）

```
0 */1 * * * /opt/caipiao/scraper/run.sh >> /var/log/caipiao.log 2>&1
```

`run.sh` 负责：git pull → python fetch.py → 无变化不 commit → git push。

## 部署 Cloudflare Pages

1. 把本仓库推到 GitHub
2. Cloudflare Pages → Connect to Git
3. Build command 留空；Build output directory 填 `site`
4. 拿到 `<project>.pages.dev` 后，替换 `site/SKILL.md` 里 `site_root` 字段
