> 🌐 English translation · [中文原文](../../../../开发工具/SOP/80_性能优化/AAO实际做了什么.md)

# The three things AAO actually does, and how to verify each

> A subpage split out of [`80-performance-optimization.md`](../80-performance-optimization.md). It takes over the same-named section (measured on Project C, 2026-09-07); AAO default settings and acceptance criteria remain on the main page.

## The three things AAO actually does, and how to verify each

Measured on Project C, 2026-09-07 (996,612 → 922,682 polygons, 671.0 → 160.7 MB).

### ① Deletes renderers that are “always off”

In this order it deleted the base avatar's built-in `Cloth_*` `Hair_*` `Other_ear/tail`, **89,072 polygons** in total.

**The criterion for verifying it is safe** (not a render — a render only shows the default state):

```bash
grep -rl "<被删物件名>" Assets/_Work/_60菜单/       # any .anim/.controller/.asset
```

**No clip references it = it is always off = deleting it is correct.**
Mentions only in probe text logs do not count —— those are not animation assets.

⚠ **Conversely, if a clip references it and it was still deleted, that is a real defect**; investigate why AAO's trace did not see it.

### ② UV repacking + reducing single-color regions to 1×1

It generates, under `Packages/nadena.dev.ndmf/__Generated/**`,
`xxx (AAO UV Packed).asset` (on the order of 2048² → 512×1024) and
`AAO Monotone RGBA(...).asset` (1×1, for textures whose sampled region is constant).

**This is the main source of the texture memory drop, not the compression format.** Most of this order's −76% came from here.

**In the texture list you will see materials' textures pointing into `__Generated/`** —— that is normal, not broken.
**But these are regenerated on every build; do not ship them in the delivery package.**

### ③ Merges skinned meshes

It generates `$$AAO_AUTO_MERGE_SKINNED_MESH_N`. AAO only merges meshes whose **activeness animations are exactly identical**,
so it will not merge two independently toggled items together.

### ⚠ In the before/after comparison table, cite the correct “texture memory before” reading

If a tool changed import settings and then reset them, the log will contain **multiple before readings**.
**Cite the last one (after the reset)**. In this order the log reads 649.3 → 671.0 → 160.7 in sequence;
the subagent's report table cited 649.3 (the voided one); the true value is 671.0.
