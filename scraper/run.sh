#!/usr/bin/env bash
# Cron 包装：git pull → scraper → 有变化才 commit+push
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# 允许通过环境变量指定 python 二进制，默认用 .venv/bin/python，再降级到系统 python3
PY="${CAIPIAO_PY:-$REPO_ROOT/.venv/bin/python}"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3)"
fi

echo "=== $(date -u +%FT%TZ) caipiao scrape ==="

git pull --rebase --autostash origin main >/dev/null 2>&1 || true

"$PY" "$REPO_ROOT/scraper/fetch.py"

# 只对 site/ 下的变化做 commit
git add site/
if git diff --cached --quiet; then
  echo "no change; skip commit"
  exit 0
fi

git commit -m "snapshot $(date -u +%FT%TZ)"
git push origin main
echo "pushed."
