#!/bin/bash
# Push to GitHub using token from env (no interactive login).
# Create token: https://github.com/settings/tokens -> Generate new token (classic), scope: repo
# Then: export GITHUB_TOKEN=ghp_xxxx && ./push.sh

set -e
cd "$(dirname "$0")"

if [ -z "$GITHUB_TOKEN" ]; then
  echo "Set GITHUB_TOKEN first. Example: export GITHUB_TOKEN=ghp_xxxx"
  echo "Create token: https://github.com/settings/tokens"
  exit 1
fi

git push "https://ItsOrv:${GITHUB_TOKEN}@github.com/ItsOrv/telegram-ssh-bot.git" main
