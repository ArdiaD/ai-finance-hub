#!/usr/bin/env bash
# Weekly discovery run. Fetches new papers into the local inbox and notifies you
# to review them. Curation, site build, and the LinkedIn draft stay manual
# (human-in-the-loop), so this script intentionally stops after `fetch`.
#
# Schedule it (see README) with launchd or cron, e.g. Mondays at 08:00.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

# shellcheck disable=SC1091
source .venv/bin/activate

LOG="$HERE/data/logs/weekly_$(date +%F).log"
mkdir -p "$HERE/data/logs"

python -m aifinhub fetch | tee "$LOG"

# Export the fresh inbox to Excel for manual yes/no/feature review on Dropbox.
python -m aifinhub review-export | tee -a "$LOG"

PENDING=$(python -m aifinhub stats | grep -o "'pending': [0-9]*" | grep -o "[0-9]*" || echo "?")

REVIEW_XLSX="data/excel/review/review_$(date +%F).xlsx"

# macOS desktop notification (no-op elsewhere).
if command -v osascript >/dev/null 2>&1; then
  osascript -e "display notification \"$PENDING papers awaiting review in $REVIEW_XLSX\" with title \"AI & Finance Hub\""
fi

cat <<MSG

Done. Next:
  1. Open  $REVIEW_XLSX  (Dropbox) and fill the decision column.
  2. cd '$HERE' && source .venv/bin/activate
     python -m aifinhub review-import $REVIEW_XLSX
     python -m aifinhub build-site
     git add docs && git commit -m 'weekly update' && git push
     python -m aifinhub draft-post --since 7d
MSG
