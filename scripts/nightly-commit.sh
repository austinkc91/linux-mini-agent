#!/bin/bash
# Nightly auto-commit and push for linux-mini-agent
# Runs at 2am via cron — backs up ALL project files (respects .gitignore)

cd /home/austin/linux-mini-agent || exit 1

# Stage ALL changes including new untracked files (respects .gitignore)
git add -A

# Check if there's anything to commit after staging
if git diff --cached --quiet; then
    echo "$(date): No changes to commit"
    exit 0
fi

# Commit with timestamp
git commit -m "Nightly auto-commit $(date '+%Y-%m-%d %H:%M')"

# Push to remote
git push origin main

echo "$(date): Nightly commit and push complete"
