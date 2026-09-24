# VRChat Avatar Customization Workspace (template, English reference)

> **Read-only translation.** Claude Code and the hooks only read [`CLAUDE.md`](CLAUDE.md). `.claude/hooks/rules-inject.js` extracts the text between the `<!-- 强制准则:BEGIN -->` and `<!-- 强制准则:END -->` lines of `CLAUDE.md` and injects it on every user turn (and every 25 tool calls). Editing this English file changes nothing at runtime.
> If you want English rules injected, translate the text **between the markers in `CLAUDE.md`** and keep the two marker lines exactly as they are (a newline must follow the BEGIN line).

Business: a client sends an asset bundle; the work in Unity/Blender covers face shaping, colorways, outfit fitting, menus, optimization and delivery.
Machine paths, archive locations and launch commands belong in `开发工具/SOP/02_环境准备与人工介入.md` and its subpages, not here.

## Mandatory rules (injected by the hook each turn)

1. **Falsify.** Before a visual conclusion, or any conclusion I have already restated twice or more, goes into a reply or drives the next step, send it to a different model for falsification (agy/Gemini etc.; if none, a subagent that does not inherit this session's context). Self-check: was the input of my latest falsification call *my conclusion*, or *whether the tool works*?
2. **Evidence.** Before reporting "done / fixed / there is no X", have tool output from this turn to back it. After a change, confirm it actually landed on disk and took effect (the value changed, the object moved), and gather evidence from a viewpoint that could expose a problem.
3. **Check the source first.** Before acting, read the vendor's notes and showcase images, the PSD/CLIP source files, the existing mechanism (who drives it, how many states, layer weight) and plugin version compatibility. Do not guess from object names or impressions.
4. **Pacing.** Before a new order or a large rework, align requirements and plan with the user via AskUserQuestion. During execution do not stop to report; raise questions through AskUserQuestion and keep working on whatever does not depend on the answer. Never end a turn with a question in the reply body.
5. **Delegate.** Execution work goes to an execution agent by default (DSH/Codex, optional; otherwise Claude subagents) — **including project edits** (Unity assets/scenes/menus/animator layers, delivery docs, builds and tests): write a brief, run `dsh_task.js --record <project> [--lock unity]`, and the agent appends the work log and commits via ws_git. The lead agent only does process control, aesthetic judgment, hard-case fallback, SOP maintenance, iterating on the execution agents, and **acceptance** (git show --stat, reading values back, rerunning criteria). Before editing a project directly, run `node .claude/hooks/delegate-check.js --exempt <category> "<reason>"`; the hook blocks the 3rd direct edit since the last dispatch.
6. **Work log.** After every step (project change, asset change, test run, user decision), append to that project's `_施工记录.md` with `开发工具/通用工具/log_step.py <project> --title … --did … --verify … --result … --open … [--commit]` and commit (timestamps come only from the clock; read back after writing, do not commit on mismatch). When taking over, read the status header first with `log_step.py <project> --show`.
7. **Two-layer records.** When you hit a wall or the user corrects you, tag the log entry "待蒸馏" (to-distill) on the spot (`log_step.py --distill "trigger moment + checkable question"`); **execution sessions do not edit the SOP body**. At the end of a phase, a clean-context agent runs `distill_collect.py` and merges the material into the SOP in place (procedure: `开发工具/SOP/04_施工记录与版本管理/收尾蒸馏与状态头.md`). Only a criterion whose absence would make the very next dispatch fail may go into the SOP immediately, noted in the tag.
8. **Read economically.** Batch multiple questions about the same material into one read; briefs longer than three lines go into a file; do not re-read large files or logs in full.

## Read first

1. `开发工具/SOP/00_总表.md` — the full stage table, checkpoints and cross-cutting rules. **Open only the page for the stage you are in.**
2. Before touching Unity/Blender/execution agents/falsification tools: `开发工具/SOP/02_环境准备与人工介入.md`.
3. Taking over a project: read its `_施工记录.md` (status header + append-only timeline), then the **newest** topic document in the project root (by mtime; do not trust old handover notes). Log and git rules: `开发工具/SOP/04_施工记录与版本管理.md`.

## Directory layout (adapt to yours)

The hooks and tools depend on some of these conventions; rename them together with the hooks (see "Known limitations" in [docs/en/architecture.md](docs/en/architecture.md)).

| Path | Meaning |
|---|---|
| `COMM-<order-id>_<client>/` | One Unity project per client order. Hooks treat any top-level directory containing `ProjectSettings/ProjectVersion.txt` as a project; its root holds `_施工记录.md` (work log) and `_任务账本.md` (task ledger) |
| `<nickname>_<base-avatar>_<date>/` | Personal orders without an order id; otherwise the same |
| `<client-assets>/` | Client asset bundles, single copy, read-only |
| `开发工具/` | Cross-order assets: `SOP/` (procedures), `通用工具/` (scripts) |
| `_长程任务_<date>_<topic>/` | Long-running cross-project tasks: briefs, ledgers, dispatch briefs, review output |
| `_DSH流水账.md` | Appended automatically by `dsh_task.js` on each dispatch; do not edit |
| `_归档/` | Archived documents; **not current state** |

## Division of labor (hard constraints)

The lead agent is Claude Code. Execution agents are optional: DSH (DeepSeek Harness) and Codex are dispatched through the same `开发工具/通用工具/dsh_task.js` (`--engine auto|dsh|codex`); without either, use Claude subagents.

- **Delegate by default.** The lead only does process control / aesthetic judgment / hard-case fallback / SOP maintenance / iterating on execution agents / acceptance. Saving lead-agent usage is a hard goal; when unsure, delegate.
- **Project edits are delegated too**; the lead verifies and records.
- **Structural gates**: `delegate-check.js` blocks the lead from editing projects directly (deny from the 3rd edit since the last dispatch; six legitimate exemption categories declared with `--exempt`); `stop-gate.js` requires direct edits and exemption reasons to be written into the work log before the turn ends.
- **Third-party falsification** before adopting any visual or load-bearing conclusion (`agy_panel.py`, MCP `agy_ask`/`agy_review`; `开发工具/SOP/05_多模型评审规程.md`).
- **External review** needed for workspace tasks runs without per-call approval; send only what is needed (docs, script/config text, images, the claims under test). This is not publication, and no unrelated credentials are sent.
- Unity and Blender may be launched freely; Play mode in self-launched sessions and restarts after crashes are handled by the agent (restore ProjectSettings changed by Play afterwards). Panel GUI actions, exiting a Play session **the user is using**, and SDK uploads go to the user.
- **Ask before irreversible actions**: deleting archives, overwriting delivery packages, discarding scene changes, force-exiting Play. Unexpected scene state is first assumed to be a human edit.

## Documentation rules

- Technical lessons go into the SOP (execution agents can read the SOP but not the lead's memory); memory holds only collaboration preferences, project status and resource locations.
- One SOP page ≤10 KB, split into subpages beyond that; UTF-8 without BOM, LF; every rule states its trade-offs (where the threshold came from, what to do when it cannot be met, the cost of each error type).
- Grep for an existing equivalent entry before writing; edit it in place instead of adding a duplicate.
