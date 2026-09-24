> 🌐 English translation · [中文原文](../../开发工具/README.md)

# Project knowledge base

> Technical assets reused across orders. **Indexed along three dimensions — base avatar / asset pack / general tools — not by client.**
> What the next order will look for is "how to handle Kipfel", "how to handle Hollow", "how to measure performance", not "which client's order was that".

Toolchain baseline: `Unity 2022.3.22f1 · VRChat SDK 3.10.4 · Modular Avatar 1.17.1 · NDMF 1.14.1 · AAO 1.9.16 · lilToon 2.3.4 · Blender 5.2`

---

## Directory

```
开发工具/
├─ README.md                    ← you are here (tool and asset index)
├─ SOP/                         work procedures, enter from SOP/00_总表.md
├─ _工具链基准.md                frozen VPM package versions
├─ _导出规格.md                  spec for rewriting the SOP into a public tutorial (not executed)
├─ 素材包说明.md + 素材包说明/    indexed by asset pack: how to install and pitfalls
├─ 通用工具/                     independent of base avatar, usable on any order as-is
├─ 菜单架构/                     structure is portable; for another base avatar edit three tables
├─ 素体_Kipfel（まめふれんず）/
│   ├─ 素体说明.md               ★ all known facts about this base avatar
│   ├─ 脚本/                     fitting scripts, bound to specific asset packs
│   ├─ 面部图集/                 compositing recipes + recipe dependency files
│   └─ 参考图/                   basis for judgments and before/after comparisons
├─ 数据报告/                     baseline data, for comparison when making similar judgments
└─ 版本历史/                     git bundle (33 commits)
```

Every script's file header marks: **applicable base avatar / related assets / toolchain version / reusability rating / purpose**.

---

## Reusability rating

| Rating | Meaning | Files |
|---|---|---|
| ★★★ | Works as-is on another order | 8 in `通用工具/` (see table below) |
| ★★ | Usable after editing the constant tables at the top | `通用工具/TexOptimize.cs` `TrimDeadParams.cs` `TraceParam.cs`, 3 in `菜单架构/`, most of `素体_Kipfel/脚本/`, 4 in `面部图集/` |
| ★ | Only useful as a reference for the approach | `ApplyEyePack.cs` `TuneEyeColor.cs` `Colorway.cs` |

> **2026-08-28 correction**: previously marking all of `通用工具/` as ★★★ was **wrong** — `PerfReport.cs`,
> `FitAAO.cs`, and `TexOptimize.cs` all hard-coded `const string AvatarName = "Kipfel"`,
> and in another project they immediately reported "Kipfel not found". All have now been changed to **auto-detection** (taking the currently selected object or the
> active `VRCAvatarDescriptor` in the scene), and only now truly deserve ★★★.

## General tools at a glance

| File | Rating | Purpose |
|---|---|---|
| `PerfReport.cs` | ★★★ | Performance report via VRChat's official rating API + polygon distribution grouped by top level |
| `AvatarDump.cs`·DumpRenderers | ★★★ | Lists each renderer's material slots and main textures |
| `FixMipStreaming.cs` | ★★★ | Batch-enables Mip Streaming (required by VRChat; build errors without it) |
| `FitAAO.cs` | ★★★ | Attaches AAO TraceAndOptimize via reflection and dumps private settings |
| `PhysBoneTools.cs`·DumpPhysBones | ★★★ | Lists affected bone count × collider count for each PhysBone, locating the source of collision check cost |
| `PhysBoneTools.cs`·DedupePhysBones | ★★★ | Finds duplicate PhysBones on the same object; deletes only after **field-by-field comparison** confirms redundancy |
| `ParamAudit.cs` | ★★★ | Parameter audit: how many bits each parameter uses, whether it's in the menu, whether it's in an animator layer |
| `SceneViewShots.cs` | ★★★ | Reproducible A/B comparison camera positions located by bone coordinates |
| `PlayTest.cs` | ⚠ | Animator layer logic regression (including a record of two dead ends); **testing is incomplete, must not be reused directly**, see the note above |
| `TexOptimize.cs` | Historical sample | The old filename-classification method is retired; the current entry point is `tex_tier_plan.py` → review CSV → `tex_tier_apply.py`, with readback and rollback per SOP80 |
| `TraceParam.cs` | ★★ | Traces what a parameter actually drives, checks whether target objects/blend shapes still exist |
| `TrimDeadParams.cs` | ★★ | Removes dead parameters (edit the parameter name table per base avatar; copy the asset before editing, leave vendor originals untouched) |
| `PhysBoneTools.cs`·PhysBoneCensus | ★★★ | Inventories PhysBones per top-level child object, finding where to cut to meet the 256 limit |
| `AvatarDump.cs`·DumpBounds | ★★★ | Finds renderers that push the AABB beyond the 5×6×6 limit (particle systems are especially prone) |
| `FindDupComponents.cs` | ★★★ | Finds/deletes duplicate singleton NDMF components (attaching two makes the plugin throw and abort the build) |
| `BuildBlockerScan.cs` | ★★★ | Scans MA MergeAnimator null references + idle/duplicate PhysBones |
| `FixAaoMergePhysBone.cs` | ★★★ | Health-checks AAO MergePhysBone, deletes invalid configurations that would abort the build |
| `PhysBoneTools.cs`·HardMergePhysBones | ★★★ | Edit-time true merge of PhysBones with the same parent and same settings (five gates; skipped if not satisfied) |
| `PhysBoneTools.cs`·MergePhysBoneGroups | ★★★ | Finds mergeable sibling PhysBone groups and attaches AAO MergePhysBone |
| `PhysBoneTools.cs`·MergePhysBoneExplicit | ★★★ | Uses componentsSet to name exactly which ones to merge |
| `FixAPSBounds.cs` | ★★ | Fixes AvatarPoseSystem handles pushing the AABB up to 9.6 m |
| `PhysBoneTools.cs`·ShedPhysBones | ★★ | Edit the target table at the top: merge a group of bang bones / strip PhysBones from dangling accessories |

**Parameter audit and tracing must be run in Play mode** — at edit time you can't see the part generated by MA / MapleCloset / VRCFury
at build time. Measured on Milfy for 300: at edit time 24 parameters, 108 bits; after build 92 parameters, 177 bits.

---

## Where to start looking

| What I want to do | Look here |
|---|---|
| Take a new Kipfel / まめふれんず order | Read `素体_Kipfel/素体说明.md` through once |
| Judge whether a piece of clothing can be worn | `素体_Kipfel/素体说明.md` §1 (compare bone names, don't look at file names) |
| Build an outfit-switching menu | `菜单架构/MenuGen.cs`, edit the three tables `Slots` `Accessories` `SlotVendorParam` |
| Body shrink keys to prevent clipping | `菜单架构/ShapeBinding.cs` (MA Shape Changer bound on the clothing) |
| Measure performance / optimize | `通用工具/PerfReport.cs` to set a baseline → `tex_tier_plan.py` to produce a plan → review CSV → `tex_tier_apply.py` to apply and save rollback → reimport/measure; for AAO trade-offs see `SOP/80_性能优化.md` |
| Installed an asset pack and don't know how to hook it up | `素材包说明.md` |
| Work by the process | `SOP/00_总表.md` |
| Change the face texture | `素体_Kipfel/面部图集/build_face_tex.py` (dependency files in `配方依赖/` in the same directory) |
| Verify animator layer logic | ⚠ Procedure pending rewrite, see the top of `SOP/70_回归测试.md` |
| See how a decision was judged at the time | `素体_Kipfel/参考图/` + `数据报告/` |

---

## Things not to look for here

- **How to investigate an aborted build** → `SOP/问题定位/构建被中止.md`
- **Hard rules that run throughout** (drive parameters, don't touch the mesh / imported ≠ used / observation conventions / self-check before saving / don't act before the cause is confirmed) → `SOP/00_总表.md`
- **Regression testing**: the methods of `PlayTest.cs` and `SOP/70_回归测试.md` were judged on 2026-09-18 to be **incomplete testing** (body blend shape adaptation to outfits wasn't caught), usable only as samples that include both positive and negative cases

---

## Provenance

The technical content is compiled from one complete customization of the Kipfel base avatar (33 commits),
plus experience from earlier orders such as Rurune (IKUSIA). Client and order information has been deliberately stripped.
