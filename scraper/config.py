"""抓取配置。URL 模板外置，便于 500 网路径再次变动时只改这里。"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = REPO_ROOT / "site"
MATCHES_DIR = SITE_DIR / "matches"

# 数据源
JCZQ_INDEX_URL = "https://trade.500.com/jczq/?playid=269&g=2"
XML_SPF_URL = "https://trade.500.com/static/public/jczq/newxml/pl/pl_spf_2.xml"
XML_NSPF_URL = "https://trade.500.com/static/public/jczq/newxml/pl/pl_nspf_2.xml"

# 单场页模板
DETAIL_URLS = {
    "shuju": "https://odds.500.com/fenxi/shuju-{gameid}.shtml",
    "yazhi": "https://odds.500.com/fenxi/yazhi-{gameid}.shtml",
    "ouzhi": "https://odds.500.com/fenxi/ouzhi-{gameid}.shtml",
}

# HTTP
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
CONCURRENCY = 4
DETAIL_ENCODING = "gb18030"  # 500 网单场页用 GBK，gb18030 是 GBK 的超集
