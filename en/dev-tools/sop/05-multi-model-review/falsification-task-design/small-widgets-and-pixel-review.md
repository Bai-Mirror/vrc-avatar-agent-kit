> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/05_多模型评审规程/证伪任务设计/小部件与像素复核.md)

> ← [Falsification task design](../falsification-task-design.md)

# Small parts and pixel re-checks

## Gemini gets small parts wrong on full-body collages; close the loop with zoomed images and pixel comparison (09-23 Project A 3c)
**Trigger**: the submission is a multi-cell full-body collage (each cell 1024², character occupying 15–25%), and the claims concern a small ornament held in the mouth or accessory details.
**Example**: Gemini judged "08/18 fishbone missing"; after zooming in it admitted 08 had the fishbone, yet judged "18 has only the fish head left" — while 18 and 08 are the same state and the mouth region is **identical pixel for pixel** (pixels with diff >30: 0/14400). It also took the avatar's built-in holographic hair accessory for "editor debug UI", and a "default on" mouth ornament for "toggle not reset".
**How to do it**: ① for small-part claims, crop a zoomed image first before sending; ② when "two cells in the same state get different conclusions", decide directly by pixel diff rather than questioning the model further; ③ state in the prompt which pieces are **default on** and which are **non-outfit pieces built into the avatar**, otherwise it will treat them as defects; ④ when it overturns your color judgment, go back to vendor data (material PPtr lookup table, texture hue statistics, vendor color-scheme images) to check — trust neither the model nor your own eyes.

## A measured false-positive pattern: **for claims like "are there two X", the model counts adjacent objects as X**

2026-09-07 regression test: 5 batches submitted, agy reported **5 "contradictions", and after zooming in to re-check each one, all were overturned**.

| False positive | What it actually was |
|---|---|
| "There's a second set of ears" ×4 | **Headwear built into the outfit** — LUNALICE's black lace bow, VioletNocturne's gold rose hairpin |
| "Not fully dressed" ×1 | 487Stockings' **underwear + stockings are simply the design** |

**Cause**: when the claim is written as "at most one set of ears", the model includes **every protrusion near the head** in the "ears" candidate set.
It doesn't know which are accessories and which are part of the outfit.

### When writing a claim, **exclude distractors**

Bad: "The character in this image has **at most one set of ears on the head**"
Good: "The character in this image has **at most one set of animal ears (cat ears/fox ears) on the head**.
　　⚠ **Headwear built into the outfit (bows, hairpins, hairbands, rose decorations) does not count as ears**; don't count them."

Likewise, claims like "not fully dressed" must state **what this outfit is supposed to look like** — ideally **with the vendor's showcase image attached as a reference**.

### The more important point: **the real defect in this round was found by closed-form criteria; visual review contributed only false positives**

| Method | Real defects found | False positives |
|---|---|---|
| Structural criterion (renderer `activeInHierarchy`) | **1** | 0 |
| Pixel criterion (pairwise pixel diff of combinations) | **1** (the same one, independent corroboration) | 0 |
| agy visual review | 0 | **5** |

**This doesn't mean visual review is useless** — it's irreplaceable for questions like "is the placement right" or "do the colors go together".
But **"is some thing displayed or not" is a closed-form question — don't send it for review; check the renderer state directly**.
See [Step templates and hard gates](../../01-automation-and-parallelism/step-templates-and-hard-gates.md).

---

## Gemini got "which eye has it installed" wrong twice (09-23 MeteorLens)
- On 09-23 it twice judged "both eyes have lenses" as "only one eye": Milfy left/right half diffs 39076/39565 px, Rurune 23410/26615 px, and in the pure-green debug image Rurune about 30200 px on each side — the pixel data overturned it both times. Both base avatars have heterochromia (one blue one brown / different colors per eye), and it likely mistook the color difference for "one covered, one not".
- **How to do it**: for existence conclusions like "is it there / is it on both sides", the primary evidence is **per-region diff pixels** (count left and right halves separately, report at thresholds 8/20/40) plus **solid-color debug renders** (a solid-color stand-in with culling off and ZTest Always, counted left and right); ask Gemini only about look and overflow/broken faces. When its existence judgment contradicts the pixels, record truthfully "overturned by pixel data" and don't change the conclusion.
