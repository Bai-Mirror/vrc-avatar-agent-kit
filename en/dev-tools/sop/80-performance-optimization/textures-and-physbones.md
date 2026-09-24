> 🌐 English translation · [中文原文](../../../../开发工具/SOP/80_性能优化/贴图与动骨.md)

> ← [80 · Performance optimization](../80-performance-optimization.md)

# Textures and PhysBones

What this page solves: how to cut texture memory without hurting the look, how PhysBone cost is calculated, whether to attach colliders to hair chains, and what to check before changing PhysBone parameters. The criteria and examples referenced by steps 3–5 of the main page are all here.

---

> → [Texture tiering: criteria, tools, and six pitfalls](textures-and-physbones/texture-tiering-criteria-and-pitfalls.md) —— `tex_tier_plan.py` and the three criterion pitfalls it smooths over (cap ≠ actual size, transitive closure is required, the total is only an upper bound).

## Textures: check format first, then size

**Uncompressed is 4 bytes/pixel, DXT5 is 1 byte —— one format mistake is worth dozens of textures.**
> Measured: of 208 MB, **170 MB came from four 2048² RGBA32 textures**.

**You must check the `DefaultTexturePlatform` entry, not just the platform overrides.**
Those four had their Standalone override set to “Automatic”; looking only at that, you would think all was fine; **the hard-coded RGBA32 was in the default platform entry**.
Moreover, when Light Limit Changer generates clones it reads the **source texture's import settings**, so **the root cause is always in the source texture**.

**Tiering** (tiers must be set per the project's actual situation; do not copy blindly):
- Keep main atlases at 2048
- Mask / normal / emission / highlight / MatCap / reflection cubemaps go down to 1024 or lower
- File names containing `mask`/`normal`/`emission`/`highlight`/`matcap`/`alpha`/`reflection` are almost always these
- **A single 1024 Cubemap takes 16 MB**

> → The three pitfalls you will hit (allowlist for main textures / judge by shader property / only explicitly named ones may be raised) are in [Texture tiering: criteria, tools, and six pitfalls](textures-and-physbones/texture-tiering-criteria-and-pitfalls.md).

## Measured gains (Project A, a heavy project with 8 outfits)

| Stage | Texture memory | Rating | Notes |
|---|---|---|---|
| Initial | 254.4 MB | VeryPoor | All 2048, some 4096 |
| AAO TraceAndOptimize attached | 226.8 MB | VeryPoor | Skinned meshes 105→82, bones 1526→1180 |
| Three-tier grading | **116.4 MB** | **Poor** | All main textures kept at 2048 |

Other gains in the same round: **recoloring merge** (multiple color variants of one outfit combined into one instance + swapping the material array) saved 43 renderers;
**dead parameters changed to NotSynced** saved 8 bits; VRCFury `UnlimitedParameters` is on standby to take over automatically if installing face tracking exceeds the limit.

## Red lines for texture tiering (stated explicitly by the author 2026-09-01)

> **The most important thing is not to affect the look.**
> 2048 is acceptable for main textures. 1024 is also acceptable, but **do not use it on easily visible main textures** —— that visibly hurts the look.

Turned into executable tiers:

| Usage | Cap | Basis |
|---|---|---|
| Main textures (base color / patterns / skin / face) | **2048**, no lower | User's red line |
| Mask / normal / emission / highlight / MatCap / alpha | 1024 | Low-frequency information; the eye cannot tell |
| Auxiliary textures of very small items | 512 | Same as above |
| Reflection Cubemap | 512 | Only used for metallic reflection; not noticeable |

**Do an A/B before lowering**: render two images from the same view, compute the max pixel difference and the “proportion of pixels with difference >8”, then crop the material's
densest region, enlarge 4× and compare side by side. Measured on ANEMONE's plaid 4096→2048: max pixel difference 56/255,
pixels with difference >8 only 1.18%, all on fine white stripes —— this kind can be lowered.

**The criterion is not “how many MB saved”, it is “A/B shows no difference”.** If it saves a lot but the difference is visible, it cannot be lowered.

## Clearing dead-weight objects

The criterion is by **reference**, not by name: an object with a renderer that simultaneously satisfies
① no curve in the generated animator layers points to it or its ancestors ② no component field references it ③ it is currently inactive → dead weight.

In one round Project A cleared 7 objects / 44,189 vertices / 25 material slots
(a redundant silver prefab left after switching to material-based recoloring, a wrist accessory the client doesn't use, and ring source items left in place after being copied eight times during mounting).

**Two false positives, don't delete by mistake**:

- **SPS / VRCFury socket markers** (`_Gimmick/Gimmick_SPS/**`): referenced at build time via component configuration,
  not through animation curves, so the reference criterion cannot see them. In this order the 16 renderers total only 736 vertices; not worth the risk.
- **Placeholder objects scaled to 0** (common in vendor prefabs, e.g. `Advanced/AvatarHight`):
  enabled and active, but draw nothing. They also often carry empty material slots —— don't go “fix” them.

After deleting, always scan for empty material slots (magenta); see [Asset and material troubleshooting](../troubleshooting/asset-and-material-checks.md).

## Texture memory: find dead weight first, then tier

The order must not be reversed. **First** find textures that are “attached but unused”, **then** do size tiering.

### Criterion for dead texture slots

⚠ VRChat's Texture Memory is counted by **deduplicated texture assets**, not by material slots.
`face.png` attached to `_MainTex`/`_OutlineTex`/`_BaseMap`/`_BaseColorMap` at the same time counts only once ——
**clearing the extra slots saves nothing at all**. It only truly saves when a texture is **referenced by nothing except dead slots**.

lilToon's `_BaseMap` / `_BaseColorMap` are compatibility aliases for URP/HDRP conversion; the shader does not sample them.
On this basis this order cleared the vendor's original eye base texture (a large texture) —— it was only referenced by these two alias slots,
while `_MainTex` had long been replaced by our heterochromia eyes, and what actually renders is the heterochromia eyes; that is direct evidence the alias slots are not sampled.

**Don't judge by “clear slot → re-render → pixel-by-pixel comparison”** (I tried; two pitfalls):
- Occlusion: the `face` material is on the `Body` mesh and the face is hidden by hair; even clearing the **main texture** shows no difference → the main texture gets judged as not sampled;
- Noise: running the same configuration twice, the alias slot's max pixel difference jumps between 0 and 2 ——
  the criterion's resolution is coarser than the quantity being measured, which amounts to no criterion.

### The tiering criterion is “how large it appears in a full-body shot”

Not what it is called, nor whether it is a main texture. What was lowered in this order:

| Texture | Original | New | Reason |
|---|---|---|---|
| Nail main texture + emission mask | 2048×2 | 512×2 | Twenty nails together occupy less than 40 pixels in a full-body shot |
| Hair ribbon main texture | 2048 | 1024 | Just a ribbon on the hair (the hair itself stays at 2048) |
| Underwear base color | 2048 | 1024 | Fully covered by outerwear in the vast majority of looks |
| Nipple overlay layer (`_Main2ndTex`) | 2048 | 1024 | Only a tiny patch of the whole body UV has content |
| Reflection cubemap ×2 | 512 | 256 | Only affects highlight reflections on gems/metal |

⚠ The `Explicit` override table matches by `path.EndsWith(key)`, so **the key must include the extension** ——
in this order one entry was written as `Matcaps/Cubemap_1` (missing `.hdr`) and never matched.
After changing, check whether the log actually reports that line; don't assume it took effect.

### Things to watch when measuring

`Perf - 性能报告` run in the editor gives **pre-build** numbers. What actually determines the upload is post-build ——
use NDMF's `AvatarProcessor.ProcessAvatar(clone)` to bake a copy in the editor and measure it,
without entering Play (entering Play cuts the MCP bridge). Destroy the baked avatar after measuring.

This order's Project A after build: texture memory 153.8 → **110.6 MB** (VeryPoor → Poor),
texture list total 313.4 → 242.5 MB. Polygons 600,962 —— five outfits and three hairstyles,
so the overall rating is necessarily VeryPoor and cannot come down without deleting content; **make this clear to the client in advance**.

## PhysBones: the “rating number” and the “real per-frame cost” are two different things

VRChat's performance rating **also counts disabled components**, while the CPU only runs the active ones each frame.
For an avatar with multiple outfits, disabled components often make up more than half —— therefore:

- The **rating number** determines the badge color, but the badge is often already locked independently by polygon count / material slots, so no amount of PhysBone optimization moves it
- The **real per-frame cost** is what affects frame rate, and its denominator is only about half of the rating number

**Rule**: when reporting gains, **give both measures**, and state which one corresponds to frame rate.
Reporting only the rating number makes people think the work was wasted; reporting only real cost makes people think the badge will change.

The collision check count is computed as **Σ(affected bones per chain × colliders attached to that chain)**,
so the gain from “removing one collider” = that chain's bone count, regardless of collider size.

## Attaching body colliders to hair/tails: two geometric criteria

The correct fix for “hair passing through the body” is to attach a torso collider to the hair chains. But **don't attach blindly to all of them**:
each attached chain adds `bone count` checks per frame, and attaching the wrong ones deforms the look.

### Criterion ①: chains already **inside** the collider in the rest pose must not be attached

The moment it is attached, the chain gets pushed out and the standing look deforms immediately.
These are usually short strands hanging along the side of the neck / in front of the chest.

### Criterion ②: chains that can't reach it are not attached (wasted checks)

**Whether it can reach cannot be judged by “how close it is at rest”**:

- An ahoge is 24 cm from the chest at rest, but it is only 10 cm long —— no matter how it swings it can't touch
- Back hair isn't close at rest either, but it is 40 cm long —— it touches as soon as the head lowers

Correct criterion: **distance from chain root to collider surface < chain length (root to farthest bone) + margin**.

### Collider size: the top edge must stop below the shoulder line

Directly reusing the torso capsule the vendor provided for the tail is a common mistake —— such capsules' top edge often reaches the chin,
effectively treating the neck as torso-thick, which pushes out hair chains resting against the neck.
Define your own short one, with coverage kept below the shoulder line.

### Where to attach: it must be an **always-active** object

Existing body colliders are often attached under **toggleable parts** (tail, a particular outfit's collider group).
Once that part is toggled off, the collider stops working and the hair starts clipping again, reproducible only in specific states.
→ Create your own and attach it to the torso bone of the main armature.

### Incidentally: a chain's `radius` must not be 0

Collision is computed by **bone line + radius**. When radius≈0 the bone line sits against the skin, and the mesh still clips through.
When attaching colliders, also raise radius to a magnitude that covers the mesh thickness.

## Before changing PhysBone parameters, first confirm “how it behaves now”

Vendor hairstyles are often `gravity = 0` + `immobile = 0` + no angle limits ——
that means **no drooping at all, and the whole head of hair gets dragged into a line when walking**, not “already tuned”.

Watch for an ordering trap when changing: with `gravityFalloff = 0`, gravity **acts constantly**,
so you must **raise falloff first, then add gravity**, otherwise the standing look gets permanently flattened.

**Visual PhysBone changes can only be viewed in Play** —— the editor does not simulate.
Motions to test: rest / head down / head tilt / walking / turning in place.
