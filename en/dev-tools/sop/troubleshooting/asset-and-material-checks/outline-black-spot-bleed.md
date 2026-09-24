> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/问题定位/素材与材质排查/描边穿出黑斑.md)

# Black spots at clothing folds: first suspect the outline shell bleeding through

> 2026-09-19, Project B tier 7 foggy knit (LOVACE Fog Knit): one black spot on each side of the `Knit` collar fold.

## Trigger
The black spot persists when rendering only this one item (`only_renderers`), it's located at a **fold/lapel where two layers of fabric sit very close**, and the material is lilToon with outline (`Hidden/lilToonOutline`, `_OutlineWidth`>0, outline color near black).

## Question
"If I temporarily set this item's outline width to 0 and render the same camera position, is the black spot still there?" — change the **build copy**'s material in Play (`Packages/com.vrcfury.temp/...`), without touching the original; it's discarded automatically on exiting Play.
- Gone → it's the inner fabric's outline shell (the backface expanded outward) showing through between the outer fabric.
- Still there → not the outline; check mesh gaps/flipped faces (`_Cull`; lilToon's default `_Cull=0` is already double-sided, so the "make double-sided" the user picked is often already double-sided).

## Fix (trade-offs)
| Approach | Cost |
|---|---|
| Set `_OutlineZBias` to 0.005 (push the outline back) | Adopted in this order: black spot gone, silhouette line kept; **copy the material** into `_Custom_<单>/Materials/` and assign it only to this item — the vendor White material is shared by several prefabs, don't change the original |
| Outline width 0 | The whole item has no silhouette line; style changes |
| Lighter outline color | Black spot becomes a gray spot; still there |
| Paint an outline-width mask / patch faces in Blender | Most precise, but requires making a texture or editing the mesh; use when ZBias isn't enough |

If ZBias is too large, silhouette lines that should be there up close get covered by the item's own fabric: after the change, render one front and one side view and check the silhouette lines are still there.

## Verification
Blind test of mixed before/after images from the same camera position sent to agy (answer key kept locally): in this order gemini correctly pointed out both before images and flagged nothing after; claude misreported the large black bow on the back (a design element) once — it didn't flag the same bow in the before images, so this can be judged a false report.
