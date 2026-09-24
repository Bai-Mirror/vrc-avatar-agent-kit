> 🌐 English translation · [中文原文](../../../../开发工具/SOP/01_自动化执行与并行/步骤模板与硬闸.md)

> ← [01 · Automation and parallelism](../01-automation-and-parallelism.md)

# Step templates for non-frontier models

The problem this page solves: **a weak model's failure mode is not "can't do it", it's improvising where there is no criterion.**
So steps must be written in a shape that leaves no room for improvisation. Read this page before writing the step table of any SOP page.

A weak model's failure mode is not "can't do it", it's **improvising where there is no criterion**.
So steps must be written in the shape below — every cell leaves no room for improvisation:

```markdown
### Step N · <phrase starting with a verb>

**Preconditions** (if any is not met, stop and report; don't try to remedy it)
- [ ] <checkable condition, stating how to check it>

**Execute** (copy exactly, don't change parameters)
1. <exact call: menu path / script name / parameter values>

**Post-criteria** (numbers or booleans, not impressions)
| Expected | How to read |
|---|---|
| <X == N> | Run <Y>, look at <which line> of <report file> |

**STOP — if any of the following occurs, stop and hand back to a human**
- <condition>
```

### Rules must carry **trade-offs**, or they become unusable with a different model

The author, 2026-09-06: "I hope you can also spell out some of the **internalized trade-offs**,
so that these documents stay general when used by **different AI models**, **avoiding the effect of internalized ability on execution**."

**Shape of the problem**: the person writing the spec (capable, with context) keeps a lot of judgment in their head
and writes only the **conclusions** into the document. Conclusions suffice in normal cases, **but not at the edges** —
and the edges are exactly where different models differ most. At an edge the reader has only two paths: **freeze**, or **improvise**.

#### Four things to add to every rule

| Element | What happens if not written |
|---|---|
| **① Where the threshold comes from** | The reader doesn't know whether it can be changed, so they either cling to it or change it arbitrarily |
| **② Failure modes in each of the two directions** | They only know "not too big", not what happens if too small, so they push it all the way to 0 |
| **③ What to do when it can't be met** | Stuck when the condition isn't met, or pretending it's met and carrying on |
| **④ When judgment is needed, what information the judgment requires** | A weak model doesn't have that information and can only make it up |

#### Counterexample and positive example (both from this procedure)

**Counterexample**: "If the reviewed subject occupies less than 1/4 of the frame, it's as if it wasn't fed" —
only a threshold. **Why 1/4? What if it can't be achieved?** A reader who "can only get 1/5" has nowhere to go.
After adding: *1/4 is an empirically measured line (at 15% verdicts contradicted each other, at 44% they converged);
if it can't be achieved, use `img_tools.py diff-crop` to crop to that region and enlarge; after cropping you must self-check that the images are still pairwise different,
otherwise it's just feeding empty images in a different way.*

**Positive example**: when writing the STOP for the probe agent in this order, the rule was written together with the **reason** —
"the control item must be judged 'supported'; **if even that is judged wrong, this observation convention is untrustworthy**, STOP immediately".
Later it hit an edge I hadn't anticipated (the item under judgment was judged "can't tell" rather than "decreased"),
and **correctly judged that the literal condition wasn't triggered, but still reported it truthfully**.
It navigated correctly by **understanding the intent**, not by matching the letter.

> **Criterion**: replace the number in the rule with another number — can the reader judge on their own whether that change is right?
> If not, the trade-off hasn't been written out.

#### Where things are "left to judgment", state the basis for judgment

Some trade-offs genuinely can't be fixed in advance. Then **state explicitly that this is a judgment point**, and list what the judgment should look at:

```markdown
**Judgment here**: <what to judge>
**Look at these**: <info 1> / <info 2>
**Leaning**: choose <X> by default, unless <condition>
**Cost of judging wrong**: choosing X wrongly leads to <consequence>; choosing Y wrongly leads to <consequence>
```

Much more useful than "decide from experience" — **a weak model doesn't have your experience, but it can read a table**.

---

### ⚠ The criterion itself must also be verified: **an always-true fake criterion is more dangerous than no criterion**

Before writing a criterion down, first confirm that **it can actually read that number**, and that **it really fails in the wrong case**.

**Measured counterexample**: one version of a step table said "number of RGBA32 textures on the default platform == 0, read `textureFormat` from `.meta`".
It looks definite, but that field in `.meta` is `-1` (Automatic) in the vast majority of cases —
**not a single `RGBA32` will ever appear**, so this criterion **always passes**.
It won't raise an error; it just makes people think it was checked.

**Rules**:

- After writing a criterion, ask yourself: **"Under what circumstances will it fail?"** If you can't answer, it's a fake criterion
- When conditions allow, check it against **one known positive and one known negative sample** (see [20's implementation pitfalls](../20-asset-inventory-and-import/implementation-pitfalls.md))
- **Criteria that haven't been verified must be marked**, e.g. "⚠ not verified in a project".
  Readers of a deterministic step table execute it as written; **not marking it amounts to deceiving them**
- When a criterion references an output line of some tool, first confirm **that tool really prints that line**

### Four hard gates beyond the template

These four are real stumbles, **weak models trip on them more easily than strong ones**, and they must be written into every step they apply to:

**① Measure the delivered state, not the source scene.**
The build pipeline merges renderers, rewrites bounding boxes and masks, and renumbers animator layers.
For any property that "may be rewritten at build time", the criterion must be taken on the baked clone,
and "what was measured" must be printed.

**② Land only one change at a time.**
With two unverified changes stacked together, a problem can't be attributed, and you can only revert everything and start over.

**③ "Useless" does not mean "harmless".**
When you find a change ineffective, don't keep it. Harmlessness is a claim that needs evidence; if you can't give a reason, revert it,
and revert by precise per-property reversion (`PrefabUtility.RevertPropertyOverride`), not the undo stack.

**④ Don't draw visual conclusions yourself.**
"I looked at the image and think it's fine" does not constitute completion. Either replace it with a closed-form criterion, or pass third-party review.
And first confirm that **the observation channel itself** can reproduce the target phenomenon —
offscreen rendering can't render grab-pass effects, edit time doesn't simulate PhysBones; images like these are broken as criteria.

### Which model tier to dispatch → [Subagent dispatch](subagent-dispatch.md)

The dispatch axis is **not model strength**, it's "does this task contain **reasoning that tools can't see**":

| Task nature | Dispatch to |
|---|---|
| **Enumerative** — every conclusion can be directly confirmed by some tool call | **Haiku** (an order of magnitude cheaper; **must hard-code which kinds of judgment are forbidden**) |
| **Reasoning** — requires cross-file comparison, judging equivalence/compatibility/root cause | **Sonnet** |
| **Aesthetic** — no closed-form criterion, what's needed is trade-offs and placement | **Fable** |
| **Troubleshooting** — other routes stuck, criteria contradict each other, three layers nested in one | **Opus** (whether to dispatch, see the subpage) |

**The two most easily missed**:
- **Subagents don't wait for background tasks** (reproduced 3/3) — the task description must hard-code "after starting, poll until it exits before reading results",
  and **the main agent must verify the final state itself**
- **Any conclusion in a report that "couldn't be reached without an action I didn't take" is never adopted** —
  test: check whether its tool calls can support that conclusion

How to derive "which judgments to forbid", the three conditions for an Opus subagent, and the cost-asymmetry analysis → **[subpage](subagent-dispatch.md)**

### Generic wrap-up actions for weak models

Every step that changes the project ends with three fixed things:

1. **Readback verification** (not reading a log that says "done", but reading back the changed values and comparing)
2. **Skeleton height self-check** (after changing the scene, self-check before saving)
3. **State clearly what was verified and what wasn't** — say explicitly what wasn't verified; don't gloss over it

---
