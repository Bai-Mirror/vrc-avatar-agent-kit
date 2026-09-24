> 🌐 English translation · [中文原文](../../../../开发工具/SOP/50_服装发型装配/给衣物补形态键.md)

# Adding blend shapes to clothing (when the vendor didn't provide a certain bust/body-shape key)

> Parent: `../50_服装发型装配.md`. On 2026-09-19 `Breast_small` was added to Project D's Esmera nipple covers; the first attempt via Blender failed, the second done directly in Unity succeeded.
> Rerun script (C-12): `开发工具/通用工具/审查/unity/Editor/NipplePatchFrames.cs`, menu `Tools/AvatarAudit/Nipple Patch Frames (Edit Mode)`; request `Library/AvatarAudit/nipple_patch_frames_request.json`, example `审查/unity/examples/nipple_patch_frames_request.json` (the original values of Project D's two frames).

## Trigger
Some body key gets driven (bust radial, foot-shape tier), and some skin-tight garment/accessory **doesn't have that key**, so it floats off or sinks in as soon as the body changes (nipple covers floating 4–8 mm off at `Breast_small=38`).

## Preferred: add a frame to a copy of the original mesh in Unity (no FBX round trip)
1. In edit mode, under the scene's real bones: `BakeMesh` once each with the body key at 0 and 100 → world-space displacement field.
2. `BakeMesh` the item once; for each item vertex, inverse-distance-weight the displacements of the body's 4 nearest vertices → world displacement.
3. Use the inverse of the item's skinning matrix `Σ wᵢ·(worldToLocal·boneᵢ.localToWorld·bindposeᵢ)` to convert the world displacement back to mesh space.
4. `Instantiate(original mesh)` + `AddBlendShapeFrame(key name, 100, displacement, null, null)` → save as `.asset` under `Assets/_Work/…`; the renderer only swaps `sharedMesh` (bones and materials untouched, **not Applied to the vendor prefab**), then add MA BlendshapeSync bound to the body's same-named key.
- Benefit: base geometry, bone weights and bindposes are **bit-for-bit identical** to the original; no export-space issues exist. The script is the four steps above, about 40 lines of `execute_code`.

## Why not go through Blender first
Done in Blender and verified by round trip inside Blender it was “0.000 mm”, but **after importing back into Unity the skinning result was off by 71 mm**: the exported mesh space and bindposes differed from the vendor's original FBX (vertices off by up to the 1 m level, bindposes off by 1.27, displacements scaled down 100×), while the renderer used the original bones in the scene.
- **Checkable question**: “After swapping in the new mesh, with the body key at 0, how far does the item's `BakeMesh` world position differ from the original mesh per vertex?” — it must be ≈0, otherwise don't proceed.
- If you really must go through Blender (e.g. to sculpt details), always do acceptance in Unity with the comparison above; don't trust Blender's internal round-trip numbers.

## Acceptance
In edit mode measure the quantiles of the item-to-body nearest distance: the new item should be of the same magnitude as the “original at tier 0” at body key 0 / default / 100 (Project D: p50 1.33 → 1.28 → 1.13 mm; the original at tier 38 was 5.74, at tier 100 14.48); at tier 0 new and old are identical value for value. In Play only read back the key values (the item's key follows the body); **do not** swap meshes in Play for comparison (see the last section of `收缩键可见后果_渲图对照.md`).
- When cross-checking keys across tools note: Unity's blend shape indices don't include Basis, so they are 1 less than Blender's shape_keys indices; match by name, not by index. When the outfit's own skeleton gets bones renamed/merged after import, fall back to matching by bone name.

## Changing frames of an “existing” key (09-23 tongue-piercing chain L6-A)
Unity `Mesh` has no API to modify a specific blend shape frame: you can only `ClearBlendShapes()` and then re-`AddBlendShapeFrame` **all** keys in the original order (or a new order). After the refill the key indices may change; `SetBlendShapeWeight` on the renderer and animation bindings must all be restored **by name**, not by index.
