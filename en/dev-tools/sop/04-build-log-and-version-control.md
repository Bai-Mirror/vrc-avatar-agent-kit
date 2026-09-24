> 🌐 English translation · [中文原文](../../../开发工具/SOP/04_施工记录与版本管理.md)

# 04 · Work log and version control　🤖

> **One `_施工记录.md` per project + workspace git.** Set by the author on 2026-09-18; it is mandatory rule 6.
> Purpose: whoever takes over at any time can answer "how far this project has got, how each step was verified, and which step to roll back to if something broke", without relying on the model's memory.

## 1. Work log

**Location**: `<工程根>/_施工记录.md`, one per project. **Append only, never edit old entries** (if you wrote something wrong, append a correction). The only exception is the **status header** at the top of the file (between `<!-- 状态头:BEGIN/END -->`: stage / most recent step / next step / pending / do-not-touch), which may be rewritten as a whole and is maintained by `log_step.py` → [Wrap-up distillation and status header](04-build-log-and-version-control/wrapup-distillation-and-status-header.md).

**When to write**: write after each completed step; don't save it up until the end of the day —
changed project files, changed assets, ran a test or audit, the user made a decision or changed something by hand, DSH returned a dispatch.

**Who writes**:

| Who did the work | Who writes |
|---|---|
| Claude changed it directly | Claude |
| DSH changed the project | Dispatch with `--record <工程>`: DSH appends an entry itself and commits via `ws_git.py` (since 09-22); after acceptance, Claude appends an "acceptance" entry with `log_step.py` |
| The user changed it by hand in Unity/Blender | Claude records a "user manual" entry, stating clearly what the user said and what was changed (if unknown, write "unknown, to be confirmed") |

**How to write**: `python3 开发工具/通用工具/log_step.py <工程> --title "55 狐耳缩放改为 k=0.92" --by Claude --did … --verify … --result ✓ --open 无 [--distill "教训"] [--stage/--next/--pending 更新状态头] [--commit "[简称] 一句话" --paths …]`; `--show` reads the status header and the latest 3 entries. When writing by hand, follow this format:

```markdown
## 2026-09-18 21:40 · 55 Fox ear scale changed to k=0.92
- Executed by: Claude / DSH (session session-xxxx) / user manual
- Changed: localScale of `Acc_FoxEar` in `Assets/_Work/工程C.unity`; `装位报告.md`
- How verified: <tool / criterion / values read>, e.g.: DumpBounds read AABB 0.305×0.164×0.128 m; agy_panel --fast 0 flags
- Result: ✓ / ✗ / unverified (reason)
- Pending: <awaiting decision, leftover issues; if none write "none">
```

**Criterion**: the "how verified" field must be something readable from tool output; if you can't write one, write the result as "unverified".
**Relationship to other documents**: audit reports, assembly reports, and full status tables are topic deliverables; the work log is a **timeline index** — link to them in entries rather than copying their content.

## 2. git

- **New Unity assets: the `.meta` must be committed together with the asset** (tripped on 2026-09-20): after creating a new `.anim`, only the `.anim` was committed, while the controller references it by the GUID in the `.meta` — when someone else pulls, Unity regenerates the GUID and the reference simply goes empty. **Checkable question**: did I create any new assets this time? Has the same-named `.meta` in `git status` been committed? (When giving paths to `ws_git.py commit`, giving a **directory** is safer than individual files; if you give individual files you must list the `.meta` yourself.)

The workspace root `~/vrc-processing` is a git repository (local, no remote).

| In the repo | Not in the repo |
|---|---|
| `CLAUDE.md`, root-level documents, `.claude/` (hooks), all text under `开发工具/` | `<客户素材目录>/`, `_下载暂存/`, `_二次创作/`, the selection atlas, showcase shot images |
| Text assets under a project's `Assets/` `ProjectSettings/` (`.unity` `.prefab` `.anim` `.controller` `.mat` `.asset` `.meta` `.cs`), `Packages/*.json`, md/txt/json at the project root | `Library/ Temp/ Logs/ obj/ UserSettings/`, `*.csproj *.sln`, VPM package directories, `ZZZ_GeneratedAssets/`, `Triturbo/*/Generated/`, `_backup/` |
| | Binaries (FBX, textures, PSD, blend, audio, dll, archives), **any single file > 5 MB** |

**Commits go through one entry point only**:

```bash
python3 开发工具/通用工具/ws_git.py commit -m "[工程C] 55 狐耳缩放改为 k=0.92"
```

It refreshes the > 5 MB exclusion list, scans the content to be committed for API keys, and then commits. `ws_git.py status` summarizes uncommitted changes per project.
Commit messages use `[工程简称] <阶段号> <一句话>` ([project short name] <stage number> <one sentence>), matching the work log entry title. **One step, one commit**; don't mix several steps into one.

**Rollback**: find the commit with `git log --oneline -- <工程>/` → `git checkout <提交> -- <路径>`.
⚠ Before rolling back scenes, prefabs or animations, close Unity or confirm the user isn't editing; refresh in Unity after rolling back;
FBX and textures aren't in the repo — they rely on each project's own restore-point directory (e.g. `_30b还原点/`).

**Trade-offs**:
- The 5 MB line was measured: the text assets of four projects total 2.5 GB, of which 63 files > 5 MB take up 1.27 GB — almost all face-tracking generated meshes, BlendShare data, and vendor AFK animations, all regenerable from the packages; the remaining ~1 GB of YAML goes into the repo.
  Raising it bloats the repo and slows `git status`; lowering it misses large scenes. **If one day a main scene exceeds 5 MB and gets excluded, handle it individually; don't move the line as a whole.**
  **Already handled individually (09-22)**: `<工程>/Assets/_Work/<名>.unity` (the project main scene) has a whitelist limit of 32 MB (`MAIN_SCENE`/`SCENE_LIMIT` in `ws_git.py`, same rule in pre-commit; 625cd03f). Cause: after Project B was split into two avatars, its main scene was 6.28 MB and was removed from version control by `refresh_excludes()` via `git rm --cached`. **Checkable question**: does the main scene appear under "excluded large files" in the commit output? If so, it has exceeded 32 MB or isn't under `_Work/`.
- VPM packages aren't in the repo: versions are frozen in `vpm-manifest.json` and can be restored with `vrc-get resolve`. The cost is that local changes to VPM packages (e.g. `autoReferenced` in the lilToon asmdef) aren't version-controlled; **such changes must be written into the work log**.

- Scripts that parse git output (`git log --name-only`, `diff --name-only`) must always pass `-c core.quotepath=false` themselves: Chinese paths are escaped to `\346\...` by default, and you can't rely on this repo's local config (AZ's replay.py failed to match paths in a clean clone).

> → [ProjectSettings side effects](04-build-log-and-version-control/projectsettings-side-effects.md) — lilToonSetting.json rewritten with the graphics API, Play sets legacyClamp, E-未核-08, re-pack the 7z after fixing dependencies.

## 3. Enforcement mechanisms (why "must write" doesn't rely on self-discipline)

| Mechanism | Where | What it does |
|---|---|---|
| Original text of the mandatory rules | The `强制准则` (mandatory rules) section of `CLAUDE.md` | Loaded at session start; **change the rules only here** |
| Injection hook | `.claude/hooks/rules-inject.js` | Injects the rules on every user message; re-injects every 25 consecutive tool calls; records the times of image views and agy calls |
| Wrap-up gate | `.claude/hooks/stop-gate.js` | Blocks once before ending a turn: project changed but work log not updated / changes not committed / viewed images without sending to agy / reply ends with a question |
| Dispatch gate | `.claude/hooks/delegate-check.js` | When writing to `开发工具/通用工具/`, reminds you to consider dispatching to DSH first |
| git backstop | `开发工具/通用工具/git-hooks/pre-commit` | Blocks files > 5 MB and suspected API keys |
| DSH side | `~/.dsh/skills/vrchat-avatar-sop.md` | DSH can't read CLAUDE.md, so the applicable rules are copied into its skill file |

The hooks are heuristic: a gate blocks only once (`stop_hook_active`); after being blocked, remedy as prompted or explain the exception in the reply.

- **Timestamps come only from the clock**: always write entries with `log_step.py` (it takes the time itself, reads back after writing, and commits in one step with `--commit`); when writing by hand, first run `date +%H:%M` on its own, see the number, then copy it. The story of 20-plus "future time" incidents across four rounds → [Wrap-up distillation and status header §Incidents](04-build-log-and-version-control/wrapup-distillation-and-status-header.md).

- **Concrete incidents when writing logs and committing** (`%` formatting in a heredoc blowing up on the body so the write failed but the commit still went through; a newly created directory missing its own `.meta`) have their own page: [Pitfalls in writing to disk and committing](04-build-log-and-version-control/save-and-commit-pitfalls.md).
