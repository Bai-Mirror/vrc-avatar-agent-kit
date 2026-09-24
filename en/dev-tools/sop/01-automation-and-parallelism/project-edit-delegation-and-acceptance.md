> 🌐 English translation · [中文原文](../../../../开发工具/SOP/01_自动化执行与并行/改工程派工与验收.md)

# Project-Edit Dispatch and Acceptance

> ← [DSH dispatch](dsh-delegation.md). The user decided on 2026-09-22: **project edits are dispatched to DSH as well; Claude accepts and records them**; and asked for this to be baked into the process rather than relying on reminders.
> Origin: an entire round of removing the base avatar's hairstyle in Project B (editing the controller, deleting objects, dismantling vendor layers, reclaiming parameters, editing delivery notes, writing the work log) was done by Claude itself via
> `execute_code` and python/sed in Bash; the old gate only watched for "writes to `开发工具/通用工具/`" and never fired once.

## Trigger moment and checkable question

**Trigger**: the next step will **change** the state of some file or some Unity object in the project — editing assets/scenes/menus/animator layers/materials, deleting objects, editing delivery documents,
running build/test menus, entering Play to collect evidence.
**Question**: can the result of this step be confirmed by a single tool call (read-back value, git diff, a line in a report)? Yes → write a task brief and dispatch.

Read-only investigation, read-backs, grep and reading reports **do not count**; do them yourself as usual (that is the acceptance).

## How to dispatch

```bash
node 开发工具/通用工具/dsh_task.js --model flash --cwd "$PWD" \
  --record <工程目录> [--lock unity] --task-file <任务书.md> --timeout 3600
```

- **`--record <project dir>`**: automatically appends hard record-keeping requirements to the end of the task brief — append to that project's `_施工记录.md` (title tagged “(DSH)”,
  four sections: what was done / how it was verified / result / open items), `ws_git.py commit` naming only the paths changed, and report `已提交: <hash>` at the end of the reply;
  after the run the script checks with git: there is a commit containing the work log after the dispatch started, and no uncommitted changes remain under the project. Missing either is judged FAIL (exit code 2), and the verification block gets an extra “record-keeping” line.
- **Baseline-diff acceptance (user decision 09-23, B3)**: project-edit dispatches add `--snapshot-cmd "<read-only command>"` (repeatable); `dsh_task.js` runs it once before and once after the dispatch, stores it in `_dsh_tmp_snapshots/<timestamp>/`, and prints the number of differing lines in the verification block; `--record` without a snapshot command produces a warning. Claude defines the commands (e.g. `python3 开发工具/通用工具/dump_vrc_menu.py <工程>`, `grep -c blendShape <clip>`, `sha256sum <资产>`); DSH cannot touch them. **No difference** before/after while DSH claims it made changes → FAIL; differences outside the expected fields → examine each one in acceptance step 3.
- **A dispatch with `--lock` but without `--record` / `--no-record` is rejected outright**: touching the editor requires declaring first whether the project will be changed. Pure read-only investigation uses `--no-record`. `--record` only accepts project directories that have `_施工记录.md` (with the underscore); long-running task directories (such as the tongue-piercing chain's `施工记录.md`) are rejected as “does not look like a project directory” — use `--no-record` instead and state in the task brief that DSH appends the record itself and commits by named paths (hit on 09-22 in L5-4b).
- **The journal is on by default**, writing `_DSH流水账.md` at the workspace root (`--no-journal` turns it off). ⛔ Before 09-22 the old version treated the argument after `--journal` as a path,
  so `--journal --json x` wrote into a file called “--json”; after 09-19 three journal entries landed in the wrong place (since moved back).

### What Claude must hard-code in the task brief (beyond the six items in [DSH dispatch 3.2](dsh-delegation.md))

1. **State readings before starting** (whether the scene is dirty, current values of key fields) — the first thing it does after handoff is re-observe, so give it a baseline to compare against.
2. **How to trigger heavy work**: full builds and NDMF/VRCFury preprocessing follow the [memory budget](../02-environment-and-manual-intervention/b850-linux-environment/memory-budget-and-concurrency.md) and use `unity_run.sh --project <工程> --batch --method <入口>`, not the interactive editor. Only measurements/renders that must stay in the editor and may exceed 20 seconds use `delayCall`, a request ID, a single-flight lock and a completion file; this must not be used to bypass the build restriction. “The third one always crashes” has been disproven by evidence that the first build also crashes.
3. **What must not be touched**: explicitly say “do not enter Play / do not quit Unity / do not touch assets not named”.
4. **Outfit fitting, building/editing menus, building part atlases**: include the fixed lines from section 1 of [DSH execution notes](../50-outfit-and-hair-assembly/part-understanding-and-menu-layout/dsh-execution-points.md) (look up records by product ID, what to do when a record is missing, blind labeling, ATLAS-DIR-NOT-EMPTY).
5. **Where to stop on failure**: if a criterion fails, **do not fix it** — paste the original output back; fixes that need Claude's judgment must not be improvised by it.

Snapshots must execute successfully and be written to disk: if the before-snapshot fails, do not dispatch; if the after-snapshot fails, it does not participate in the business diff and acceptance fails. JSON `snapshots.executions` records exit code/signal/error; error text does not count as a change, and line order and duplicate lines must not be dropped.

## Claude's acceptance (this is Claude's job, done every time)

| # | What to check | How |
|---|---|---|
| 1 | Verification block | Exit code 0, “record-keeping ✓ commit <hash>”; for exit code 2 read `problems` in `--json` first |
| 2 | Scope of changes | `git show --stat <hash>`: only the expected paths; inspect every extra one |
| 3 | Values really written | Read back key values yourself with one **read-only** call (asset fields, `CalcTotalCost()`, scene object state) or grep the file; do not trust its self-report |
| 4 | Report and quotations | Compare the readings it pasted word for word against the original report/log |
| 5 | Work log | DSH's entry has all four sections, and its readings match steps 3 and 4 |
| 6 | Snapshot diff and output **content** match its **metadata** | When the output is a data file (weights, parameter table, list), sample one field and compare it against both “the previous version” and “recomputed with the new algorithm”: equal to the previous version means it was not written back. 09-23 tongue-piercing chain: `舌头权重_参考.json` had `algorithm`/`checks` stating box kernel w6, but `weights` was 494/494 equal to v1 (the script computed `W2` but did not write it back); L5-5 acceptance only looked at metadata, the downstream sweep and renders all used the old weights, and it was only caught at the L6-A regression |

After acceptance, append a line under DSH's entry: `> 验收（Claude，HH:MM）：通过 / 不通过——<证据一句>` (acceptance (Claude, HH:MM): pass / fail — <one-sentence evidence>), then `ws_git.py commit`.
On failure: state clearly what is missing, re-dispatch (stating “continue from the half-finished work”) or handle it as a fallback; **do not silently finish it yourself**.

## Structural gates (hooks, not self-discipline)

- **`.claude/hooks/delegate-check.js`** (PreToolUse: Write/Edit/Bash/Unity MCP/Blender code execution):
  when it judges that Claude is directly editing a project or writing project-side tools, it reminds on the 1st and 2nd time since the last DSH dispatch, and **denies from the 3rd time on**.
  For Bash it examines each piece of write evidence (redirect targets, write-command arguments, file-writing APIs inside interpreters) and where it lands; heredoc data bodies (task brief, work-log text) do not count;
  Claude's own territory (SOP, CLAUDE.md, `.claude/`, `_长程任务_*`, the journal, each project's `_施工记录.md`, `/tmp`) does not count.
- **Dispatch resets the counter**: when `rules-inject.js` sees Bash run `dsh_task.js`, it resets the count to zero.
- **`stop-gate.js`**: at wrap-up, if this session has new direct edits → it blocks once, requiring the work log to state why they were not dispatched, and dispatching the remaining edits of the same kind.
  The uncommitted-changes check skips: project directories with `--record`, and **files changed after any running DSH dispatch started** (09-22: the gate forced Claude to make an “in-progress save” of the asset-notes directory DSH was writing, sweeping up DSH's in-progress files and mislabeling the commit message). Claude must not make whole-directory commits of directories DSH is writing.

### Legitimate exceptions: declare first, then act

```bash
node .claude/hooks/delegate-check.js --exempt <类别> "<理由>"
```

Only six categories are accepted, valid for 20 minutes, each logged to `~/.cache/vrc-rules/exempt.log`:

| Category | Example |
|---|---|
| `不可逆` (irreversible) | Deleting archives, overwriting delivery packages — these must be asked of the user anyway; after asking, Claude does it personally |
| `红线` (red line) | Operations near keys or the read-only client-asset area |
| `用户确认` (user confirmation) | Small adjustments that need back-and-forth confirmation with the user, editing while asking |
| `维护SOP` (maintain SOP) | Editing the procedures themselves (usually does not trigger; the SOP directory is already allowed) |
| `迭代DSH` (iterate DSH) | Editing DSH's own toolchain (`dsh_task.js` etc. are already allowed; this refers to their copies inside projects) |
| `兜底` (fallback) | Troubleshooting after DSH exit code 1/2 or STOP; **write the session or exit code in the reason** |

“All the context is in my head”, “it's just one line”, “dispatch round-trips are too slow” are **not** legitimate reasons.
Restarting Unity after a crash or clearing `Temp/UnityLockfile` is environment recovery; declare it as fallback.

## Trade-offs

- **Why block only on the 3rd time**: the first two reminders leave room for cases that “really only need one line and are about to be dispatched”; measured rounds of project edits easily involve a dozen-plus direct edits, so three is enough to stop it at the start.
- **Why the exemption lasts 20 minutes rather than per-use**: fallback troubleshooting is often several consecutive steps; per-use declarations turn the reasons into a running log; a time window + per-entry logging + recording in the work log at wrap-up is auditable after the fact.
- **Cost of a false positive**: one more exemption declaration; **cost of a false negative**: another round of Claude quota burned on execution work. So Bash is judged somewhat broadly on purpose.

## DSH self-verification only verifies its own assumptions (09-22 H-07)
**Trigger**: DSH reports self-verification like “all N combinations, 0 differences, PASS”.
**Facts**: in H-07 round 2, DSH self-verified 382 combinations, all passing; Claude ran an independent check (several read-only subagents gathering evidence from YAML/source code + dispatching someone to try to refute each FAIL) and still confirmed 5 defects — all **outside the premises** of DSH's self-verification: the real build chain changed WD (it simulated WD=False), radial-puppet intermediate values and remote quantization (it only tested whole-step values), renderers with more than 4 slots (the generator loop hard-coded 3 slots, and the self-check only covered one outfit), and which field MA actually uses as the menu name.
**Practice**: for deliveries like menus/animator layers and recoloring that “have many combinations and are verified by reasoning”, switch perspective during acceptance: ① real build-chain semantics (what VRCFury/MA/NDMF will change); ② boundaries and intermediate values (radial midpoints, k/127 quantization); ③ coverage (every item, every slot, no sampling); ④ which field a tool actually reads (read the plugin source). Independent-check conclusions must be reproducible by a second person (give path:line).
