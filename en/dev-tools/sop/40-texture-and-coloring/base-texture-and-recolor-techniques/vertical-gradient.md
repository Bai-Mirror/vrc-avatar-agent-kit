> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/40_贴图配色/素体贴图与改色手法/竖向渐变.md)

# Vertical gradients (requests like “lighter on top, darker at the bottom”)

> A subpage split out of [`base-texture-and-recolor-techniques.md`](../base-texture-and-recolor-techniques.md). It takes over the vertical-gradient section of “Base texture and recolor techniques”; the read-back self-check criterion remains on the main page.

### Vertical gradients (requests like “lighter on top, darker at the bottom”)

Two pitfalls, both actually hit:

1. **Don't guess the direction.** PNG row 0 is at the top, the Unity UV origin is at the bottom left, and the two flips are easy to get tangled in;
   the relative position of the eyebrow island and the eye island in the atlas says nothing about direction on the face either.
   Criterion: take the vertices whose UVs fall inside the band, **split them into columns by u**, compute the slope of `dY/dv` per column, then vote
   (the overall correlation coefficient gets diluted to r=0.12 by the curve of the brow ridge; after splitting into columns, 9 of 12 columns have the same sign and the conclusion is clean).
2. **Normalize t per column**, not with the global bbox — the eyebrow is an arc, and computing by row globally would drop both ends of the arc entirely into “top” or “bottom”.
3. **Damp the luminance scaling** (measured factor 0.35). The original eyebrow is already denser on top and lighter at the bottom;
   multiplying directly by `lum/ref` cancels out exactly the gradient you want — the first version differed by only 3.4 luminance between top and bottom, after damping by 17.6.

Every step needs a **read-back self-check**: the measured luminance of the top and bottom segments must really differ, otherwise the direction or the mask is wrong.
