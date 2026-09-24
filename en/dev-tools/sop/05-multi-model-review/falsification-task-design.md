> 🌐 English translation · [中文原文](../../../../开发工具/SOP/05_多模型评审规程/证伪任务设计.md)

> ← [05 · Multi-model review procedure](../05-multi-model-review.md)

# How to design falsification tasks

This page is **required reading before writing a falsification task**. Four techniques, all learned the hard way on this order.

### Technique: probes should **compare against the opposite variant**, not against a neutral baseline

For the same blend shape, the two comparison methods give opposite conclusions (measured 2026-09-06):

| Comparison | Verdict | Model's own words |
|---|---|---|
| `eyelid_turi1` **@100 vs all-zero baseline** | **Can't tell** | "No discernible raising or upturn seen" |
| `eyelid_turi1` **@60 vs `eyelid_tare2`@60** (opposite variant) | **Supported** | "Clearly upturned/cat eyes; the outer eye corners are clearly lifted upward" |

**Same key, smaller value — change the comparison target and it goes from "can't tell" to "clearly".**

Reason: comparing a variant against the neutral baseline gives a one-sided signal; comparing against the **opposite variant** doubles the signal,
and gives the model an anchor for "which dimension the difference should appear in".

**Rules**:
- Design probes by default as **A+ vs A−** (positive variant vs negative variant), not A vs zero
- Use vs zero only for existence questions like "does this key move anything at all"
- **"vs zero judged can't-tell" does not imply "this key can't produce the effect"** — on that basis I nearly tore down the whole set of candidate options

⚠ Related lesson: **don't use the two closest groups in the options as evidence of "whether the difference is big enough"**.
In this order c1 and c4 share the same upturn key (60 vs 100) and are the closest pair of the four groups
(crop sumdiff 5.2M, whereas c3–c4 is 11.9M); comparing them naturally gives "can't tell".
**To verify a difference, compare the farthest pair; to verify similarity, compare the closest pair.** Don't mix them up.

### Technique: **plant a control claim with a known answer in the falsification task**

The review result itself also needs to be falsifiable — otherwise it's "whatever the model says goes". How:
**mix into the claims to be judged one whose answer you have already independently confirmed**, and hard-code the handling rule.

Example (2026-09-06, judging blend shape direction):

| Claim | Status |
|---|---|
| "`eyelid_turi1` **raises** the outer eye corner relative to the inner corner" | To be judged — only vertex-method data |
| "`eyelid_turi3` **raises** the outer eye corner relative to the inner corner" | To be judged |
| "`eyelid_tare2` **lowers** the outer eye corner relative to the inner corner" | **Control** — both the vertex method and the render method have confirmed it droops |

Hard-coded in the task description:

> **The control claim must be judged "supported". If even it is judged wrong, this observation setup is untrustworthy;
> STOP immediately and don't push further.**

This gives the review three outcomes instead of two:
**pass / problems found / the criterion itself is untrustworthy** — the third was previously undetectable and would just be taken as one of the first two.

**Why it's needed**: this order measured one case of "the same model giving opposite judgments on the same image twice"
(the per-image description said ref05 had "slightly drooping eye tails", while the falsification said "fully wide open, eye tails not drooping").
Without a control, you can't tell whether the model was wrong or my image feeding/questioning was wrong.

⚠ The control should be **of the same kind and difficulty** as the items being judged. Using something obvious ("there is a face in the image") as a control is meaningless —
it only checks "did the model look at the image", not "can the model tell the direction at this granularity".
(That said, a **channel self-check** like "there is a face in the image" should still be included; it checks something else: whether my crop is right.)

### Technique: use a **difference map** to locate the region to review automatically; don't point to coordinates yourself

When reviewing "the eye-shape differences between these options", the eyes occupy only **15%** of the frame width in a full-face close-up —
far below the "≥1/3" threshold, and the model's verdicts **contradict each other** (measured: the same model's verdicts on three candidate groups
conflicted with each other and with the pixel diffs). **It's not that the model is bad; the thing to be reviewed isn't in the image.**

Locating the crop box **must not rely on looking at the image and pointing to coordinates yourself** — that is exactly the most error-prone step. Let the region surface by itself:

```python
# Subtract options pairwise and sum → the changed region is, by definition, where it lights up
heat = sum(abs(arr[a] - arr[b]).sum(axis=2) for a, b in pairs)
mask = heat > heat.max() * 0.06
ys, xs = np.nonzero(mask)
x0, x1 = np.percentile(xs, 2), np.percentile(xs, 98)   # use percentiles to avoid scattered noise
y0, y1 = np.percentile(ys, 2), np.percentile(ys, 98)
# add a margin, crop, and upscale to a long side of ~1400px
```

Measured: the eye box was auto-located to 480×292, **raising its share of frame width from 15% to 44%**;
pairwise crop sumdiff rose from the 1-million range to the **12-million range**, with a maximum single-pixel diff of **231/255** —
the difference was large all along; it was just diluted in the full-face view.

**After cropping, self-check two things** (otherwise it's just feeding empty images in a different way):
1. The three crops are **still pairwise different** (sumdiff ≠ 0)
2. Add a **channel self-check** claim to the falsification task, e.g. "D0: the first image is an eye close-up, and a pair of eyes is visible" —
   if even D0 is judged "contradicted", the crop is wrong, not the options

### ⚠ Incidentally: don't pass off "a measured number" as a criterion

In the same round I wrote a **fake criterion**: measuring the eye aspect ratio by a dark-pixel threshold.
For four images (including the baseline) it gave a height of **462 for all of them** — exactly the height of my crop band,
meaning the threshold was catching **hair**, not eyes; the dark-pixel counts were nearly identical across the four.
**It gives the same number for any input, i.e. it's trivially true.**

The self-exposing point: **the baseline measured the same as the candidates**.
So a quantitative criterion must always **come with a control sample known to differ** (see [The shape of a criterion](../troubleshooting/observation-criteria/shape-of-a-criterion.md));
if it can't measure a difference, the criterion is broken, not the samples lacking a difference.


---

## Technique: **when a verdict flips, test repeatability first — distinguish "model instability" from "the stimulus changed"**

When the same comparison gives opposite verdicts in two rounds, there are two completely different causes, **with opposite handling**:

| Cause | Criterion | Handling |
|---|---|---|
| **Model instability** (same input, different output) | Run the same batch of images N times in a row; verdicts inconsistent | Switch to multi-model cross-checking; or the judgment itself is unreliable — switch to a closed-form criterion |
| **The stimulus changed** (the inputs actually differ) | Run N times in a row; verdicts consistent | **The difference is in the images** — go find how the two batches differ |

**How to do it**: take the disputed run and **re-run it unchanged 3 times in a row** (same images, same claims, same model), and see whether the verdicts scatter.

### Measured (2026-09-06 Project C)

`eyelid_tare2`@100 vs all-zero:
- Batch with bangs → **supported**
- Batch with bangs hidden → **can't tell**
- **Bangs-hidden batch run 3 times in a row → 3/3 "can't tell", repeatable**

Conclusion: **it's not model instability; hiding the bangs made the eye tails harder to read.**
Presumed mechanism: the edge of the bangs gave the eye tail a reference; with it removed, the eye tail sits on smooth skin and loses contrast.

**This falsified a hypothesis I was about to adopt** — "the bangs hide the upturn effect; hide them and it becomes visible".
The actual direction is the opposite. **Without this repeatability test, I would have written "hide the bangs" into the SOP as a fix.**

> **Corollary**: changing render conditions (hiding occluders, changing background, changing lighting) **changes how readable the review is,
> and not necessarily in the "clearer" direction**. Once conditions change, re-verify the control; you can't carry over the previous round's conclusion.

---

> → The false-positive pattern for "are there two X"-type claims has moved to [Small parts and pixel re-checks](falsification-task-design/small-widgets-and-pixel-review.md).

## ⚠ Correction: the "agy 0 real defects / 5 false positives" table above was later overturned

Measured 2026-09-07: **there really were two sets of ears on the head.**
The four pieces of `Acc_GothicRoseFox` are two color variants of "ears / tail" × "white / pink"
(same FBX, same 9 bones, bounding boxes 1 cm apart, materials `WHITE` vs `PINK`), and the preset had all four turned on.

**agy's observation was correct. The re-check step was wrong** — it attributed the correct observation "there's a second set of ears"
to the outfit's built-in headwear, so the whole item was judged a false positive, which in turn led me to write a wrong statistics table
and a methodological conclusion built on that table.

### When re-checking a visual identification, ask the right question

| Don't ask | Ask |
|---|---|
| "Is the thing it mentioned actually the thing it thinks it is?" | **"Is the phenomenon it describes actually there?"** |

Phenomenon present = a real identification, only **the attribution is pending**; phenomenon absent = only then is it a false positive.
**Judging "wrong attribution" as "wrong identification" makes you lose a real defect and gives you a wrong estimate of how much to trust the review tool.**

### For "how many X"-type identifications, count the renderers

In this case, just listing the **materials and bone arrays** of the child objects under that container shows at a glance that they are two color variants —
faster than cropping and zooming to re-check, and closed-form.

> → [Small parts and pixel re-checks](falsification-task-design/small-widgets-and-pixel-review.md) — the model gets small parts wrong on full-body collages: crop zoomed images, decide same-state cells by pixel diff, state default-on and built-in pieces in the prompt, check colors against vendor data (09-23).
