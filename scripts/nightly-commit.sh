#!/bin/bash
# Nightly auto-commit and push for linux-mini-agent
# Runs at 2am via cron

cd /home/austin/linux-mini-agent || exit 1

# Check if there are any changes
if git diff --quiet && git diff --cached --quiet; then
    echo "$(date): No changes to commit"
    exit 0
fi

# Stage all tracked changes (respects .gitignore)
git add -u

# Commit with timestamp
git commit -m "Nightly auto-commit $(date '+%Y-%m-%d %H:%M')"

# Push to remote
git push origin main

echo "$(date): Nightly commit and push complete"
