> 🌐 English translation · [中文原文](../../../../开发工具/SOP/01_自动化执行与并行/DSH派工.md)

# DSH Dispatch Procedure

> **Hand work to DSH by default.** (User decision 2026-09-08) Claude does only five things (table below); everything else is dispatched.
> This page is required reading before dispatching. The tools are `开发工具/通用工具/dsh_task.js` (dispatch) and `dsh_session.js` (post-mortem).
> **On Beijing weekdays 09-12 and 14-18 peak hours, the same script automatically switches to Codex** (09-23) → [Codex dispatch](codex-delegation.md).

## 1. Division of labor

**Claude does only these five; everything else goes to DSH:**

| Left to Claude | Why it cannot be dispatched |
|---|---|
| **Overall process control** | Requires cross-stage trade-offs and changing the plan itself; DSH only sees one task at a time |
| **Aesthetic assessment** | No closed-form criterion; what is needed is trade-offs and landing points |
| **Complex fallback** | Troubleshooting when DSH STOPs or its conclusions contradict each other |
| **Maintaining the SOP** | Procedures must record trade-offs, not just rules |
| **Iterating and updating DSH** | **Letting DSH modify its own toolchain risks breaking itself** (user decision 2026-09-09). Scope: configuration and patches under `~/.dsh`, `dsh_task.js` / `dsh_session.js` / `agy_mcp_server.js`, MCP wiring, hooks, skills. If needed, an Opus subagent within Claude may do it, but not DSH |

**Deciding sentence**: can the output of this task be directly confirmed by some tool call? Yes → dispatch to DSH.
No, and it requires synthesizing judgment across evidence → keep it with Claude.

⚠ **When unsure, lean toward dispatching.** The costs are asymmetric: a wrong dispatch costs a few minutes and a little DeepSeek quota (cheap),
while not dispatching and doing it yourself burns Claude quota (expensive, and a hard constraint).

### ⚠ General tool development and debugging **must be dispatched**; **DSH's own toolchain is not**

**Dispatch**: project-side analysis scripts — parsing `.anim` / `.prefab` / `.meta`, computing criteria, producing lists.
These are not among the five things left to Claude.

**Do not dispatch**: DSH's own stack (`~/.dsh` configuration and patches, `dsh_task.js` / `dsh_session.js` /
`agy_mcp_server.js`, MCP wiring, hooks, skills). **The reason is not that it cannot do it well, but that it would be modifying what it itself runs on** —
if broken, even the error might not make it back. These belong to Claude (dispatch an Opus subagent within Claude if needed).

**Project edits are dispatched too; Claude accepts and records them** (user 09-22): dispatch with `--record <project>`, DSH writes the work log and commits itself, and the script checks the record-keeping with git;
Claude's acceptance checklist, the six exemption categories and gate behavior → **[Project-edit dispatch and acceptance](project-edit-delegation-and-acceptance.md)**.
“All the context is in my head, briefing it is costly” is **not** a legitimate reason.

Structural gates: `.claude/hooks/delegate-check.js` (PreToolUse, Write/Edit/Bash/Unity/Blender; the 3rd direct project edit since the last dispatch is denied) + `stop-gate.js`.
At phase wrap-up, check the dispatch ratio once with `dsh_session.js stats`.
**Counterexamples, trade-offs of the four reasons, how to self-check** → [Dispatch boundaries and self-check](delegation-boundaries-and-selfcheck.md)

## 2. Models, pricing and vision capability boundaries → [DSH model and vision capability](dsh-model-and-vision-capability.md)

Read before choosing a model (images use `vision`, Pro hard-banned) or judging whether an image task can be dispatched.

## 3. How to dispatch

```bash
node 开发工具/通用工具/dsh_task.js \
  --model flash --images "路径1,路径2" \
  --cwd "$PWD" --task-file 任务书.md [--timeout 3600] [--record <工程> | --no-record] [--lock unity|blender] \
  [--json 结果.json] [--brief <速查档>] [--doc <写回文档>]
```
The journal is written to `_DSH流水账.md` by default (`--no-journal` turns it off); with `--lock` you must declare `--record`/`--no-record`, otherwise the dispatch is refused.
When no timeout is given, a task brief >2000 characters or with ≥3 list items gets 3600 seconds, otherwise 900 seconds; multi-step tasks should still explicitly get 3600, and re-dispatches first pick up the half-finished work.

**Balance (added by the author 09-23)**: before dispatching / after each batch run `python3 开发工具/通用工具/dsh_balance.py`. Only add new tasks on exit 0; stop dispatching once the balance falls below the reserve line (`DSH_RESERVE_CNY`, configured in kit.env or via `--reserve-cny`); at low balance the lead takes on necessary small tasks, and large batches wait for the user's decision. A failed query also pauses new tasks; do not merge currencies, do not use old environment keys.

### Two hard money-saving rules (user decision 2026-09-09)

**① Merge multiple questions about the same batch of material into one task brief.**
Context is not shared across sessions; splitting the same material into 4 dispatches means ingesting it 4 times (measured on the foot task).

**② Use `--brief` to point at the project quick-reference file; do not let it re-scan raw files.**
The quick-reference file replaces repeated scanning with verified conclusions. `--brief` requires checking the file first, reading raw assets only for missing items and reporting “missing X, read Y additionally”.
**Maintain one `_工程速查.md` per project, and update it after each round.**

**Where outputs land**: DSH's final answer goes to **stdout** (the verification block goes to stderr; the two are separate for easy scripting);
`--json` writes “answer + verification verdict + tool-call list + session directory” together into a structured file.
**If you want it to produce files, hard-code absolute paths in the task brief**; do not expect to fish them out of stdout — it can only write inside the workspace.

| Exit code | Meaning | **What to do next** |
|---|---|---|
| `0` | Finished and verification passed | Accept, but still review conclusions per the iron rule in section 6 |
| `1` | Pre-dispatch snapshot failed or DSH failed | Check JSON/problems and stderr; a non-zero/timed-out/truncated/unwritten snapshot must not proceed to dispatch; fix the cause first, do not blindly re-run |
| **`2`** | **Finished but verification failed** | **Do not blindly re-run.** First read `problems` in `--json`:<br>· Model mismatch → go to `~/.dsh/settings.yaml` and delete the `agent-default-model` section<br>· Images not read → check whether the paths exist and whether the shim was used (see pitfall ③)<br>· Wrap-up not completed → read the session log to see where it got stuck, then narrow the scope and re-dispatch |

### 3.1 ⚠ Long task briefs always go through `--task-file`; do not inline with `--task`
**Backticks** in the task brief are executed by bash as command substitution — the content vanishes from the prompt, and it still hands in a decent-looking answer (measured: inline 4/6 correct, file 6/6).
**Any task brief over three lines, or containing backticks/quotes/`$`/`!`, is written to a .md first and passed with `--task-file`.** Arguments not fully delivered are harder to detect than it doing something wrong.

## 3.2 Minimal task-brief structure (six items; missing any one causes problems)

The eight-section structure of [Subagent prompts](subagent-prompts.md) applies too, but dispatching DSH needs at least these six:

1. **One sentence stating what this route is responsible for**, which step of the process, and whether prerequisites are done.
2. **Verified facts** (write “use directly, do not re-verify”). ⚠ This section has the greatest benefit and also the greatest risk —
   every number in it must be one you personally verified; **wrong numbers will be executed as written, not questioned**.
3. **Verifiable criteria**: what counts as done. Criteria must be directly confirmable by some tool call.
4. **Read-back requirement**: whenever assets are generated/modified, state “after changing, read back to verify and report the values read”.
   For cross-tool assets (FBX exported from Blender for Unity), **a round-trip check in the source tool does not count as acceptance** — on 2026-09-19 a nipple-pasty copy was 0.000 mm in Blender but skinned 71 mm off in Unity. The task brief states “the world-coordinate difference of Unity's `BakeMesh` against the original prevails, verified by Claude”; whatever can be done directly in Unity (adding frames to a mesh) should not detour through Blender.
5. **Fallback for missing tools**: explicitly write “if X is not in the tool list, report `NO-X-TOOLS` directly; do not guess” —
   MCP is configured with `failOnStartupError: false`, so tools **silently disappear** when the connection fails;
   this item distinguishes “the tool was not attached” from “it lazily did not call it”.
6. **Output paths as absolute paths**, and they must be inside the workspace (sandbox below).

> ⚠ **DSH runs in the `workspace-write` sandbox**: `workspaceRoot` is the directory passed via `--cwd`,
> and **it cannot write outside the workspace** (including `~/.dsh`). So actions like “changing DSH configuration / adding MCP / deleting a settings section”
> **can only be done on the Claude side and cannot be dispatched to DSH**. If loosening is truly needed, use the `DSH_PERMISSION_MODE` environment variable,
> but that amounts to removing the guardrail; think it through first.

## 4. ⚠ Six silent failures (none report errors; caught by verification)

Symptoms, criteria, and automated gates → summary table at the top of [DSH silent failures](dsh-silent-failure.md); mechanisms and post-mortems in each section.

## 5. Handoff lock: Unity / Blender can be held by only one side at a time

The Claude side and the DSH side connect to the **same** Unity editor and the **same** Blender add-on socket.
Read-only concurrency was measured without blowing up (both sides running `get_objects_summary` simultaneously worked), **but write operations must be exclusive**.

- `--lock unity` / `--lock blender` writes `~/.dsh/handoff.lock`; when it is held by someone else, the dispatch is refused outright.
- Before Claude itself touches Unity/Blender, it also reads this file first.
- The lock only protects “who is writing”; it does not guarantee the other side left a clean state — **the first thing after handoff is to re-observe; do not trust readings from before the handoff**.

## 6. Post-mortem: gather evidence from session logs, not from its self-report

```bash
node 开发工具/通用工具/dsh_session.js list          # list sessions: model/turns/tools/wrap-up
node 开发工具/通用工具/dsh_session.js show latest --reasoning
node 开发工具/通用工具/dsh_session.js grep "read_image"
node 开发工具/通用工具/dsh_session.js stats
```

The log contains `user/message`, `assistant/message`, **`reasoning` (thought process)**,
`tool/call`, `tool/result`, `request/header` (real model and effort).

**Iron rule of acceptance**: any “conclusion that could not be reached without performing that action” is not accepted —
the way to tell is whether its `tool/call` entries can support the conclusion.
It is when it reports “I'm done, no problems” that you should review most carefully.

**When it reports “the X you gave has a problem”, handle it in this order** (neither changing things as it says, nor ignoring it):
① First assume it is right — it has no reason to fabricate a conclusion that makes things harder for itself;
② **Verify that item yourself** (read files, run scripts, extract numbers); do not just look at its wording;
③ If verified, first fix that error in the task brief, then narrow the scope and re-dispatch; if not, hard-code the correct value in the task brief,
   and record this misjudgment in [Troubleshooting/troubleshooting record procedure](../troubleshooting/troubleshooting-log-procedure.md).

> ⚠ The “suspected failures” of `stats` use a broad regex that over-reports rather than under-reports; review each one before concluding.

## 7. Environment facts

See [DSH capability and modification · Environment facts](dsh-capability-and-modification.md). When the environment changes, go sync that section.

Related: [Subagent prompts](subagent-prompts.md) (the eight-section structure also applies to writing DSH task briefs),
[Subagent dispatch](subagent-dispatch.md), [05 multi-model review procedure](../05-multi-model-review.md).
