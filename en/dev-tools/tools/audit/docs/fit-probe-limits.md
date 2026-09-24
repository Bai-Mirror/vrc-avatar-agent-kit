> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/fit-probe-limits.md)

# T2 Fit Probe · Known Limitations and First-Run Checks <!-- nav -->

> Formerly: T2 (originally `审查/README_T2.md`) §10. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Previous: [T2 Fit probe · self-check C and v3 regression checklist](fit-probe-selfcheck-2.md) <!-- nav -->

## 10. Known limitations / key checks for Claude's compile and first run

**Things that can't be verified without opening Unity and need confirmation on the first run:**

1. **Whether `BakeMesh(mesh, true)` + `localToWorldMatrix` double-scales**: for bodies/clothing with `lossyScale != 1`,
   confirm world coordinates are correct (measure a mesh of known size, or temporarily print the body bounding box diagonal and compare with what's measured in the editor).
   The rationale is in item 3 of section 4.
2. **Whether `RaycastCommand.ScheduleBatch` really works in editor Play mode**: if it throws, `ray_backend` becomes
   `physics_raycast` (significantly slower), with an explanation in `warnings`. Functionality is still correct.
3. **The actual convention of `queriesHitBackfaces` and `hit.normal`**: look at the output `calibration`. If
   `hit_normal_usable=false`, Unity flips back-face normals, and the triangle winding criterion is used instead (already calibrated and corrected).
4. **Whether `GetBonesPerVertex/GetAllBoneWeights` can be read on body meshes with Read/Write off**: if not, it automatically falls back to
   `nearest_bone`, and region statistics become coarser (`warnings` will say so). If all projects fall back, you'll need to enable Read/Write on the body mesh
   in import settings before auditing, and write that step into the SOP.
5. **Interface coupling**: this file implements `IAuditTool` against the current version of `AuditIO.cs`. If tool C later changes the signatures of
   `IAuditTool` / `AuditContext` / `AuditJson`, this file needs to follow (it errors at compile time, not silently).
6. **v2 body collider (layer 29) cooking and hits in Play**: on the first run, confirm `build_body_collider` takes a normal amount of time,
   and `warnings` has no `身体烘焙网格没有三角面` (baked body mesh has no triangles) or `排除被删除顶点后…` (after excluding deleted vertices…); also confirm the body layer has no colliders belonging to the avatar itself
   (if there are, `warnings` notes it). If the body collider wasn't built, `rejected_through_body` will be all 0, falling back to relying only on
   `rejected_opposite_normal` (results are still better than v1, but thin regions may have residue).
7. **`RaycastCommand` with commands of `distance=0`**: v2 issues neutral distance-0 commands for excluded vertices (only as placeholders,
   to keep NaN out of the batch). If the first run throws on that construct, `ray_backend` falls back to `physics_raycast`; in that case change those
   commands to not be submitted (array slicing), and functionality is unaffected.
8. **v2 `body=auto` region coverage criterion**: confirm that the `regions` of the selected `<body>` in `body_candidates` include
   both foot and torso regions; if `region_bone_examples` shows a lot of `Other`, the parent chain didn't trace up to humanoid bones (e.g.
   the Animator isn't Humanoid, or the bones hang outside the avatar root), and you should specify `body` explicitly.
9. **v3 clothing skinning region statistics**: look at each clothing piece's `region_source` / `coverage_regions`. If a piece is
   `no_bones` (MeshRenderer) / `unreadable_weights` (mesh has Read/Write off) / `map_mismatch`, it **did not**
   have scope filtering applied, and its `covered`/`pierced` are still in the old convention. Check whether `coverage_regions` agrees with the visual judgment in §9.5
   (e.g. `sailor` shouldn't include `RightHand`).
10. **v3 sole thickness rays**: look at `feet[].thickness_p50_mm`/`thickness_count`. If `thickness_count=0`,
    `Physics.RaycastNonAlloc` didn't get a single valid hit on that clothing (perhaps all sole vertices are above/outside the clothing),
    and classification falls back to name keywords, with `class_source=name` or `default` in the output. If shoes and socks are both judged the same class,
    first check whether `thickness_p50_mm` is reasonable, then consider tuning `sole_min_mm`.
11. **v3 change in how `feet[]` is consumed**: old scripts that read `feet[].signed_mm` directly will
    fail to find the key on entries with `class!=footwear` — consumers must branch on `class` first (see the note in §5).

**Declared algorithm limitations (also written in the design document):**

- For non-manifold, double-sided, or very thin clothing meshes, front/back and “passing through” judgments have errors: **go by what remains significant after comparison with positive and negative samples**;
  don't treat a single number as conclusive.
- `body=auto` v4 relies on “name candidates passing the foot+torso skinning weight check → fall back to region coverage + most vertices”: a full-body outfit SMR may also qualify;
  check `regions`/`vertex_count` in `body_candidates`, and specify `body` explicitly when necessary.
- If layer 29 (body) / 30 (clothing) are occupied by the avatar itself there will be false hits, and `warnings` will note it; changing layers requires changing both
  `AuditFitProbe.BodyLayer`/`TempLayer` and the layers used by T3 (to avoid conflicts).
- v3 coverage scope uses the **clothing vertices' main bones**, not “whether the vertex is really enclosed by fabric”: cut-out, open-front, and draped clothing
  (designed to enclose a region but with no fabric there) may still be counted as “covering that region”, requiring `covered=0` or a visual recheck.
  Conversely, stray weights that fit tightly but don't belong to that region (< `region_min_share`) are ignored.
- v3 feet output “each foot × each piece of clothing covering that foot”; with multiple layers (socks + shoes) both layers are in `feet[]`, distinguished by `class`;
  but “which one is the outer layer” isn't judged by this tool (look at `thickness_p50_mm` or the wrapping direction).
- v2's `rejected_through_body` uses “hit distance < clothing hit distance”, which naturally also vetoes cases like armpits/between fingers where
  the body occludes itself first (coverage is on the conservative side); in high-coverage scenarios, recheck by combining `rejected_*` and `markers`.
- The `zero_weight` bucket collects both kinds of invisible vertices, “total weight 0” and “more than 3 m from Hips” (the field name follows the task brief).
  The 3 m threshold only catches obvious anomalies; normal body vertices won't be wrongly excluded.
- Non-Play mode temporarily creates GameObjects, and Unity may mark the scene dirty (we **don't save and don't MarkSceneDirty**);
  the normal entry `RequiresPlayMode=true` already avoids this.
