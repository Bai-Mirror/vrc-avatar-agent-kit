> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/40_贴图配色/素体贴图与改色手法/拼瞳撞色与选色.md)

# Two-color split irises and contrast color picking (including the no-op of luminance compensation)

> A subpage split out of [`base-texture-and-recolor-techniques.md`](../base-texture-and-recolor-techniques.md). It takes over the three split-iris/contrast-color sections (split line, color picking, luminance compensation) from the end of the “Base texture and recolor techniques” page; steps and criteria remain on the main page.

## Two-color split irises: the split line must sit on the **dark band already present in the source image**

**Trigger moment**: stacking two iris textures from the same series top-and-bottom into a contrast split (like Milfy's stardust: `pink` upper half + `X` lower half).

**Self-check question**:

> Does my split line fall on a **bright area** or a **dark band** of the source image?

**Been burned (Project B v2 eye texture, 2026-09-20)**: two split lines were made for the same stardust texture set,
one at the position carried over from the previous round, one moved up into a bright area (wanting blue to take up more).
The latter was judged major by agy's blind check as a “harsh horizontal dark discontinuity”; the former drew zero flags.

Only after checking pixels did it make sense: **all three source images (pink/blue/yellow) have a built-in dark band in the same row range**
(V drops by about 10% in all three colors) — that is the upper-eyelid shadow cast on the iris.
The feather zone of the carried-over line **happened to cover exactly this dark band**, so the contrast transition was hidden by a natural shadow;
the one moved up into the bright area had nothing to cover the luminance difference, and it showed up directly as a horizontal line.

**Method**: before stacking, first print the **luminance profile of the source image itself** (row by row, mean V of pixels inside the alpha),
and align the feather zone with the lowest point. If the split line set in the previous round “looks fine”, first check whether it sits on the dark band before deciding whether to move it.

## Contrast color picking: check whether the hue wheel goes the short way or the long way

The transition band between two colors **passes through every hue between them on the color wheel**. Going the long way passes through unwanted colors.

> Measured (same as above): the current **pink + gold** hue path goes 318°→**5°**→34°, around the long way through red/orange,
> dropping in the middle to saturation 0.53, `rgb(161,83,76)`, a **brick-brown mud color** (independently flagged by agy as “muddy brown”).
> Switching to **pink + blue** goes 318°→purple→215°, the short way; saturation stays ≥0.48 throughout, and the transition band is a clean purple.

**Self-check**: how far apart are the hue angles of the two main colors? >180° means the long way, and the transition band will necessarily pass through the complementary region — compute it before painting.

## ⚠ Don't do “luminance compensation”, it's a no-op

After a linear blend `out = a*w + b*(1-w)`, trying to “pull the luminance back to the linear interpolation of the two ends” is a **mathematical identity**:
luminance is a linear function of RGB, so `lum(a*w+b*(1-w)) ≡ lum(a)*w + lum(b)*(1-w)`, and the gain is always 1.

> Been burned (same as above): I wrote a luminance-compensation version and only noticed when the output was **point-for-point identical** to the uncompensated version.

**Criterion**: after writing any compensation-type operation, take a **per-pixel diff** of the before and after images; a difference of 0 means it is a no-op.
If you really need to change the luminance at the seam, do it in a **nonlinear** space (e.g. add a bias to V or L\* alone), or just move the split line.
