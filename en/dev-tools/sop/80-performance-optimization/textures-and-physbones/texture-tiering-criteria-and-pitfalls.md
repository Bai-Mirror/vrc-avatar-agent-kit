> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/80_性能优化/贴图与动骨/贴图分级判据与坑.md)

# Texture tiering: criteria, tools, and six pitfalls

> A subpage split out of [`textures-and-physbones.md`](../textures-and-physbones.md). It takes over the sections “Generate a plan with the tool first” and “Texture tiering: three pitfalls you will hit”; how to check format and size, the red lines, and A/B testing remain on the main page.

## Generate a plan with the tool first: `通用工具/tex_tier_plan.py`

```bash
python 开发工具/通用工具/tex_tier_plan.py <工程目录> [--csv out.csv]
```

It does not open Unity; it follows the plain-text chain **scene → prefab → material → texture → .meta**,
assigns tiers by shader property, and outputs a per-texture “current → target” list. It only produces a plan and does not modify files.

### ⚠ Three criterion pitfalls this script smooths over (2026-09-09; I got each wrong first and then fixed it)

**① `maxTextureSize` is a cap, not the actual size.**
A 512 source image with a 2048 cap still occupies 512 worth of VRAM. Estimating by the cap **overstates by 7×**
(estimated 1107 MB / measured on the baked avatar 160.7 MB). You must read the image file header to get the real size,
then take `min(source long edge, import cap)`. For ones whose size cannot be read (exr/hdr/tga), mark a question mark; do not substitute the cap.

**② Looking only at GUIDs that appear directly in the scene YAML misses a lot.**
Materials on prefab instances live in the `.prefab`; the scene only references the prefab ——
without a transitive closure, Project C found only 10 materials while there were actually 79. You must expand prefab/controller/asset.

**③ Even with ① and ② fixed, the total is still only an upper bound, not an expected gain.**
The closure counts materials that AAO strips after the build, and the compression format can only be assumed.
**There is only one criterion for the real gain: rerun `PerfReport.cs` after the change and compare before/after.**
Per-texture suggestions are reliable (tiering by property is independent of the total); do not report the total figure.
## Texture tiering: three pitfalls you will hit (measured 2026-09-01)

### ① Decide “is it a main texture” with an **allowlist**, not an aux blocklist

lilToon has dozens of auxiliary texture properties (`_RimColorTex` / `_MetallicGlossMap` /
`_ReflectionColorTex` / `_Bump2ndScaleMask` / `_MatcapBlendMask` …); a blocklist will inevitably miss some.
The missed ones get treated as main textures and assigned the 2048 tier, while the vendor originally set them to 512 ——
**raising one means 16× the memory**; measured texture memory actually rose from 102.6 to 139.9 MB.

Correct approach: `MainProps = { _MainTex, _Main2ndTex, _Main3rdTex, _BaseMap, _BaseColorMap, _Albedo }`;
any property not on this allowlist is treated as an auxiliary texture.

### ② Judge by **shader property**, not by file name

Kitty's normal map file name is just a number —— the name has no “normal” in it, so judging by file name would treat it as a main texture. Check which material slot uses it (`_BumpMap` etc.) and its import type.
It is assigned to `_BumpMap`; judging by property makes it obvious. File names are only a fallback.

### ③ Only explicitly named textures may be **raised**; everything else is only lowered, never raised

After A/B, when you need to bring a texture back from 512 to 1024 you must be able to raise it; but setting in both directions indiscriminately raises all the textures the vendor deliberately lowered.
The boundary: entries named in the `Explicit` table are set in both directions; the rest are changed only `if (current > want)`.
- **Changing TextureImporter requires `SaveAndReimport()`**; only `SetDirty` + `Refresh` does not persist to disk. Back up the original settings before changing, and do not overwrite an existing backup. For tiering, use `tex_tier_plan.py`/`tex_tier_apply.py` to judge usage by shader property, reimport after modifying .meta, and read back; the old `TexOptimize.cs` is only a reference for compression formats, and its file-name-based tiering logic is not reused.
