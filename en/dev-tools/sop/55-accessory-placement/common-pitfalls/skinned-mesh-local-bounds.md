> 🌐 English translation · [中文原文](<../../../../../开发工具/SOP/55_配饰装位/通用坑/蒙皮件localBounds.md>)

# Skinned pieces whose armature was moved: `localBounds` must be recomputed at the end

> Subpage split out of [55 · Accessory placement / Common pitfalls](../common-pitfalls.md). Takes over the localBounds section of the common pitfalls and its “all-green log but empty image” self-check; this is the root cause of culling diverging from the criteria.

## Skinned pieces whose armature was moved: `localBounds` must be recomputed at the end

`SkinnedMeshRenderer.localBounds` is **baked into the asset**, and Unity uses it (after the root bone transform) for frustum culling.
After moving/rescaling an accessory armature, this box drifts away from the real geometry —
measured: the animal ears' self-reported box was at y=3.9 meters while the real geometry was at y=1.2 meters, **no overlap at all**,
so the whole mesh was culled from **every camera position** and not a single pixel was drawn. All 8 renderers of the ear/tail package were hit.

Method: skinned world vertices → transform into `rootBone` local space → build a bbox → leave a 5cm margin.
Don't paper over it with `updateWhenOffscreen = true` (recomputed every frame; penalized in the VRChat performance panel).

### “All-green log but empty image” → first suspect the criteria and the renderer are looking at different things

I spun on this bug for four or five rounds before finding it, because **all criteria were computed from vertices**
(`mesh.vertices` × bone matrices), while culling looks at **the renderer's box**, and the two can diverge arbitrarily.
One line is enough for a self-check: print `Renderer.bounds` next to the measured vertex bbox, and alert if they don't coincide.
