#!/usr/bin/env bash
# Assemble the static dashboard site into ./site. Used by both GitHub Pages (.github/workflows/pages.yml)
# and Vercel (vercel.json). No build tools: the dashboard is one HTML file plus the committed results JSON.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf site 2>/dev/null || rm -rf site/* 2>/dev/null || true   # a server may hold the dir open on Windows
mkdir -p site/results
cp bench/dashboard.html site/index.html
for f in results.json live.json demo_transcript.txt; do
  [ -f "bench/results/$f" ] && cp "bench/results/$f" site/results/
done
[ -d bench/results/runs ] && cp -r bench/results/runs site/results/runs
sha="${VERCEL_GIT_COMMIT_SHA:-${GITHUB_SHA:-$(git rev-parse HEAD 2>/dev/null || echo unknown)}}"
printf '{"built": "%s", "commit": "%s", "host": "%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${sha:0:7}" "${VERCEL:+vercel}${GITHUB_ACTIONS:+github-pages}" > site/results/meta.json
echo "site/ assembled: $(find site -type f | wc -l) files"
