> 🌐 English translation · [中文原文](../../../开发工具/SOP/80_性能优化.md)

# 80 · Performance optimization　🤖

**The order is fixed; don't reverse it**:
```
① Produce baseline report → ② List textures one by one to find anomalies → ③ Change import settings → ④ Attach AAO → ⑤ Produce another report and compare
```

**Keep a report file for every step**; put the before and after reports into the delivery.

> → [Compressing PhysBone to 256](80-performance-optimization/compressing-physbone-to-256.md) —— 256 is a hard cap, not a rating; the build will throw; the panel counts **pre-build** numbers, so AAO's build-time merge cannot reduce it; an in-scene merge must add non-source chains to `ignoreTransforms` (missing this turns Spine/Upper_leg/LeftEye into physics bones); an empty AAO MergePhysBone makes preprocessing return false directly.

## Deterministic steps

### Step 1 · Confirm the environment is usable　🤖

**Preconditions**
- [ ] [70](70-regression-testing.md) has passed, and `回归报告.md` is on disk

**Execution**
1. Confirm the environment is usable per [02](02-environment-and-manual-intervention.md)

**Post-criteria**

| Expected | How to read |
|---|---|
| Steps 1–4 of 02 all pass | Post-criteria of each step in 02 |

**STOP**
- 02 judges “need a human” → ask for help per section 3 of 02; don't touch the project while waiting

---

### Step 2 · Produce the baseline report, measuring the delivery state　🤖

**Preconditions**
- [ ] Step 1 passed; no leftover baked clones in the scene

**Execution**
1. Bake a clone with NDMF `AvatarProcessor.ProcessAvatar(clone)`, **without entering Play**
2. Run `PerfReport.cs` (`Perf - 性能报告`) on the clone, with `基线` (baseline) in the file name
3. Record the armature height (difference in world y between the Head and Foot bones); destroy the clone

**Post-criteria**

| Expected | How to read |
|---|---|
| Every item in the “Acceptance” table has a number | Corresponding row of the report |
| **It really was the clone that was measured** | Print the target object name when generating the report (`PerfReport.cs` doesn't print it itself; log it on the calling side) |
| Clones after measuring = 0 | Hierarchy |

**STOP**
- Bake error → [Troubleshooting/Build aborted](troubleshooting/build-aborted.md)
- Measured on the source scene → void and redo

---

### Step 3 · Clear dead-weight objects　🤖

**Preconditions**
- [ ] Step 2 passed; the animator layers from [60](60-menu-and-animation-layers.md) have been generated

**Execution**
1. Scan by reference: ① no animator-layer curve points to it or its ancestors ② no component field references it ③ inactive → add to the list
2. Remove false positives (`_Gimmick/Gimmick_SPS/**`, placeholders scaled to 0), then delete; scan for empty material slots
3. Read-back verification + armature-height self-check

**Post-criteria**

| Expected | How to read |
|---|---|
| Every list item has ①②③ all true | Per-item output of the scan script |
| Empty material slots = 0 | Iterate renderers' `sharedMaterials` and count null |
| Armature height = value recorded in step 2 (diff < 1 mm) and `Animator.isHuman` | World y of Head/Foot bones |

**STOP**
- To revert → roll back precisely with `PrefabUtility.RevertPropertyOverride`, not the undo stack

---

### Step 4 · Textures: check format → clear dead slots → tier　🤖

**Preconditions**
- [ ] Step 3 passed (find dead weight first, then tier); the subpage sections “check format first”, “three pitfalls”, and “red lines” have been read

**Execution**
1. **Use a script to read the runtime true value `Texture2D.format`**; do not parse `.meta`'s `textureFormat`
   (⚠ see “Why you cannot read `.meta` to determine format” below); also read `maxTextureSize`, ignoring platform overrides
2. Only clear textures “referenced by nothing except dead slots”
3. Tier with `tex_tier_plan.py` → review CSV → `tex_tier_apply.py` (only lower, never raise; keep rollback); handle compression format separately based on runtime readings. The old `TexOptimize.cs` is only a reference for format handling
4. Enable Mip Streaming with `FixMipStreaming.cs`
5. For conspicuous textures to be lowered, do an A/B first and submit the images to `agy_panel.py` for review (criteria in the subpage's red lines); don't make visual conclusions yourself
6. Read-back verification + armature-height self-check

**Post-criteria**

| Expected | How to read |
|---|---|
| Count of uncompressed formats (`RGBA32` / `ARGB32` and the like) == 0 | **Script reads `Texture2D.format`**, not `.meta` |
| `streamingMipmaps: 1` = all | Re-read `.meta` (this field really is in `.meta`) |
| Every entry in the review CSV has a result, zero failures | apply report and rollback record |
| Main textures `maxTextureSize` ≥ 2048 (exceptions must state their basis: share of the full-body shot); others ≤ original value | `.meta` before/after comparison |
| A/B: no visible difference identified by ≥2 models | `agy_panel.py` output |

**STOP**
- Texture memory rises instead → back to the subpage's “three pitfalls”; A/B difference identified by ≥2 models → don't lower

> → [Why you cannot read `.meta` to determine texture format](80-performance-optimization/why-meta-cant-tell-format.md) —— `textureFormat` in `.meta` is mostly -1 (Automatic), so counting RGBA32 by it always gives 0; write a probe to read the runtime `Texture2D.format`; a normal map's DXT5nm must not be converted to DXT1 as if it were ordinary DXT5.

---

### Step 5 · Attach AAO, then tighten PhysBone / AABB　🤖

**Preconditions**
- [ ] Step 4 passed and has its own report (land only one change at a time)

**Execution**
1. Attach Trace And Optimize with `FitAAO.cs`, default settings (`allowShuffleMaterialSlots` / `optimizeTexture` on by default); produce a report as in step 2
2. Continue only if PhysBone or AABB exceeds the cap table: use `PhysBoneTools.cs`·PhysBoneCensus / `PhysBoneTools.cs`·DumpPhysBones / `AvatarDump.cs`·DumpBounds to find where to start
3. Land only one change at a time: `PhysBoneTools.cs`·DedupePhysBones → the four merge tools → `FixAPSBounds.cs`; hair-chain colliders and PhysBone parameters follow the subpage criteria; judge the look only in Play
4. Read-back verification + armature-height self-check

**Post-criteria**

| Expected | How to read |
|---|---|
| No Error-level NDMF logs in the Console | Filter Console by Error |
| Bones / blend shapes / skinned meshes ≤ baseline; polygons = baseline | This step's report vs baseline |
| PhysBone ≤ 256 and duplicates = 0; AABB ≤ 5×6×6 m | Output of the three scripts (counted on the clone) |
| Gains reported in both measures | This step's report |

**STOP**
- Build aborted → [Troubleshooting/Build aborted](troubleshooting/build-aborted.md)
- Look deformed / rest pose pushed out → roll back with `PrefabUtility.RevertPropertyOverride`

---

### Step 6 · Produce another report, compare, and write delivery notes　🤖

**Preconditions**
- [ ] Steps 3–5 each have a report

**Execution**
1. Produce a report as in step 2, with `优化后` (optimized) in the file name; compare each item against the baseline and write one sentence explaining every difference
2. Put both reports into the delivery; if the rating is still VeryPoor because of polygon count → state this clearly in the delivery notes (see “Multiple outfits” below)

**Post-criteria**

| Expected | How to read |
|---|---|
| All five rows of the “Acceptance” table pass | Both reports + regression screenshots |
| No row in the difference table lacks an explanation | Difference table |

**STOP**
- Any difference can't be explained → don't deliver; split stacked changes and rerun
- Platform-override changes can't be verified in the editor → mark the report “this item not verified on a real device”

---

## A real gain (measured on v1.1)

| Item | Baseline | Optimized | Method |
|---|---|---|---|
| Texture memory | 208.4 MB | **92.4 MB** | Changed import settings (**halved without reducing size**) |
| Bones | 758 | 588 | AAO default settings |
| Blend shapes | 536 | 157 | AAO |
| Skinned meshes | 64 | 51 | AAO |
| Polygons | 391,865 | 391,865 | **AAO does not reduce polygons** |

## AAO

The default settings are very effective, but `allowShuffleMaterialSlots` and `optimizeTexture` **are on by default**,
so during regression **specifically look for material misassignment and texture seams**.

Misconfiguration **aborts the build outright** → [Troubleshooting/Build aborted](troubleshooting/build-aborted.md).

## PhysBone / AABB caps

| Item | Cap | Tool |
|---|---|---|
| Total PhysBones | 256 | `PhysBoneTools.cs`·PhysBoneCensus counts by top-level child object to find where to start |
| Collision check cost | — | `PhysBoneTools.cs`·DumpPhysBones lists affected bones × colliders per bone |
| Duplicate PhysBones | 0 | `PhysBoneTools.cs`·DedupePhysBones (delete only after **field-by-field comparison** confirms redundancy) |
| AABB | 5×6×6 m | `AvatarDump.cs`·DumpBounds finds the renderer blowing it up (**particle systems especially**) |
| APS handle pushes AABB to 9.6 m | — | `FixAPSBounds.cs` |

The four entry points for merging PhysBones (all in `PhysBoneTools.cs`), chosen in increasing order of precision:
MergePhysBoneGroups (find mergeable sibling groups) → MergePhysBoneExplicit (explicitly named) →
HardMergePhysBones (true edit-time merge, five gates) → ShedPhysBones (change the target table)

## Avatars with multiple outfits are necessarily VeryPoor; this is normal

The PC polygon Poor threshold is 70k; four outfits + three hairstyles total 390k polygons.
The only way down is **reducing polygons**, which means modifying the client's own assets and **requires the client's approval**.
**Explain this clearly in the delivery notes**, so the client doesn't think something was done wrong.

## Mip Streaming

VRChat **mandates** it; the build errors if it's not enabled. `FixMipStreaming.cs` enables it in bulk.

## Acceptance

| Item | Criterion |
|---|---|
| Texture memory | Optimized < baseline; and no RGBA32 default platform entries remain |
| PhysBone | ≤ 256, with no duplicates |
| AABB | Within 5×6×6 |
| Materials | After AAO runs, **recheck each item for misassignment and seams** (the cost of `allowShuffleMaterialSlots`) |
| Reports | Both before and after reports present; every difference explainable |

### Four mandatory checks (after attaching AAO, before producing the optimized report)

1. **Write thresholds as trade-offs; personal accounts must pass too**: texture thresholds (main 2048 / mask 1024 / small items 512) are not “only for commercial”; personal accounts are lowered the same way (multiple outfits are necessarily VeryPoor); do an A/B before lowering.
2. **AAO installed ≠ component attached**: `Trace And Optimize` must be on the active root; having the package installed with 0 components is a recurring pitfall.
3. **Particle bounds**: particle `bounds` blowing up the AABB (historically Milfy 9.60 m); list them with `AvatarDump.cs`·DumpBounds, don't just look at the static bounding box.
4. **An invalid `MergePhysBone` aborts the build**; **after AAO you must rerun the dead-parameter check** (AAO deletes/renames clip paths).

Criteria and examples → [What AAO actually does](80-performance-optimization/what-aao-actually-does.md), [Textures](80-performance-optimization/textures-and-physbones.md).

⚠ **Platform-override changes cannot be verified in the editor**; see measure ① “platform override vs default tier” in [Observation measures](troubleshooting/observation-criteria.md) (for the current review method see [70](70-regression-testing.md)).

## Subpage index

| Subpage | When to open |
|---|---|
| [Textures and PhysBones](80-performance-optimization/textures-and-physbones.md) | Before starting steps 3–5: check format first then size, three pitfalls, A2BD measured gains, red lines and A/B, dead weight and dead texture slots, PhysBone rating vs real cost, geometric criteria for hair-chain colliders, check current state before changing PhysBone parameters |

---

> → [The three things AAO actually does](80-performance-optimization/what-aao-actually-does.md) —— deletes “always off” renderers (how to verify safety via clip references), UV repacking and single-color 1×1 (main cause of the texture memory drop), merging skinned meshes; cite the correct before reading in the before/after table.

**Rule**: for every number in a report, state **which file snapshot it was taken from**; don't take it from a scrolling log by memory.
