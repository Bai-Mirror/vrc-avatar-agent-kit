> 🌐 English translation · [中文原文](../../../../开发工具/SOP/40_贴图配色/素体贴图与改色手法.md)

> ← [40 · Texture and coloring](../40-texture-and-coloring.md)

# Base texture and recolor techniques

What this page solves: how to swap, recolor, and make gradients on base avatar textures (eyes / makeup / body), plus techniques for recoloring outfits without breaking unrelated parts, without touching vendor materials, and without painting small items into one flat cloth. The criteria and past incidents referenced by steps 2~4 and 6 of the main page are all here.

---

## Base avatar textures (eyes / makeup / body) — a separate matter from outfit recoloring

Outfit recoloring changes `_Color`; **a base avatar texture swaps the whole image**, which goes down a different path.
The “eye color” and “hair color” in the requirements questionnaire mostly have to be delivered via base avatar texture packs;
missing them means an entire ordered requirement goes undone (the 輝夜 order almost missed a pack of 203 textures).

### First tell overlay layers from whole base images apart

Judge by **alpha opaque ratio**; it separates them at a glance:

| Type | Opaque ratio | Usage |
|---|---|---|
| Whole base image | Comparable to the base avatar original | Swap `_MainTex` directly |
| Overlay layer | Noticeably lower | Hook to `_Main2ndTex`, or **composite offline** into the base image |

**Prefer offline compositing**: the eye-color layer covers the whole eye UV island (mostly opaque inside the island), so it is a whole-eye replacement anyway.
Going through `_Main2ndTex` means babysitting a pile of switches like `_Main2ndTexBlendMode` / `_Main2ndTexAlphaMode` / `_Color2nd`,
and the result depends on the shader version; offline alpha-over gives you exactly what you get, you can open the image directly to verify it, and it doesn't cost an extra sampling layer.

Exception: **if the vendor's manual specifies which slot to use, follow it.** forelise's nipple layer explicitly says “メインカラー2nd”,
and also states that `Nipple_On`/`Nipple_Up`/`Nipple_Big` were **all at 100** when it was painted —
if you only enable `Nipple_On`, the painted areola and the geometric bump won't line up.

```bash
python 开发工具/通用工具/eye_composite.py <工程> --level 5 --pair blue yellow --pupil off
```

### Heterochromia: first prove the two eyes are separate in UV

The left and right eyes of the eye-color layer are usually **two fully separate UV islands** (first measure the column range of each island,
and confirm they do not overlap and have identical opaque pixel counts). Once confirmed, cut along the middle-seam column and take one color per side; no hand-drawn mask is needed.
**After compositing you must read back and verify that the two halves really are different colors**, and the mask must use **the eye-color layer's own alpha** —
using the composite's alpha selects a pile of skin color, both sides measure #D8AE9D, and it looks like “it didn't take effect” when actually the criterion is wrong.

### Recoloring by mask (for things like eyelashes / eyebrows that have no ready-made color)

The asset pack provided eyelashes in 12 color families, but **no silver-white** (even the lightest line, ashgray1, is only #AEA2A3).
This can only be recolored, and both mask sources must be provable, not hand-drawn:

- **Included in the pack**: some packs ship an eyebrow mask texture, one channel of which is exactly the two brow arches (inspect each channel before using it)
- **Subtract two color tiers**: pixels where `|black3 − ashgray1| > 12` are the eyelashes (measured to fall in a separate UV region; the mask is very clean)

Recolor with **luminance-preserving tinting** `new = target × (lum / mean_lum)`; filling a flat color directly gives you a blob with no brush strokes.

> → [lilToon color overlay layers: vendor masks allow local recoloring](base-texture-and-recolor-techniques/liltoon-color-overlay-layers.md) — how to wire up masked overlay layers, mask names lie so measure coverage first, look blend-mode enums up in source, multiply (乗算) can't brighten and the four brightening trade-offs.

> → [Vertical gradients (lighter on top, darker at the bottom)](base-texture-and-recolor-techniques/vertical-gradient.md) — the three pitfalls: don't guess direction (take the band's vertices, split into columns by u, vote on `dY/dv`), normalize t per column, damp luminance scaling to 0.35.

## Shared materials (skip checking and you'll break unrelated parts)

One material slot of an outfit is often shared by several meshes. Measured examples:
`Outfit01` shared by five meshes: shirt/shorts/socks/vest/boots; `Outfit02` shared by bag/underwear/hat/glasses/cat tail.
**Swapping a shared material directly changes unrelated parts.** Override textures can only be hooked to the material slot of a specific mesh.

## Rendering adds one more layer of amplification

A red that looks dull on the texture may render vivid — measured `_MainTexHSVG` saturation 1.75 + `_EmissionColor` 1.414.
**Adjust colors by texture values, accept via simulation or actual rendering; don't draw conclusions from texture thumbnails.**

**Don't read the numbers in a `.mat` directly as colors.** If the project is Linear (`m_ActiveColorSpace: 1`),
the file stores linear floats while the Inspector shows sRGB; describing colors from the file numbers will be wildly wrong.

## Batch material edits must be idempotent

A script with relative operations like “blend 50% toward the target color” drifts a second time if rerun.
- Use a **state file** to record processed items; **don't stuff marker comments into `.mat`** (risk of being rewritten by Unity's serializer)
- First `dry-run` to produce a change-detail table, confirm the magnitude, then apply, **and run it only once**

## What I got wrong (kept from v1.1)

The second-layer texture looked like it wasn't taking effect, and I inferred that lilToon's `LIL_FEATURE_MAIN2ND` feature switch had been turned off.
I checked `ProjectSettings/lilToonSetting.json`: **it was on**. The real cause was that the image's raw pixels were a dull brown to begin with,
and the vividness came from the saturation and Emission parameters.
→ **“I guess some switch is off” must not be stated as a conclusion before it has been verified.**

## Non-destructive recoloring: change `_Color`, don't change vendor materials

lilToon's `_Color` is **multiplied onto `_MainTex`**. So overall darkening, cooling, and contrast accents
can all be done by changing only `_Color`, without touching the texture or the vendor material:

1. Copy the vendor material into the project's own directory (**don't put it in any folder that gets rebuilt wholesale**);
2. `copy.SetColor("_Color", original color × tint)`;
3. Point the target renderer at the copy;
4. **Keep a ledger**: `renderer path|slot index → original material GUID`; restoring depends entirely on it.

Three hard rules (each one was learned the hard way):

- **The ledger records only the original at first touch.** When a later rule in the table overrides an earlier one, the second rule reads what is already the first rule's copy;
  if you record that, the next restore round points to an asset that has already been deleted → material slot null → magenta.
- **Every rule computes from the original.** Multiplying the whole set by 0.26 to darken, then multiplying the contrast items by 0.78, compounds to 0.20;
  the contrast accents end up darker than their surroundings, as if nothing was done.
- **After recoloring you must rerun menu generation.** The material curves of the color layer (when multiple color schemes are merged into one instance) are sampled from the materials
  currently in the scene; if you don't rerun, the old curves will overwrite it back.

## When PSD/CLIP source files exist, prefer editing the source files

Vendors often ship layered source files along with the package (some base avatars include PSD source files, split by body part;
some also carry **gradient map layers** hidden by default — look through the layer list first).

**Edit source files the controllable, traditional way** (`psd-tools` + numpy to read layers, compute gradient maps, composite and export);
**do not redraw textures with generative models** — generative models can't control UV alignment or color consistency,
and the edited images often have seams that don't line up and colors that don't match across parts.

If you really must use a generative model (e.g. to patch a small pattern), you must: strictly constrain the prompt, cross-check with multiple models,
and **only use it on small areas that don't affect UV seams**.

`psd_tools.composite()` may not match the vendor's exported final product (measured mean RGB difference 17.97); compare against the finished PNG before compositing.

The PSD layer alpha is the coverage, so recoloring on the source layer is naturally clean; where to look for source files: `PSD/` `CLIP/` `原本/` directories inside the pack, color-variant `Textures/` in the base avatar pack, other makeup products for the same base avatar.

Source files may be in a different art style (flat hard edges vs the vendor's soft edges); confirm with the user before swapping; only fall back to the flattened image when there truly is no source file, and the algorithm is to re-composite using ink color as coverage, not a hue shift.

> **Source registration and licensing**: register source files centrally by “which pack / which image / version”; check the source of private shaders and paid textures brought in by templates order by order; Patreon shaders don't go into deliveries ([40 main page](../40-texture-and-coloring.md) “Licensing and portability”).

## Recolor per item, not by wildcard

**2026-09-01, the author pointed out**: “Don't rigidly change all accessories to a single color, for example this teddy bear
and the bandages on the legs.” The root cause was a wildcard like `("Outfit_XXX", "*", tint)` in the recolor rule table —
cheap, but it treats the whole outfit as one piece of cloth.

Criterion: **would this thing still be recognizable if its color changed? If not, don't paint it.**

| | Examples | Why |
|---|---|---|
| **Can paint** | Jacket, skirt, top, socks, shoes, gloves, belt, bag | Large areas of fabric; color belongs to the “color scheme”, and it's still the same garment after the change |
| **Can't paint** | Teddy bear, bandages, gauze, blood bag, IV tube, badges, stickers | Small items with their own narrative identity; their color **is the design element itself**, and painting them one flat color erases them from the picture |

Implementation note: **materials are shared across renderers** (in this project the `Shoes` material is used on bandages/shoes/socks at the same time).
Listing rules item by item is the only way to “tint only the socks, not the bandages” — the tinter makes a separate copy of the material for each named slot,
and slots not named are left untouched.

### Contrast accents must be **actively raised**; don't count on them “emerging naturally when the surroundings are darkened”

At one point I wanted to save effort: the blood bag and IV tube are already blood red, so darkening the surroundings to 0.26 would produce contrast naturally.
The render came out wrong — the vendor's original color leans grayish pink, it simply doesn't pop on a pure black base, and reads as a gray patch.
**Small-area contrast accents must be actively brightened and saturated**, and only on one or two items (small area, and core to the narrative).
Large-area color changes only ruin the dark base tone.

> → [Two-color split irises and contrast color picking (including the no-op of luminance compensation)](base-texture-and-recolor-techniques/eye-color-mixing-and-picking.md) — the split line must sit on the dark band already in the source image (print the luminance profile first), a hue-angle difference >180° goes the long way through muddy colors, luminance compensation after a linear blend is an identity no-op.


- **When you get an “eye texture pack”**: it is most likely a whole-face atlas, and swapping eyes = swapping makeup. Whether it can be transplanted directly, and how to swap only the eyes → [An eye texture pack is usually a whole-face atlas](base-texture-and-recolor-techniques/eye-texture-pack-face-atlas.md)
