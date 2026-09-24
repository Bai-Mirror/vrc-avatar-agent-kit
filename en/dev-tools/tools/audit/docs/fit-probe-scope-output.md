> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/fit-probe-scope-output.md)

# T2 Fit Probe · v3 Coverage Scope, Output, Performance <!-- nav -->

> Formerly: T2 (originally `审查/README_T2.md`) §4.6 / §5 / §6. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Previous: [T2 Fit probe · algorithm and criteria (7–10), v2 exclusions and rejections](fit-probe-algorithm-2.md) · Next: [T2 Fit probe · self-check 1: API signatures](fit-probe-selfcheck-api.md) <!-- nav -->

## 4.6 v3 coverage scope (region scope / `out_of_scope`)

**Problem**: `sailor` (sailor-suit top) was recorded as `pierced` on 109 RightHand and 60 RightThumb* body vertices — the hand is
outside the cuff and was never within the top's coverage scope. The old version counted any “outward ray hitting a back face / inward ray hitting a front face” as coverage, so hanging geometry like cuffs and
hems falling within the 25 mm range would wrongly pull in hand/leg vertices; `loafer` pierce_ratio 0.42 and `bag` 1.0
are very likely the same kind.

**Criterion** (computed once per clothing piece, before ray statistics):
1. Read the main bone of each vertex of the clothing's **own mesh** (the highest-weight bone; prefer `GetBonesPerVertex/GetAllBoneWeights`,
   falling back to `Mesh.boneWeights`).
2. The main bone is merged into a region via the parent-chain mapping of item 1.5 in §4 (the same mapping as for body vertices).
3. Compute each region's share of the clothing's vertex count; **regions with share ≥ `region_min_share` (default 0.02)** form the clothing's
   covered region set; output `coverage_regions` (`region`/`vertices`/`share`) and `region_source`.
4. In the main probe, if a body vertex's region isn't in the set but the ray produced a hit (at least one of `covered_inside` or `pierced`) →
   not counted in `covered`/`pierced`/`rejected_*`, counted as `out_of_scope` (per piece `total.out_of_scope` +
   per region `out_of_scope`, kept in the output for checking). Vertices without any hit aren't counted (otherwise every clothing piece would have tens of thousands).

**Trade-offs**:
- Use the clothing's own skinning, not a common bounding box or tags: skinning is the direct evidence of “where this garment is designed to enclose”.
- The 2% threshold blocks the very few vertices on cuffs/hems driven by finger bones; when all regions of a clothing piece are < the threshold, fall back to “all regions that appear”
  and write `warnings`.
- When the clothing region set and the body region set are **completely disjoint** (the two parent-chain mappings don't line up, e.g. the clothing comes with its own armature), the scope
  limit is dropped, `region_source="map_mismatch"`, to avoid zeroing out the whole piece; `warnings` will name it.
- Non-skinned meshes (`MeshRenderer` without bones) and meshes with Read/Write off can't be judged: `region_source=no_bones` /
  `unreadable_weights`, likewise no scope limit (keeping the old behavior). When you see these values, know that the piece's `covered`/`pierced`
  still include old-convention false positives.
- `region_min_share` only affects “which regions count as covered”; it doesn't change the geometric criterion of the rays themselves.

---

## 5. Output

`<out>/geo_<state_id>.json` (**pretty-printed, key order = the order below, byte-for-byte identical across two runs**):

> **v4 (task AA / 04 T-10) two changes**: ① the output file name changed from `fit_<state_id>.json` to `geo_<state_id>.json`
> (the unified naming of `03c` L3; T-14 reads `geo_*.json`); ② when the request says `"poke": true` or `"poke": {…}`, a top-level `poke` block is appended after
> `params` = T-28a static pierce patches (shell signed depth × connected patch area, the main geometric criterion).
> Fields, thresholds and Unity acceptance are in the main `README.md` §3.2.5; T2's existing distance/foot-shoe metrics are kept, and `poke` is a parallel block.


```json
{
  "avatar": "Kaguya-...",
  "avatar_path": "Kaguya-...",
  "state_id": "default",
  "body_path": "Body",
  "body_vertex_count": 51234,
  "body_vertex_used": 50410,
  "weights_source": "bone_weights",
  "mode": "play",
  "ray_backend": "raycast_command",
  "excluded_vertices": {"nanimated": 780, "non_finite": 0, "zero_weight": 44},
  "region_bone_examples": {"LeftFoot": ["Foot_L$Toe_L$85", "Foot_L_Const", "Toe_L"], "Hips": ["Hips"]},
  "calibration": {"hit_normal_usable": true, "winding_sign": 1, "detail": "..."},
  "params": {},
  "garments": [
    {"path": "Outfit/Skirt", "material_names": ["M_Skirt"], "vertex_count": 8123,
     "skipped": false, "skip_reason": null,
     "region_source": "bone_weights", "region_share_min": 0.02,
     "coverage_regions": [{"region": "Hips", "vertices": 7300, "share": 0.899},
                          {"region": "LeftUpperLeg", "vertices": 400, "share": 0.049}],
     "total": {"covered": 12000, "pierced": 340, "coverage": 12100, "pierce_ratio": 0.0281,
               "max_depth_mm": 6.2, "p95_depth_mm": 4.1, "depth_saturated": false,
               "rejected_through_body": 12, "rejected_opposite_normal": 7, "out_of_scope": 55},
     "regions": [{"region": "Hips", "covered": 900, "pierced": 120, "coverage": 950,
                  "pierce_ratio": 0.1263, "max_depth_mm": 6.2, "p95_depth_mm": 4.4,
                  "depth_saturated": false, "rejected_through_body": 0, "rejected_opposite_normal": 0,
                  "out_of_scope": 0}]}
  ],
  "feet": [
    {"side": "Left", "garment_path": "Outfit/Shoes", "class": "footwear", "class_source": "geometry",
     "class_detail": "脚底下方厚度 p50 >= sole_min_mm", "thickness_p50_mm": 9.3, "thickness_count": 430,
     "foot_verts": 610, "sole_verts": 430,
     "signed_mm": {"p05": -1.2, "p50": 0.8, "p95": 4.0}, "signed_count": 420,
     "below_sole": 18, "floating_gt5mm": 12, "heel_p50_mm": -0.4, "heel_count": 41,
     "toe_pierced": 3, "toe_checked": 60, "shape_keys": {"Foot_Size": 100}},
    {"side": "Left", "garment_path": "Outfit/Socks", "class": "legwear", "class_source": "geometry",
     "class_detail": "脚底下方厚度 p50 < 2mm（贴身）", "thickness_p50_mm": 1.1, "thickness_count": 430,
     "foot_verts": 610, "sole_verts": 430,
     "covered": 430, "pierced": 5, "coverage": 435, "pierce_ratio": 0.0115,
     "gap_avg_mm": 0.9, "gap_count": 430, "shape_keys": {"Foot_Size": 100}}
  ],
  "markers": [{"pos": [0.01, 0.82, -0.03], "region": "Hips", "garment": "Outfit/Skirt",
               "depth_mm": 6.2, "vertex": 12345}],
  "body_candidates": [
    {"path": "Body", "vertex_count": 51234, "has_foot": true, "has_torso": true,
     "selected": true, "regions": ["Chest", "Head", "Hips", "LeftFoot", "LeftLowerLeg", "Spine"]}
  ],
  "warnings": [],
  "timings_ms": {"bake_body": 40.1, "bake_garments": 380.5}
}
```

- `params` is the request object embedded verbatim (the example uses `{}` to omit its contents). In a real run it's the full request.
- `excluded_vertices` / `body_vertex_used` / `region_bone_examples` and every
  `rejected_*` / `depth_saturated`, `coverage`, `signed_count`, `toe_checked`, `foot_verts`, `sole_verts`,
  `body_candidates`, `warnings`, `calibration`, `weights_source`, `mode`, `ray_backend`
  are **diagnostic extra fields** beyond the task brief; criteria in 4.5.
- **New fields in v3**: per clothing piece `region_source` / `region_share_min` / `coverage_regions` and
  `total.out_of_scope`, per region `out_of_scope` (criteria in §4.6); per `feet[]` entry
  `class` / `class_source` / `class_detail` / `thickness_p50_mm` / `thickness_count` (criteria in item 7 of §4).
- **The `feet[]` structure changed in v3**: v2 was “one entry per foot, reporting only the one clothing piece with the most coverage, and only sole metrics”; v3 is
  “one entry for each foot × each clothing piece covering that foot”. Entries with `class=footwear` have `signed_mm`/`below_sole`/
  `floating_gt5mm`/`heel_*`/`toe_*`; entries with `class=legwear|other` **don't have** these sole fields, only
  `covered`/`pierced`/`coverage`/`pierce_ratio`/`gap_avg_mm`/`gap_count`. Consumers read by branching on `class`.
- `thickness_p50_mm` is `null` (JSON `null`) when there's no geometric data.
- `body_candidates` in v2 is an array of objects (`path` / `vertex_count` / `has_foot` / `has_torso` / `selected` / `regions`);
  the old version was an array of strings.
- Clothing with `skipped=true` (invisible / mesh with Read/Write off) has `total` all 0 and empty `regions`,
  with `skip_reason` explaining why.
- `status.json` is written uniformly by AuditIO's `AuditStatus` (including `tool`/`time`); while running, T2 updates per piece
  `progress="3/10"`, `message=衣物路径` (clothing path).
- **The scene is not marked / not saved** (temporary changes in Play mode are lost on exiting Play).

---

## 6. Performance estimate (estimated, not measured)

- 100k body vertices, 10 clothing pieces → main probe `2 × 10万 × 10 = 200 万` (2 × 100k × 10 = 2 million) rays, plus v2 body hits
  `2 × 10万 = 20 万` (2 × 100k = 200k) rays (computed only once); in Play mode `RaycastCommand.ScheduleBatch` parallelizes at 32 rays per job.
  The whole round (including cooking 11 MeshColliders + 10 BakeMesh calls) takes **about 5~25 seconds**; the bulk is rays and collider cooking.
  The body is a non-convex MeshCollider, slightly more expensive to cook, but built only once.
- Non-Play mode (if `RequiresPlayMode` is changed to false or Probe is called directly) falls back to per-ray `Physics.Raycast`,
  taking **about 1~3 minutes** at the same scale. That's why this tool requires Play mode.
- Additional v3 overhead: sole thickness uses per-ray `Physics.RaycastNonAlloc` (sole vertex count × 2 sides × clothing piece count; on Project A
  about `645 × 2 × 10 ≈ 1.3 万` (≈ 13k) rays, with an extra round of upward rays for some clothing), negligible relative to the main probe (< 1 second order);
  clothing skinning region statistics are one linear scan per piece.
- Memory: temporary arrays about `O(2 × 顶点数)` (O(2 × vertex count); about 20~25 MB for 100k vertices), plus one copy of vertices/normals for the body collider
  (about `2 × 顶点数 × 12 B`); each clothing piece is released after use; Play mode's own 10 GB+ footprint is unrelated to this tool.

---
