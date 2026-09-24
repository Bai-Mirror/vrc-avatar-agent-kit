# Architecture and Replication

[中文](../zh/架构与复刻.md) · [Back to README](../../README.en.md)

What each of the six layers contains and why; what you need to replicate it; how to degrade when a layer is missing. Linked SOP pages are in Chinese; translations are under [`en/`](../../en/dev-tools/sop/00-overview.md).

## 1. Six layers

```
┌ Model ───────────── Claude Code lead │ DSH / Codex executors (optional) │ Gemini etc. falsifiers (optional)
├ Orchestration ───── dsh_task.js dispatch │ Claude subagents │ plan → apply → read back
├ Tool access ─────── Unity MCP │ Blender MCP │ agy MCP │ editor scripts │ Python/Blender scripts
├ Knowledge ───────── SOP: overview → stage pages → subpages │ tool index │ toolchain baseline
├ Gates ───────────── 4 Claude Code hooks │ git pre-commit
└ Records & learning  work log + status header │ ws_git │ dispatch journal │ to-distill tags → distillation
```

### 1.1 Model layer

| Role | Default | Responsibility |
|---|---|---|
| Lead | Claude Code | Process control, aesthetic judgment, hard-case fallback, SOP maintenance, iterating on executors, acceptance |
| Executor | DSH (DeepSeek Harness) / Codex CLI, optional | Project edits, analysis scripts, builds and tests, asset inventory |
| Falsifier | agy (Antigravity CLI, calling Gemini etc.); DeepSeek vision, optional | Adversarial review of the lead's conclusions |

**Why**: the lead's quota is the most expensive, and the lead gets anchored by its own context — a conclusion becomes more convincing each time it is restated. Execution goes to cheaper models; conclusions go to a different model on a different subscription to be attacked. See [DSH dispatch](../../en/dev-tools/sop/01-automation-and-parallelism/dsh-delegation.md), [Codex dispatch](../../en/dev-tools/sop/01-automation-and-parallelism/codex-delegation.md), [05 · Multi-model review](../../en/dev-tools/sop/05-multi-model-review.md).

### 1.2 Orchestration layer

| Component | Path | Role |
|---|---|---|
| Dispatcher | `开发工具/通用工具/dsh_task.js` | One entry point for DSH or Codex (`--engine auto` picks by time of day); `--lock unity|blender` hands over the editor; `--record <project>` makes the executor write its own work-log entry and commit; `--snapshot-cmd` diffs state before and after; afterwards it verifies from the session log what the executor actually did (e.g. counts `read_image` calls on image tasks, one missing image = FAIL); memory and concurrency gates |
| Session review | `dsh_session.js`, `dsh_snapshot.js`, `dsh_usage.js` | Session logs, snapshot diffs, usage |
| Orchestration rule | [01 · Automation and parallelism](../../en/dev-tools/sop/01-automation-and-parallelism.md) | Produce plans in parallel → apply once, serially → read back |
| Brief writing | [Subagent prompts](../../en/dev-tools/sop/01-automation-and-parallelism/subagent-prompts.md), [Step templates and hard stops](../../en/dev-tools/sop/01-automation-and-parallelism/step-templates-and-hard-gates.md) | Eight-part structure that weaker models can follow correctly |

**Why**: the parallelism boundary is not the dependency graph but the single Unity instance — reading, judging and pose computation can fan out; scene edits, baking and Play mode must queue. So tools come as paired "plan / apply" entry points: plans run in parallel and can go to weak models; apply queues once and is followed immediately by a read-back. Executors fail silently (an image accepted but never looked at; a write that never reached disk), so verification uses session logs and snapshots, not the executor's own report.

### 1.3 Tool access layer

| Component | Path / source | Role |
|---|---|---|
| Unity MCP | `com.coplaydev.unity-mcp` (version in [Project setup and first compile](../../en/dev-tools/sop/02-environment-and-manual-intervention/project-setup-and-first-compile.md)) | Read/write scenes, run editor code, run tests |
| Blender MCP | Blender extension (local port) | `bpy` access to vertices, bones, shape keys |
| agy MCP | `开发工具/通用工具/agy_mcp_server.js` | Wraps multi-model falsification as two tools, `agy_review` and `agy_ask`, shared by lead and executors |
| Unity editor scripts | `开发工具/通用工具/*.cs`, `审查/unity/`, `生成/`, `部件图鉴/` | Performance report, PhysBone census and merging, parameter audit, build-blocker scan, menu assertions, part-atlas captures |
| Python / Blender / shell | `开发工具/通用工具/*.py`, `*.sh` | Shape-key measurement, texture tiering, unpacking, `unity_run.sh` (launch Unity under a memory cap), `unity_recover.sh` (read-only post-crash diagnosis) |
| Tool index | [工具索引](../../en/dev-tools/sop/00-overview/tool-index.md) | Find tools by task |

**Why**: falsification is an MCP tool rather than a command because in long contexts the model forgets to call it; in the tool list it is visible every turn. Editor work goes through `-executeMethod` batch runs where possible and the interactive editor is kept for viewing and editing, because builds and preprocessing in the interactive editor repeatedly triggered graphics crashes.

### 1.4 Knowledge layer

| Component | Path | Role |
|---|---|---|
| Overview | [00_总表](../../en/dev-tools/sop/00-overview.md) | Full stage table, checkpoints, five cross-cutting rules |
| Stage pages | `开发工具/SOP/10_…` to `90_…` | Each opens with a deterministic step table and machine-checkable pass criteria; details in a same-named subdirectory |
| Troubleshooting | [Troubleshooting index](../../en/dev-tools/sop/00-overview/troubleshooting-index.md) | Look up by symptom |
| Toolchain baseline | [_工具链基准](../../en/dev-tools/_toolchain-benchmark.md) | Frozen versions of Unity, the VRChat SDK and plugins, with reasons |

**Why**: executors cannot read the lead's memory, only files, so all technical lessons go into the SOP. Pages stay ≤10 KB and are read on demand, bounding each dispatch's context cost. Every rule states its trade-offs (threshold source, failure modes both ways, what to do when unmet), so a successor can judge a changed number.

### 1.5 Gate layer

| Hook | Event | What it does |
|---|---|---|
| `.claude/hooks/rules-inject.js` | UserPromptSubmit, PostToolUse | Injects the mandatory rules between the two marker lines in `CLAUDE.md` on every user turn and again every 25 consecutive tool calls; records timestamps for image viewing, falsification and dispatch |
| `.claude/hooks/delegate-check.js` | PreToolUse | Warns when the lead edits a project directly (Write/Edit, Bash writes, Unity MCP write actions, Blender code execution); denies from the 3rd edit since the last dispatch unless one of six legitimate exemption categories is declared with `--exempt <category> "<reason>"` |
| `.claude/hooks/stop-gate.js` | Stop | Before a turn ends: project changed but work log not updated or not committed; images viewed after the last falsification; final paragraph ends with a question; direct edits without a recorded reason. Blocks once |
| `.claude/hooks/session-start.js` | SessionStart | On start, resume and after context compaction, runs `baseline_recheck.sh` and injects a read-only reality check (memory, processes, locks, uncommitted changes, status headers) |
| `开发工具/通用工具/git-hooks/pre-commit` | git commit | Blocks files over 5 MB and likely secrets |

**Why**: rules in `CLAUDE.md` enter the context once, then drift away in long or unattended sessions; what was missing was a structural trigger, not memory. Hooks pass silently on parse errors (a hook must not become a failure point) and block only once to avoid loops.

### 1.6 Records and self-learning layer

| Component | Path | Role |
|---|---|---|
| Work log | `_施工记录.md` at each project root | Status header at the top may be rewritten as a block; the timeline below is append-only |
| Log entry point | `开发工具/通用工具/log_step.py` | Appends entries, maintains the status header, `--distill` adds a to-distill tag, `--commit` commits in one step; time comes only from the system clock; read back after writing, no commit on mismatch |
| Commit entry point | `开发工具/通用工具/ws_git.py` | The only commit path for the workspace; excludes large assets automatically |
| Dispatch journal | `_DSH流水账.md` | Appended by `dsh_task.js` on every dispatch, including the executor's "lessons for the SOP" section |
| Distillation input | `开发工具/通用工具/distill_collect.py` | Collects tags, lesson sections and SOP pages changed since a given time |
| Procedure | [End-of-phase distillation and status header](../../en/dev-tools/sop/04-build-log-and-version-control/wrapup-distillation-and-status-header.md) | The full two-layer method and its acceptance checks |

**Why**: an execution session editing the SOP from a tired context produces cross-page contradictions and pages that are split without being shortened; notes written after the fact get rationalized. So symptoms are recorded on the spot (facts and a checkable question only), and a clean-context agent merges them into the SOP in place at the end of a phase. The only exception is a criterion whose absence would break the very next dispatch. Model-estimated times proved unreliable, so time comes only from the clock.

## 2. Replication checklist

### Subscriptions and APIs

| Item | Required? | Use |
|---|---|---|
| Claude Code (Claude subscription or API) | Required | Lead |
| agy (Antigravity CLI) and the Gemini etc. models behind it | Intermediate | Falsification |
| DeepSeek API + DSH | Full, optional | Cheap executor; image tasks need a model alias that declares image input |
| Codex CLI (ChatGPT subscription) | Full, optional | Executor; `dsh_task.js` reads its remaining quota and stops dispatching above a threshold |

### Software

Versions per [_工具链基准](../../en/dev-tools/_toolchain-benchmark.md). Author's environment:

- Unity 2022.3.22f1 + VRChat SDK 3.10.x (projects created with VCC / ALCOM / vrc-get)
- Modular Avatar, NDMF, Avatar Optimizer, lilToon, VRCFury and other VPM packages (frozen per the baseline table; never upgraded mid-order)
- Blender 5.x with an MCP extension
- Node.js (hooks and dispatcher), Python 3 (analysis scripts), git, bash
- The author runs Ubuntu; `unity_run.sh` depends on `systemd-run` and `flock` and must be rewritten or skipped on Windows/macOS

### Hardware

The author uses a Linux workstation with 30 GB RAM and the workspace on NVMe. Concurrency is budgeted by memory, not CPU: an interactive Unity takes about 3–5 GB, a batch import 2–4 GB, a DSH session with its MCP subprocesses about 0.3–0.8 GB. With less memory, lower the dispatcher's gates (`DSH_TASK_MIN_GB`, `DSH_TASK_MAX_SESS`). Rationale: [Memory budget and concurrency](../../en/dev-tools/sop/02-environment-and-manual-intervention/b850-linux-environment/memory-budget-and-concurrency.md).

### MCP servers

Copy `.mcp.example.json` to `.mcp.json` and keep what you need:

- Unity MCP: install `com.coplaydev.unity-mcp` in the project and set Transport to Stdio in its panel (troubleshooting ladder in [02 · Environment and human handoff](../../en/dev-tools/sop/02-environment-and-manual-intervention.md))
- Blender MCP: the Blender extension, with online access enabled in preferences
- agy: `node 开发工具/通用工具/agy_mcp_server.js` (agy must be installed and signed in)

### What to set in `kit.env`

Copy `kit.env.example` to `kit.env` and fill in the real values behind the placeholders used in the SOP and scripts:

| Placeholder | Meaning |
|---|---|
| `<工作区>` | Workspace root (this repository) |
| `<Unity安装根>` | Unity Hub editor install root (containing `Editors/<version>/Editor/Unity`) |
| `<素材库>` | Root of your own purchased-asset library |
| `<存档目录>` | Archive and delivery-package directory |
| `<客户素材目录>` | Where client asset bundles are stored |

Variable names: see comments in `kit.env.example`. Also point hook commands in `.claude/settings.json` and server paths in `.mcp.json` at your machine.

## 3. Fallbacks

| Missing | What to do | What you lose |
|---|---|---|
| DSH / Codex | Use Claude Code `Agent` subagents for execution; write briefs per [Subagent prompts](../../en/dev-tools/sop/01-automation-and-parallelism/subagent-prompts.md) and accept as before (git show, read-back values, rerun criteria). `delegate-check.js` resets its counter only when Bash runs `dsh_task.js`; without the dispatcher, either declare `--exempt` or change the hook so subagent dispatch also resets it | Higher lead quota use; no session-log verification or snapshot diffs |
| agy | For rule 1, spawn a Claude subagent that does not inherit the current context, give it only the material and numbered claims, and require "supports / contradicts / can't tell" per claim (see [05](../../en/dev-tools/sop/05-multi-model-review.md)). `stop-gate.js` recognizes agy / DeepSeek vision calls, not subagent falsification — explain in the reply or adjust the hook | No hedge against a single vendor's biases; same subscription pool |
| Unity MCP | Most editor scripts have menu entries; click them or run `unity_run.sh --batch --method <entry>` | Interactive scene read/write; some audit scripts need a batch entry point |
| Blender MCP | Run `bl_*.py` with `blender --background --python <script>` | Interactive exploration |
| Methods only | Read the SOP; skip the hooks | Rule enforcement |

## 4. Known limitations

- **SOP thresholds are calibrated to the author's base avatars and plugin versions.** Numbers like 0.3 mm seams, 12° angles or 1 mm distance percentiles come from specific base avatars and specific versions of Modular Avatar / AAO / lilToon / the VRChat SDK. Recalibrate after changing base avatars or upgrading plugins; thresholds marked "calibrate per project" or "not measured" in the SOP are not pass criteria as-is.
- **Regression testing is not fully validated.** For body/foot blendshape fitting of clothing, the old methods and scripts are only positive/negative samples; untested tools and thresholds in the current entry point, [70 · Regression testing](../../en/dev-tools/sop/70-regression-testing.md), still need per-project calibration.
- **Hooks are coupled to naming conventions.** The hooks treat any top-level directory containing `ProjectSettings/ProjectVersion.txt` as a project; they use the names `_施工记录.md`, `_任务账本.md`, `_长程任务_*`, `_DSH流水账.md`, `开发工具/SOP/` and `CLAUDE.md` to tell the lead's own files from project files; `rules-inject.js` extracts the rules between `<!-- 强制准则:BEGIN -->` and `<!-- 强制准则:END -->`. Renaming any of these requires updating the matching regexes in `.claude/hooks/`.
- **Directory names are Chinese.** Scripts and hooks reference them by path; renaming a directory means a global replace plus a run of `开发工具/通用工具/check_links.py` for broken links.
- **The dispatcher parses specific CLI session-log formats**; DSH/Codex log changes require updating its verification.
- **Linux-first.** Paths, process management and Unity launch assume Ubuntu; Windows is not systematically covered.
- **Cases are anonymized.** Originals behind "工程A…G" (Projects A–G) and provenance markers are not public; cited line numbers cannot be checked here.
