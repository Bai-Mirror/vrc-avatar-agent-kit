> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/40_贴图配色/素体贴图与改色手法/眼贴图包多半是整脸图集.md)

> ← [Base texture and recolor techniques](../base-texture-and-recolor-techniques.md)

# An “eye texture pack” is usually a whole-face atlas: whether it can be transplanted directly depends on the eye-disc bbox

**Trigger moment**: the client / we ourselves have picked an eye texture pack and are about to hook it up to the base avatar's face material.

## First see clearly what it is

Packs on Booth called “◯◯ eye texture” **often contain an entire 4096² face atlas** (`_MainTex`), not a standalone small iris image.
That's because the base avatar's face is one atlas: scalp, eyebrows, eyelashes, mouth, decorative parts, and **the left and right eyeball discs** are all packed into a single 4096².
So “swapping the eyes” at the file level means “swapping the whole face texture” — **it swaps the makeup along with it**.

## Criterion: whether the eye-disc bounding boxes of the two images match pixel for pixel

Official / third-party textures for the same base avatar share the UVs → **the eye discs' position and size in the atlas must be exactly the same**.

Method (as done for Project B Milfy):
1. Segment the eye discs in each of the two images (first see what color the outer ring of the eye disc is, set an RGB threshold on that color, take min/max x row by row and fill);
2. Compare the bboxes. Match → **you can transplant directly by coordinates, with zero alignment error**;
3. Then do a **left-right symmetry check**: `(image width − 2) − L.x_max ≈ R.x_min`. A mismatch means the segmentation got polluted by something like the eyelash strip in the middle; tighten the x range and redo.

Measured conclusion: in one eye texture pack, several variants had eye discs in exactly the same position as the face texture used in the project → same UV, transplant directly;
another pack at first glance had a different layout (larger eye discs, no small side pieces) — but see the next section: this “difference” was later proven to be a misjudgment; the measured difference was small.

## Swap only the eyes, not the makeup: composite with an eye-disc mask

Don't replace the whole image. Measured: two face textures with the same UV still differ noticeably over large areas **outside the eye discs**
(makeup, blush, decorative parts are all different) — replacing the whole image changes the face along with it.

Method: `out = new·w + original·(1−w)`, where `w` = the eye-disc mask with a 5 px Gaussian feather.
For packs with different UVs (such as Prism): `resize` its eyeball alpha bounding box to this base avatar's eye-disc bbox, then apply the same mask.
> **The alignment reference can be taken from the mesh**: rasterize the loop-UV polygons of the vertices displaced by the blend shapes (`pupil_*` / `highlight_*`) into a mask,
> and you get the **exact position of the pupils/highlights in the atlas**, without eyeballing. Note that this kind of mask gives you the “pupil”; **the eye disc itself has to be segmented separately**.

## First ask “is this pack made for this base avatar?” — **if so, transplant directly, don't scale a single pixel**

On 2026-09-20 I made two mistakes in a row here, at the cost of two rounds of rework:
I treated a texture pack that was **made for Milfy in the first place** (the Prism series; both its path in the library and the pack name carry the base avatar's name)
as “a texture for a different base avatar”, first scaled it once by the eyeball bounding box, then after agy pointed out an offset, did an affine transform by the iris box —
**both times I was fixing a problem that did not exist**; the result was a shrunken iris with a blank band left below it, uglier than a direct transplant.

**Criteria (run these two first, then decide whether to scale)**:
1. **Source**: does the pack's path in the asset library and its pack name carry this base avatar's name? What base avatar does the product page list?
   The main library's `<素材库>/.booth-archive/manifest.json` `items[].avatars` gives the supported base avatar list directly.
2. **Alpha coverage**: intersect this base avatar's eye-disc mask with the image's `alpha>8`.
   **The signature of native alignment is “coverage ≈100% and the bbox extends only a few dozen pixels beyond the eye disc”** — the extension is **UV bleed**, not misalignment.
   The pack from the previous section that “looked different at first glance” turned out to be exactly this case → native.

**Native → transplant directly**: `out = new·w + original·(1−w)`, `w` = feathered eye-disc mask. No scaling, no translation, no affine.

**Genuinely for another base avatar → only then do the iris-box affine**: segment the iris on each side (native image = non-outer-ring color inside the eye disc; foreign image =
`(sat>30) | (lum<170)` excluding near-white soft glow), scale x/y independently to map the foreign iris box onto the native iris box
(`a=1/sx, c=src_x0−tgt_x0/sx`, whole-image `Image.transform(AFFINE)` then crop with the eye-disc mask),
**and after that segment the iris box again to reconcile** (center difference <10 px, size difference <5%).
⚠ Note that the “eyeball alpha bounding box” **cannot** be used as the alignment reference: how much bleed/peripheral soft glow the bounding box contains is up to each vendor.

## The premise you give the falsification model determines what it will falsify (lesson from the same round)

In my prompt to agy I wrote that “the right column was transplanted from another base avatar and **may be misaligned**”.
So it dutifully went looking for transplant errors and reported back “iris 5–10% too large, pupil too high, hard round edge at the lower rim” — **all three correct**,
but they were **caused by my own scaling**, not a problem with the asset itself. It did not, and could not, question the premise I gave it.

> **Checkable question**: does my prompt to the falsification model contain any sentence that is “my assumption” rather than “an observable fact”?
> If so, first list that sentence as an item to falsify too; at minimum ask it once more “if this premise is wrong, how would your conclusion change”.
> Related: [The criterion itself may be broken](../../troubleshooting/observation-criteria/criterion-may-be-broken.md).
