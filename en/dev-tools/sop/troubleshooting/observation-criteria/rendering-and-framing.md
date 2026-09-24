> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/问题定位/观测口径/渲染与取景.md)

> ← [Observation criteria](../observation-criteria.md) · [00 · Master table](../../00-overview.md)

# Rendering and framing: the image was rendered ≠ anything was drawn

This page is entirely about the "**log all PASS, image wrong**" category. Common thread:
**the file was written and the log says done, but the pixels are wrong** — and downstream (review models, clients) receives pixels.

---

> → [Three pitfalls of the render pipeline (solid color / `-nographics` / duplicate images)](rendering-and-framing/three-render-pipeline-pitfalls.md) — log all PASS but image a solid color: test `getextrema()` first; render batchmode without `-nographics`; when shooting several sets in a row, reload the scene per set and do a pairwise pixel diff.
>
> → [Taking photos of a part in the Editor](rendering-and-framing/photographing-parts-in-editor.md) — four rules for rendering eyes/accessories without entering Play: stale skinning needs `BakeMesh`; isolate with a free layer + `cullingMask` rather than turning off other renderers; add a default-0 time offset to the shader for frame-by-frame reproducibility; use the same frame with "the effect off" as the control for pixel statistics.

>
> → [How to measure whether an effect reads](rendering-and-framing/measuring-effect-visibility.md) — when the base's median luminance is ≥200 the lightness route is dead; use CIELAB to split ΔE into lightness and "chroma + hue" — changing hue is often several times more effective than adjusting brightness; a dark rim alone is net-negative; social viewing distance must be recomputed after downsampling.

> → [Clear the scene before a full-avatar render](rendering-and-framing/clear-scene-before-full-render.md) — "clipping" in a showcase shot: first suspect a second avatar root in the scene (same position); PCS placement targets are real renderers, not gizmos (one render with `cullingMask=0` tells them apart); evaluate tiers via the controller from parameters rather than manual SetActive; outfit hits compare `activeSelf`, not `activeInHierarchy`.

## 1 · A tool's "master copy" and "project copy" diverge

### Trigger
**After a subagent or you yourself modified a tool script under `Assets/Editor/`.**

### Question
**"Is the master copy in `开发工具/通用工具/` still identical to the project copy?"**

```bash
cmp -s "开发工具/通用工具/X.cs" "<工程>/Assets/Editor/AvatarGen/X.cs" && echo 一致 || echo 已分叉
```

### If the answer is wrong
**Back-port the project copy into the master copy** (the project copy is the one that actually ran successfully); back up first.

### Evidence (2026-09-06)
`AvatarPortrait.cs`: master copy 33,160 B, project copy 35,171 B.
Only the project copy had the `ShootOne` and probe debug logging that made rendering actually work.
**Without back-porting, the next order would start from the master copy and lose all these fixes** — and hit the same pitfall again.

⚠ Side note: **order-specific scripts** (e.g., `CommCSetup.cs`) should not stay in
`Assets/Editor/AvatarGen/`, the directory for general-purpose tools; before delivery packaging, remove them and their diagnostic menu items.


---

## 2 · Zoned criteria: **first prove you're measuring that body part**

### Trigger
**When you're going to measure pixel differences per "body part" zone, to judge whether a zone's parameters took effect.**

### Question
**"How do I know this y band really is the eyebrows (/mouth/eyes)?"**

### If the answer is wrong
**Don't pick coordinates off the top of your head. Do a horizontal band scan and let the changes surface by themselves**:

```python
for y0 in range(250, 900, 40):
    ...  # one band every 40 px; compute pairwise sumdiff / significant pixels across options; print as a histogram
```

Whichever bands the changes concentrate in are the body part you want to measure.

### Evidence: I got this wrong twice in a row (2026-09-06)

**Mistake one: measured the wrong band.** I guessed the "brow zone" as y300–380 and measured six pairwise groups with
**significant pixels = 0**, concluding "the eyebrow keys are dead on the candidate images, hidden by the bangs".
A later band scan showed **y250–410 was all 0** — that whole stretch is the **forehead**, where nothing would change anyway.
The real brow zone is **y410–490**.

**Mistake two: the conclusion was also backwards.** Re-measured on the correct band:

| | Brow zone y410–490 significant pixels | Eye zone y490–610 (control) |
|---|---|---|
| With bangs | **5,668** | 89,426 |
| Bangs hidden | **22,015** | 102,428 |

The eyebrows were **never "dead"**; with bangs there were already 5,668 significant pixels, rising 4× with bangs hidden.
I read "I measured the wrong place" as "that body part is occluded".

### Criterion: **a zero result must first rule out "measured the wrong place"**

> **When a zoned criterion yields 0, the first explanation is always "this zone was never supposed to change", not "the parameter didn't take effect".**
> How to rule it out: **the same scan must include a control band known to change** (here, the eye zone).
> Control band also 0 → the data is wrong; control band normal while target band is 0 → only then consider "the parameter didn't take effect".

This is the spatial version of the same law as [The shape of a criterion](shape-of-a-criterion.md):
**criteria with a control expose themselves on the spot; criteria without a control output confident false conclusions.**

> Also keeping one observation that still holds: `mouth_corner_angle_up = 15` in the mouth zone
> (band scan confirmed six-group differences of 0 at y730–810, while that band did contain mouth structure in other scans)
> had a max pixel difference of **1** — **a key with too small an amplitude is as good as absent in review images**.
> But note: this too requires first confirming that the mouth is what's being measured, so as not to repeat the brow-zone mistake.

---

> → Stale edit-time rendering, whether baking can save it, and whether baked-avatar paths are right — all three have been merged into
> [Taking photos of a part in the Editor](rendering-and-framing/photographing-parts-in-editor.md) (merged 2026-09-21; formerly section 6 of this page and the two sections after it).
