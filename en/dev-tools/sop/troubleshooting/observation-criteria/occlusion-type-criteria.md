> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/问题定位/观测口径/遮挡类判据.md)

> ← [The criterion itself may be broken](criterion-may-be-broken.md)

# Occlusion-type criteria: first rule out "occluding itself", then verify against a known state (2026-09-20, Project B)

**Trigger**: criteria that use ray occlusion to measure things like "how much of the eyeball is exposed when the eyes are closed".

The first version put the entire `Body` mesh into the BVH and cast rays from the front toward the eyeball vertices — **0.0% exposed even with eyes open**.
Cause: in front of the eyeball there is also a **cornea/highlight transparent card**; the rays hit it first, so every eyeball vertex was judged "occluded".
**Fix**: when building the BVH, cull the faces of **the eyeball itself** (exclude any face with a vertex in the eyeball cluster), keeping only eyelids and skin as occluders.
After the fix: eyes open 33.5%, `vrc.blink` 0.0%, single-eye `wink` closes only one side (L=0 / R=34.16) — **only once it can discriminate does the criterion count as valid**.

> **Checkable question**: in a state where "it definitely shouldn't alarm", is my criterion's output clearly different from the "should alarm" state?
> Verifying only the "should alarm" side misses always-zero criteria; **an always-zero criterion always looks like a pass**.
> After judging, ask once more "is this zero a zero with margin": Project B also ran four levels blink=0.6/0.7/0.8/0.9,
> and the vendor and post-bake curves tracked each other (at 0.9: 4.31% vs 5.47%) before we dared say "eye close isn't broken, no compensation needed".
> Related: [Zero and identical both ≠ pass](zero-and-same-arent-pass.md).
---

## The same ruler has a second use: **measure the visible region first, then decide where to put content**

**Trigger**: you tuned position parameters in an **empty disc / unoccluded preview**, but once applied to the real model it's "completely invisible".

Project B's in-eye meteor fell into exactly this on 2026-09-21: rendering the lens alone on black, the meteor looked great (peak 211/255),
but applied to the eye it was not visible at all. After eliminating layer by layer it turned out **the geometry wasn't fully occluded and the shader wasn't failing to draw; the position was wrong** —
the meteor band's `_MLMeteorArea` v range 0.58–0.95 had been tuned on the empty disc, and that segment sits right behind the upper eyelid.

**Measurement** (same ruler as above, just replacing "pass/fail" with "per-bin visibility"):
render two images — ① only the target surface, in a solid marker color; ② target surface in solid color + the full occluders.
For each marker pixel in ①, check whether it is still the marker color in ②, and **compute visibility per position bin**:

| Eye disc v | 0.75–1.00 | 0.70–0.75 | 0.65–0.70 | 0.60–0.65 | 0.10–0.60 | 0.00–0.05 |
|---|---|---|---|---|---|---|
| Visibility | **0%** | 8% | 60% | 93% | 81–100% | 5% |

After changing to v 0.12–0.62, visible brightened pixels went 121 → 943 (**7.8×**) and peak contrast 41 → 99 (**2.4×**).

> **Checkable question**: was this position parameter set in the **real, occluded environment**, or in an empty disc/preview?
> Numbers tuned on an empty disc are only a starting point. **A different base avatar has a different eyelid shape; this visibility table must be re-measured, not copied.**
> Threshold trade-off: only bins with visibility ≥90% count as "usable"; 60–90% bins are only for enter/exit transitions; <10% are not used at all.
