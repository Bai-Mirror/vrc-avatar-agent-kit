> 🌐 English translation · [中文原文](../../../../开发工具/SOP/04_施工记录与版本管理/收尾蒸馏与状态头.md)

> ← [04 · Work log and version control](../04-build-log-and-version-control.md)

# Wrap-up distillation and the status header (two-layer system, decided by the author 2026-09-23)

## Why switch to two layers
The 09-23 workflow review (`_工作流审理_20260923.md`) established that execution sessions writing SOPs as they went, in a fatigued context, produced cross-page contradictions ("four things / five / six categories"), splitting without shrinking (27 subpages moved line by line), and a DSH skill file that contradicted `--record`; meanwhile the `排障记录规程` (troubleshooting log procedure) showed that "after-the-fact logging gets rationalized". Both sides are right, so we split into layers: **the phenomenon layer is recorded on the spot; the rule layer is distilled at wrap-up.**

## Phenomenon layer (execution session, record as you go)
- Write only facts: the action, the abnormal output that triggered it, the hypothesis at the time, the evidence that falsified/confirmed it. It lands in that project's `_施工记录.md` (`log_step.py`) or in the "lessons that should go into the SOP" section of a DSH reply (goes into the dispatch log).
- When hitting a wall or being corrected, add `--distill "trigger moment + checkable question"`; it's enough for the entry to carry a "to-distill" tag — **don't change the SOP body**.
- Exception: a criterion that would make **the very next dispatch trip immediately** if not fixed (e.g. a tool name or parameter value is wrong) may be fixed in the SOP on the spot by one line, with "already written into page X on the spot" noted in the tag, to be re-checked during distillation.

## Rule layer (wrap-up, clean context)
**When**: at the end of a stage, or at the end of a day, or when `baseline_recheck.sh` reports "to-distill tags ≥ 8".
**Who**: an agent with no conversation history — a Claude subagent (the `Agent` tool, given only the material pack and the named pages) or one DSH dispatch (`--no-record`). It must not be the session that is doing the work.
**Input**: `python3 开发工具/通用工具/distill_collect.py --since "$(上次蒸馏时间)" --out 材料包.md` (three sections: to-distill tags, DSH lesson sections, SOP pages changed during this period).
**Actions** (also printed at the end of the material pack):
1. For each tag/lesson, first `grep` the SOP for a synonymous entry; if there is one, edit in place (add the trigger moment, checkable question, trade-offs); only add a new one if there isn't, on the most fitting page.
2. For each changed page: byte count (>10,240 → split into subpages, with the step table and criteria kept on the main page), dead links via `python3 开发工具/通用工具/check_links.py [--baseline <改前快照>/开发工具/SOP]`, same-topic contradictions across pages (numbers, counts, categories). Before splitting pages, **take a fresh** snapshot (save this round's `before_<轮>/` separately per the `bh_prep.py` convention; don't reuse the cross-round `tmp/bh/before/`: the 09-19 archive was stale by W2 and `check_lines.py` falsely reported old lines missing); the over-limit criterion counts only **pages this round is responsible for**; pages that parallel tasks are writing (during W2, [00 Master table/Tool index](../00-overview/tool-index.md) was 26 KB) are marked with their origin in the report and not counted.
3. Don't change work logs or the dispatch log; produce an "merged → page:section" list.
4. Record the time with `distill_collect.py --mark "<一句话>"`; `ws_git.py commit` names only the SOP pages that were changed.
**Acceptance (Claude)**: sample 3 tags and find them by grep in the SOP; `find SOP -size +10240c` leaves only exempt pages (pages being written by parallel tasks must be marked with their origin); `python3 开发工具/通用工具/check_links.py` reports 0 new broken links (links already broken before the change are exempted with `--baseline`).

**Trade-off**: distillation lags incidents by a few hours to a day, at the cost that dispatches in that window can't read the new rules — hence the "trips immediately" exception. Conversely, without splitting the layers the cost is what happened from 09-18 to 09-23: 20-plus SOP commits a day, every page hugging 10 KB, contradictions everywhere.

## Status header
At the top of each project's `_施工记录.md`, after the `>` description block:
```
<!-- 状态头:BEGIN（可整块改写，由 log_step.py 或验收者维护；下面的时间线只追加不改） -->
## 当前状态（YYYY-MM-DD HH:MM）
- **阶段 / 交付状态**：80 性能优化 / 进行中
- **最近一步**：<最后一条标题>
- **下一步**：  1. …（来源 路径:行）
- **未决 / 等用户**：  - …
- **不许动**：<用户禁区>
<!-- 状态头:END -->
```
(The template above is the literal format that `log_step.py` parses; it is kept in the original Chinese. Its fields are: stage / delivery status, most recent step, next steps (with source path:line), pending / waiting on the user, and do-not-touch (the user's no-go zones).)

Taking over: `log_step.py <工程> --show`. Each time `log_step.py` appends an entry you can also update the status header with `--stage/--next/--pending/--forbid`; if not given, only "most recent step" is updated. `baseline_recheck.sh` prints a summary of the status headers of all seven projects together.

## Incident record: timestamps (why time may only come from the clock)
- **Take entry times from `date`; don't write them by feel** (on 2026-09-18, twice wrote timestamps 10–20 minutes later than actual): during long tasks the sense of time drifts; run `date +%H:%M` once before writing an entry. On 09-19 it happened again and worse: in one afternoon, 6 consecutive entries with "future times" **25–105 minutes later** than actual (after context compaction, time was estimated from the amount of work done). Self-check: a new entry's time must not be later than `date`, nor earlier than the last commit (`git log -1 --format=%ad --date=format:%H:%M`).
  - **Happened twice more on 09-20** (written 17:05 but actually 16:33; 17:14 actually 17:10): both times **the whole entry was written first, with `date` run in the same command**, so the time was "what I thought" rather than what `date` said. **Fix**: **see** the output of `date` **first**, then copy that number into the entry; don't put `date` and `cat >> 施工记录` in the same command. Self-check: which tool output did I copy this timestamp from?
  - **Third recurrence, overnight 09-22**: pushing on for 2 hours straight while the user rested, 20 entries were written with "future times" 15–60 minutes later than actual (05:1x–07:2x, actually 04:53–06:33), only noticed as 06:33 when `date` was once put in the same command as writing an entry. Corrected one by one using `git log --date=format:%H:%M`. Fourth time the same day: an `AskUserQuestion` waited about 4 hours for an answer, and I recorded the decision as 14:4x based on the time before asking (actually around 18:00). **After `AskUserQuestion` returns, run `date` first, then record the decision time** — the user may answer hours later. **One more fix**: before each acceptance, run `date +%H:%M` on its own and write only that number in the entry, never estimates like "0x".
