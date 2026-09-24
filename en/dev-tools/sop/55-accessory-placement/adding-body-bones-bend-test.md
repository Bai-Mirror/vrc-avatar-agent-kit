> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/55_配饰装位/给身体加骨的弯曲试验.md>)

> ← [55 · Accessory placement](../55-accessory-placement.md)

# Bend test after adding bones to a body mesh (tongue etc.)

**Trigger**: when you insert new bones into a section of the base avatar mesh (tongue, ears, tail root…) and compute weights, and need to judge “will it break at the maximum bend pose”.
Source: tongue-piercing chain L5-4 → L5-4b (2026-09-22, the L5-4 and L5-4b entries of `_长程任务_20260922_舌钉链饰品/施工记录.md`): a test render was judged a blocker by Gemini for self-intersection on the inner bend side; only after adding quantification was a yaw distribution with zero self-intersection found.

## Checkable questions
1. Were the **blend shapes actually active** in the test-render pose applied? (L5-4 missed `tang_narrow` 80 of the tongue-pull state; tongue width was computed at rest as 16.8 mm, 5.5 mm wider than actual.)
2. Does the skinning method match the target platform? Unity's SkinnedMeshRenderer is **linear blending**; turn off `use_deform_preserve_volume` on the Blender Armature modifier.
3. Did you compute the geometric lower bound: centerline bend radius R = arc length ÷ total angle (radians); **if R is less than the half-width there, the inner side must fold over**; weights can't save it — only more arc length or less angle.
4. Measure before looking at images:
   - `N_x` = number of pairs **not sharing vertices** in the self-overlap of the deformed submesh triangle BVH (true self-intersection);
   - `N_fold` = number of edge-sharing adjacent face pairs with normal dot product < −0.2 (creases);
   - `r_min` = minimum edge length ratio (deformed / rest).
   First confirm `N_x>0` on a configuration already judged broken (the metric catches the problem), then sweep.

## Trade-offs
- **N_x=0 doesn't mean it looks fine**: the tongue at 15/25/40 has zero self-intersection but N_fold=8, and the render still shows a step on the inner bend. Acceptance must report both N_x and N_fold, plus a 45° oblique render of the inner bend side sent to agy.
- Sweep order: first sweep **angle distribution across joints** (cheap, doesn't change the armature), then sweep **total angle** (changes numbers in a plan the user has seen — ask), and only last move bone positions (changes the bone table — go back to the plan). Tongue measurement: widening box-kernel weights (w 1–3.5 mm) made it worse; no improvement found on the weight side.
- At a fixed total angle, shifting angle toward distal joints isn't necessarily better: tongue 5/25/50 had more self-intersection than 15/30/35, because distal segments are shorter.
- **The review image must match “how it will be seen”** (L5-4e→4f): with an orthographic 30 mm macro + flat shading + wireframe, tongue-only image, Gemini judges any large LBS bend a blocker (on such an image every crease of a 494-vertex low-poly mesh is magnified); switching to a game view (smooth shading, textured, whole face, perspective vFOV 60°, 0.3/0.5/1.0 m) the whole tongue is only 59/36/18 px. Produce both kinds: macro images with geometric metrics (`N_x`, `N_fold`, crease angle) for engineering comparison, game-view images for the “can it be delivered” judgment; state clearly in the review prompt which kind the image is.
- Tongue measured conclusion: switching weights from “linear over neighboring bones” to **a box kernel along arc length, w=6 mm**, with the yaw distribution unchanged (15/30/35, total 80), self-intersection went 2→0 and crease angle 148°→97°, without touching the angle values the user has seen.

