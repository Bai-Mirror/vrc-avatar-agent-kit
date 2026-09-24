> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/02_环境准备与人工介入/B850_Linux环境/内存预算与并发.md)

> ← [This machine (Linux) Linux environment](../b850-linux-environment.md)

# Memory Budget and Concurrency (2026-09-22 OOM Incident)

**Incident**: at 20:28 on 09-22 the kernel OOM killer killed the entire systemd scope containing the Claude app (`app-com.anthropic.Claude-*.scope`, peak 22.3 GB memory + 5.6 GB swap). **Everything started from a Claude session lives in this scope**: two interactive Unity instances, one batch-import Unity, a background Blender, about 9 DSH sessions (3 H-05 ones each also opening nested vision sessions) + the MCP child processes each DSH brings along — all died together, and Claude itself was restarted. Cost: DSH outputs written but uncommitted, the Unity editor and import queue interrupted, shadow credentials left in temporary directories.
This machine has 30 GB of total memory (`free -g`; the 14 GB in old documents was from before the machine migration).

## Checkable questions (before dispatching / starting heavy processes)
1. How much is available in `free -g`? **Below 8 GB, do not start new DSH sessions or batch Unity.**
2. How many DSH sessions are there now? `pgrep -fc "bin.js --profile headless"` (nested vision sessions count too). **≤4 at the same time.**
3. How many interactive Unity instances are open? **With both open, do not run batch imports**; batch imports plus interactive Unity total ≤2 Unity processes.
4. Is the work to dispatch the kind that “opens nested sessions” (blind labeling for part atlases, multi-route agy)? **Dispatch only 1 of these at a time.**

**Structural gate**: `dsh_task.js` checks automatically before dispatching (if available <8 GB or DSH sessions ≥4, it waits in 30 s steps, up to 90 min; adjust thresholds with `DSH_TASK_MIN_GB`/`DSH_TASK_MAX_SESS`, disable with `DSH_TASK_NO_GATE=1`). Nested dispatches cannot see other sessions inside the sandbox, so only the memory check takes effect.

## Launch and recovery go through scripts (2026-09-23 workflow review B4/A6, user decision)
- **Always start Unity with `bash 开发工具/通用工具/unity_run.sh --project <工程> [--batch --method X]`**: checks memory (interactive ≥8 GB, batch ≥6 GB), refuses if the same project already has a live process, `-force-vulkan`, and runs the process in a `systemd-run --user` unit with `MemoryMax` (interactive 14G, batch 10G, adjustable via `--mem`), so exceeding the limit kills only that Unity instead of dragging down the whole Claude process group; batch jobs are serialized machine-wide by one flock.
- **Full builds and NDMF/VRCFury preprocessing are not run in the interactive editor**: all 4 identical Vulkan swapchain crash stacks came from the interactive editor popping progress bars; use `--batch --method <entry>` (`-executeMethod`) instead; the interactive editor is only for viewing and editing.
- **After a crash, `bash 开发工具/通用工具/unity_recover.sh <工程>`**: report only (processes, log tail, locks, MCP status, uncommitted changes); if the process is still alive it exits 1 and prompts to kill first; only `--yes` clears stale locks; `--launch` then reopens through unity_run.sh. It never auto-saves and never checks out.
- **DSH concurrency**: besides pgrep, `dsh_task.js` also counts slot files under `<工作区>/.dsh_slots/` (nested dispatches cannot see processes inside the sandbox but can see slots; measured, nested vision sessions also create slots). **DSH sessions do not get MemoryMax**: a `spawnSync` timeout only kills the direct child, and a `systemd-run --scope` layer leaves orphans; a single session is 0.3–0.8 GB, and the total is controlled by the slot count (≤4). Trade-off: the main OOM culprit is Unity (3–8 GB each), so put that in a cgroup first.

## Trade-offs
- Concurrency is set by memory, not CPU: one interactive Unity is about 3–5 GB, batch import 2–4 GB (more for large projects), one DSH session with MCP children about 0.3–0.8 GB, the Claude app 1–2 GB.
- Prefer queuing: 12 atlas sets like H-05 run serially “1–2 sets at a time”, which beats running 3 concurrently and having OOM knock all of them back.
- Post-incident recovery checklist: delete each project's `Temp/UnityLockfile`, `~/.unity-mcp/unity-mcp-status-*.json`, `~/.dsh/handoff.lock` (when the holder pid is dead); **find `_dsh_tmp*/**/.dsh/.credentials*` and delete the shadow credentials**; check one by one whether the outputs of killed tasks are complete (JSON fields, renders) before deciding whether to write the record on their behalf or re-dispatch.

## Watchdog (resident since 09-22, v2 on 09-23)
- Practice: every 10 s read `MemAvailable`; if < 3 GB, `kill` the **batch** Unity (least important, re-runnable), protecting the interactive editor and DSH.
- **Matching must be anchored to the executable path**: `pgrep -f '^<Unity安装根>/Editors/[^ ]+/Editor/Unity -batchmode'`. v1 used the unanchored `pgrep -f "Editor/Unity -batchmode"`, and at 01:56 on 09-23 it killed “the shell that started it” (whose command line contained the full script text) as the target — any shell whose command line happens to contain that text gets hit.
- Write the script to a file and start it with `bash file`; do not write it with a heredoc and run it in the same command (the parent shell's command line will carry the match string).
- Live situation at 01:56 on 09-23: interactive Unity 7.8 GB (DSH running full preprocessing in it) + MeteorLens batch Unity 5.1 GB + the user's Android emulator 1.5 GB (started by a systemd user service, not ours to manage) → 1 GB available. The “≥8 GB” before starting a batch only checks the starting point; preprocessing in the interactive editor grows another 2–3 GB; **do not start batch jobs while the interactive editor is running full preprocessing**.

## Previous time: with Unity + the user's Blender both open, do not run concurrent headless Blender (2026-09-20 23:53, merged from “Processes and waiting”)

**Trigger moment**: Unity is open on one side, the user also has Blender open, and I want to run `blender --background` for measurement/rendering.

**The scene this time**: this machine's 30 GiB of memory was pushed to **22 GiB used / 1.7 GiB available, swap 13/15 GiB**.
Top consumers: Unity RSS **4.4 GB** (managed 1.6 GB / reserved 2.3 GB), qemu VM 2.5 GB, **opencode ×3 about 1.8 GB**,
claude-desktop ×2 about 1.1 GB, the user's Blender RSS 450 MB but **1.99 GB swapped out**.
Consequence: **the Claude desktop app was restarted** (journal: `Started app-com.anthropic.Claude-…scope`,
old instance `1.1G memory peak, 583.4M memory swap peak`), after which a helper process reported
`Missing X server or $DISPLAY … The platform failed to initialize. Exiting.`.
**Unity never crashed throughout** (no `mono_crash*.blob`, MCP responded instantly, only normal Asset Pipeline Refresh in the log) —
it looked like a crash, but actually the whole machine was paging.

**Every headless Blender must fully load the .blend**: for Project B's 135 MB scene, one headless instance is GB-scale.
In this round I opened 6 in a row (repair parameter sweep, bake, eye close, export, render ×2).

**Practice**:
- `free -h` before starting; **if more than half of swap is used, clear the field first, then work**.
- Headless Blender **serially, exit when done**; do not leave them running concurrently with `run_in_background`.
- Whatever can be measured read-only via MCP in the **already open** Blender session should not start another headless instance (almost all measurements can).
- When clearing the field, **the user's Blender/Unity must not be closed by me** (there may be unsaved changes; see “never discard scene changes without permission”);
  first list what can be closed (VMs, idle opencode sessions) for the user and let a human decide.

> **Checkable question**: will the process I am about to start make `free -h` available drop below 2 GB?
> How many processes of the same kind are already running?
