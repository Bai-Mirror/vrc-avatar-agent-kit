> 🌐 English translation · [中文原文](../../../../开发工具/SOP/30_捏脸/五官缩放几何.md)

> ← [30 · Face sculpting](../30-face-sculpt.md)

# Scaling geometry for layered-card facial features

The problem this page solves: **the eyes of anime base avatars aren't eyeballs; they're dozens of flat cards stacked together**, and any transform that scrambles the layer order causes interpenetration, white specks, and thickened eyeliner.
Needed only for **geometric-scaling** face sculpting; for the type where the user directly sets blend shapes, see [Baking and compensation](baking-and-compensation.md).

The eyes of anime base avatars **usually aren't eyeballs; they're dozens of flat cards stacked together** — pupil, eye white, eye-rim line,
eyelashes and highlights each one layer. Measured: 17 cards per side, **minimum layer spacing 0.03 mm**.
Any transform that scrambles the layer order causes interpenetration, white specks, and thickened eyeliner.

**Thinking through first "which transforms mathematically cannot break the layer order" is much faster than trial and error.**

| Transform | Consequence |
|---|---|
| Scale x/z, pin y | ❌ Not an overall shrink; the middle shrinks inward laterally |
| Full similarity transform, then translate the front edge back to the original depth | ❌ The deepest card gets pushed forward 6 mm and pokes out through the face skin |
| Scale each card around its own mean depth | ❌ Seams split by `0.13 × 深度差` (0.13 × depth difference), measured max 1.46 mm |
| **Apply the same similarity transform to the whole group together** | ✅ Layer order naturally preserved |

Vendors often don't provide a blend shape for "make the whole eye smaller"; to judge, see whether the blend shape moves the skin slot: `eye_big`/`瞳大`/`eye_center` only move `Body_eye`, and the displacement signature of `eye_small`/`瞳小` matches `eye_close` (it closes the eye, not a proportional shrink).

## Mandatory practices

1. Put working files **in place inside the base avatar package's unpack directory**, keeping `*_prebake_backup.blend` and `*_unity_original.fbx`
   — FBX is binary and doesn't go into git; when something goes wrong, only restore points can save you.
2. First verify that the **number of shared vertices between `Body_eye` and `Body_skin` is 0**, otherwise scaling will tear the mesh.
3. **Don't split off the eyebrows by a z threshold to handle them separately** — the eyeliner cards themselves span vertically from the eye to the eyebrow,
   and any horizontal cut splits one continuous stroke into two.
4. **Split into front/deep clusters by depth**: the front cluster gets a full 3D similarity transform; the deep cluster (behind the face skin, invisible) is scaled only in x/z.
   There's a natural gap between the two clusters; check whether any seam points cross the boundary.
5. The eye-socket shadow is painted on the face skin; add a **proportional shrink with smooth falloff** for it, otherwise a gap opens between the shrunk eyelashes and the eye socket, and the eyeball behind is visible from above.
6. **Multiply expression key displacements by the same scale factor** — under a similarity transform both sides multiplied by the same factor keeps the closure relationship exact.
