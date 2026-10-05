#!/usr/bin/env bash
# One headless run: ./run.sh <repo> <question> <arm: ctl|cg|cgf> <rep>
# Writes runs/<repo>-<question>-<arm>-<rep>.jsonl (stream-json). Skips if it already exists.
set -euo pipefail
cd "$(dirname "$0")"
repo=$1 q=$2 arm=$3 rep=$4
RUNS=${RUNS:-runs}
out="$RUNS/$repo-$q-$arm-$rep.jsonl"
mkdir -p "$RUNS"
[[ -s $out ]] && grep -q '"type":"result"' "$out" && exit 0

question=$(jq -r --arg r "$repo" --arg q "$q" '.[$r][$q]' questions.json)
prompt="$question

This is a read-only task: do not edit files. Answer with file:line references."

if [[ $arm == ctl ]]; then
  dir="repos/$repo-ctl"; mcp=(--strict-mcp-config)
else
  dir="repos/$repo"; mcp=(--mcp-config "$PWD/mcp-codegraph.json" --strict-mcp-config)
fi
[[ $arm == cgf ]] && prompt="Start by calling the codegraph_explore MCP tool, and use it before grep or reading files.

$prompt"

cd "$dir"
# env -u: a shell-exported API key would override the subscription login and bill API credit.
env -u ANTHROPIC_API_KEY claude -p "$prompt" \
  --model "${MODEL:-claude-opus-5-5}" \
  --output-format stream-json --verbose --include-hook-events \
  --setting-sources project,local \
  "${mcp[@]}" \
  --allowedTools 'Read' 'Grep' 'Glob' 'Bash' 'mcp__codegraph__*' \
  --disallowedTools 'Edit' 'Write' 'NotebookEdit' 'Agent' \
  --no-session-persistence \
  > "../../$out" 2> "../../$out.err"
