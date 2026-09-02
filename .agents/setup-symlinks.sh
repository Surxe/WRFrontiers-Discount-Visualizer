#!/usr/bin/env bash
#
# Link the per-tool agent directories to the .agents source of truth.
#
# .agents/ is the single source of truth for agent rules and skills. Each AI
# tool discovers skills/rules from its own directory, so we mirror the relevant
# .agents subdirectories into each tool dir with relative symlinks. The tool
# dirs are gitignored; this script recreates them on any checkout.
#
# Run from anywhere:  bash .agents/setup-symlinks.sh
# Re-running is safe (idempotent): existing correct links are left alone,
# stale links are replaced.
#
# Windows note: git-bash / WSL run this as-is. In a plain Command Prompt use
# the equivalent `mklink /D` junctions documented in .agents/README.md.

set -euo pipefail

# Resolve repo root as the parent of this script's directory (.agents/..).
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
cd "$repo_root"

# tool_dir/link_name -> .agents/target
# Claude Code and Windsurf discover skills from <tool>/skills; the .agents
# rules are additionally mirrored where a tool consumes a rules/ directory.
links=(
  ".claude/skills:../.agents/skills"
  ".windsurf/skills:../.agents/skills"
  ".windsurf/rules:../.agents/rules"
  ".cursor/skills:../.agents/skills"
  ".cursor/rules:../.agents/rules"
)

link_one() {
  local link_path="$1" target="$2"
  mkdir -p "$(dirname "$link_path")"

  if [ -L "$link_path" ]; then
    if [ "$(readlink "$link_path")" = "$target" ]; then
      echo "ok    $link_path -> $target"
      return
    fi
    rm "$link_path"
  elif [ -e "$link_path" ]; then
    echo "skip  $link_path (exists and is not a symlink; leaving untouched)" >&2
    return
  fi

  ln -s "$target" "$link_path"
  echo "link  $link_path -> $target"
}

for entry in "${links[@]}"; do
  link_one "${entry%%:*}" "${entry#*:}"
done

echo "Done. Tool directories are mirrors of .agents/ and are gitignored."
