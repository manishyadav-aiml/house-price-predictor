#!/usr/bin/env bash
# S18: scan the whole Git history (not just the latest commit) for likely secrets.
# For a deeper scan also run:  gitleaks detect   or   trufflehog git file://.
PATTERN='(api[_-]?key|secret|passw(or)?d|token|private[_-]?key)["'"'"' ]*[:=]["'"'"' ]*[A-Za-z0-9_\-\/+]{12,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|sk_live_[0-9a-zA-Z]+'
echo "== tracked .env files in history =="; git log --all --name-only --pretty=format: | grep -E '(^|/)\.env($|\.)' | grep -v example | sort -u
echo "== suspicious strings in history =="; git log --all -p | grep -E -i "$PATTERN" | head -50
echo "If anything shows up: rotate that secret first, then clean history (git filter-repo)."
