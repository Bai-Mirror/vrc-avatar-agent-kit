> 🌐 English translation · [中文原文](../../../开发工具/SOP/05_多模型评审规程.md)

# 05 · Multi-model review procedure　🔍

> **On 2026-09-01 the author explicitly asked to raise the priority of multi-model review.**
> This is not a bonus item "done when there's spare capacity"; it is **a mandatory gate for every detailed task and every stage commit**.

## Why it must be sent out: **the main conversation gets anchored by its own context** (the user's fourth emphasis, 2026-09-06)

> "In past tasks the main conversation often gave optimistic assessments because of **context anchoring**, which in fact couldn't pass my review;
> and Gemini is **a separate subscription pool**, and Flash is quite good in both accuracy and speed."

This changes three things:

**① The reason for sending out is not "multiple models are more accurate", it's "I've been anchored".**
A conclusion restated in your own context becomes more convincing the more it's restated, and **the number of restatements has nothing to do with correctness**.
So the criterion isn't "is this conclusion hard", it's "**how many times have I restated it**" — once restated, it must be sent out.

**② The scope isn't limited to visual conclusions.** Anchoring doesn't discriminate: technical root causes, requirement interpretations and option trade-offs are all included.

**③ Gemini is a separate subscription pool**, independent of the main conversation's quota — this gate is **affordable**.
"Saving quota" refers to **three-model/five-model cross-checking**; it's not a reason to skip single-model falsification.

### ⚠ "Ran agy_panel" ≠ "passed the gate"

The original drift criterion was "three consecutive tool calls without agy_panel". **On 2026-09-06 it was measured giving a false negative**:
that round called agy_panel several times, but **all of it was debugging the tool itself** (finding out why gemini timed out),
and not once was a conclusion sent for falsification. The criterion didn't trigger, and it drifted for a whole round anyway.

> **Corrected self-check question**: in the most recent agy call, was the **input "my conclusion" or "whether the tool works"**?
> If the latter, it's as if nothing was checked.

### Design falsification tasks like this; don't ask "what do you think"

Asking for impressions only gets agreement. The correct shape:

- **List the conclusions numbered** (C1, C2…), and require a choice of `支持 / 矛盾 / 看不出` (supported / contradicted / can't tell) **for each one**
- **"Contradicted" must point to which image and which part**; anything unclear is always `看不出` (can't tell) — **no guessing just to give an answer**
- State explicitly: "**No agreeing for its own sake. Your value lies in pointing out the ones that are wrong.**"
- State explicitly: "Base it only on the images actually attached; don't write a word about images not attached"
- Leave an open slot: "What else in the images doesn't fit this set of conclusions but wasn't asked above?"

> Subpage: image order for blind tests (agy_panel numbers from `img00`) and mapping identifications back → [Blind test image order and identification mapping](05-multi-model-review/blind-order-and-id-match.md)

## Choosing the right tool: don't confuse the scripts, don't confuse the MCP tools

`agy_panel.py` and `agy-task.py` are two **scripts** with different purposes;
the MCP tools `agy_review` (**finds faults only**) and `agy_ask` (interpret / compare / weigh) are two **tools**; asking the wrong one doesn't raise an error, it just answers off-topic.
The division of labor, pitfall examples and checkable questions for both pairs → **[05 · Choosing the right review tool](05-multi-model-review/choosing-the-right-tool.md)**

## ⚠ Review reports must state **which tool and which model were used**

The default model of `agy-task.py` is **`gemini-3.8-flash-low`** (since 09-17; the original 3.5 has been retired),
while this procedure's default lineup is **`gemini-3.7-flash-high`** — **they are not the same thing.**

A problem measured on 2026-09-07: one subagent used `agy-task.py` (reporting `gemini-3.8-flash-low`) to make
a load-bearing judgment, while other rounds the same night used `agy_panel.py --fast` (3.7-flash-high).
**When comparing verdicts across rounds, if the models differ, the comparison itself is confounded.**

**Rules**:
1. When dispatching a review task, **specify the tool and model in the task brief**
2. Require **the report to state which was actually used**
3. **Before comparing verdicts across rounds, first confirm both rounds used the same tool and model** —
   otherwise "the same comparison gave different verdicts" may just mean the model changed

## Three lineups

| Occasion | Lineup | Notes |
|---|---|---|
| **Every everyday step** (finished an accessory, adjusted a color, rendered a batch) | **`--fast` single-model quick review** | gemini-3.7-flash-high. Seconds, cheap — **the more often it's used, the more it pays off** |
| **Major milestones** (an SOP stage done, preparing delivery) | **3-model cross-check** | claude-opus-4-6-thinking + gemini-3.7-flash-high + DeepSeek vision |
| **Unclear results** (the 3 models contradict each other / only 1 flags it / can't tell right from wrong) | **Expand to 5 models** | Add gemini-3.1-pro-high + gpt-oss-120b-medium (`--wide`) |

```bash
# Everyday quick review (the workhorse; should be the vast majority of calls)
python 开发工具/通用工具/agy_panel.py --task t.md --images ... --fast

# Major milestone: 3-model cross-check
python 开发工具/通用工具/agy_panel.py --task t.md --images ...

# Unclear results: 5 models
python 开发工具/通用工具/agy_panel.py --task t.md --images ... --wide
```

### Lineup trade-off: why the workhorse is a single-model quick review

**Why the workhorse is single-model (decided by the author 2026-09-01)**: early on the rule was "accept only when ≥2 models agree", because a single model
would report nonexistent defects with confidence 1.0. But 3.7-flash's hallucination rate has dropped noticeably, and **the value of review mainly
comes from frequency, not from lineup size** — reviewing every step catches far more than finishing ten steps and then running three models.
So: `--fast` at every everyday step, saving the cross-check lineup for major milestones.

`--fast` automatically lowers the consistency threshold to 1 (with only one reviewer, "≥2 agree" is a threshold that can never be met,
which would push every flag into "to be checked", reading like "zero items accepted" — **very easy to misread as a pass**).
The cost is that you must **re-check each item yourself**: measured, 3.7-flash still misidentifies objects —
it flagged a metal ring on an earring as "halo remnant not synced in displacement"; the location was right (there really was an out-of-place black ring there),
the attribution wrong. **The location it points to is more trustworthy than the conclusion it gives.**

## Image granularity: the easiest step to get wrong, and the most costly

**The 2026-09-01 lesson**: I fed a 360px full-body three-quarter thumbnail to three models for accessory acceptance,
and over three rounds not one model pointed out "the headwear placement is wrong", "the halo should be offset to one side", or "the animal ears aren't embedded into the head".
**It's not that the models are bad — at that size those details simply don't exist in the image.**

Rules:

| What to review | What to feed |
|---|---|
| Overall tone, wardrobe consistency, color relationships | Full-body three-quarter, ≥600px |
| **Whether a single accessory is installed correctly** | **A close-up of that accessory**, the accessory occupying ≥1/3 of the frame, and **at least three views** |
| Clipping | Close-ups of the conflicting area, orthographic views, one per side |
| Closed-form judgments such as whether it fits over/hugs | **Don't feed images**; write it as a script assertion |

**Criterion**: measure the thing to be reviewed on the image — **if it doesn't take up 1/4 of the frame, don't expect the model to see it**.

## How to design falsification tasks → [subpage](05-multi-model-review/falsification-task-design.md)

Four techniques; look them up before writing a task:

| Technique | In one sentence |
|---|---|
| **Compare against the opposite variant, not a neutral baseline** | Same key, smaller value — change the comparison target and it goes from "can't tell" to "clearly" |
| **Plant a control claim with a known answer** | Gives the review a third outcome: pass / problems found / **the criterion itself is untrustworthy** |
| **Use a difference map to auto-locate the region to review** | Don't eyeball the image to point out crop coordinates; that's the most error-prone step |
| **Don't pass off "a measured number" as a criterion** | Quantitative criteria must come with a control sample; degenerate cases must explicitly refuse to answer, no forced rankings |

⚠ **"vs zero judged can't-tell" does not imply "this key can't produce the effect"** — on that basis I nearly tore down the whole set of candidate options.

### Trade-offs of the "≥1/4" line

**Where the threshold came from**: measured, not made up. When the eyes occupied **15%** of frame width,
the same model's verdicts on three candidate groups **contradicted each other** and conflicted with the pixel diffs;
after cropping to **44%** the verdicts converged and agreed with the pixel diffs. 1/4 is a conservative line taken between these two points.

**What happens if you deviate either way**:
- **Too small** → the model isn't "seeing wrong"; those details **simply aren't in the image**, so it switches to commenting on background, pose, lighting
- **Too large** → feeding only close-ups loses "does this thing fit within the whole", and the model starts picking at **edge softness caused by upscaling**
  → **a close-up must be sent together with an overall image**, and the prompt should state "edge softness is due to upscaling, not a defect"

**What to do if you can't reach 1/4** (try in order; don't force it through):
1. Use `通用工具/img_tools.py diff-crop` to crop to that region and upscale — after cropping **self-check that they're still pairwise different**, otherwise it's just feeding empty images in a different way
2. Still can't reach it → **re-render from a closer camera**
3. The camera can't do it either (occluded) → this thing **simply can't be reviewed on this set of images**;
   pull it out of this review round and state so; don't leave it in and pretend it was reviewed

## Prompt essentials

- State explicitly "**evaluate only the images actually attached**". DeepSeek will fabricate evaluations of images it wasn't given (measured: sent 2, it reviewed 8).
- Don't list "which images there are" in the task; the model will make things up following the list.
- **Write the prompt header according to the image type** (triptych / single image / flat product image each get their own; not shared): using the wrong one gets the whole batch judged wrong (09-22 H-05 Vend batch, see section 4 of [Visual division of labor and evidence gathering](50-outfit-and-hair-assembly/part-understanding-and-menu-layout/visual-division-and-evidence.md)).
- State explicitly which are **deliberate acceptance conditions** (T-pose, dark gray background, underwear only), or you'll get a pile of noise.
- Require "state what is wrong"; forbid "consider suggesting…".
- **Attach the author's showcase images as reference**, so the model compares "the author's design intent vs. how it looks now" —
  this is far more effective than having it judge "is it installed right" from nothing.

## Reading the results

- **Merge once more by the flagged object**. Token-overlap clustering splits different wordings of the same problem into multiple "to be checked" items;
  if three items all point at the same accessory, that means three models all say it's wrong.
- Single-model flags do contain hallucinations, but **don't discard them outright**; re-check yourself.
- **Zero agreed items ≠ pass**. First ask: is there really no problem, or did the images I fed make the problems invisible to them?

Related: [00 Master table](00-overview.md) · [55 Accessory placement](55-accessory-placement.md) · [40 Texture recoloring](40-texture-and-coloring.md)
