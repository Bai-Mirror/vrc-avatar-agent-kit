> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/02_环境准备与人工介入/B850_Linux环境/Blender脚本的坑.md)

> ← [This machine (Linux) Linux environment](../b850-linux-environment.md) · [Scripting pitfalls](scripting-pitfalls.md)

# Blender Scripting Pitfalls (bpy 5.2 / Headless Rendering / Geometric Quantities)

Moved on 2026-09-25 from the appendix at the end of “Scripting pitfalls”. What they share with that page: the script does not error, but the reading is not the quantity you think it is.

## 1 · Blender 5.2 bone API (09-22 tongue-piercing chain L5-1, reported by DSH)

- `bpy.types.Bone` **no longer has `roll`**: read `EditBone.roll` in edit mode, or back-compute it from `bone.matrix_local`.
- `Bone.x_axis/y_axis/z_axis` are measured to be in **parent-bone space** (the same world orientation gives different readings for root and child bones). To check “a bone's local axis points along some world axis”, always use `bone.matrix_local.col[i]`, otherwise the criterion will silently prove itself true.
**Checkable question**: which space and which version's attribute is the bone axis/roll I am reading? Have I run a counterexample on 5.2 once?

## 2 · False alarm from headless EEVEE (09-22 L5-4f)
`blender --background` rendering EEVEE prints `amdgpu_device_initialize failed / failed to load driver: radeonsi`, and when a small object is in a large frame the whole-frame mean looks like pure background, making it easy to misjudge “EEVEE is unavailable”. Use **non-background pixel count** as the criterion (or render a mask to measure the object's pixel width); measured, it renders fine.

## 3 · Units, precision and criterion pitfalls in geometry scripts (09-22 tongue-piercing chain L5-5, 09-23 L5-7)
- `mathutils.Vector` is **float32**: rewriting the same algorithm outside Blender with numpy float64 differs by ~1e-6 per point; for “point-by-point agreement”, run it back in Blender with mathutils, or compare at the other side's stored precision (e.g. round to 8 digits).
- `BVHTree.find_nearest/ray_cast` return **scene units** (the .blend files in this workspace are mostly meters): multiply by 1000 before writing the report, otherwise “0.0039 mm” is actually 3.9 mm.
- On an open sub-mesh (a piece cut out of a larger mesh), using the normal's sign to judge “did it penetrate” gives **false negatives**: near edges signed is negative while the actual separation is 1.5 mm. Always judge penetration with `BVHTree.overlap`; use signed only for depth diagnosis.
- In a pose family that only rotates the root bone + translates one child bone, the relative distance between two pieces of geometry rigidly driven by the same bone is constant — when sweep readings do not change with the parameter, check this first; the script is not broken.
- “Single-triangle normals” give false rotation angles under narrowing/shearing (09-23 L5-7: 8.27° vs neighborhood-weighted 0.47°) → use neighborhood area weighting for surface-normal criteria.
