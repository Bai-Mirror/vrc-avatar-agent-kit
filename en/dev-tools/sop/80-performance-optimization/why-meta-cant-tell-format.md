> 🌐 English translation · [中文原文](../../../../开发工具/SOP/80_性能优化/为什么不能读meta判格式.md)

# ⚠ Why you cannot read `.meta` to determine texture format

> A subpage split out of [`80-performance-optimization.md`](../80-performance-optimization.md). It takes over the same-named mechanism explanation under step 4; step 4's criteria remain on the main page.

### ⚠ Why you cannot read `.meta` to determine texture format

The `textureFormat` of `DefaultTexturePlatform` in `.meta` is **almost always `-1` (Automatic)** ——
measured on one project: of 777 textures, 563 were `-1` and 214 were `1`; **not a single `RGBA32` ever appears**.
The real format is chosen automatically by the importer per platform; `.meta` simply does not record it.

Counting “how many are RGBA32” by the `.meta` enum value **always yields 0** ——
this is a **false criterion that always passes**, more dangerous than having no criterion: it makes people think they checked.

**Correct approach**: write a probe script that reads the runtime `Texture2D.format` and let Unity report it.
Judge “uncompressed” by the format name containing `RGBA`/`ARGB` and not being DXT/BC family, not by enum numbers.

> A similar trap: normal maps report as `DXT5` (DXT5nm, X stored in alpha);
> **do not treat them as “DXT5 with alpha” and convert to DXT1** — that destroys the normals.
