#!/bin/sh
# usage: cd <ワークスペース> && run.sh claude|codex|pi
# launchd や cron から、定期の整理を CLI で回す（launchd は WorkingDirectory にワークスペースを書く）。スケジューラーのあるアプリでは、アプリに登録する（../schedule.md）。
set -eu
case ${1:-} in claude|codex|pi) ;; *) sed -n '2,3p' "$0" >&2; exit 2 ;; esac
PATH=$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/local/bin:$PATH  # launchd の PATH は短い（python3 も 3.11 以上のものを先に見つける）
PROMPT=$(cat "$(dirname "$0")/../prompt.txt")
PLUGIN=$(cd "$(dirname "$0")/../../.." && pwd)  # このスクリプトのあるプラグインの根元。$0 が相対パスのことがあるので、cd の前に決める
# GitHub から入れた Claude Code のプラグインは ~/.claude/plugins/cache/ の下から読まれ（run.sh を指すマーケットプレイスの写しとは別の場所）、-p では許しなしに読めない（run.md などが開けない。2026-10-26 に確かめた）
CACHE=$HOME/.claude/plugins/cache; [ -d "$CACHE" ] || CACHE=
# ワークスペース: 今いるフォルダから上へ desk.toml、なければ ~/.desk.toml の workspace（desk.py）。リンクをたどった実際のパスで、Claude Code がメモリに使うものと同じ
ROOT=$(python3 "$(dirname "$0")/../../../lib/desk.py") || exit 2
cd "$ROOT"
MEM=$HOME/.claude/projects/$(printf %s "$ROOT" | tr '/._' '---')/memory
echo "== $(date '+%F %T') desk-dreaming $1"
case $1 in
claude) claude -p "$PROMPT" --permission-mode auto --add-dir "$MEM" --add-dir "$PLUGIN" ${CACHE:+--add-dir "$CACHE"} ;;
codex) codex exec -C "$ROOT" -s workspace-write --skip-git-repo-check --add-dir "$MEM" "$PROMPT" ;;
pi) pi -p "$PROMPT" ;;
esac
