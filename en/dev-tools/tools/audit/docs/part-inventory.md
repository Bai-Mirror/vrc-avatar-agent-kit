> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/part-inventory.md)

# T-05 Part inventory export AuditPartInventory · scope and basis <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) §11 / §11.1. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [T1/T3 known limitations](known-limits.md) · Next page: [T-05 part inventory · output skeleton](part-inventory-output.md) <!-- nav -->

## 11. T-05 Part inventory export `AuditPartInventory`

> File: `unity/Editor/AuditPartInventory.cs` (T-05). An **edit-mode** menu action; it does not go through `request.json` / the state-machine pump.
> Menu: `Tools/AvatarAudit/Export Part Inventory` (priority 110). You can also call
> `AvatarAudit.AuditPartInventory.Export(null)` in `execute_code` to get the written path.
> Output: `<工程>/_感知/out/inventory.json` (directory created automatically); progress is also written to `status.json` in the same directory.
> Read-only: no MarkSceneDirty, no asset changes, no temporary objects (the temporary Mesh from `BakeMesh` is `DestroyImmediate`d after use).

### 11.1 Scope and basis

- **Only active roots are inventoried**: `Resources.FindObjectsOfTypeAll(VRCAvatarDescriptor)` filtered to `activeInHierarchy` and not prefab assets;
  **all** `SkinnedMeshRenderer` and `MeshRenderer` under a root (including inactive hidden parts) are output, sorted separately by path relative to the avatar root,
  and written into `renderers[]` in turn; `ParticleSystemRenderer` is **counted only, not expanded**. Renderer entries are distinguished by `type`.
- **Region mapping (SMR)**: walking up the parent chain, the first `HumanBodyBones` encountered is that bone's region (same logic as T2 §4.6; when no humanoid
  Animator is available, falls back to the raw bone name). **MA MergeArmature outfit bones are mapped via `mergeTarget` + bone name** (task B-补-18, BF rework):
  `RegionMapper` calls MA's `GetBonesMapping()` via reflection (returns `(baseBone, mergeBone)` pairs), maps the outfit bone to the
  avatar humanoid bone it will be merged into, then takes the region; decorative bones (shoe chains, bows) walk the parent chain to the nearest mapped bone. **When identity matching fails, it falls back to bone names**
  (task AY, B-补-03): common spellings such as `Foot.L` / `Foot_L` /
  `Lower_leg.L` / `Toe.R` / `leftfoot` map to humanoid regions such as `LeftFoot` / `LeftLowerLeg` / `LeftToes`;
  when a decorative bone (`Shoes_Chain.001.L`) isn't recognized, it keeps walking up the parent chain (settling via `Foot.L`), and only records `Other` if still unrecognized.
  *Why*: imported outfits/accessories often carry their own independent armature, whose bones are not the avatar's humanoid Transforms, so identity matching lands wholesale on `Other`,
  and the sole thickness becomes `null` as a result (Project B lop-eared rabbit `Shoes`); the `covers` of MA-merged parts (e.g. `08_WhitePink_Milfy_MA/Shoes`)
  are also wholesale `Other`, and `key_gaps` can't be judged. Priority: MA mapping > identity matching > bone-name fallback.
  `region_weights` = share of skin weights; `region_vertex_share` = share of vertices by dominant bone,
  `covers` = regions where the latter share ≥ `region_share_min` (0.02). Three tiers for reading weights: `GetBonesPerVertex/GetAllBoneWeights`
  → legacy `Mesh.boneWeights` → nearest-bone approximation when unreadable; `region_source` indicates which tier was used.
- **Region approximation (MR, task AQ)**: MeshRenderer has no skin weights, so instead the `MeshFilter.sharedMesh` vertices are transformed to world space and the
  **nearest bone** is found (candidates prefer the full set of humanoid bones, falling back to body SMR bones, then all SMR bones), taking its region. With vertices →
  `region_source="nearest_bone"`; mesh without Read/Write enabled (MR can't `BakeMesh`) → falls back to the single point of the object's position →
  `region_source="nearest_bone_object"` (a single region at full share; coarse but not empty). Neither is skin weights; tell them apart via `region_source`.
- **`part_like` (task AQ)**: if the name or any ancestor name (up to the avatar root) contains an exclusion substring → `false`, otherwise `true`; both SMR and MR
  have it. The exclusion table is `PartLikeExcludeTokens` in the file header (configurable; changing the table changes the criterion; `inventory.part_like_rule` also records a copy):
  `PCS Preview Icon` / `AreaShow` / `AvatarHight` / `APS_` / `Timer` / `功能_` / `SpsScreenMarker`.
  This judges "is it a tool/preview/debug object", looks only at names, is case-insensitive, and **does not replace human review** — a real part wrongly excluded only affects the readability of the MR list,
  while a missed exclusion makes a person look once more; the trade-off is to prefer wrongly excluding over wrongly letting through; in the Project A measurement, about 50 of 58 MRs were AreaShow/SPS
  markers/plugin timers, etc.
- **Counts (task AQ)**: the root and each avatar each write `smr_count`/`mr_count`/`psr_count`; the old `renderer_count` is kept,
  value = `smr_count + mr_count` (= length of `renderers[]`, consistent with the old basis; PSR not expanded).
- **`body_keys` (task AQ)**: each avatar writes **all** blend shape names of the body SMR (in `GetBlendShapeName` order, not sorted or deduplicated),
  plus `body_key_count`; an empty list when the body isn't identified. Used by `perception/profile_keys.py` to write the base avatar profile's `all_keys:`.
- **Closedness**: after welding triangle vertices by position (1e-5 m), edges used by only 1 triangle ÷ number of unique edges =
  `boundary_edge_ratio`; `closed = ratio ≤ 0.10`. Source of 0.10: offline calibration in Blender on Project A meshes;
  MMN `Shoes` after triangulation 3.7%, `Socks` 1.0%, flat cloth pieces 29%+; 10% tolerates shoe openings/cuffs while still blocking pure planes.
- **Sole thickness heuristic**: lowest world Y of the body's foot vertices (the body = contains both feet and torso, visible, most vertices) − lowest world Y of this part's foot vertices;
  `shoe_like = sole_thickness_mm ≥ 4` (`03a` S6). Edit mode builds no colliders and casts no rays; this is a **heuristic**, not a T2-precision value.
  Body identification and region mapping are now shared with T-10 / T2 via `AuditBodyPick` (task AY); after imported outfits' own armatures fall back to bone names,
  the `Shoes` of Milfy-type outfits are no longer `Other`, so that part now has `sole_thickness_mm` (B-补-03).
- **Switch method**: scans the descriptor's `baseAnimationLayers` + `specialAnimationLayers` and the controllers of all
  MA MergeAnimators under the avatar, extracting `m_Enabled` / `m_IsActive` curves clip by clip. For MA MergeAnimator with
  `pathMode: Absolute` (the two A2_FX mergers in Project A), paths are already relative to the avatar root and used directly;
  for `Relative`, the avatar-root-relative prefix is prepended according to the host/`relativePathRoot`. `switch.method` takes values
  `m_Enabled | m_IsActive | none`; **when both exist, `m_Enabled` is recorded**; the three flags `by_enabled`/`by_active_self`/
  `by_active_ancestor` and `sources[]` (clip/asset path/source controller) are all present for T-04's detailed judgment.
  Project A's `kaguya_cloth/outer` is written to activeSelf by the whole-outfit radial and to m_Enabled by the vendor ON/OFF clip,
  so under this rule it records `m_Enabled` (the T-05 acceptance expectation).
- **P8 default and `switch.method` basis (B-补-04, signed off 09-19)**: **`switch.method` is authoritative; `by_active_self`/
  `by_active_ancestor` are only informational fields and must not be used to override `switch.method`.** `kaguya_cloth/outer` has all three flags true,
  but the vendor clip only writes `m_Enabled` and our `On_部位_外套` only writes `m_IsActive`; `byEnabled ? "m_Enabled" : …` at `AuditPartInventory.cs:615`
  prefers `m_Enabled`, so `m_Enabled` is recorded. Under the P8 default "no change", the D1/D3 candidates of `vis(kaguya.outer)`
  are written as `m_Enabled` in `DepPlan.BuildTargets` (`DepPlan.cs:1394`) per `MethodFor(path)`;
  and because of `SwitchAllActiveSelf` (`DepPlan.cs:1220-1241`: as soon as a vis part has one `m_Enabled`, the candidate is kicked out of sc),
  it **lands on the clip backend** (measured at `AJ_T06_依赖编译器.log:47`: "kaguya_cloth/outer is switched by m_Enabled per inventory
  → lands on the clip backend"; compare `kaguya.body_under_sailor`, which goes through sc). Changing P8 (`03:35`) requires changing the project and **re-exporting
  `inventory.json`**, otherwise the declaration is inconsistent with the project and it still lands on clip.
- **MA control**: reflection scans `ModularAvatarObjectToggle` (`m_objects[].Object` resolved to avatar-root-relative paths) and
  `ModularAvatarMenuItem`; only a hit on "the renderer itself or one of its ancestors" counts as control, written into `renderers[].ma`. MA visibility only lands on activeSelf
  at build time, and there is no corresponding curve at edit time, so it is a separate column outside `switch`.
