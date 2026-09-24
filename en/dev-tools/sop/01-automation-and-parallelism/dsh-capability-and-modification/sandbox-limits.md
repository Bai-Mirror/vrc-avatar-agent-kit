> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/01_自动化执行与并行/DSH能力与改造/沙箱限制.md)

> ← [DSH capability and modification](../dsh-capability-and-modification.md)

# DSH Sandbox Limits (bwrap)

Every DSH command runs inside `bwrap --unshare-pid --die-with-parent --dev /dev --tmpfs /tmp` (`lib/index.js` of `@deepseek-ai/dsh-sandbox-local`). Three consequences:

## 1 · Background processes started by DSH do not outlive its session (09-22 `E-通用-01`)
**Trigger**: the task brief has DSH start a multi-hour batch job (Unity bulk import etc.) with `nohup setsid … &` and return immediately.
**Facts**: every DSH command runs inside `bwrap --unshare-pid --die-with-parent`; when the session ends the whole process group is killed; keeping it alive by hanging it on its own background task does not help either (09-22 the import queue started at 20:13; after DSH wrapped up, the queue and the Unity batch job vanished together, with `queue.txt` stuck at `开始 H10-Sio` (starting H10-Sio)).
**Practice**: for long batch jobs, DSH **writes the script and completes the prerequisites**, and the launch step is run by Claude in its own session with `run_in_background` (declare `--exempt 兜底`); acceptance checks `queue.txt` / logs. Checkable question: after DSH reports “started”, is `pgrep -fa <script name>` still there?

## 2 · There is no GPU in the DSH sandbox (09-22 A-23 round 2)
`bwrap --dev /dev` gives a minimal /dev without `/dev/nvidia*`/`/dev/dri` ⇒ batch Unity started by DSH falls back to **software Vulkan** (lilToon exceeds 32 texture parameters, magenta); Blender EEVEE also renders in software (small objects can render but slowly, with radeonsi warnings). **For trustworthy renders/GPU work**: DSH writes the script and a one-line launch command, and Claude runs it outside the sandbox with `run_in_background` (same as the “long batch jobs” item). Checkable question: are there large patches of `(255,0,255)` in the render? Is there `failed to load driver` in the log?

## 3 · `/tmp` in bash is a freshly mounted empty directory for every command (measured 09-18 on this machine (Linux), reported by DSH 09-23 in tongue-piercing chain L5-5c)
- Mechanism: the sandbox mounts a new `--tmpfs /tmp` for every bash command ⇒ it is both **private** (cannot see the host `/tmp`) and **emptied after the command ends**. DSH's read/write tools do not go through the bash sandbox and read/write the host `/tmp` — the two sides do not see the same directory.
- Phenomena: ① DSH writes `/tmp/x.json` in one bash command, and the next command cannot read it; ② the task brief asks it to process files under the host `/tmp/...` (e.g. Claude's scratchpad `/tmp/claude-1000/...`); the read tool can read them, but `diff`/`python` in bash cannot find them — it will “rebuild a copy and compare” on its own, and still write PASS in the report.
- Checkable question: “Are all the files the task brief asks DSH to process with bash inside the workspace (`--cwd`)?”
- Practice: put inputs and intermediate products in the workspace's `_dsh_tmp_<task>/` (already ignored by `/_dsh_tmp*/` in `.gitignore`) and delete after use; do not tell DSH in the task brief to put files needed across commands in `/tmp`. During verification, Claude re-runs the key commands itself outside the sandbox; do not just look at the output it pasted.
- Also: “overwritten old products” must be backed up explicitly — `--backup` should back up the old draft of `--out`, not the input source; when the old draft is already in git there is no need to save a separate copy (the L5-5c backup was byte-identical to the previous commit and has been deleted).
