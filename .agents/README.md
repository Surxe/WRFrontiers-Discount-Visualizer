# Agent documentation

`.agents/` is the single source of truth for all agent-facing documentation in
this repo:

- `rules/` - always-relevant constraints (currently none; placeholder).
- `skills/` - on-demand procedures and knowledge, one directory per skill, each
  with a `SKILL.md` whose frontmatter `name` + `description` is the only part a
  tool preloads. The full body loads only when the tool judges the skill
  relevant, so keep the `description` a sharp trigger.

This mirrors the pattern used by the sibling repo WRFrontiersDB-Site, so guidance
stays structured the same way across both.

## Per-tool setup

Each AI tool discovers skills (and rules, where supported) from its own
directory. Rather than duplicate content, those directories are **symlinks back
into `.agents/`**. They are gitignored and must be recreated per checkout.

### Linux / macOS / git-bash / WSL

```bash
bash .agents/setup-symlinks.sh
```

Idempotent - run it after any fresh clone. It creates:

| Link                | Target          | Used by      |
| ------------------- | --------------- | ------------ |
| `.claude/skills`    | `.agents/skills` | Claude Code  |
| `.windsurf/skills`  | `.agents/skills` | Windsurf     |
| `.windsurf/rules`   | `.agents/rules`  | Windsurf     |
| `.cursor/skills`    | `.agents/skills` | Cursor       |
| `.cursor/rules`     | `.agents/rules`  | Cursor       |

### Windows (plain Command Prompt)

`ln -s` is unavailable, so use directory junctions instead. Open Command Prompt
as Administrator and run, for each tool dir you use (`/D` makes a directory
junction):

```bat
mklink /D "%CD%\.claude\skills"   "%CD%\.agents\skills"
mklink /D "%CD%\.windsurf\skills" "%CD%\.agents\skills"
mklink /D "%CD%\.windsurf\rules"  "%CD%\.agents\rules"
```

## Notes

- Claude Code discovers skills only from `.claude/skills/<name>/SKILL.md`. A
  skill whose instruction file is named anything else will not be loaded, so
  every skill's agent file is `SKILL.md`.
- The `.claude/` directory is a gitignored mirror; the pre-existing
  `.claude/RESUME.md` is an untracked local note and coexists with the
  `.claude/skills` symlink this script creates.
- The Astro app lives under `src/frontend/`, but `.agents/` sits at the repo
  root (where Claude Code is launched), so skills apply repo-wide.
- Claude Code does not auto-load `rules/`; only skills are symlinked into
  `.claude/`. Rules reach Claude only if promoted into a repo-root `CLAUDE.md`
  (deliberately out of scope here).
