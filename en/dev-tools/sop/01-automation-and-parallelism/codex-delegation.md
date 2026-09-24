> 🌐 English translation · [中文原文](../../../../开发工具/SOP/01_自动化执行与并行/Codex派工.md)

# Codex Dispatch (Executor Subagent During DeepSeek Peak Hours)

> The user decided on 2026-09-23: the lead is Claude; **on weekdays 09-12 and 14-18 Beijing time (DeepSeek peak, double price), execution work is dispatched to Codex instead**; other times remain DSH Flash as before.
> Heavy work is carried by Claude and Codex; Gemini (agy) and DeepSeek remain **independent third-party falsification sources** — external review is not skipped just because Codex can see images.
> The tool is still `dsh_task.js` (the same record-keeping, snapshots, locks, journal and hook recognition), with just one extra engine switch.

## 1. How to dispatch

```bash
node 开发工具/通用工具/dsh_task.js [--engine auto|dsh|codex] [--model luna|terra|sol|astra|luna6] [--effort low…ultra] \
  --task-file 任务书.md --record <工程> [--lock unity] [--images a.png,b.png] --snapshot-cmd "<只读命令>" --json 结果.json
```

- `--engine auto` (default): chosen automatically by Beijing time; the script converts to Beijing time (UTC+8), independent of this machine's time zone.
- Writing a Codex alias for `--model` automatically goes to Codex; flash/vision task briefs are dispatched as-is during peak hours and land on luna.
- With images: all Codex tiers can read images; images are sent as attachments with the message; verification checks the number of `input_image` in the rollout — one fewer is judged FAIL.

## 2. Choosing a tier (trade-offs)

| Tier | Model | Used for | Reasoning effort |
|---|---|---|---|
| luna | gpt-5.6-luna | Daily execution: ledgers, inventories, scripts, build tests, delivery files | medium (default) |
| terra / sol | gpt-5.6-terra / gpt-6-sol | Model editing, Unity fitting, multi-step complex agents, hard troubleshooting, image review | high; xhigh if stuck |
| astra | gpt-6-astra | Complex creative work in collaboration with Fable (creative photo planning, accessory design reasoning), idea expansion | high–max; ultra only when the user names it |

Start with the low tier; upgrade only with evidence of failure; write the reason for upgrading into the work log. Merge multiple questions about the same batch of material into one dispatch (quota is counted over a weekly window; re-ingesting the same material burns quota too).

## 3. Quota and concurrency

- The subscription (ChatGPT login) is limited by a **weekly window**. The script reads the remaining quota from `rate_limits.primary.used_percent` in the latest rollout and **refuses to dispatch at ≥85%** (adjustable via `CODEX_MAX_USED_PCT`); once the line is hit, peak-hour work waits for off-peak and goes to DSH, or is left for the user to decide.
- Concurrency ≤2 (user decision 09-23, `CODEX_TASK_MAX_SESS`); counted separately from DSH, sharing the memory gate (do not start when available <8 GB). Unity write operations still go through the handoff lock, held by one side at a time.

## 4. Measured pitfalls (09-23)

1. **The workspace-write sandbox makes `.git` read-only** ⇒ ws_git commits fail with `index.lock: Read-only file system`. The script now always adds `--add-dir <工作区>/.git`; add it too when calling `codex exec` by hand.
2. **`-i` is variadic**; positional arguments after it are swallowed as image paths, producing `No prompt provided via stdin`. The script always passes the task brief via stdin (trailing `-`).
3. The stdout of `--json` only has the thread_id and messages; tool details, actual model, wrap-up and quota are all in `~/.codex/sessions/**/rollout-*<thread>.jsonl`. For post-mortems read the rollout, not the self-report.
4. If the lead redirects a dispatch's stdout/stderr into the `--record` directory, the record-keeping check treats them as “leftover uncommitted” and judges FAIL (C01 instance) ⇒ redirect to `_dsh_tmp_codex_logs/`.
5. If the child process inherits `CLAUDECODE`, ws_git attributes DSH/Codex commits to Claude; the script now strips it.
6. **Image generation**: the `image_generation` feature is on by default, and images can be generated directly in `codex exec`; images first land in `~/.codex/generated_images/<thread>/`, so the task brief must say “copy to <target dir>/<filename>”. Attach reference images with `--images` (for appearance ground truth use only showcase shots accepted by the lead). Image generation consumes subscription quota; check the quota line before dispatching.
7. Codex cannot read CLAUDE.md or Claude's memory; the script automatically prepends a “dispatch identity” section to the task brief (who the lead is, SOP entry point, no irreversible actions). The task brief must still be self-contained.

## 5. Acceptance

Same as DSH, see [Project-edit dispatch and acceptance](project-edit-delegation-and-acceptance.md): check the verification block (engine/model/wrap-up/record-keeping/snapshots), `git show --stat`, read-back values. The work-log title suffix is `（Codex）`.
