> 🌐 English translation · [中文原文](../../../../开发工具/SOP/问题定位/排障记录规程.md)

> ← [00 · Master table](../00-overview.md)

# Troubleshooting log procedure

The problem this page solves: **recorded, yet repeated anyway.**

The author, 2026-09-06: "When you hit obstacles and need to troubleshoot, remember to **record and analyze more**,
to avoid **knowing and still making the mistake**. Both SOP documents and memory need to be **updated as you go**."

## First, acknowledge the failure mode

Two instances on the same day, where both rules **were already written down in black and white in memory**:

- `gemini-check-every-visual-claim` (hard gate, reminded for the **fourth time**) → still drifted for a whole round
- `prove-cause-before-fixing` → still inferred the cause from a 300-character log tail and wrote a useless patch

**"Was it recorded" isn't the bottleneck; "what shape it was recorded in" is.**

## Four failure reasons → four writing requirements

| Why recording didn't help | Writing requirement |
|---|---|
| Memory is **absent at the moment of decision** — three layers deep into troubleshooting, nobody goes back to read it | Hang the gate on the **action**: "**right before writing a patch**, ask…", not on the topic |
| What was recorded was a **principle**, not a trigger. "Don't act before the cause is proven" doesn't stop anyone | Each entry needs **① a trigger moment ② a question answerable on the spot ③ a concrete action if the answer is wrong** |
| **After-the-fact records get rationalized** — written after the obstacle is past, they come out as narrative, not criteria | **Record as you go**: before it's solved, first record "symptom + my hypothesis at the time" |
| **The criterion itself may be broken**; a bad criterion is worse than none (it gives false reassurance) | After writing, ask: "**Under what circumstances would it fail?**" If you can't answer, it's a fake criterion |

## Template

```markdown
### <one-sentence symptom>
**Trigger**: when you are about to <concrete action>
**Question**: <a question answerable on the spot>
**If the answer is wrong**: <a concrete action, not "pay attention">
**Evidence**: <measured numbers / verbatim log text, not a paraphrase>
```

## Where it goes

> **From 2026-09-23, split into two layers** (the user decided): this page's "record as you go" covers only the **symptom layer** — on the spot, record "symptom + hypothesis at the time + evidence" into the work log and tag it "to-distill" (`log_step.py --distill`); the **rule layer** (writing into the SOP) is done at wrap-up by a clean-context agent — procedure in [Wrap-up distillation and status header](../04-build-log-and-version-control/wrapup-distillation-and-status-header.md). Reason: after-the-fact records get rationalized (this page), but an executing session editing the SOP on the spot writes contradictions and fragments (`_工作流审理_20260923.md` §2.5). Each layer takes half.

| Content | Destination |
|---|---|
| General patterns, reusable across orders | **Memory** (`~/.claude/.../memory/`) + one index line in `MEMORY.md` |
| Stage-specific practices and criteria | First tag "to-distill"; at wrap-up distill into the corresponding **SOP subpage** (criteria always stay on the main page; mechanism explanations sink to subpages) |
| This order's specific course of events and numbers | `建档.md` / reports / ledgers in the order directory |
| Tool pitfalls | **Write them into the tool's own docstring** — whoever uses the tool will definitely see it |

## Wrap-up action: count once at the end of every stage

"Update as you go" slips under pressure. In the self-check after the 2026-09-06 round, **three entries had been missed**
(Bash couldn't open Japanese paths, render output rendered into `Assets/`, log all PASS but image a solid color).

> **At the end of every SOP stage, always ask once: how many walls did this stage hit? How many entries were recorded?**
> If you can't count them, some were missed.

## Two practices measured to work

1. **Put the specific instances of earlier fabrication into the "reporting discipline" section of subagent task descriptions** —
   far more effective than abstractly writing "don't fabricate". After adding it, the subsequent runs all proactively marked "unverified" where unsure.
2. **When writing a criterion, first ask "is the range it scans large enough?"** The same kind of mistake occurred twice this round:
   the `Assembly-CSharp-Editor.dll` timestamp is always true for compile errors in **vendor-supplied asmdefs**;
   building a GUID index by scanning only `Assets/` reports every component GUID in `Packages/` as a broken link.

## Related

[Observation criteria](observation-criteria.md)
